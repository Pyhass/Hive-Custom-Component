"""Tests for the water heater re-exported from Home Assistant core."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    STATE_ECO,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from custom_components.hive.const import DOMAIN, SERVICE_BOOST_HOT_WATER

from .conftest import make_device

ENTITY_ID = "water_heater.hot_water"


def hot_water(operation: str = "SCHEDULE", *, online: bool = True) -> dict[str, Any]:
    """A hot water product as pyhive's getWaterHeater returns it."""
    return make_device(
        "hotwater",
        ha_type="water_heater",
        hive_id="hotwater-1",
        name="Hot Water",
        ha_name="Hot Water",
        online=online,
        status={"current_operation": operation},
    )


@pytest.fixture
def platform_devices() -> dict[str, list[dict[str, Any]]]:
    """Water heater devices returned by the mocked Hive session."""
    return {"water_heater": [hot_water()]}


@pytest.fixture
def mock_hotwater(mock_hive: MagicMock) -> MagicMock:
    """Make the hot water setters awaitable."""
    for method in ("setMode", "setBoostOn", "setBoostOff"):
        setattr(mock_hive.hotwater, method, AsyncMock())
    return mock_hive.hotwater


@pytest.mark.parametrize(
    ("platform_devices", "expected"),
    [
        ({"water_heater": [hot_water("SCHEDULE")]}, STATE_ECO),
        ({"water_heater": [hot_water("ON")]}, STATE_ON),
        ({"water_heater": [hot_water("OFF")]}, STATE_OFF),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_water_heater_state(hass: HomeAssistant, expected: str) -> None:
    """Hive operation names map to HA water heater states."""
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    "platform_devices", [{"water_heater": [hot_water(online=False)]}]
)
@pytest.mark.usefixtures("setup_integration")
async def test_water_heater_offline(hass: HomeAssistant) -> None:
    """An offline hot water controller is unavailable."""
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("service", "data", "hive_mode"),
    [
        (SERVICE_TURN_ON, {}, "MANUAL"),
        (SERVICE_TURN_OFF, {}, "OFF"),
        (SERVICE_SET_OPERATION_MODE, {ATTR_OPERATION_MODE: STATE_ECO}, "SCHEDULE"),
        (SERVICE_SET_OPERATION_MODE, {ATTR_OPERATION_MODE: STATE_ON}, "MANUAL"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_set_mode(
    hass: HomeAssistant,
    mock_hotwater: MagicMock,
    service: str,
    data: dict[str, Any],
    hive_mode: str,
) -> None:
    """Turning on/off and changing operation set the Hive mode."""
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
    )

    assert mock_hotwater.setMode.await_args.args[1] == hive_mode


@pytest.mark.usefixtures("setup_integration")
async def test_boost_hot_water_service(
    hass: HomeAssistant, mock_hotwater: MagicMock
) -> None:
    """hive.boost_hot_water boosts for the given minutes, or turns boost off."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_BOOST_HOT_WATER,
        {ATTR_ENTITY_ID: ENTITY_ID, "time_period": "01:00:00", "on_off": "on"},
        blocking=True,
    )
    assert mock_hotwater.setBoostOn.await_args.args[1] == 60

    await hass.services.async_call(
        DOMAIN,
        SERVICE_BOOST_HOT_WATER,
        {ATTR_ENTITY_ID: ENTITY_ID, "on_off": "off"},
        blocking=True,
    )
    mock_hotwater.setBoostOff.assert_awaited_once()
