"""Boundary regression tests using fictional serve events."""
import unittest
from serve_overlay import build_plan

def record(**changes):
    r=dict(setNumber=1,pointId='P001',serveId='S001',serveNumber=2,eventType='serve',contactVerified=True,confirmedPostContactUs=12000000,
           launchSpeedKphEstimate=74.4,method='endpoint_drag_model',statsIncluded=True,
           clip=dict(startFrame=100,durationFrames=240,sourceInUs=10000000,playbackRate=1))
    r.update(changes);return r

class Checks(unittest.TestCase):
    def test_exact_contact_frame_is_excluded_and_long_rally_caps_at_three_seconds(self):
        p=build_plan([record()],30)[0]
        self.assertEqual((p['startFrame'],p['endFrame']),(161,251))
    def test_short_clip_and_next_attempt_cap(self):
        r=record();r['clip']['durationFrames']=75
        self.assertEqual(build_plan([r],30)[0]['endFrame'],175)
        r['nextServeStartFrame']=167
        self.assertEqual(build_plan([r],30)[0]['durationFrames'],6)
    def test_variable_fps_and_playback_rate(self):
        r=record();r['clip']['playbackRate']=2
        p=build_plan([r],'30000/1001')[0]
        self.assertEqual(p['startFrame'],130);self.assertEqual(p['durationFrames'],89)
        self.assertLessEqual(p['durationFrames']/(30000/1001),3)
    def test_let_is_distinct_does_not_change_statistics(self):
        a=record(serveId='S001-let',eventType='let',statsIncluded=False)
        b=record(serveId='S001-retry')
        out=build_plan([a,b],30)
        self.assertFalse(out[0]['statsIncluded']);self.assertTrue(out[1]['statsIncluded'])
        with self.assertRaises(ValueError):build_plan([a,a],30)
    def test_unverified_toss_and_missing_evidence_rejected(self):
        for changes in [dict(contactVerified=False),dict(eventType='toss_catch'),dict(confirmedPostContactUs=9000000),dict(launchSpeedKphEstimate=float('nan'))]:
            with self.assertRaises(ValueError):build_plan([record(**changes)],30)
    def test_imputation_explicit_no_upper_bound_used(self):
        r=record(method='model_imputed',imputationBasis='same set/player/type',intervalKph=[50,100])
        p=build_plan([r],30)[0];self.assertEqual((p['qualifier'],p['speed']),('补估','74'))
        r.pop('imputationBasis')
        with self.assertRaises(ValueError):build_plan([r],30)
    def test_point_ends_before_first_renderable_frame(self):
        with self.assertRaises(ValueError):build_plan([record(pointEndFrame=161)],30)

    def test_label_shows_before_serve_but_both_exit_together(self):
        p=build_plan([record()],30)[0]
        self.assertEqual(p['labelStartFrame'],100)
        self.assertLess(p['labelStartFrame'],p['startFrame'])
        self.assertEqual(p['labelEndFrame'],p['endFrame'])
        self.assertEqual(p['labelStates'],[dict(startFrame=100,endFrame=251,label='二发')])

    def test_double_fault_not_preannounced_and_does_not_restart_timer(self):
        p=build_plan([record(doubleFaultConfirmedUs=13000000)],30)[0]
        self.assertEqual(p['labelStates'],[dict(startFrame=100,endFrame=191,label='二发'),dict(startFrame=191,endFrame=251,label='二发 · 双误')])
        self.assertEqual(p['durationFrames'],90)

    def test_late_fault_cannot_resurrect_expired_overlay(self):
        p=build_plan([record(doubleFaultConfirmedUs=16000000)],30)[0]
        self.assertTrue(p['outcomeAfterOverlayWindow']);self.assertEqual(len(p['labelStates']),1)
        for changes in [dict(serveNumber=1,doubleFaultConfirmedUs=13000000),dict(doubleFaultConfirmedUs=11000000)]:
            with self.assertRaises(ValueError):build_plan([record(**changes)],30)

if __name__=='__main__':unittest.main()


