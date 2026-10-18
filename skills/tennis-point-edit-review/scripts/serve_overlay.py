"""Pure timing plan for verified, retained serves; no media or editor writes."""
import argparse, json, math
from fractions import Fraction
from output_language import resolve_language, text
from pathlib import Path
from speed_evidence import unavailable_reason

def fraction(value):
    return Fraction(str(value))

def build_plan(records, fps, language="zh-CN", *, allow_imputed=False):
    """See helper-usage.md. All source timestamps are integer microseconds.

    confirmedPostContactUs is visually verified outgoing-ball evidence, NOT a
    fitted launch time. The caller supplies the current source-to-edit mapping.
    Nonlinear time remaps must be split into constant-rate spans beforehand.
    """
    language=resolve_language(language)
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
        method=r['method']
        missing=method=='unestimated'
        if missing:
            if r.get('launchSpeedKphEstimate') is not None or r.get('included') is not False:
                raise ValueError('N/A needs a null speed excluded from speed aggregates')
            reason=unavailable_reason(r.get('unavailableAudit',{}))
        else:
            speed=float(r['launchSpeedKphEstimate'])
            if not math.isfinite(speed) or speed<=0:raise ValueError('Invalid speed estimate')
            if method=='partial_trajectory_model' and r.get('qualityAccepted') is not True:
                raise ValueError('Unaccepted partial fit cannot receive a numeric label')
            if method=='model_imputed' and (not allow_imputed or not r.get('imputationBasis')):
                raise ValueError('Imputed labels require explicit opt-in and documented support')
        c=r['clip']
        for val in (c['startFrame'],c['durationFrames'],c['sourceInUs'],r['confirmedPostContactUs']):
            if not isinstance(val,int) or isinstance(val,bool):raise ValueError('Exact integer frames and source microseconds required')
        rate=fraction(c['playbackRate'])
        if rate<=0 or c['durationFrames']<=0:raise ValueError('Forward constant-rate clip required')
        local=Fraction(r['confirmedPostContactUs']-c['sourceInUs'],1000000)*fps/rate
        if 'confirmedPostContactSourceFrame' in r:
            f=r['confirmedPostContactSourceFrame'];base=c.get('sourceInFrame');source_fps=fraction(c.get('sourceFps',0))
            if type(f) is not int or type(base) is not int or f<base or source_fps<=0:
                raise ValueError('Native CFR guard needs sourceInFrame, sourceFps and outgoing source frame')
            local=max(local,Fraction(f-base)/source_fps*fps/rate)
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
        label=text('一发' if r['serveNumber']==1 else '二发',language)
        states=[dict(startFrame=c['startFrame'],endFrame=end,label=label)]
        fault_after_window=False
        if 'doubleFaultConfirmedUs' in r:
            fault=r['doubleFaultConfirmedUs']
            if r['eventType']!='serve' or r['serveNumber']!=2 or type(fault) is not int or fault<r['confirmedPostContactUs']:
                raise ValueError('Double fault needs a second serve and later verified fault evidence')
            fault_frame=c['startFrame']+math.floor(Fraction(fault-c['sourceInUs'],1000000)*fps/rate)+1
            if fault_frame<end:
                states[0]['endFrame']=fault_frame
                states.append(dict(startFrame=fault_frame,endFrame=end,label=text('二发 · 双误',language)))
            else:fault_after_window=True
        if 'letConfirmedUs' in r:
            confirmed=r['letConfirmedUs']
            if r['eventType']!='let' or type(confirmed) is not int or confirmed<r['confirmedPostContactUs'] or 'doubleFaultConfirmedUs' in r:
                raise ValueError('Let label requires independent later let evidence and cannot be a double fault')
            let_frame=c['startFrame']+math.floor(Fraction(confirmed-c['sourceInUs'],1000000)*fps/rate)+1
            if let_frame<end:
                states[0]['endFrame']=let_frame
                states.append(dict(startFrame=let_frame,endFrame=end,label=text('一发 · 擦网' if r['serveNumber']==1 else '二发 · 擦网',language)))
            else:fault_after_window=True
        entry=dict(setNumber=r['setNumber'],pointId=r['pointId'],serveId=r['serveId'],startFrame=start,endFrame=end,durationFrames=end-start,
                        labelStartFrame=c['startFrame'],labelEndFrame=end,labelStates=states,outcomeAfterOverlayWindow=fault_after_window,
                        qualifier='' if missing else text('补估' if method=='model_imputed' else '约',language),speed='N/A' if missing else str(math.floor(speed+.5)),unit='' if missing else 'km/h',statsIncluded=r['statsIncluded'])
        if missing:entry.update(speedAvailable=False,unavailableReason=reason)
        out.append(entry)
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('output');a=p.parse_args()
    d=json.loads(Path(a.input).read_text(encoding='utf-8-sig'))
    Path(a.output).write_text(json.dumps(build_plan(d['records'],d['fps'],d.get('outputLanguage','zh-CN'),allow_imputed=d.get('allowImputed') is True),ensure_ascii=False,indent=2),encoding='utf8')

