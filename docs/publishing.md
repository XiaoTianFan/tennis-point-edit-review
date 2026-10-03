# Publish this repository

The repository is prepared locally. Creating a remote and uploading it are separate actions.

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
