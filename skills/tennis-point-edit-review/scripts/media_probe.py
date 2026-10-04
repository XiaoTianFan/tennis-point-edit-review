"""Read source presentation timestamps; no transcoding or editor operations."""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def identity(path):
    path = Path(path).resolve()
    before = path.stat()
    with path.open('rb') as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Source changed while hashing')
    return {'path': str(path), 'size': after.st_size, 'mtimeNs': after.st_mtime_ns,
            'sha256': digest.hexdigest()}


def metadata(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                             '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def assess_timestamps(timestamps, time_base, rates):
    """CFR means a reported rate fits EVERY PTS within one time-base tick.

    Alternating rounded intervals alone are not VFR. Missing/nonmonotone PTS or
    insufficient precision remain unknown; irregular timing is not a diagnosis
    of missing camera frames. Constant-rate duplicate pictures are not detected.
    """
    base = Fraction(time_base)
    if base <= 0:
        raise ValueError('Positive time base required')
    periods = {}
    for value in rates:
        try:
            fps = Fraction(value)
            if fps > 0 and 1 / fps >= 2 * base:
                periods[str(fps)] = 1 / fps / base
        except (ValueError, ZeroDivisionError):
            pass
    errors = {fps: Fraction(0) for fps in periods}
    first = last = None
    count = missing = nonmonotone = 0
    deltas = Counter()
    for pts in timestamps:
        index = count
        count += 1
        if pts is None:
            missing += 1
            continue
        if first is None:
            first = pts
        if last is not None:
            delta = pts - last
            deltas[delta] += 1
            nonmonotone += delta <= 0
        for fps, period in periods.items():
            errors[fps] = max(errors[fps], abs(pts - first - index * period))
        last = pts
    fitted = [fps for fps, error in errors.items() if error <= 1]
    unknown = count < 3 or missing or nonmonotone or not periods
    classification = 'unknown' if unknown else 'cfr' if fitted else 'variable_or_discontinuous'
    return {'classification': classification, 'fittedRates': [] if unknown else fitted,
            'frameCount': count, 'missingPts': missing, 'nonmonotonePts': nonmonotone,
            'firstPts': first, 'lastPts': last, 'timeBase': str(base),
            'intervalTicks': [{'ticks': ticks, 'count': n} for ticks, n in deltas.most_common(12)],
            'maxGridErrorTicks': {fps: float(error) for fps, error in errors.items()},
            'note': 'Timing only; no ball detection, visual review, or duplicate-picture diagnosis.'}


def probe(path):
    source = identity(path)
    info = metadata(source['path'])
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    if video is None:
        raise ValueError('No video stream')
    # Stream output instead of holding every frame record in memory.
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                    '-show_frames', '-show_entries', 'frame=pts',
                                    '-of', 'compact', source['path']], stdout=subprocess.PIPE,
                                   stderr=errors, text=True, encoding='utf-8')
        try:
            def timestamps():
                for line in process.stdout:
                    if not line.startswith('frame|') and line.strip() != 'frame':
                        continue
                    fields = dict(part.split('=', 1) for part in line.strip().split('|')[1:] if '=' in part)
                    value = fields.get('pts', 'N/A')
                    yield int(value) if value != 'N/A' else None
            timing = assess_timestamps(timestamps(), video['time_base'],
                                       [video.get('avg_frame_rate', '0/0'), video.get('r_frame_rate', '0/0')])
            if process.wait() != 0:
                errors.seek(0)
                raise ValueError('Timestamp probe failed: ' + errors.read().decode('utf-8', errors='replace')[-2000:])
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
    stat = Path(source['path']).stat()
    if (stat.st_size, stat.st_mtime_ns) != (source['size'], source['mtimeNs']):
        raise ValueError('Source changed during probe')
    return {'schema': 'tennis-media-probe/v1', 'source': source, 'scope': 'all_video_frames',
            'video': video, 'audio': [s for s in info['streams'] if s['codec_type'] == 'audio'],
            'timing': timing}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source'); parser.add_argument('output')
    args = parser.parse_args()
    result = probe(args.source)
    with Path(args.output).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result['timing']))
