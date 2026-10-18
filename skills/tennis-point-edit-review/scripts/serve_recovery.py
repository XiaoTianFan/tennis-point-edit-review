"""Execute reviewed partial-flight screening; no automatic vision or editor writes."""
import copy,json,sys
from pathlib import Path

def screen(case):
    import numpy as np
    from partial_trajectory import fit_partial,alternating_holdouts
    from speed_evidence import assess_partial_quality
    obs=np.asarray(case['observations'],float);camera=case['camera'];options=copy.deepcopy(case['options'])
    if options.get('collision_lower_seconds') is None or not case.get('cutoffBasis'):
        raise ValueError('Reviewed pre-impact cutoff and basis required')
    bracket=case['contactBracketSeconds'];ct=options['contact_seconds']
    if len(bracket)!=2 or not bracket[0]<=ct<=bracket[1] or bracket[1]>=obs[0,0]:
        raise ValueError('Reviewed contact bracket must precede all observations')
    error=case['centroidError'];pixels=float(error['pixels'])
    if not np.isfinite(pixels) or pixels<=0 or not error.get('basis'):
        raise ValueError('Positive native-pixel localisation error and basis required')
    variants=case['variants']
    required={(f,s) for f in ('geometry','drag','lift') for s in ('low','high')}
    if not required<={(v.get('family'),v.get('side')) for v in variants} or any(not v.get('basis') for v in variants):
        raise ValueError('Supply justified low/high geometry, drag and lift inputs')
    for v in variants:
        keys={'geometry':('priors','bounds'),'drag':('drag',),'lift':('lift_vector',)}.get(v['family'],())
        defaults={'drag':.020,'lift_vector':[0.,0.,0.]}
        changed=any(k in v.get('options',{}) and v['options'][k]!=options.get(k,defaults.get(k)) for k in keys)
        if v['family']=='geometry':changed=changed or not np.array_equal(v.get('camera',camera),camera)
        if keys and not changed:raise ValueError('Sensitivity variant does not change '+v['family'])
    base=fit_partial(obs,camera,**options);initial=base['state'];lo,hi=np.array(options['bounds'])
    def run(observations=obs,cam=camera,overrides=None):
        opt={**options,'initial_state':initial,**(overrides or {})}
        lower,upper=np.array(opt['bounds']);opt['initial_state']=np.clip(opt['initial_state'],lower+1e-6,upper-1e-6).tolist()
        return fit_partial(observations,cam,**opt)
    starts=[]
    for factor in (.7,1.35):
        q=np.array(initial);q[3:]*=factor
        starts.append(run(overrides={'initial_state':np.clip(q,lo+1e-6,hi-1e-6).tolist()}))
    holdouts=alternating_holdouts(obs,camera,**{**options,'initial_state':initial}) if len(obs)>=12 else []
    perturbations=[];failures=[]
    def perturb(family,side,basis,observations=obs,cam=camera,overrides=None):
        try:
            result=run(observations,cam,overrides);result.update(family=family,side=side,basis=basis);perturbations.append(result)
        except (ValueError,RuntimeError) as error:failures.append({'family':family,'side':side,'error':str(error)})
    for side,time in zip(('low','high'),bracket):
        perturb('timing',side,'Source contact bracket',overrides={'contact_seconds':time})
    for v in variants:perturb(v['family'],v['side'],v['basis'],cam=v.get('camera',camera),overrides=v.get('options'))
    tau=(obs[:,0]-obs[0,0])/np.ptp(obs[:,0]);curve=8*(tau-.5)**2-1
    for side,sign in (('low',-1),('high',1)):
        altered=obs.copy();altered[:,2]+=sign*pixels*curve
        perturb('centroid',side,error['basis']+'; correlated vertical curvature',observations=altered)
    rng=np.random.default_rng(0)
    for n in range(2):
        altered=obs.copy();altered[:,1:]+=rng.normal(0,.75*pixels,(len(obs),2))
        perturb('centroid','noise'+str(n),error['basis']+'; deterministic Gaussian stress',observations=altered)
    checks=copy.deepcopy(case['visualChecks'])
    stable=all(r['converged'] and not r['fitAtParameterBoundary'] and abs(r['launchSpeedKphEstimate']/base['launchSpeedKphEstimate']-1)<=.02 for r in starts)
    checks['initialStateStabilityReviewed']=checks.get('initialStateStabilityReviewed') is True and stable
    quality=assess_partial_quality(base,holdouts,perturbations,checks,case.get('policy'))
    if failures:quality.update(accepted=False,reasons=quality['reasons']+['sensitivity fits failed'])
    base['qualityAccepted']=quality['accepted']
    return {'candidate':base,'multistarts':starts,'holdouts':holdouts,'variants':perturbations,
            'variantFailures':failures,'visualChecks':checks,'quality':quality}

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('Usage: serve_recovery.py INPUT.json NEW_OUTPUT.json')
    case=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'));result=screen(case)
    with Path(sys.argv[2]).open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
