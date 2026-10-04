# Stage-based workflow maintenance

Revisions v23–v23.3 clarify agent-owned work, concrete stage delivery, necessary
interactive review, and the distinction between main-cut and review labels.
This is repository maintenance context, not additional match instructions.

The skill entry now groups each stage's work, required reading and completion
checks. Default delivery is one substantive stage per turn; explicit continuous
execution preserves the same checks. Setup is part of the first substantive
stage, and inapplicable stages do not require empty deliverables or approvals.
Existing project notes hold the small progress record; no new state schema or
workflow engine is introduced.

The seven stages deliver: cut timeline → adjudication/scoring/basic graphics →
review ⇄ recalculation → statistics/speed data → panels and speed overlays →
final QA. Stage 1 keeps the ledger internal and does not advance scores; stages
3–4 may repeat; stage 5 supplies all data for the combined graphics stage 6.

## Scenario review

These are documentation walk-throughs, not a live-editor or model reliability
benchmark. Use them for a future fresh-agent evaluation without supplying the
expected behavior to that agent.

| Starting request or condition | Expected behavior |
|---|---|
| Raw footage, no execution preference | Stage 1 cuts every point from serve to dead ball with required reactions and places it on a playable timeline. Keep the ledger internal; scoring starts in stage 2. |
| Already cut points and a known final score | Check cuts and internal mappings, then reuse the timeline for agent-owned point adjudication, scoring and basic graphics in stage 2. |
| A few clipped endings or uncertain serves | Inspect source gaps and continuous context; adopt clear decisions. Only unresolved material questions and necessary related points enter review. |
| Review is necessary | Deliver matching review sequence and interactive HTML, or the standalone review workspace. Every selected review row stays visible; unrelated points are not added by default. |
| Scoring still disagrees with the supplied final game/set score after source checks | Include each problem game's points individually, with necessary adjacent evidence. Preserve known answers; repeat stages 3–4 as needed without fabricating a matching score. |
| Statistics and speed data are ready | Stage 6 renders both five-page panels and per-serve speed overlays from stage 5's shared data and timing; neither requires its own stage or fixed rendering order. |
| A long rally, before speed estimation | Serve label starts before service and exits no later than three seconds after the confirmed post-contact display start, or at an earlier boundary. It does not fill the rally. |
| Resume with reviewed answers or completed statistics | Read current state and the affected stage references; preserve IDs, answers and completed work. Recompute dependencies or build the remaining panels/labels as appropriate. |
| “Do everything continuously; ask only when necessary” | Continue across stages with progress reports, required reading and self-checks; genuine unanswered questions block only dependent conclusions. |
| Familiar user, “skip the introduction” or “start directly” | Omit onboarding; do not infer permission to replace default staged delivery with one full pass. |
| Any stage completes, including a review/recalculation repeat | Name the completed and next applicable stages, report results, and ask whether to proceed. Wait unless continuous execution was explicitly requested; at final delivery, state that the workflow is complete. |
| A batch or a few serve-label examples pass, with executable work remaining | Continue the same stage without asking to proceed. Stage 2 covers point outcomes, serves and basic graphics for every target point; only unresolved questions after source checks enter review. An actual interruption remains an incomplete stage, not a new stage. |
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
Fresh-agent compliance on a real match has not been tested in this revision.
