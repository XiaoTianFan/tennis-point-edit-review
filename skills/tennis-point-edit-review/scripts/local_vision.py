"""Source-bound event review records, separate from point answers and approvals."""
from fractions import Fraction
import math

SCHEMA = 'tennis-vision-review/v1'
KINDS = {'racket_contact', 'bounce', 'serve_onset', 'dead_ball', 'other'}
VERDICTS = {'pending', 'confirmed', 'rejected', 'uncertain'}
SIDES = {None, 'near', 'far', 'unknown'}


def frame_number(value, count):
    if type(value) is not int or not 0 <= value < count:
        raise ValueError('Vision event frame outside source')
    return value


def annotation(raw, count):
    allowed = {'verdict', 'kind', 'side', 'frame', 'note', 'evidence', 'reviewSeconds', 'updatedAt'}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise ValueError('Invalid vision annotation fields')
    value = {**dict(verdict='pending', kind=None, side=None, frame=None, note='', evidence=[], reviewSeconds=None), **raw}
    if any(not (item is None or isinstance(item, str)) for item in [value['verdict'], value['kind'], value['side']]) or value['verdict'] not in VERDICTS or value['kind'] not in KINDS | {None} or value['side'] not in SIDES:
        raise ValueError('Invalid vision annotation value')
    if value['frame'] is not None:
        frame_number(value['frame'], count)
    if value['verdict'] == 'confirmed' and (value['kind'] is None or value['frame'] is None):
        raise ValueError('Confirmed event requires a kind and reviewed frame')
    if not isinstance(value['note'], str) or len(value['note']) > 10000:
        raise ValueError('Invalid vision note')
    if not isinstance(value['evidence'], list) or len(value['evidence']) > 50 or any(not isinstance(x, str) or not x.strip() or len(x) > 4096 for x in value['evidence']):
        raise ValueError('Invalid vision evidence references')
    seconds = value['reviewSeconds']
    if seconds is not None and (type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 <= seconds <= 86400):
        raise ValueError('Invalid vision review duration')
    if 'updatedAt' in value and not isinstance(value['updatedAt'], str):
        raise ValueError('Invalid vision annotation timestamp')
    return value


def validate_vision(project):
    review = project.get('visionReview')
    if review is None:
        if project.get('visionAnnotations'):
            raise ValueError('Vision annotations require bound proposals')
        return
    if not isinstance(review, dict) or review.get('schema') != SCHEMA:
        raise ValueError('Unsupported vision review schema')
    asset = next((a for a in project['assets'] if a['id'] == review.get('assetId')), None)
    digest = review.get('sourceIdentity', {}).get('sha256')
    if not asset or not isinstance(digest, str) or len(digest) != 64 or digest != asset.get('sourceIdentity', {}).get('sha256'):
        raise ValueError('Vision review source identity differs from media')
    mapping = asset.get('sourceMapping', {})
    if mapping.get('schema') != 'original-pts-grid/v1':
        raise ValueError('Vision review requires a bound source clock')
    origin = Fraction(mapping['originSeconds']); rate = Fraction(str(project['fps']))
    events = review.get('events')
    if not isinstance(events, list) or len(events) > 100000:
        raise ValueError('Invalid vision proposal list')
    ids = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError('Invalid vision proposal object')
        eid = event.get('id')
        if not isinstance(eid, str) or not eid.strip() or len(eid) > 200 or eid in ids:
            raise ValueError('Invalid or duplicate vision event ID')
        ids.add(eid)
        if not isinstance(event.get('kind'), str) or not (event.get('side') is None or isinstance(event.get('side'), str)) or event.get('kind') not in KINDS or event.get('side') not in SIDES:
            raise ValueError('Invalid vision proposal kind or side')
        frame = frame_number(event.get('frame'), asset['frames'])
        seconds = Fraction(event['seconds'])
        if not origin <= seconds < origin + Fraction(asset['frames']) / rate or abs((seconds-origin)*rate-frame) > 1:
            raise ValueError('Vision proposal clock and frame disagree')
        if event.get('adjudication') is not None:
            raise ValueError('Imported vision proposals must remain unadopted')
        interval = event.get('intervalSeconds')
        if interval is not None:
            if not isinstance(interval, list) or len(interval) != 2:
                raise ValueError('Invalid vision evidence interval')
            lo, hi = map(Fraction, interval)
            if not origin <= lo <= seconds <= hi < origin + Fraction(asset['frames']) / rate:
                raise ValueError('Vision evidence interval outside source')
    annotations = project.get('visionAnnotations', {})
    if not isinstance(annotations, dict) or set(annotations) - ids:
        raise ValueError('Unknown vision annotation event')
    for value in annotations.values():
        annotation(value, asset['frames'])


def payload(project):
    review = project.get('visionReview')
    if review is None:
        return None
    values = project.get('visionAnnotations', {})
    return dict(schema=SCHEMA, sourceIdentity=review['sourceIdentity'], assetId=review['assetId'],
                proposalIdentity=review.get('proposalIdentity'), events=review['events'], annotations=values,
                counts={state: sum(values.get(e['id'], {}).get('verdict', 'pending') == state for e in review['events']) for state in sorted(VERDICTS)},
                adoptedForScoring=False, adoptedForStatistics=False)
