"""Five serve/return metrics from explicit point-level visual annotations.

No inference from final winner, rally count, or third-shot error alone.
Caller selects the same set/match scope as the audited effective-point ledger.
"""
from collections import Counter

KEYS = ('serveDirectRate', 'returnIn', 'returnFirstIn', 'returnSecondIn', 'returnWinners')

def rate(n, d):
    return dict(numerator=n, denominator=d, percent=round(100*n/d, 1) if d else None)

def aggregate_returns(points, require_complete=True):
    counts={p:Counter() for p in ('A','B')};seen=set();missing=[]
    for r in points:
        if r.get('statsIncluded') is not True:continue
        key=(r.get('setNumber',1),r['pointId'])
        if key in seen:raise ValueError('Duplicate effective point')
        seen.add(key)
        s,w,n=r['server'],r['winner'],r['serveNumber'];receiver='B' if s=='A' else 'A'
        if s not in counts or w not in counts or n not in (1,2):raise ValueError('Invalid point identity')
        a=r.get('serveReturn',{})
        if a.get('reviewed') is not True or a.get('returnOutcome') not in ('in','error','ace','not_applicable'):
            missing.append(r['pointId']);continue
        if type(a.get('returnWinner')) is not bool:raise ValueError('Explicit return-winner boolean required')
        outcome=a['returnOutcome'];end=r['ending']
        if not a.get('evidence'):raise ValueError('Return annotation needs source evidence')
        if end=='DF':
            if outcome!='not_applicable' or a.get('serveIn') is not False or n!=2 or w==s or a['returnWinner']:
                raise ValueError('Double fault is not a legal serve or return winner')
        elif a.get('serveIn') is not True or outcome=='not_applicable':
            raise ValueError('Non-DF effective point needs a legal serve or separate exceptional scope')
        if (outcome=='ace') != (end=='ACE'):raise ValueError('ACE annotation mismatch')
        if outcome in ('ace','error') and (w!=s or a['returnWinner']):raise ValueError('Unreturned legal serve must award server')
        if a['returnWinner'] and (outcome!='in' or w!=receiver or end!='W'):
            raise ValueError('Return winner must be an in-court receiving winner')
        counts[s]['servicePoints']+=1
        if outcome=='not_applicable':continue
        counts[receiver]['legalServesFaced']+=1;counts[receiver][f'legalServe{n}Faced']+=1
        if outcome in ('ace','error'):counts[s]['serveDirect']+=1
        if outcome=='in':
            counts[receiver]['returnsIn']+=1;counts[receiver][f'return{n}In']+=1
        counts[receiver]['returnWinners']+=int(a['returnWinner'])
    if missing and require_complete:raise ValueError('Review missing serve/return evidence: '+','.join(missing))
    metrics={}
    for p,c in counts.items():
        metrics[p]={k:None for k in KEYS} if missing else dict(
            serveDirectRate=rate(c['serveDirect'],c['servicePoints']),
            returnIn=rate(c['returnsIn'],c['legalServesFaced']),
            returnFirstIn=rate(c['return1In'],c['legalServe1Faced']),
            returnSecondIn=rate(c['return2In'],c['legalServe2Faced']),returnWinners=c['returnWinners'])
    return dict(metrics=metrics,rawCounts=counts,coverage=dict(effectivePoints=len(seen),reviewedPoints=len(seen)-len(missing),missingPointIds=missing,complete=not missing))


