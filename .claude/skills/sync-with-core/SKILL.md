---
name: sync-with-core
description: Fetch the latest Home Assistant core hive integration (homeassistant/components/hive) from GitHub, compare it with custom_components/hive, and merge core's changes into this repo - new and removed files, and core's edits to the files we keep our own copies of (sensor.py, __init__.py, config_flow.py, const.py, services.yaml, strings.json, icons.json) - while keeping this repo's deliberate differences. Pass `full` for a full scan that compares every file with core's current version, not just what core changed since the last sync. Leaves everything uncommitted for the user to review. Use after a new HA release or beta, when core changes the hive integration, when an import from core fails, or when the user asks to sync with or compare against core.
---

# Sync with core

Principle 1 in `CLAUDE.md` applies: this component re-exports core's hive integration and only keeps its own code where it has to differ from core. Syncing means taking everything core changed, while keeping the differences that are the reason this repo exists.

**Never commit, stage, push or stash-drop anything.** Leave every change in the working tree for the user to review, and finish with a report of what changed (step 6). Before starting, run `git status --short`. If there are uncommitted changes in files you're about to merge, tell the user and ask before going on, so their work and the merge don't get mixed up.

## Modes
- **Default** (`/sync-with-core`, or with a target such as `/sync-with-core dev`): merge only what core changed between the last sync (base) and the target. Fast, but it never looks at a file core didn't touch. So drift in our own copies, such as a difference that's no longer needed or a core fix we never took, goes unnoticed.
- **Full scan** (`/sync-with-core full`, optionally with a target, e.g. `/sync-with-core full dev`; also when the user asks for a "full scan", "full compare" or to "check all files"): do everything the default mode does, and also step 4b. That compares **every** file in `custom_components/hive` with core's version at the target, whether core changed it or not. Use it on the first run, after a long gap, or whenever the base in `.github/core_sync.json` might be wrong.

## 1. Pick the versions
- **Target** (what to merge in): the latest stable core release, unless the user names one (`dev`, a beta tag like `2026.12.0b1`, or another tag). Stable is the default because code from `dev` can use HA APIs our users don't have yet.
  ```bash
  TARGET=$(gh release view --repo home-assistant/core --json tagName -q .tagName)
  ```
- **Base** (core as it was when we last synced): read it from `.github/core_sync.json`, which looks like `{"ref": "2026.11.2"}`. The merge only applies what core changed between base and target, so our own changes are kept.
  If the file doesn't exist yet (first run), use the HA version the tests run against, `.venv/bin/python -c "import homeassistant.const as c; print(c.__version__)"`, and tell the user the first merge is approximate, so they should review every hunk.

If base and target are the same, there's nothing new from core. In default mode, say so and stop. In full-scan mode, skip the merge (step 4) and go on to step 4b.

## 2. Fetch both versions of core
```bash
S=<scratchpad>/core-sync; rm -rf "$S"; mkdir -p "$S"
for ref in "$BASE" "$TARGET"; do
  mkdir -p "$S/$ref"
  for f in $(gh api "repos/home-assistant/core/contents/homeassistant/components/hive?ref=$ref" --jq '.[] | select(.type=="file") | .name'); do
    gh api "repos/home-assistant/core/contents/homeassistant/components/hive/$f?ref=$ref" --jq .content | base64 -d > "$S/$ref/$f"
  done
done
diff -rq "$S/$BASE" "$S/$TARGET"    # what core changed
ls custom_components/hive
```
If a local clone of core exists (see "Related repos" in `CLAUDE.md`), you can `git -C <clone> fetch upstream --tags` and use `git -C <clone> show <ref>:homeassistant/components/hive/<file>` instead. Ignore `__pycache__`.

## 3. Sort every file
| File | How to sync it |
|---|---|
| Re-exported module (`binary_sensor.py`, `climate.py`, `light.py`, `switch.py`, `water_heater.py`, `entity.py`, `services.py`) | Leave it alone. It's one line, `from homeassistant.components.hive.<name> import *`, so core's changes to it reach users automatically. That's expected, and this repo needs no change. Don't diff it, edit it, or list it as a change in the report |
| Our own copy (`sensor.py`, `__init__.py`, `config_flow.py`, `const.py`, `services.yaml`, `strings.json`, `icons.json`) | Three-way merge (step 4) |
| `manifest.json` | Never merge. Our `version`, exact `requirements` pin and codeowners differ on purpose (principle 2). Only add new keys core introduces, such as `quality_scale` or `loggers` |
| `translations/en.json` | Not in core. Regenerate it from `strings.json` with `.venv/bin/python script/gen_translations.py` |
| New in core | Step 5 |
| Gone from core | Step 5 |

## 4. Merge our copies
For each file in the "our own copy" row that core changed between base and target:
```bash
cp custom_components/hive/<f> "$S/ours-<f>"      # keep a copy to compare against afterwards
git merge-file --diff3 -L ours -L "core $BASE" -L "core $TARGET" \
  custom_components/hive/<f> "$S/$BASE/<f>" "$S/$TARGET/<f>"
```
`git merge-file` writes the merged result into our file. It exits with the number of conflicts, so a non-zero exit is normal here.
- **JSON files**: if ours is indented differently from core, the merge is noisy. Reformat ours to core's style first (`jq --indent 2 . <f>`, which keeps key order). That's a whitespace-only change the user will see in the diff, so mention it.
- **Resolving conflicts**: take core's change unless it would undo one of our deliberate differences. The usual differences are the extra attribute sensors in `sensor.py`, our config flow and options flow (scan interval, 2FA debug and device registration) in `config_flow.py` and `strings.json`, and calling core's setup helpers ourselves in `__init__.py`, because core's own `__init__.py` never runs when we replace the `hive` domain. `git log -p -- <file>` shows why we changed something.
- If you can't tell which side is right, leave the conflict markers in place and list the conflict in the report. Lint and tests will fail until the user decides, which is what you want.
- Check every merged file for code that relies on something newer than the minimum HA version in `hacs.json`. Guard it with `try`/`except ImportError`, or tell the user the minimum needs to go up.

## 4b. Full scan (full-scan mode only)
Compare every file on both sides with core at the target, two-way (ours against `$S/$TARGET`), whether or not core changed it. This doesn't depend on the base, so it also catches drift the merge can't see.

**Re-exported modules**: don't diff core's code (it reaches users automatically). Only check that:
- the file is exactly `from homeassistant.components.hive.<name> import *`, with nothing local added. If local code has crept in, report it, because it's a local override (last resort, `CLAUDE.md`);
- core still has `<name>.py` at the target;
- it's listed in the `F403` per-file-ignores in `pyproject.toml`;
- any guarded fallback (`try`/`except ImportError`) is still needed. If the `hacs.json` minimum already has the file, the guard can go.

**Our own copies** (`sensor.py`, `__init__.py`, `config_flow.py`, `const.py`, `services.yaml`, `strings.json`, `icons.json`), plus `manifest.json` keys:
```bash
diff -u "$S/$TARGET/<f>" custom_components/hive/<f>
# JSON: compare content, not formatting
diff <(jq -S . "$S/$TARGET/<f>") <(jq -S . custom_components/hive/<f>)
```
Sort every difference (hunk) into one of:
- **Deliberate**: one of our reasons to differ (the extra attribute sensors, our config and options flow, calling core's setup helpers in `__init__.py`, the `manifest.json` pin and version). Keep it. `git log -p -S '<text>' -- <file>` usually shows why it was added.
- **Outdated**: core has moved on and our copy still has the old code (a renamed API, a bug fix, a removed or changed key, style core adopted). Take core's version, unless it needs an HA newer than the `hacs.json` minimum.
- **Unclear**: you can't tell. Don't change it. List it for the user.

Also look for:
- code in our copy that duplicates something core now provides (e.g. a helper or constant core's `const.py` now has). Switch to core's when we can import it rather than copy it;
- local files that core doesn't have, other than `translations/`. Report them, so the user can confirm each one is still needed;
- for `sensor.py`: whether any sensor we add locally is now in core's `sensor.py`. If so, ours is a duplicate and can go.

Apply only the "outdated" changes. Leave "deliberate" and "unclear" as they are.

## 5. Add or remove files
- **New module in core** (as `services.py` was in 2026.11): add a re-export. `hacs.json` allows older HA versions that don't have the file, so guard the import:
  ```python
  """Re-export core's hive <name> (added in Home Assistant <version>)."""

  try:
      from homeassistant.components.hive.<name> import *  # noqa: F403
  except ImportError:  # Home Assistant < <version> has no hive/<name>.py.
      pass
  ```
  If core added the file in a version at or below the `hacs.json` minimum, skip the guard and write the plain one line. Either way, add the file to the `F403` per-file-ignores in `pyproject.toml`, next to the other re-exports.
  Then read core's `__init__.py`. If it calls something from the new file, our `__init__.py` must call it too. Import it from the local re-export (`from .<name> import …`). Once `hacs.json` reaches that HA version, the guard can go.
- **New platform** (a new `<platform>.py` and a new entry in core's `PLATFORMS`): add the re-export and add the platform to `PLATFORMS` / `PLATFORM_LOOKUP` in our `const.py`. Point it out in the report, because it changes the entities users get.
- **New data file**: copy it as it is.
- **Removed or renamed in core**: remove or rename our file to match. Keep a guarded fallback if an older HA version that `hacs.json` still allows has the old name.
- **A re-exported module we'd now need to change**: don't copy it here. Replacing a re-export with a local module is a last resort (`CLAUDE.md`), so raise it with the user.

Finally, record the new base: write `{"ref": "<TARGET>"}` to `.github/core_sync.json`. It stays uncommitted like everything else.

## 6. Verify and report
```bash
script/lint --check   # without --check it reformats every file, not just the merged ones
script/test
.venv/bin/python -c "import custom_components.hive"
```
To tell whether a failure is new, run the tests on a clean copy without touching the user's working tree:
```bash
git worktree add "$S/clean" HEAD
(cd "$S/clean" && VENV="$OLDPWD/.venv" script/test -q)
git worktree remove --force "$S/clean"
```
If the target is newer than the HA version in `.venv`, also run the tests against it (the `triage-compat` skill shows how to set up `.venv-ha-beta`).

Then report to the user:
- the base and target versions;
- each file added, removed or merged, with a one-line summary of what core changed in it;
- every conflict and how you resolved it, and any you left for them;
- anything that changes behaviour for users (new platforms, entities or services);
- in full-scan mode, a table of every file checked, with each difference marked deliberate (kept), outdated (taken from core) or unclear (left for them). List the re-export checks too, so the user can see nothing was skipped;
- test and lint results, and which failures were already there before the merge.

Say that nothing has been committed, and that `git diff` shows the full change.
