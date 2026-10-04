"""CFR review media, canonical graphics and deterministic FFmpeg export."""
import hashlib
import json
import subprocess
import time
from fractions import Fraction
from pathlib import Path
from local_model import read, write, duration, overlay_range, validate

HERE = Path(__file__).resolve().parent

def run(args):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise ValueError(result.stderr[-3000:] or result.stdout[-3000:])
    return result.stdout

def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]))

def prepare_media(source, output, fps='30', width=1280, start=0, length=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or source == output:
        raise ValueError('Use a new media path')
    rate = Fraction(str(fps))
    if not 1 <= rate <= 120 or width % 16 or not 320 <= width <= 3840 or start < 0 or (length is not None and length <= 0):
        raise ValueError('Invalid media parameters')
    info = probe(source)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    if video.get('color_transfer') in ('smpte2084', 'arib-std-b67'):
        raise ValueError('HDR source: establish and verify an SDR tone-map before creating this proxy')
    output.parent.mkdir(parents=True, exist_ok=True)
    args = ['ffmpeg', '-v', 'error', '-nostdin', '-n', '-ss', start, '-i', source]
    if length is not None:
        args += ['-t', length]
    args += ['-map', '0:v:0', '-map', '0:a:0?', '-vf',
        f'fps={fps},scale={width}:{width*9//16}:force_original_aspect_ratio=decrease,pad={width}:{width*9//16}:(ow-iw)/2:(oh-ih)/2,setsar=1',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', '-g', str(round(float(rate))),
        '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-movflags', '+faststart', output]
    run(args)
    checked = probe(output)
    stream = next(s for s in checked['streams'] if s['codec_type'] == 'video')
    result = {'path': str(output), 'frames': int(stream['nb_frames']), 'fps': str(rate),
        'hasAudio': any(s['codec_type'] == 'audio' for s in checked['streams']),
        'originalPath': str(source), 'sourceStartSeconds': start, 'sourceProbe': info,
        'timing': 'cfr-proxy', 'mapping': 'original presentation time = sourceStartSeconds + frame / fps; resampled frames are not original frame numbers'}
    write(output.with_suffix('.media.json'), result)
    return result

def frame_image(asset, frame, fps, output):
    if type(frame) is not int or frame < 0 or frame >= asset['frames']:
        raise ValueError('Frame outside source')
    output = Path(output)
    if not output.exists():
        output.parent.mkdir(parents=True, exist_ok=True)
        # Seek to the presentation timestamp of the CFR frame, not a keyframe approximation.
        run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-ss', f'{float(Fraction(frame)/Fraction(str(fps))):.9f}',
            '-i', asset['path'], '-frames:v', '1', '-q:v', '2', output])
    return output

def render_graphics(project, directory):
    directory = Path(directory)
    entries = [{k: o[k] for k in ('id', 'component', 'props', 'placement', 'naturalHeight') if k in o} for o in project.get('overlays', [])]
    if not entries:
        return project
    request = {'canvas': {'width': project['width'], 'height': project['height']}, 'entries': entries}
    if project.get('browserChannel'):
        request['browserChannel'] = project['browserChannel']
    template_manifest = (HERE.parent / 'examples/ui-manifest.json').read_bytes()
    digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode() + template_manifest).hexdigest()[:16]
    out = directory / 'graphics' / digest
    manifest = out / 'render-manifest.json'
    if not manifest.exists():
        # Preserve an interrupted render; retry into a fresh directory.
        if out.exists():
            out = out.with_name(digest + '-' + str(time.time_ns()))
            manifest = out / 'render-manifest.json'
        request_file = directory / ('graphics-' + digest + '.json')
        write(request_file, request)
        run(['node', HERE / 'render_overlays.cjs', request_file, out])
    result = read(manifest)
    for o in project['overlays']:
        o['image'] = str(out / (o['id'] + '.png'))
    project['graphicsManifest'] = str(manifest)
    return project

def export_video(project, directory, progress=lambda value: None):
    validate(project, check_files=True)
    if project.get('needsRebuild'):
        raise ValueError('Review or timeline changes need agent reconciliation before final export')
    directory = Path(directory).resolve()
    if directory.exists():
        raise ValueError('Use a new export directory')
    directory.mkdir(parents=True)
    write(directory / 'project-snapshot.json', project)
    assets = {a['id']: a for a in project['assets']}
    fps = float(Fraction(str(project['fps'])))
    parts = []
    for index, clip in enumerate(project['clips']):
        asset = assets[clip['assetId']]
        n = duration(clip)
        seconds = n / fps
        args = ['ffmpeg', '-v', 'error', '-nostdin', '-n']
        hold = clip.get('kind') == 'hold'
        if hold:
            image = frame_image(asset, clip['inFrame'], project['fps'], directory / f'hold-{index}.jpg')
            args += ['-loop', '1', '-framerate', project['fps'], '-i', image]
        else:
            args += ['-ss', f'{clip["inFrame"]/fps:.9f}', '-i', asset['path']]
        overlays = [o for o in project.get('overlays', []) if o['clipId'] == clip['id'] and overlay_range(o, clip)[1] > overlay_range(o, clip)[0]]
        for overlay in overlays:
            if not Path(overlay.get('image', '')).is_file():
                raise ValueError('Missing rendered graphic: ' + overlay['id'])
            args += ['-loop', '1', '-framerate', project['fps'], '-i', overlay['image']]
        audio_index = 0
        if hold or not asset.get('hasAudio'):
            audio_index = 1 + len(overlays)
            args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
        filters = [f'[0:v]setpts=PTS-STARTPTS,scale={project["width"]}:{project["height"]}:out_range=tv:out_color_matrix=bt709,setsar=1,format=yuv420p,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709[v0]']
        for i, overlay in enumerate(overlays):
            start, end = overlay_range(overlay, clip)
            extra = ''
            if overlay['component'] == 'statsPanel':
                fade = min(9, (end-start)//2) / fps
                extra = f',fade=t=in:st={start/fps}:d={fade}:alpha=1,fade=t=out:st={(end-1)/fps-fade}:d={fade}:alpha=1' if fade else ''
            filters.append(f'[{i+1}:v]format=rgba{extra}[o{i}]')
            filters.append(f"[v{i}][o{i}]overlay=0:0:enable='gte(n,{start})*lt(n,{end})':shortest=1[v{i+1}]")
        filters.append(f'[{audio_index}:a]atrim=duration={seconds},asetpts=PTS-STARTPTS,aresample=48000,apad,afade=t=in:d={min(2/fps, seconds/2)},afade=t=out:st={max(0, seconds-2/fps)}:d={min(2/fps, seconds/2)}[audio]')
        part = directory / f'part-{index:04}.mp4'
        args += ['-filter_complex', ';'.join(filters), '-map', f'[v{len(overlays)}]', '-map', '[audio]',
            '-frames:v', n, '-t', f'{seconds:.9f}', '-r', project['fps'], '-c:v', 'libx264',
            '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-ac', '2', part]
        run(args)
        parts.append(part)
        progress({'state': 'running', 'completedClips': index+1, 'totalClips': len(project['clips'])})
    listing = directory / 'parts.txt'
    listing.write_text(''.join(f"file '{part.name}'\nduration {duration(clip)/fps:.9f}\n" for part, clip in zip(parts, project['clips'])), encoding='utf-8')
    target = directory / 'edited.mp4'
    # Normalize the final timestamps and codec parameters across video and JPEG holds.
    # Explicit segment durations keep AAC packet padding out of the timeline clock.
    expected = sum(duration(c) for c in project['clips'])
    run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'concat', '-safe', '1', '-i', listing,
         '-vf', f'setpts=N/({fps}*TB)', '-af', 'aresample=48000:async=1:first_pts=0',
         '-frames:v', expected, '-t', f'{expected/fps:.9f}', '-r', project['fps'],
         '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-movflags', '+faststart', target])
    result = probe(target)
    video = next(s for s in result['streams'] if s['codec_type'] == 'video')
    if int(video['nb_frames']) != expected:
        raise ValueError('Export frame count mismatch')
    report = {'state': 'complete', 'path': str(target), 'revision': project['revision'], 'frames': expected,
        'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'probe': result}
    write(directory / 'export.json', report)
    progress(report)
    return report
