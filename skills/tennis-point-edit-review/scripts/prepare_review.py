"""Publish initial point labeling BEFORE agent adjudication, for either work mode."""
import argparse
import copy
from fractions import Fraction
from pathlib import Path

from local_editor import initialize
from local_model import read, write
from output_language import resolve_language
from review_io import build


def prepare(plan, base, provisional=False, mode='agent-dominant'):
    if mode not in ('agent-dominant', 'human-first'):
        raise ValueError('Unknown working mode')
    p = copy.deepcopy(plan)
    language = resolve_language(p.get('outputLanguage'))
    base = Path(base).resolve()
    assets = {}
    for asset in p['assets']:
        if 'metadata' in asset:
            asset['metadata'] = str((base / asset['metadata']).resolve())
            assets[asset['id']] = {**asset, **read(asset['metadata'])}
        else:
            asset['path'] = str((base / asset['path']).resolve())
            assets[asset['id']] = asset
    fps = Fraction(str(p.get('fps', next(iter(assets.values()))['fps'])))
    existing = p.get('review', {})
    if not existing.get('source') or not existing.get('ledgerRevision'):
        raise ValueError('Source and ledgerRevision required')
    if existing.get('rows') or p.get('answers'):
        raise ValueError('Already published review: resume it; never replace rows or answers with a blank scaffold')
    rows, grouped, start = [], {}, 0
    used = {c.get('pointId') for c in p['clips'] if c.get('pointId')}
    candidate_index = 1
    for clip in p['clips']:
        if clip.get('kind') == 'hold':
            start += clip.get('durationFrames', round(Fraction(str(clip.get('durationSeconds', 0))) * fps))
            continue
        if any(k in clip for k in ('inSeconds', 'outSeconds')):
            if any(k in clip for k in ('inFrame', 'outFrame')):
                raise ValueError('Specify seconds or frames, not both')
            clip['inFrame'] = round(Fraction(str(clip.pop('inSeconds'))) * fps)
            clip['outFrame'] = round(Fraction(str(clip.pop('outSeconds'))) * fps)
        if 'pointId' not in clip:
            if not provisional:
                raise ValueError('Group clips into stable pointId values first, or explicitly use --provisional-points')
            while 'P' + str(candidate_index).zfill(5) in used:
                candidate_index += 1
            clip['pointId'] = 'P' + str(candidate_index).zfill(5)
            used.add(clip['pointId']); candidate_index += 1
            clip['candidatePoint'] = True
        asset = assets[clip['assetId']]
        if asset.get('timing') != 'cfr-proxy' or Fraction(asset['fps']) != fps:
            raise ValueError('Use prepared CFR media at the timeline rate')
        a, b = clip['inFrame'], clip['outFrame']
        if type(a) is not int or type(b) is not int or not 0 <= a < b <= asset['frames']:
            raise ValueError('Invalid clip range')
        pid = clip['pointId']
        if pid not in grouped:
            row = dict(reviewId='R' + str(len(rows)+1).zfill(3), pointId=pid,
                       **{k:clip.get(k) for k in ('serverId','serveNumber','gameNumber','setNumber')},
                       mainStartSeconds=float(Fraction(start, 1)/fps), reviewStartSeconds=float(Fraction(start, 1)/fps),
                       sourceRangesSeconds=[], evidenceRanges=[], initial={},
                       candidatePoint=bool(clip.get('candidatePoint')), countingIssueRequired=False,
                       reason=('Initial labeling: no agent outcome yet. ' if language == 'en' else '首次标注：尚无agent球果判断。') +
                              (('Candidate segment; verify point grouping, note any merge/split needed.' if language == 'en' else '候选片段；先核实分的归组，需合并/拆分请注明。') if clip.get('candidatePoint') else ''))
            rows.append(row); grouped[pid] = row
        row = grouped[pid]
        source_start = Fraction(str(asset.get('sourceStartSeconds', 0)))
        row['sourceRangesSeconds'].append([float(source_start + Fraction(a, 1)/fps), float(source_start + Fraction(b, 1)/fps)])
        row['evidenceRanges'].append(dict(assetId=clip['assetId'], inFrame=a, outFrame=b,
                                          originalPath=asset.get('originalPath'), sourceMapping=clip.get('sourceMapping')))
        start += b-a
    if not rows:
        raise ValueError('No point/candidate clips to label')
    # Separate draft/revision identity from later stage-3 exception review.
    review = dict(source=existing['source'], ledgerRevision=str(existing['ledgerRevision']) + ':initial',
                  timelineName=p['title'], outputLanguage=language, purpose='initial-labeling',
                  workingMode=mode, players=p['players'], rows=rows)
    p.update(outputLanguage=language, workingMode=mode, review=review)
    ledger = dict(source=review['source'], ledgerRevision=review['ledgerRevision'], purpose='initial-labeling',
                  players=p['players'], points=[dict(pointId=r['pointId'], serverId=None, reviewStatus='pending',
                  candidatePoint=r['candidatePoint'], evidenceRanges=r['evidenceRanges']) for r in rows])
    return p, review, ledger


def publish(plan_path, directory, mode='agent-dominant', surface='local', provisional=False):
    plan_path, directory = Path(plan_path).resolve(), Path(directory).resolve()
    if directory.exists():
        raise ValueError('Use a new review directory; resume existing drafts in place')
    if surface not in ('html', 'local', 'both'):
        raise ValueError('Unknown review surface')
    plan, review, ledger = prepare(read(plan_path), plan_path.parent, provisional, mode)
    directory.mkdir(parents=True)
    write(directory/'plan.json', plan)
    write(directory/'review-data.json', review)
    write(directory/'ledger.json', ledger)
    if surface in ('html', 'both'):
        build(review, directory/'review.html')
    if surface in ('local', 'both'):
        initialize(plan, directory/'edit', directory)
    write(directory/'handoff.json', dict(workingMode=mode, purpose='initial-labeling',
          nextAction='wait-for-human-labeling' if mode == 'human-first' else 'agent-adjudication',
          reviewReady=True, adjudicationPerformed=False, rows=len(review['rows']),
          note='Use one active answer surface; reconcile exports if both were used.'))
    return directory


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan'); parser.add_argument('directory')
    parser.add_argument('--mode', choices=['agent-dominant', 'human-first'], default='agent-dominant')
    parser.add_argument('--surface', choices=['html', 'local', 'both'], default='local')
    parser.add_argument('--provisional-points', action='store_true')
    args = parser.parse_args()
    print(publish(args.plan, args.directory, args.mode, args.surface, args.provisional_points))
