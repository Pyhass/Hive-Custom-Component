"""Tests for the Hive sensors added by this component."""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import PERCENTAGE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import make_device


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_battery_sensor(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Battery level is exposed as a diagnostic percentage sensor."""
    await _setup(hass, mock_config_entry)

    state = hass.states.get("sensor.lounge_trv_battery")
    assert state is not None
    assert state.state == "87"
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
    assert state.attributes["device_class"] == "battery"

    entry = er.async_get(hass).async_get("sensor.lounge_trv_battery")
    assert entry.unique_id == "trv-1-Battery"
    assert entry.entity_category == "diagnostic"


@pytest.mark.parametrize(
    "sensor_devices",
    [
        [
            make_device("Battery", 50, online=False),
            make_device("Availability", "Offline"),
        ]
    ],
)
async def test_offline_device(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Offline devices are unavailable, but their Availability sensor still reports."""
    await _setup(hass, mock_config_entry)

    assert hass.states.get("sensor.lounge_trv_battery").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.lounge_trv_availability").state == "Offline"


@pytest.mark.parametrize(
    "sensor_devices", [[make_device("Heating_Mode", "SCHEDULE", name="Thermostat")]]
)
async def test_heating_mode_sensor(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Heating mode is an enum sensor with lower-cased state."""
    mock_hive.heating.getScheduleNowNextLater = AsyncMock(return_value=None)

    await _setup(hass, mock_config_entry)

    state = hass.states.get("sensor.thermostat_heating_mode")
    assert state.state == "schedule"
    assert state.attributes["options"] == ["schedule", "manual", "off"]
    assert state.attributes["Schedule not active"] == ""


@pytest.mark.parametrize(
    "sensor_devices", [[make_device("Hotwater_Mode", "ON", name="Hot Water")]]
)
async def test_hotwater_mode_schedule_attributes(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Hot water mode shows the now/next schedule slots as attributes."""

    def slot(status: str, start: int, end: int) -> dict[str, Any]:
        return {
            "value": {"status": status},
            "start": start * 60,
            "Start_DateTime": datetime(2026, 1, 1, start, 0),
            "End_DateTime": datetime(2026, 1, 1, end, 0),
        }

    mock_hive.hotwater.getScheduleNowNextLater = AsyncMock(
        return_value={"now": slot("ON", 6, 8), "next": slot("OFF", 8, 17)}
    )

    await _setup(hass, mock_config_entry)

    state = hass.states.get("sensor.hot_water_hotwater_mode")
    assert state.state == "on"
    assert state.attributes["Now"] == "ON : 06:00 - 08:00"
    assert state.attributes["Next"] == "OFF : 08:00 - 17:00"
    assert "Later" not in state.attributes


@pytest.mark.parametrize("sensor_devices", [[make_device("Unknown_Type", 1)]])
async def test_unknown_sensor_type_is_ignored(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Device types without a description don't create entities."""
    await _setup(hass, mock_config_entry)

    assert hass.states.async_entity_ids("sensor") == []
