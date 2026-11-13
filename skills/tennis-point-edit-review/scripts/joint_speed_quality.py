"""Explicit conditional acceptance contract for joint trajectory candidates.

Policy thresholds are recording-specific screening choices, not accuracy or
confidence guarantees. The caller executes and retains every diagnostic fit.
"""
import hashlib
import json
import math

FAMILIES = ('timing', 'geometry', 'drag', 'lift', 'centroid', 'depth', 'readout')
VISUAL_CHECKS = ('ballIdentityVerified', 'contactBracketVerified', 'firstCollisionVerified',
                 'preImpactSegmentVerified', 'cameraCalibrationReviewed', 'registrationReviewed',
                 'metricDepthConstraintReviewed', 'sourceClockReviewed', 'netClearanceReviewed')


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Finite numeric value required')
    return float(value)


def candidate_fingerprint(candidate):
    fields = ('parameters', 'physics', 'launchSpeedKphEstimate', 'flightSeconds', 'evidenceId')
    content = {key: candidate[key] for key in fields}
    return hashlib.sha256(json.dumps(content, sort_keys=True, allow_nan=False).encode()).hexdigest()


def supported_variant(variant, base, policy):
    """Compare FULL common-reference residual, not air RMS or unlike objectives.

    referenceScore is evaluated against the same frozen evidence, weights and
    priors even when the fitting observations/priors differ. Holdouts instead
    use predictive scores and must not be admitted through this function.
    """
    if not variant.get('basis') or not variant.get('resultRef'):
        raise ValueError('Retain variant rationale and executed result reference')
    if variant.get('converged') is not True or variant.get('fitAtParameterBoundary') is not False:
        return False
    score, original = variant.get('referenceScore', {}), base.get('referenceScore', {})
    if not original.get('objectiveId') or score.get('objectiveId') != original['objectiveId']:
        raise ValueError('Full joint scores require the SAME frozen objective identity')
    rms, cost, base_cost = number(variant['rmsPixels']), number(score['sumSquares']), number(original['sumSquares'])
    if min(rms, cost, base_cost) < 0:
        raise ValueError('Residual scores cannot be negative')
    return rms <= number(policy['maxRmsPixels']) and cost <= base_cost + number(policy['maxReferenceCostIncrease'])


def assess_joint_quality(candidate, *, holdouts, multistarts, variants, visual_checks, policy):
    """Return a bound report; does not mutate/approve candidate in place.

    Explicit thresholds and all required families prevent a joint method name
    from bypassing evidence/stability gates. See API reference for diagnostics.
    """
    keys = ('minAirObservations', 'minSpanSeconds', 'maxRmsPixels', 'maxHeldOutRmsPixels',
            'maxHeldOutSpeedFraction', 'maxMultistartSpeedFraction', 'maxSupportedWidthFraction',
            'maxReferenceCostIncrease')
    if not policy.get('basis') or any(number(policy[k]) <= 0 for k in keys):
        raise ValueError('Predeclared positive recording-specific policy and rationale required')
    speed = number(candidate['launchSpeedKphEstimate'])
    if speed <= 0 or candidate.get('candidateId') != candidate_fingerprint(candidate):
        raise ValueError('Positive, identity-bound joint candidate required')
    reasons = ['missing '+key for key in VISUAL_CHECKS if visual_checks.get(key) is not True]
    if candidate.get('converged') is not True or candidate.get('fitAtParameterBoundary') is not False:
        reasons.append('base fit failed or reached parameter boundary')
    if number(candidate['observationCount']) < policy['minAirObservations'] or number(candidate['spanSeconds']) < policy['minSpanSeconds']:
        reasons.append('insufficient pre-impact observations/span')
    if not 0 <= number(candidate['rmsPixels']) <= policy['maxRmsPixels']:
        reasons.append('base reprojection residual too large')
    for name, fits, threshold, score_key in (
            ('holdout', holdouts, policy['maxHeldOutSpeedFraction'], 'heldOutRmsPixels'),
            ('multistart', multistarts, policy['maxMultistartSpeedFraction'], 'rmsPixels')):
        if len(fits) < 2 or len({r.get('resultRef') for r in fits}) < 2:
            reasons.append('missing distinct '+name+' fits')
        for fit in fits:
            if not fit.get('resultRef'):
                raise ValueError('Every diagnostic attempt needs a retained result reference')
            if fit.get('converged') is not True:
                if not fit.get('failureReason'):
                    raise ValueError('Failed diagnostic needs an explicit failure reason')
                reasons.append(name+' did not converge')
                continue
            if fit.get('fitAtParameterBoundary') is not False:
                reasons.append(name+' failed or reached parameter boundary')
            if abs(number(fit['launchSpeedKphEstimate'])/speed-1) > threshold:
                reasons.append('unstable '+name+' speed')
            max_rms = policy['maxHeldOutRmsPixels'] if name == 'holdout' else policy['maxRmsPixels']
            if not 0 <= number(fit[score_key]) <= max_rms:
                reasons.append(name+' prediction residual too large')
    required = {(family, side) for family in FAMILIES for side in ('low', 'high')}
    if not required <= {(v.get('family'), v.get('side')) for v in variants}:
        reasons.append('missing low/high diagnostic families')
    supported, stress = [], []
    for variant in variants:
        if not variant.get('basis') or not variant.get('resultRef'):
            raise ValueError('Every variant needs a rationale and retained result reference')
        if variant.get('converged') is not True:
            if not variant.get('failureReason'):
                raise ValueError('Failed variant needs an explicit failure reason')
            reasons.append('failed diagnostic fit needs investigation')
            stress.append(variant)
            continue
        value = number(variant['launchSpeedKphEstimate'])
        if value <= 0:
            raise ValueError('Positive variant speed required')
        (supported if supported_variant(variant, candidate, policy) else stress).append(variant)
    values = [speed] + [v['launchSpeedKphEstimate'] for v in supported]
    if (max(values)-min(values))/speed > policy['maxSupportedWidthFraction']:
        reasons.append('supported alternatives too wide for declared policy')
    return dict(schema='joint-speed-quality/v1', candidateId=candidate['candidateId'],
                accepted=not reasons, reasons=list(dict.fromkeys(reasons)), policy=policy,
                visualChecks=visual_checks,
                supportedResultRefs=[v['resultRef'] for v in supported],
                stressResultRefs=[v['resultRef'] for v in stress],
                supportedRangeKph=[min(values), max(values)],
                interpretation='Conditional screening only; not calibrated absolute speed accuracy.')


def require_joint_acceptance(record):
    if record.get('method') != 'joint_trajectory_model':
        return
    report = record.get('jointQuality', {})
    if record.get('qualityAccepted') is not True or report.get('schema') != 'joint-speed-quality/v1' or report.get('accepted') is not True or report.get('reasons') != []:
        raise ValueError('Joint candidate must pass full evidence/stability screening')
    identity = candidate_fingerprint(record)
    if record.get('candidateId') != identity or report.get('candidateId') != identity:
        raise ValueError('Joint acceptance belongs to a different candidate/evidence version')
