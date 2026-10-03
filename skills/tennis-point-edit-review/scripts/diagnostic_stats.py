"""Derive rally, third-ball and terminal-stroke metrics from reviewed events.

Point results remain independent of stroke labels. Unknown hands/directions are
retained explicitly; an onsite game award must never create a synthetic point.
"""
from collections import Counter,defaultdict

def rate(n,d):
    return dict(numerator=n,denominator=d,percent=round(100*n/d,1) if d else None)

def aggregate_diagnostics(points,shots):
    pp={p['pointId']:p for p in points if p.get('statsIncluded') is True}
    if len(pp)!=sum(p.get('statsIncluded') is True for p in points):raise ValueError('Duplicate point')
    events=defaultdict(list);keys=set()
    for s in shots:
        if s.get('countsAsShot') is not True:continue
        pid=s['pointId'];ix=s['shotIndex'];key=(pid,ix)
        if pid not in pp:raise ValueError('Shot without included point')
        if key in keys:raise ValueError('Duplicate shot')
        keys.add(key);events[pid].append(s)
    buckets={k:dict(count=0,wins=Counter()) for k in ('short','medium','long')}
    out={p:dict(thirdReached=0,thirdWon=0,thirdError=0,
         hands={k:Counter() for k in ('W','UE','FE')},directions=Counter(),errorMotion=Counter(),ueMotion=Counter(),unclassifiedErrors=0) for p in 'AB'}
    df=0
    for pid,p in pp.items():
        if p.get('errorAssessment'):
            from error_review import validate_error_assessment
            validate_error_assessment(p)
        is_error=p['ending'] in ('UE','FE') or (p['ending']=='OTHER' and p.get('terminalError') is True)
        rr=sorted(events[pid],key=lambda s:s['shotIndex'])
        if p['ending']=='DF':
            if rr or p['shots']!=0:raise ValueError('Double fault is outside rally distribution')
            df+=1;continue
        if [r['shotIndex'] for r in rr]!=list(range(1,p['shots']+1)):raise ValueError('Missing contact event: '+pid)
        for r in rr:
            expected=p['server'] if r['shotIndex']%2 else ('B' if p['server']=='A' else 'A')
            if r['hitter']!=expected:raise ValueError('Contact order conflicts: '+pid)
        b=buckets['short' if len(rr)<=4 else 'medium' if len(rr)<=8 else 'long']
        b['count']+=1;b['wins'][p['winner']]+=1
        third=next((r for r in rr if r['shotIndex']==3),None)
        if third:
            if not third.get('evidence'):raise ValueError('Third contact evidence required')
            t=out[p['server']];t['thirdReached']+=1;t['thirdWon']+=p['winner']==p['server']
            t['thirdError']+=len(rr)==3 and is_error and p['winner']!=p['server']
        if p['ending']=='W' or is_error:
            end=rr[-1];h=p['winner'] if p['ending']=='W' else ('B' if p['winner']=='A' else 'A')
            if end['hitter']!=h:raise ValueError('Terminal player conflicts: '+pid)
            hand=end.get('hand') or 'unknown'
            if hand not in ('FH','BH','other','unknown'):raise ValueError('Invalid hand')
            if is_error and p['ending']=='OTHER':out[h]['unclassifiedErrors']+=1
            else:out[h]['hands'][p['ending']][hand]+=1
            if p['ending']!='W':
                direction=end.get('errorDirection') or 'unknown'
                if direction not in ('net','out','unknown'):raise ValueError('Use net/out/unknown only')
                out[h]['directions'][direction]+=1
                motion=end.get('terminalErrorMotion') or 'unknown'
                if motion not in ('moving','stationary','unknown'):raise ValueError('Invalid terminal error motion')
                if motion!='unknown' and not end.get('motionEvidence'):raise ValueError('Motion requires before/contact/after evidence')
                out[h]['errorMotion'][motion]+=1
                if p['ending']=='UE':out[h]['ueMotion'][motion]+=1
    total=sum(b['count'] for b in buckets.values());metrics={}
    for player,x in out.items():
        metrics[player]={'servePlusOneWon':rate(x['thirdWon'],x['thirdReached']),'servePlusOneErrors':x['thirdError'],
            'terminalHands':{k:{h:c[h] for h in ('FH','BH','other','unknown')} for k,c in x['hands'].items()},
            'errorDirections':{k:x['directions'][k] for k in ('net','out','unknown')}}
        error_total=sum(x['directions'].values())
        metrics[player]['errorNet']=rate(x['directions']['net'],error_total)
        metrics[player]['errorOut']=rate(x['directions']['out'],error_total)
        metrics[player]['errorMotionCounts']={k:x['errorMotion'][k] for k in ('moving','stationary','unknown')}
        metrics[player]['errorMoving']=rate(x['errorMotion']['moving'],error_total)
        metrics[player]['errorStationary']=rate(x['errorMotion']['stationary'],error_total)
        metrics[player]['unclassifiedErrors']=x['unclassifiedErrors']
        metrics[player]['ueMotionCounts']={k:x['ueMotion'][k] for k in ('moving','stationary','unknown')}
        metrics[player]['ueMoving']=x['ueMotion']['moving']
        metrics[player]['ueStationary']=x['ueMotion']['stationary']
        assert sum(metrics[player]['ueMotionCounts'].values())==sum(x['hands']['UE'].values())
        assert sum(metrics[player]['errorMotionCounts'].values())==error_total
        for k,b in buckets.items():metrics[player][k+'WinRate']=rate(b['wins'][player],b['count'])
    return dict(metrics=metrics,rallyDistribution={k:rate(b['count'],total) for k,b in buckets.items()},
                includedPoints=len(pp),rallyPoints=total,zeroShotDoubleFaults=df,shotCount=len(keys))
