# Maintaining

This is the runbook for keeping the component released, compatible and healthy.
For development setup, see [CONTRIBUTING.md](CONTRIBUTING.md). Each procedure also
has a Claude Code skill in `.claude/skills/`, listed at the end.

## What runs automatically

| When | Workflow | What it does | If it fails |
|---|---|---|---|
| Every PR and every push to `master` | `ci.yml` | HACS validation, hassfest, lint and tests. A push to master also re-enables scheduled workflows that GitHub turned off. | Fix it in the PR before merging |
| Daily, 04:17 UTC | `compat.yml` | Tests against the newest HA stable and beta, plus an import check against HA `dev` | [Compatibility is red](#compatibility-is-red) |
| Daily, 05:29 UTC | `stale.yml` | Labels issues and PRs inactive for 60 days, then closes issues after 30 more days and PRs after 14 | Add the `pinned` label to keep something open |
| Monday, 06:23 UTC | `pyhive_bump.yml` | Opens a PR if a newer `pyhive-integration` is on PyPI | [Dependency PRs](#dependency-prs) |
| Weekly | Dependabot | PRs for GitHub Actions versions and for `requirements_test.txt` | [Dependency PRs](#dependency-prs) |
| A GitHub release is published | `release.yml` | Checks the tag matches `manifest.json`, then attaches `hive.zip` | [Releasing](#releasing) |
| Manual | `delete_beta.yml` | Deletes old pre-releases and their tags, keeping the newest | Not applicable |

## Releasing

Versions are `YEAR.MONTH.PATCH`, for example `2026.10.0`. Betas add `bN`, for example `2026.10.0b1`.
HACS installs by tag, so **the tag must equal `version` in `manifest.json`**.

1. Open a PR that sets `version` in `custom_components/hive/manifest.json`. Merge it
   once CI passes.
2. Check that the last Compatibility run on `master` passed, so you aren't shipping
   something current HA versions break.
3. Publish the release from the same version:

   ```bash
   # beta: HACS offers it only to users who opt into betas
   gh release create 2026.10.0b1 --target master --prerelease --generate-notes
   # stable
   gh release create 2026.10.0 --target master --latest --generate-notes
   ```

4. Watch the **Release** run: `gh run watch $(gh run list -w release.yml -L1 --json databaseId -q '.[0].databaseId')`.
   - It checks the tag *after* publishing. If it fails, the release is already
     visible to HACS users. Delete it straight away with
     `gh release delete <tag> --cleanup-tag`, fix the cause, and release again.
   - A beta tag must be a pre-release, and a pre-release must have a beta tag.
5. After a stable release that replaces a run of betas, run **Delete Beta Releases**:
   `gh workflow run delete_beta.yml`.

## Compatibility is red

Most platforms re-export Home Assistant core's hive code, so a new HA release can
break the component with no change here. Open the failing run
(`gh run list -w compat.yml`) and check which job failed:

| Failing job | Usually means | Do this |
|---|---|---|
| **Tests (HA stable)** | Users on the latest HA are probably broken now | Fix first, and release a patch |
| **Tests (HA beta)** | The next HA release (first Wednesday of the month) will break it | Fix before that release. Ship a beta if needed |
| **Import smoke test (HA dev)** | Something the component imports was renamed or removed in core | Adapt before it reaches beta |
| **Find Home Assistant … release** step | The test plugin for a brand-new HA release isn't on PyPI yet | Usually fixes itself within a day. Rerun it |
| **HACS and hassfest** | New validation rules | Update the manifest or repo structure as it says |

To reproduce locally, install the HA version that failed into a separate venv:

```bash
VENV=.venv-ha-beta script/setup
VIRTUAL_ENV=.venv-ha-beta uv pip install "pytest-homeassistant-custom-component==<test_plugin from the run log>"
VENV=.venv-ha-beta script/test
```

Common causes are renamed imports, changed entity base classes, and new
required manifest keys. The Home Assistant developer blog
(https://developers.home-assistant.io/blog) announces these ahead of time.

## Dependency PRs

- **`pyhive-integration`** (from `pyhive_bump.yml`): read the release notes linked in the
  PR. If CI hasn't run, close and reopen the PR (see the `BOT_TOKEN` note below). Merge
  it once green. Release it on its own, or together with the next change.
- **`pytest-homeassistant-custom-component`** (Dependabot): this moves the HA version CI
  tests against. Update the comment in `requirements_test.txt` to say which HA
  version it pins. If HA has raised its minimum Python version, see below.
- **`ruff`** (Dependabot): if lint fails, run `script/lint` on the branch and push.
- **GitHub Actions** (Dependabot, grouped): merge once CI passes.

### When Home Assistant needs a newer Python

Update every one of these together:

- `python-version` in `.github/workflows/ci.yml` and `compat.yml` (3 places)
- `PYTHON_VERSION` in `script/_common.sh`
- `target-version` in `pyproject.toml`

Then run `script/setup --recreate`.

### When dropping support for old Home Assistant versions

Raise `homeassistant` in `hacs.json`. It stops HACS offering new releases to
users on older HA versions.

## Repo settings (one-time; check they're still on)

- **Branch protection on `master`:**
  - Require the checks *HACS validation*, *Hassfest*, *Lint* and *Tests*.
  - Turn on *Require review from Code Owners*.
- **Secret `BOT_TOKEN`:** a fine-grained PAT with Contents and Pull requests write
  access on this repo. Without it, PRs from `pyhive_bump.yml` don't trigger CI.
- **Pyhive repo:** add a `HIVE_COMPONENT_DISPATCH_TOKEN` secret and a publish step
  that sends `repository_dispatch`. The snippet is in the header of `pyhive_bump.yml`.
  It triggers a bump PR as soon as Pyhive releases.
- **Scheduled workflows enabled:**
  - Check with `gh workflow list --all`.
  - CI switches them back on after the next push to master, but if the repo goes
    quiet for 60 days they stop again.

## Known issues in the code

- `sensor.py` has update branches for `CurrentTemperature`, `Heating_Boost` and
  `Hotwater_Boost` that never run, because no sensor description matches those
  types. `get_current_temp_sa()` also calls `heating.minmaxTemperature`,
  `currentTemperature` and `targetTemperature`, but only the first of those exists
  in pyhive. Pointing it at `Current_Temperature` would therefore crash. Either
  delete this code or fix it along with the pyhive method names.
- `async_setup_hive_entry` raises `UnknownHiveError` from the user step. That path
  is unreachable, because the step checks for `AuthenticationResult` first.

## Claude Code skills

Run these in Claude Code from the repo root. Each one follows the matching
section above.

| Skill | Use it to |
|---|---|
| `/release` | Cut a beta or stable release, from the version bump through to checking the Release run |
| `/triage-compat` | Find out why Compatibility is red, reproduce it locally and fix it |
| `/bump-pyhive` | Move to a new `pyhive-integration`, and check whether its changes affect this component |
| `/repo-health` | Check workflows, recent runs, open bot PRs, branch protection and secrets in one report |
