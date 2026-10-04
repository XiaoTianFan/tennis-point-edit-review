"""Audit declared source coverage and point lineage; never infer unseen events."""
import argparse, json
from collections import defaultdict
from pathlib import Path

KINDS = {'rally','serve_fault','serve_let','aborted_toss','shadow_swing','retrieval','waiting','changeover','source_gap','unclassified'}
PLAY = {'rally','serve_fault','serve_let'}

def display_order(point_ids, revision):
    """Caller supplies the final counted points in source order, once per point.

    A clip/serve list is not a point list. Stable IDs and review IDs are untouched.
    """
    if not isinstance(revision,str) or not revision.strip(): raise ValueError('Ledger revision required')
    if not isinstance(point_ids,list) or any(not isinstance(p,str) or not p.strip() for p in point_ids):
        raise ValueError('Explicit ordered stable point IDs required')
    if len(set(point_ids))!=len(point_ids): raise ValueError('One entry per point, not per retained fragment')
    return {'ledgerRevision':revision,'count':len(point_ids),
            'points':[{'pointId':p,'displayNumber':i+1} for i,p in enumerate(point_ids)]}

def audit_coverage(data):
    scopes = {r['source']:r for r in data['scopes']}
    if len(scopes) != len(data['scopes']): raise ValueError('Duplicate source scope')
    findings=[]; groups=defaultdict(list)
    for r in data['intervals']:
        if r['source'] not in scopes: raise ValueError('Unknown source')
        if r['kind'] not in KINDS: raise ValueError('Unknown interval kind')
        if any(type(r[k]) is not int for k in ('startUs','endUs')) or r['endUs']<=r['startUs']: raise ValueError('Positive integer microsecond range required')
        if r['kind'] in PLAY and not r.get('pointId'): raise ValueError('Played event needs stable pointId')
        if r.get('retained') is False and not r.get('reason'): raise ValueError('Deleted interval needs reason')
        groups[r['source']].append(r)
    totals={'coveredUs':0,'declaredReviewedUs':0}
    for source,s in scopes.items():
        if any(type(s[k]) is not int for k in ('startUs','endUs')) or s['startUs']<0 or s['endUs']<=s['startUs']: raise ValueError('Invalid source scope')
        cursor=s['startUs']
        for r in sorted(groups[source],key=lambda x:(x['startUs'],x['endUs'])):
            a,b=r['startUs'],r['endUs']
            if a<s['startUs'] or b>s['endUs']: raise ValueError('Interval outside source scope')
            if a>cursor: findings.append({'source':source,'issue':'uncovered_gap','startUs':cursor,'endUs':a})
            if a<cursor: findings.append({'source':source,'issue':'overlapping_intervals','startUs':a,'endUs':min(cursor,b)})
            fresh=max(0,b-max(cursor,a));totals['coveredUs']+=fresh
            if r.get('reviewed') is True and r['kind'] not in ('source_gap','unclassified'): totals['declaredReviewedUs']+=fresh
            else: findings.append({'source':source,'issue':'unreviewed_or_missing_evidence','startUs':a,'endUs':b})
            cursor=max(cursor,b)
        if cursor<s['endUs']: findings.append({'source':source,'issue':'uncovered_gap','startUs':cursor,'endUs':s['endUs']})
    return {'complete':not findings,'findings':findings,**totals,'scope':'Declared source intervals only; reviewed flag is not proof of visual accuracy'}

def audit_lineage(points, lineage=()):
    by={p['pointId']:p for p in points}
    if len(by)!=len(points): raise ValueError('Duplicate stable pointId')
    active={k:v for k,v in by.items() if v.get('active',True)}
    for p in active.values():
        if type(p.get('sourceOrder')) is not int or type(p.get('sourceStartUs')) is not int: raise ValueError('Explicit source order and start timestamp required')
    for link in lineage:
        old,new=link['from'],link['to'];kind=link['kind']
        if not old or not new or len(old)!=len(set(old)) or len(new)!=len(set(new)): raise ValueError('Invalid lineage IDs')
        if kind not in ('merge','split'): raise ValueError('Unknown lineage kind')
        if kind=='merge' and (len(old)<2 or len(new)!=1): raise ValueError('Merge requires multiple old candidates, one surviving point')
        if kind=='split' and (len(old)!=1 or len(new)<2): raise ValueError('Split requires one old candidate, multiple resulting points')
        if not link.get('reason') or not link.get('revision'): raise ValueError('Lineage needs evidence reason and revision')
        if any(k not in by for k in old+new): raise ValueError('Unknown lineage ID; preserve retired candidates')
        if any(k not in active for k in new) or any(k in active for k in set(old)-set(new)): raise ValueError('Retired candidate still active or output inactive')
    ordered=sorted(active.values(),key=lambda p:(p['sourceOrder'],p['sourceStartUs']))
    keys=[(p['sourceOrder'],p['sourceStartUs']) for p in ordered]
    if len(keys)!=len(set(keys)): raise ValueError('Ambiguous source chronology')
    return {'activePointIdsInSourceOrder':[p['pointId'] for p in ordered], 'lineageCount':len(lineage),'reviewMigration':'Never automatically copy one winner to every split output; reconcile by source evidence internally'}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('input');args=a.parse_args()
    d=json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
    out={'coverage':audit_coverage(d)}
    if 'points' in d:out['lineage']=audit_lineage(d['points'],d.get('lineage',[]))
    if 'displayPointIds' in d:out['displayOrder']=display_order(d['displayPointIds'],d['ledgerRevision'])
    print(json.dumps(out,ensure_ascii=False,indent=2))


