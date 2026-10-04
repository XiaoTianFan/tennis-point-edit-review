# Stage-based workflow maintenance

Revisions v23–v23.7 clarify agent-owned work, concrete stage delivery, necessary
interactive review, visual adjudication and the distinction between main-cut and review labels.
This is repository maintenance context, not additional match instructions.

The skill entry now groups each stage's work, required reading and completion
checks. Default delivery follows stage checkpoints; when stage 2 needs review,
continue directly through stage 3 and deliver verified review materials before
waiting for user answers. Explicit continuous execution preserves the same checks.
Setup is part of the first substantive stage, and inapplicable stages do not require empty deliverables or approvals.
Existing project notes hold the small progress record; no new state schema or
workflow engine is introduced.

The seven stages deliver: cut timeline → adjudication/scoring/basic graphics →
review ⇄ recalculation → statistics/speed data → panels and speed overlays →
final QA. Stage 1 keeps the ledger internal and does not advance scores; stages
3–4 may repeat; stage 5 supplies all data for the combined graphics stage 6.

v23.6 replaces negative-only caveats with the agent's next action and the relevant
stage/reference. Repeated dead-ball, review-visibility and default instructions
now point to their detailed rules. Evidence distinctions and completion gates
remain; no detection tool or runtime behavior is added.

## Scenario review

These are documentation walk-throughs, not a live-editor or model reliability
benchmark. Use them for a future fresh-agent evaluation without supplying the
expected behavior to that agent.

| Starting request or condition | Expected behavior |
|---|---|
| Raw footage, no execution preference | Stage 1 cuts every point from serve to dead ball with required reactions and places it on a playable timeline. Keep the ledger internal; scoring starts in stage 2. |
| Stage 1 needs serve order or point grouping to cut correctly | Make those event judgments now, save their evidence and reuse/check them in stage 2. Stage boundaries govern delivery, not permission to reason about needed events. |
| Players have stopped, but the ending event is unclear | Trace the same ball backward to the first ending event; locate it from source frames before setting the cut. Stage 2 completes cause/winner adjudication; only gaps remaining after source checks enter review. |
| Suitable source frames already exist | Reuse frames with adequate source/time identity, clarity and density; crop/rearrange them as needed. Extract more only for missing context or detail. |
| Choosing an analysis method | Use agent visual inspection of source context to identify events. Extraction/crops support viewing; detection/tracking only helps investigate a specific uncertainty. Do not build or rely on whole-match automatic boundary detection. Existing calculation and rendering helpers retain their roles. |
| A match-specific helper seems useful | Keep necessary temporary scripts in the task workspace. Match execution does not authorize skill changes; adding a tool to the skill requires an explicit user request and demonstrated utility. |
| Already cut points and a known final score | Check cuts and internal mappings, then reuse the timeline for agent-owned point adjudication, scoring and basic graphics in stage 2. |
| A few clipped endings or uncertain serves | Inspect source gaps and continuous context; adopt clear decisions. Only unresolved material questions and necessary related points enter review. |
| Stage 2 finishes without review needs | Skip stages 3–4, report the result and ask whether to enter the next applicable stage; do not create an empty review file. |
| Review is necessary | Continue from stage 2 directly into stage 3 without a proceed prompt; build, verify and deliver its review sequence and interactive HTML, or the standalone review workspace. A questions list without the required interactive file is incomplete; waiting for answers does not block building it. Every selected row stays visible; unrelated points are not added by default. |
| Scoring still disagrees with the supplied final game/set score after source checks | Include each problem game's points individually, with necessary adjacent evidence. Preserve known answers; repeat stages 3–4 as needed without fabricating a matching score. |
| Statistics and speed data are ready | Stage 6 renders both five-page panels and per-serve speed overlays from stage 5's shared data and timing; neither requires its own stage or fixed rendering order. |
| A long rally, before speed estimation | Serve label starts before service and exits no later than three seconds after the confirmed post-contact display start, or at an earlier boundary. It does not fill the rally. |
| Resume with reviewed answers or completed statistics | Read current state and the affected stage references; preserve IDs, answers and completed work. Recompute dependencies or build the remaining panels/labels as appropriate. |
| “Do everything continuously; ask only when necessary” | Continue across stages with progress reports, required reading and self-checks; genuine unanswered questions block only dependent conclusions. |
| Familiar user, “skip the introduction” or “start directly” | Omit onboarding; do not infer permission to replace default staged delivery with one full pass. |
| A delivery checkpoint is reached, including a review/recalculation repeat | Stage 2 with review needs continues into stage 3; stage 3 requests review answers for stage 4. At other checkpoints name the completed and next applicable stages, report results, and ask whether to proceed. Wait unless continuous execution was explicitly requested; at final delivery, state that the workflow is complete. |
| Any stage has a successful batch or partial artifact, with executable work remaining | Continue that stage without asking to proceed. All seven stages and rework require full scoped coverage, every prescribed deliverable and required checks. Stage 2 includes point outcomes, serves and basic graphics together. An actual interruption remains an incomplete stage, not a new stage. |
| Reporting progress or asking for point review | Use chat and the existing interactive review HTML/sequence. Do not add mock audio, listening samples, demonstrations or separate reports unless requested; internal logs stay internal. |
| Delete or merge points after review | Rebuild consecutive display numbers; preserve stable point IDs, published review mappings and answers. |

## Preserved contracts and validation

Environment details moved from the entry to `editing-environments.md`; Premiere
project-path setup, terminal access, hybrid graphics and capability verification
remain required. Local clips no longer require a human-review row for every
point; their stable IDs remain available for navigation, while answer validation
still rejects points outside the published review subset. The viewer identifies
unlisted points and counts all timeline point IDs independently of review rows.
Scoring, review-state semantics, CV tools, speed estimation and the seven visual
components are unchanged. No private match data is used here.

Run `python tools/package.py refresh` then `python tools/validate.py` after edits.
The existing suite checks runtime logic, package contracts, links and the recovery
archive. It does not prove a fresh agent will follow the instructions or that a
real match has been adjudicated or rendered correctly.

For v23, all 167 Python tests and 8 local-editor JavaScript tests passed. A
synthetic browser check covered two timeline points with one review row and with
no review rows: both points remained navigable and correctly counted, and the
selected review answer survived reload without adding a row for the clear point.
The browser reported only the existing favicon request returning HTTP 403.
For v23.6, all 167 Python tests, 42 workflow contracts, package checks and 35
Markdown section links passed. Executable helpers and all seven JSX templates
remain unchanged. v23.7 also passed all 167 Python tests and package/contract
checks. Fresh-agent compliance on a real match has not been tested.
