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

## Related repos

Every change to this repo has to be weighed against two other repos:

- **Home Assistant core** (`home-assistant/core`, forked as `Pyhass/core`), and
  its `homeassistant/components/hive` integration.
- **`pyhive-integration`** (`Pyhass/Pyhiveapi` on GitHub, imported as
  `apyhiveapi`), the library pinned in `manifest.json`.

**This repo's Hive code mostly just imports core.** The platform modules
(`binary_sensor.py`, `climate.py`, `light.py`, `switch.py`, `water_heater.py`,
`entity.py`) re-export core's hive integration as they are. Local code exists only
where we have to differ from core, mainly `sensor.py`, plus the setup glue in
`__init__.py`, `config_flow.py` and `const.py`. So before changing something, check
what core does now, and don't copy core code into this repo to change it. When you
change the local code, compare it with core's version so it doesn't drift further
than it has to, and check that every `apyhiveapi` call matches the library
version we pin.

Both repos are usually cloned somewhere on the maintainer's computer. Look for the
local clones first, for example by searching nearby directories for a git repo
whose remote matches one of the names above, and don't assume a path. Core's clone
may be a fork, so check its `upstream` remote as well as `origin`. If you can't
find one, ask the user before cloning it, or fall back to GitHub (`gh`). When a
change here should also go upstream (principle 1), say which repo it belongs in.

## Reviewing pull requests

These rules apply to every review, by hand or by the Claude Code workflow
(`.github/workflows/claude.yml`). In CI there are no local clones: fetch from
GitHub instead.

- **Check every `apyhiveapi` call against the version the PR pins.** The tests
  mock the library with `MagicMock`, so a method that doesn't exist still passes
  CI. Check that each method, attribute and exception exists in the pinned
  library, and quote where it's defined. In the review workflow, the pinned
  wheel is unpacked at `.pyhive-src/apyhiveapi/`. pyhive 1.0.x uses camelCase
  names (`getTargetTemperature`). 2.0 uses snake_case (`get_target_temperature`),
  with camelCase aliases in `helper/compat_aliases.py` for only some of them.
- **Compare local code with core's hive integration.** It's at
  `https://raw.githubusercontent.com/home-assistant/core/<ref>/homeassistant/components/hive/<file>`,
  where `<ref>` is in `.github/core_sync.json`, or `dev` for core's latest.
  Changes to `sensor.py`, `__init__.py`, `config_flow.py`, `const.py`,
  `strings.json` or `services.yaml` must keep the deliberate differences
  (principle 1) and not drift further. Re-export modules must stay one-line
  imports. Core's `async_setup` never runs here, so anything it registers
  (services) must be registered by our `__init__.py`.
- **Check Home Assistant versions.** Code must work on the minimum in
  `hacs.json` and on the version the tests pin (`pytest-homeassistant` in
  `requirements_test.txt`). Use contributors.home-assistant.io and the core source
  for API changes.
- **Know which line the PR is on.** A PR into `master` must keep a stable
  pyhive pin. A PR into `dev` may pin a pyhive beta. For a merge of `master`
  into `dev`, review the conflict resolutions and every call that differs
  between the two pyhive versions.
- **Check Home Assistant best practices** for local code (see
  [Home Assistant best practices](#home-assistant-best-practices)).
- **Protect users' setups.** Changed unique IDs or entity IDs orphan entities
  and break automations. Auth failures must raise `ConfigEntryAuthFailed`, so
  users can reauthenticate without deleting the integration. New, renamed or
  removed entities, attributes and services belong in the PR description.

## Home Assistant best practices

This is a custom component, but it inherits Home Assistant's integration
standards. Local code should meet them the way a core integration would. Apply
them when writing code and in every review. The rules are the
[integration quality scale](https://contributors.home-assistant.io/core/quality-scale/rules/)
(one page per rule at `https://contributors.home-assistant.io/core/quality-scale/<rule>/`)
and the [developer docs](https://contributors.home-assistant.io/core/). They moved
from developers.home-assistant.io, which now redirects there.
Fetch the page for a rule rather than relying on memory: they change.

The ones that come up most in this repo's local code:

- **Config entries:**
  - keep the Hive client in `entry.runtime_data`, not `hass.data` (`runtime-data`);
  - raise `ConfigEntryNotReady` or `ConfigEntryAuthFailed` from setup
    (`test-before-setup`, `reauthentication-flow`);
  - unload everything that was set up (`config-entry-unloading`).
- **Services** are registered in `async_setup`, not per entry (`action-setup`),
  and raise `ServiceValidationError` or `HomeAssistantError` with a translation
  key (`action-exceptions`, `exception-translations`).
- **Entities:**
  - `_attr_has_entity_name = True` and a `translation_key` instead of hard-coded
    names (`has-entity-name`, `entity-translations`);
  - a stable `unique_id` (`entity-unique-id`);
  - the correct `device_class`, `state_class` and `entity_category`
    (`entity-device-class`, `entity-category`);
  - noisy or rarely used entities disabled by default
    (`entity-disabled-by-default`);
  - `available` set from the device's online state (`entity-unavailable`), and
    a single log line when a device goes unavailable and comes back
    (`log-when-unavailable`);
  - `PARALLEL_UPDATES` set in each platform (`parallel-updates`).
- **Devices:** entities are attached to a device with `DeviceInfo` (`devices`).
  Removed devices can be cleaned up (`stale-devices`).
- **Async and I/O:**
  - no blocking calls in the event loop;
  - use the shared session from `aiohttp_client.async_get_clientsession`
    (`inject-websession`, `async-dependency`);
  - sensible polling intervals (`appropriate-polling`).
- **Config flow:**
  - all text in `strings.json`;
  - one entry per account (`unique-config-entry`);
  - the connection tested before the entry is created (`test-before-configure`).
- **Typing:** full type hints on new code (`strict-typing`).

Principle 1 still comes first. Don't replace a re-export with a local copy just to
meet a rule. A gap in core's code is fixed upstream in `home-assistant/core`. Rules
that only apply to core (brands, core documentation, the quality scale declaration
itself) don't apply here.

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

- There are two release lines:
  - **`dev`** is the default branch, for new work and the next
    `pyhive-integration` (currently the 2.0 betas). PRs target `dev`, and betas
    are tagged from it (`--target dev`).
  - **`master`** is the stable line users have now (pyhive 1.0.x). A fix that
    has to reach users before the betas finish goes in a PR to `master`, and is
    released from it (`--target master`). Then merge `master` into `dev`. Keep
    dev's pin, version and 2.0 changes, and rename any 1.0.x-only `apyhiveapi`
    call to its 2.0 name.
  - "Closes #N" only closes issues when a PR merges into `dev`, the default
    branch, so close issues by hand for a `master` PR.
- `script/setup`, `script/test`, `script/lint` (`--check` in CI). `.venv` must be
  Python 3.14 (`script/setup --recreate`).
- Tests mock `apyhiveapi`. When the library changes, also exercise the real code:
  from 2.0 the library ships `apyhiveapi/data/data.json`, and
  `startSession({"username": "use@file.com"})` runs a session from it offline.
- The tag of a release must equal `version` in `manifest.json`. Beta tags (`bN`)
  are always pre-releases, and stable tags never are.
- Don't commit, push, release or merge unless asked. Releases are visible to every
  HACS user.
