"""Clock, covariance and full-path primitives for reviewed 3D reconstruction.

No detection, calibration, capture-cadence inference or acceptance is performed.
Source PTS stay immutable; this clock is used only for physical inference.
"""
import numpy as np
from scipy.integrate import solve_ivp
from partial_trajectory import acceleration


class CaptureClock:
    def __init__(self, source_seconds, *, omitted_intervals=(), readout_seconds=0., frame_height=None):
        self.source = np.asarray(source_seconds, float)
        if self.source.ndim != 1 or len(self.source) < 2 or not np.isfinite(self.source).all() or np.any(np.diff(self.source) <= 0):
            raise ValueError('Strictly increasing native source PTS required')
        self.gaps = []
        seen = set()
        for gap in omitted_intervals:
            frame, duration = gap['beforeFrame'], float(gap['seconds'])
            if type(frame) is not int or not 1 <= frame < len(self.source) or frame in seen:
                raise ValueError('Unique gap boundary inside source required')
            if not np.isfinite(duration) or duration <= 0 or not gap.get('basis'):
                raise ValueError('Positive omitted duration and independent cadence evidence required')
            seen.add(frame)
            self.gaps.append((frame, duration))
        self.readout = float(readout_seconds)
        self.height = float(frame_height) if frame_height is not None else None
        if not np.isfinite(self.readout) or (self.height is not None and (not np.isfinite(self.height) or self.height <= 0)):
            raise ValueError('Finite readout and positive sensor height required')
        if self.readout and self.height is None:
            raise ValueError('Rolling readout needs native sensor height')

    def seconds(self, frame):
        f = np.asarray(frame, float)
        if not np.isfinite(f).all() or np.any(f < 0) or np.any(f > len(self.source)-1):
            raise ValueError('Fractional frame outside source clock')
        value = np.interp(f, np.arange(len(self.source)), self.source)
        # A missing interval lies BETWEEN frames. A step at the later integer
        # frame would introduce an artificial jump into fitted event times.
        for boundary, duration in self.gaps:
            value = value + duration * np.clip(f-boundary+1, 0, 1)
        return value

    def elapsed(self, frame, sensor_row, contact_frame, contact_sensor_row):
        rows = np.asarray(sensor_row, float)
        contact_row = float(contact_sensor_row)
        if not np.isfinite(rows).all() or not np.isfinite(contact_row):
            raise ValueError('Native row coordinates required, including collision rows')
        if self.height is not None and (np.any(rows < 0) or np.any(rows >= self.height) or not 0 <= contact_row < self.height):
            raise ValueError('Rows must belong to the unwarped source image')
        rolling = self.readout*(rows-contact_row)/self.height if self.readout else 0.
        return self.seconds(frame)-self.seconds(contact_frame)+rolling


def covariance_factors(covariances, count):
    """Cholesky factors for source/local coordinate 2x2 centroid covariances."""
    c = np.asarray(covariances, float)
    if c.shape != (count, 2, 2) or not np.isfinite(c).all() or not np.allclose(c, c.transpose(0, 2, 1), rtol=1e-9, atol=1e-12):
        raise ValueError('One finite symmetric 2x2 covariance per observed centroid required')
    try:
        return np.linalg.cholesky(c)
    except np.linalg.LinAlgError as error:
        raise ValueError('Centroid covariance must be positive definite') from error


def whiten(residual_xy, factors):
    residual = np.asarray(residual_xy, float)
    return np.linalg.solve(factors, residual[..., None])[..., 0]


def integrate_flight(state, times, *, drag=.020, lift_vector=(0., 0., 0.), gravity=9.81, max_step=.01):
    """RK45 forwards AND backwards from contact; seventh state is signed arc length.

    Supports unsorted/repeated/zero times. Backward integration is for the toss,
    with its own velocity at contact, never a reversed outgoing serve.
    """
    q = np.asarray(state, float)
    t = np.asarray(times, float)
    lift = np.asarray(lift_vector, float)
    if q.shape != (6,) or lift.shape != (3,) or t.ndim != 1 or not len(t):
        raise ValueError('Six-state contact, three-component lift and nonempty times required')
    if not np.isfinite(np.r_[q, t, lift, drag, gravity, max_step]).all() or drag < 0 or gravity <= 0 or max_step <= 0:
        raise ValueError('Finite physical inputs, positive gravity/step and nonnegative drag required')
    initial = np.r_[q, 0.]
    out = np.tile(initial, (len(t), 1))

    def rhs(_, x):
        return np.r_[x[3:6], acceleration(x[3:6], drag, lift, gravity), np.linalg.norm(x[3:6])]

    for positive in (False, True):
        indices = np.flatnonzero(t > 0 if positive else t < 0)
        if not len(indices):
            continue
        end = float(np.max(t[indices]) if positive else np.min(t[indices]))
        solution = solve_ivp(rhs, (0., end), initial, rtol=1e-9, atol=1e-10, max_step=max_step, dense_output=True)
        if not solution.success:
            raise ValueError('Trajectory integration failed')
        out[indices] = solution.sol(t[indices]).T
    return out


def flight_metrics(state, collision_seconds, **physics):
    """Complete MODELLED pre-first-collision path, never a directly measured length."""
    duration = float(collision_seconds)
    if not np.isfinite(duration) or duration <= 0:
        raise ValueError('Positive reviewed first-collision duration required')
    q = np.asarray(state, float)
    end = integrate_flight(q, [duration], **physics)[0]
    horizontal = float(np.linalg.norm(end[:2]-q[:2]))
    arc = float(end[6])
    return dict(launchSpeedKphEstimate=float(3.6*np.linalg.norm(q[3:])),
                flightSeconds=duration, horizontalDistanceMetres=horizontal,
                horizontalMeanFlightKph=3.6*horizontal/duration,
                modeledArcLengthMetres=arc, modeledPathMeanKph=3.6*arc/duration,
                preCollisionSpeedKph=float(3.6*np.linalg.norm(end[3:6])),
                collisionPositionMetres=end[:3].tolist())
