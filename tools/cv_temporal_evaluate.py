"""Compare frozen temporal candidates with partial, independently read references.

Measures collision timing coverage, not tennis semantics or review savings.
Uses exact rational source times and maximum-cardinality one-to-one matching.
"""
import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def interval(item):
    values = item['intervalSeconds']
    if not isinstance(values, list) or len(values) != 2:
        raise ValueError('Expected a two-endpoint source interval')
    a, b = map(Fraction, map(str, values))
    if a < 0 or b < a:
        raise ValueError('Invalid source interval')
    return a, b


def distance(t, bracket):
    a, b = bracket
    return max(a-t, t-b, Fraction(0))


def compare(predictions, reference, windows, tolerance=Fraction(1, 20)):
    tolerance = Fraction(str(tolerance))
    if tolerance < 0:
        raise ValueError('Tolerance must be nonnegative')
    if predictions.get('status') != 'complete':
        raise ValueError('Incomplete predictions')
    segments = reference['segmentIds']
    if not segments or len(set(segments)) != len(segments):
        raise ValueError('Reference segment IDs must be unique and nonempty')
    specs = {w['id']: w for w in windows['windows']}
    runs = {w['windowId']: w for w in predictions['windows']}
    if len(specs) != len(windows['windows']) or len(runs) != len(predictions['windows']):
        raise ValueError('Duplicate window ID')
    if set(specs) != set(runs) or not set(segments) <= set(specs):
        raise ValueError('Prediction/window/reference scope mismatch')
    if reference['sourceIdentity']['sha256'] != windows['sourceSha256']:
        raise ValueError('Source identity mismatch')
    refs = reference['events']
    if len({r['id'] for r in refs}) != len(refs):
        raise ValueError('Duplicate reference event ID')
    for r in refs:
        a,b = r['frameBracket']
        if type(a) is not int or type(b) is not int or not 0 <= a <= b:
            raise ValueError('Invalid reference frame bracket')
        if 'sourceFrames' in r:
            frames = r['sourceFrames']
            if ([f['ordinal'] for f in frames] != [a,b] or
                    tuple(f['pts']*Fraction(f['timeBase']) for f in frames) != interval(r)):
                raise ValueError('Reference interval does not match source PTS')
    for collection in [refs, reference['unknowns'], reference['observableIntervals']]:
        for item in collection:
            if item['segmentId'] not in segments:
                raise ValueError('Annotation outside reference scope')
            interval(item)
    details, matches, missed = [], [], []
    for segment in segments:
        truth = sorted((r for r in refs if r['segmentId'] == segment),
                       key=lambda r: (interval(r), r['id']))
        window = specs[segment]
        if (type(window['startFrame']) is not int or type(window['endFrameExclusive']) is not int
                or not 0 <= window['startFrame'] < window['endFrameExclusive']):
            raise ValueError('Invalid frame window')
        candidates = []
        for i, c in enumerate(runs[segment]['candidates']):
            t = Fraction(str(c['seconds']))
            if (t < 0 or type(c['frame']) is not int or not
                    window['startFrame'] <= c['frame'] < window['endFrameExclusive']):
                raise ValueError('Candidate outside frozen source window')
            if 'pts' in c and t != c['pts']*Fraction(c['timeBase']):
                raise ValueError('Candidate time does not match source PTS')
            candidates.append(dict(c, evaluationId=f'{segment}/candidate-{i:04}', t=t))
        candidates.sort(key=lambda c: (c['t'], c['evaluationId']))
        # Augmenting paths maximize one-to-one cardinality. Temporal distance
        # orders ties locally; this does not claim globally minimum total error.
        edges = [[j for j in sorted(range(len(truth)),
                  key=lambda j: (distance(c['t'], interval(truth[j])), truth[j]['id']))
                  if distance(c['t'], interval(truth[j])) <= tolerance] for c in candidates]
        owners = {}

        def assign(i, seen):
            for j in edges[i]:
                if j in seen:
                    continue
                seen.add(j)
                if j not in owners or assign(owners[j], seen):
                    owners[j] = i
                    return True
            return False

        for i in range(len(candidates)):
            assign(i, set())
        paired = {i: j for j, i in owners.items()}
        unknowns = [interval(u) for u in reference['unknowns'] if u['segmentId'] == segment]
        visible = [interval(u) for u in reference['observableIntervals'] if u['segmentId'] == segment]
        for i,c in enumerate(candidates):
            row = dict(candidateId=c['evaluationId'], segmentId=segment,
                       frame=c['frame'], seconds=str(c['t']),
                       view=c.get('view'), trackId=c.get('trackId'))
            if i in paired:
                r = truth[paired[i]]
                row.update(status='matched_timing', referenceId=r['id'],
                           bracketDistanceSeconds=float(distance(c['t'], interval(r))))
                matches.append(row)
            elif edges[i]:
                row.update(status='duplicate_collision_candidate',
                           adjacentReferenceIds=[truth[j]['id'] for j in edges[i]])
            elif any(distance(c['t'], u) <= tolerance for u in unknowns):
                row['status'] = 'unresolved_reference'
            elif any(a <= c['t'] <= b for a,b in visible):
                row['status'] = 'false_collision_candidate'
            else:
                row['status'] = 'not_adjudicated'
            details.append(row)
        for j,r in enumerate(truth):
            if j not in owners:
                a,b = r['frameBracket']
                inside = window['startFrame'] <= a and b < window['endFrameExclusive']
                missed.append(dict(referenceId=r['id'], segmentId=segment,
                    frameBracket=r['frameBracket'], event=r['event'],
                    cause='no_matching_candidate' if inside else 'outside_frozen_route_window'))
    counts = {s: sum(d['status']==s for d in details) for s in
              ['matched_timing','duplicate_collision_candidate','false_collision_candidate',
               'unresolved_reference','not_adjudicated']}
    judged = sum(counts[s] for s in ['matched_timing','duplicate_collision_candidate','false_collision_candidate'])
    return dict(schema='tennis-temporal-route-evaluation/v1', segmentIds=segments,
        toleranceSeconds=str(tolerance), matching='maximum_cardinality_one_to_one',
        counts=dict(referenceEvents=len(refs), candidates=len(details), missed=len(missed),
                    referenceUnknownIntervals=len(reference['unknowns']),
                    outsideWindowMisses=sum(m['cause']=='outside_frozen_route_window' for m in missed),
                    **counts),
        knownEventTimingRecall=len(matches)/len(refs) if refs else None,
        adjudicatedCandidateTimingPrecision=len(matches)/judged if judged else None,
        allCandidatePrecision=None if judged != len(details) else (len(matches)/judged if judged else None),
        matches=matches, missed=missed, candidates=details,
        actualOperatingReviewSeconds=None, pairedReviewSavingsSeconds=None,
        semanticAccuracy=None, productionAccepted=False,
        limits=['Timing match alone does not verify ball identity or collision semantics.',
                'Known-event recall is conditional on this partial observable reference.',
                'Unknown and not-adjudicated candidates are not counted as true or false.',
                'Duplicate candidates consume review work and count against candidate precision.',
                'Reference annotation is not a paired guided operational review measurement.'])


def run(run_dir, reference_path, windows_path, output):
    root = Path(run_dir)
    raw = root/'predictions.json'
    manifest = read(root/'manifest.json')
    reference, windows = read(reference_path), read(windows_path)
    if digest(raw) != reference['priorPredictions']['sha256']:
        raise ValueError('Predictions changed after independent reference freeze')
    if digest(windows_path) != manifest['windows']['sha256']:
        raise ValueError('Frozen routing windows changed')
    if manifest['sourceIdentity']['sha256'] != reference['sourceIdentity']['sha256']:
        raise ValueError('Manifest/reference source mismatch')
    result = compare(read(raw), reference, windows)
    result['inputs'] = {key: dict(path=str(Path(path).resolve()),sha256=digest(path))
        for key,path in [('algorithm',__file__),('predictions',raw),
                         ('manifest',root/'manifest.json'),('reference',reference_path),('windows',windows_path)]}
    with Path(output).open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(result['counts']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ['run','reference','windows','output']:
        parser.add_argument('--'+flag, required=True)
    args = parser.parse_args()
    run(args.run,args.reference,args.windows,args.output)
