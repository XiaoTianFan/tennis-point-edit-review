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
