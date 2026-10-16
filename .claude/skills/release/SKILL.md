---
name: release
description: Cut a beta or stable release of the Hive custom component - check for the newest pyhive-integration (betas included) when releasing a beta, bump manifest.json, publish the GitHub release with a matching tag, and verify the Release workflow. Use when the user asks to release, ship, tag, or publish a version or beta.
---

# Release

Follow MAINTAINING.md → "Releasing", and the principles in `CLAUDE.md`. The rules that matter:
- **Betas are the fast, opt-in channel.** They're how new `pyhive-integration` builds and fixes reach users before core HA ships them. Stable releases go to every HACS user.
- The tag must equal `version` in `custom_components/hive/manifest.json`, for example `2026.10.0` or `2026.10.0b1`. Use a lowercase `b`, with no dot before it.
- Beta tags (`bN`) are always published as pre-releases. Stable tags never are.
- A stable release must pin a stable `pyhive-integration`. A pre-release pin only ships in a beta. `check_release.py` fails the Release run otherwise, but by then the release is already public, so check before publishing.
- Publishing a release is visible to every HACS user, and so is deleting one. **Confirm the exact tag and whether it is a pre-release with the user before running `gh release create`.** Never commit, push, or open PRs unless the user asks.

## Steps

1. **Pick the version.**
   - Read the current `version` from the manifest and list recent tags: `gh release list -L 10`.
   - Propose the next version and let the user confirm or change it:
     - New month: `YEAR.MONTH.0`.
     - Same month: bump the patch number.
     - Beta: add `b1`, or the next free `bN`.

2. **Check pyhive-integration.**
   - **Beta:** always look up the newest version on PyPI, pre-releases included:
     ```bash
     curl -fsS https://pypi.org/pypi/pyhive-integration/json | jq -r '.releases | keys[]' \
       | .venv/bin/python -c 'import sys; from packaging.version import Version; print(max(sys.stdin.read().split(), key=Version))'
     jq -r '.requirements[]' custom_components/hive/manifest.json
     ```
     If it's newer than the pin, run `/bump-pyhive` for it first, and get that merged to `master`, unless the user decides to skip it. Check for an open `deps/pyhive-integration-*` PR before starting a new one.
   - **Stable:** the pin must not be a pre-release. If `master` pins a pyhive beta, stop: either wait for a stable pyhive, or move the pin to the latest stable with `/bump-pyhive` first.

3. **Check it's safe to ship.**
   - `gh run list -w ci.yml -b master -L 1` and `gh run list -w compat.yml -L 1` must both be green. If either is red, stop and report. For a red Compatibility run, suggest `/triage-compat`.
   - A hassfest **warning** about `pyhive-integration` differing from core hive is expected (see `CLAUDE.md`). Only errors count.
   - `script/test` and `script/lint --check` must pass locally.
   - Check `git log <last-tag>..origin/master --oneline`. If there's nothing to release, say so.

4. **Bump the manifest.** Change only the `version` value in `manifest.json`. Don't touch `requirements`; that's `/bump-pyhive`. The change must reach `master` before tagging:
   - If the user asks, make a branch `release/<version>`, commit it, and open a PR.
   - Otherwise hand the change over for them to commit.
   - Wait until it's merged, then check with `git fetch && git show origin/master:custom_components/hive/manifest.json | jq -r '.version, .requirements[]'`.

5. **Publish** (only after the user confirms the tag):
   ```bash
   gh release create <version> --target master --generate-notes --prerelease   # beta
   gh release create <version> --target master --generate-notes --latest       # stable
   ```
   For a beta, add the `pyhive-integration` version to the notes, and say whether it's ahead of core's.

6. **Verify.**
   - Watch the Release workflow:
     ```bash
     gh run watch $(gh run list -w release.yml -L1 --json databaseId -q '.[0].databaseId') --exit-status
     ```
   - Then confirm `hive.zip` is attached: `gh release view <version> --json assets -q '.assets[].name'`.
   - If the check job fails, the release is already visible to HACS users. Tell the user, and offer `gh release delete <version> --cleanup-tag` (it needs their OK), then a corrected release.

7. **Clean up** after a stable release that replaces betas. Offer `gh workflow run delete_beta.yml`. It keeps the newest pre-release and never touches stable releases.

Report the release URL, the `pyhive-integration` version it ships, the Release run result and anything left for the user to do.
