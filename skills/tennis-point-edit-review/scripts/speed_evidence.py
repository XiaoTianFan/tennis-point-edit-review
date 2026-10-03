"""Evidence-gated endpoint inversion, conservative fallback, and partial-fit acceptance.

Verified flags represent an agent's recorded source inspection, never a claim
that this module can recognize contact, let, bounce, or ball identity from pixels.
"""
import copy,itertools,math
from launch_speed import reconstruct
from serve_event_audit import NON_CONTACT

def finite(value):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):
        raise ValueError('Finite numeric input required')
    return float(value)

def bracket(event,allowed):
    if event.get('verified') is not True or event.get('kind') not in allowed or not event.get('note'):
        raise ValueError('Independently reviewed event kind, bracket and note required')
    lo,hi=map(finite,event['bracketSeconds']);centre=finite(event['estimateSeconds'])
    if lo>hi or not lo<=centre<=hi:raise ValueError('Event estimate outside its original-frame bracket')
    return lo,centre,hi

def parameter(p,nonnegative=False):
    centre=finite(p['value']);lo,hi=map(finite,p['range'])
    if not p.get('basis') or lo>centre or centre>hi or (nonnegative and lo<0):
        raise ValueError('Parameter needs centre, enclosing sensitivity range, and evidence/prior basis')
    return lo,centre,hi

def estimate_endpoint(evidence):
    """Input contract and generated synthetic example: references/serve-speed-audit.md.

    Sensitivity is a corner envelope of declared intervals, not a confidence
    interval. Correlated/model errors remain; no arbitrary speed cap is applied.
    """
    e=evidence
    if e.get('eventType') not in ('serve','let') or e.get('ballIdentityVerified') is not True:
        raise ValueError('Actual struck-ball serve/let and ball identity required')
    c=bracket(e['contact'],{'racket_contact'})
    b=bracket(e['endpoint'],{'first_bounce','first_net_impact'})
    if e['eventType']=='let' and e['endpoint']['kind']!='first_net_impact':
        raise ValueError('A let must use pre-net flight, never a post-net bounce')
    if e.get('crossesEarlierCollision') is not False:
        raise ValueError('Verify the chosen segment contains no earlier impact')
    if b[0]<=c[2]:raise ValueError('Contact and endpoint brackets overlap or reverse')
    d=parameter(e['horizontalDistanceMetres'],True)
    h=parameter(e['contactHeightMetres'],True);z=parameter(e['endpointHeightMetres'],True)
    k=parameter(e['dragPerM'],True);lift=parameter(e['liftPerM'])
    gravity=finite(e.get('gravityMS2',9.81))
    if d[0]<=0 or gravity<=0:raise ValueError('Positive distance and gravity required')
    dt=b[1]-c[1];tr=(b[0]-c[2],b[2]-c[0])
    r=reconstruct(d[1],dt,h[1],z[1],drag=k[1],lift=lift[1],gravity=gravity)
    values=[r['launchSpeedKphEstimate']]
    for distance,t,height,end_height,drag,signed_lift in itertools.product(
            (d[0],d[2]),tr,(h[0],h[2]),(z[0],z[2]),(k[0],k[2]),(lift[0],lift[2])):
        values.append(reconstruct(distance,t,height,end_height,drag=drag,lift=signed_lift,gravity=gravity)['launchSpeedKphEstimate'])
    r.update(method='endpoint_physics',flightSeconds=dt,flightSecondsRange=list(tr),
             horizontalMeanFlightKph=3.6*d[1]/dt,
             sensitivityRangeKph=[min(values),max(values)],
             sensitivityType='Declared parameter-corner envelope; not calibrated probability or absolute accuracy',
             ballIdentityVerified=True,flightSegmentVerified=True,evidence=copy.deepcopy(e))
    return r

def impute_same_group(target,records):
    """Non-recursive mean for an observed contact only; fail if support is absent."""
    if target.get('eventType') not in ('serve','let') or target.get('contactVerified') is not True or target.get('speedApplicable') is False:
        raise ValueError('Imputation cannot invent a racket contact')
    group=(target['setNumber'],target['serverId'],target['serveNumber'],target.get('conditionGroup'))
    support=[];seen=set()
    for r in records:
        if (r['setNumber'],r['serverId'],r['serveNumber'],r.get('conditionGroup'))!=group:continue
        if not r.get('included',True) or r.get('eventType')!='serve' or r.get('speedApplicable') is False:continue
        if r.get('method')=='model_imputed' or r.get('serveId')==target.get('serveId'):continue
        if not all(r.get(k) is True for k in ('contactVerified','ballIdentityVerified','flightSegmentVerified')):continue
        if r.get('method')=='partial_trajectory_model' and r.get('qualityAccepted') is not True:continue
        key=r['serveId']
        if key in seen:raise ValueError('Duplicate support serve')
        seen.add(key);v=finite(r['launchSpeedKphEstimate'])
        if v<=0:raise ValueError('Positive supported estimate required')
        support.append(r)
    if not support:raise ValueError('No independent same-group support; leave a documented gap')
    values=[r['launchSpeedKphEstimate'] for r in support]
    interval=[min(r.get('sensitivityRangeKph',[r['launchSpeedKphEstimate']]*2)[0] for r in support),
              max(r.get('sensitivityRangeKph',[r['launchSpeedKphEstimate']]*2)[1] for r in support)]
    return {'method':'model_imputed','launchSpeedKphEstimate':sum(values)/len(values),
            'supportEnvelopeKph':interval,
            'imputationBasis':{'group':list(group),'supportServeIds':[r['serveId'] for r in support],
                'estimator':'Arithmetic mean of independently supported contacts, not recursively imputed',
                'caveat':'Population fallback, not this serve measured; missingness may be biased. Support envelope is not individual uncertainty.'}}

def assess_partial_quality(candidate,holdouts,variants,visual_checks,policy=None):
    """Acceptance screening, NOT absolute accuracy validation. Caller supplies perturbations.

    Pixel thresholds are defaults for a 1080p source; scale/review for each clip.
    Required sensitivity families: timing, geometry, drag, lift. They cannot be
    replaced by merely rerunning identical observations with the same assumptions.
    """
    p={'minObservations':12,'minSpanSeconds':.18,'maxRmsPixels':2.5,
       'maxHeldOutRmsPixels':3.5,'maxHeldOutSpeedFraction':.12,'maxSensitivityWidthFraction':.35}
    p.update(policy or {});reasons=[]
    for key in ('ballIdentityVerified','contactBracketVerified','preImpactSegmentVerified','cameraCalibrationReviewed','metricDepthConstraintReviewed','initialStateStabilityReviewed'):
        if visual_checks.get(key) is not True:reasons.append('missing '+key)
    speed=finite(candidate['launchSpeedKphEstimate'])
    if speed<=0:raise ValueError('Positive candidate speed required')
    if candidate['observationCount']<p['minObservations']:reasons.append('too few observations')
    if finite(candidate['spanSeconds'])<p['minSpanSeconds']:reasons.append('track too short')
    if finite(candidate['rmsPixels'])>p['maxRmsPixels']:reasons.append('large reprojection residual')
    if candidate.get('fitAtParameterBoundary') is not False:reasons.append('base fit at boundary or not checked')
    if candidate.get('converged') is not True:reasons.append('base fit did not converge')
    if len(holdouts)<2:reasons.append('missing alternating-frame holdouts')
    for h in holdouts:
        if h.get('converged') is not True or h.get('fitAtParameterBoundary') is not False or finite(h['heldOutRmsPixels'])>p['maxHeldOutRmsPixels'] or abs(finite(h['launchSpeedKphEstimate'])/speed-1)>p['maxHeldOutSpeedFraction']:
            reasons.append('unstable held-out prediction')
    if not {'timing','geometry','drag','lift'}<={v.get('family') for v in variants}:
        reasons.append('missing sensitivity families')
    required_sides={(family,side) for family in ('timing','geometry','drag','lift') for side in ('low','high')}
    if not required_sides<={(v.get('family'),v.get('side')) for v in variants}:
        reasons.append('missing low/high sensitivity checks')
    values=[speed]
    for v in variants:
        value=finite(v['launchSpeedKphEstimate'])
        if value<=0:raise ValueError('Positive variant speed required')
        values.append(value)
        if v.get('converged') is not True or v.get('fitAtParameterBoundary') is not False:reasons.append('perturbed fit unstable or at boundary')
    if (max(values)-min(values))/speed>p['maxSensitivityWidthFraction']:reasons.append('parameter sensitivity too wide')
    return {'accepted':not reasons,'reasons':list(dict.fromkeys(reasons)),
            'sensitivityRangeKph':[min(values),max(values)],'policy':p,
            'interpretation':'Conditional candidate passed/failed stated checks; no radar benchmark or calibrated absolute error.'}
