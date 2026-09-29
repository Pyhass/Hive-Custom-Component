---
name: bump-pyhive
description: Update the pyhive-integration (apyhiveapi) requirement in the Hive custom component's manifest.json, review what changed in the library, and verify the component against it. Use when a pyhive bump PR is open, a new pyhive release is out, or the user wants to test a pyhive beta/dev build.
---

# Bump pyhive-integration

`pyhive-integration` (imported as `apyhiveapi`) is pinned in `custom_components/hive/manifest.json` `requirements`. Dependabot can't bump it, so `.github/workflows/pyhive_bump.yml` opens `deps/pyhive-integration-<ver>` PRs instead.

## 1. Pick the target
```bash
jq -r '.requirements[]' custom_components/hive/manifest.json                             # current
curl -fsS https://pypi.org/pypi/pyhive-integration/json | jq -r '.info.version'           # latest stable
curl -fsS https://pypi.org/pypi/pyhive-integration/json | jq -r '.releases | keys[]' | tail -10
gh pr list --label dependencies --search "pyhive-integration in:title"                    # existing bot PR?
```
If there's already a bot PR for the target, work on that branch (`gh pr checkout <n>`) instead of making a new change.

## 2. Review what changed
Diff the two versions' sources and look closely at anything this component calls:
```bash
S=$(mktemp -d)
for v in <current> <target>; do
  uv pip download --no-deps "pyhive-integration==$v" -d "$S/$v" 2>/dev/null || pip download --no-deps "pyhive-integration==$v" -d "$S/$v"
done
```
Unpack both and diff `apyhiveapi/`. Things to check:
- `Auth` methods used in `config_flow.py` and `__init__.py`: `login`, `sms_2fa`, `device_registration`, `get_device_data`, `is_device_registered`, `forget_device`.
- `Hive`, `session.startSession`, `session.deviceList`, `updateInterval`.
- `helper/const.py`: `PRODUCTS`, `DEVICES` and `sensor_commands`. A new or renamed `hiveType` needs a matching `SENSOR_TYPES` entry in `sensor.py`, or core's platform descriptions, before it shows up in HA.
- Exceptions in `helper/hive_exceptions.py`.
- The getters that tests mock: `getSensor`, `getClimate`, `getWaterHeater`, `getLight`, `getSwitch` and `getScheduleNowNextLater`.

Also check whether the version HA core pins (`homeassistant/components/hive/manifest.json` in `.venv`) differs a lot. Core's re-exported platforms are written against that version.

## 3. Apply and verify
- Change only the `pyhive-integration==` pin in `manifest.json`. Don't change the component `version`; that happens at release.
- Install and test:
  ```bash
  VIRTUAL_ENV=.venv uv pip install "pyhive-integration==<target>"
  script/test
  script/lint --check
  ```
- Where the diff showed behaviour changes, add tests for them.
- For a beta or dev build, suggest also releasing a component beta (see `/release`) so users can try it.

## 4. Report
Report:
- the version change
- a short summary of the library changes that matter to this component, with any risks
- the test results
- whether it's ready to merge

If a bot PR has no CI runs, remind the user to close and reopen it, or to set up the `BOT_TOKEN` secret. Don't commit, push, or merge unless asked.
