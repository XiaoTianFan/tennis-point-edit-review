# Conditional model uncertainty / 条件模型不确定范围

The aim is an honest per-serve range supported by the source and stated model, not a requested ±2, ±3 or ±5 km/h precision. A higher confidence level normally requires a **wider** interval within a fixed statistical model. A narrower interval needs better evidence or stronger justified assumptions; it does not establish higher confidence by itself.

## Keep three quantities separate

1. **Adopted central launch estimate**: one accepted individual reconstruction. Retain full precision internally; display a rounded integer, explicitly estimated.
2. **Broad sensitivity/stress envelope**: results from deliberately extreme timing, depth, camera or aerodynamic scenarios. Its endpoints need not be jointly plausible or equally supported; it is not a probability interval.
3. **Conditional model range**: an envelope of scenario-wise refit quantiles and supported deterministic alternatives, with its assumptions and attrition disclosed. This may be narrower than the stress envelope because it uses a stated support model, not because inconvenient results were deleted.

Do not relabel 2.5–97.5 percentile endpoints as a validated 95% confidence interval. Measurement-noise draws and chosen priors/scenarios are not automatically a calibrated sampling distribution or Bayesian posterior. Single-camera model discrepancy, unknown image processing, wind, ball condition and uncertain capture timing may lie outside the range. No radar or independent multi-view benchmark means no demonstrated absolute-error guarantee.

## Build the ensemble

- Freeze a versioned source/evidence/model record and a policy **before looking for a desirable range**: distributions and correlations, scenario rationale, seeds, sample counts, support thresholds, accepted failure/boundary fractions and minimum converged counts. Changes after diagnostics need an explicit reason and a new revision.
- Perturb independent court/net control measurements and their shared localization biases; refit the **entire camera** per draw, retaining coupled focal/pose/distortion/principal/aspect parameters. Do not perturb each fitted camera parameter independently as if their errors were unrelated. Keep shared calibration draws aligned across serves in the same camera segment; a camera error does not shrink by counting more serves.
- Perturb ball centroids with per-observation covariance plus group-level biases, registration uncertainty, depth-prior means and justified aerodynamic prior means. Distinguish random perturbation distributions from deterministic alternative model families. Avoid double-counting a calibration error as independent ball jitter without a reason.
- Refit all contact, toss, outgoing and collision/local-rebound nuisance parameters for every draw. Do not just add noise to a previously estimated speed. Reuse paired draw IDs across timing/readout scenarios so differences are interpretable. The nominal source clock and each additional capture/readout hypothesis must come from this recording's evidence.
- Record every attempted draw, convergence, nonfinite failure reason, parameter boundary names and net/event consistency. Finite converged boundary draws remain in quantiles and boundary counts; their concentration may reveal truncation by a prior rather than precision. If the declared failure/boundary policy fails, investigate/widen defensible inputs/recollect evidence or withhold the interval. Never silently summarize only convenient survivors.
- Ensure held-out predictions, first-collision ordering and net clearance remain physically compatible. A draw contradicting the reviewed event is a failed/incompatible draw with a recorded reason, not an omitted record. No post-net or post-bounce data may lengthen the outgoing flight.

No universal number of draws guarantees tail accuracy. Report draws per scenario, not just the total. With small samples the tails are coarse; compare additional batches/seeds and disclose Monte Carlo variation when it materially changes displayed bounds. Seeds enable reproduction, not certainty.

## Support and range construction

Evaluate deterministic alternatives on the **same frozen full joint objective**: common observed data, covariance weights, collision constraints, prior terms and loss/scaling. Fit with perturbed assumptions if needed, then score predicted toss/flight/event/rebound against that common reference. Keep airborne RMS as a diagnostic, not the sole acceptance criterion. Different observation subsets, holdouts or changed residual definitions need predictive comparisons; their raw training costs are not comparable.

`joint_speed_quality.supported_variant` requires a referenced executed fit, convergence, interior parameters, a shared `referenceScore.objectiveId`, an image-residual screen and a predeclared maximum increase in reference sum of squares. This is a conditional engineering support policy, not an automatic chi-square confidence test. The cost allowance must be justified per objective; there is deliberately **no universal cost allowance of 9** or universal ±one-frame readout range. Failed diagnostics require investigation; merely rejected but converged stress alternatives stay in the audit with reasons and may still reveal structural uncertainty that the stated model omits.

For each accepted scenario compute the declared lower/upper quantiles of its full refit speeds. Take the envelope of those limits, the adopted central value and all supported deterministic alternatives. Do not pool scenarios into a single distribution unless their probabilities are independently justified. Store unrounded limits; round the lower bound down and upper bound up for display. Include the central estimate even if it lies outside the sampled quantiles. Keep stress limits in a separate field, never silently substitute them for the conditional interval.

`trajectory_uncertainty.summarize_uncertainty` implements paired draw accounting, scenario quantiles, failure/boundary gates and this envelope. It is a **summary helper**, not a camera sampler or inference engine; its inputs must come from actual retained refits. `display_values` is the single centre/range rounding path for CSV and labels. The summary and consumer must share the adopted estimate identity (joint `candidateId`, or versioned A/B `estimateId`); equal speeds alone do not make ranges interchangeable between serves. Its `conditional_model_range` schema cannot be supplied as an unlabelled generic confidence interval.

## Display and explanation

Use two lines when requested: estimated launch speed, then `Model uncertainty: low–high km/h` (Chinese: `模型不确定范围`). Both share the same start/end frames. A speed-only version hides the range and retains exactly the same central estimate and frame window. Final audited N/A stays unitless and has no invented interval. Imputed group speeds cannot acquire an individual model range through this interface.

If the CSV has different numbers, name their quantities explicitly: unrounded versus displayed launch speed, horizontal average, 3D path average, pre-collision speed, broad sensitivity endpoints and conditional range endpoints. Do not expect readers to infer which one is printed. The adoption record links the integer display back to its full-precision centre and evidence revision.

Improving accuracy means acquiring a better timing/contact bracket, a longer sharp pre-impact track, independently constrained camera/depth, useful toss or collision evidence, better sensor metadata, or independent radar/multi-view validation. Increasing optimizer iterations or the number of Monte Carlo draws reduces numerical/sampling error only; it cannot remove a wrong geometry or missing physical effect. Report independent validation bias, absolute error and rejection/coverage on held-out serves when such ground truth becomes available.
