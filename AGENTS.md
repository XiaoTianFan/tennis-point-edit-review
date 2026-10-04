# Maintaining this repository

This repository distributes one user-owned tennis editing skill. The editable
package is skills/tennis-point-edit-review/. README, docs, demo and tools are
repository maintenance files, not extra instructions to inject into a match.

- Read the skill entry and relevant references before changing workflow semantics.
- Preserve adopted boundaries and review-state semantics. Do not silently drop
  guidelines or copy project-specific players, paths, IDs, media or credentials.
- Keep demonstrations synthetic. Generate their values through the real helpers.
- Preserve the seven canonical JSX templates unless a style change was requested.
- After intentional package edits run python tools/package.py refresh, then
  python tools/validate.py. Do not run archive repair to undo uncommitted edits.
- Update account and repository copies only within the user's requested scope.
  Follow docs/synchronization.md; never pretend an account Skill has a Git path.
- Import a full exported snapshot using the sync helper's dry run first. Resolve
  conflicts instead of overwriting local edits. Keep account binding private.
- Publication to GitHub is separate from local preparation. Never embed tokens.
