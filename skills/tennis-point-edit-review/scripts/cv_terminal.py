"""Optional forward observations; never point, cut or winner adoption."""
from fractions import Fraction

SCHEMA = 'tennis-terminal-window/v1'
STATUSES = {'pending', 'continuation', 'cessation_only', 'verified', 'source_truncated', 'not_play'}
ANCHORS = {'candidate_next_serve', 'visual_discontinuity', 'recording_end', 'manual'}
SAMPLING = {'navigation', 'sampled_native', 'continuous_playback', 'mixed'}
VERDICTS = {'pending': 'pending', 'continuation': 'rejected', 'cessation_only': 'uncertain',
            'verified': 'confirmed', 'source_truncated': 'uncertain', 'not_play': 'rejected'}


def seconds(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('Invalid terminal source time')
    try:
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError('Invalid terminal source time') from exc


def proposal(value, event, bounds):
    if not isinstance(value, dict) or set(value) != {'schema', 'anchor'} or value['schema'] != SCHEMA:
        raise ValueError('Invalid terminal window schema')
    anchor = value['anchor']
    if not isinstance(anchor, dict) or set(anchor) != {'kind', 'seconds'} or not isinstance(anchor['kind'], str) or anchor['kind'] not in ANCHORS:
        raise ValueError('Invalid terminal context anchor')
    interval = event.get('intervalSeconds')
    if not isinstance(interval, list) or len(interval) != 2:
        raise ValueError('Terminal window requires a source evidence interval')
    lo, hi = map(seconds, interval); at = seconds(anchor['seconds'])
    if not bounds[0] <= lo <= seconds(event['seconds']) <= at <= hi < bounds[1]:
        raise ValueError('Terminal window or anchor outside source context')
    if event.get('motionExample') is not None:
        raise ValueError('Terminal and motion examples need separate events')
    return value


def annotation(raw):
    allowed = {'status', 'lastLiveSeconds', 'firstDeadBallWindowSeconds', 'observedThroughSeconds',
               'continuationFound', 'cessationObserved', 'sourceGapSeconds', 'sampling', 'nativeEvidence', 'actor'}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise ValueError('Invalid terminal observation fields')
    value = dict(status='pending', lastLiveSeconds=None, firstDeadBallWindowSeconds=None,
                 observedThroughSeconds=None, continuationFound=None, cessationObserved=None,
                 sourceGapSeconds=None, sampling='navigation', nativeEvidence=[], actor=None)
    value.update(raw)
    if not isinstance(value['status'], str) or value['status'] not in STATUSES or not isinstance(value['sampling'], str) or value['sampling'] not in SAMPLING:
        raise ValueError('Invalid terminal observation status or sampling')
    for key in ['continuationFound', 'cessationObserved']:
        if value[key] is not None and type(value[key]) is not bool:
            raise ValueError('Terminal continuation/cessation must be explicit booleans or unknown')
    for key in ['lastLiveSeconds', 'observedThroughSeconds', 'sourceGapSeconds']:
        if value[key] is not None:
            value[key] = str(seconds(value[key]))
    window = value['firstDeadBallWindowSeconds']
    if window is not None:
        if not isinstance(window, list) or len(window) != 2 or seconds(window[0]) > seconds(window[1]):
            raise ValueError('Invalid first-dead-ball window')
        value['firstDeadBallWindowSeconds'] = [str(seconds(t)) for t in window]
    evidence = value['nativeEvidence']
    if not isinstance(evidence, list) or len(evidence) > 50 or any(not isinstance(x, str) or not x.strip() or len(x) > 4096 for x in evidence):
        raise ValueError('Invalid terminal native evidence')
    actor = value['actor']
    if actor is not None and (not isinstance(actor, dict) or set(actor) != {'role', 'id'} or
                              actor.get('role') not in ('agent', 'owner') or not isinstance(actor.get('id'), str) or not actor['id'].strip() or len(actor['id']) > 200):
        raise ValueError('Invalid terminal observer')
    if value['status'] != 'pending' and actor is None:
        raise ValueError('Terminal observation requires its declared observer')
    return value


def validate_record(raw, event, parent, bounds, origin, rate):
    if 'terminalWindow' not in event:
        raise ValueError('Terminal observation requires a bound terminal window')
    proposal(event['terminalWindow'], event, bounds)
    value = annotation(raw); status = value['status']
    if parent['verdict'] != VERDICTS[status]:
        raise ValueError('Terminal status and event verdict disagree')
    lo, hi = map(seconds, event['intervalSeconds'])
    times = [seconds(value[k]) for k in ['lastLiveSeconds', 'observedThroughSeconds', 'sourceGapSeconds'] if value[k] is not None]
    death = value['firstDeadBallWindowSeconds']
    if death is not None:
        times += list(map(seconds, death))
    if any(not lo <= t <= hi for t in times):
        raise ValueError('Terminal observation outside its bound source window')
    if status == 'pending':
        return value
    if not parent['note'].strip() or value['observedThroughSeconds'] is None:
        raise ValueError('Terminal observation requires an explanation and forward extent')
    through = seconds(value['observedThroughSeconds'])
    live = seconds(value['lastLiveSeconds']) if value['lastLiveSeconds'] is not None else None
    gap = seconds(value['sourceGapSeconds']) if value['sourceGapSeconds'] is not None else None
    if gap is not None and gap > through:
        raise ValueError('A declared source gap must have been reached in review')
    if status == 'not_play':
        if live is not None or death is not None or value['continuationFound'] is not None or value['cessationObserved'] is not None:
            raise ValueError('Non-play context cannot assert live play or a tennis ending')
        return value
    if live is None or live > through:
        raise ValueError('Terminal observation requires ordered live and forward times')
    if status == 'continuation':
        if value['continuationFound'] is not True or death is not None or value['cessationObserved'] is True:
            raise ValueError('Continuation cannot also confirm a terminal event')
        if gap is not None and min(seconds(event['seconds']), live) <= gap <= through:
            raise ValueError('A source gap cannot establish continuation of the preceding play')
    elif status in {'cessation_only', 'verified'}:
        if value['cessationObserved'] is not True or value['continuationFound'] is not False or through <= live:
            raise ValueError('Cessation requires explicit forward review without observed continuation')
        if status == 'cessation_only' and death is not None:
            raise ValueError('Cessation-only cannot supply a precise dead-ball window')
        if status == 'cessation_only' and gap is not None and live <= gap <= through:
            raise ValueError('A source gap cannot establish cessation of the preceding play')
        if status == 'verified':
            if death is None or not live <= seconds(death[0]) <= seconds(death[1]) < through:
                raise ValueError('Verified death requires an ordered bracket and later forward evidence')
            if not value['nativeEvidence'] or value['sampling'] not in {'sampled_native', 'mixed'}:
                raise ValueError('Verified death requires declared native sequence evidence')
            if gap is not None and live <= gap <= seconds(death[1]):
                raise ValueError('Cannot verify death across a missing source interval')
            if parent['kind'] != 'dead_ball' or parent['frame'] is None:
                raise ValueError('Verified terminal observation requires a dead-ball review frame')
            frame_time = origin + Fraction(parent['frame']) / rate
            if not seconds(death[0])-1/rate <= frame_time <= seconds(death[1])+1/rate:
                raise ValueError('Reviewed frame must locate the declared dead-ball bracket')
    elif status == 'source_truncated':
        if gap is None or not live <= gap <= through or death is not None or value['cessationObserved'] is True:
            raise ValueError('Truncated ending needs a source gap and cannot assert cessation or exact death')
    return value
