"""Check declared clip-ending evidence against current cuts; never infer ball state."""
import argparse
from fractions import Fraction
import json
from pathlib import Path

SCHEMA = 'tennis-endpoints/v1'


def seconds(value):
    # Decimal strings and rational strings preserve the original presentation clock.
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('Expected original PTS seconds, as a number or rational string')
    return Fraction(str(value))


def binding(project, clip):
    asset = next(a for a in project['assets'] if a['id'] == clip['assetId'])
    clock = asset['sourceMapping']
    if clock['schema'] != 'original-pts-grid/v1':
        raise ValueError('Bind original source timing before endpoint checks')
    return dict(assetId=asset['id'], pointId=clip.get('pointId'),
                inFrame=clip['inFrame'], outFrame=clip['outFrame'],
                sourceSha256=asset['sourceIdentity']['sha256'],
                originSeconds=clock['originSeconds'], timeBase=clock['timeBase'],
                fps=str(project['fps']))


def template(project):
    return dict(schema=SCHEMA, records=[dict(clipId=c['id'], binding=binding(project, c),
        status='pending', anchor=None, lastLiveSeconds=None, endWindowSeconds=None,
        retainThroughSeconds=None, forwardWindowSeconds=None, continuationFound=None,
        cessationObserved=None, reason='', evidence=[]) for c in project['clips']
        if c.get('kind', 'video') == 'video'])


def check_record(project, clip, record, evidence_base=None):
    if record.get('binding') != binding(project, clip):
        raise ValueError('Stale source/cut binding; inspect the changed cut and refresh this record')
    status = record.get('status')
    if status not in ('verified', 'uncertain', 'source_truncated'):
        raise ValueError('Endpoint still pending')
    if not isinstance(record.get('reason'), str) or not record['reason'].strip():
        raise ValueError('Describe the ending evidence or concrete remaining gap')
    refs = record.get('evidence')
    if not isinstance(refs, list) or not refs or any(not isinstance(x, str) or not x.strip() for x in refs):
        raise ValueError('Retained evidence/observation file references required')
    if evidence_base is not None and any(not (Path(evidence_base) / x).is_file() for x in refs):
        raise ValueError('Referenced evidence file is missing')
    b = record['binding']; rate = seconds(b['fps']); origin = seconds(b['originSeconds'])
    start, cut = (origin + Fraction(b[k]) / rate for k in ('inFrame', 'outFrame'))
    asset = next(a for a in project['assets'] if a['id'] == b['assetId'])
    available_end = origin + Fraction(asset['frames']) / rate
    anchor = record['anchor']; at = seconds(anchor['sourceSeconds'])
    kind = anchor['kind']
    if kind not in ('next_serve', 'recording_end', 'source_gap'):
        raise ValueError('Use the next actual serve, recording end, or documented source gap')
    if not cut <= at <= available_end:
        raise ValueError('Cut crosses anchor, or anchor is outside the working source')
    if kind == 'next_serve':
        if anchor.get('relation') not in ('same_point', 'next_point', 'unknown'):
            raise ValueError('A next serve is not automatically a next point; declare its relation')
    elif not isinstance(anchor.get('reason'), str) or not anchor['reason'].strip():
        raise ValueError('Explain why no next-serve anchor is available')
    if kind == 'recording_end' and at != available_end:
        raise ValueError('Recording-end anchor must reach the available source end')
    if kind == 'recording_end' and asset.get('sourceProbe', {}).get('format', {}).get('duration'):
        fmt = asset['sourceProbe']['format']
        original_end = seconds(fmt.get('start_time', 0)) + seconds(fmt['duration'])
        if available_end + 1 / rate < original_end:
            raise ValueError('Bounded proxy is not the recording end; inspect the remaining original')
    live = seconds(record['lastLiveSeconds'])
    retain = seconds(record['retainThroughSeconds'])
    forward = record['forwardWindowSeconds']
    if not isinstance(forward, list) or len(forward) != 2:
        raise ValueError('Forward inspection window required')
    first, last = map(seconds, forward)
    if not origin <= first <= live <= retain < cut or live < start or not cut <= last <= at:
        raise ValueError('Forward window must cover last live play, retained ending, and the actual cut')
    if live == retain and status != 'source_truncated':
        raise ValueError('Retain ending evidence after the last observed live ball')
    if last == cut and not (kind != 'next_serve' and cut == at):
        raise ValueError('Inspect original footage beyond the proposed cut')
    if record.get('continuationFound') is not False:
        raise ValueError('Continuation after the proposed cut is unchecked or requires repair')
    if status == 'verified':
        window = record.get('endWindowSeconds')
        if not isinstance(window, list) or len(window) != 2:
            raise ValueError('Observed first-dead-ball bracket required')
        low, high = map(seconds, window)
        if not live <= low <= high <= retain:
            raise ValueError('Dead-ball bracket must follow live play and fit before the retained tail')
    else:
        if record.get('endWindowSeconds') is not None:
            raise ValueError('Uncertain endings must not claim a verified dead-ball timestamp')
        if status == 'uncertain' and record.get('cessationObserved') is not True:
            raise ValueError('Keep footage through observed cessation before using an uncertain ending')
        if status == 'source_truncated' and (kind == 'next_serve' or cut != at):
            raise ValueError('Source-truncated endings must retain through the available boundary')


def audit(project, document, evidence_base=None):
    if document.get('schema') != SCHEMA or not isinstance(document.get('records'), list):
        raise ValueError('Expected ' + SCHEMA)
    clips = {c['id']: c for c in project['clips'] if c.get('kind', 'video') == 'video'}
    if not clips:
        raise ValueError('No video clips to inspect')
    records = {}; findings = []; provisional = []
    for r in document['records']:
        cid = r.get('clipId')
        if cid not in clips or cid in records:
            findings.append(dict(clipId=cid, issue='Unknown or duplicate clip record'))
        else:
            records[cid] = r
    for cid, clip in clips.items():
        if cid not in records:
            findings.append(dict(clipId=cid, issue='Missing endpoint record')); continue
        try:
            check_record(project, clip, records[cid], evidence_base)
            if records[cid]['status'] != 'verified': provisional.append(cid)
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
            findings.append(dict(clipId=cid, issue=str(error)))
    return dict(checksPassed=not findings, complete=not findings and not provisional,
                checkedClips=len(clips), provisionalClipIds=provisional, findings=findings,
                scope='Declared evidence and current source/cut consistency only; not visual proof or score adjudication')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('project', help='Current local project.json, or equivalent assets/fps/clips mapping')
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--template', help='Write a new pending evidence document; never overwrite')
    group.add_argument('--evidence', help='Check filled evidence against current cuts')
    a = p.parse_args(); project = json.loads(Path(a.project).read_text(encoding='utf-8-sig'))
    if a.template:
        with Path(a.template).open('x', encoding='utf-8') as f:
            json.dump(template(project), f, ensure_ascii=False, indent=2)
    else:
        path = Path(a.evidence)
        result = audit(project, json.loads(path.read_text(encoding='utf-8-sig')), path.resolve().parent)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result['checksPassed']: raise SystemExit(2)


if __name__ == '__main__':
    main()
