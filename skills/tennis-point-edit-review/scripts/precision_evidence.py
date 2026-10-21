"""Native original-PTS ROI frames and adjacent bracketing, never proxy/grid timing."""
import argparse
from fractions import Fraction
import io
import json
import math
from pathlib import Path
from media_probe import metadata
from source_binding import verify_original, unchanged
from stage_cache import Stage, safe, save

PURPOSES = ('line','net','contact','speed')


def extract(asset, start, end, output, purpose, roi, max_frames=240, job=None):
    import av
    if purpose not in PURPOSES: raise ValueError('Choose a precision purpose')
    if not all(math.isfinite(float(x)) for x in (start,end)) or not 0 <= start < end or end-start > 15:
        raise ValueError('Use a finite original-PTS window of at most 15 seconds')
    if type(max_frames) is not int or not 3 <= max_frames <= 1200:
        raise ValueError('Use 3..1200 frames per bounded window')
    if not isinstance(roi,(list,tuple)) or len(roi)!=4 or any(type(x) is not int for x in roi):
        raise ValueError('Explicit native coded-pixel ROI x,y,width,height required')
    fingerprint = verify_original(asset)
    info = metadata(fingerprint['path'])
    video = next(s for s in info['streams'] if s['codec_type']=='video')
    if video.get('color_transfer') in ('smpte2084','arib-std-b67'):
        raise ValueError('HDR precision display requires an explicitly verified transform')
    x,y,w,h=roi
    if min(x,y)<0 or min(w,h)<=0 or x+w>video['width'] or y+h>video['height']:
        raise ValueError('ROI outside native coded frame')
    out=safe(output); out.mkdir(parents=True,exist_ok=False)
    job=safe(job) if job else out
    if not out.is_relative_to(job): raise ValueError('Evidence catalog must be inside the declared job')
    stage=Stage.create(job,purpose)
    start,end=Fraction(str(start)),Fraction(str(end))
    result=dict(schema='tennis-precision-evidence/v1',stageId=stage.owner['stageId'],purpose=purpose,
                sourceIdentity=fingerprint,sourceTimeBase=video['time_base'],windowSeconds=[str(start),str(end)],
                coordinateSpace='native-coded-pixels',sourceSize=[video['width'],video['height']],crop=list(roi),
                sampleAspectRatio=video.get('sample_aspect_ratio','1:1'),displayMatrix=video.get('side_data_list',[]),
                sourceToImageScale=[1,1],imageToDisplayScale=[1,1],resampled=False,
                pixelTransform='decoded source to RGB24, then integer ROI crop; no resize or fps filter',
                visualReview='not_performed',uncertainty='PTS quantization is not shutter/contact uncertainty; retain observed event brackets',
                status='extracting',records=[])
    last_time=None; previous=None
    def emit(frame,relation):
        if len(result['records']) >= max_frames: raise ValueError('Frame bound reached; split into overlapping windows')
        image=frame.to_image().crop((x,y,x+w,y+h))
        stream=io.BytesIO(); image.save(stream,format='PNG')
        name=f'roi-{len(result["records"]):05d}.png'
        ref=stage.put(name,stream.getvalue())
        result['records'].append(dict(pts=frame.pts,timeBase=str(frame.time_base),
            sourceSeconds=str(frame.pts*frame.time_base),relation=relation,image=ref,
            artifact=name,pixelSize=[w,h],displayScale=[1,1]))
    try:
        with av.open(fingerprint['path']) as container:
            stream=container.streams.video[0]; stream.thread_count=2
            container.seek(int(start/stream.time_base),stream=stream,backward=True,any_frame=False)
            entered=False
            for frame in container.decode(stream):
                if frame.pts is None: raise ValueError('Native frame missing PTS')
                t=frame.pts*frame.time_base
                if last_time is not None and t<=last_time: raise ValueError('Nonmonotone native PTS')
                last_time=t
                if t<start:
                    previous=frame
                    continue
                if not entered:
                    if previous is not None: emit(previous,'before')
                    entered=True
                emit(frame,'inside' if t<end else 'after')
                if t>=end: break
        unchanged(fingerprint)
        if not any(r['relation']=='inside' for r in result['records']): raise ValueError('No frames inside requested window')
        result['status']='extracted'
        result['bracketing']={k:any(r['relation']==k for r in result['records']) for k in ('before','after')}
        return result
    except BaseException as error:
        result['status']='partial'; result['error']=str(error)
        raise
    finally:
        save(out/'evidence.json',result,exclusive=True)
        stage.index(out/'evidence.json')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('asset',help='Bound .media.json, or project.json with --asset-id')
    p.add_argument('start',type=float); p.add_argument('end',type=float); p.add_argument('output')
    p.add_argument('--asset-id');p.add_argument('--purpose',required=True,choices=PURPOSES)
    p.add_argument('--roi',required=True);p.add_argument('--max-frames',type=int,default=240)
    p.add_argument('--job',required=True,help='Full job root containing canonical records and output')
    a=p.parse_args()
    from local_model import read
    asset=read(a.asset)
    if a.asset_id: asset=next(x for x in asset['assets'] if x['id']==a.asset_id)
    result=extract(asset,a.start,a.end,a.output,a.purpose,list(map(int,a.roi.split(','))),a.max_frames,a.job)
    print(json.dumps(dict(records=len(result['records']),stage=str(Path(a.job).resolve()/'.stage-cache'/result['stageId']),
                          bracketing=result['bracketing']),ensure_ascii=False))


if __name__=='__main__':main()
