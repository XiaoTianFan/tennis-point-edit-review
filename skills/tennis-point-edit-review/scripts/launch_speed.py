"""Conditional launch-speed reconstruction and per-set aggregation.

Inputs must identify measured vs assumed geometry/timing. Output is an estimate,
not a radar reading. No automatic unlabelled filling of missing observations.
"""
import math
from collections import defaultdict

def flight(vx, vz, height, duration, *, drag=.020, lift=0., gravity=9.81, steps=100):
    """2D vertical-plane RK4, quadratic drag and signed transverse lift."""
    if duration<=0 or height<0 or drag<0:raise ValueError('Invalid physical input')
    q=[0.,height,vx,vz];dt=duration/steps
    def deriv(s):
        x,z,u,w=s;v=math.hypot(u,w)
        return [u,w,-drag*v*u-lift*v*w,-gravity-drag*v*w+lift*v*u]
    for _ in range(steps):
        a=deriv(q);b=deriv([q[i]+dt*a[i]/2 for i in range(4)])
        c=deriv([q[i]+dt*b[i]/2 for i in range(4)]);d=deriv([q[i]+dt*c[i] for i in range(4)])
        q=[q[i]+dt*(a[i]+2*b[i]+2*c[i]+d[i])/6 for i in range(4)]
    return q

def reconstruct(distance, duration, height, end_height=0., *, drag=.020, lift=0., gravity=9.81):
    """Solve initial velocity from endpoint distance, duration and height.

    Identifiability is conditional on supplied drag/lift and geometry. Vary them
    for a sensitivity interval; do not call it a calibrated confidence interval.
    """
    if distance<=0 or duration<=0:raise ValueError('Positive distance and time required')
    v=[distance/duration,(end_height-height)/duration+gravity*duration/2]
    for _ in range(20):
        q=flight(*v,height,duration,drag=drag,lift=lift,gravity=gravity)
        err=[q[0]-distance,q[1]-end_height]
        if math.hypot(*err)<1e-5:break
        cols=[]
        for i in range(2):
            w=v.copy();w[i]+=.001;r=flight(*w,height,duration,drag=drag,lift=lift,gravity=gravity)
            cols.append([(r[0]-q[0])/.001,(r[1]-q[1])/.001])
        a,c=cols[0];b,d=cols[1];det=a*d-b*c
        if abs(det)<1e-9:raise ValueError('Underdetermined inverse trajectory')
        v[0]-=(d*err[0]-b*err[1])/det;v[1]-=(-c*err[0]+a*err[1])/det
    else:raise ValueError('Inverse trajectory did not converge')
    return {'launchSpeedKphEstimate':3.6*math.hypot(*v),'initialVelocityMS':v,'model':'gravity + quadratic drag + stated signed lift',
            'parameters':{'dragPerM':drag,'liftPerM':lift,'gravityMS2':gravity},'endpointResidualM':math.hypot(*err)}

def aggregate_serves(records):
    """Each included physical serve gets one vote; never select an error bound."""
    groups=defaultdict(list);seen=set()
    for r in records:
        if not r.get('included',True):continue
        key=(r['setNumber'],r['serveId'])
        if key in seen:raise ValueError('Duplicate serve in set')
        seen.add(key)
        value=r.get('launchSpeedKphEstimate')
        if value is None or not math.isfinite(value) or value<=0:raise ValueError('Complete per-serve estimates required; obtain evidence or explicitly labelled model imputation first')
        if r['serveNumber'] not in (1,2):raise ValueError('Unresolved serve number')
        if r.get('method')=='model_imputed' and not r.get('imputationBasis'):raise ValueError('Imputation requires disclosed supporting population')
        groups[(r['setNumber'],r['serverId'])].append(r)
    out=[]
    for (set_number,player),rr in sorted(groups.items()):
        best=max(rr,key=lambda r:r['launchSpeedKphEstimate'])
        by={n:[r['launchSpeedKphEstimate'] for r in rr if r['serveNumber']==n] for n in (1,2)}
        out.append({'setNumber':set_number,'serverId':player,'count':len(rr),
          'allServeMeanKphEstimate':sum(r['launchSpeedKphEstimate'] for r in rr)/len(rr),
          'firstServeMeanKphEstimate':sum(by[1])/len(by[1]) if by[1] else None,
          'secondServeMeanKphEstimate':sum(by[2])/len(by[2]) if by[2] else None,
          'firstServeCount':len(by[1]),'secondServeCount':len(by[2]),
          'fastestServeKphEstimate':best['launchSpeedKphEstimate'],'fastestServeId':best['serveId'],
          'imputedCount':sum(r.get('method')=='model_imputed' for r in rr)})
    return out



