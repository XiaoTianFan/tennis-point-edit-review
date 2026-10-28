"""Summarize paired conditional refits; no fabricated posterior/confidence claim.

Each failed/boundary draw stays in the accounting. Quantiles are scenario-wise,
not a pooled distribution of scenarios with invented probabilities. Standard
library only so overlay/statistics consumers do not acquire SciPy dependencies.
"""
import math
from joint_speed_quality import number


def quantile(values, probability):
    ordered = sorted(values)
    index = (len(ordered)-1)*probability
    lo, hi = math.floor(index), math.ceil(index)
    return ordered[lo] + (ordered[hi]-ordered[lo])*(index-lo)


def summarize_uncertainty(central, draws, *, estimate_id, scenarios, policy, supported_variants=()):
    """scenarios maps IDs to rationale. Draw = scenario/drawId/converged/speed/bounds.

    Failed draws need failureReason and may have null speed. Finite converged
    boundary draws remain in quantiles and are counted. Policy must predeclare
    acceptance fractions, quantiles, minimum draws, seed and model assumptions.
    """
    central = number(central)
    if not isinstance(estimate_id, str) or not estimate_id:
        raise ValueError('Versioned adopted-estimate identity required')
    if central <= 0 or not scenarios or any(not key or not basis for key, basis in scenarios.items()):
        raise ValueError('Positive centre and justified scenarios required')
    qlo, qhi = map(number, policy['quantiles'])
    failure_limit = number(policy['maxFailureFraction'])
    boundary_limit = number(policy['maxBoundaryFraction'])
    minimum = policy['minConvergedPerScenario']
    if not 0 < qlo < qhi < 1 or type(minimum) is not int or minimum < 2 or not 0 <= failure_limit <= 1 or not 0 <= boundary_limit <= 1:
        raise ValueError('Valid declared quantiles, counts and attrition limits required')
    if not policy.get('basis') or not policy.get('assumptions') or type(policy.get('seed')) is not int:
        raise ValueError('Predeclared rationale, model assumptions and reproducible seed required')
    groups = {key: [] for key in scenarios}
    seen = set()
    for draw in draws:
        key = (draw['scenario'], draw['drawId'])
        if key[0] not in groups or not isinstance(key[1], str) or not key[1] or key in seen:
            raise ValueError('Unique identified draw in a declared scenario required')
        seen.add(key)
        if type(draw.get('converged')) is not bool:
            raise ValueError('Every draw needs explicit convergence status')
        if draw['converged']:
            if number(draw['launchSpeedKphEstimate']) <= 0 or not isinstance(draw.get('boundaryParameters'), list):
                raise ValueError('Converged draw needs positive speed and explicit boundary list')
            if any(not isinstance(p, str) or not p for p in draw['boundaryParameters']):
                raise ValueError('Boundary parameter names required')
        elif not draw.get('failureReason'):
            raise ValueError('Failed draws must remain with a reason')
        groups[key[0]].append(draw)
    # Reuse random draws across scenarios; no silent lost IDs after a failed fit.
    identities = [{d['drawId'] for d in group} for group in groups.values()]
    if not identities[0] or any(ids != identities[0] for ids in identities[1:]):
        raise ValueError('All scenarios must account for the same paired draw IDs')
    summaries = {}
    reasons = []
    envelope = [central]
    for name, group in groups.items():
        good = [d for d in group if d['converged']]
        failed = len(group)-len(good)
        bounded = sum(bool(d['boundaryParameters']) for d in good)
        if len(good) < minimum or failed/len(group) > failure_limit or bounded/max(len(good), 1) > boundary_limit:
            reasons.append(name+': insufficient stable refits under declared attrition policy')
        values = [d['launchSpeedKphEstimate'] for d in good]
        interval = [quantile(values, qlo), quantile(values, qhi)] if values else None
        if interval:
            envelope.extend(interval)
        counts = {}
        for draw in good:
            for parameter in set(draw['boundaryParameters']):
                counts[parameter] = counts.get(parameter, 0)+1
        summaries[name] = dict(total=len(group), converged=len(good), failed=failed,
                               boundaryDraws=bounded, boundaryCounts=counts, quantileRangeKph=interval)
    for variant in supported_variants:
        if variant.get('supported') is not True or not variant.get('resultRef') or not variant.get('supportBasis'):
            raise ValueError('Only independently screened, referenced alternatives may expand display range')
        speed = number(variant['launchSpeedKphEstimate'])
        if speed <= 0:
            raise ValueError('Positive supported alternative speed required')
        envelope.append(speed)
    interval = [min(envelope), max(envelope)]
    return dict(schema='serve-model-uncertainty/v1', kind='conditional_model_range',
                estimateId=estimate_id, accepted=not reasons, reasons=reasons, centralKph=central, rangeKph=interval,
                scenarios=scenarios, scenarioSummaries=summaries, policy=policy,
                supportedResultRefs=[v['resultRef'] for v in supported_variants],
                interpretation='Conditional model range, not a calibrated confidence interval; unmodeled error can exceed it.')


def display_values(speed, uncertainty=None, *, estimate_id=None):
    """One rounding path for CSV and video; bounds outward, centre half-up once."""
    speed = number(speed)
    if speed <= 0:
        raise ValueError('Positive accepted launch speed required')
    result = dict(speedKph=math.floor(speed+.5))
    if uncertainty is None:
        return result
    if not estimate_id or uncertainty.get('estimateId') != estimate_id:
        raise ValueError('Uncertainty belongs to a different serve or estimate revision')
    if uncertainty.get('schema') != 'serve-model-uncertainty/v1' or uncertainty.get('kind') != 'conditional_model_range' or uncertainty.get('accepted') is not True or uncertainty.get('reasons') != []:
        raise ValueError('Only accepted conditional model ranges may be displayed')
    lo, hi = map(number, uncertainty['rangeKph'])
    if number(uncertainty['centralKph']) != speed or not 0 < lo <= speed <= hi:
        raise ValueError('Uncertainty range must belong to and enclose the adopted centre')
    result['rangeKph'] = [math.floor(lo), math.ceil(hi)]
    return result
