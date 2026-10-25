# Sources and dependencies

The repository layout references these projects; their source code was not copied:
- https://github.com/anthropics/skills
- https://github.com/remotion-dev/skills
- https://github.com/vercel-labs/skills
- https://agentskills.io/specification

Development dependencies are installed by the package manager, not vendored:
React / React DOM (MIT), esbuild (MIT), Playwright CLI (Apache-2.0),
NumPy (BSD-3-Clause), SciPy (BSD-3-Clause), OpenCV (Apache-2.0).
Inspect installed packages for their full license notices.

The skill links to ITF, LTA, ATP and physics sources for definitions and methods.
Those external publications and brands are not relicensed by this repository.

Demo court artwork, fictional event data and rendered screenshots are original
repository assets covered by the repository MIT License. No match footage is included.

## Optional vision experiments

The optional vision adapter can explicitly load a user's separately obtained
TennisProject architecture and state dictionaries. No third-party architecture,
weights, recorded footage or dataset is bundled. Those files retain their own
terms; a public download link does not establish redistribution permission.
OpenCV, NumPy, PyAV and optional PyTorch remain external dependencies. Research
references and inspected versions are documented in docs/cv-component-research.md.

