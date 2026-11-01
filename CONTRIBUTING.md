# Contributing

Thanks for helping out. This is a Home Assistant custom component for Hive. It is
installed through HACS and builds on the Hive integration in Home Assistant core.

## Set up

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and `jq`.

```bash
script/setup      # .venv with Python 3.14, Home Assistant and the test tools, same as CI
```

## Everyday commands

| Command | What it does |
|---|---|
| `script/test` | Run the tests. Extra arguments go to pytest: `script/test tests/test_climate.py -x` |
| `script/lint` | Fix lint and formatting, and regenerate `translations/en.json` |
| `script/lint --check` | The checks CI runs, without changing anything |
| `script/develop` | Run Home Assistant at http://localhost:8123 with this component loaded |

`script/develop` keeps its Home Assistant instance in `config/`. The first time,
go through onboarding, then add the Hive integration with a real Hive account.
Restart it after changing code.

## How the component is put together

- `sensor.py` and `config_flow.py` are this repo's own code. `__init__.py` is too.
- `binary_sensor.py`, `climate.py`, `light.py`, `switch.py`, `water_heater.py` and
  `entity.py` are one-line re-exports of Home Assistant core's hive platforms. To
  change their behaviour, either replace the re-export with a real module here, or
  change it in core.
- Talking to Hive is done by [`pyhive-integration`](https://pypi.org/project/pyhive-integration/)
  (imported as `apyhiveapi`). Its version is pinned in `manifest.json`.
- Text shown in the UI lives in `strings.json`. Run `script/lint` after editing it;
  `translations/en.json` is generated from it and a test checks they match.

## Tests

The tests start a real Home Assistant in memory and mock the Hive API, so they
need no network or account. There is one file per platform. The fixtures in
`tests/conftest.py` do most of the work:

- `make_device(...)` builds a device the way pyhive returns it.
- Parametrize `sensor_devices` or `platform_devices` to choose what Hive reports.
- `setup_integration` loads the integration with those devices.

```python
@pytest.mark.parametrize(
    "platform_devices",
    [{"switch": [make_device("activeplug", True, ha_type="switch", ha_name="Fan")]}],
)
@pytest.mark.usefixtures("setup_integration")
async def test_plug(hass: HomeAssistant) -> None:
    assert hass.states.get("switch.fan").state == "on"
```

Add or update a test with every behaviour change.

## Pull requests

- Branch from `master` and open the PR against `master`.
- CI must pass: HACS validation, hassfest, lint and tests.
- @KJonline is asked to review automatically.
- Don't bump `version` in `manifest.json` unless the PR is meant to be released
  (see [MAINTAINING.md](MAINTAINING.md)).
