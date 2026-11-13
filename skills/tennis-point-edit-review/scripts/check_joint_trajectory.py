"""Numerical and evidence-boundary checks against independent analytic motion."""
import unittest
import numpy as np
from scipy.integrate import quad
from build_joint_case import synthetic_case, solve_case
from joint_trajectory import predict_joint, score_joint
from trajectory_measurements import CaptureClock, covariance_factors, whiten, integrate_flight, flight_metrics


class Measurements(unittest.TestCase):
    def test_fractional_gap_clock_is_continuous_and_does_not_change_pts(self):
        pts = np.arange(10)/30
        clock = CaptureClock(pts, omitted_intervals=[dict(beforeFrame=4, seconds=1/30, basis='Independent cadence evidence')])
        self.assertAlmostEqual(float(clock.seconds(3.5)), 4/30)
        self.assertLess(float(clock.seconds(4+1e-7)-clock.seconds(4-1e-7)), 1e-7)
        np.testing.assert_array_equal(clock.source, pts)
        with self.assertRaises(ValueError): CaptureClock(pts, omitted_intervals=[dict(beforeFrame=4, seconds=1/30)])

    def test_collision_and_observation_rows_receive_identical_readout_rule(self):
        clock = CaptureClock(np.arange(20)/30, readout_seconds=.02, frame_height=720)
        self.assertAlmostEqual(float(clock.elapsed(15.5, 600, 3.5, 120)), .4+.02*480/720)
        for row in [-1, 720, float('nan')]:
            with self.assertRaises(ValueError): clock.elapsed(15.5, row, 3.5, 120)

    def test_covariance_whitening_retains_anisotropy_and_correlation(self):
        covariance = [[[4., 1.], [1., 2.]]]
        r = np.array([[3., -2.]])
        white = whiten(r, covariance_factors(covariance, 1))
        self.assertAlmostEqual(float(np.sum(white**2)), float(r[0] @ np.linalg.inv(covariance[0]) @ r[0]))
        for bad in ([[[1., 2.], [2., 1.]]], [[[1., 0.], [1., 2.]]]):
            with self.assertRaises(ValueError): covariance_factors(bad, 1)

    def test_arc_length_is_integral_of_speed_not_chord_or_horizontal_distance(self):
        q = np.array([0., 0., 2.5, 4., 25., -1.])
        duration = .6
        metrics = flight_metrics(q, duration, drag=0.)
        expected = quad(lambda t: np.linalg.norm(q[3:]+[0., 0., -9.81*t]), 0., duration)[0]
        self.assertAlmostEqual(metrics['modeledArcLengthMetres'], expected, places=8)
        self.assertGreater(expected, metrics['horizontalDistanceMetres'])
        self.assertNotAlmostEqual(metrics['modeledPathMeanKph'], metrics['launchSpeedKphEstimate'])

    def test_backward_forward_and_repeated_times_against_analytic_ballistics(self):
        q = np.array([1., 2., 3., .2, 4., -1.])
        times = np.array([.2, -.1, 0., -.3, .2])
        actual = integrate_flight(q, times, drag=0.)
        expected = q[:3]+times[:, None]*q[3:]+times[:, None]**2*np.array([0., 0., -4.905])
        np.testing.assert_allclose(actual[:, :3], expected, atol=1e-9)
        np.testing.assert_allclose(actual[0], actual[-1], atol=1e-12)


class JointFit(unittest.TestCase):
    def test_both_directions_and_first_net_impact_recover_known_speed(self):
        for direction, net in ((1, False), (-1, False), (1, True), (-1, True)):
            with self.subTest(direction=direction, net=net):
                case = synthetic_case(direction, net)
                result = solve_case(case)
                self.assertTrue(result['converged'])
                self.assertFalse(result['fitAtParameterBoundary'])
                self.assertFalse(result['qualityAccepted'])
                self.assertAlmostEqual(result['launchSpeedKphEstimate'], case['truth']['launchSpeedKph'], places=4)
                self.assertLess(result['rmsPixels'], 1e-5)

    def test_joint_score_contains_toss_collision_priors_and_both_rebound_axes(self):
        case = synthetic_case()
        result = solve_case(case)
        self.assertEqual(set(result['residualBlockSums']), {'toss', 'air', 'post', 'collision', 'priors'})
        options = case['options']
        options = {k: options[k] for k in ('contact_sensor_row', 'collision', 'drag', 'lift_vector', 'toss_drag')}
        options['clock'] = CaptureClock(case['sourceSeconds'], frame_height=720)
        p = np.array(result['parameters'])
        p[13] = 0.  # Delete x curvature, keeping exactly the same air trajectory.
        score = score_joint(p, case['observations'], case['camera'], objective_id='frozen-synthetic', priors=case['options']['priors'], **options)
        self.assertLess(score['blockSums']['air'], 1e-7)
        self.assertGreater(score['blockSums']['post'], .01)

    def test_event_readout_changes_fitted_path_duration_not_video_pts(self):
        case = synthetic_case()
        opts = case['options']
        clock = CaptureClock(case['sourceSeconds'], readout_seconds=.01, frame_height=720)
        p = case['truth']['parameters']
        _, _, duration = predict_joint(p, case['observations'], case['camera'], clock=clock,
                                        contact_sensor_row=opts['contact_sensor_row'], collision=opts['collision'], drag=0., toss_drag=0.)
        expected = (p[10]-p[9])/30+.01*(opts['collision']['sensorRow']-opts['contact_sensor_row'])/720
        self.assertAlmostEqual(duration, expected)

    def test_no_post_net_or_air_observations_across_collision(self):
        case = synthetic_case(net=True)
        case['observations']['post'] = synthetic_case()['observations']['post']
        with self.assertRaises(ValueError): solve_case(case)
        case = synthetic_case()
        case['observations']['air']['frames'][-1] = case['options']['collision']['frameBracket'][1]+1
        with self.assertRaises(ValueError): solve_case(case)

    def test_event_bounds_and_ground_homography_cannot_silently_replace_evidence(self):
        case = synthetic_case()
        case['options']['bounds'][0][9] = 19.
        with self.assertRaises(ValueError): solve_case(case)
        case = synthetic_case()
        case['camera'] = np.eye(3).tolist()
        with self.assertRaises(ValueError): solve_case(case)

    def test_readout_scenario_cannot_reverse_observation_order(self):
        case = synthetic_case()
        opts = case['options']
        case['observations']['toss']['sensorRows'] = [200., 100.]*5
        clock = CaptureClock(case['sourceSeconds'], readout_seconds=.5, frame_height=720)
        with self.assertRaisesRegex(ValueError, 'strictly ordered'):
            predict_joint(case['truth']['parameters'], case['observations'], case['camera'], clock=clock,
                          contact_sensor_row=opts['contact_sensor_row'], collision=opts['collision'], drag=0., toss_drag=0.)
if __name__ == '__main__':
    unittest.main()
