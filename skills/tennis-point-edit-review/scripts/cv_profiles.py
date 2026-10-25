"""Optional motion-example provenance and source-group-separated evaluation windows."""
import copy
from fractions import Fraction
import math
import re

SCHEMA = 'tennis-motion-profile/v1'
CHOICES = {
    'handedness': {'left', 'right', 'unknown'},
    'family': {'forehand', 'backhand', 'overhead', 'serve', 'unknown'},
    'form': {'groundstroke', 'volley', 'smash', 'serve', 'unknown'},
    'spin': {'flat', 'topspin', 'slice', 'kick', 'unknown'},
}
STATES = {'agent_proposed', 'agent_observed', 'owner_confirmed', 'unknown', 'skipped'}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value):
        raise ValueError('Invalid motion example identifier')
    return value


def labels(raw, player_ids):
    if not isinstance(raw, dict) or set(raw) - (set(CHOICES) | {'playerId'}):
        raise ValueError('Invalid motion labels')
    result = {'playerId': None, **{k: 'unknown' for k in CHOICES}, **raw}
    if result['playerId'] is not None and (not isinstance(result['playerId'], str) or result['playerId'] not in player_ids):
        raise ValueError('Unknown motion example player')
    for field, choices in CHOICES.items():
        if not isinstance(result[field], str) or result[field] not in choices:
            raise ValueError('Invalid motion ' + field)
    allowed = {'forehand': {'groundstroke', 'volley', 'unknown'},
               'backhand': {'groundstroke', 'volley', 'unknown'},
               'overhead': {'smash', 'unknown'}, 'serve': {'serve', 'unknown'}}
    if result['family'] in allowed and result['form'] not in allowed[result['family']]:
        raise ValueError('Motion family and form disagree')
    if result['spin'] == 'kick' and result['family'] not in {'serve', 'unknown'}:
        raise ValueError('Kick requires serve or unknown family')
    return result


def interval(raw):
    if not isinstance(raw, list) or len(raw) != 2 or any(type(x) not in (str, int) for x in raw):
        raise ValueError('Motion interval requires two rational source times')
    try:
        a, b = map(Fraction, raw)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('Invalid motion source time') from exc
    if not a < b:
        raise ValueError('Empty or reversed motion interval')
    return a, b


def groups(raw):
    if not isinstance(raw, list) or not raw or len(raw) > 100:
        raise ValueError('Recording groups required for motion examples')
    values = [identifier(x) for x in raw]
    if len(set(values)) != len(values):
        raise ValueError('Duplicate recording group')
    return values


def proposal(raw, event, bounds, player_ids):
    if not isinstance(raw, dict) or set(raw) - {'profileId', 'recordingGroupIds', 'intervalSeconds', 'suggested'}:
        raise ValueError('Invalid motion example proposal')
    result = copy.deepcopy(raw)
    identifier(result.get('profileId')); groups(result.get('recordingGroupIds'))
    a, b = interval(result.get('intervalSeconds'))
    if not bounds[0] <= a <= Fraction(event['seconds']) <= b <= bounds[1]:
        raise ValueError('Motion example outside source or navigation time')
    result['suggested'] = labels(result.get('suggested', {}), player_ids)
    return result


def annotation(raw, player_ids):
    if not isinstance(raw, dict) or set(raw) != {'status', 'labels', 'actor'}:
        raise ValueError('Motion annotation requires status, labels and actor')
    status = raw['status']; actor = raw['actor']
    if not isinstance(status, str) or status not in STATES or not isinstance(actor, dict) or set(actor) != {'role', 'id'}:
        raise ValueError('Invalid motion confirmation provenance')
    if actor['role'] not in ('agent', 'owner') or not isinstance(actor['id'], str) or not actor['id'].strip() or len(actor['id']) > 200:
        raise ValueError('Invalid motion confirmer')
    if (status == 'owner_confirmed' and actor['role'] != 'owner') or (status.startswith('agent_') and actor['role'] != 'agent'):
        raise ValueError('Motion status and confirmer disagree')
    return dict(status=status, labels=labels(raw['labels'], player_ids), actor=dict(actor))


def payload(project):
    review = project.get('visionReview', {})
    output = []
    for event in review.get('events', []):
        candidate = event.get('motionExample')
        if candidate is None:
            continue
        saved = project.get('visionAnnotations', {}).get(event['id'], {})
        decision = saved.get('motionExample')
        output.append(dict(id=event['id'], profileId=candidate['profileId'],
                           recordingGroupIds=candidate['recordingGroupIds'],
                           sourceIdentity=review['sourceIdentity'], intervalSeconds=candidate['intervalSeconds'],
                           navigationSeconds=event['seconds'], suggested=candidate.get('suggested', {}),
                           decision=decision, evidence=saved.get('evidence', []), note=saved.get('note', ''),
                           reviewSeconds=saved.get('reviewSeconds'), updatedAt=saved.get('updatedAt')))
    return dict(schema=SCHEMA, revision=project.get('revision', 0), examples=output,
                adoptedForScoring=False, adoptedForStatistics=False, adoptedForTraining=False,
                provenance='Actor records are local declared provenance, not authenticated identity. Agent actions must not claim owner confirmation.')


def split_windows(profile, queries, *, mode, context_seconds):
    """Exclude calibration clips plus model context; reject alternate exports of shared groups.

    Input intervals must cover each entire calibration/query clip or rally, rather
    than only the labelled frame. No automatic original/render time mapping exists.
    """
    if profile.get('schema') != SCHEMA or mode not in ('unseen_recording', 'session_assisted'):
        raise ValueError('Invalid motion profile or evaluation mode')
    if type(context_seconds) not in (int, float) or not math.isfinite(context_seconds) or context_seconds < 0:
        raise ValueError('A finite nonnegative context exclusion is required')
    buffer = Fraction(str(context_seconds)); support = []
    for e in profile['examples']:
        digest = e.get('sourceIdentity', {}).get('sha256')
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Support source identity required')
        support.append((set(groups(e.get('recordingGroupIds'))), digest, interval(e.get('intervalSeconds'))))
    accepted, excluded = [], []
    ids = set()
    for q in queries:
        qid = identifier(q.get('id'))
        if qid in ids:
            raise ValueError('Duplicate query window')
        ids.add(qid); qgroups = set(groups(q.get('recordingGroupIds'))); qa, qb = interval(q.get('intervalSeconds'))
        digest = q.get('sourceIdentity', {}).get('sha256')
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Query source identity required')
        reasons = set()
        for sgroups, sdigest, (sa, sb) in support:
            if digest == sdigest and not qgroups & sgroups:
                raise ValueError('Same source has contradictory recording groups')
            if not qgroups & sgroups:
                continue
            if mode == 'unseen_recording':
                reasons.add('recording_used_for_calibration')
            elif digest != sdigest:
                reasons.add('shared_recording_different_source_without_time_mapping')
            elif qa - buffer <= sb + buffer and qb + buffer >= sa - buffer:
                reasons.add('calibration_clip_or_temporal_context')
        (excluded if reasons else accepted).append(dict(q, exclusionReasons=sorted(reasons)))
    return dict(mode=mode, profileRevision=profile['revision'], contextSeconds=context_seconds,
                eligible=accepted, excluded=excluded, labelsRead=False)


if __name__ == '__main__':
    import argparse
    from local_model import Store, read, write
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export'); export.add_argument('directory'); export.add_argument('output')
    attach = sub.add_parser('attach'); attach.add_argument('directory'); attach.add_argument('event_id'); attach.add_argument('proposal')
    attach.add_argument('--expected-revision', type=int, required=True)
    split = sub.add_parser('split'); split.add_argument('profile'); split.add_argument('queries'); split.add_argument('output')
    split.add_argument('--mode', choices=['unseen_recording','session_assisted'], required=True)
    split.add_argument('--context-seconds', type=float, required=True)
    args = parser.parse_args()
    if args.command == 'attach':
        result = Store(args.directory).apply(args.expected_revision, dict(type='motion-example', eventId=args.event_id, proposal=read(args.proposal)))
        print('Motion example attached at project revision', result['revision'])
    elif args.command == 'export':
        write(args.output, payload(Store(args.directory).get()))
    else:
        write(args.output, split_windows(read(args.profile), read(args.queries), mode=args.mode, context_seconds=args.context_seconds))
