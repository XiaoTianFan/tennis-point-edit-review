"""CFR review media, canonical graphics and deterministic FFmpeg export."""
import hashlib
import json
import math
import re
import subprocess
import tempfile
import time
from fractions import Fraction
from pathlib import Path
from local_model import read, write, duration, overlay_range, validate, check_export_request
from media_probe import identity
from source_binding import mapping, unchanged

HERE = Path(__file__).resolve().parent

def run(args):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise ValueError(result.stderr[-3000:] or result.stdout[-3000:])
    return result.stdout

def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]))


def run_progress(args, fps, progress):
    """Read encoded video time without buffering stderr or counting clips."""
    with tempfile.TemporaryFile(mode='w+t', encoding='utf-8') as errors:
        with subprocess.Popen([str(a) for a in [args[0], '-progress', 'pipe:1', '-nostats', *args[1:]]],
                stdout=subprocess.PIPE, stderr=errors, text=True, encoding='utf-8', errors='replace') as process:
            batch = {}
            for line in process.stdout:
                key, sep, value = line.strip().partition('=')
                if sep: batch[key] = value
                if key == 'progress':
                    if batch.get('frame', '').isdigit():
                        progress(float(Fraction(int(batch['frame'])) / Fraction(str(fps))))
                    elif batch.get('out_time_us', '').lstrip('-').isdigit():
                        progress(max(0, int(batch['out_time_us']) / 1e6))
                    batch = {}
            if process.wait():
                errors.seek(0)
                raise ValueError(errors.read()[-3000:] or 'Video encoding failed')


def original_bitrate(project):
    """Duration-weighted original VIDEO bitrate; never substitute proxy/container rate."""
    assets = {a['id']: a for a in project['assets']}
    weights = {}
    for clip in project['clips']:
        key = clip['assetId']
        weights[key] = weights.get(key, 0) + duration(clip)
    total = 0
    for key, weight in weights.items():
        asset = assets[key]
        info = asset.get('sourceProbe')
        if not info and asset.get('originalPath'):
            try: info = probe(asset['originalPath'])
            except (ValueError, OSError): return None
        video = next((s for s in (info or {}).get('streams', []) if s.get('codec_type') == 'video'), {})
        try: bitrate = int(video.get('bit_rate', 0))
        except (TypeError, ValueError): return None
        if bitrate <= 0: return None
        total += weight * bitrate
    return round(total / sum(weights.values())) if weights else None

def source_settings(info):
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    rates = [video.get('r_frame_rate'), video.get('avg_frame_rate')]
    rate = next((Fraction(r) for r in rates if r and r != '0/0' and 1 <= Fraction(r) <= 240), None)
    if rate is None:
        raise ValueError('Cannot determine source frame rate; specify a verified rate')
    sar = video.get('sample_aspect_ratio', '1:1')
    sar = Fraction(sar.replace(':', '/')) if sar not in ('N/A', '0:1') else Fraction(1)
    width, height = round(video['width'] * sar), video['height']
    rotation = next((int(s.get('rotation', 0)) for s in video.get('side_data_list', []) if 'rotation' in s), int(video.get('tags', {}).get('rotate', 0)))
    if abs(rotation) % 180 == 90:
        width, height = height, width
    audio = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
    return dict(width=width, height=height, fps=str(rate),
                audio=dict(sampleRate=int(audio['sample_rate']), channels=int(audio['channels'])) if audio else None,
                color={k: video[k] for k in ('color_space', 'color_transfer', 'color_primaries', 'color_range') if k in video},
                variableFrameRate=video.get('r_frame_rate') != video.get('avg_frame_rate'))


def prepare_media(source, output, fps=None, width=None, start=0, length=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or source == output:
        raise ValueError('Use a new media path')
    info = probe(source)
    fingerprint = identity(source)
    settings = source_settings(info)
    rate = Fraction(str(fps or settings['fps']))
    target_width = width or settings['width']
    target_height = round(settings['height'] * target_width / settings['width'])
    # H.264 4:2:0 needs even dimensions; pad the last pixel instead of cropping.
    target_width += target_width % 2
    target_height += target_height % 2
    if not 1 <= rate <= 240 or not 2 <= target_width <= 8192 or not 2 <= target_height <= 8192 or start < 0 or (length is not None and length <= 0):
        raise ValueError('Invalid media parameters')
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    if video.get('color_transfer') in ('smpte2084', 'arib-std-b67'):
        raise ValueError('HDR source: establish and verify an SDR tone-map before creating this proxy')
    output.parent.mkdir(parents=True, exist_ok=True)
    clock = mapping(info, start)
    from local_render import source_input, grid_filter
    bound = {'originalPath': str(source), 'sourceMapping': clock}
    _, grid = grid_filter(bound, 0, rate)
    args = source_input(bound, Fraction(clock['originSeconds'])) + ['-n']
    if length is not None:
        args += ['-t', length]
    args += ['-map', '0:v:0', '-map', '0:a:0?', '-vf',
        f'{grid},scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,setsar=1',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', '-g', str(round(float(rate))),
        '-c:a', 'aac']
    if settings['audio']:
        args += ['-af', f"atrim=start={float(Fraction(clock['originSeconds'])):.9f},asetpts=PTS-({clock['originSeconds']})/TB,aresample=async=1:first_pts=0",
                 '-ar', settings['audio']['sampleRate'], '-ac', settings['audio']['channels']]
    # Preserve supported SDR color tags. HDR requires an explicitly verified tone map.
    for key, option in [('color_space', '-colorspace'), ('color_transfer', '-color_trc'), ('color_primaries', '-color_primaries'), ('color_range', '-color_range')]:
        value = settings['color'].get(key)
        if value and value not in ('unknown', 'unspecified'):
            args += [option, value]
    args += ['-movflags', '+faststart', output]
    run(args)
    unchanged(fingerprint)
    checked = probe(output)
    stream = next(s for s in checked['streams'] if s['codec_type'] == 'video')
    result = {'path': str(output), 'frames': int(stream['nb_frames']), 'fps': str(rate),
        'width': stream['width'], 'height': stream['height'], 'audio': source_settings(checked)['audio'],
        'sourceSettings': settings,
        'hasAudio': any(s['codec_type'] == 'audio' for s in checked['streams']),
        'originalPath': str(source), 'sourceStartSeconds': start, 'sourceProbe': info,
        'sourceIdentity': fingerprint, 'sourceMapping': clock,
        'timing': 'cfr-proxy', 'mapping': 'original PTS time = sourceMapping.originSeconds + frame / fps; resampled frames are not original frame numbers'}
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
    entries = [{k: o[k] for k in ('id', 'component', 'props', 'placement', 'naturalHeight', 'outputLanguage') if k in o} for o in project.get('overlays', [])]
    if not entries:
        return project
    request = {'canvas': {'width': project['width'], 'height': project['height']}, 'layout': 'fit', 'entries': entries, 'outputLanguage': project.get('outputLanguage', 'zh-CN')}
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

def export_clips(project, scope='full', clip_ids=None):
    """Validate an explicit export scope and retain master order, including holds."""
    if scope not in ('full', 'selected'):
        raise ValueError('Export scope must be full or selected')
    if scope == 'full':
        return list(project['clips'])
    if not isinstance(clip_ids, list) or not clip_ids or any(not isinstance(x, str) for x in clip_ids):
        raise ValueError('Select at least one clip to export')
    ids = set(clip_ids)
    if len(ids) != len(clip_ids) or ids - {c['id'] for c in project['clips']}:
        raise ValueError('Export selection contains duplicate or unknown clips')
    return [c for c in project['clips'] if c['id'] in ids]


def export_settings(project, options=None):
    options = options or {}
    if not isinstance(options, dict):
        raise ValueError('Export options must be an object')
    scope = options.get('scope', 'full')
    clips = export_clips(project, scope, options.get('clipIds'))
    result = {k: options.get(k, project[k]) for k in ('width', 'height', 'fps')}
    result.update(scope=scope, clipIds=[c['id'] for c in clips])
    for key in ('width', 'height'):
        if type(result[key]) is not int or not 2 <= result[key] <= 8192 or result[key] % 2:
            raise ValueError('Use even output dimensions from 2 to 8192')
    try:
        rate = Fraction(str(result['fps']))
    except (ValueError, ZeroDivisionError):
        raise ValueError('Use a valid positive output frame rate') from None
    if not 1 <= rate <= 240:
        raise ValueError('Output fps must be between 1 and 240')
    result['fps'] = str(rate)
    choice = options.get('bitrate', 'quality')
    source_rate = original_bitrate({**project, 'clips': clips})
    if choice == 'quality': target_rate = None
    elif choice == 'source':
        if source_rate is None: raise ValueError('Original video bitrate unavailable')
        target_rate = source_rate
    else:
        if isinstance(choice, bool) or not re.fullmatch(r'\d+', str(choice)) or not 100_000 <= int(choice) <= 500_000_000:
            raise ValueError('Use a video bitrate from 100000 to 500000000 bits/s')
        target_rate = int(choice)
    result.update(bitrate=str(choice), videoBitrate=target_rate, sourceVideoBitrate=source_rate)
    filename = options.get('filename', 'edited.mp4')
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError('Output filename is required')
    filename = filename.strip()
    if not filename.lower().endswith('.mp4'):
        filename += '.mp4'
    if not filename or len(filename) > 180 or re.search(r'[<>:"/\\|?*\x00-\x1f]', filename) or filename.startswith('.') or filename[-5:-4] in (' ', '.') or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', filename):
        raise ValueError('Use a valid MP4 filename without directory separators')
    result['filename'] = filename
    result['audio'] = project.get('audio', next((a.get('audio') for a in project['assets'] if a.get('audio')), None))
    if 'audio' not in project and not result['audio']:
        asset = next((a for a in project['assets'] if a.get('hasAudio')), None)
        if asset:
            result['audio'] = asset.get('sourceSettings', {}).get('audio')
    return result


def export_video(project, directory, progress=lambda value: None, options=None, target=None, *, user_requested=False):
    from local_render import preflight, encode
    import shutil
    validate(project)
    check_export_request(project, user_requested)
    settings = export_settings(project, options)
    target = Path(target).resolve() if target else Path(directory).resolve() / settings['filename']
    if target.exists():
        raise ValueError('Output file already exists; choose another filename')
    directory = Path(directory).resolve()
    if directory.exists():
        raise ValueError('Use a new export directory')
    selected = set(settings['clipIds'])
    ranges, master_frame, timeline_frames = [], 0, 0
    for clip in project['clips']:
        n = duration(clip)
        if clip['id'] in selected:
            ranges.append(dict(clipId=clip['id'], masterStartFrame=master_frame, masterEndFrame=master_frame+n,
                exportStartFrame=timeline_frames, exportEndFrame=timeline_frames+n))
            timeline_frames += n
        master_frame += n
    render = {**project, 'clips': export_clips(project, settings['scope'], settings['clipIds'])}
    fingerprints = preflight(render)  # Before creating ANY export files; no proxy fallback.
    directory.mkdir(parents=True)
    write(directory / 'project-snapshot.json', project)
    final_path = directory / '.encoded.mp4'
    def report_progress(value, stage='encoding'):
        progress(dict(state='running', stage=stage, progressPercent=value))
    report_progress(0)
    resources = encode(render, settings, final_path, fingerprints, report_progress)
    report_progress(99, 'finalizing')
    result = probe(final_path)
    video = next(s for s in result['streams'] if s['codec_type'] == 'video')
    if int(video['nb_frames']) != resources['frames']:
        raise ValueError('Export frame count mismatch')
    # Exclusive destination creation prevents accidental replacement across filesystems.
    try:
        with target.open('xb') as dest, final_path.open('rb') as src:
            shutil.copyfileobj(src, dest, 1024*1024)
    except BaseException:
        # Leave diagnostics in this fresh export directory; never remove an existing target.
        raise
    report = {'state': 'complete', 'progressPercent': 100, 'stage': 'complete',
        'durationSeconds': float(Fraction(resources['frames']) / Fraction(settings['fps'])),
        'path': str(target), 'revision': project['revision'], 'frames': resources['frames'],
        'settings': settings, 'timelineFrames': timeline_frames, 'fullTimelineFrames': master_frame, 'ranges': ranges,
        'warnings': project.get('needsRebuild', []), 'userRequested': user_requested,
        'sha256': identity(target)['sha256'], 'probe': result, 'render': resources,
        'originals': list(fingerprints.values())}
    write(directory / 'export.json', report)
    final_path.unlink()  # Only the known duplicate created by this invocation.
    progress(report)
    return report
