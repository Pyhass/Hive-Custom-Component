# Hive Custom Component

A HACS custom component that replaces Home Assistant core's `hive` integration
(same `domain`). Procedures live in [MAINTAINING.md](MAINTAINING.md), setup in
[CONTRIBUTING.md](CONTRIBUTING.md), and step-by-step skills in `.claude/skills/`.

## Why this repo exists

Two principles decide most questions here. Apply them to code, CI, releases and
the skills.

### 1. Extend core, reuse it wherever possible

The component adds capability on top of core's hive integration, such as the extra
attribute sensors in `sensor.py`. It is not a fork.

- Re-export core's platforms (`binary_sensor.py`, `climate.py`, `light.py`,
  `switch.py`, `water_heater.py`, `entity.py`) instead of copying them. Only write
  local code for something core doesn't do, and keep it as small as possible.
- When core changes, adapt to it. Replacing a re-export with a local module is a
  last resort, and the user should know.
- A fix or feature that would help everyone belongs upstream in core or
  `pyhive-integration` as well. This repo can ship it first.

### 2. The opt-in fast channel

Everyone on core's integration gets the official, slower release train. Installing
this component is an opt-in to get changes sooner, and its HACS betas go further
still, as a testing channel.

- `manifest.json` may pin a **newer `pyhive-integration` than core does**, including
  pre-releases. That divergence is the point of the repo, not a mistake.
- The pin stays exact (`==`). Users get the version we tested.
- **Pre-release `pyhive-integration` only ships in component betas** (pre-releases,
  which HACS offers only to users who opt in). A stable component release must pin a
  stable `pyhive-integration`. `.github/scripts/check_release.py` enforces this.
- When cutting a component beta, always check PyPI for the newest
  `pyhive-integration`, pre-releases included, and bump to it first if it's newer
  than the pin (`/bump-pyhive`, then `/release`).
- Never let the fast channel break people. Stable releases need green CI and a
  green Compatibility run.

## What this means for CI

hassfest compares a custom integration's requirements with every core
integration's pins, including core hive's own. With principle 2 that always gives a
`[REQUIREMENTS]` error for `pyhive-integration`: "pins a package Home Assistant
depends on" when we match core, or "is incompatible with …" when we're ahead.
`.github/scripts/hassfest.py` runs the official hassfest image and turns only those
`pyhive-integration` errors into warnings. Every other error still fails, including
conflicts with Home Assistant's own dependencies or package constraints, because
those can break a user's whole installation. Don't loosen the pin to `>=` to
silence it.

## Working here

- `script/setup`, `script/test`, `script/lint` (`--check` in CI). `.venv` must be
  Python 3.14 (`script/setup --recreate`).
- Tests mock `apyhiveapi`. When the library changes, also exercise the real code:
  from 2.0 the library ships `apyhiveapi/data/data.json`, and
  `startSession({"username": "use@file.com"})` runs a session from it offline.
- The tag of a release must equal `version` in `manifest.json`. Beta tags (`bN`)
  are always pre-releases, and stable tags never are.
- Don't commit, push, release or merge unless asked. Releases are visible to every
  HACS user.
