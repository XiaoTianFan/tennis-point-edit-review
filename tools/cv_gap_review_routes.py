"""Experimental review intervals for supported track gaps; never event times.

Consumes frozen temporal-route observations, without accepting reference labels.
No points are interpolated and no collision or tennis outcome is adopted.
"""
import argparse
import math
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

from cv_temporal_routes import digest, read, save


DEFAULTS = dict(maxGapSeconds=.50, endpointFitSeconds=.10,
                minEndpointObservations=3, minEndpointSpanSeconds=.03,
                minSpeedPixelsPerSecond=60., maxSpeedPixelsPerSecond=1800.,
                minVelocityChange=140., maxEndpointRmsPixels=4.,
                maxMeetingDistancePixels=14., minSmoothGainPixels=.15,
                maxSmoothRatio=.90, reviewPreSeconds=.20,
                reviewPostSeconds=.30)


def config(raw):
    if set(raw) - set(DEFAULTS):
        raise ValueError('Unknown gap review parameter')
    cfg = {**DEFAULTS, **raw}
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not math.isfinite(v) or v <= 0 for v in cfg.values()):
        raise ValueError('Parameters must be finite positive numbers')
    if type(cfg['minEndpointObservations']) is not int or cfg['minEndpointObservations'] < 3:
        raise ValueError('At least three endpoint observations required')
    if cfg['maxSmoothRatio'] > 1 or cfg['minSpeedPixelsPerSecond'] >= cfg['maxSpeedPixelsPerSecond']:
        raise ValueError('Invalid ratio or speed bounds')
    return cfg


def endpoint(track, at_end, cfg):
    if track['stationaryResponse']:
        return None
    points = track['observations']
    times = [float(Fraction(p['seconds'])) for p in points]
    if not points or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Track observations must increase in source time')
    if len({p['view'] for p in points}) != 1:
        raise ValueError('Track must be view-local')
    origin = times[-1] if at_end else times[0]
    selected = [p for p, t in zip(points, times) if abs(t-origin) <= cfg['endpointFitSeconds']]
    if len(selected) < cfg['minEndpointObservations']:
        return None
    ts = np.array([float(Fraction(p['seconds']))-origin for p in selected])
    if ts[-1]-ts[0] < cfg['minEndpointSpanSeconds']:
        return None
    xy = np.array([[p['x'], p['y']] for p in selected], dtype=float)
    if not np.isfinite(xy).all():
        raise ValueError('Nonfinite observation')
    basis = np.c_[np.ones(len(ts)), ts]
    fit = np.linalg.lstsq(basis, xy, rcond=None)[0]
    rms = float(np.sqrt(np.mean((basis@fit-xy)**2)))
    speed = float(np.linalg.norm(fit[1]))
    if rms > cfg['maxEndpointRmsPixels'] or not cfg['minSpeedPixelsPerSecond'] <= speed <= cfg['maxSpeedPixelsPerSecond']:
        return None
    return dict(trackId=track['id'], origin=origin, point=points[-1] if at_end else points[0],
                xy=fit[0], velocity=fit[1], rms=rms, support=selected)


def pair_route(before, after, cfg):
    a, b = before['point'], after['point']
    gap = after['origin']-before['origin']
    if a['view'] != b['view'] or not 0 < gap <= cfg['maxGapSeconds']:
        return None
    velocity_delta = before['velocity']-after['velocity']
    change = float(np.linalg.norm(velocity_delta))
    if change < cfg['minVelocityChange']:
        return None
    difference = before['xy']-after['xy']+after['velocity']*gap
    meeting = float(np.clip(-np.dot(difference, velocity_delta)/change**2, 0., gap))
    distance = float(np.linalg.norm(difference+velocity_delta*meeting))
    if distance > cfg['maxMeetingDistancePixels']:
        return None
    # The best geometric meeting is diagnostic only: no exact event is inferred.
    support = before['support']+after['support']
    ts = np.array([float(Fraction(p['seconds']))-before['origin']-meeting for p in support])
    xy = np.array([[p['x'],p['y']] for p in support], dtype=float)
    hinged = np.c_[np.ones(len(ts)), ts, np.maximum(ts, 0.)]
    smooth = np.c_[np.ones(len(ts)), ts, ts*ts]
    error = lambda basis: float(np.sqrt(np.mean((basis@np.linalg.lstsq(basis,xy,rcond=None)[0]-xy)**2)))
    hinge_rms, smooth_rms = error(hinged), error(smooth)
    if smooth_rms-hinge_rms < cfg['minSmoothGainPixels'] or hinge_rms > smooth_rms*cfg['maxSmoothRatio']:
        return None
    return dict(kind='track_gap_review', view=a['view'],
                beforeTrackId=before['trackId'], afterTrackId=after['trackId'],
                frameBracket=[a['frame'],b['frame']],
                intervalSeconds=[a['seconds'],b['seconds']],
                endpointSourceFrames=[{k:p[k] for k in ['frame','pts','timeBase','seconds']} for p in [a,b]],
                observedSupportIds=[p['id'] for p in support],
                gapSeconds=gap, meetingDistancePixels=distance,
                endpointRmsPixels=[before['rms'],after['rms']],
                velocityChangePixelsPerSecond=change,
                hingedRmsPixels=hinge_rms, smoothRmsPixels=smooth_rms,
                exactEventFrame=None, collisionType=None, automaticAccepted=False,
                reviewReason='missing_observation_or_association_break_requires_source_review')


def merge_cards(items):
    """Union overlapping review ranges without equating their underlying events."""
    cards = []
    for item in sorted(items,key=lambda x:(x['start'],x['end'],x['id'])):
        if cards and item['start'] <= cards[-1]['intervalSeconds'][1]:
            card = cards[-1]
            card['intervalSeconds'][1] = max(card['intervalSeconds'][1],item['end'])
            card['memberIds'].append(item['id'])
        else:
            cards.append(dict(id=f'card-{len(cards):04}', intervalSeconds=[item['start'],item['end']],
                              memberIds=[item['id']], semanticEventCount=None))
    return cards


def analyze_window(window, cfg):
    tracks = window['tracks']
    ends = [e for p in tracks if (e := endpoint(p,True,cfg)) is not None]
    starts = [e for p in tracks if (e := endpoint(p,False,cfg)) is not None]
    routes = []
    for a in ends:
        for b in starts:
            if a['trackId'] == b['trackId']:
                continue
            route = pair_route(a,b,cfg)
            if route is not None:
                route['id'] = f'gap-{len(routes):04}'
                routes.append(route)
    # Competing endpoint pairings remain visible instead of selecting a false identity.
    for r in routes:
        r['competingRouteIds'] = [q['id'] for q in routes if q is not r and
            (q['beforeTrackId'] == r['beforeTrackId'] or q['afterTrackId'] == r['afterTrackId'])]
    support = [p for t in tracks for p in t['observations']]
    # Bounds are passed from the frozen source windows, including empty frames.
    low, high = window['sourceIntervalSeconds']
    items = []
    for i,c in enumerate(window['candidates']):
        t = float(Fraction(c['seconds']))
        items.append(dict(id=f'collision-{i:04}',start=max(low,t-cfg['reviewPreSeconds']),
                          end=min(high,t+cfg['reviewPostSeconds'])))
    baseline_cards = merge_cards(items)
    for r in routes:
        a,b = map(lambda x:float(Fraction(x)),r['intervalSeconds'])
        items.append(dict(id=r['id'],start=max(low,a-cfg['reviewPreSeconds']),
                          end=min(high,b+cfg['reviewPostSeconds'])))
    cards = merge_cards(items)
    return dict(windowId=window['windowId'], gapRoutes=routes, reviewCards=cards,
                originalCandidateCount=len(window['candidates']), baselineReviewCards=baseline_cards,
                originalObservations=len(support), interpolatedObservations=0,
                fullWindowSeconds=high-low,
                baselineReviewSeconds=sum(c['intervalSeconds'][1]-c['intervalSeconds'][0] for c in baseline_cards),
                proposedReviewSeconds=sum(c['intervalSeconds'][1]-c['intervalSeconds'][0] for c in cards),
                fallbackRequired=not cards, omissionAuditRequired=True,
                automaticAccepted=0, pointCount=None)


def run(raw_run, windows_path, config_path, output):
    started = time.perf_counter()
    raw_run, output = Path(raw_run), Path(output)
    manifest, predictions, windows = read(raw_run/'manifest.json'), read(raw_run/'predictions.json'), read(windows_path)
    cfg = config(read(config_path))
    if predictions.get('status') != 'complete' or digest(windows_path)['sha256'] != manifest['windows']['sha256']:
        raise ValueError('Complete frozen run and identical source windows required')
    if windows['sourceSha256'] != manifest['sourceIdentity']['sha256']:
        raise ValueError('Source mismatch')
    # Bounds use the committed stream's actual PTS, not a presumed constant FPS.
    stream_path = Path(manifest['stream']['path'])
    if digest(stream_path)['sha256'] != manifest['stream']['sha256']:
        raise ValueError('Upstream stream manifest changed')
    stream = read(stream_path)
    times = []
    import json
    for chunk in stream['chunks']:
        path = stream_path.parent/'chunks'/chunk['file']
        if path.resolve().parent != (stream_path.parent/'chunks').resolve() or digest(path)['sha256'] != chunk['sha256']:
            raise ValueError('Changed or invalid committed chunk')
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        if len(rows) != chunk['frames']:
            raise ValueError('Chunk frame count mismatch')
        times.extend(float(Fraction(row['seconds'])) for row in rows)
    if any(b <= a for a,b in zip(times,times[1:])):
        raise ValueError('Source times must increase')
    specs = {w['id']:w for w in windows['windows']}
    if len(specs) != len(windows['windows']) or {w['windowId'] for w in predictions['windows']} != set(specs):
        raise ValueError('Window identity mismatch')
    for w in predictions['windows']:
        spec = specs[w['windowId']]
        a,b = spec['startFrame'],spec['endFrameExclusive']
        if type(a) is not int or type(b) is not int or not 0 <= a < b <= len(times):
            raise ValueError('Invalid source window')
        w['sourceIntervalSeconds'] = [times[a],times[b-1]]
        for t in w['tracks']:
            for p in t['observations']:
                f = p['frame']
                if type(f) is not int or not a <= f < b or abs(float(Fraction(p['seconds']))-times[f]) > 1e-9:
                    raise ValueError('Track observation not bound to source window PTS')
    output.mkdir(exist_ok=False)
    save(output/'manifest.json',dict(schema='tennis-gap-review-experiment/v1',algorithm=digest(__file__),
         upstreamManifest=digest(raw_run/'manifest.json'),upstreamPredictions=digest(raw_run/'predictions.json'),
         sourceIdentity=manifest['sourceIdentity'],windows=digest(windows_path),config=digest(config_path),
         parameters=cfg,referenceInputsAccepted=False))
    loaded = time.perf_counter()-started
    results = [analyze_window(w,cfg) for w in predictions['windows']]
    save(output/'predictions.json',dict(schema='tennis-gap-review-predictions/v1',status='complete',
         windows=results,automaticAccepted=0,exactEventPredictionsAdded=0,
         costs=dict(cacheReadAndValidationSeconds=loaded,routingSeconds=time.perf_counter()-started-loaded,
                    upstreamInferenceSeconds=None,actualOperatingReviewSeconds=None,pairedSavingsSeconds=None),
         limits=['Gap intervals are review routes, not 50ms event-time predictions.',
                 'Merged review cards retain all members; they do not identify a single physical event.',
                 'Missing or one-sided tracks still require full-source omission audit.',
                 'Proposed review duration excludes fallback and omission-audit cost.']))
    print(json.dumps(dict(windows=len(results),gapRoutes=sum(len(w['gapRoutes']) for w in results),
                         reviewCards=sum(len(w['reviewCards']) for w in results),
                         fallbackWindows=sum(w['fallbackRequired'] for w in results))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ['run','windows','config','output']:
        parser.add_argument('--'+flag,required=True)
    args = parser.parse_args()
    run(args.run,args.windows,args.config,args.output)
