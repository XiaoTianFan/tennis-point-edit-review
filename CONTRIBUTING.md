# Contributing

Keep changes small and explain the observable workflow problem they solve.

1. Preserve existing boundaries or document an explicitly adopted replacement.
2. Add synthetic examples for meaningful scoring, denominator or sync changes.
3. Update canonical templates, metadata and checks together when UI contracts change.
4. Run `python tools/package.py refresh`, `python tools/validate.py`, and regenerate
   screenshots when visible templates or mock data changed.
5. Keep real recordings, player identities, account exports and credentials out of commits.

Do not expand default user review forms simply because internal evidence has more
fields. Do not introduce new metrics that duplicate existing indicators.

Check the actual recording, camera view and render target when verifying an edit.

Keep job data under the saved checkout's ignored `outputs/`, unless the user
specifies a directory. Follow [job storage](docs/job-storage.md) for defaults,
immutable relocation maps and migration validation. Never commit private inventories.

For local workbench changes run `npm run check:local` and verify the affected
browser interaction. Cover full/review view mapping, long-timeline fit, known
and unassigned games, and user-requested exports with confirmations absent.
Keep the agent's unsolicited-render policy separate from user export controls;
updating a running server requires a restart, not only a browser reload.
