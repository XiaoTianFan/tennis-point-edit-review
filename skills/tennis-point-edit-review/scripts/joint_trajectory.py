"""Conditional joint toss/contact/flight/collision candidate (NumPy + SciPy).

See references/serve-speed-joint-api.md. Camera calibration and source review
are inputs, not inferred here. Fixed physics per fit; refit across assumptions.
This Python API accepts a distortion-aware projection callable or a 3x4 matrix
for already-undistorted pixels. It never automatically approves a candidate.
"""
import numpy as np
from scipy.optimize import least_squares
from trajectory_measurements import covariance_factors, whiten, integrate_flight, flight_metrics
from joint_speed_quality import candidate_fingerprint


def project_points(camera, xyz):
    xyz = np.asarray(xyz, float)
    if callable(camera):
        pixels = np.asarray(camera(xyz), float)
    else:
        matrix = np.asarray(camera, float)
        if matrix.shape != (3, 4) or not np.isfinite(matrix).all() or np.linalg.matrix_rank(matrix) < 3:
            raise ValueError('Reviewed metric camera required')
        image = np.c_[xyz, np.ones(len(xyz))] @ matrix.T
        if np.any(image[:, 2] <= 1e-8):
            raise ValueError('Ball behind/on camera plane')
        pixels = image[:, :2]/image[:, 2:]
    if pixels.shape != (len(xyz), 2) or not np.isfinite(pixels).all():
        raise ValueError('Camera must project every point to finite pixels')
    return pixels


def _observations(group, minimum):
    f = np.asarray(group['frames'], float)
    xy = np.asarray(group['xy'], float)
    rows = np.asarray(group['sensorRows'], float)
    if f.ndim != 1 or len(f) < minimum or xy.shape != (len(f), 2) or rows.shape != f.shape:
        raise ValueError('Insufficient or mismatched reviewed observations')
    if not np.isfinite(np.r_[f, xy.ravel(), rows]).all() or np.any(np.diff(f) <= 0):
        raise ValueError('Finite unique ordered observation frames required')
    return f, xy, rows, covariance_factors(group['covariances'], len(f))


def predict_joint(parameters, observations, camera, *, clock, contact_sensor_row, collision, drag=.020, lift_vector=(0., 0., 0.), toss_drag=.020):
    """Project observed groups and event using one corrected clock for ALL rows."""
    p = np.asarray(parameters, float)
    contact, velocity, toss_velocity = p[:3], p[3:6], p[6:9]
    cf, ef = p[9:11]
    duration = float(clock.elapsed(ef, collision['sensorRow'], cf, contact_sensor_row))
    if duration <= 0:
        raise ValueError('Corrected collision must follow contact')
    physics = dict(drag=drag, lift_vector=lift_vector)
    end = integrate_flight(np.r_[contact, velocity], [duration], **physics)[0, :3]
    endpoint_xy = project_points(camera, end[None, :])[0]
    predicted = {}
    for name, group in observations.items():
        times = clock.elapsed(group['frames'], group['sensorRows'], cf, contact_sensor_row)
        if not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
            raise ValueError('Corrected observation times must remain strictly ordered')
        if name == 'toss':
            if np.any(times >= 0):
                raise ValueError('Toss observations must precede corrected contact')
            xyz = integrate_flight(np.r_[contact, toss_velocity], times, drag=toss_drag)[:, :3]
            predicted[name] = project_points(camera, xyz)
        elif name == 'air':
            if np.any(times <= 0) or np.any(times >= duration):
                raise ValueError('Air observations must be strictly before first collision')
            xyz = integrate_flight(np.r_[contact, velocity], times, **physics)[:, :3]
            predicted[name] = project_points(camera, xyz)
        elif name == 'post':
            if collision['kind'] != 'first_bounce' or len(p) != 15 or np.any(times <= duration):
                raise ValueError('Rebound localization only after first court bounce')
            dt = (times-duration)[:, None]
            # A separate image curve in BOTH axes; never integrated into serve path.
            predicted[name] = endpoint_xy + dt*p[11:13] + dt**2*p[13:15]
        else:
            raise ValueError('Unknown observation group')
    return predicted, end, duration


def score_joint(parameters, observations, camera, *, objective_id, priors=(), **options):
    """Evaluate any fit on one FROZEN full objective for comparable diagnostics.

    options are predict_joint's clock/contact/collision/physics arguments. Keep
    the candidate's physical coefficients when scoring its predicted path, but
    keep reference observations, covariance, priors and collision weights fixed.
    objective_id identifies those reference inputs, not the candidate parameters.
    """
    if not objective_id:
        raise ValueError('Versioned reference objective identity required')
    data = {name: _observations(group, 1) for name, group in observations.items()}
    predicted, end, _ = predict_joint(parameters, observations, camera, **options)
    blocks = {name: whiten(predicted[name]-group[1], group[3]).ravel() for name, group in data.items()}
    collision = options['collision']
    blocks['collision'] = np.array([(end[collision['axis']]-collision['valueMetres'])/collision['sigmaMetres']])
    blocks['priors'] = np.array([(parameters[r['index']]-r['mean'])/r['sigma'] for r in priors])
    sums = {key: float(np.dot(value, value)) for key, value in blocks.items()}
    return dict(objectiveId=objective_id, sumSquares=sum(sums.values()), blockSums=sums)


def fit_joint(observations, camera, *, clock, contact_sensor_row, contact_bracket,
              collision, initial_parameters, bounds, evidence_id, priors=(),
              drag=.020, lift_vector=(0., 0., 0.), toss_drag=.020, max_evaluations=400):
    """Fit one conditional candidate; see API reference for parameter order/units.

    Bounds/priors are independently grounded. No universal geometry or precision
    defaults. Covariance is in the same image coordinates as projected centroids.
    """
    if not evidence_id or not {'toss', 'air'} <= set(observations) or set(observations)-{'toss', 'air', 'post'}:
        raise ValueError('Versioned evidence identity, toss and pre-impact air groups required')
    data = {name: _observations(group, 6 if name == 'air' else 3) for name, group in observations.items()}
    cb = np.asarray(contact_bracket, float)
    eb = np.asarray(collision['frameBracket'], float)
    if cb.shape != (2,) or eb.shape != (2,) or not np.isfinite(np.r_[cb, eb]).all() or cb[0] >= cb[1] or eb[0] >= eb[1] or cb[1] >= eb[0]:
        raise ValueError('Ordered non-overlapping reviewed event brackets required')
    if collision.get('kind') not in ('first_bounce', 'first_net_impact') or collision.get('verified') is not True or not collision.get('basis'):
        raise ValueError('Reviewed FIRST collision required')
    axis, value, sigma = collision['axis'], float(collision['valueMetres']), float(collision['sigmaMetres'])
    if type(axis) is not int or axis not in (0, 1, 2) or not np.isfinite([value, sigma]).all() or sigma <= 0:
        raise ValueError('Finite collision plane and positive constraint sigma required')
    if collision['kind'] == 'first_bounce' and (axis != 2 or value <= 0):
        raise ValueError('Court contact plane is ball CENTRE height (positive radius)')
    if collision['kind'] == 'first_net_impact' and ('post' in observations or axis == 2):
        raise ValueError('Net impact stops flight; no post-net bounce localization')
    if data['toss'][0][-1] >= cb[0] or data['air'][0][0] <= cb[1] or data['air'][0][-1] >= eb[0]:
        raise ValueError('Reviewed groups must stay outside event brackets')
    if 'post' in data and data['post'][0][0] <= eb[1]:
        raise ValueError('Post-bounce group must follow whole collision bracket')
    p0 = np.asarray(initial_parameters, float)
    lo, hi = np.asarray(bounds, float)
    size = 15 if 'post' in data else 11
    if p0.shape != (size,) or lo.shape != p0.shape or hi.shape != p0.shape or not np.isfinite(np.r_[p0, lo, hi]).all() or np.any(lo >= hi) or np.any(p0 <= lo) or np.any(p0 >= hi):
        raise ValueError('Finite parameters strictly inside matching bounds required')
    if lo[9] < cb[0] or hi[9] > cb[1] or lo[10] < eb[0] or hi[10] > eb[1]:
        raise ValueError('Fitted event bounds must stay inside reviewed brackets')
    for prior in priors:
        if type(prior['index']) is not int or not 0 <= prior['index'] < size or not np.isfinite([prior['mean'], prior['sigma']]).all() or prior['sigma'] <= 0 or not prior.get('basis'):
            raise ValueError('Finite independently grounded parameter prior required')
    options = dict(clock=clock, contact_sensor_row=contact_sensor_row, collision=collision, drag=drag, lift_vector=lift_vector, toss_drag=toss_drag)

    def blocks(p):
        predicted, end, _ = predict_joint(p, observations, camera, **options)
        residuals = {name: whiten(predicted[name]-group[1], group[3]).ravel() for name, group in data.items()}
        residuals['collision'] = np.array([(end[axis]-value)/sigma])
        residuals['priors'] = np.array([(p[r['index']]-r['mean'])/r['sigma'] for r in priors])
        return residuals

    result = least_squares(lambda p: np.concatenate(list(blocks(p).values())), p0,
                           bounds=(lo, hi), max_nfev=max_evaluations, x_scale='jac')
    predicted, _, duration = predict_joint(result.x, observations, camera, **options)
    residuals = blocks(result.x)
    metrics = flight_metrics(result.x[:6], duration, drag=drag, lift_vector=lift_vector)
    candidate = dict(metrics, method='joint_trajectory_model', qualityAccepted=False,
                     parameters=result.x.tolist(), physics=dict(dragPerM=drag, liftVectorPerM=list(lift_vector), tossDragPerM=toss_drag),
                     evidenceId=evidence_id, converged=bool(result.success),
                     fitAtParameterBoundary=bool(np.any(np.minimum(result.x-lo, hi-result.x)/(hi-lo) < .001)),
                     observationCount=len(data['air'][0]),
                     spanSeconds=float(np.ptp(clock.elapsed(data['air'][0], data['air'][2], result.x[9], contact_sensor_row))),
                     rmsPixels=float(np.sqrt(np.mean(np.sum((predicted['air']-data['air'][1])**2, axis=1)))),
                     weightedResidualSumSquares=float(sum(np.dot(v, v) for v in residuals.values())),
                     residualBlockSums={k: float(np.dot(v, v)) for k, v in residuals.items()},
                     predictedPixels={k: v.tolist() for k, v in predicted.items()},
                     collisionKind=collision['kind'], interpretation='Conditional joint candidate; source review, validation and uncertainty still required.')
    candidate['candidateId'] = candidate_fingerprint(candidate)
    candidate['referenceScore'] = score_joint(result.x, observations, camera, objective_id=evidence_id, priors=priors, **options)
    return candidate
