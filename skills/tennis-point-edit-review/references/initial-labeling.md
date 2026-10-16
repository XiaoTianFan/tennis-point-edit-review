# Initial labeling and human–agent collaboration

After clips exist and before agent outcome recognition, prepare a usable answer
surface. Applies to raw cuts, existing timelines and [rendered partitions](rendered-video.md).
Reuse confirmed facts. Default agent-dominant prepares/verifies the surface then
continues adjudication when authorized; do not require whole-match user labeling.
Explicit human-first prepares the surface and waits for answers or a mode switch;
independent infrastructure work may continue. Record workingMode; no routine mode
questionnaire. Read current persisted answers before writes after human editing.

## Working mode

Both modes preserve initial nulls, AI versus human provenance, partial handoff and
existing review-state semantics. Opening a surface is not human review. Unknown
server/serve/game/set stay null; ACE/DF inference requires a selected server.
Changing server invalidates dependent ACE/DF. Manual metadata controls apply to
initial labeling, not proof of complete scoring/statistics coverage.

## Prepare and open

Map stable clips/P IDs to a [local plan](local-editor.md). Same-P clips produce one
row with all evidence ranges. Local mode uses only its integrated list:

```sh
python "<skill>/scripts/prepare_review.py" "<work>/plan.json" "<work>/initial-v1" --mode agent-dominant --surface local
python "<skill>/scripts/local_editor.py" serve "<work>/initial-v1/edit" --open
```

External editors use --surface html. Both is explicit compatibility, not normal
local delivery; do not create redundant offline HTML beside the workbench. If
both surfaces already contain edits, reconcile source/version/P before merging.
There is no automatic synchronization.

Use --provisional-points for unverified grouping; expose merge/split questions,
not confirmed denominators. With verified grouping share stable P IDs. Never
silently transfer answers across split/merged points; follow [lineage](coverage-and-exceptions.md).

The helper writes plan/review-data/ledger and selected surface into a new directory;
it refuses to overwrite published work. Resume the same workspace and draft
identity instead of rerunning blank preparation. Asset metadata is relative to the
input plan. handoff.json records readiness/next action, not interactive acceptance.

## Manual labeling and handoff

Rows offer winner / cannot determine, dead-ball type, double fault, extra,
reviewed, notes and nullable server/serve/game/set. All rows remain visible in
order after search or editing. Workbench saves revision/history and exports via
Send to agent or context; external HTML keeps browser drafts and Copy results.

```sh
python "<skill>/scripts/review_io.py" merge "<work>/initial-v1/ledger.json" "<work>/exported-review.txt" "<work>/ledger-next.json"
```

Use fresh workbench review.json or context.review. Export tennis-point-review/v1
retains purpose=initial-labeling, source and revision; both sides must match.
Pending stays pending, reviewed unknown clears adopted winner, null does not erase
confirmed facts. Preserve history; then qualify grouping and score/serve events
before statistics. See [merge and inference](ledger-and-review.md).

## Initial labeling versus stage 3

Initial scope is all current points/candidates, with :initial identity. Stage 3
contains only true remaining questions/problem games unless broader review was
requested. Preserve initial versions/answers and migrate confirmed facts explicitly;
do not turn every initial row into an exception. Local stage 3 uses the same
master clips with a review view; external editors use a review sequence and HTML.

Before handoff verify scoped row coverage, nulls, play/jump/frame-step, answer and
explicit unknown, save/reload/export, row order/R-P mapping and language. Use an
isolated copy for synthetic answers. Generated files alone are not acceptance.
