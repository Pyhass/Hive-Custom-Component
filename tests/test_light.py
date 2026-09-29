"""Tests for the lights re-exported from Home Assistant core."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
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

from .conftest import make_device


def light(
    hive_type: str, name: str, *, online: bool = True, **status: Any
) -> dict[str, Any]:
    """A light product as pyhive's getLight returns it."""
    return make_device(
        hive_type,
        ha_type="light",
        hive_id=f"{hive_type}-1",
        name=name,
        ha_name=name,
        online=online,
        status={"state": True, "brightness": 128, **status},
        attributes={"mode": "SCHEDULE"},
    )


WARM_WHITE = light("warmwhitelight", "Kitchen")
TUNEABLE = light("tuneablelight", "Bedroom", color_temp=370)
COLOUR = light(
    "colourtuneablelight", "Lounge Lamp", mode="COLOUR", hs_color=(255, 0, 0)
)
COLOUR_WHITE = light(
    "colourtuneablelight", "Desk Lamp", mode="WHITE", color_temp=153
) | {"hiveID": "colour-white-1", "device_id": "colour-white-1"}


@pytest.fixture
def platform_devices() -> dict[str, list[dict[str, Any]]]:
    """Light devices returned by the mocked Hive session."""
    return {"light": [WARM_WHITE, TUNEABLE, COLOUR, COLOUR_WHITE]}


@pytest.fixture
def mock_light(mock_hive: MagicMock) -> MagicMock:
    """Make the light setters awaitable."""
    mock_hive.light.turnOn = AsyncMock()
    mock_hive.light.turnOff = AsyncMock()
    return mock_hive.light


@pytest.mark.usefixtures("setup_integration")
async def test_light_states(hass: HomeAssistant) -> None:
    """Each Hive light type exposes the matching colour modes."""
    state = hass.states.get("light.kitchen")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert state.attributes["mode"] == "SCHEDULE"

    state = hass.states.get("light.bedroom")
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 2702  # 370 mireds

    state = hass.states.get("light.lounge_lamp")
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.HS
    assert state.attributes[ATTR_HS_COLOR] == (0.0, 100.0)

    state = hass.states.get("light.desk_lamp")
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 6535  # 153 mireds


@pytest.mark.parametrize(
    "platform_devices",
    [
        {
            "light": [
                light("warmwhitelight", "Kitchen", state=False),
                light("warmwhitelight", "Porch", online=False)
                | {"hiveID": "porch-1", "device_id": "porch-1"},
            ]
        }
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_light_off_and_offline(hass: HomeAssistant) -> None:
    """A light that is off reads off; an offline light is unavailable."""
    assert hass.states.get("light.kitchen").state == STATE_OFF
    assert hass.states.get("light.porch").state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("entity_id", "data", "expected"),
    [
        ("light.kitchen", {}, (None, None, None)),
        # Brightness is sent as a percentage rounded to 5, never below 5.
        ("light.kitchen", {ATTR_BRIGHTNESS: 255}, (100, None, None)),
        ("light.kitchen", {ATTR_BRIGHTNESS: 1}, (5, None, None)),
        ("light.bedroom", {ATTR_COLOR_TEMP_KELVIN: 4000}, (None, 4000, None)),
        ("light.lounge_lamp", {ATTR_HS_COLOR: (120, 50)}, (None, None, (120, 50, 100))),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_turn_on(
    hass: HomeAssistant,
    mock_light: MagicMock,
    entity_id: str,
    data: dict[str, Any],
    expected: tuple,
) -> None:
    """turn_on converts HA values to what Hive expects."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, **data},
        blocking=True,
    )

    assert mock_light.turnOn.await_args.args[1:] == expected


@pytest.mark.usefixtures("setup_integration")
async def test_turn_off(hass: HomeAssistant, mock_light: MagicMock) -> None:
    """turn_off is passed straight to Hive."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.kitchen"},
        blocking=True,
    )

    mock_light.turnOff.assert_awaited_once()
