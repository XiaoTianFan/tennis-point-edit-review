"""Synthetic regressions: collision timing, misses, fallbacks, and quality failures."""
import copy,math,unittest
from serve_event_audit import audit_attempts
from speed_evidence import estimate_endpoint,impute_same_group,assess_partial_quality
from launch_speed import reconstruct,aggregate_serves
from serve_overlay import build_plan

def evidence():
    def p(v,lo,hi):return {'value':v,'range':[lo,hi],'basis':'Explicit synthetic assumption'}
    return {'eventType':'let','ballIdentityVerified':True,'crossesEarlierCollision':False,
        'contact':{'kind':'racket_contact','estimateSeconds':10.,'bracketSeconds':[9.99,10.01],'verified':True,'note':'Synthetic adjacent-frame bracket'},
        'endpoint':{'kind':'first_net_impact','estimateSeconds':10.70,'bracketSeconds':[10.69,10.71],'verified':True,'note':'Synthetic first-impact bracket'},
        'horizontalDistanceMetres':p(12.,11.,13.),'contactHeightMetres':p(2.7,2.45,2.95),
        'endpointHeightMetres':p(.94,.89,.99),'dragPerM':p(.02,.012,.028),'liftPerM':p(0.,-.004,.004)}

def speed_record(key='s1',speed=90,**kw):
    r=dict(setNumber=1,serveId=key,serverId='A',serveNumber=1,eventType='serve',included=True,
           method='endpoint_physics',launchSpeedKphEstimate=speed,contactVerified=True,
           ballIdentityVerified=True,flightSegmentVerified=True)
    r.update(kw);return r

class EventChecks(unittest.TestCase):
    def test_let_keeps_second_serve(self):
        r=audit_attempts([dict(eventId='a',kind='serve',outcome='fault'),dict(eventId='b',kind='serve',outcome='let'),dict(eventId='c',kind='serve',outcome='in')])
        self.assertEqual([x['serveNumber'] for x in r],[1,2,2]);self.assertFalse(r[1]['countsAsServeOpportunity'])
    def test_abandoned_toss_vs_attempted_miss(self):
        r=audit_attempts([dict(eventId='t',kind='toss_catch'),dict(eventId='m',kind='serve_miss'),dict(eventId='s',kind='serve',outcome='in')])
        self.assertEqual([x['serveNumber'] for x in r],[1,1,2]);self.assertFalse(r[0]['serviceFault'])
        self.assertTrue(r[1]['serviceFault']);self.assertFalse(r[1]['speedApplicable']);self.assertIsNone(r[1]['launchSpeedKphEstimate'])
    def test_second_swing_miss_is_double_fault_without_speed(self):
        r=audit_attempts([dict(eventId='m',kind='serve_miss')],2)[0]
        self.assertTrue(r['doubleFault']);self.assertTrue(r['serviceSequenceEnded']);self.assertFalse(r['included'])
    def test_point_end_and_duplicate_rejected(self):
        with self.assertRaises(ValueError):audit_attempts([dict(eventId='a',kind='serve',outcome='in'),dict(eventId='b',kind='toss_catch')])
        with self.assertRaises(ValueError):audit_attempts([dict(eventId='a',kind='toss_catch')]*2)
    def test_miss_cannot_leak_into_speed_denominator(self):
        r=speed_record(eventType='serve_miss',launchSpeedKphEstimate=None)
        with self.assertRaises(ValueError):aggregate_serves([r])
        r['included']=False
        self.assertEqual(aggregate_serves([r,speed_record()])[0]['count'],1)
    def test_let_scope_must_be_explicit(self):
        r=speed_record(eventType='let')
        with self.assertRaises(ValueError):aggregate_serves([r])
        r['includeLetsInSpeedScope']=True;self.assertEqual(aggregate_serves([r])[0]['count'],1)
    def test_unaccepted_partial_cannot_leak_into_statistics(self):
        r=speed_record(method='partial_trajectory_model',qualityAccepted=False)
        with self.assertRaises(ValueError):aggregate_serves([r])
        r['qualityAccepted']=True
        self.assertEqual(aggregate_serves([r])[0]['count'],1)

class EndpointChecks(unittest.TestCase):
    def test_corrected_time_changes_speed_without_an_arbitrary_cap(self):
        r=estimate_endpoint(evidence());bad=reconstruct(12.,.4,2.7,.94)
        self.assertLess(r['launchSpeedKphEstimate'],bad['launchSpeedKphEstimate']*.7)
        self.assertGreater(r['launchSpeedKphEstimate'],r['horizontalMeanFlightKph'])
        self.assertLess(r['sensitivityRangeKph'][0],r['launchSpeedKphEstimate'])
        self.assertGreater(r['sensitivityRangeKph'][1],r['launchSpeedKphEstimate'])
    def test_net_height_projection_is_not_collision_evidence(self):
        e=evidence();e['endpoint']['estimateSeconds']=10.4
        with self.assertRaises(ValueError):estimate_endpoint(e)
        e=evidence();e['endpoint']['verified']=False
        with self.assertRaises(ValueError):estimate_endpoint(e)
    def test_let_cannot_use_post_net_bounce(self):
        e=evidence();e['endpoint']['kind']='first_bounce'
        with self.assertRaises(ValueError):estimate_endpoint(e)
    def test_unknown_or_prior_collision_rejected(self):
        for value in (True,None):
            e=evidence();e['crossesEarlierCollision']=value
            with self.assertRaises(ValueError):estimate_endpoint(e)
    def test_nonfinite_inputs_and_reversed_brackets(self):
        for v in (float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):reconstruct(v,.5,2.7)
        e=evidence();e['contact']['bracketSeconds']=[10.1,9.9]
        with self.assertRaises(ValueError):estimate_endpoint(e)

class FallbackChecks(unittest.TestCase):
    def test_only_independent_same_group_contacts_support_imputation(self):
        target=speed_record('target');pool=[speed_record('a',80),speed_record('b',100),speed_record('foreign',200,serverId='B'),speed_record('let',200,eventType='let',included=False),speed_record('imputed',200,method='model_imputed'),speed_record('other-set',200,setNumber=2)]
        r=impute_same_group(target,pool)
        self.assertEqual(r['launchSpeedKphEstimate'],90);self.assertEqual(r['imputationBasis']['supportServeIds'],['a','b'])
    def test_missing_support_or_missed_contact_never_fabricated(self):
        with self.assertRaises(ValueError):impute_same_group(speed_record('t'),[])
        with self.assertRaises(ValueError):impute_same_group(speed_record('t',eventType='serve_miss'),[speed_record()])
    def test_partial_candidate_requires_acceptance(self):
        with self.assertRaises(ValueError):impute_same_group(speed_record('t'),[speed_record(method='partial_trajectory_model')])
        r=impute_same_group(speed_record('t'),[speed_record(method='partial_trajectory_model',qualityAccepted=True)])
        self.assertEqual(r['launchSpeedKphEstimate'],90)

class QualityChecks(unittest.TestCase):
    def base(self):
        c=dict(launchSpeedKphEstimate=100,observationCount=20,spanSeconds=.3,rmsPixels=1.,fitAtParameterBoundary=False,converged=True)
        h=[dict(launchSpeedKphEstimate=100,heldOutRmsPixels=1.,fitAtParameterBoundary=False,converged=True) for _ in range(2)]
        variants=[dict(launchSpeedKphEstimate=v,family=f,side=s,fitAtParameterBoundary=False,converged=True) for f in ('timing','geometry','drag','lift') for s,v in [('low',95),('high',105)]]
        visual={k:True for k in ('ballIdentityVerified','contactBracketVerified','preImpactSegmentVerified','cameraCalibrationReviewed','metricDepthConstraintReviewed','initialStateStabilityReviewed')}
        return c,h,variants,visual
    def test_stable_candidate_can_pass(self):self.assertTrue(assess_partial_quality(*self.base())['accepted'])
    def test_one_sided_sensitivity_or_unreviewed_depth_cannot_pass(self):
        c,h,v,w=self.base()
        self.assertFalse(assess_partial_quality(c,h,v[::2],w)['accepted'])
        w['metricDepthConstraintReviewed']=False
        self.assertFalse(assess_partial_quality(c,h,v,w)['accepted'])
    def test_synthetic_case_is_computed_and_explicitly_not_a_benchmark(self):
        from build_speed_case import build
        case=build()
        self.assertTrue(case['synthetic'])
        self.assertEqual(case['corrected'],estimate_endpoint(case['input']))
    def test_tiny_residual_does_not_override_bound_or_missing_visual_evidence(self):
        c,h,v,w=self.base();c.update(rmsPixels=.001,fitAtParameterBoundary=True)
        self.assertFalse(assess_partial_quality(c,h,v,w)['accepted'])
        c['fitAtParameterBoundary']=False;w['ballIdentityVerified']=False
        self.assertFalse(assess_partial_quality(c,h,v,w)['accepted'])
    def test_unstable_geometry_and_failed_holdout_rejected(self):
        c,h,v,w=self.base();v[1]['launchSpeedKphEstimate']=170
        self.assertFalse(assess_partial_quality(c,h,v,w)['accepted'])
        c,h,v,w=self.base();h[0]['heldOutRmsPixels']=9
        self.assertFalse(assess_partial_quality(c,h,v,w)['accepted'])
    def test_incomplete_sensitivity_and_short_track_rejected(self):
        c,h,v,w=self.base();c['observationCount']=8
        self.assertFalse(assess_partial_quality(c,h,v,w)['accepted'])
        c,h,v,w=self.base();self.assertFalse(assess_partial_quality(c,h,v[:2],w)['accepted'])
    def test_pixel_thresholds_follow_source_resolution(self):
        c,h,v,w=self.base()
        baseline=assess_partial_quality(c,h,v,w)
        c['rmsPixels']*=2
        for item in h:item['heldOutRmsPixels']*=2
        w['frameHeight']=2160
        scaled=assess_partial_quality(c,h,v,w)
        self.assertEqual(scaled['accepted'],baseline['accepted'])
        self.assertEqual(scaled['policy']['maxRmsPixels'],5)

class LetOverlayChecks(unittest.TestCase):
    def record(self,**changes):
        r=dict(setNumber=1,pointId='point',serveId='let',serveNumber=2,eventType='let',contactVerified=True,confirmedPostContactUs=12000000,letConfirmedUs=12700000,launchSpeedKphEstimate=72.,method='endpoint_physics',statsIncluded=False,clip=dict(startFrame=0,durationFrames=240,sourceInUs=10000000,playbackRate=1))
        r.update(changes);return r
    def test_let_label_only_after_confirmation_keeps_timer(self):
        p=build_plan([self.record()],30)[0]
        self.assertEqual(p['labelStates'],[dict(startFrame=0,endFrame=82,label='二发'),dict(startFrame=82,endFrame=151,label='二发 · 擦网')])
        self.assertEqual(p['durationFrames'],90)
    def test_first_serve_let_stays_first_and_late_confirmation_cannot_resurrect(self):
        self.assertEqual(build_plan([self.record(serveNumber=1)],30)[0]['labelStates'][-1]['label'],'一发 · 擦网')
        p=build_plan([self.record(letConfirmedUs=17000000)],30)[0]
        self.assertEqual(len(p['labelStates']),1);self.assertTrue(p['outcomeAfterOverlayWindow'])
    def test_let_cannot_also_be_double_fault(self):
        with self.assertRaises(ValueError):build_plan([self.record(doubleFaultConfirmedUs=13000000)],30)

if __name__=='__main__':unittest.main()
