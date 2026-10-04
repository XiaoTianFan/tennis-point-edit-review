# Stage-based workflow maintenance

Revision v23 addresses observed failures to finish agent-owned analysis, deliver
interactive review, and distinguish main-cut labels from review information.
This is repository maintenance context, not additional match instructions.

The skill entry now groups each stage's work, required reading and completion
checks. Default delivery is one substantive stage per turn; explicit continuous
execution preserves the same checks. Setup is part of the first substantive
stage, and inapplicable stages do not require empty deliverables or approvals.
Existing project notes hold the small progress record; no new state schema or
workflow engine is introduced.

## Scenario review

These are documentation walk-throughs, not a live-editor or model reliability
benchmark. Use them for a future fresh-agent evaluation without supplying the
expected behavior to that agent.

| Starting request or condition | Expected behavior |
|---|---|
| Raw footage, no execution preference | Briefly explain the remaining workflow; begin evidence/ledger work and deliver the first stage's actual results with the next step. |
| Already cut points and a known final score | Reuse cuts; map stable points, add visible locators, inspect actual serves and outcomes. Build scoring and short serve labels in stage 2; final score constrains but does not fabricate outcomes. |
| A few clipped endings or uncertain serves | Inspect source gaps and continuous context; adopt clear decisions. Only unresolved material questions and necessary related points enter review. |
| Review is necessary | Deliver matching review sequence and interactive HTML, or the standalone review workspace. Every selected review row stays visible; unrelated points are not added by default. |
| A long rally, before speed estimation | Serve label starts before service and exits no later than three seconds after the confirmed post-contact display start, or at an earlier boundary. It does not fill the rally. |
| Resume with reviewed answers or completed statistics | Read current state and the affected stage references; preserve IDs, answers and completed work. Recompute dependencies or build the remaining panels/labels as appropriate. |
| “Do everything continuously; ask only when necessary” | Continue across stages with progress reports, required reading and self-checks; genuine unanswered questions block only dependent conclusions. |
| Familiar user, “skip the introduction” or “start directly” | Omit onboarding; do not infer permission to replace default staged delivery with one full pass. |
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
