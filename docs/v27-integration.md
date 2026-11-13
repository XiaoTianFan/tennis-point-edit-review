# v27.1 integration

Release `2026.11.13-v27.1` combines local main at `6701bd1` with the cloud
serve-speed branch at `284cddb`. Both descended from `2b63d12` (v26.0).
The merge retains all 67 local commits and the cloud commit as ancestors;
it does not replace the local work with the older cloud branch's base.

## Retained behavior

The local line retains endpoint audits, 1080p-equivalent working media with
original-source export, optional vision observations and resumable/shared
decoding, motion profiles, player appearance observations, forward-ending
review, integrated point/event review, and temporal/gap-routing experiments.
The [vision acceptance record](cv-acceptance-status.md) and
[temporal-routing notes](cv-temporal-routing.md) retain their evidence and
limitations. Integrating these commits does not promote experiments to
unattended production analysis.

The cloud line adds [joint reconstruction](../skills/tennis-point-edit-review/references/serve-speed-pipeline.md),
separate source/capture clocks, covariance-weighted observations, integrated
3D path metrics, candidate-bound acceptance, conditional uncertainty summaries
and optional overlay metadata. Existing endpoint and partial-trajectory routes
remain available. Camera/tracking adapters and rendering the extra uncertainty
row remain explicit task responsibilities; see the
[API contract](../skills/tennis-point-edit-review/references/serve-speed-joint-api.md).

Vision proposals do not automatically become verified ball observations or
accepted joint-speed inputs. Native evidence, identity, geometry, event and
quality checks still apply. Source PTS remain authoritative for editing,
labels and audio. Review observations, adopted scores/statistics and owner
confirmation remain separate. All seven canonical JSX templates are unchanged.

## Conflict resolution

- Keep both local and cloud release history and workflow obligations.
- Preserve the local vision entry while adding the cloud speed-method entry.
- Merge workflow rules by identity, retaining local runtime files and their
  updated checksums, plus every new cloud rule.
- Align active release labels in both READMEs, the skill entry, package metadata,
  UI manifest and serve-speed explanation. Historical experiment dates stay intact.
- Rebuild the recovery archive from the combined source with
  `python tools/package.py refresh`; do not select either old archive as authority.

## Validation and publication

Local integration validation passed:

| Check | Result |
|---|---|
| `python tools/validate.py` | 172 package tests and 156 repository tests passed; archive integrity, 69 workflow rules, 103 runtime/protected entries and documentation links passed |
| `npm run check:adapters` | 8 tests passed |
| `node --test tools/local-editor.test.cjs` | 21 tests passed |
| `npm run demo:build` | 36 fictional points and seven canonical-component previews built |
| Preservation comparison | All 63 local-only changed files and seven JSX templates unchanged; all 12 cloud-added files identical to the cloud commit |
| `git diff --check` | Passed |

The Python validation includes the joint numerical checks,
uncertainty/overlay contracts, existing physics and scoring checks, local
editor, endpoint/media and optional vision regressions, package integrity,
workflow obligations and documentation links. Synthetic checks do not establish
real-world speed accuracy or complete the remaining vision acceptance work.

Publish the merge to GitHub main without rewriting either parent history.
Verify local and remote commit equality and GitHub validation before removing
integrated feature branches. A linked worktree may be detached at its retained
commit before deleting its branch; its files must be preserved. Repository
publication does not update an account-saved Skill or restart a running editor.
