"""Bounded, opt-in vision pilot; does not adjudicate or update a match project."""
import argparse
from collections import deque
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import platform
import time

import av
import cv2
import numpy as np

from cv_observations import (COURT, LocalTrackNet, camera_change, classical, fit_court,
                             ground_hypothesis, select_track)
from job_workspace import safe_path
from local_model import read, write
from media_probe import identity, metadata
from seam_cv import local_score
from source_binding import mapping, unchanged
from working_media import working_size

SCHEMA = 'tennis-vision-observations/v1'
DEFAULTS = dict(backend='classical', windows=[[0,5]], maxFrames=1200,
                hsvLow=[18,42,80],hsvHigh=[62,255,255],motionThreshold=12,
                maxArea=190,maxSpan=35,courtEvery=60,threads=8,device='cpu')


def settings(value):
    c={**DEFAULTS,**value}
    if c['backend'] not in ('classical','local-tracknet'):
        raise ValueError('Unsupported vision backend')
    if not isinstance(c['windows'],list) or not c['windows'] or len(c['windows'])>20:
        raise ValueError('Supply 1..20 bounded windows')
    end=None
    for a,b in c['windows']:
        a,b=Fraction(str(a)),Fraction(str(b))
        if a<0 or b<=a or b-a>30 or end is not None and a<end:
            raise ValueError('Sorted nonoverlapping windows of at most 30 seconds required')
        end=b
    for key in ('maxFrames','courtEvery','threads'):
        if type(c[key]) is not int or c[key]<1:
            raise ValueError(key+' must be a positive integer')
    if c['maxFrames']>10000 or c['threads']>32:
        raise ValueError('Pilot resource bound exceeded')
    if len(c['hsvLow'])!=3 or len(c['hsvHigh'])!=3 or any(not 0<=a<=b<=m for a,b,m in zip(c['hsvLow'],c['hsvHigh'],[179,255,255])):
        raise ValueError('Invalid HSV bounds')
    for k in ('motionThreshold','maxArea','maxSpan'):
        if not isinstance(c[k],(int,float)) or not math.isfinite(c[k]) or c[k]<=0:
            raise ValueError('Invalid '+k)
    return c


class SeamSignals:
    """Same local/flow signals as seam_cv; hypotheses remain distinct from events."""
    def __init__(self):
        self.previous=self.older=None
        self.history=deque(maxlen=30)
        self.flow=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST)

    def step(self, image):
        row=dict(candidate=False,localDifference=0.,motionResidual=0.,innovation=0.)
        if self.previous is not None:
            previous=self.previous
            score=local_score(cv2.absdiff(image,previous),np)
            baseline=float(np.median(self.history)) if self.history else 0.
            mad=float(np.median(np.abs(np.array(self.history)-baseline))) if self.history else 0.
            threshold=max(1.5,baseline*2.2,baseline+7*mad)
            innovation=0.
            if self.older is not None:
                predicted=np.clip(previous.astype(np.int16)*2-self.older,0,255).astype('uint8')
                innovation=local_score(cv2.absdiff(image,predicted),np)
            if score>=threshold:
                yy,xx=np.mgrid[:image.shape[0],:image.shape[1]].astype('float32')
                back=self.flow.calc(image,previous,None);forward=self.flow.calc(previous,image,None)
                a=cv2.remap(previous,xx+back[:,:,0],yy+back[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
                b=cv2.remap(image,xx+forward[:,:,0],yy+forward[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
                residual=min(local_score(cv2.absdiff(image,a),np),local_score(cv2.absdiff(previous,b),np))
                row.update(motionResidual=residual,candidate=residual>=1.2 and (self.older is None or innovation>=max(1.5,baseline*2)))
            row.update(localDifference=score,innovation=innovation,threshold=threshold)
            self.history.append(score)
            self.older=previous.astype(np.int16)
        self.previous=image
        return row


def frames(source, start, end):
    """Yield every decoded original frame in the absolute PTS half-open interval."""
    start,end=Fraction(str(start)),Fraction(str(end))
    with av.open(str(source)) as container:
        stream=container.streams.video[0]
        container.seek(int(start/stream.time_base),stream=stream,backward=True,any_frame=False)
        last=None
        for frame in container.decode(stream):
            if frame.pts is None:
                raise ValueError('Missing original PTS')
            seconds=frame.pts*frame.time_base
            if last is not None and seconds<=last:
                raise ValueError('Nonmonotone original PTS')
            last=seconds
            if seconds<start:continue
            if seconds>=end:break
            yield frame,seconds


def infer_events(rows):
    """Image-space trajectory turn proposals; no gap filling and no tennis verdict."""
    events=[]
    for i in range(3,len(rows)-3):
        window=rows[i-3:i+4];r=rows[i]
        if any(x['windowId']!=r['windowId'] or x['segmentId']!=r['segmentId'] or x['track'] is None for x in window):continue
        ts=np.array([float(Fraction(x['seconds'])) for x in window])
        if np.max(np.diff(ts))>.06:continue
        ys=np.array([x['track']['y'] for x in window]);xs=np.array([x['track']['x'] for x in window])
        before=ys[3]-ys[0];after=ys[6]-ys[3]
        if before<=3 or after>=-3 or ys[3]<max(ys[2],ys[4]):continue
        if max(np.abs(np.diff(xs)))>r['nativeSize'][0]*.08:continue
        if events and r['windowId']==events[-1]['windowId'] and float(Fraction(r['seconds']))-float(Fraction(events[-1]['seconds']))<.15:continue
        xy=[r['track']['x'],r['track']['y']]
        geometry=r['court'] if r['camera']['status']=='stable_candidate' else {}
        events.append(dict(id=f'E{len(events)+1:04}',kind='bounce_candidate',status='proposed',
                           alternatives=['racket_contact','mistrack','projection_turn'],windowId=r['windowId'],
                           pts=r['pts'],seconds=r['seconds'],timeBase=r['timeBase'],xy=xy,
                           bracketSeconds=[window[0]['seconds'],window[-1]['seconds']],
                           supportRecordIds=[x['id'] for x in window],
                           conditionalGround=ground_hypothesis(geometry,xy,max(3,r['nativeSize'][0]/640*2)),
                           confidence=None,confidenceMeaning='uncalibrated heuristic; inspection required',
                           adjudication=None))
    return events


def scan(source, directory, config):
    started=time.perf_counter();cpu_start=time.process_time()
    config=settings(config)
    directory=safe_path(directory)
    if directory.exists():raise ValueError('Use a new run directory; existing results are immutable')
    fingerprint=identity(source);info=metadata(source)
    video=next(s for s in info['streams'] if s['codec_type']=='video')
    if video.get('color_transfer') in ('smpte2084','arib-std-b67'):
        raise ValueError('HDR transform not qualified for this backend')
    if video.get('sample_aspect_ratio','1:1') not in ('1:1','0:1','N/A') or any(float(s.get('rotation',0))%360 for s in video.get('side_data_list',[])):
        raise ValueError('Pilot requires unrotated square-pixel input; do not silently remap evidence')
    width,height=video['width'],video['height']
    if video.get('duration'):
        available_end=Fraction(video.get('start_time','0'))+Fraction(video['duration'])
        if any(Fraction(str(b))>available_end for _,b in config['windows']):
            raise ValueError('Requested window exceeds available source duration')
    ww,wh=working_size(width,height)
    sx,sy=width/ww,height/wh
    calibration=config.get('calibration')
    if calibration and (calibration.get('sourceSha256')!=fingerprint['sha256'] or calibration.get('nativeSize')!=[width,height]):
        raise ValueError('Calibration source/size mismatch')
    if calibration and (len(config['windows'])!=1 or calibration.get('validWindows')!=config['windows']):
        raise ValueError('Explicit calibration must match a single inspected camera window')
    code={n:identity(Path(__file__).with_name(n))['sha256'] for n in ('cv_pipeline.py','cv_observations.py','seam_cv.py')}
    directory.mkdir(parents=True)
    write(directory/'run-start.json',dict(sourceIdentity=fingerprint,config=config,code=code,status='running'))
    cv2.setNumThreads(1);cv2.setRNGSeed(0)
    model=LocalTrackNet(config) if config['backend']=='local-tracknet' else None
    provenance=model.provenance if model else dict(backend='classical',scoreKind='pixel_intensity_not_probability')
    load_end=time.perf_counter()
    rows=[];courts=[];coverage=[]
    try:
        with (directory/'observations.jsonl').open('x',encoding='utf-8') as stream:
            for wi,(start,end) in enumerate(config['windows']):
                recent=deque(maxlen=3);previous=track=None;last_time=None;reference=None;segment=0
                seam=SeamSignals();court=dict(status='abstained',reason='not_calibrated');camera=dict(status='unknown')
                count=0
                for frame,seconds in frames(source,start,end):
                    if len(rows)>=config['maxFrames']:raise ValueError('Frame budget exhausted; use shorter windows')
                    native=frame.to_ndarray(format='bgr24')
                    work=cv2.resize(native,(ww,wh),interpolation=cv2.INTER_AREA) if (ww,wh)!=(width,height) else native
                    gray=cv2.cvtColor(work,cv2.COLOR_BGR2GRAY)
                    small=cv2.resize(gray,(640,round(640*wh/ww)))
                    signals=seam.step(small)
                    if signals['candidate']:
                        segment+=1;recent.clear();track=None;reference=None
                        court=dict(status='abstained',reason='visual_discontinuity')
                    if reference is None:
                        reference=small.copy()
                    # Check against anchor every frame, not only successive shifts.
                    camera=camera_change(reference,small)
                    colour=classical(work,previous,config)
                    recent.append(work)
                    learned=model.detect(list(recent)) if model else None
                    for group in (colour,learned):
                        for c in group or []:
                            c['x']*=sx;c['y']*=sy
                            c['box']=[c['box'][0]*sx,c['box'][1]*sy,c['box'][2]*sx,c['box'][3]*sy]
                    if count%config['courtEvery']==0 or signals['candidate']:
                        points=model.court_points(work) if model else []
                        for p in points:
                            for c in p['candidates']:
                                c['x']*=sx;c['y']*=sy
                        chosen=[p for p in points if p['selected'] is not None]
                        court=fit_court([[p['selected']['x'],p['selected']['y']] for p in chosen],
                                        [COURT[p['keypoint']] for p in chosen]) if points else dict(status='abstained',reason='no_court_model')
                        court['provenance']='learned_keypoints'
                        courts.append(dict(windowId=wi,pts=frame.pts,seconds=str(seconds),rawKeypoints=points,fit=court))
                    if calibration and segment==0 and camera['status']=='stable_candidate':
                        court={**fit_court(calibration['imagePoints'],calibration['courtPoints']),
                               'provenance':'explicit_external_calibration','referenceKind':calibration['referenceKind']}
                    dt=float(seconds-last_time) if last_time is not None else 0.
                    selected,reason=select_track(learned if model else colour,track,dt,math.hypot(width,height))
                    if camera['status']!='stable_candidate':
                        selected=None;reason='camera_not_qualified'
                    row=dict(id=f'F{len(rows):06}',windowId=wi,windowFrame=count,segmentId=segment,
                             pts=frame.pts,timeBase=str(frame.time_base),seconds=str(seconds),
                             nativeSize=[width,height],analysisSize=[ww,wh],modelSize=[640,360] if model else None,
                             colourCandidates=colour,modelCandidates=learned,
                             track=selected,trackStatus=reason,interpolated=False,camera=camera,
                             court=court,seam=signals)
                    rows.append(row);stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
                    track=selected;previous=gray;last_time=seconds;count+=1
                    if count%60==0:print(json.dumps(dict(window=wi,frames=count,elapsedSeconds=round(time.perf_counter()-started,2))),flush=True)
                if not count:raise ValueError('Requested window has no decoded frames')
                coverage.append(dict(windowId=wi,requested=[str(start),str(end)],decodedFrames=count,
                                     firstSeconds=rows[-count]['seconds'],lastSeconds=rows[-1]['seconds'],
                                     visualReview='not_performed'))
        unchanged(fingerprint)
        events=infer_events(rows)
        digest=hashlib.sha256(json.dumps(dict(source=fingerprint,config=config,backend=provenance,code=code),sort_keys=True).encode()).hexdigest()
        result=dict(schema=SCHEMA,runId=digest,sourceIdentity=fingerprint,sourceProbe=info,
                    config=config,backend=provenance,code=code,coordinateSpace='original encoded pixels',
                    coverage=coverage,courts=courts,events=events,
                    boundaryEvidence=[dict(recordId=r['id'],pts=r['pts'],seconds=r['seconds'],kind='visual_discontinuity',
                                           status='proposed_edit_seam',tennisEvent=None) for r in rows if r['seam']['candidate']],
                    pointProposals=[dict(windowId=c['windowId'],serveOnset=None,deadBallEnd=None,status='abstained',
                                         reason='ball visibility/trajectory turns do not establish serve or first dead ball') for c in coverage],
                    adjudications=[],statistics=dict(status='not_qualified',values=None),
                    metrics=dict(decodedFrames=len(rows),detectedFrames=sum(bool(r['modelCandidates'] if model else r['colourCandidates']) for r in rows),
                                 trackedFrames=sum(r['track'] is not None for r in rows),eventProposals=len(events),
                                 wallSeconds=time.perf_counter()-started,cpuSeconds=time.process_time()-cpu_start,
                                 setupSeconds=load_end-started,peakMemoryBytes=None,modelApiCalls=0,
                                 agentTokens=None,reviewSeconds=None),
                    runtime=dict(python=platform.python_version(),opencv=cv2.__version__,numpy=np.__version__,pyav=av.__version__),
                    observationsSha256=identity(directory/'observations.jsonl')['sha256'],
                    status='complete',limitations=['bounded windows only','no winner/line/speed adjudication',
                    'detector responses are not calibrated probabilities','no independently certified truth'])
        write(directory/'result.json',result)
        return result
    except Exception as exc:
        write(directory/'failure.json',dict(status='failed',error=str(exc),decodedFrames=len(rows)))
        raise


def make_plan(result_path, media_path, players_path, output):
    """Review the whole scanned windows; proposed events never trim the source."""
    result=read(result_path);media=read(media_path)
    if result.get('schema')!=SCHEMA or result.get('status')!='complete':raise ValueError('Completed vision run required')
    if media.get('sourceIdentity',{}).get('sha256')!=result['sourceIdentity']['sha256']:
        raise ValueError('Review media and vision source identities differ')
    if media.get('sourceMapping',{}).get('schema')!='original-pts-grid/v1':raise ValueError('Bound media clock required')
    if Path(output).exists():raise ValueError('Plan already exists')
    fps=Fraction(media['fps']);origin=Fraction(media['sourceMapping']['originSeconds'])
    clips=[];review=[]
    for item in result['coverage']:
        a,b=map(Fraction,item['requested'])
        first=math.floor((a-origin)*fps);last=math.ceil((b-origin)*fps)
        if first<0 or last>media['frames']:raise ValueError('Working media does not cover the full evidence window')
        pid=f'CV{item["windowId"]+1:04}';rid=f'R{item["windowId"]+1:03}'
        candidates=[e for e in result['events'] if e['windowId']==item['windowId']]
        detail='；'.join(f'{float(Fraction(e["seconds"])):.3f}s 落点/触拍待核' for e in candidates) or '未形成可靠落点候选'
        clips.append(dict(id=pid,pointId=pid,assetId='vision-source',inFrame=first,outFrame=last,candidatePoint=True,
                          setNumber=None,gameNumber=None,serverId=None,serveNumber=None))
        review.append(dict(reviewId=rid,pointId=pid,setNumber=None,gameNumber=None,serverId=None,serveNumber=None,candidatePoint=True,
                           sourceRangesSeconds=[[float(a),float(b)]],initial={},
                           evidenceRanges=[dict(assetId='vision-source',inFrame=first,outFrame=last)],
                           reason='视觉实验窗口，不代表一分；'+detail+'。发球起始、首次死球及计分资格待agent核实。'))
    plan=dict(title='视觉实验：候选证据（未判分）',outputLanguage='zh-CN',workingMode='agent-dominant',
              players=read(players_path),assets=[dict(id='vision-source',metadata=str(Path(media_path).resolve()))],clips=clips,
              review=dict(source='cv:'+result['runId'],ledgerRevision='cv:'+result['runId'][:16],
                          purpose='initial-labeling',provisionalPoints=True,rows=review),overlays=[],
              visionEvidence=dict(result=str(Path(result_path).resolve()),runId=result['runId'],status='proposed'),
              statistics=dict(status='pending'),approval={})
    write(output,plan)
    return plan


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('scan');p.add_argument('source');p.add_argument('output');p.add_argument('--config',required=True)
    p=sub.add_parser('plan');p.add_argument('result');p.add_argument('media');p.add_argument('players');p.add_argument('output')
    a=parser.parse_args()
    if a.command=='scan':
        result=scan(a.source,a.output,read(a.config));print(json.dumps(result['metrics'],ensure_ascii=False))
    else:
        plan=make_plan(a.result,a.media,a.players,a.output);print(json.dumps(dict(clips=len(plan['clips']),output=a.output)))


if __name__=='__main__':main()
