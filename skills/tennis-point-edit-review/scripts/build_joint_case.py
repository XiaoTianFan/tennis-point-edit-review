"""Generate fictional joint-fit inputs and actual computed output; no private media.

Independent analytic zero-drag trajectories provide known test truth. This is
an API/numerical demonstration, never evidence of real-camera speed accuracy.
"""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from joint_trajectory import fit_joint, project_points
from trajectory_measurements import CaptureClock


def synthetic_case(direction=1, net=False):
    camera = np.array([[500., 480., 0., 9600.], [0., 360., -500., 7200.], [0., 1., 0., 20.]])
    contact = np.array([0.2, -9.*direction, 2.5])
    outgoing = np.array([1.7*direction, 28.*direction, -3.5 if net else -1.])
    toss = np.array([.1, .15, -1.3])
    cf = 20.35
    duration = 9./28. if net else (-1+math.sqrt(1+2*9.81*(contact[2]-.0335)))/9.81
    ef = cf+30*duration
    collision = dict(kind='first_net_impact' if net else 'first_bounce', verified=True,
                     basis='Synthetic analytic first collision', frameBracket=[math.floor(ef), math.ceil(ef)],
                     axis=1 if net else 2, valueMetres=0. if net else .0335, sigmaMetres=.004,
                     sensorRow=360.)
    parameters = np.r_[contact, outgoing, toss, cf, ef]
    if not net:
        parameters = np.r_[parameters, [22., -38., 11., 17.]]
    observations = {}
    for name, frames in (('toss', np.arange(10., 20.)), ('air', np.arange(22., math.floor(ef)))):
        times = (frames-cf)/30
        velocity = toss if name == 'toss' else outgoing
        xyz = contact+times[:, None]*velocity + times[:, None]**2*np.array([0., 0., -9.81/2])
        xy = project_points(camera, xyz)
        observations[name] = dict(frames=frames.tolist(), xy=xy.tolist(), sensorRows=xy[:, 1].tolist(),
                                  covariances=np.tile([[.25, .06], [.06, .64]], (len(frames), 1, 1)).tolist())
    end = contact+duration*outgoing+duration**2*np.array([0., 0., -9.81/2])
    end_xy = project_points(camera, end[None, :])[0]
    collision['sensorRow'] = float(end_xy[1])
    if not net:
        frames = np.arange(math.ceil(ef)+1., math.ceil(ef)+6.)
        dt = (frames-ef)/30
        xy = end_xy + dt[:, None]*parameters[11:13]+dt[:, None]**2*parameters[13:15]
        observations['post'] = dict(frames=frames.tolist(), xy=xy.tolist(), sensorRows=xy[:, 1].tolist(),
                                    covariances=np.tile(np.eye(2)*.5, (len(frames), 1, 1)).tolist())
    spread = np.array([.5, 1., .5, 5., 10., 5., 2., 2., 2., .5, .5]+([] if net else [60.]*4))
    lo, hi = parameters-spread, parameters+spread
    lo[9], hi[9] = 20., 21.
    lo[10], hi[10] = collision['frameBracket']
    initial = parameters.copy()
    initial[:9] += [.02, .1, .04, .2, -.3*direction, .1, .02, -.03, .06]
    initial[9:11] += [.04, -.06]
    options = dict(contact_sensor_row=float(project_points(camera, contact[None, :])[0, 1]),
                   contact_bracket=[20., 21.], collision=collision,
                   initial_parameters=initial.tolist(), bounds=[lo.tolist(), hi.tolist()],
                   evidence_id='synthetic-joint-'+str(direction)+'-'+('net' if net else 'bounce'),
                   priors=[dict(index=1, mean=float(contact[1]), sigma=.12, basis='Synthetic independent baseline-depth measurement')],
                   drag=0., toss_drag=0., lift_vector=[0., 0., 0.])
    return dict(camera=camera.tolist(), observations=observations, sourceSeconds=(np.arange(80)/30).tolist(),
                options=options, truth=dict(parameters=parameters.tolist(), launchSpeedKph=3.6*float(np.linalg.norm(outgoing))))


def solve_case(case):
    return fit_joint(case['observations'], case['camera'], clock=CaptureClock(case['sourceSeconds'], frame_height=720), **case['options'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    args = parser.parse_args()
    case = synthetic_case()
    output = dict(description='Synthetic numerical regression, not a real-world benchmark or approved label.',
                  case=case, candidate=solve_case(case))
    with Path(args.output).open('x', encoding='utf-8') as target:
        target.write(json.dumps(output, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
