# Tennis Match Edit

**A reusable agent skill for turning tennis recordings into point-by-point edits,
auditable scoring, and compact match statistics.**

[中文说明](README.zh-CN.md) · [Skill entry](skills/tennis-point-edit-review/SKILL.md) · [Gallery](docs/gallery.md) · [Account sync](docs/synchronization.md)

![Scoreboard, serve speed and note templates with fictional data](docs/images/scoreboard.png)

*Every screenshot uses fictional Player A / Player B data and a generated court
illustration. No match footage, player identities or measured serve speeds are included.*

## What it does

- Cuts individual points while keeping the first dead ball and necessary reactions.
- Separates visual outcome, adopted ruling, rules-based score and onsite notation.
- Creates a compact review timeline and an offline interactive list whose rows stay visible.
- Derives five statistics pages from point and shot events, including FH/BH outcomes,
  independent UE/FE classification, and movement counts **within UE**.
- Estimates launch speed for every included serve, then adds post-contact speed labels.
- Reuses the navy/lime scoreboard, review labels, notes and statistics templates.

The workflow resumes from the current stage and defaults to one stage per turn,
with inspected deliverables, the current/next stage, and a question asking whether to proceed.
An explicit request enables continuous execution; required references and checks
still apply. Stage 1 delivers the complete point-cut timeline and keeps its ledger
as an internal log. Stage 2 performs point adjudication, scoring and basic graphics.
Stages 3–4 repeat review and recalculation as needed. Stage 5 prepares all statistics,
speeds and timing; stage 6 builds panels and speed overlays together; stage 7 verifies
the result. Review covers unresolved points or problem games that still disagree
with the supplied final score after the agent's own checks.

Current skill revision: **2026.10.05-v23.3**. See the [bilingual serve-speed explanation](docs/serve-speed-explained.md) for event timing, collision handling, physics, optional 3D fitting, quality checks and fallbacks.

ChatCut, **Premiere Pro** and a standalone pipeline are primary editing choices.
The [environment contract](skills/tennis-point-edit-review/references/editing-environments.md)
selects an editor separately from its graphics implementation. Premiere has explicit
legacy CEP/ExtendScript and newer UXP routes, with a terminal-only interaction
contract and fresh-machine setup guidance. The agent does not need Computer Use.
The [Premiere guide](skills/tennis-point-edit-review/references/premiere-pro.md)
contains setup and execution instructions; the
[graphics contract](skills/tennis-point-edit-review/references/graphics-adapters.md)
covers editable native graphics and rendered overlays. Default hybrid graphics
combine native editable scores/labels where qualified with rendered statistics.
Available graphics controls depend on the host version and template; the agent
checks these before building the timeline.

The standalone [Courtside workbench](skills/tennis-point-edit-review/references/local-editor.md)
ships inside the skill: a local timeline, source/edited playback, decoded frame stepping,
clip trimming/reordering, overlay timing, point review, revisioned JSON handoff and FFmpeg export.
Agents operate it entirely through the bundled CLI; users review in a browser.

## Preview

![Serve and third-shot panel with derived mock statistics](docs/images/stats-serve.png)

![Rally and shot outcomes with derived mock statistics](docs/images/stats-rally.png)

The default panel has **5 pages, 39 main comparison rows, 8 seconds per page**.
Higher/lower comparison rules choose the highlighted main value; descriptive
distributions stay neutral. See [all five pages](docs/gallery.md).

## Install and use

This repository keeps its independently installable package under
`skills/tennis-point-edit-review/`. From a clone, a compatible Skills CLI can install it:

```sh
npx skills add . --skill tennis-point-edit-review
```

Local-path installation is supported by the [Skills CLI](https://github.com/vercel-labs/skills).
You can also copy the **whole skill folder**, including references, examples and
scripts, into a skill directory supported by your agent.

In ChatCut, ask the connected agent to save/update this folder as your personal
workflow Skill, then select it from **My Skills**. A generic skill installation
does not install ChatCut's editing capabilities: actual editing needs a connected
video editor, media access and visual inspection.

Example request:

> Use the skill at `<skill-folder>/SKILL.md` to edit `<source-video>` in Premiere Pro.

The editor choice is optional. The agent reads the workflow and setup guidance
from the complete skill package, inspects the media and available tools, and
asks only for necessary unresolved information or a required manual setup step.

## Repository layout

```text
skills/tennis-point-edit-review/  Complete portable skill package
  SKILL.md                      Workflow entry and required references
  references/                   Match rules, workflow and editor setup
  examples/                     Seven canonical JSX components and review HTML
  scripts/                      Evidence, scoring, aggregation and checks
                                Optional Premiere interchange, terminal MCP and graphics adapters
demo/                           Reproducible fictional data and screenshot renderer
docs/                           Gallery, publishing and synchronization guides
tools/                          Validation, packaging and conflict-aware snapshot sync
.github/workflows/              Automated validation
```

## Reproduce the demonstrations

Python 3.10+ and Node.js 20+ are used for repository maintenance.

```sh
python -m pip install -r requirements-dev.txt
npm ci
npm run demo:build
npm run demo:capture
python tools/validate.py
npm run check:adapters
```

The renderer compiles the **actual JSX templates**, with a fixed preview frame.
Screenshots are captured by Playwright CLI; no alternate hand-drawn panels are used.
A local browser is required; if none is available, install one using
`npx playwright-cli install-browser chromium`.
Generated working pages are ignored under `output/playwright/`; selected PNGs
are kept under `docs/images/`. See [demo notes](demo/README.md).

## Maintain one source and sync deliberately

Use this Git repository as the durable, reviewable source. The account-saved Skill
is a reusable copy managed by ChatCut, **not a Windows folder that Git can watch**.

You can still update the account first, then ask an agent to retrieve its complete
package, compare it with this repository, merge changes, run checks, and commit.
That is an explicit sync operation, not automatic bidirectional synchronization.
The included helper handles exported files and conflicts; it does not log in to
ChatCut or push to GitHub. See [the synchronization guide](docs/synchronization.md).

## Scope and limits

Designed for singles: regular/short sets, advantage/no-ad, timed play and point
tiebreaks. Doubles requires explicit rule and service-order adaptation.
Scoring and stroke classifications require source evidence; estimated serve
launch speeds are not radar measurements. Unknown observations remain unknown.

## Contributing and license

Read [CONTRIBUTING.md](CONTRIBUTING.md). Code, skill text and original demo assets
are available under the [MIT License](LICENSE). External articles, brands and
installed dependencies retain their own licenses; see [notices](THIRD_PARTY_NOTICES.md).

Repository organization draws on the self-contained skill folders used by
[Anthropic Skills](https://github.com/anthropics/skills) and
[Remotion Skills](https://github.com/remotion-dev/skills). No upstream skill or
template code was copied for this packaging work.
