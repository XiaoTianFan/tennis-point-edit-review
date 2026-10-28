"""Gap review contracts: uncertain ranges must never become exact contacts."""
import unittest
from fractions import Fraction

import cv_gap_review_routes as gaps


def track(name, frames, fn, view=0, stationary=False):
    return dict(id=name,stationaryResponse=stationary,observations=[
        dict(id=f'{name}/{i}',frame=i,pts=i,timeBase='1/60',seconds=str(Fraction(i,60)),
             view=view,x=fn(i/60)[0],y=fn(i/60)[1]) for i in frames])


def window(tracks,candidates=None):
    return dict(windowId='test',tracks=tracks,candidates=candidates or [],sourceIntervalSeconds=[0.,1.])


class GapRoutes(unittest.TestCase):
    def setUp(self):
        self.cfg = gaps.config({})
        self.flight = lambda t:(100+100*t,500-400*abs(t-.3))

    def test_two_sided_gap_has_range_and_retains_all_support(self):
        tracks = [track('a',range(10,16),self.flight),track('b',range(21,27),self.flight)]
        result = gaps.analyze_window(window(tracks),self.cfg)
        self.assertEqual(len(result['gapRoutes']),1)
        route = result['gapRoutes'][0]
        self.assertEqual(route['frameBracket'],[15,21])
        self.assertIsNone(route['exactEventFrame'])
        self.assertIsNone(route['collisionType'])
        self.assertFalse(route['automaticAccepted'])
        self.assertEqual(result['interpolatedObservations'],0)
        self.assertEqual(result['originalObservations'],12)
        self.assertTrue(result['omissionAuditRequired'])

    def test_smooth_occlusion_is_not_collision_route(self):
        fn = lambda t:(100+100*t,400+600*(t-.3)**2)
        result = gaps.analyze_window(window([track('a',range(10,16),fn),track('b',range(21,27),fn)]),self.cfg)
        self.assertEqual(result['gapRoutes'],[])
        self.assertTrue(result['fallbackRequired'])

    def test_stationary_wrong_view_one_sided_and_long_gap_reject(self):
        before = track('a',range(10,16),self.flight)
        for after in [track('b',range(21,27),self.flight,view=1),
                      track('b',range(21,23),self.flight),
                      track('b',range(46,52),self.flight),
                      track('b',range(21,27),lambda t:(130,500),stationary=True)]:
            with self.subTest(after=after):
                self.assertEqual(gaps.analyze_window(window([before,after]),self.cfg)['gapRoutes'],[])

    def test_spatially_unrelated_tracks_not_joined(self):
        shifted = lambda t:(self.flight(t)[0]+200,self.flight(t)[1])
        result = gaps.analyze_window(window([track('a',range(10,16),self.flight),track('b',range(21,27),shifted)]),self.cfg)
        self.assertEqual(result['gapRoutes'],[])

    def test_competing_pairs_retained_without_identity_choice(self):
        result = gaps.analyze_window(window([track('a',range(10,16),self.flight),
            track('b',range(21,27),self.flight),track('c',range(21,27),self.flight)]),self.cfg)
        self.assertEqual(len(result['gapRoutes']),2)
        self.assertTrue(all(len(r['competingRouteIds'])==1 for r in result['gapRoutes']))
        self.assertEqual(len(result['reviewCards']),1)
        self.assertEqual(len(result['reviewCards'][0]['memberIds']),2)
        self.assertIsNone(result['reviewCards'][0]['semanticEventCount'])

    def test_overlapping_collision_cards_preserve_member_ids(self):
        result = gaps.analyze_window(window([],candidates=[{'seconds':'1/3'},{'seconds':'1/3'}]),self.cfg)
        self.assertEqual(result['originalCandidateCount'],2)
        self.assertEqual(result['reviewCards'][0]['memberIds'],['collision-0000','collision-0001'])
        self.assertFalse(result['fallbackRequired'])

    def test_invalid_parameters_fail(self):
        for cfg in [{'maxGapSeconds':float('nan')},{'minEndpointObservations':2},
                    {'maxSmoothRatio':1.2},{'unexpected':1}]:
            with self.assertRaises(ValueError):
                gaps.config(cfg)


if __name__ == '__main__':
    unittest.main()
