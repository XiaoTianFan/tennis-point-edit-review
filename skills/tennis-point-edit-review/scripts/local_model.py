"""Portable local timeline model, review protocol and revision-fenced persistence."""
from output_language import resolve_language
import copy
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

SCHEMA = 'tennis-local-edit/v1'
CAUSES = {'out', 'net', 'two_bounces', 'replay', 'ace', 'winner', 'other'}
COMPONENTS = {'scoreboard', 'serveLabel', 'serveSpeed', 'statsPanel', 'reviewId', 'reviewLabel', 'explanation'}

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)

def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(label + ' must be an integer >= ' + str(minimum))
    return value

def keyed(items, label):
    result = {}
    for item in items:
        key = item.get('id')
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', key) or key in result:
            raise ValueError('Invalid/duplicate ' + label + ' id')
        result[key] = item
    return result

def duration(clip):
    return clip['durationFrames'] if clip.get('kind') == 'hold' else clip['outFrame'] - clip['inFrame']

def layout(project):
    start = 0
    result = []
    for clip in project['clips']:
        result.append({**clip, 'startFrame': start, 'endFrame': start + duration(clip)})
        start += duration(clip)
    return result

def overlay_range(overlay, clip):
    if overlay.get('anchor', 'clip') == 'source':
        start, end = overlay['startFrame'] - clip['inFrame'], overlay['endFrame'] - clip['inFrame']
    else:
        start, end = overlay['startFrame'], overlay['endFrame']
    return max(0, start), min(duration(clip), end)

def validate(project, check_files=False):
    resolve_language(project.get("outputLanguage"))
    if project.get('schema') != SCHEMA:
        raise ValueError('Unsupported project schema')
    integer(project.get('revision'), 'revision')
    fps = Fraction(str(project['fps']))
    if not 1 <= fps <= 240:
        raise ValueError('fps outside 1..240')
    for key in ('width', 'height'):
        integer(project[key], key, 2)
        if project[key] > 8192 or project[key] % 2:
            raise ValueError('Use even dimensions <= 8192')
    if project.get('audio'):
        integer(project['audio']['sampleRate'], 'audio sample rate', 1)
        integer(project['audio']['channels'], 'audio channels', 1)
        if project['audio']['sampleRate'] > 96000 or project['audio']['channels'] > 8:
            raise ValueError('Unsupported audio configuration')
    players = keyed(project['players'], 'player')
    if len(players) != 2:
        raise ValueError('Local review currently requires two scoring sides')
    assets = keyed(project['assets'], 'asset')
    for asset in assets.values():
        integer(asset['frames'], 'asset frames', 1)
        if check_files and not Path(asset['path']).is_file():
            raise ValueError('Media unavailable: ' + asset['id'])
    rows = project['review']['rows']
    if not project['review'].get('source') or not project['review'].get('ledgerRevision'):
        raise ValueError('Review source and ledgerRevision required')
    pids = [r['pointId'] for r in rows]
    rids = [r['reviewId'] for r in rows]
    if len(set(pids)) != len(pids) or len(set(rids)) != len(rids):
        raise ValueError('Review point and review IDs must be unique')
    for row in rows:
        if row['serverId'] not in players:
            raise ValueError('Unknown server')
    clips = keyed(project['clips'], 'clip')
    if not clips:
        raise ValueError('At least one clip required')
    for clip in clips.values():
        if clip['assetId'] not in assets or clip.get('kind', 'video') not in ('video', 'hold'):
            raise ValueError('Invalid clip asset or kind')
        integer(clip['inFrame'], 'inFrame')
        if clip.get('kind') == 'hold':
            integer(clip['durationFrames'], 'durationFrames', 1)
            if clip['inFrame'] >= assets[clip['assetId']]['frames']:
                raise ValueError('Hold frame outside asset')
        elif not clip['inFrame'] < integer(clip['outFrame'], 'outFrame', 1) <= assets[clip['assetId']]['frames']:
            raise ValueError('Clip outside source or empty')
        # Timeline points include clear points outside the human-review subset.
        point_id = clip.get('pointId')
        if point_id is not None and (not isinstance(point_id, str) or not point_id.strip()):
            raise ValueError('Invalid clip point ID')
    for overlay in keyed(project.get('overlays', []), 'overlay').values():
        if overlay['clipId'] not in clips or overlay['component'] not in COMPONENTS:
            raise ValueError('Unknown overlay target/component')
        if overlay.get('anchor', 'clip') not in ('clip', 'source'):
            raise ValueError('Unknown overlay anchor')
        if integer(overlay['endFrame'], 'overlay end', 1) <= integer(overlay['startFrame'], 'overlay start'):
            raise ValueError('Empty overlay')
    for pid, answer in project.get('answers', {}).items():
        if pid not in pids:
            raise ValueError('Unknown answer point')
        normalize_answer(answer, players)
    return project

def normalize_answer(raw, players):
    x = {'scoringPlayerId': None, 'winnerUndetermined': False, 'deadBallType': None,
         'doubleFaultConfirmed': None, 'extra': False, 'reviewConfirmed': False,
         'countingIssueResolved': False, 'note': '', **raw}
    if x['scoringPlayerId'] is not None and x['scoringPlayerId'] not in players:
        raise ValueError('Unknown scoring player')
    if x['deadBallType'] is not None and x['deadBallType'] not in CAUSES:
        raise ValueError('Unknown cause')
    for name in ('winnerUndetermined', 'extra', 'reviewConfirmed', 'countingIssueResolved'):
        if type(x[name]) is not bool:
            raise ValueError('Invalid boolean: ' + name)
    if x['doubleFaultConfirmed'] is not None and type(x['doubleFaultConfirmed']) is not bool:
        raise ValueError('Invalid double fault')
    if not isinstance(x['note'], str) or len(x['note']) > 10000:
        raise ValueError('Invalid note')
    if x['deadBallType'] == 'replay':
        x.update(scoringPlayerId=None, winnerUndetermined=False, doubleFaultConfirmed=None, extra=False)
    if x['winnerUndetermined']:
        x.update(scoringPlayerId=None, doubleFaultConfirmed=None)
        if x['deadBallType'] == 'ace':
            x['deadBallType'] = None
    return x

def review_payload(project):
    players = {p['id']: p for p in project['players']}
    result = []
    for row in project['review']['rows']:
        x = normalize_answer(project.get('answers', {}).get(row['pointId'], {**row.get('initial', {}), 'reviewConfirmed': False}), players)
        if not x['reviewConfirmed']:
            status = 'partial' if x['scoringPlayerId'] or x['deadBallType'] or x['note'] else 'pending'
        elif x['winnerUndetermined']:
            status = 'unresolved'
        elif row.get('countingIssueRequired') and not x['countingIssueResolved']:
            status = 'partial'
        elif x['deadBallType'] == 'replay':
            status = 'replay'
        else:
            status = 'resolved' if x['scoringPlayerId'] and x['deadBallType'] else 'partial'
        result.append({**x, 'reviewId': row['reviewId'], 'pointId': row['pointId'], 'serverId': row['serverId'],
            'scoringPlayer': players.get(x['scoringPlayerId'], {}).get('name'), 'status': status,
            'inferenceRequired': x['winnerUndetermined'] and x['reviewConfirmed'] and not x['extra'],
            'countsTowardScore': False if x['extra'] or x['deadBallType'] == 'replay' else None,
            'countingStatus': 'extra' if x['extra'] else 'replay' if x['deadBallType'] == 'replay' else None})
    return {'schema': 'tennis-point-review/v1', 'source': project['review']['source'],
        'ledgerRevision': project['review']['ledgerRevision'], 'timelineName': project['title'],
        'totalRows': len(result), 'completedRows': sum(r['status'] in ('resolved', 'replay', 'unresolved') for r in result),
        'unresolvedRows': sum(r['status'] == 'unresolved' for r in result),
        'inferenceRequiredRows': sum(r['inferenceRequired'] for r in result), 'rows': result}

def context(project):
    return {'schema': 'tennis-local-context/v1', 'revision': project['revision'],
        'outputLanguage': resolve_language(project.get('outputLanguage')),
        'review': review_payload(project), 'timeline': layout(project), 'assets': project['assets'],
        'overlays': project.get('overlays', []), 'selection': project.get('selection', {}),
        'needsRebuild': project.get('needsRebuild', []), 'events': project.get('events', [])}

class Conflict(ValueError):
    pass

class Store:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.path = self.directory / 'project.json'

    @contextmanager
    def locked(self):
        lock = self.directory / '.write-lock'
        try:
            handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise Conflict('Another writer is active; reload and retry')
        try:
            os.close(handle)
            yield
        finally:
            lock.unlink()

    def get(self):
        return validate(read(self.path))

    def commit(self, value, expected, event):
        with self.locked():
            current = self.get()
            if current['revision'] != expected:
                raise Conflict('Project changed in another tab or agent; reload before retrying')
            value = copy.deepcopy(value)
            value['revision'] = expected + 1
            value['events'] = (current.get('events', []) + [{'revision': value['revision'],
                'at': datetime.now(timezone.utc).isoformat(), **event}])[-200:]
            validate(value)
            write(self.directory / 'history' / f'{expected:06}.json', current)
            write(self.path, value)
            return value

    def apply(self, expected, operation):
        p = self.get()
        kind = operation['type']
        if kind in ('undo', 'redo'):
            source, target = ('undo', 'redo') if kind == 'undo' else ('redo', 'undo')
            stack = p.get(source, [])
            if not stack:
                raise ValueError('Nothing to ' + kind)
            value = copy.deepcopy(p)
            snapshot = value[source].pop()
            value.setdefault(target, []).append({k: copy.deepcopy(p[k]) for k in ('clips', 'overlays', 'answers', 'needsRebuild')})
            value.update(snapshot)
        else:
            value = copy.deepcopy(p)
            if kind != 'selection':
                value['undo'] = (p.get('undo', []) + [{k: copy.deepcopy(p.get(k, {} if k == 'answers' else [])) for k in ('clips', 'overlays', 'answers', 'needsRebuild')}])[-40:]
                value['redo'] = []
            clips = keyed(value['clips'], 'clip')
            if kind == 'trim':
                clip = clips[operation['id']]
                if clip.get('kind') == 'hold':
                    clip['durationFrames'] = integer(operation['durationFrames'], 'duration', 1)
                else:
                    clip.update(inFrame=integer(operation['inFrame'], 'in'), outFrame=integer(operation['outFrame'], 'out', 1))
                value['needsRebuild'] = sorted(set(value.get('needsRebuild', []) + ['clip-evidence', 'graphics-timing']))
            elif kind == 'reorder':
                order = operation['ids']
                if len(order) != len(clips) or set(order) != set(clips):
                    raise ValueError('Reorder must include every clip exactly once')
                value['clips'] = [clips[c] for c in order]
                value['needsRebuild'] = sorted(set(value.get('needsRebuild', []) + ['presentation-order']))
            elif kind == 'overlay':
                o = keyed(value['overlays'], 'overlay')[operation['id']]
                o.update(startFrame=integer(operation['startFrame'], 'start'), endFrame=integer(operation['endFrame'], 'end', 1))
                value['needsRebuild'] = sorted(set(value.get('needsRebuild', []) + ['graphics-timing']))
            elif kind == 'review':
                row = next(r for r in value['review']['rows'] if r['pointId'] == operation['pointId'])
                answer = normalize_answer(operation['answer'], {p['id'] for p in value['players']})
                if answer['deadBallType'] == 'ace' and answer['scoringPlayerId'] != row['serverId']:
                    raise ValueError('ACE must belong to the server')
                if answer['doubleFaultConfirmed'] and answer['scoringPlayerId'] == row['serverId']:
                    raise ValueError('Double fault cannot score for server')
                value.setdefault('answers', {})[row['pointId']] = answer
                value['needsRebuild'] = sorted(set(value.get('needsRebuild', []) + ['score-and-statistics']))
            elif kind == 'selection':
                value['selection'] = {k: operation[k] for k in ('clipId', 'frame', 'mode') if k in operation}
            else:
                raise ValueError('Unknown operation')
        return self.commit(value, expected, {'type': kind, 'operation': operation})
