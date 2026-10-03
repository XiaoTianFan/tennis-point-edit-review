"""Optional conditional 3D flight candidate fitter (NumPy + SciPy).

The caller supplies a reviewed camera projection, metric coordinate system,
contact time, pre-impact ball observations, parameter bounds and priors. This
does not calibrate a camera, track a ball or automatically accept a speed.
"""
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares

def acceleration(velocity,drag=.020,lift_vector=(0.,0.,0.),gravity=9.81):
    v=np.asarray(velocity,dtype=float);speed=np.linalg.norm(v)
    return np.array([0.,0.,-gravity])-drag*speed*v+speed*np.cross(np.asarray(lift_vector,float),v)

def simulate(state,times,drag=.020,lift_vector=(0.,0.,0.),gravity=9.81):
    """State is [x,y,z,vx,vy,vz] in metres/seconds; z points up. RK45 integration."""
    q=np.asarray(state,dtype=float);ts=np.asarray(times,dtype=float);lv=np.asarray(lift_vector,dtype=float)
    if q.shape!=(6,) or ts.ndim!=1 or not len(ts) or lv.shape!=(3,):raise ValueError('Invalid state, times, or lift vector shape')
    if not np.isfinite(q).all() or not np.isfinite(ts).all() or not np.isfinite(lv).all() or not np.isfinite([drag,gravity]).all():raise ValueError('Finite physical inputs required')
    if ts[0]<0 or ts[-1]<=0 or np.any(np.diff(ts)<=0) or drag<0 or gravity<0:raise ValueError('Ordered positive flight times and nonnegative physics required')
    def rhs(_,x):return np.r_[x[3:],acceleration(x[3:],drag,lv,gravity)]
    result=solve_ivp(rhs,(0.,ts[-1]),q,t_eval=ts,rtol=1e-7,atol=1e-8,max_step=.02)
    if not result.success:raise ValueError('Flight integration failed')
    return result.y.T

def project(state,times,camera,**physics):
    cam=np.asarray(camera,float)
    if cam.shape!=(3,4) or not np.isfinite(cam).all() or np.linalg.matrix_rank(cam)<3:raise ValueError('Calibrated 3x4 camera projection required')
    xyz=simulate(state,times,**physics)[:,:3]
    uv=np.c_[xyz,np.ones(len(xyz))]@cam.T
    if np.any(uv[:,2]<=1e-8):raise ValueError('Trajectory behind or on the camera plane')
    return uv[:,:2]/uv[:,2:]

def fit_partial(observations,camera,*,contact_seconds,initial_state,bounds,priors=(),
                collision_lower_seconds=None,pixel_sigma=2.5,drag=.020,
                lift_vector=(0.,0.,0.),gravity=9.81,max_evaluations=250):
    """Observations = [absolute source seconds, pixel x, pixel y].

    Priors = {index: state component 0..5, mean: value, sigma: positive spread}.
    Bounds, camera and physics stay fixed during each fit; assess their uncertainty
    with separate fits. No source time, height or calibration is fabricated here.
    """
    obs=np.asarray(observations,float);lo,hi=np.asarray(bounds,float);q0=np.asarray(initial_state,float)
    if obs.ndim!=2 or obs.shape[1]!=3 or len(obs)<6 or not np.isfinite(obs).all():raise ValueError('At least six finite observations required')
    if lo.shape!=(6,) or hi.shape!=(6,) or q0.shape!=(6,) or not np.isfinite(np.r_[lo,hi,q0]).all() or np.any(lo>=hi) or np.any(q0<=lo) or np.any(q0>=hi):raise ValueError('Finite initial state strictly inside metric bounds required')
    if not np.isfinite(contact_seconds) or np.any(obs[:,0]<=contact_seconds) or np.any(np.diff(obs[:,0])<=0):raise ValueError('Unique source times after observed contact required')
    if collision_lower_seconds is not None and (not np.isfinite(collision_lower_seconds) or obs[-1,0]>=collision_lower_seconds):raise ValueError('Pre-impact fit cannot include collision or post-impact frames')
    if not np.isfinite(pixel_sigma) or pixel_sigma<=0:raise ValueError('Positive source-pixel residual scale required')
    for p in priors:
        if type(p['index']) is not int or not 0<=p['index']<6 or not np.isfinite([p['mean'],p['sigma']]).all() or p['sigma']<=0:raise ValueError('Invalid metric prior')
    times=obs[:,0]-contact_seconds;physics=dict(drag=drag,lift_vector=lift_vector,gravity=gravity)
    def residual(q):
        pixels=((project(q,times,camera,**physics)-obs[:,1:])/pixel_sigma).ravel()
        return np.r_[pixels,[(q[p['index']]-p['mean'])/p['sigma'] for p in priors]]
    result=least_squares(residual,q0,bounds=(lo,hi),loss='soft_l1',f_scale=2.,max_nfev=max_evaluations)
    predicted=project(result.x,times,camera,**physics)
    boundary=np.minimum(result.x-lo,hi-result.x)/(hi-lo)<.001
    return {'launchSpeedKphEstimate':float(np.linalg.norm(result.x[3:])*3.6),
            'state':result.x.tolist(),'rmsPixels':float(np.sqrt(np.mean(np.sum((predicted-obs[:,1:])**2,axis=1)))),
            'observationCount':len(obs),'spanSeconds':float(np.ptp(times)),
            'fitAtParameterBoundary':bool(boundary.any()),'converged':bool(result.success),
            'predictedPixels':predicted.tolist(),'residualPixels':(predicted-obs[:,1:]).tolist(),
            'method':'partial_trajectory_model','qualityAccepted':False,
            'parameters':{'dragPerM':drag,'liftVectorPerM':list(lift_vector),'gravityMS2':gravity},
            'interpretation':'Candidate only. Requires source inspection, holdout/perturbation screening, and uncertainty disclosure.'}

def alternating_holdouts(observations,camera,**options):
    """Predict unused alternating frames. This is not independent speed ground truth."""
    obs=np.asarray(observations,float)
    if len(obs)<12:raise ValueError('Both training subsets need at least six observations')
    out=[]
    for parity in (0,1):
        train=obs[parity::2];test=obs[1-parity::2]
        fit=fit_partial(train,camera,**options)
        physics={k:options[k] for k in ('drag','lift_vector','gravity') if k in options}
        prediction=project(fit['state'],test[:,0]-options['contact_seconds'],camera,**physics)
        out.append({k:fit[k] for k in ('launchSpeedKphEstimate','fitAtParameterBoundary','converged')})
        out[-1].update(parity=parity,heldOutRmsPixels=float(np.sqrt(np.mean(np.sum((prediction-test[:,1:])**2,axis=1)))))
    return out
