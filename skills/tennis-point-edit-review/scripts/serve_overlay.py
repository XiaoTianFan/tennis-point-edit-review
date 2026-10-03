"""Pure timing plan for verified, retained serves; no media or editor writes."""
import argparse, json, math
from fractions import Fraction
from pathlib import Path

def fraction(value):
    return Fraction(str(value))

def build_plan(records, fps):
    """See helper-usage.md. All source timestamps are integer microseconds.

    confirmedPostContactUs is visually verified outgoing-ball evidence, NOT a
    fitted launch time. The caller supplies the current source-to-edit mapping.
    Nonlinear time remaps must be split into constant-rate spans beforehand.
    """
    fps=fraction(fps)
    if fps<=0:raise ValueError('fps must be positive')
    limit=math.floor(3*fps)
    if limit<1:raise ValueError('fps too low for a three-second interval')
    seen=set();out=[]
    for r in records:
        key=(r['setNumber'],r['serveId'])
        if key in seen:raise ValueError('Duplicate actual serve ID')
        seen.add(key)
        if r.get('eventType') not in ('serve','let'):
            raise ValueError('Only actual serve contacts can receive speed overlays')
        if r.get('contactVerified') is not True:
            raise ValueError('Agent must verify outgoing contact evidence before placement')
        if r.get('serveNumber') not in (1,2):raise ValueError('Actual serve opportunity number required')
        speed=float(r['launchSpeedKphEstimate'])
        if not math.isfinite(speed) or speed<=0:raise ValueError('Invalid speed estimate')
        method=r['method']
        if method=='model_imputed' and not r.get('imputationBasis'):
            raise ValueError('Model imputation needs its own documented basis')
        c=r['clip']
        for val in (c['startFrame'],c['durationFrames'],c['sourceInUs'],r['confirmedPostContactUs']):
            if not isinstance(val,int) or isinstance(val,bool):raise ValueError('Exact integer frames and source microseconds required')
        rate=fraction(c['playbackRate'])
        if rate<=0 or c['durationFrames']<=0:raise ValueError('Forward constant-rate clip required')
        local=Fraction(r['confirmedPostContactUs']-c['sourceInUs'],1000000)*fps/rate
        if local<0 or local>=c['durationFrames']:
            raise ValueError('Verified outgoing event is not inside this retained clip')
        start=c['startFrame']+math.floor(local)+1
        caps=[start+limit,c['startFrame']+c['durationFrames']]
        for field in ('pointEndFrame','nextServeStartFrame'):
            if field in r:
                if not isinstance(r[field],int):raise ValueError('Frame cap must be integer')
                caps.append(r[field])
        end=min(caps)
        if end<=start:raise ValueError('No visible frame remains after outgoing evidence')
        label='一发' if r['serveNumber']==1 else '二发'
        states=[dict(startFrame=c['startFrame'],endFrame=end,label=label)]
        fault_after_window=False
        if 'doubleFaultConfirmedUs' in r:
            fault=r['doubleFaultConfirmedUs']
            if r['eventType']!='serve' or r['serveNumber']!=2 or type(fault) is not int or fault<r['confirmedPostContactUs']:
                raise ValueError('Double fault needs a second serve and later verified fault evidence')
            fault_frame=c['startFrame']+math.floor(Fraction(fault-c['sourceInUs'],1000000)*fps/rate)+1
            if fault_frame<end:
                states[0]['endFrame']=fault_frame
                states.append(dict(startFrame=fault_frame,endFrame=end,label='二发 · 双误'))
            else:fault_after_window=True
        out.append(dict(setNumber=r['setNumber'],pointId=r['pointId'],serveId=r['serveId'],startFrame=start,endFrame=end,durationFrames=end-start,
                        labelStartFrame=c['startFrame'],labelEndFrame=end,labelStates=states,outcomeAfterOverlayWindow=fault_after_window,
                        qualifier='补估' if method=='model_imputed' else '约',speed=str(math.floor(speed+.5)),unit='km/h',statsIncluded=r['statsIncluded']))
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('output');a=p.parse_args()
    d=json.loads(Path(a.input).read_text(encoding='utf-8-sig'))
    Path(a.output).write_text(json.dumps(build_plan(d['records'],d['fps']),ensure_ascii=False,indent=2),encoding='utf8')


