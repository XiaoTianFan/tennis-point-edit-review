# Reproducible fictional demonstration

`build_mock.py` generates a fictional six-game, 4:2 short set and annotated
point/shot/serve events. It calls the same score audit, aggregation and template
assembly helpers used by the skill. Synthetic evidence labels are explicitly
marked as fixtures; no video or physical measurement is implied.

`build.cjs` compiles the actual JSX with esbuild and renders it with React.
A fixed preview frame provides the small animation-hook shim needed for a still;
this is not a replacement for testing animation in the target editor.
The preview container grows to fit dense rows and sublabels, then scales uniformly
into a 1920 x 1080 artboard. The seven stored JSX files remain unchanged.

`capture.cjs` starts a loopback server, uses Playwright CLI to inspect the gallery,
checks that text stays inside its component bounds, and writes PNGs.

Run `npm ci`, then `npm run demo:capture`.
Browser working files live under ignored output/playwright; final README images
live under docs/images. Do not include real player names, footage or measurements.
Use a regular Node.js runtime for Playwright's browser process. The capture script
uses npm's Node executable; PLAYWRIGHT_NODE_PATH can override it in embedded shells.
