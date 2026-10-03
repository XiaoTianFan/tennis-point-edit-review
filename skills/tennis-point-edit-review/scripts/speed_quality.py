"""Agent-side model diagnostics. No new human review form or automatic exclusions."""
from collections import defaultdict
import math

def audit_speed_quality(records):
    groups=defaultdict(list); seen=set(); flags=[]
    for r in records:
        if not r.get('included',True):continue
        key=(r['setNumber'],r['serveId'])
        if key in seen:raise ValueError('Duplicate serve')
        seen.add(key)
        v=r.get('launchSpeedKphEstimate')
        if not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0:raise ValueError('Positive finite estimate required')
        if r['serveNumber'] not in (1,2):raise ValueError('Resolve serve number before aggregation')
        groups[(r['setNumber'],r['serverId'],r['serveNumber'])].append(r)
        if r.get('method')=='model_imputed' and not r.get('imputationBasis'):raise ValueError('Disclose model support')
        if r.get('fitAtParameterBoundary') or r.get('ballIdentityVerified') is False or r.get('flightSegmentVerified') is False:
            flags.append({'serveId':r['serveId'],'issue':'recheck_model_before_publication'})
    results=[]
    for (sn,player,n),rr in sorted(groups.items()):
        observed=[r for r in rr if r.get('method')!='model_imputed']
        full=sum(r['launchSpeedKphEstimate'] for r in rr)/len(rr)
        om=sum(r['launchSpeedKphEstimate'] for r in observed)/len(observed) if observed else None
        results.append({'setNumber':sn,'serverId':player,'serveNumber':n,'count':len(rr),'evidenceCount':len(observed),'imputedCount':len(rr)-len(observed),'evidenceSupportedMeanKph':om,'fullPopulationMeanKph':full,'imputationMeanShiftKph':full-om if om is not None else None,'interpretation':'Descriptive sensitivity to inclusion; neither proves population accuracy'})
    people=defaultdict(list)
    for rr in groups.values():
        for r in rr:people[(r['setNumber'],r['serverId'])].append(r)
    for (sn,player),rr in people.items():
        best=max(rr,key=lambda r:r['launchSpeedKphEstimate'])
        if best.get('method')=='model_imputed':flags.append({'serveId':best['serveId'],'issue':'highest_central_estimate_is_imputed_not_visually_ranked'})
        elif best.get('fastestCandidateReviewed') is not True:flags.append({'serveId':best['serveId'],'issue':'agent_must_reinspect_fastest_candidate'})
    return {'groups':results,'agentChecks':flags,'requiresUserForm':False}


