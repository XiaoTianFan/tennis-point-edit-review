"""Propose rendered-video edit seams, preserving every source frame for review.

Python standard library + FFmpeg/ffprobe; no learned model or temporal sampling.
Seams are edit candidates, never tennis point or scoring decisions.
"""
import argparse
from collections import deque
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median
import subprocess
import time

from media_probe import identity, metadata, assess_timestamps
from local_model import read, write

DETECTOR = 'rgb-adaptive-v1'
DEFAULTS = dict(width=320, sceneThreshold=8.0, differenceFloor=0.5,
                adaptiveRatio=3.0, madMultiplier=6.0, windowFrames=30)


def settings(values=None):
    result = {**DEFAULTS, **(values or {})}
    if set(result) != set(DEFAULTS):
        raise ValueError('Unknown detector setting')
    for key in ('width', 'windowFrames'):
        if type(result[key]) is not int or not 2 <= result[key] <= (1920 if key == 'width' else 1000):
            raise ValueError('Invalid ' + key)
    for key in ('sceneThreshold', 'differenceFloor', 'adaptiveRatio', 'madMultiplier'):
        value = result[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 100:
            raise ValueError('Invalid ' + key)
    return result


def metric_rows(path):
    """FFmpeg settb=AVTB emits integer microsecond PTS, including nonzero origins."""
    current = None
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            if line.startswith('frame:'):
                if current is not None:
                    yield current
                match = re.match(r'frame:(\d+)\s+pts:(-?\d+)\s+pts_time:', line)
                if not match:
                    raise ValueError('Missing or invalid presentation timestamp')
                current = dict(frame=int(match[1]), ptsUs=int(match[2]))
            elif line.startswith('lavfi.scd.') and current is not None:
                key, value = line.strip().split('=', 1)
                if key in ('lavfi.scd.mafd', 'lavfi.scd.score'):
                    current['difference' if key.endswith('mafd') else 'sceneScore'] = float(value)
    if current is not None:
        yield current


def analyze(rows, config, video):
    history = deque(maxlen=config['windowFrames'])
    pts, candidates = [], []
    for row in rows:
        if row['frame'] != len(pts) or any(k not in row for k in ('ptsUs', 'difference', 'sceneScore')):
            raise ValueError('Incomplete frame metrics')
        if pts and row['ptsUs'] <= pts[-1]:
            raise ValueError('Nonmonotone PTS: diagnose source before reconstructing seams')
        if not all(math.isfinite(row[k]) and 0 <= row[k] <= 100 for k in ('difference', 'sceneScore')):
            raise ValueError('Invalid frame metrics')
        pts.append(row['ptsUs'])
        baseline = median(history) if history else 0.0
        mad = median(abs(v - baseline) for v in history) if history else 0.0
        threshold = max(config['differenceFloor'], baseline * config['adaptiveRatio'],
                        baseline + config['madMultiplier'] * mad)
        reasons = []
        if row['sceneScore'] >= config['sceneThreshold']:
            reasons.append('scene_score')
        if row['difference'] >= threshold:
            reasons.append('adaptive_difference')
        if row['frame'] and reasons:
            candidates.append({**row, 'id': 'S' + str(row['frame']).zfill(8),
                               'adaptiveThreshold': round(threshold, 6), 'signals': reasons,
                               'status': 'proposed'})
        history.append(row['difference'])
    if not pts:
        raise ValueError('No decoded video frames')
    # Never merge nearby hits or remove short segments: flashes, dissolves and
    # rapid edits must remain inspectable instead of silently losing a seam.
    for i, row in enumerate(candidates):
        row['adjacentHit'] = (i > 0 and row['frame'] - candidates[i-1]['frame'] == 1) or (
            i+1 < len(candidates) and candidates[i+1]['frame'] - row['frame'] == 1)
        row['sourceTimeUs'] = row['ptsUs'] - pts[0]
    timing = assess_timestamps(iter(pts), '1/1000000',
                              [video.get('avg_frame_rate', '0/0'), video.get('r_frame_rate', '0/0')])
    return pts, candidates, timing


def scan(source, directory, config=None):
    start = time.monotonic()
    config = settings(config)
    directory = Path(directory).resolve()
    if directory.exists():
        raise ValueError('Use a new scan directory; retain previous decisions')
    source = identity(source)
    info = metadata(source['path'])
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    if video is None:
        raise ValueError('No video stream')
    version = subprocess.check_output(['ffmpeg', '-version'], text=True, encoding='utf-8').splitlines()[0]
    directory.mkdir(parents=True)
    # Relative filter output path avoids FFmpeg filter escaping of Windows paths.
    graph = (f"scale={config['width']}:-2:flags=area,format=rgb24,settb=AVTB,"
             'scdet,metadata=mode=print:file=metrics.txt')
    command = ['ffmpeg', '-hide_banner', '-v', 'error', '-nostdin', '-xerror',
               '-err_detect', 'explode', '-copyts', '-i', source['path'], '-map', '0:v:0',
               '-an', '-sn', '-dn', '-vf', graph, '-fps_mode', 'passthrough', '-f', 'null', '-']
    # Logs and per-frame metrics survive failed/interrupted runs. Only scan.json
    # marks success. Decode at all timestamps, without keyframe-only seeking.
    with (directory / 'decode.log').open('w', encoding='utf-8') as errors:
        subprocess.run(command, cwd=directory, stdout=subprocess.DEVNULL, stderr=errors, check=True)
    pts, candidates, timing = analyze(metric_rows(directory / 'metrics.txt'), config, video)
    if str(video.get('nb_frames', '')).isdigit() and int(video['nb_frames']) != len(pts):
        raise ValueError('Decoded frame count differs from container count; diagnose before publishing a scan')
    if identity(source['path']) != source:
        raise ValueError('Source changed during scan')
    fingerprint = hashlib.sha256(json.dumps([DETECTOR, source['sha256'], config, version], sort_keys=True).encode()).hexdigest()
    report = dict(schema='tennis-seams/v1', detector=DETECTOR, scanId=fingerprint, source=source,
                  settings=config, ffmpegVersion=version, frameCount=len(pts), firstPtsUs=pts[0],
                  lastPtsUs=pts[-1], timestampsSha256=hashlib.sha256(json.dumps(pts,separators=(',',':')).encode()).hexdigest(), timing=timing, candidates=candidates,
                  coverage='every decoded video frame; visual/tennis review not performed',
                  coordinate='zero-based decoded display frame; seam is first frame of next clip',
                  limitations=['Invisible edits cannot be recovered from rendered pixels.',
                               'Motion, flashes, overlays and transitions can cause false hits.',
                               'Same-court jumps and dissolves can be missed; inspect non-hit spans.',
                               'An edit seam is not necessarily a point boundary.'])
    write(directory / 'timestamps.json', pts)
    write(directory / 'decisions.json', dict(schema='tennis-seam-decisions/v1', scanId=fingerprint,
          sourceSha256=source['sha256'], boundaryFrames=[c['frame'] for c in candidates],
          status='proposed', note='Edit boundaryFrames to reject, move or add seams; then set status=reviewed.'))
    elapsed = time.monotonic()-start
    write(directory / 'runtime.json', dict(elapsedSeconds=round(elapsed, 3), decodedFrames=len(pts),
                                          framesPerSecond=round(len(pts)/elapsed, 2)))
    write(directory / 'scan.json', report)
    return report


def partition(report, decisions=None):
    if report.get('schema') != 'tennis-seams/v1' or type(report.get('frameCount')) is not int or report['frameCount'] < 1:
        raise ValueError('Invalid scan')
    if decisions is None:
        frames = [c['frame'] for c in report['candidates']]
        status = 'proposed'
    else:
        if (decisions.get('schema') != 'tennis-seam-decisions/v1' or decisions.get('scanId') != report['scanId']
                or decisions.get('sourceSha256') != report['source']['sha256']):
            raise ValueError('Decisions belong to another scan/source')
        frames, status = decisions['boundaryFrames'], decisions['status']
        if status not in ('proposed', 'reviewed'):
            raise ValueError('Invalid decision status')
    if not isinstance(frames, list) or any(type(f) is not int or not 0 < f < report['frameCount'] for f in frames):
        raise ValueError('Boundaries must be interior integer source frames')
    if frames != sorted(set(frames)):
        raise ValueError('Boundaries must be sorted and unique')
    bounds = [0, *frames, report['frameCount']]
    return [dict(id='C' + str(i+1).zfill(5), inFrame=a, outFrame=b, boundaryStatus=status)
            for i, (a, b) in enumerate(zip(bounds, bounds[1:]))]


def make_plan(scan_path, media_path, decisions=None, players=None, language='en'):
    scan_path, media_path = Path(scan_path).resolve(), Path(media_path).resolve()
    report, media = read(scan_path), read(media_path)
    if media.get('timing') != 'cfr-proxy' or media.get('sourceStartSeconds') != 0:
        raise ValueError('Prepare a full-length CFR proxy from the rendered source')
    original = identity(media['originalPath'])
    if original != report['source']:
        raise ValueError('Proxy original does not match scanned source; rescan after moving/changing source')
    pts = read(scan_path.with_name('timestamps.json'))
    if (len(pts) != report['frameCount'] or pts[0] != report['firstPtsUs'] or pts[-1] != report['lastPtsUs']
            or hashlib.sha256(json.dumps(pts,separators=(',',':')).encode()).hexdigest() != report['timestampsSha256']):
        raise ValueError('Timestamp mapping does not match scan')
    source_clips = partition(report, decisions)
    fps = Fraction(media['fps'])
    clips = []
    for clip in source_clips:
        a, b = clip['inFrame'], clip['outFrame']
        # Nearest CFR boundary, with explicit residual; original display frames
        # and PTS remain authoritative. No keyframe copy or seconds accumulation.
        first = int(Fraction(pts[a] - pts[0], 1000000) * fps + Fraction(1,2))
        last = media['frames'] if b == len(pts) else int(Fraction(pts[b] - pts[0], 1000000) * fps + Fraction(1,2))
        if not 0 <= first < last <= media['frames']:
            raise ValueError('Proxy collapses source seams; use a higher verified CFR rate or native editor')
        clips.append(dict(id=clip['id'], assetId='rendered', inFrame=first, outFrame=last,
                          sourceMapping={**clip, 'sourceSha256': original['sha256'],
                              'inPtsUs': pts[a], 'outPtsUs': pts[b] if b < len(pts) else None,
                              'proxyBoundaryErrorUs': float(Fraction(first, 1)/fps*1000000 - (pts[a]-pts[0]))},
                          boundaryStatus=clip['boundaryStatus']))
    return dict(title='Reconstructed edit', outputLanguage=language, fps=media['fps'],
                width=media['width'], height=media['height'],
                players=players or [dict(id='A', name='Player A'), dict(id='B', name='Player B')],
                assets=[dict(id='rendered', metadata=str(media_path))], clips=clips, overlays=[],
                reconstruction=dict(scanId=report['scanId'], source=report['source'],
                                    boundaryStatus=source_clips[0]['boundaryStatus'], pointGrouping='unverified'),
                review=dict(source=original['sha256'], ledgerRevision=report['scanId'][:16], rows=[]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    detect = sub.add_parser('scan'); detect.add_argument('source'); detect.add_argument('directory')
    detect.add_argument('--settings', help='JSON object overriding recorded defaults')
    plan = sub.add_parser('plan'); plan.add_argument('scan'); plan.add_argument('media'); plan.add_argument('output')
    plan.add_argument('--decisions'); plan.add_argument('--players'); plan.add_argument('--language', choices=['en', 'zh-CN'], default='en')
    args = parser.parse_args()
    if args.command == 'scan':
        report = scan(args.source, args.directory, read(args.settings) if args.settings else None)
        print(json.dumps(dict(scanId=report['scanId'], frames=report['frameCount'], candidates=len(report['candidates']))))
    else:
        if Path(args.output).exists():
            raise ValueError('Use a new plan path')
        result = make_plan(args.scan, args.media, read(args.decisions) if args.decisions else None,
                           read(args.players) if args.players else None, args.language)
        write(args.output, result)
        print(str(Path(args.output).resolve()))


if __name__ == '__main__':
    main()
