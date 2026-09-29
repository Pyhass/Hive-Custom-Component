"""Tests for the Hive sensors added by this component."""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import PERCENTAGE, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.hive import sensor

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


@pytest.mark.parametrize(
    ("sensor_devices", "entity_id", "expected"),
    [
        (
            [make_device("Power", 42.5, name="Fan Plug")],
            "sensor.fan_plug_power",
            {"state": "42.5", "unit_of_measurement": "W", "device_class": "power"},
        ),
        (
            [make_device("Current_Temperature", 19.5, name="Hallway")],
            "sensor.hallway_current_temperature",
            {
                "state": "19.5",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
            },
        ),
        (
            [make_device("Heating_Current_Temperature", 20.1, name="Heating")],
            "sensor.heating_heating_current_temperature",
            {
                "state": "20.1",
                "unit_of_measurement": "°C",
                "state_class": "measurement",
            },
        ),
        (
            [make_device("Heating_Target_Temperature", 21, name="Heating")],
            "sensor.heating_heating_target_temperature",
            {"state": "21", "icon": "mdi:thermometer"},
        ),
        (
            [make_device("Mode", "SCHEDULE", name="Fan Plug")],
            "sensor.fan_plug_mode",
            {"state": "SCHEDULE", "icon": "mdi:eye"},
        ),
    ],
)
async def test_value_sensors(
    hass: HomeAssistant,
    mock_hive: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected: dict[str, str],
) -> None:
    """Each simple sensor type reports its value with the right unit and class."""
    await _setup(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state.state == expected.pop("state")
    for attribute, value in expected.items():
        assert state.attributes[attribute] == value


@pytest.mark.parametrize(
    "sensor_devices", [[make_device("Heating_Mode", "MANUAL", name="Thermostat")]]
)
async def test_heating_mode_schedule_attributes(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Heating mode shows now/next/later target temperatures; incomplete slots are skipped."""

    def slot(target: float, start: int, end: int) -> dict[str, Any]:
        return {
            "value": {"target": target},
            "start": start * 60,
            "Start_DateTime": datetime(2026, 1, 1, start, 0),
            "End_DateTime": datetime(2026, 1, 1, end, 0),
        }

    mock_hive.heating.getScheduleNowNextLater = AsyncMock(
        return_value={
            "now": slot(20, 6, 9),
            "next": slot(16, 9, 17),
            "later": slot(21, 17, 22),
        }
    )

    await _setup(hass, mock_config_entry)

    state = hass.states.get("sensor.thermostat_heating_mode")
    assert state.state == "manual"
    assert state.attributes["Now"] == "20 °C : 06:00 - 09:00"
    assert state.attributes["Next"] == "16 °C : 09:00 - 17:00"
    assert state.attributes["Later"] == "21 °C : 17:00 - 22:00"


INCOMPLETE_SCHEDULES = [
    {},
    {"now": {"value": {}, "start": 0}, "next": {"value": {}}, "later": {}},
]


@pytest.mark.parametrize(
    "sensor_devices",
    [
        [
            make_device("Heating_Mode", "SCHEDULE", name="Thermostat"),
            make_device("Hotwater_Mode", "SCHEDULE", name="Hot Water"),
        ]
    ],
)
@pytest.mark.parametrize("schedule", INCOMPLETE_SCHEDULES)
async def test_incomplete_schedule(
    hass: HomeAssistant,
    mock_hive: MagicMock,
    mock_config_entry: MockConfigEntry,
    schedule: dict[str, Any],
) -> None:
    """Schedule slots missing a target, status or time are left out."""
    mock_hive.heating.getScheduleNowNextLater = AsyncMock(return_value=schedule)
    mock_hive.hotwater.getScheduleNowNextLater = AsyncMock(return_value=schedule)

    await _setup(hass, mock_config_entry)

    for entity_id in (
        "sensor.thermostat_heating_mode",
        "sensor.hot_water_hotwater_mode",
    ):
        attributes = hass.states.get(entity_id).attributes
        assert not {"Now", "Next", "Later", "Schedule not active"} & set(attributes)


@pytest.mark.parametrize(
    "sensor_devices", [[make_device("Hotwater_Mode", "SCHEDULE", name="Hot Water")]]
)
async def test_hotwater_mode_later_slot(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Hot water shows the later slot when Hive sends one."""
    mock_hive.hotwater.getScheduleNowNextLater = AsyncMock(
        return_value={
            "later": {
                "value": {"status": "ON"},
                "start": 1020,
                "Start_DateTime": datetime(2026, 1, 1, 17, 0),
                "End_DateTime": datetime(2026, 1, 1, 18, 0),
            },
        }
    )

    await _setup(hass, mock_config_entry)

    attributes = hass.states.get("sensor.hot_water_hotwater_mode").attributes
    assert attributes["Later"] == "ON : 17:00 - 18:00"


@pytest.mark.parametrize(
    "sensor_devices", [[make_device("Hotwater_Mode", "OFF", name="Hot Water")]]
)
async def test_hotwater_mode_no_schedule(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Without a schedule the hot water sensor says so."""
    mock_hive.hotwater.getScheduleNowNextLater = AsyncMock(return_value=None)

    await _setup(hass, mock_config_entry)

    state = hass.states.get("sensor.hot_water_hotwater_mode")
    assert state.state == "off"
    assert state.attributes["Schedule not active"] == ""


@pytest.mark.parametrize(
    "sensor_devices", [[make_device("Heating_Mode", None, name="Thermostat")]]
)
async def test_mode_sensor_without_state(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A mode sensor with no state reads unknown instead of failing."""
    mock_hive.heating.getScheduleNowNextLater = AsyncMock(return_value=None)

    await _setup(hass, mock_config_entry)

    assert hass.states.get("sensor.thermostat_heating_mode").state == STATE_UNKNOWN


async def test_sensor_platform_without_devices(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The sensor platform adds nothing when Hive reports no sensors."""
    hive = MagicMock()
    hive.session.deviceList = {"sensor": []}
    mock_config_entry.runtime_data = hive
    add_entities = MagicMock()

    await sensor.async_setup_entry(hass, mock_config_entry, add_entities)

    add_entities.assert_not_called()
