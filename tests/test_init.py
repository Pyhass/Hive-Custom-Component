"""Tests for setting up and unloading the Hive integration."""

from unittest.mock import MagicMock

from aiohttp.web_exceptions import HTTPServiceUnavailable
from apyhiveapi.helper.hive_exceptions import HiveReauthRequired
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
<<<<<<< HEAD
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from custom_components.hive import async_remove_config_entry_device, refresh_system
=======
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

>>>>>>> 1a55d87294f3c1fd059bd190faec008e020cc2cf
from custom_components.hive.const import DOMAIN

from .conftest import HUB_ID


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
    ("exception", "state"),
    [
        (HTTPServiceUnavailable(), ConfigEntryState.SETUP_RETRY),
        (HiveReauthRequired(), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_failures(
    hass: HomeAssistant,
    mock_hive: MagicMock,
    mock_auth: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    state: ConfigEntryState,
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
    assert bool(list(reauth_flows)) is isinstance(exception, HiveReauthRequired)
<<<<<<< HEAD


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
=======
>>>>>>> 1a55d87294f3c1fd059bd190faec008e020cc2cf
