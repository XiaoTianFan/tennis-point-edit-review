# Serve-speed reconstruction architecture / 发球估速流水线

Use with [method selection](serve-speed-model.md), [evidence recovery](serve-speed-audit.md), [joint API](serve-speed-joint-api.md), [uncertainty](serve-speed-uncertainty.md) and [overlay timing](serve-speed-overlay.md). This is a reusable methodology, not a promise that every video supports a speed or a narrow range. Preserve existing event, review and scoring semantics.

## Scope and method routing

For a **speed-only pass**, preserve the full input: all frames, cuts, waits, faults, net contacts, lets and original audio. Extract analysis clips with exact source-frame/PTS mappings first; these are views of the source, not a new edited master. A net touch is physical evidence; a legal let is a separately established outcome. Statistics still follow the existing legal-serve-only convention unless the user requests another explicit scope.

| Route | Appropriate evidence | Result and limitation |
|---|---|---|
| A: endpoint inverse physics | Reviewed contact and first bounce/net impact, metric endpoint geometry and event brackets | Conditional initial velocity; sparse evidence makes geometry/timing/drag assumptions influential |
| B: partial 3D flight | Calibrated camera, independent contact depth, enough verified pre-impact observations | Conditional initial state; a safe truncation is not a measured collision or full flight |
| C: joint toss/contact/flight/first collision | Useful toss track and outgoing observations, independently calibrated camera, bracketed first collision; optional nearby rebound observations | Shared 3D contact/time, full pre-collision path; stronger constraints only when supported by the source |

C extends the physical reconstruction; it does not license bypassing A/B review or force an unavailable toss into the fit. Prefer the richest *supported* route. Evaluate simpler and no-lift alternatives as diagnostics, not independent speed votes. Shared inputs make estimates correlated, so never average routes as if they were separate measurements. If two plausible solutions fit equally well but give materially different speeds, retain the ambiguity, widen the range or withhold the estimate. Do not choose the solution nearest an expected player speed.

## Data boundaries and provenance

Keep these independently versioned records in the task workspace; invalidate dependent fits/labels when an upstream version changes:

| Layer | Required content | Must not do |
|---|---|---|
| Source manifest | Source checksum, dimensions, decoded frame count, integer PTS/time base, audio origin, cuts, playback/capture assumptions | Replace source identity with a proxy or reconstructed clock |
| Attempt ledger | Unique serve ID, point/set/server/opportunity, contact/outgoing brackets, first-collision kind/bracket, physical net touch versus legal outcome | Turn practice swings, re-tosses or duplicate camera views into serves |
| Geometry | Coordinate convention, independent court/net controls, camera model/parameters, priors, registration transforms and held-out residuals | Calibrate the camera to achieve a desired ball speed |
| Observations | Authoritative reviewed native frame, centroid, sensor row, covariance, group/identity, visibility, review/exclusion reason | Count interpolation, occlusion or detector predictions as observed ball positions |
| Fit and checks | Input/code version, bounds/priors, objective blocks, all starts/holdouts/variants, convergence/boundaries, source review | Treat numerical success or small pixel RMS as speed validation |
| Ensemble | Full camera and trajectory refits, paired draw IDs/seeds/scenarios, failures and boundary counts, support/attrition policies | Silently discard extreme or failed fits to narrow the range |
| Adopted result | Single full-precision centre, named speed/path quantities, conditional range and separate stress envelope, acceptance report | Substitute an upper bound, flight average or group mean for launch speed |
| Render and QA | Same result revision, rounded display values, source-to-output frame map, boundary frames, decoded audio/video checks | Move labels using inferred capture time or silently drop faults/lets |

## Two clocks, event brackets and sensor readout

**Source clock** is the decoded PTS timeline used for clips, audio and labels. **Capture clock** is a documented physical-time hypothesis. CFR output alone does not prove real-time capture. Inspect duplicate/omitted exposures, speed changes and cadence using independent source evidence; never infer time compression merely because the resulting speed seems low. VFR uses actual PTS, not a nominal FPS substitution. State the real-time assumption if capture metadata cannot resolve it.

Do not carry a dropped-frame pattern, FPS, contact phase or rolling-readout value from a different recording. If a missing duration `d` is independently supported between frames `j-1` and `j`, interpolate its addition continuously as `d * clip(f-j+1, 0, 1)` for fractional frame `f`. Subtract the corrected contact time. A step function at `j` creates a false discontinuity in event fitting. Do not add a missing duration already represented by PTS. Record alternative timing hypotheses rather than deciding from the desired speed.

Use the same rolling-readout correction for toss points, outgoing points **and collision-event time**:

`elapsed(f,y) = captureTime(f) - captureTime(contactFrame) + readoutSeconds * (y-contactSensorRow)/sensorHeight`.

Rows are in the original unwarped sensor image, not stabilized or cropped display coordinates. Record image orientation and readout sign. Positive/negative scenarios are sensitivity assumptions when metadata is unavailable, not measured shutter properties. Do not automatically use ±one frame for every camera. Bound fractional contact/collision parameters within reviewed source brackets and check corrected temporal ordering for every scenario.

## Independent geometry and observation uncertainty

1. Split at actual camera/crop changes. For small movements, estimate static-background registration per frame, exclude players/ball/score graphics, retain inlier counts and residuals, and inspect held-out features. A background homography is a registration approximation; translating cameras, depth parallax or rolling deformation may require time-varying camera calibration instead.
2. Fit court-line **centres**, stable court intersections and noncoplanar net/post/strap controls. Check nominal court/net dimensions, visible reference quality and line contamination. Record intrinsics, pose, radial distortion, principal point and any aspect correction. Do not freely fit all intrinsics from an ambiguous plane. A court homography maps ground points only; it cannot locate an airborne ball in 3D.
3. Compare defensible camera models (e.g. pinhole versus radial, constrained principal/aspect alternatives), inspect reprojection and held-out controls, and use independent baseline/contact-depth information. A toss offers gravity information but does not remove every scale/depth ambiguity. Far-server views can especially need depth evidence.
4. Detect *candidates* using positive, negative or absolute local contrast as appropriate: bright ball on dark court, dark ball on bright ceiling, early blurred streak. Review native temporal ROIs; exclude roof seams, rackets, bodies, net/receiver overlap and static old balls. A convenient detector threshold is not a visibility verdict.
5. Store a positive-definite 2×2 centroid covariance in the coordinate system being fitted. Give blurred/elongated images anisotropic uncertainty, a justified localization floor, and group-level correlated biases. If points are registered, transform covariance using the local image-transform Jacobian and include registration uncertainty. Keep original sensor rows separately. Independent per-frame noise cannot represent shared calibration or registration error.

## Joint physical model and first collision

At racket contact, the toss and outgoing flight share one position `p0` and one contact time. Their velocities differ across the impact. Fit the incoming toss over its observed short segment under gravity and stated drag; integrate backwards from contact when convenient. Fit outgoing motion using:

`p' = v; v' = (0,0,-g) - k |v| v + |v| (L × v)`.

`k` has units 1/m; `L` is an effective lift vector, **not measured RPM**. No wind and constant coefficients are assumptions. Keep aerodynamics constrained by defensible priors or fixed per candidate and refit across alternatives; a single camera rarely identifies every camera, depth, contact time, drag and lift unknown at once. Check directions in the chosen world coordinates; both near-to-far and far-to-near serves must work without a hard-coded velocity sign. Do not arbitrarily discount a model speed to mimic radar.

Whiten each pixel residual by its covariance Cholesky factor. Keep separate residual blocks for toss, outgoing flight, collision, rebound localization and metric priors. Record objective scaling/loss definitions. Bad observations should prompt source review; a robust loss is not permission to hide systematic residuals. The portable fitter uses ordinary weighted least squares after review so full-objective comparisons remain explicit.

For a first court bounce, constrain the **ball centre** at ball radius above the court, not z=0 by accident. A few post-bounce points may localize the collision through a separate quadratic **image curve in both x and y**, anchored at the projected collision point. Perspective can curve the horizontal image coordinate, particularly for an approaching ball. Do not force a straight x curve, identify its coefficients as physical bounce/spin parameters, include distant rebound/return strokes, or extend the outgoing flight through the bounce. Compare alternative local rebound models/window lengths when evidence is weak.

For first net contact, terminate the flight there. Use a reviewed net contact constraint with ball-radius/contact-plane convention and uncertainty; do not infer the original speed from post-net flight or a later bounce. For a supposed clean serve, inspect the trajectory at net crossing against the **local net-height profile**, ball radius and calibration uncertainty. Test both directions, central fit and ensemble. A model crossing below the net before the nominated bounce contradicts the event hypothesis; revisit it rather than claiming a clean serve. Modeled clearance alone does not prove what was visually observed or establish a legal let.

## What distance and speed mean

For a complete fitted flight ending at the first collision time `T`:

| Field | Definition | Interpretation |
|---|---|---|
| `launchSpeedKphEstimate` | `3.6 * norm(v0)` | Adopted launch estimate, before appreciable in-flight slowing |
| `horizontalDistanceMetres` | Norm of horizontal endpoint displacement | Ground-plane chord diagnostic, not airborne path length |
| `horizontalMeanFlightKph` | `3.6 * horizontalDistance / T` | Sanity check; not a second independent estimate or launch speed |
| `modeledArcLengthMetres` | Integral from 0 to T of `norm(v(t)) dt` | Full curved 3D **modeled** path length |
| `modeledPathMeanKph` | `3.6 * modeledArcLength / T` | Full-path average; generally distinct from launch speed |
| `preCollisionSpeedKph` | `3.6 * norm(v(T-))` | Speed immediately before the first collision |

The reconstruction and initial velocity are fitted together. It is not necessary to first measure an independent arc length then divide by time to estimate launch speed. Integrating the accepted trajectory produces that path length consistently; dividing it by flight time gives an **average**, not the initial speed. The extra 3D length alone does not account for aerodynamic slowing. Do not claim the path is faithfully observed at every 3D location: single-view reconstruction remains conditional on geometry, timing, physical priors and visibility. A partial route may report only its modeled window, explicitly named, not an invented full contact-to-bounce distance.

## Validation and execution boundaries

Run multiple initial velocities; interleaved-frame holdouts and, when feasible, contiguous held-out windows; alternative camera models; low/high contact timing, readout, metric depth, drag, lift and correlated centroid/registration perturbations; and removal of ambiguous early streaks. Keep the same source scope. Assess full joint residuals, physical bounds, geometry and held-out predictions together. Interleaved holdouts share camera and correlated noise and are not independent speed ground truth. Equal-quality alternative speeds reveal weak identifiability.

Predeclare acceptance/support thresholds with a source-specific rationale. Existing route-B screening stays intact; route C has a separate explicit policy, not relaxed B checks under another method name. `joint_speed_quality.py` binds acceptance to the numerical candidate and evidence version. Any changed candidate must be re-screened. The uncertainty report is a separate gate: an acceptable centre does not automatically justify a display range.

Use [scenario-wise paired refits](serve-speed-uncertainty.md) for uncertainty. Keep possible but poorly supported extremes as stress tests. A fixed cost increase used in one experiment is not a universal statistical threshold; evaluate alternative parameters on a common frozen full objective. Do not compare a held-out/subset fit's training cost with the full-data cost.

The portable code implements conditional fitting, clock correction, covariance weighting, integrated path metrics, quality/uncertainty contracts and overlay-plan metadata. It does **not** automatically discover serves, establish capture cadence, calibrate/register cameras, review ball identities, sample whole-camera refits, check the net profile or render the additional uncertainty row in every editor. Those remain explicit task adapters and reviewed diagnostics. No unavailable stage may be reported as executed. See [API responsibilities](serve-speed-joint-api.md).

Numerical acceleration is optional. Before replacing the reference integrator with compiled RK4 or another backend, compare positions, velocities, arc length, both directions, negative toss times, repeated/mixed times and event roots against an independent high-accuracy solver, then halve the step size. Retain tolerances and worst errors. Faster fitting must not change uncertainty semantics; do not ship task-specific compiled binaries.

For full-length speed-only delivery, verify decoded source/output frame counts, PTS order, all cuts, first/last frames, aspect/color/orientation and every label's before/first/last/after frames. Preserve audio without a reconstructed-clock remap; use stream copy when compatible, compare decoded PCM exactly when unchanged, or quantify alignment/sample count/waveform differences if re-encoded. Equal duration alone does not prove frame or audio preservation. Keep all labels, CSV and summary on the same adopted result revision; hiding uncertainty changes presentation only.
