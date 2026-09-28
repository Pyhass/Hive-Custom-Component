"""Tests for setting up and unloading the Hive integration."""

from unittest.mock import MagicMock

from aiohttp.web_exceptions import HTTPServiceUnavailable
from apyhiveapi.helper.hive_exceptions import HiveReauthRequired
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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
