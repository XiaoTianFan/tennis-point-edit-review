# Git and the account-saved Skill

## There is no account filesystem path

The account-saved Skill is a reusable record in ChatCut's My Skills library.
Its package can be retrieved or updated by a connected agent. It is not a folder
on this computer and cannot be assigned as a Git remote, watched directory or
symlink. A temporary/local extracted package is a snapshot of that record.

The durable editable package in this repository is:
`skills/tennis-point-edit-review/`.

The helper below works with **exported JSON files**. It does not implement a
ChatCut login, call a private API, install an account Skill or push a Git remote.

## Recommended: repository first

1. Edit the package and preserve the adopted boundaries.
2. Refresh the recovery archive: `python tools/package.py refresh`.
3. Run `python tools/validate.py`, inspect the diff and commit.
4. Export `python tools/package.py export --output dist/skill-package.json`.
5. Ask your connected agent to update the intended account Skill from this package.
6. Have it retrieve the saved package and compare it with the repository. Only
   after equality is verified, record a shared baseline using the command below.

Repository-only README, demo and screenshots are not uploaded as skill contents.

## Supported: account first

You can ask an agent:

> Update my saved tennis Skill as requested. Then retrieve its complete package,
> synchronize it into this repository, preserve local changes, run the checks and
> commit the result. Do not publish to GitHub unless I also request that.

The agent retrieves a full snapshot, writes only the package contents to an ignored
file such as `dist/account-export.json`, then uses:

```sh
python tools/package.py plan --input dist/account-export.json
python tools/package.py import --input dist/account-export.json --apply
python tools/validate.py
```

The plan is always read-only. Import compares local and incoming files against
a previous shared baseline. If both changed differently, it refuses the operation.
Local-only changes are preserved and reported as needing an account update.
If there is no baseline, differing existing files require manual reconciliation;
they are not silently overwritten. Deletions require `--allow-deletes`.

When both sides agree, record the common baseline:
```sh
python tools/package.py baseline --input dist/account-export.json
```

The baseline stores file hashes in ignored `.skill-sync/`, never credentials or
account identities. It is deliberately local. A fresh clone can establish its own
baseline by comparing a complete account export. A baseline does not itself save,
commit or push anything.

## Export format and integrity

The preferred neutral interchange shape is
`{"schema":"tennis-skill-package/v1","packageFiles":{"SKILL.md":"...", ...}}`.
The helper also accepts a plain packageFiles mapping or this skill's validated
recovery archive. It rejects unsafe paths, symlinks, missing entry files and
incomplete snapshots relative to their embedded archive.

This package includes an ASCII-safe recovery archive with per-file SHA-256 hashes.
If retrieved text contains damaged Unicode but the archive validates, the helper
recovers that text and reports which files were recovered. It never treats
corrupted display text as an intentional edit or guesses missing content.

For deliberate repository edits, rebuild the archive; do not repair from an older
archive over newer edits. Generated archive differences are not merge conflicts.
