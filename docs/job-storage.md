# Job storage and relocation

The saved checkout on this installation is `F:\Codes\tennis-match-edit`; its
canonical job root is `F:\Codes\tennis-match-edit\outputs`. This local binding is
documented here, not hardcoded into the distributed skill. `outputs/` is ignored
by Git; the legacy `output/` ignore remains for existing repository maintenance
artifacts. No match data belongs in the package or a disposable Git worktree.

Use `local_editor.py workspace --source "<source>"` before producing job data.
The helper resolves the saved checkout from Git's common directory, independent
of cwd and linked worktrees. Extracted installations require an explicit absolute
`TENNIS_OUTPUTS_ROOT` or `--outputs-root`. An explicit `--work-dir` takes priority.
New default names are exclusive; collisions get a numeric suffix. Existing jobs
resume in place, and source/final library locations are separate from job storage.

The operational [storage contract](../skills/tennis-point-edit-review/references/job-storage.md)
defines the layout and migration boundaries. JSON reads in Courtside/Edit apply
the closest `relocation-map.json` to absolute path values in memory. Original
bytes and historical cleanup/export records remain intact. Mappings use complete
path boundaries and reject destinations outside the containing job or through
reparse points. Standalone scripts can use `read_document(path, workspace=job)`;
raw historical scripts and reports still require the map when following old paths.

For a migration, keep a private manifest under ignored outputs, copy and hash
every retained file, check current project and recovery dependencies, and compare
any missing references with the pre-migration baseline. Remove only exact verified
old copies and empty directories. Preserve shared infrastructure and unrelated files.
Measure unique roots once and report source/final libraries separately from jobs.
Relocation is not disk reclamation; include new audit records and caches in after totals.

Validation: `python -m unittest discover -s tools -p test_job_workspace.py`,
`python tools/package.py refresh`, `python tools/validate.py`, and
`npm run check:local`. Exercise a relocated project through HTTP media and graphics
endpoints plus a browser smoke. Do not render another full match for a path-only change.
