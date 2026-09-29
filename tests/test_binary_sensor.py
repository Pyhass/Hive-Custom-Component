"""Tests for the binary sensors re-exported from Home Assistant core."""

from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import make_device

CONTACT = make_device(
    "contactsensor",
    True,
    ha_type="binary_sensor",
    hive_id="contact-1",
    name="Front Door",
    ha_name="Front Door",
)
MOTION_OFFLINE = make_device(
    "motionsensor",
    False,
    ha_type="binary_sensor",
    hive_id="motion-1",
    name="Hallway",
    ha_name="Hallway",
    online=False,
)
HUB_STATUS_OFFLINE = make_device(
    "Connectivity",
    False,
    ha_type="binary_sensor",
    hive_id="hub-1",
    name="Hive Hub",
    ha_name="Hive Hub Status",
    online=False,
)


@pytest.fixture
def platform_devices() -> dict[str, list[dict[str, Any]]]:
    """Binary sensor devices returned by the mocked Hive session."""
    return {"binary_sensor": [CONTACT, MOTION_OFFLINE, HUB_STATUS_OFFLINE]}


@pytest.mark.usefixtures("setup_integration")
async def test_binary_sensors(hass: HomeAssistant) -> None:
    """Device class and state come from the Hive device."""
    state = hass.states.get("binary_sensor.front_door")
    assert state.state == STATE_ON
    assert state.attributes["device_class"] == "opening"

    # Offline devices go unavailable, except the hub's own connectivity sensor.
    assert hass.states.get("binary_sensor.hallway").state == STATE_UNAVAILABLE
    state = hass.states.get("binary_sensor.hive_hub_status")
    assert state.state == STATE_OFF
    assert state.attributes["device_class"] == "connectivity"


@pytest.mark.parametrize(
    "sensor_devices",
    [
        [
            make_device("Heating_State", "ON", name="Thermostat"),
            make_device("Heating_Boost", "OFF", name="Thermostat"),
            make_device("Hotwater_Boost", "ON", name="Hot Water", online=False),
        ]
    ],
)
async def test_heating_and_hot_water_state_sensors(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Heating and hot water state/boost come from the sensor list as binary sensors.

    They have no description in this component's sensor platform, so they don't
    also show up as sensors.
    """
    assert hass.states.get("binary_sensor.thermostat_heating_state").state == STATE_ON
    assert hass.states.get("binary_sensor.thermostat_heating_boost").state == STATE_OFF
    assert (
        hass.states.get("binary_sensor.hot_water_hotwater_boost").state
        == STATE_UNAVAILABLE
    )
    assert hass.states.async_entity_ids("sensor") == []
