---
name: bump-pyhive
description: Update the pyhive-integration (apyhiveapi) requirement in the Hive custom component's manifest.json, review what changed in the library, and verify the component against it. Use when a pyhive bump PR is open, a new pyhive release or beta is out, before cutting a component beta, or the user wants to test a pyhive beta/dev build.
---

# Bump pyhive-integration

`pyhive-integration` (imported as `apyhiveapi`) is pinned in `custom_components/hive/manifest.json` `requirements`. Dependabot can't bump it, so `.github/workflows/pyhive_bump.yml` opens `deps/pyhive-integration-<ver>` PRs instead.

Read the principles in `CLAUDE.md` first. In short:
- This repo may pin a **newer** `pyhive-integration` than core hive does, including pre-releases. That's intended.
- Keep the pin exact (`==`). Don't switch to `>=` to quiet hassfest; `.github/scripts/hassfest.py` already treats that difference as a warning.
- A pre-release pin can only ship in a component **beta**. A stable component release needs a stable pin.

## 1. Pick the target
```bash
jq -r '.requirements[]' custom_components/hive/manifest.json                             # current pin
curl -fsS https://pypi.org/pypi/pyhive-integration/json | jq -r '.info.version'           # latest stable
# newest version overall, pre-releases included (sorted as versions, not by upload date)
curl -fsS https://pypi.org/pypi/pyhive-integration/json | jq -r '.releases | keys[]' \
  | .venv/bin/python -c 'import sys; from packaging.version import Version; print(max(sys.stdin.read().split(), key=Version))'
gh pr list --search "pyhive-integration in:title" --state open                           # existing PR?
```
- For a beta (or when the user asks for "latest"), the target is the newest version overall.
- For a stable release, the target is the latest stable.
- Also note core's pin, from `.venv/lib/python*/site-packages/homeassistant/components/hive/manifest.json`. Core's re-exported platforms are written against it, so a big gap needs a closer look.

If there's already an open PR for the target, work on that branch (`gh pr checkout <n>`) instead of making a new change.

## 2. Review what changed
`uv pip download` doesn't exist, so fetch the wheels from PyPI's JSON API into the scratchpad and unpack them there:
```bash
S=<scratchpad>/pyhive
for v in <current> <target>; do
  url=$(curl -fsS "https://pypi.org/pypi/pyhive-integration/$v/json" | jq -r '[.urls[]|select(.packagetype=="bdist_wheel")][0].url')
  mkdir -p "$S/dl-$v" "$S/src-$v" && curl -fsSL -o "$S/dl-$v/pkg.whl" "$url" && unzip -qo "$S/dl-$v/pkg.whl" -d "$S/src-$v"
done
diff -rq "$S/src-<current>/apyhiveapi" "$S/src-<target>/apyhiveapi"
```
Check anything this component, or core's re-exported platforms, calls:
- `Auth` methods used in `config_flow.py` and `__init__.py`: `login`, `sms_2fa`, `device_registration`, `get_device_data`, `is_device_registered`, `forget_device`. Also the attributes the flow sets: `access_token`, `device_group_key`, `device_key`.
- `Hive`, `session.startSession`, `session.deviceList`, `session.updateData`, `updateInterval`.
- Every `hive.<platform>.<method>(` call in the component and in core's hive platforms (`grep -hoE "hive\.[a-z_]+\.[A-Za-z_]+\(" ...`). Confirm each exists on the target with a compatible signature, at runtime rather than by reading code.
- How devices are accessed (`device["hiveType"]`, `.get("deviceData")`). 2.x devices are dataclasses with a legacy-key mapping.
- `PRODUCTS`, `DEVICES` and the sensor dispatch. A new or renamed `hiveType` needs a matching `SENSOR_TYPES` entry in `sensor.py`, or core's platform descriptions, before it shows up in HA.
- Exceptions in `helper/hive_exceptions.py`, especially anything `startSession` can now raise. `async_setup_entry` must map it: connection problems to `ConfigEntryNotReady`, credential or config problems to `ConfigEntryAuthFailed`.

Also check that `pyhive-integration` isn't in HA's `homeassistant/package_constraints.txt`. If it ever is, HA won't install a different version, and principle 2 needs rethinking.

## 3. Apply and verify
- Change only the `pyhive-integration==` pin in `manifest.json`. Don't change the component `version`; that happens at release.
- Install and test:
  ```bash
  VIRTUAL_ENV=.venv uv pip install --refresh-package pyhive-integration "pyhive-integration==<target>"
  script/test
  script/lint --check
  python3 .github/scripts/hassfest.py      # needs Docker; the pyhive line should be a warning
  ```
  (`--refresh-package` matters for a release published in the last few hours.)
- The tests mock the library. On 2.x, also run an offline session from the bundled `data/data.json` (username `use@file.com`) and call the real getters for every platform.
- Where the diff showed behaviour changes, add tests for them.
- For a pre-release target, the next step is a component beta (`/release`). For a stable target, it can go in the next stable release.

## 4. Report
Report:
- the version change, and how it compares with core's pin
- a short summary of the library changes that matter to this component, with any risks
- the test, lint and hassfest results
- whether it's ready to merge, and whether it can ship stable or only as a beta

If a bot PR has no CI runs, remind the user to close and reopen it, or to set up the `BOT_TOKEN` secret. Don't commit, push, or merge unless asked.
