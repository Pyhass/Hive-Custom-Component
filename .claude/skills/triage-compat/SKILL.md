---
name: triage-compat
description: Diagnose and fix a failing nightly Compatibility workflow (compat.yml) for the Hive custom component - identifies which Home Assistant channel broke, reproduces it locally against that HA version, and fixes it. Use when Compatibility is red, a new HA release/beta broke the component, or the user asks whether the component works with a given HA version.
---

# Triage Compatibility

Background: most platform files (`binary_sensor.py`, `climate.py`, `light.py`, `switch.py`, `water_heater.py`, `entity.py`) re-export `homeassistant.components.hive.*`. `__init__.py`, `sensor.py` and `config_flow.py` are this repo's own code, but they rely on HA helpers and on core's `HiveEntity`. HA changes break things here without any commit in this repo.

## 1. Find what failed
```bash
gh run list -w compat.yml -L 5
gh run view <run-id>                       # which jobs failed
gh run view <run-id> --log-failed | tail -200
```
From the log, note the job and the HA version. The "Find Home Assistant … release" step prints `homeassistant=` and `test_plugin=`.

Map it using the table in MAINTAINING.md → "Compatibility is red":
- **stable** fails: users are broken now, so treat it as urgent.
- **beta** fails: must be fixed before the next monthly HA release.
- **dev** smoke import fails: an import was renamed or removed upstream.
- The resolver step fails with "No pytest-homeassistant-custom-component release pins…": the plugin isn't published yet. Rerun later with `gh run rerun <id> --failed`. There's nothing to fix.
- **HACS/hassfest** fails: follow the validator's message.

## 2. Reproduce locally
Use a separate venv so `.venv` (which matches CI's pinned HA) stays untouched:
```bash
VENV=.venv-ha-beta script/setup
VIRTUAL_ENV=.venv-ha-beta uv pip install "pytest-homeassistant-custom-component==<test_plugin>"
VENV=.venv-ha-beta script/test -x
```
For a dev failure, run the smoke test instead:
```bash
VIRTUAL_ENV=.venv-ha-dev uv pip install "homeassistant @ git+https://github.com/home-assistant/core@dev"
.venv-ha-dev/bin/python .github/scripts/smoke_import.py
```
(Create `.venv-ha-dev` with `VENV=.venv-ha-dev script/setup` first.)

## 3. Find the upstream change
- Compare core's hive integration between the two HA versions:
  `https://github.com/home-assistant/core/commits/dev/homeassistant/components/hive`.
- Search https://developers.home-assistant.io/blog for deprecations of the symbol that failed.
- Check the installed source: `.venv-ha-beta/lib/python3.*/site-packages/homeassistant/components/hive/`.

## 4. Fix
- Keep the fix working on **both** the pinned HA (`.venv`) and the failing version. Run `script/test` in both venvs.
- If core changed a re-exported platform in a way that conflicts with this component (for example it now expects something `__init__.py` doesn't provide), adapt `__init__.py`. Only replace the re-export with a local module as a last resort, and tell the user.
- Add or adjust a test that would have caught it.
- Run `script/lint`.

## 5. Report
Tell the user:
- which HA version and channel broke, and the root cause (with the upstream link)
- the fix, and the test results in both venvs
- whether a release is needed: stable breakage needs a patch release now (suggest `/release`); beta breakage needs one before HA's release date

Don't commit, push, or open PRs unless asked.
