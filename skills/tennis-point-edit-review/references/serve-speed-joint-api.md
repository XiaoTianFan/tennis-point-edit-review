# Joint reconstruction API and adapter contract

Read the [pipeline](serve-speed-pipeline.md) and [uncertainty policy](serve-speed-uncertainty.md) first. These helpers extend endpoint and partial-flight APIs; they do not replace source review. NumPy/SciPy are required for fitting (`requirements-speed.txt`); quality, uncertainty summaries and overlay planning use the standard library.

## Responsibilities

| Module | Implements | Caller supplies |
|---|---|---|
| `trajectory_measurements` | Fractional capture clock, native-row correction, covariance whitening, forward/backward RK45, integrated path metrics | Immutable native PTS, justified gaps/readout, reviewed sensor rows/covariances and first-collision duration |
| `joint_trajectory` | Conditional joint candidate, full reference score, callable/matrix projection | Reviewed tracks, independent camera, priors/bounds and events |
| `joint_speed_quality` | Explicit quality policy, comparable-objective support, candidate-bound acceptance | Executed starts/holdouts/variants, native visual checks and result references |
| `trajectory_uncertainty` | Paired accounting, failure/boundary gates, scenario quantiles/envelope, display rounding | Whole-camera/trajectory refits, distributions, scenarios, retained draw records |
| `serve_overlay` | Existing frame-safe timing plus optional range metadata | Editor composition of the range row and visual/media QA |

No CLI runs automatic video-to-speed inference. Task adapters still decode sources, calibrate/register cameras, review ball candidates, sample camera fits, check the net profile and render in the chosen editor. Persist their versions and inputs/outputs. A camera callable must reject behind-camera points; preserve its code and numeric parameters in the task manifest. Matrix mode assumes already-undistorted pixels. Do not silently discard distortion or registration uncertainty.

## Fit inputs

`fit_joint(observations, camera, *, clock, contact_sensor_row, contact_bracket, collision, initial_parameters, bounds, evidence_id, priors=(), drag=.020, lift_vector=(0,0,0), toss_drag=.020, max_evaluations=400)` returns a **candidate with `qualityAccepted=False`**. Aerodynamic defaults are initial assumptions, not a universal uncertainty distribution.

World coordinates are metres, z up; velocities m/s; coefficients 1/m. Camera and observed centroids use the same image coordinates. `CaptureClock(source_seconds, omitted_intervals=(), readout_seconds=0., frame_height=None)` accepts ordered native PTS converted to seconds. Optional gaps are `{beforeFrame, seconds, basis}`; fractional frames interpolate actual PTS with continuous gap additions. `frame_height` and every sensor row refer to the unwarped source. Keep original PTS for rendering; the capture clock is inference-only.

`observations` contains `toss` and `air`, optionally `post`. Each group has ordered unique `frames`, pixel `xy` pairs, original `sensorRows`, and positive-definite 2×2 `covariances`. Solver minima are three toss, six air and three post points—**numerical minima, not quality thresholds**. A justified policy usually requires more evidence and span. Toss precedes the entire contact bracket; air lies strictly between contact/collision brackets; post follows the collision bracket. Corrected row times must also remain ordered. Occluded/inferred positions do not enter these arrays.

`contact_bracket=[lowerFrame,upperFrame]` is reviewed on native frames. `collision` contains:

- `kind`: `first_bounce` or `first_net_impact`; `verified=true` and `basis` describe actual source review.
- `frameBracket`: nonzero-width source bracket strictly after contact; `sensorRow`: the collision's native row, with uncertainty handled by perturbation.
- `axis`, `valueMetres`, `sigmaMetres`: world-coordinate collision plane and positive residual scale. Court bounce requires axis 2 and positive ball-centre height (radius). Net contact uses a horizontal axis and documented ball-radius/contact-side convention. First net contact cannot have a `post` group.

| Parameter indices | Meaning |
|---|---|
| 0–2 | Shared contact x, y, z |
| 3–5 | Outgoing initial vx, vy, vz |
| 6–8 | Incoming toss velocity at contact |
| 9, 10 | Fractional contact and first-collision source frames |
| 11–12, optional | Local rebound image velocity x/y, pixels/s |
| 13–14, optional | Rebound x/y quadratic coefficients, pixels/s² (coefficient of t², not acceleration) |

Use 11 parameters without `post`, 15 with it, with matching finite bounds. Initial values are strictly interior; event bounds stay inside reviewed brackets. Priors are `{index,mean,sigma,basis}`, with positive sigma in matching units and independent support. Another serve's estimated speed is not a contact-geometry prior. `evidence_id` identifies the frozen source/input/model revision. Geometry/aerodynamics remain conditional per fit; adapters rerun fits across assumptions.

The objective is ordinary weighted least squares over whitened toss/air/post pixels plus collision-plane and prior residuals. Review erroneous observations before fitting. Output contains full-precision launch/path metrics, predicted pixels, residual block sums, parameters/physics, convergence/boundary flags and a `candidateId` fingerprint. This binds numerical state and evidence version; it cannot prove visual inspection occurred.

## Diagnostics and acceptance

1. Execute multiple velocity starts and at least two real held-out fits. Fit training groups, project unused observations with `predict_joint`, and report `heldOutRmsPixels` in native-scale image coordinates. Training RMS is not held-out error. Save the actual result references.
2. Execute justified low/high variants in `timing`, `geometry`, `drag`, `lift`, `centroid`, `depth`, `readout`. They must change relevant inputs, not repeat the same run. Retain failed attempts. No-lift and clear-observation subsets are useful additional diagnostics, not substitutes for missing families.
3. `score_joint(parameters, frozen_observations, camera, objective_id=..., priors=frozen_priors, **prediction_options)` evaluates a candidate on a frozen full objective. Prediction options are `clock`, `contact_sensor_row`, `collision`, `drag`, `lift_vector`, `toss_drag`. Retain each candidate's physical/camera hypothesis but keep reference data, weights, event constraints and priors fixed. The shared objective ID describes those reference inputs; do not put unlike subset training costs under it.
4. Call `assess_joint_quality(candidate, holdouts=..., multistarts=..., variants=..., visual_checks=..., policy=...)`. Diagnostics have speed, `converged`, `fitAtParameterBoundary`, `rmsPixels`, `resultRef`; holdouts also have `heldOutRmsPixels`. Variants additionally have `family`, `side`, `basis`, `referenceScore={objectiveId,sumSquares}`. Numerical failures may have null speed but require `failureReason` and a retained `resultRef`; the quality report rejects the candidate while retaining the attempt. Do not invent a finite speed. Resolve failed diagnostics before adopting the centre.
5. Truthfully supply all `VISUAL_CHECKS` exported by `joint_speed_quality`, including independent camera/depth, registration, source clock, first collision and net clearance. Predeclare policy `basis`, `minAirObservations`, `minSpanSeconds`, `maxRmsPixels`, `maxHeldOutRmsPixels`, `maxHeldOutSpeedFraction`, `maxMultistartSpeedFraction`, `maxSupportedWidthFraction`, `maxReferenceCostIncrease`. These are source-specific engineering screens, not accuracy guarantees.
6. Only on acceptance, attach the report as `jointQuality` and copy its `accepted` to `qualityAccepted`. Preserve all diagnostics and supported/stress references. Overlay, aggregation and imputation-support consumers reject unaccepted joint candidates; a changed numerical state/evidence version invalidates the fingerprint. Range acceptance is separate.

Modern final-N/A audits set `methodologyVersion='joint-v1'` and resolve A/B/C route decisions. Missing toss/collision evidence may make C inapplicable, but retain the actual reason. Old A/B audits remain readable; new work must not use that compatibility to skip an applicable joint route. `pending` remains distinct from final N/A.

## Uncertainty and display

The adapter performs actual whole-camera and trajectory refits. Each summary draw is `{scenario, drawId, converged, launchSpeedKphEstimate, boundaryParameters}`. Failures may have null speed but require `failureReason`; converged draws explicitly list active boundary names, or `[]`. All scenarios account for the same paired IDs, including failures. `scenarios` maps IDs to rationale.

`summarize_uncertainty(central, draws, estimate_id=..., scenarios=..., policy=..., supported_variants=...)` requires policy `quantiles=[lower,upper]`, `minConvergedPerScenario`, `maxFailureFraction`, `maxBoundaryFraction`, `seed`, `assumptions`, `basis`. Failure fraction uses all attempts; boundary fraction uses converged draws. Supported alternatives supply `supported=true`, `resultRef`, `supportBasis`, speed, mapped from the actual quality report. The helper does not independently rerun that screening. An `accepted=false` result must not reach labels.

Attach an accepted summary as `modelUncertainty`. Bind `estimate_id` to the joint `candidateId`, or a unique versioned `estimateId` on an A/B record. A matching scalar speed alone cannot transfer an interval between serves or revisions. Use `display_values(launchSpeedKphEstimate, modelUncertainty, estimate_id=...)` for **both CSV display columns and video**; keep unrounded quantities separately. `serve_overlay.build_plan(..., show_uncertainty=True)` / CLI JSON `showUncertainty=true` adds `uncertaintyRangeKph`, `uncertaintyLabel`, `uncertaintyText`. Default is false. Centre and window stay identical; N/A has no range. Missing/rejected ranges fail when requested, and group imputation cannot receive an individual model range.

The seven canonical JSX files are unchanged. An editor adapter must compose the additional requested text below the speed, using established styling, safe margins and the same interval. Metadata is not proof that an editor rendered the row. Full-length speed-only tasks retain every original frame/cut and audio; never remap render/audio time through `CaptureClock`.

## Reproduction

From the skill root:

```sh
python -m pip install -r scripts/requirements-speed.txt
python scripts/build_joint_case.py /path/to/task-workspace/joint-synthetic-check.json
cd scripts
python -m unittest check_joint_trajectory check_trajectory_uncertainty
```

The [computed synthetic example](../examples/serve-speed-joint-case.json) uses independent analytic zero-drag motion and a fictional pinhole camera. The helper solves it, including two-axis rebound curvature. It remains an unaccepted candidate: numerical recovery is not native-video validation. Tests cover opposite directions, net termination, timing continuity, event readout, covariance, full path integration, rejection gates, accounting, range rounding and overlay boundaries. No real match media/identities or inferred real-world precision belong in this package.

Use a new file in the current task workspace; the helper refuses to overwrite. Regenerating the distributed example is a separate, explicitly authorized package-maintenance action: generate a new result, compare it, then deliberately replace the example and refresh the package archive. Ordinary match execution does not authorize changes to the installed skill.
