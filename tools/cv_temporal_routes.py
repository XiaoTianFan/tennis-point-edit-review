"""Experimental observation-only temporal routing. No tennis outcomes are adopted.

Inputs are committed cv_stream observations and explicit source-frame windows.
This research CLI is not enabled in the distributed editing skill.
"""
import argparse
import hashlib
import json
import math
import time
from fractions import Fraction
from pathlib import Path

import numpy as np


DEFAULTS = dict(maxGapSeconds=.05, maxSpeedPixelsPerSecond=1800.,
                associationSlackPixels=4., ambiguityMarginPixels=4.,
                stationaryRadiusPixels=4., stationarySeconds=.25,
                stationaryObservations=12, fitHalfWindowSeconds=.10,
                minObservationsEachSide=3, minVelocityChange=140.,
                maxFitRmsPixels=4., minSmoothGainPixels=.35,
                maxSmoothRatio=.85, suppressSeconds=.12,
                reviewPreSeconds=.20, reviewPostSeconds=.30)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    p = Path(path)
    return dict(path=str(p.resolve()), sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                   allow_nan=False)+'\n', encoding='utf-8')


def config(raw):
    if set(raw) - (set(DEFAULTS) | {'netProjectionBox'}):
        raise ValueError('Unknown temporal route parameter')
    value = {**DEFAULTS, **raw}
    for key in DEFAULTS:
        if isinstance(value[key], bool) or not isinstance(value[key], (int, float)) or not math.isfinite(value[key]) or value[key] <= 0:
            raise ValueError('Parameters must be finite positive numbers')
    for key in ['stationaryObservations', 'minObservationsEachSide']:
        if not isinstance(value[key], int):
            raise ValueError('Observation counts must be integers')
    if value['maxSmoothRatio'] > 1:
        raise ValueError('Smooth ratio must not exceed one')
    box = value.get('netProjectionBox')
    if box is not None and (not isinstance(box, list) or len(box) != 4 or
                            any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) for x in box) or
                            box[0] >= box[2] or box[1] >= box[3]):
        raise ValueError('Invalid net projection box')
    return value


def associate(records, cfg):
    """Keep separate view-local paths; ambiguous matches start new paths."""
    tracks = []
    for row in records:
        t = float(Fraction(row['seconds']))
        obs = [dict(id=f'{row["id"]}/C{i}', frame=row['ordinal'], pts=row['pts'],
                    seconds=row['seconds'], timeBase=row['timeBase'], t=t,
                    view=int(c['view']), x=float(c['x']), y=float(c['y']))
               for i, c in enumerate(row['modelCandidates'])]
        if any(not math.isfinite(o[k]) for o in obs for k in ['x', 'y']):
            raise ValueError('Nonfinite candidate coordinate')
        edges = []
        for k, track in enumerate(tracks):
            last = track[-1]; dt = t-last['t']
            if not 0 < dt <= cfg['maxGapSeconds']:
                continue
            vx = vy = 0.
            if len(track) >= 2:
                before = track[-2]; delta = last['t']-before['t']
                vx = (last['x']-before['x'])/delta
                vy = (last['y']-before['y'])/delta
            for j, point in enumerate(obs):
                if point['view'] != last['view']:
                    continue
                step = math.hypot(point['x']-last['x'], point['y']-last['y'])
                if step <= cfg['maxSpeedPixelsPerSecond']*dt+cfg['associationSlackPixels']:
                    distance = math.hypot(point['x']-last['x']-vx*dt,
                                          point['y']-last['y']-vy*dt)
                    edges.append((distance, k, j))
        used_tracks, used_points = set(), set()
        for distance, k, j in sorted(edges):
            competitors = [d for d, a, b in edges if (a == k or b == j) and (a, b) != (k, j)]
            if competitors and min(competitors)-distance < cfg['ambiguityMarginPixels']:
                continue
            if k not in used_tracks and j not in used_points:
                tracks[k].append(obs[j]); used_tracks.add(k); used_points.add(j)
        tracks.extend([o] for j, o in enumerate(obs) if j not in used_points)
    return tracks


def analyze_window(records, cfg):
    if not records:
        raise ValueError('Empty source window')
    times = [float(Fraction(r['seconds'])) for r in records]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Source PTS must increase')
    paths, candidates = [], []
    for k, points in enumerate(associate(records, cfg)):
        xy = np.array([[p['x'], p['y']] for p in points])
        ts = np.array([p['t'] for p in points])
        radius = float(np.linalg.norm(xy-np.median(xy, axis=0), axis=1).max())
        stationary = bool(len(points) >= cfg['stationaryObservations'] and
                      ts[-1]-ts[0] >= cfg['stationarySeconds'] and
                      radius <= cfg['stationaryRadiusPixels'])
        path_id = f'track-{k:04}'
        paths.append(dict(id=path_id, stationaryResponse=stationary,
                          semanticObject=None, radiusPixels=radius, observations=points))
        if stationary:
            continue  # Retained in paths; not asserted to be an old or irrelevant ball.
        proposals = []
        for i, p in enumerate(points):
            mask = np.abs(ts-ts[i]) <= cfg['fitHalfWindowSeconds']
            u = ts[mask]-ts[i]; coords = xy[mask]
            count = cfg['minObservationsEachSide']
            if sum(u < 0) < count or sum(u > 0) < count or np.diff(u).max() > cfg['maxGapSeconds']:
                continue
            basis = np.c_[np.ones(len(u)), u, np.maximum(u, 0)]
            fit = np.linalg.lstsq(basis, coords, rcond=None)[0]
            residual = float(np.sqrt(np.mean((basis@fit-coords)**2)))
            smooth_basis = np.c_[np.ones(len(u)), u, u*u]
            smooth_fit = np.linalg.lstsq(smooth_basis, coords, rcond=None)[0]
            smooth = float(np.sqrt(np.mean((smooth_basis@smooth_fit-coords)**2)))
            change = float(np.linalg.norm(fit[2]))
            if (change < cfg['minVelocityChange'] or residual > cfg['maxFitRmsPixels'] or
                    smooth-residual < cfg['minSmoothGainPixels'] or residual > smooth*cfg['maxSmoothRatio']):
                continue
            box = cfg.get('netProjectionBox')
            overlap = None if box is None else box[0] <= p['x'] <= box[2] and box[1] <= p['y'] <= box[3]
            proposals.append(dict(trackId=path_id, frame=p['frame'], pts=p['pts'],
                                  timeBase=p['timeBase'], seconds=p['seconds'], xy=[p['x'],p['y']],
                                  view=p['view'], kind='trajectory_change',
                                  residualPixels=residual, smoothResidualPixels=smooth,
                                  velocityChangePixelsPerSecond=change, score=(smooth-residual)*change,
                                  netProjectionOverlap=overlap,
                                  reviewReason='net_ground_depth_unresolved' if overlap else 'collision_mechanism_unresolved',
                                  observedSupportIds=[points[j]['id'] for j in np.flatnonzero(mask)],
                                  automaticAccepted=False, collisionType=None, firstDeadBall=None,
                                  pointWinner=None, serveAttemptNumber=None))
        chosen = []
        for event in sorted(proposals, key=lambda e:(-e['score'], e['frame'])):
            if all(abs(float(Fraction(event['seconds']))-float(Fraction(other['seconds']))) >= cfg['suppressSeconds'] for other in chosen):
                chosen.append(event)
        candidates.extend(chosen)
    candidates.sort(key=lambda e:(e['frame'], e['view'], e['trackId']))
    intervals = []
    for event in candidates:
        t = float(Fraction(event['seconds']))
        a, b = max(times[0], t-cfg['reviewPreSeconds']), min(times[-1], t+cfg['reviewPostSeconds'])
        if intervals and a <= intervals[-1][1]:
            intervals[-1][1] = max(intervals[-1][1], b)
        else:
            intervals.append([a,b])
    return dict(tracks=paths, candidates=candidates, proposedReviewIntervalsSeconds=intervals,
                proposedWindowSeconds=sum(b-a for a,b in intervals),
                fullWindowSeconds=times[-1]-times[0],
                fallbackRequired=not candidates, automaticAccepted=0,
                omissionAuditRequired=True, pointCount=None,
                limits=['Stationary response is not proof of an old ball.',
                        'Projected net overlap is not a physical net collision.',
                        'A trajectory change is not a bounce, contact, dead ball or point.',
                        'Proposed window length is not measured review work saved.'])


def run(stream_path, windows_path, config_path, output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    started = time.perf_counter()
    stream, windows, cfg = read(stream_path), read(windows_path), config(read(config_path))
    if stream.get('status') != 'complete' or windows['sourceSha256'] != stream['sourceIdentity']['sha256']:
        raise ValueError('Complete stream with matching source required')
    specs = windows['windows']
    if len({w['id'] for w in specs}) != len(specs) or any(type(w[k]) is not int for w in specs for k in ['startFrame','endFrameExclusive']):
        raise ValueError('Invalid source window IDs or frames')
    ordered = sorted(specs, key=lambda w:w['startFrame'])
    if any(w['startFrame'] < 0 or w['endFrameExclusive'] <= w['startFrame'] for w in ordered) or any(a['endFrameExclusive'] > b['startFrame'] for a,b in zip(ordered,ordered[1:])):
        raise ValueError('Windows must be bounded and nonoverlapping')
    # Persist exact code/inputs/config before any prediction is computed.
    save(output/'manifest.json', dict(schema='tennis-temporal-route-experiment/v1',
         algorithm=digest(__file__), stream=digest(stream_path), windows=digest(windows_path),
         config=digest(config_path), parameters=cfg, sourceIdentity=stream['sourceIdentity'],
         labelsRead=False, referenceInputsAccepted=False))
    records = []; ordinal = 0
    for chunk in stream['chunks']:
        path = Path(stream_path).parent/'chunks'/chunk['file']
        if path.resolve().parent != (Path(stream_path).parent/'chunks').resolve() or digest(path)['sha256'] != chunk['sha256']:
            raise ValueError('Invalid or modified committed chunk')
        count = 0
        for line in path.read_text(encoding='utf-8').splitlines():
            row = json.loads(line); row['ordinal'] = ordinal
            records.append(row); ordinal += 1; count += 1
        if count != chunk['frames']:
            raise ValueError('Chunk frame count mismatch')
    if any(w['endFrameExclusive'] > len(records) for w in specs):
        raise ValueError('Window outside committed source')
    loaded = time.perf_counter()-started
    results = []
    for w in specs:
        results.append(dict(windowId=w['id'], **analyze_window(records[w['startFrame']:w['endFrameExclusive']], cfg)))
    save(output/'predictions.json',dict(schema='tennis-temporal-route-predictions/v1',
         status='complete', windows=results, automaticAccepted=0,
         costs=dict(cacheReadAndValidationSeconds=loaded, routingSeconds=time.perf_counter()-started-loaded,
                    upstreamInferenceSeconds=None, referenceAnnotationSeconds=None,
                    actualOperatingReviewSeconds=None, pairedReviewSavingsSeconds=None)))
    print(json.dumps(dict(windows=len(results), candidates=sum(len(r['candidates']) for r in results),
                         stationaryTracks=sum(p['stationaryResponse'] for r in results for p in r['tracks']),
                         fallbackWindows=sum(r['fallbackRequired'] for r in results))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ['stream','windows','config','output']:
        parser.add_argument('--'+flag, required=True)
    args = parser.parse_args()
    run(args.stream,args.windows,args.config,args.output)
