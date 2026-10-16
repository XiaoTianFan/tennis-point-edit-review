# Rendered edits: reconstruct clip seams

A supplied edited render is an existing edit. Reconstruct its boundaries and
preserve every frame and original audio; do not recut it using inferred dead-ball
times. Detection proposes edit seams, never tennis points or winners. Continuous
raw matches still use visual point cutting.

## Scan and reconstruct

Needs Python 3.10+, NumPy, opencv-python, FFmpeg/scdet and ffprobe. Missing CV
modules stop the scan rather than falling back silently. Source is read-only;
each scan/plan uses new task-workspace paths. Replace identities and paths:

```sh
python "<skill>/scripts/seam_detect.py" scan "<render>" "<work>/scan"
python "<skill>/scripts/local_editor.py" media "<render>" "<work>/proxy.mp4"
python "<skill>/scripts/seam_detect.py" plan "<work>/scan/scan.json" "<work>/proxy.media.json" "<work>/plan.json" --decisions "<work>/scan/decisions.json" --players "<work>/players.json" --language en
```

players is the current two id/name pairs; anonymous placeholders are only for
explicit anonymous preparation. Plans reference one media asset, not re-encoded
clips. Local init/serve opens it; use existing [host adapters](editing-environments.md)
for ChatCut or [Premiere exchange](premiere-pro.md). JSON alone is not a verified
host import. Keep the requested editor. Before outcome recognition prepare
[initial labeling](initial-labeling.md), using --provisional-points until grouping
is verified; candidates are not valid statistical denominators. Apply the
[retained-attempts and input checks](inputs-and-rules.md#核实当前输入).

## Detector and evidence

Two full sequential decodes inspect every display frame: RGB/scdet, then local
tiles, temporal prediction innovation and bidirectional
[DIS optical-flow](https://docs.opencv.org/4.x/de/d4f/classcv_1_1DISOpticalFlow.html)
residuals. Local changes are not diluted by the static court; flow tests how much
ordinary movement explains. Local metrics cover all frames, flow runs on local
anomalies. Sensitive candidates remain for inspection, including consecutive
hits; no minimum duration, keyframe rounding or merging removes a potential cut.

--settings overrides width, sceneThreshold, differenceFloor, adaptiveRatio,
madMultiplier, windowFrames. Defaults are starting values, not calibrated accuracy
claims. Source hash, detector/configuration, FFmpeg/OpenCV/NumPy versions fence
scan identity; reruns retain prior decisions. scan.json appears only after full
decoding and source rehashing; partial output or zero candidates is not proof of
complete seam recovery. Zero hits yields one full-length provisional clip.

Metrics/PTS: metrics.txt contains each frame's RGB/scene scores; cv-metrics.csv
contains local difference/innovation/residual; timestamps.json stores display PTS
in integer microseconds. runtime.json records performance, decode logs retain
errors. Metrics coverage is separate from visual-review coverage.

Frame N is the first frame of the next clip, zero-based/half-open. sourceMapping
retains original frames and PTS; CFR proxy boundaries use nearest integer frames
with proxyBoundaryErrorUs. Collapsed boundaries fail. VFR proxy frames are not
original measurements; keep original PTS for speed. A render cannot restore
material previously removed or altered in speed.

## Review boundaries before calling them points

Inspect before/at frames, neighboring motion and non-hit spans using
[source inspection](source-inspection.md). Fixed-court small jumps may be missed;
fast motion, flashes, overlays and pans can be false hits. Invisible edits cannot
be recovered reliably. Preserve transition frames and label approximate splits.

Edit sorted unique boundaryFrames in decisions.json to reject/move/add cuts.
Set status=reviewed only after inspection; scanId/sourceSha256 must match. Publish
a new plan; preserve old answers and [lineage](coverage-and-exceptions.md).
Several source clips may share P (fault/let); one clip may contain multiple points
or non-match footage. Group from complete context without changing clip bounds.

## Preserve the supplied edit

Validate master start=0, end=media.frames, each clip end equals the next start,
and summed lengths equal the input frame count. This proves every frame appears
once. Preserve first faults, waits, dead-ball sends and tails. Review temporarily
ripple-hides other points while retaining selected clips whole. Point grouping
and inferred endings are annotations, not permission to shorten the user's edit.

Inspect the complete point through its next source seam before adopting a winner;
never call later hits dead-ball sends just to fit an early ending or final score.
Missing ending evidence remains unknown. Repair a mistaken seam from exact
neighboring frames while preserving the full partition. If the owner excludes
project metadata, read only the named render. Preview live; obey the
[full export gate](local-editor.md#导出与边界).
