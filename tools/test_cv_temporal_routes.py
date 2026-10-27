"""Changed-contract checks for observation-only experimental routing."""
import json
import unittest
from fractions import Fraction

try:
    import cv_temporal_routes as routes
except ImportError:
    routes = None


def frames(fn, count=37, times=None):
    values = times or [i/60 for i in range(count)]
    return [dict(id=f'F{i:09}', ordinal=i, pts=i, timeBase='1/60',
                 seconds=str(Fraction(t)), modelCandidates=fn(t)) for i,t in enumerate(values)]


@unittest.skipIf(routes is None, 'NumPy runtime required for temporal experiment')
class TemporalRoutes(unittest.TestCase):
    def setUp(self):
        self.cfg = routes.config({'netProjectionBox':[0,470,1920,540]})

    def test_smooth_flight_is_not_collision(self):
        result = routes.analyze_window(frames(lambda t:[dict(x=100+100*t,y=400+180*(t-.3)**2,view=0)]), self.cfg)
        self.assertEqual(result['candidates'], [])
        self.assertTrue(result['fallbackRequired'])

    def test_stationary_competitor_retained_and_moving_collision_localized(self):
        result = routes.analyze_window(frames(lambda t:[dict(x=900,y=510,view=0),
                 dict(x=100+100*t,y=510-180*abs(t-.3),view=0)]), self.cfg)
        self.assertEqual(sum(p['stationaryResponse'] for p in result['tracks']),1)
        self.assertTrue(any(abs(float(Fraction(e['seconds']))-.3) <= 1/60 for e in result['candidates']))
        self.assertEqual(sum(len(p['observations']) for p in result['tracks']),74)
        self.assertTrue(all(p['semanticObject'] is None for p in result['tracks']))
        json.dumps(result,allow_nan=False)

    def test_net_projection_does_not_adopt_tennis_outcome(self):
        result = routes.analyze_window(frames(lambda t:[dict(x=100+100*t,y=510-180*abs(t-.3),view=0)]), self.cfg)
        self.assertTrue(result['candidates'])
        for event in result['candidates']:
            self.assertTrue(event['netProjectionOverlap'])
            self.assertFalse(event['automaticAccepted'])
            self.assertIsNone(event['collisionType'])
            self.assertIsNone(event['firstDeadBall'])
            self.assertIsNone(event['pointWinner'])
        self.assertIsNone(result['pointCount'])

    def test_gap_does_not_manufacture_collision(self):
        times = [i/60 for i in range(12)]+[.4+i/60 for i in range(12)]
        result = routes.analyze_window(frames(lambda t:[dict(x=100+100*t,y=510-180*abs(t-.3),view=0)],times=times), self.cfg)
        self.assertEqual(result['candidates'],[])
        self.assertEqual(len(result['tracks']),2)

    def test_views_remain_separate_observations(self):
        result = routes.analyze_window(frames(lambda t:[dict(x=100+100*t,y=510-180*abs(t-.3),view=v) for v in [0,1]]),self.cfg)
        self.assertEqual(len(result['tracks']),2)
        self.assertTrue(all(len({o['view'] for o in p['observations']})==1 for p in result['tracks']))

    def test_short_stationary_track_serializes_without_becoming_old_ball(self):
        result = routes.analyze_window(frames(lambda t:[dict(x=100,y=500,view=0)],count=12),self.cfg)
        self.assertFalse(result['tracks'][0]['stationaryResponse'])
        json.dumps(result,allow_nan=False)

    def test_invalid_time_and_parameters_fail(self):
        with self.assertRaises(ValueError):
            routes.config({'maxGapSeconds':float('nan')})
        with self.assertRaises(ValueError):
            routes.config({'netProjectionBox':[0,540,100,470]})
        with self.assertRaises(ValueError):
            routes.analyze_window(frames(lambda t:[],times=[.1,.1]),self.cfg)


if __name__=='__main__':
    unittest.main()
