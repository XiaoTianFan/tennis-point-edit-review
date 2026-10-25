"""Bind complete stream evidence and unadopted event proposals to a new editor plan."""
import argparse
from fractions import Fraction
import json
import math
from pathlib import Path

from cv_stream import read, validate_chunks
from local_model import write
from local_vision import SCHEMA, validate_vision
from media_probe import identity
from source_binding import unchanged


def make_plan(stream_path, proposals_path, media_path, players_path, output):
    stream_path = Path(stream_path).resolve()
    stream = read(stream_path); proposals = read(proposals_path); media = read(media_path)
    if stream.get('schema') != 'tennis-vision-stream/v1' or stream.get('status') != 'complete':
        raise ValueError('A complete committed stream is required')
    if proposals.get('schema') != 'tennis-vision-proposals/v1' or proposals.get('status') != 'complete':
        raise ValueError('Complete unadopted event proposals required')
    source = stream['sourceIdentity']; digest = source['sha256']
    if any(item.get('sourceIdentity', {}).get('sha256') != digest for item in [proposals, media]):
        raise ValueError('Event proposals, stream and review media have different sources')
    unchanged(source)
    if proposals.get('streamIdentity', {}).get('sha256') != identity(stream_path)['sha256']:
        raise ValueError('Event proposals refer to a different stream result')
    validate_chunks(stream_path.parent, dict(chunks=stream['chunks'], **stream['coverage']))
    if media.get('sourceMapping', {}).get('schema') != 'original-pts-grid/v1':
        raise ValueError('Bound review media required')
    origin = Fraction(media['sourceMapping']['originSeconds']); rate = Fraction(media['fps'])
    first = Fraction(stream['coverage']['firstSeconds']); last = Fraction(stream['coverage']['lastSeconds'])
    if abs(first-origin)*rate > 1 or not last < origin+Fraction(media['frames'])/rate or abs(last-origin-Fraction(media['frames']-1)/rate)*rate > 1:
        raise ValueError('Review media must cover the complete source stream')
    if Path(output).exists():
        raise ValueError('Plan already exists')
    observed = set()
    for chunk in stream['chunks']:
        with (stream_path.parent/'chunks'/chunk['file']).open(encoding='utf-8') as f:
            observed.update(Fraction(json.loads(line)['seconds']) for line in f)
    events = []
    for event in proposals.get('events', []):
        seconds = Fraction(event['seconds'])
        if seconds not in observed:
            raise ValueError('Event navigation timestamp is not a committed source PTS')
        frame = math.floor((seconds-origin)*rate+Fraction(1, 2))
        events.append(dict(event, frame=frame))
    asset = dict(media, id='vision-source')
    review = dict(schema=SCHEMA, assetId=asset['id'], sourceIdentity=source,
                  streamIdentity=identity(stream_path), proposalIdentity=identity(proposals_path), events=events,
                  quality=proposals.get('quality', 'unqualified'), metrics=proposals.get('metrics', {}))
    players = read(players_path)
    validate_vision(dict(assets=[asset], fps=media['fps'], visionReview=review, players=players))
    plan = dict(title='视觉事件证据复核', outputLanguage='zh-CN', workingMode='agent-dominant',
                players=players, assets=[dict(id=asset['id'], metadata=str(Path(media_path).resolve()))],
                clips=[dict(id='vision-full-source', assetId=asset['id'], inFrame=0, outFrame=media['frames'], label='完整源视频')],
                review=dict(source='cv:'+stream['runId'], ledgerRevision='cv:'+stream['runId'][:16], purpose='vision-events', rows=[]),
                visionReview=review, visionAnnotations={}, overlays=[], statistics=dict(status='pending'), approval={})
    write(output, plan)
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['stream', 'proposals', 'media', 'players', 'output']:
        parser.add_argument(name)
    args = parser.parse_args()
    result = make_plan(args.stream, args.proposals, args.media, args.players, args.output)
    print(f"Created full-source event review plan: {len(result['visionReview']['events'])} unadopted events")
