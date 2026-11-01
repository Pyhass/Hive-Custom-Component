"""Tests for the switches re-exported from Home Assistant core."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import make_device

PLUG = make_device(
    "activeplug",
    True,
    ha_type="switch",
    hive_id="plug-1",
    name="Fan Plug",
    ha_name="Fan Plug",
    attributes={"mode": "MANUAL"},
)
HEAT_ON_DEMAND = make_device(
    "Heating_Heat_On_Demand",
    False,
    ha_type="switch",
    hive_id="heating-1",
    name="Heating",
    ha_name="Heating Heat on Demand",
)
OFFLINE_PLUG = make_device(
    "activeplug",
    True,
    ha_type="switch",
    hive_id="plug-2",
    name="Lamp Plug",
    ha_name="Lamp Plug",
    online=False,
)
# pyhive lists Hive actions as switches, but there is no description for them.
ACTION = make_device(
    "action", True, ha_type="switch", hive_id="action-1", ha_name="Leaving Home"
)


@pytest.fixture
def platform_devices() -> dict[str, list[dict[str, Any]]]:
    """Switch devices returned by the mocked Hive session."""
    return {"switch": [PLUG, HEAT_ON_DEMAND, OFFLINE_PLUG, ACTION]}


@pytest.mark.usefixtures("setup_integration")
async def test_switch_states(hass: HomeAssistant) -> None:
    """Plugs and heat on demand are switches; actions are not."""
    state = hass.states.get("switch.fan_plug")
    assert state.state == STATE_ON
    assert state.attributes["mode"] == "MANUAL"

    assert hass.states.get("switch.heating_heat_on_demand").state == STATE_OFF
    entry = er.async_get(hass).async_get("switch.heating_heat_on_demand")
    assert entry.entity_category == "config"

    assert hass.states.get("switch.lamp_plug").state == STATE_UNAVAILABLE
    assert hass.states.get("switch.leaving_home") is None


@pytest.mark.parametrize(
    ("service", "method"),
    [(SERVICE_TURN_ON, "turnOn"), (SERVICE_TURN_OFF, "turnOff")],
)
@pytest.mark.usefixtures("setup_integration")
async def test_turn_on_off(
    hass: HomeAssistant, mock_hive: MagicMock, service: str, method: str
) -> None:
    """Turning a switch on or off calls Hive."""
    setattr(mock_hive.switch, method, AsyncMock())

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: "switch.fan_plug"}, blocking=True
    )

    getattr(mock_hive.switch, method).assert_awaited_once()
