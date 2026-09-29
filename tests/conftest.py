"""Fixtures for Hive custom component tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from custom_components.hive.const import DOMAIN

USERNAME = "user@example.com"
PASSWORD = "test-password"
HUB_ID = "hub-1"
TOKENS = {
    "AuthenticationResult": {
        "AccessToken": "access-token",
        "RefreshToken": "refresh-token",
        "IdToken": "id-token",
    }
}
DEVICE_DATA = ["device-group-key", "device-key", "device-password"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/hive instead of the core hive integration."""


def make_device(
    hive_type: str,
    state: Any = None,
    *,
    ha_type: str = "sensor",
    hive_id: str = "trv-1",
    name: str = "Lounge TRV",
    ha_name: str | None = None,
    online: bool = True,
    status: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build a device dict shaped like the ones pyhive returns.

    status defaults to {"state": state}; extra keys (e.g. temperatureunit, min_temp)
    are added at the top level, the way pyhive's addList adds them.
    """
    return {
        "hiveID": hive_id,
        "hiveName": name,
        "hiveType": hive_type,
        "haType": ha_type,
        "haName": ha_name or f"{name} {hive_type.replace('_', ' ')}",
        "device_id": hive_id,
        "device_name": name,
        "parentDevice": HUB_ID,
        "deviceData": {
            "model": "TRV001",
            "manufacturer": "Hive",
            "version": "1.0.0",
            "online": online,
        },
        "status": {"state": state} if status is None else status,
        **extra,
    }


HUB_DEVICE = {
    "device_id": HUB_ID,
    "hiveName": "Hive Hub",
    "deviceData": {"model": "NANO2", "manufacturer": "Hive", "version": "4.0.0"},
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for an account that finished setup."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=USERNAME,
        unique_id=USERNAME,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            "tokens": TOKENS,
            "device_data": DEVICE_DATA,
        },
    )


@pytest.fixture
def sensor_devices() -> list[dict[str, Any]]:
    """Sensor devices returned by the mocked Hive session."""
    return [make_device("Battery", 87)]


@pytest.fixture
def platform_devices() -> dict[str, list[dict[str, Any]]]:
    """Devices for the other platforms, keyed like pyhive's deviceList."""
    return {}


def _echo(device: dict[str, Any]) -> dict[str, Any]:
    return device


@pytest.fixture
def mock_hive(
    sensor_devices: list[dict[str, Any]],
    platform_devices: dict[str, list[dict[str, Any]]],
) -> Generator[MagicMock]:
    """Patch the Hive API client used by async_setup_entry.

    Every getter hands the device back unchanged, so a test controls entity
    state through the device dicts it passes in.
    """
    devices = {"parent": [HUB_DEVICE], "sensor": sensor_devices, **platform_devices}
    hive = MagicMock()
    hive.session.startSession = AsyncMock(return_value=devices)
    hive.session.deviceList = devices
    hive.session.updateData = AsyncMock()
    hive.sensor.getSensor = AsyncMock(side_effect=_echo)
    hive.heating.getClimate = AsyncMock(side_effect=_echo)
    hive.hotwater.getWaterHeater = AsyncMock(side_effect=_echo)
    hive.light.getLight = AsyncMock(side_effect=_echo)
    hive.switch.getSwitch = AsyncMock(side_effect=_echo)
    hive.updateInterval = AsyncMock()
    with patch("custom_components.hive.Hive", return_value=hive):
        yield hive


@pytest.fixture
def mock_auth() -> Generator[MagicMock]:
    """Patch the Hive Auth client used by the config flow."""
    auth = MagicMock()
    auth.login = AsyncMock(return_value=TOKENS)
    auth.sms_2fa = AsyncMock(return_value=TOKENS)
    auth.device_registration = AsyncMock()
    auth.get_device_data = AsyncMock(return_value=DEVICE_DATA)
    auth.is_device_registered = AsyncMock(return_value=True)
    auth.forget_device = AsyncMock()
    with (
        patch("custom_components.hive.config_flow.Auth", return_value=auth),
        patch("custom_components.hive.Auth", return_value=auth),
    ):
        yield auth


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Stop config flow tests from setting up the integration."""
    with patch(
        "custom_components.hive.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the integration with the mocked Hive client."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
