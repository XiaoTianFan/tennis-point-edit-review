"""Map historical source-clock agent labels into a new rendered-input clock.

Manifest consistency is evidence for a mapping, not proof of pixel identity or
independent ground truth. Explicitly inspected render correspondences remain
necessary. Deleted source files are not required to map retained labels.
"""
import argparse
from fractions import Fraction
from pathlib import Path

from local_model import read, write, layout
from media_probe import identity, metadata


def render_mapping(project, export, actual_frames, actual_fps):
    if export.get('state')!='complete' or export.get('revision')!=project['revision']:
        raise ValueError('Require completed export and matching saved project revision')
    rate=Fraction(str(project['fps']))
    if Fraction(str(export['settings']['fps']))!=rate or Fraction(str(actual_fps))!=rate:
        raise ValueError('Different export frame rates need a separately verified resampling map')
    if actual_frames!=export['frames'] or export.get('timelineFrames')!=actual_frames:
        raise ValueError('Rendered frame count disagrees with export')
    master={c['id']:c for c in layout(project)}
    assets={a['id']:a for a in project['assets']}
    if 'clipIds' not in export['settings'] or 'ranges' not in export:
        raise ValueError('Legacy export has no explicit clip order/ranges; verify its map separately')
    selected=export['settings']['clipIds']
    ranges=export['ranges']
    if [r['clipId'] for r in ranges]!=selected or len(selected)!=len(set(selected)):
        raise ValueError('Ambiguous export order')
    output=[];end=0
    for item in ranges:
        clip=master[item['clipId']]
        a,b=item['exportStartFrame'],item['exportEndFrame']
        if a!=end or b<=a or b-a!=clip['endFrame']-clip['startFrame'] or (item['masterStartFrame'],item['masterEndFrame'])!=(clip['startFrame'],clip['endFrame']):
            raise ValueError('Export range/trim mismatch')
        end=b
        asset=assets[clip['assetId']]
        clock=asset.get('sourceMapping')
        if clock:
            origin=Fraction(clock['originSeconds']);clock_kind='bound_original_pts_grid'
        else:
            probe=asset.get('sourceProbe',{})
            if not probe or Fraction(probe.get('format',{}).get('start_time','0'))!=0 or asset.get('sourceStartSeconds',0)!=0:
                raise ValueError('Legacy origin not established; provide an explicit mapping')
            origin=Fraction(0);clock_kind='legacy_zero_origin_from_saved_sourceProbe; conditional'
        output.append(dict(clipId=clip['id'],pointId=clip.get('pointId'),assetId=clip['assetId'],
                           kind=clip.get('kind','video'),renderFrames=[a,b],
                           sourceFrames=[clip['inFrame'],clip.get('outFrame')],originSeconds=str(origin),
                           clockBasis=clock_kind,fps=str(rate)))
    if end!=actual_frames:raise ValueError('Export coverage incomplete')
    return output


def map_label(rows, asset_id, seconds, bracket=None):
    """Return ALL retained occurrences; hold frames are never new gameplay events."""
    t=Fraction(str(seconds));result=[]
    for row in rows:
        if row['kind']=='hold' or row['assetId']!=asset_id:continue
        fps=Fraction(row['fps']);origin=Fraction(row['originSeconds'])
        a,b=[origin+Fraction(f)/fps for f in row['sourceFrames']]
        if not a<=t<b:continue
        offset=Fraction(row['renderFrames'][0])/fps-a
        bounds=list(map(lambda x:Fraction(str(x)),bracket or [seconds,seconds]))
        retained=a<=bounds[0]<=bounds[1]<b
        result.append(dict(clipId=row['clipId'],pointId=row['pointId'],seconds=str(t+offset),
                           bracketSeconds=[str(x+offset) for x in bounds] if retained else None,
                           bracketStatus='retained' if retained else 'crosses_trim_unmappable',
                           provenance='mapped_agent_baseline',clockBasis=row['clockBasis']))
    return dict(status='mapped' if result else 'not_retained_or_unknown_asset',occurrences=result)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('project');p.add_argument('export');p.add_argument('render');p.add_argument('output')
    a=p.parse_args()
    if Path(a.output).exists():raise ValueError('Use a new mapping output')
    project=read(a.project);export=read(a.export);info=metadata(a.render)
    fingerprint=identity(a.render)
    if export.get('sha256') and export['sha256']!=fingerprint['sha256']:
        raise ValueError('Render no longer matches exported bytes')
    video=next(s for s in info['streams'] if s['codec_type']=='video')
    rows=render_mapping(project,export,int(video['nb_frames']),video['avg_frame_rate'])
    write(a.output,dict(schema='tennis-render-reference-map/v1',sourceIdentity=fingerprint,
                        projectIdentity=identity(a.project),exportIdentity=identity(a.export),
                        rows=rows,status='manifest_consistent',pixelCorrespondence='not_verified',
                        referenceKind='agent_baseline_not_independent_ground_truth'))
    print('Mapped',len(rows),'ranges; visual correspondence still requires inspection')


if __name__=='__main__':main()
