# Rendering and evidence implementation

The local renderer decodes identity-bound originals. A sequential FFmpeg process
composites at most ten seconds into raw YUV frames; bounded PCM is decoded before
that process starts. PyAV owns one persistent H.264 encoder and one AAC encoder.
No media intermediate is written. The muxer's movie clock uses the audio sample
rate so MP4 edit-list durations do not round the final audio length to milliseconds.

Timeline and output frame rates remain rational. Source grid normalization occurs
before cutting; output-rate selection occurs across the complete edit, not once
per clip. Audio boundaries use cumulative rounded sample positions. Internal
chunks do not introduce fades, padding, or encoder priming. Final sample count
follows the actual output-frame duration; a fractional-frame tail is trimmed or
padded with silence.

`sourceMapping` includes the container start, grid origin and original time base.
FFmpeg input seeking is relative to the container start while `copyts` retains
absolute PTS for the filters. New proxies start at zero. Legacy binding accepts
current bytes explicitly and checks the old source metadata and zero-origin proxy;
it cannot establish historical identity or repair ambiguous bounded-proxy cuts.

Run `python -m unittest tools.test_local_editor tools.test_original_export` for
actual media exports, overlay intervals/fades, dimensions/FPS, holds, original
identity failures, nonzero source clocks, chunk equivalence and many-cut audio.
`python tools/validate.py` checks the complete package and repository contracts.
Render and evidence dependencies are reported by `local_editor.py doctor`.
