"""Synthetic accounting/acceptance tests; these are not real coverage benchmarks."""
import copy
import unittest
from build_joint_case import synthetic_case, solve_case
from joint_speed_quality import FAMILIES, VISUAL_CHECKS, assess_joint_quality, supported_variant, require_joint_acceptance
from trajectory_uncertainty import summarize_uncertainty, display_values
from serve_overlay import build_plan
from launch_speed import aggregate_serves
from speed_evidence import unavailable_reason


def policy():
    return dict(quantiles=[.025, .975], minConvergedPerScenario=3,
                maxFailureFraction=.25, maxBoundaryFraction=.5, seed=7,
                assumptions=['Synthetic accounting fixture, not a calibrated probability model'],
                basis='Small fixture for summary semantics only')


def draws():
    # Fictional scalar records test summary arithmetic; actual fitted examples
    # are generated separately by build_joint_case, never called measured data.
    return [dict(scenario=scenario, drawId=str(i), converged=True,
                 launchSpeedKphEstimate=value+offset, boundaryParameters=[])
            for scenario, offset in [('nominal', 0), ('readout', 2)]
            for i, value in enumerate([90., 96., 104., 110.])]


def summary():
    return summarize_uncertainty(100., draws(), estimate_id='synthetic-estimate-v1', scenarios={'nominal': 'Synthetic nominal', 'readout': 'Synthetic readout alternative'}, policy=policy())


class Uncertainty(unittest.TestCase):
    def test_scenario_envelope_not_pooled_quantiles_and_outward_rounding(self):
        result = summary()
        self.assertTrue(result['accepted'])
        self.assertEqual(display_values(100., result, estimate_id='synthetic-estimate-v1'), dict(speedKph=100, rangeKph=[90, 112]))
        self.assertAlmostEqual(result['rangeKph'][0], 90.45)
        self.assertAlmostEqual(result['rangeKph'][1], 111.55)
        self.assertEqual(display_values(100.5)['speedKph'], 101)

    def test_failed_and_boundary_draws_stay_in_accounting(self):
        data = draws()
        data[0].update(converged=False, launchSpeedKphEstimate=None, failureReason='Synthetic fit failure')
        data[1]['boundaryParameters'] = ['contact', 'drag']
        result = summarize_uncertainty(100, data, estimate_id='synthetic-estimate-v1', scenarios={'nominal': 'test', 'readout': 'test'}, policy=policy())
        self.assertEqual(result['scenarioSummaries']['nominal']['failed'], 1)
        self.assertEqual(result['scenarioSummaries']['nominal']['boundaryCounts'], {'contact': 1, 'drag': 1})
        # Converged boundary speed remains; it is not silently discarded.
        self.assertAlmostEqual(result['scenarioSummaries']['nominal']['quantileRangeKph'][0], 96.4)
        data[2].update(converged=False, failureReason='another failed fit')
        rejected = summarize_uncertainty(100, data, estimate_id='synthetic-estimate-v1', scenarios={'nominal': 'test', 'readout': 'test'}, policy=policy())
        self.assertFalse(rejected['accepted'])
        with self.assertRaises(ValueError): display_values(100, rejected, estimate_id='synthetic-estimate-v1')

    def test_missing_duplicate_nonfinite_and_unpaired_draws_fail(self):
        for change in ('missing', 'duplicate', 'nan', 'unaccounted_failure'):
            data = draws()
            if change == 'missing': data.pop()
            elif change == 'duplicate': data.append(data[0])
            elif change == 'nan': data[0]['launchSpeedKphEstimate'] = float('nan')
            else: data[0]['converged'] = False
            with self.subTest(change=change), self.assertRaises(ValueError):
                summarize_uncertainty(100, data, estimate_id='synthetic-estimate-v1', scenarios={'nominal': 'test', 'readout': 'test'}, policy=policy())

    def test_only_supported_alternatives_expand_range_and_centre_is_preserved(self):
        variant = dict(supported=True, resultRef='synthetic-fit', supportBasis='Frozen-objective screen', launchSpeedKphEstimate=120.3)
        result = summarize_uncertainty(100, draws(), estimate_id='synthetic-estimate-v1', scenarios={'nominal': 'test', 'readout': 'test'}, policy=policy(), supported_variants=[variant])
        self.assertEqual(display_values(100, result, estimate_id='synthetic-estimate-v1')['rangeKph'], [90, 121])
        variant['supported'] = False
        with self.assertRaises(ValueError):
            summarize_uncertainty(100, draws(), estimate_id='synthetic-estimate-v1', scenarios={'nominal': 'test', 'readout': 'test'}, policy=policy(), supported_variants=[variant])
        with self.assertRaises(ValueError): display_values(99, result, estimate_id='synthetic-estimate-v1')
        result['kind'] = '95_percent_confidence_interval'
        with self.assertRaises(ValueError): display_values(100, result, estimate_id='synthetic-estimate-v1')


class JointAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = solve_case(synthetic_case())

    def inputs(self):
        base = copy.deepcopy(self.candidate)
        diagnostic = dict(launchSpeedKphEstimate=base['launchSpeedKphEstimate'], converged=True,
                          fitAtParameterBoundary=False, rmsPixels=.1, heldOutRmsPixels=.2,
                          referenceScore=base['referenceScore'], basis='Synthetic gate fixture')
        variants = [dict(diagnostic, family=f, side=s, resultRef=f+'-'+s) for f in FAMILIES for s in ('low', 'high')]
        holds = [dict(diagnostic, resultRef='holdout-'+str(i)) for i in range(2)]
        starts = [dict(diagnostic, resultRef='start-'+str(i)) for i in range(2)]
        p = dict(basis='Synthetic gate fixture only', minAirObservations=6, minSpanSeconds=.1,
                 maxRmsPixels=1., maxHeldOutRmsPixels=2., maxHeldOutSpeedFraction=.1,
                 maxMultistartSpeedFraction=.02, maxSupportedWidthFraction=.3, maxReferenceCostIncrease=2.)
        return base, dict(holdouts=holds, multistarts=starts, variants=variants,
                          visual_checks={k: True for k in VISUAL_CHECKS}, policy=p)

    def test_same_air_rms_but_bad_joint_objective_is_stress_not_supported(self):
        base, args = self.inputs()
        alternative = copy.deepcopy(args['variants'][0])
        alternative['referenceScore']['sumSquares'] += 3
        self.assertFalse(supported_variant(alternative, base, args['policy']))
        alternative['referenceScore']['objectiveId'] = 'different-subset'
        with self.assertRaises(ValueError): supported_variant(alternative, base, args['policy'])

    def test_missing_family_review_holdout_or_boundary_prevents_acceptance(self):
        for change in ('family', 'review', 'holdout', 'boundary', 'failed_variant'):
            base, args = self.inputs()
            if change == 'family': args['variants'].pop()
            elif change == 'review': args['visual_checks']['sourceClockReviewed'] = False
            elif change == 'holdout': args['holdouts'][0]['heldOutRmsPixels'] = 4.
            elif change == 'failed_variant': args['variants'][0].update(converged=False, launchSpeedKphEstimate=None, failureReason='Synthetic failed fit')
            else: base['fitAtParameterBoundary'] = True
            with self.subTest(change=change):
                self.assertFalse(assess_joint_quality(base, **args)['accepted'])

    def test_failed_holdout_is_retained_without_fabricating_speed(self):
        base, args = self.inputs()
        args['holdouts'][0].update(converged=False, launchSpeedKphEstimate=None, failureReason='Synthetic numerical failure')
        report = assess_joint_quality(base, **args)
        self.assertFalse(report['accepted'])
        self.assertIn('holdout did not converge', report['reasons'])

    def test_numeric_label_and_statistics_reject_unaccepted_or_changed_candidate(self):
        base, args = self.inputs()
        record = dict(base, setNumber=1, pointId='P-test', serveId='S-test', serverId='A', serveNumber=1,
                      eventType='serve', outcome='in', included=True, statsIncluded=True,
                      contactVerified=True, confirmedPostContactUs=1000000,
                      clip=dict(startFrame=0, durationFrames=120, sourceInUs=0, playbackRate=1))
        for consumer in (lambda r: build_plan([r], 30), lambda r: aggregate_serves([r])):
            with self.assertRaises(ValueError): consumer(record)
        record['jointQuality'] = assess_joint_quality(base, **args)
        record['qualityAccepted'] = record['jointQuality']['accepted']
        self.assertTrue(record['qualityAccepted'])
        self.assertEqual(len(build_plan([record], 30)), 1)
        self.assertEqual(aggregate_serves([record])[0]['count'], 1)
        record['modelUncertainty'] = summarize_uncertainty(record['launchSpeedKphEstimate'], draws(),
            estimate_id=record['candidateId'], scenarios={'nominal': 'test', 'readout': 'test'}, policy=policy())
        self.assertIn('uncertaintyText', build_plan([record], 30, show_uncertainty=True)[0])
        record['launchSpeedKphEstimate'] += 1
        with self.assertRaises(ValueError): require_joint_acceptance(record)

    def test_new_recovery_audit_resolves_joint_route_before_final_na(self):
        audit = {key: dict(status='complete', reason='Synthetic review') for key in ('sourceSearch', 'contactReview', 'geometryReview', 'preImpactExtension')}
        audit['methodologyVersion'] = 'joint-v1'
        audit['methods'] = [dict(method=m, status='unavailable', reason='Synthetic unavailable evidence') for m in ('endpoint_physics', 'partial_trajectory_model')]
        with self.assertRaises(ValueError): unavailable_reason(audit)
        audit['methods'].append(dict(method='joint_trajectory_model', status='not_applicable', reason='Toss not visible in retained source'))
        self.assertIn('Toss not visible', unavailable_reason(audit))


class RangeOverlay(unittest.TestCase):
    def test_optional_second_line_uses_same_centre_and_window(self):
        record = dict(setNumber=1, pointId='P-test', serveId='S-test', serveNumber=1, eventType='serve',
                      method='endpoint_physics', estimateId='synthetic-estimate-v1', launchSpeedKphEstimate=100., modelUncertainty=summary(),
                      contactVerified=True, confirmedPostContactUs=1000000, statsIncluded=True,
                      clip=dict(startFrame=0, durationFrames=120, sourceInUs=0, playbackRate=1))
        plain = build_plan([record], 30, 'en')[0]
        full = build_plan([record], 30, 'en', show_uncertainty=True)[0]
        for key in ('speed', 'startFrame', 'endFrame', 'labelEndFrame'):
            self.assertEqual(plain[key], full[key])
        self.assertNotIn('uncertaintyText', plain)
        self.assertEqual(full['uncertaintyText'], '90–112 km/h')
        self.assertEqual(full['uncertaintyLabel'], 'Model uncertainty')
        record['estimateId'] = 'another-serve-with-the-same-speed'
        with self.assertRaisesRegex(ValueError, 'different serve or estimate revision'):
            build_plan([record], 30, show_uncertainty=True)
        record['estimateId'] = 'synthetic-estimate-v1'
        record.pop('modelUncertainty')
        with self.assertRaises(ValueError): build_plan([record], 30, show_uncertainty=True)


if __name__ == '__main__':
    unittest.main()
