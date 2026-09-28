"""Fixtures for Hive custom component tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

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
    state: Any,
    *,
    hive_id: str = "trv-1",
    name: str = "Lounge TRV",
    online: bool = True,
) -> dict[str, Any]:
    """Build a device dict shaped like the ones pyhive returns."""
    return {
        "hiveID": hive_id,
        "hiveName": name,
        "hiveType": hive_type,
        "haType": "sensor",
        "haName": f"{name} {hive_type.replace('_', ' ')}",
        "device_id": hive_id,
        "device_name": name,
        "parentDevice": HUB_ID,
        "deviceData": {
            "model": "TRV001",
            "manufacturer": "Hive",
            "version": "1.0.0",
            "online": online,
        },
        "status": {"state": state},
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
def mock_hive(sensor_devices: list[dict[str, Any]]) -> Generator[MagicMock]:
    """Patch the Hive API client used by async_setup_entry."""
    devices = {"parent": [HUB_DEVICE], "sensor": sensor_devices}
    hive = MagicMock()
    hive.session.startSession = AsyncMock(return_value=devices)
    hive.session.deviceList = devices
    hive.session.updateData = AsyncMock()
    hive.sensor.getSensor = AsyncMock(side_effect=lambda device: device)
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
    with patch("custom_components.hive.config_flow.Auth", return_value=auth):
        yield auth


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Stop config flow tests from setting up the integration."""
    with patch(
        "custom_components.hive.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry
