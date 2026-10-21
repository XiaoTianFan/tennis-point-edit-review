"""Bounded original decode/composition into one persistent H.264/AAC encoder.

No video/audio media intermediates. FFmpeg supplies raw pixels and bounded PCM;
PyAV muxes the single final encode. Memory does not grow with timeline length.
"""
from contextlib import contextmanager
from fractions import Fraction
import math
from pathlib import Path
import subprocess
import tempfile
from local_model import duration, overlay_range
from source_binding import verify_original, unchanged

CHUNK_SECONDS = 10
THREADS = 2


def nearest(value):
    return math.floor(value + Fraction(1, 2))


def input_index(output_index, timeline_rate, output_rate, count):
    # FFmpeg fps round=near: last input whose rounded output timestamp <= j.
    return min(count - 1, max(0, math.ceil((Fraction(output_index) + Fraction(1, 2)) * timeline_rate / output_rate) - 1))


def preflight(project):
    selected = {c['assetId'] for c in project['clips']}
    checked, paths = {}, {}
    for asset in project['assets']:
        if asset['id'] not in selected:
            continue
        path = str(Path(asset.get('originalPath', '')).resolve())
        expected = asset.get('sourceIdentity', {})
        key = (path, expected.get('sha256'), expected.get('size'))
        if key not in paths:
            paths[key] = verify_original(asset)
        elif asset.get('sourceMapping', {}).get('schema') != 'original-pts-grid/v1':
            raise ValueError('Unbound original mapping')
        checked[asset['id']] = paths[key]
    for overlay in project.get('overlays', []):
        if overlay.get('view', 'both') != 'review' and overlay['clipId'] in {c['id'] for c in project['clips']}:
            if not Path(overlay.get('image', '')).is_file():
                raise ValueError('Missing rendered graphic: ' + overlay['id'])
    import av
    av.codec.Codec('libx264', 'w'); av.codec.Codec('aac', 'w')
    return checked


def source_input(asset, start):
    # copyts preserves ORIGINAL stream PTS, including nonzero container starts.
    # Decode a bounded preroll so fps can bracket the requested grid boundary.
    seek = max(Fraction(0), start - Fraction(asset['sourceMapping']['containerStartSeconds']) - 2)
    return ['ffmpeg', '-v', 'error', '-nostdin', '-threads', str(THREADS),
            '-copyts', '-ss', f'{float(seek):.9f}', '-i', asset['originalPath']]


def grid_filter(asset, frame, rate):
    start = Fraction(asset['sourceMapping']['originSeconds']) + Fraction(frame) / rate
    return start, f'settb=AVTB,setpts=PTS-({start})/TB,fps={rate}:start_time=0:round=near'


def video_command(project, settings, asset, clip, offset, count):
    rate = Fraction(str(project['fps']))
    hold = clip.get('kind') == 'hold'
    start, grid = grid_filter(asset, clip['inFrame'] + (0 if hold else offset), rate)
    args = source_input(asset, start)
    overlays = [o for o in project.get('overlays', []) if o.get('view', 'both') != 'review'
                and o['clipId'] == clip['id'] and overlay_range(o, clip)[1] > overlay_range(o, clip)[0]]
    for overlay in overlays:
        args += ['-loop', '1', '-framerate', str(rate), '-i', overlay['image']]
    if hold:
        grid += ',trim=end_frame=1,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop=-1'
    w, h = settings['width'], settings['height']
    factor = min(Fraction(w,project['width']), Fraction(h,project['height']))
    cw, ch = (max(2, int(project[k]*factor)//2*2) for k in ('width','height'))
    # The preview canvas defines geometry, not the sampling resolution. Fit the
    # original directly at output size; never downsample to a small proxy canvas.
    filters = [f'[0:v]{grid},trim=end_frame={count},setpts=N/({rate}*TB),'
               f'scale={cw}:{ch}:force_original_aspect_ratio=decrease:flags=lanczos:out_range=tv:out_color_matrix=bt709,'
               f'pad={cw}:{ch}:(ow-iw)/2:(oh-ih)/2,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[v0]']
    for i, overlay in enumerate(overlays):
        first, end = overlay_range(overlay, clip)
        extra = ''
        if overlay['component'] == 'statsPanel':
            fade = min(max(1, round(.3 * float(rate))), (end-first)//2) / float(rate)
            if fade:
                extra = (f',setpts=PTS+{offset}/({rate}*TB),fade=t=in:st={first/float(rate)}:d={fade}:alpha=1'
                         f',fade=t=out:st={(end-1)/float(rate)-fade}:d={fade}:alpha=1,setpts=PTS-{offset}/({rate}*TB)')
        filters += [f'[{i+1}:v]format=rgba,scale={cw}:{ch}:flags=lanczos,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black@0{extra}[o{i}]',
                    f"[v{i}][o{i}]overlay=0:0:enable='gte(n,{first-offset})*lt(n,{end-offset})':shortest=1[v{i+1}]"]
    filters += [f'[v{len(overlays)}]format=yuv420p[out]']
    return args + ['-filter_complex_threads', '1', '-filter_complex', ';'.join(filters), '-map', '[out]',
                   '-an', '-frames:v', str(count), '-fps_mode', 'passthrough', '-threads', '1',
                   '-f', 'rawvideo', '-pix_fmt', 'yuv420p', 'pipe:1']


@contextmanager
def decoder(args):
    # A bounded stderr tail file avoids a full pipe deadlock. Error verbosity only.
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen([str(a) for a in args], stdout=subprocess.PIPE, stderr=errors)
        try:
            yield process.stdout
            if process.wait():
                errors.seek(max(0, errors.tell()-4000))
                raise ValueError(errors.read().decode('utf-8', 'replace') or 'Source decoder failed')
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
            process.stdout.close()


def exact_read(pipe, size):
    result = bytearray()
    while len(result) < size:
        block = pipe.read(size-len(result))
        if not block:
            raise ValueError('Source ended before the declared frame/sample range')
        result.extend(block)
    return result


def pcm_chunk(asset, clip, offset, count, global_start, rate, sample_rate, channels):
    import numpy as np
    begin = nearest(Fraction(global_start) * sample_rate / rate)
    end = nearest(Fraction(global_start + count) * sample_rate / rate)
    length = end - begin
    if clip.get('kind') == 'hold' or not asset.get('sourceSettings', {}).get('audio'):
        return np.zeros((length, channels), dtype=np.float32)
    start = Fraction(asset['sourceMapping']['originSeconds']) + Fraction(clip['inFrame'] + offset) / rate
    # async/first_pts retains real gaps/late audio as silence; no per-cut AAC.
    args = source_input(asset, start) + ['-vn', '-map', '0:a:0', '-af',
            f'atrim=start={float(start):.9f},asetpts=PTS-({start})/TB,aresample={sample_rate}:async=1:first_pts=0,'
            f'apad=whole_len={length},atrim=end_sample={length}',
            '-ac', str(channels), '-ar', str(sample_rate), '-f', 'f32le', 'pipe:1']
    with decoder(args) as pipe:
        pcm = np.frombuffer(exact_read(pipe, length*channels*4), dtype='<f4').reshape(length, channels).copy()
        if pipe.read(1): raise ValueError('Audio decoder exceeded chunk bound')
    # Fades apply to the true clip, not the internal streaming chunk boundaries.
    clip_start = nearest(Fraction(global_start-offset) * sample_rate / rate)
    clip_end = nearest(Fraction(global_start-offset+duration(clip)) * sample_rate / rate)
    fade = min(nearest(2 * sample_rate / rate), (clip_end-clip_start)//2)
    if fade:
        positions = np.arange(begin, end)
        gain = np.minimum(1, np.minimum((positions-clip_start)/fade, (clip_end-positions)/fade))
        pcm *= gain[:, None]
    return pcm


def encode(project, settings, path, fingerprints, progress):
    import av
    import numpy as np
    rate, out_rate = Fraction(str(project['fps'])), Fraction(settings['fps'])
    total = sum(duration(c) for c in project['clips'])
    expected = max(1, nearest(Fraction(total) * out_rate / rate))
    audio = settings['audio'] or dict(sampleRate=48000, channels=2)
    sr, channels = audio['sampleRate'], audio['channels']
    layout = {1:'mono', 2:'stereo', 3:'2.1', 4:'4.0', 5:'5.0', 6:'5.1', 7:'6.1', 8:'7.1'}[channels]
    target_samples = nearest(Fraction(expected) * sr / out_rate)
    assets = {a['id']: a for a in project['assets']}
    frame_bytes = settings['width'] * settings['height'] * 3 // 2
    output_frame = audio_pos = timeline_pos = 0
    max_pcm = chunks = 0
    with av.open(str(path), 'w', format='mp4', options={'movflags': '+faststart', 'movie_timescale': str(sr)}) as output:
        video = output.add_stream('libx264', rate=out_rate)
        video.width, video.height, video.pix_fmt = settings['width'], settings['height'], 'yuv420p'
        video.codec_context.thread_count = THREADS
        video.codec_context.time_base = 1/out_rate
        video.options = {'preset': 'veryfast', 'color_range': 'tv', 'colorspace': 'bt709',
                         'color_primaries': 'bt709', 'color_trc': 'bt709'}
        if settings['videoBitrate']: video.bit_rate = settings['videoBitrate']
        else: video.options['crf'] = '18'
        sound = output.add_stream('aac', rate=sr)
        sound.layout = layout
        sound.bit_rate = 128000 * max(1, channels // 2)
        sound.codec_context.time_base = Fraction(1, sr)
        def send_audio(pcm):
            nonlocal audio_pos
            for at in range(0, len(pcm), 1024):
                data = np.ascontiguousarray(pcm[at:at+1024].T)
                frame = av.AudioFrame.from_ndarray(data, format='fltp', layout=layout)
                frame.sample_rate, frame.pts, frame.time_base = sr, audio_pos, Fraction(1, sr)
                audio_pos += frame.samples
                for packet in sound.encode(frame): output.mux(packet)
        for clip in project['clips']:
            asset = assets[clip['assetId']]
            unchanged(fingerprints[asset['id']])
            for offset in range(0, duration(clip), max(1, int(rate*CHUNK_SECONDS))):
                count = min(duration(clip)-offset, max(1, int(rate*CHUNK_SECONDS)))
                pcm = pcm_chunk(asset, clip, offset, count, timeline_pos, rate, sr, channels)
                max_pcm = max(max_pcm, pcm.nbytes); chunks += 1
                pcm_at = 0
                with decoder(video_command(project, settings, asset, clip, offset, count)) as pipe:
                    for n in range(count):
                        raw = exact_read(pipe, frame_bytes)
                        while output_frame < expected and input_index(output_frame, rate, out_rate, total) == timeline_pos+n:
                            frame = av.VideoFrame.from_ndarray(np.frombuffer(raw, dtype=np.uint8).reshape(settings['height']*3//2, settings['width']), format='yuv420p')
                            frame.pts, frame.time_base = output_frame, 1/out_rate
                            for packet in video.encode(frame): output.mux(packet)
                            output_frame += 1
                        want = min(len(pcm)-pcm_at, max(0, min(target_samples, nearest(Fraction(timeline_pos+n+1)*sr/rate))-audio_pos))
                        if want:
                            send_audio(pcm[pcm_at:pcm_at+want]); pcm_at += want
                        progress((timeline_pos+n+1)/total*98)
                    if pipe.read(1): raise ValueError('Video decoder exceeded chunk bound')
                timeline_pos += count
            unchanged(fingerprints[asset['id']])
        if output_frame != expected: raise ValueError('Output frame clock mismatch')
        if audio_pos < target_samples:
            send_audio(np.zeros((target_samples-audio_pos, channels), dtype=np.float32))
        for packet in video.encode(None): output.mux(packet)
        for packet in sound.encode(None): output.mux(packet)
    return dict(frames=expected, audioSamples=audio_pos, sampleRate=sr, videoEncodes=1, audioEncodes=1,
                intermediateMediaBytes=0, maxPcmBytes=max_pcm, chunks=chunks, chunkSeconds=float(CHUNK_SECONDS),
                maxConcurrentSourceDecoders=1, encoderThreads=THREADS, source='originalPath')
