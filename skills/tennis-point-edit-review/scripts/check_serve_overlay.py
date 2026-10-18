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
        with self.assertRaises(ValueError):build_plan([r],30)
        p=build_plan([r],30,allow_imputed=True)[0];self.assertEqual((p['qualifier'],p['speed']),('补估','74'))
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

    def unavailable(self):
        audit={k:dict(status='complete',reason='Synthetic source review') for k in ('sourceSearch','contactReview','geometryReview','preImpactExtension')}
        audit['methods']=[dict(method='endpoint_physics',status='unavailable',reason='First collision is occluded'),
                          dict(method='partial_trajectory_model',status='rejected',reason='Sensitivity too wide',attempted=True,resultRef='synthetic-result')]
        return record(method='unestimated',launchSpeedKphEstimate=None,included=False,unavailableAudit=audit)

    def test_na_preserves_label_window_and_excludes_numeric_speed(self):
        from launch_speed import aggregate_serves
        r=self.unavailable();p=build_plan([r],30)[0]
        self.assertEqual((p['qualifier'],p['speed'],p['unit']),('','N/A',''))
        self.assertFalse(p['speedAvailable']);self.assertEqual(p['endFrame'],p['labelEndFrame'])
        self.assertEqual(aggregate_serves([r]),[])
        r['included']=True
        with self.assertRaises(ValueError):build_plan([r],30)

    def test_untried_or_accepted_route_cannot_be_labelled_na(self):
        for status in ('pending','accepted'):
            r=self.unavailable();r['unavailableAudit']['methods'][0]['status']=status
            with self.assertRaises(ValueError):build_plan([r],30)
        r=self.unavailable();r['unavailableAudit']['methods'][1].pop('resultRef')
        with self.assertRaises(ValueError):build_plan([r],30)

    def test_native_frame_guard_survives_fractional_microsecond_rounding(self):
        from fractions import Fraction
        fps=Fraction(60000,1001)
        for frame in range(102,130):
            r=record(confirmedPostContactUs=round(Fraction(frame)/fps*1000000),confirmedPostContactSourceFrame=frame)
            r['clip'].update(sourceInUs=round(Fraction(100)/fps*1000000),sourceInFrame=100,sourceFps=str(fps))
            self.assertEqual(build_plan([r],str(fps))[0]['startFrame'],100+frame-100+1)
        r['clip'].pop('sourceFps')
        with self.assertRaises(ValueError):build_plan([r],str(fps))

if __name__=='__main__':unittest.main()


