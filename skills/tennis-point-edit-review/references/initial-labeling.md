# Initial labeling and human–agent collaboration

Prepare a usable review surface **after clips exist and before agent outcome
recognition starts**. Apply this to stage-1 raw cuts, existing timelines and
[rendered partitions](rendered-video.md). Reuse confirmed facts and current work.

## Working mode

- `agent-dominant` is the default. Prepare and verify the surface, supply its link
  with stage 1, then perform stage-2 adjudication when authorized. The user may
  take over. Do not require them to label the whole match or add an approval point.
  Normal staged/continuous execution still applies.
- `human-first` follows the user's explicit wish to start manually. Prepare all
  current point/candidate rows and hand over the surface. Wait for answers or an
  instruction to switch back; do not prefill speculative tennis conclusions.
  Independent media/infrastructure work can continue. Accept full or partial
  handoff, preserve confirmed answers, and complete uncovered work from there.

Record `workingMode` in the plan/stage record. No routine mode questionnaire;
switch only when requested or clearly implied. Read current workbench context or
HTML exports before any agent write following human editing.

## Prepare and open

Use a [local plan](local-editor.md) with CFR assets, stable clip IDs and point
mapping. A host timeline can be mapped for review while retaining the chosen
editor. Shared `pointId` values produce one row with all clip evidence ranges.
Names and known server/serve/game/set values come from this task; unknowns stay
null. Agent `initial` values never represent human confirmation.

```sh
python "<skill>/scripts/prepare_review.py" "<work>/plan.json" "<work>/initial-v1" --mode agent-dominant --surface both
python "<skill>/scripts/local_editor.py" serve "<work>/initial-v1/edit" --open
```

Choose `--mode human-first` when requested. `--surface html` creates the offline
table beside the chosen editor; `local` provides integrated video playback; `both`
creates both. Supply an openable `review.html` path or running session URL.
`handoff.json` records readiness/next action, not browser or tennis acceptance.
Use one active answer surface: HTML drafts and workbench saves do not synchronize.
If both were used, reconcile by source/revision/P ID before merging.

If reconstructed clip grouping is unverified, explicitly use
`--provisional-points` to expose candidates immediately. These P mappings are
provisional, not confirmed points or statistical denominators. Users can note
needed merges/splits; apply them using [lineage rules](coverage-and-exceptions.md)
and a new review revision. Never silently transfer answers to split/merged
points. With verified grouping, supply stable/shared `pointId` values and omit
this flag. A clip is not automatically one point.

The command writes `plan.json`, `review-data.json`, `ledger.json` and the selected
surface to a **new** directory. It refuses an existing destination or published
review/answers. Resume the same page/workspace and draft identity; do not rerun
blank preparation. Asset metadata paths resolve from the input plan.

## Manual labeling and handoff

Initial rows offer winner / cannot determine, dead-ball type, double fault,
extra point, reviewed and notes, plus nullable server, serve number, game and set.
ACE/double-fault inference requires a selected server; changing server clears a
dependent ACE/double-fault result. These extra controls apply only to initial
labeling. A reviewed outcome with unknown metadata does not establish complete
score/statistical coverage.

Rows stay visible and in order after editing/search. HTML keeps browser drafts
and Copy results exports all rows. The workbench saves revisions/history; use
Send to agent or `local_editor.py context`. Existing pending/partial/resolved/
replay/unresolved semantics apply; opening the page is not human review.

```sh
python "<skill>/scripts/review_io.py" merge "<work>/initial-v1/ledger.json" "<work>/exported-review.txt" "<work>/ledger-next.json"
```

For the workbench, use its freshly exported `review.json` or the `review` object
from `context`. Exports retain `tennis-point-review/v1` and add
`purpose: "initial-labeling"` plus optional server/serve/game/set fields.
Both ledger and export must match purpose, source
and revision. Pending stays pending; reviewed unknowns have no adopted winner.
Nulls do not erase previous facts; reconcile intentional corrections and retain
confirmation/exclusion history. This is an intermediate ledger: verify grouping,
map player IDs into the established scoring/event model, run stage-2 score/serve
checks, then stage-5 technical coverage.

## Initial labeling versus stage 3

Initial labeling exposes all current points/candidates to allow starting from
zero. Its directory and `:initial` revision/draft identity differ from later
exception review. Preserve it when publishing stage 3; do not turn every initial
row into an unresolved exception or require all rows to be human-reviewed in
agent-dominant mode. Stage 3 retains only actual unresolved questions/problem
games after agent checks, unless the user requests more, and uses its existing
review timeline. Transfer confirmed facts with their histories.

Before handoff, open the chosen surface. Check scoped row coverage, unknowns,
clip jumps/playback (local) or editor locations (HTML), an answer and an explicit
unknown, save/reload/export, visibility/order, R/P mapping and language. File
generation alone is not interactive acceptance.
