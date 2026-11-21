"""Tests for setting up and unloading the Hive integration."""

from unittest.mock import MagicMock

from aiohttp.web_exceptions import HTTPServiceUnavailable
from apyhiveapi.helper.hive_exceptions import HiveReauthRequired
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component

from custom_components.hive import async_remove_config_entry_device, refresh_system
from custom_components.hive.const import DOMAIN

from .conftest import HUB_ID
from .test_light import WARM_WHITE


async def test_setup_and_unload(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The entry loads, registers the hub and unloads cleanly."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is mock_hive
    hub = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, HUB_ID), mock_config_entry.entry_id
    )
    assert hub is not None
    assert hub.name == "Hive Hub"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state", "reauth"),
    [
        # pyhive-integration 2.0 adds HiveConnectionError (retry) and
        # HiveUnknownConfiguration (reauth). Add them back with that bump.
        (HTTPServiceUnavailable(), ConfigEntryState.SETUP_RETRY, False),
        (HiveReauthRequired(), ConfigEntryState.SETUP_ERROR, True),
    ],
)
async def test_setup_failures(
    hass: HomeAssistant,
    mock_hive: MagicMock,
    mock_auth: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    state: ConfigEntryState,
    reauth: bool,
) -> None:
    """Network errors retry setup, auth errors start reauth."""
    mock_hive.session.startSession.side_effect = exception
    # Keep the reauth flow waiting on the 2FA step so it can be observed.
    mock_auth.login.return_value = {"ChallengeName": "SMS_MFA"}
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is state
    reauth_flows = mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
    assert bool(list(reauth_flows)) is reauth


@pytest.mark.parametrize(
    ("options", "interval"), [({}, 120), ({CONF_SCAN_INTERVAL: 60}, 60)]
)
async def test_scan_interval_passed_to_session(
    hass: HomeAssistant,
    mock_hive: MagicMock,
    mock_config_entry: MockConfigEntry,
    options: dict,
    interval: int,
) -> None:
    """The scan interval option (default 120s) is handed to the Hive session."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options=options)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    session_config = mock_hive.session.startSession.await_args.args[0]
    assert session_config["options"] == {CONF_SCAN_INTERVAL: interval}
    assert session_config["tokens"] == mock_config_entry.data["tokens"]


@pytest.mark.usefixtures("setup_integration")
async def test_only_platforms_with_devices_are_set_up(hass: HomeAssistant) -> None:
    """Platforms Hive reports no devices for aren't loaded."""
    assert "hive.sensor" in hass.config.components
    for platform in ("binary_sensor", "climate", "light", "switch", "water_heater"):
        assert f"hive.{platform}" not in hass.config.components


async def test_reload_skips_platforms_never_set_up(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Reload only unloads the platforms that were set up (#208).

    Hive has no lights here, but another integration loaded the light component.
    Before HA 2026.11, unloading the light platform for this entry raised and
    aborted the reload; HA now logs a warning instead. Neither should happen.
    """
    assert await async_setup_component(hass, "light", {})
    await hass.async_block_till_done()

    assert await hass.config_entries.async_reload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert setup_integration.state is ConfigEntryState.LOADED
    assert "Ignored unload request" not in caplog.text


async def test_reload_picks_up_new_device_types(
    hass: HomeAssistant, mock_hive: MagicMock, setup_integration: MockConfigEntry
) -> None:
    """A device type added since setup (e.g. a new light) appears after a reload."""
    assert "hive.light" not in hass.config.components
    devices = {**mock_hive.session.deviceList, "light": [WARM_WHITE]}
    mock_hive.session.startSession.return_value = devices
    mock_hive.session.deviceList = devices

    assert await hass.config_entries.async_reload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert setup_integration.state is ConfigEntryState.LOADED
    assert "hive.light" in hass.config.components
    assert hass.states.get("light.kitchen") is not None


async def test_remove_entry_forgets_device(
    hass: HomeAssistant,
    mock_hive: MagicMock,
    mock_auth: MagicMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Deleting the entry deregisters this Home Assistant device from Hive."""
    await hass.config_entries.async_remove(setup_integration.entry_id)
    await hass.async_block_till_done()

    mock_auth.forget_device.assert_awaited_once_with("access-token", "device-key")


async def test_remove_device(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Any Hive device can be removed from the device page."""
    hub = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, HUB_ID), setup_integration.entry_id
    )

    assert await async_remove_config_entry_device(hass, setup_integration, hub)


async def test_refresh_system(hass: HomeAssistant) -> None:
    """refresh_system runs the method, then signals every entity to update."""
    calls = []
    signals = []
    async_dispatcher_connect(hass, DOMAIN, lambda: signals.append(True))

    class FakeEntity:
        def __init__(self) -> None:
            self.hass = hass

        @refresh_system
        async def turn_on(self, value: int) -> None:
            calls.append(value)

    await FakeEntity().turn_on(5)
    await hass.async_block_till_done()

    assert calls == [5]
    assert signals == [True]
