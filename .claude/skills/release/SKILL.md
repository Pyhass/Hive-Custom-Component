---
name: release
description: Cut a beta or stable release of the Hive custom component - bump manifest.json, publish the GitHub release with a matching tag, and verify the Release workflow. Use when the user asks to release, ship, tag, or publish a version or beta.
---

# Release

Follow MAINTAINING.md → "Releasing". The rules that matter:
- The tag must equal `version` in `custom_components/hive/manifest.json`, for example `2026.10.0` or `2026.10.0b1`.
- Beta tags (`bN`) are always published as pre-releases. Stable tags never are.
- Publishing a release is visible to every HACS user, and so is deleting one. **Confirm the exact tag and whether it is a pre-release with the user before running `gh release create`.** Never commit, push, or open PRs unless the user asks.

## Steps

1. **Pick the version.**
   - Read the current `version` from the manifest and list recent tags: `gh release list -L 10`.
   - Propose the next version and let the user confirm or change it:
     - New month: `YEAR.MONTH.0`.
     - Same month: bump the patch number.
     - Beta: add `b1`, or the next free `bN`.

2. **Check it's safe to ship.**
   - `gh run list -w ci.yml -b master -L 1` and `gh run list -w compat.yml -L 1` must both be green. If either is red, stop and report. For a red Compatibility run, suggest `/triage-compat`.
   - `script/test` and `script/lint --check` must pass locally.
   - Check `git log <last-tag>..origin/master --oneline`. If there's nothing to release, say so.

3. **Bump the manifest.** Change only the `version` value in `manifest.json`. Don't touch `requirements`; that's `/bump-pyhive`. The change must reach `master` before tagging:
   - If the user asks, make a branch `release/<version>`, commit it, and open a PR.
   - Otherwise hand the change over for them to commit.
   - Wait until it's merged, and check with `git fetch && git show origin/master:custom_components/hive/manifest.json | jq -r .version`.

4. **Publish** (only after the user confirms the tag):
   ```bash
   gh release create <version> --target master --generate-notes --prerelease   # beta
   gh release create <version> --target master --generate-notes --latest       # stable
   ```

5. **Verify.**
   - Watch the Release workflow:
     ```bash
     gh run watch $(gh run list -w release.yml -L1 --json databaseId -q '.[0].databaseId') --exit-status
     ```
   - Then confirm `hive.zip` is attached: `gh release view <version> --json assets -q '.assets[].name'`.
   - If the check job fails, the release is already visible to HACS users. Tell the user, and offer `gh release delete <version> --cleanup-tag` (it needs their OK), then a corrected release.

6. **Clean up** after a stable release that replaces betas. Offer `gh workflow run delete_beta.yml`. It keeps the newest pre-release and never touches stable releases.

Report the release URL, the Release run result and anything left for the user to do.
