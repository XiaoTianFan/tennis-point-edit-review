# Rendered edits: reconstruct clip seams

Use this branch when the user supplies an edited, rendered file without an
accessible clip timeline. Preserve that edit and its audio. A raw continuous
match still uses visual point cutting; this detector does not locate tennis
points in unedited footage or infer winners, serves, games or statistics.

## Scan and reconstruct

Requires Python 3.10+, FFmpeg with `scdet`, and ffprobe. Run in the task workspace,
never the skill directory. Each scan uses a new output directory; source is read
only. Replace paths and player identities with this task's values.

```sh
python "<skill>/scripts/seam_detect.py" scan "<rendered-video>" "<work>/seams-v1"
python "<skill>/scripts/local_editor.py" media "<rendered-video>" "<work>/rendered-proxy.mp4"
python "<skill>/scripts/seam_detect.py" plan "<work>/seams-v1/scan.json" "<work>/rendered-proxy.media.json" "<work>/rough-plan.json" --decisions "<work>/seams-v1/decisions.json" --players "<work>/players.json" --language en
```

`players.json` is an array of the current two `id/name` pairs. Omit only for
explicitly anonymous preparation; generated Player A/B labels are placeholders.
The plan contains editable references to the single rendered media asset, not
separate lossy re-encodes. `local_editor.py init/serve` can play its reconstructed
clips; the same source mapping can feed the existing [editing adapters](editing-environments.md).
For Premiere, translate the plan to the existing [exchange contract](premiere-pro.md),
verify CFR timing and import/read back in Pr. For ChatCut, use available host tools
to place the mapped ranges and read them back. A JSON plan alone is not an
imported or verified host timeline. Do not switch the user's requested editor.

Before any outcome recognition, run the [initial labeling preparer](initial-labeling.md)
on the generated plan. If grouping is unverified, use `--provisional-points` to
expose candidate segments immediately; manual users can note needed merges/splits.
Agent-dominant remains the default. Human-first hands over this surface and waits.
Do not describe a rough partition as completed stage-1 point cutting.

## Detector and evidence

One full sequential decode spatially reduces each frame to RGB at width 320; **no frames
are skipped in time**. FFmpeg's [scdet](https://ffmpeg.org/ffmpeg-filters.html#scdet)
provides scene score and mean absolute frame difference. A candidate is emitted
when scene score reaches 8, or RGB difference reaches the maximum of 0.5, three times
the preceding 30-frame median, and median plus six median absolute deviations.
This second signal can expose small jumps in a stable court view. All defaults
are starting values, not real-match calibrated accuracy claims. No minimum clip
duration, nearest-keyframe rounding, flash removal or adjacent-hit merging is
applied. Consecutive hits are flagged for inspection.

`--settings settings.json` overrides the named `width`, `sceneThreshold`,
`differenceFloor`, `adaptiveRatio`, `madMultiplier`, `windowFrames` settings.
Record the detector revision, settings and FFmpeg build; rerun into a new directory when changing
them. Identical detector/bytes/settings/build yield the same scan identity and candidates.
`scan.json` is written only after successful full decoding and source rehashing;
a partial folder or empty hit list does not establish a successful scan.

Outputs: `metrics.txt` contains every frame's scores; `timestamps.json` contains
the decoded display-order PTS expressed as integer microseconds; `scan.json`
records source SHA-256, configuration, build, timing assessment and candidates;
`runtime.json` records elapsed scan time; `decode.log` retains errors.
Zero candidates produces one full-length rough clip, with boundaries still
unverified. Metrics coverage is not visual-review coverage.

Frame coordinates are zero-based and half open. A seam at frame N means frame N
starts the next clip; all frames from 0 through the source end are covered once.
Original display frames and PTS survive in `sourceMapping`. A CFR review proxy
maps seams to its nearest integer frame and records `proxyBoundaryErrorUs`; VFR
proxy frames are not original frames. Collapsed seams fail rather than disappear.
Keep the original for precise evidence and use the existing PTS rules for speed.
This does not restore the camera originals or material removed before rendering.

## Review boundaries before calling them points

Inspect candidate neighborhoods with [source inspection](source-inspection.md),
including the frame before/at each seam and enough continuous context on both
sides. Inspect non-hit ranges as well: same-court near-identical cuts, gradual
transitions and small edits can be missed. Camera pans, lighting flashes,
scoreboard changes and movement can produce false hits. Invisible edits cannot
be inferred reliably from pixels. Transitions may span several frames and have
no single original cut; preserve the transition footage and record the chosen
split as an approximation. Do not silently trim it away.

Edit `decisions.json`'s sorted `boundaryFrames` to reject, move or add cuts, then
set `status: "reviewed"` only after actual inspection. `scanId` and
`sourceSha256` fence decisions to that exact scan. Generate a **new** plan after
corrections; never overwrite a published review or its drafts. Preserve full
coverage and original audio until explicit exclusions are justified.

An accepted seam is an edit boundary, not proof of a new scoring point. Several
clips may belong to one point (first/second serve, let, replay); a clip may contain
multiple points or non-match material. Group or split from actual context and
retain lineage before adopting stable P numbers. No score or statistics are
invented from clip count. Missing first serves, endings or original speed remain
missing evidence. Qualification on the user's real footage is a separate gate.
