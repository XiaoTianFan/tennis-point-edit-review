# Publish this repository

Publishing requires an explicit user request. For an existing clone with `origin`:

1. Inspect `git status` and the diff; keep match media, credentials and account exports out of commits.
2. Run `python tools/package.py refresh`, `python tools/validate.py`, and relevant editor checks.
3. Commit the intended changes, fetch origin, and inspect divergence before pushing. Do not force-push over remote work.
4. Push the intended branch, compare local HEAD with its remote ref, and inspect the validation workflow result.

Pushing this repository does not update an account-saved Skill or a running local
editor. Account transfer follows [synchronization](synchronization.md); backend
editor changes require a process restart. Report these delivery surfaces separately.

For first publication to a new remote:

1. Read the README and license, inspect screenshots, and run `python tools/validate.py`.
2. Create an empty repository on GitHub under your chosen account.
3. Add its URL and push the existing main branch:

```sh
git remote add origin https://github.com/YOUR_ACCOUNT/tennis-match-edit.git
git push -u origin main
```

Replace YOUR_ACCOUNT with your actual account. No GitHub account or remote is
hardcoded in this project. Do not put credentials in a URL or tracked file.

Suggested description:
> Tennis point editing, scoring review and event-derived statistics as an agent skill.

Suggested topics: agent-skills, tennis, video-editing, sports-analytics, chatcut.

After publication, users can install with:
`npx skills add YOUR_ACCOUNT/tennis-match-edit --skill tennis-point-edit-review`.

Screenshots are checked into docs/images; the README uses relative links, so a
GitHub Pages deployment is not required. Add a release tag only after reviewing
the commit you intend to publish.
