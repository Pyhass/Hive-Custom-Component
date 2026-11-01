"""Tests for the climate entity re-exported from Home Assistant core."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_BOOST,
    PRESET_NONE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from custom_components.hive.const import (
    DOMAIN,
    SERVICE_BOOST_HEATING_OFF,
    SERVICE_BOOST_HEATING_ON,
)

from .conftest import make_device

ENTITY_ID = "climate.heating"


def heating(
    *, mode: str = "SCHEDULE", boost: str = "OFF", online: bool = True
) -> dict[str, Any]:
    """A heating product as pyhive's getClimate returns it."""
    return make_device(
        "heating",
        ha_type="climate",
        hive_id="heating-1",
        name="Heating",
        ha_name="Heating",
        online=online,
        temperatureunit="C",
        min_temp=5,
        max_temp=32,
        status={
            "mode": mode,
            "action": True,
            "current_temperature": 19.2,
            "target_temperature": 21,
            "boost": boost,
        },
    )


@pytest.fixture
def platform_devices() -> dict[str, list[dict[str, Any]]]:
    """Climate devices returned by the mocked Hive session."""
    return {"climate": [heating()]}


@pytest.fixture
def mock_heating(mock_hive: MagicMock) -> MagicMock:
    """Make the heating setters awaitable."""
    for method in ("setMode", "setTargetTemperature", "setBoostOn", "setBoostOff"):
        setattr(mock_hive.heating, method, AsyncMock())
    return mock_hive.heating


@pytest.mark.usefixtures("setup_integration")
async def test_climate_state(hass: HomeAssistant) -> None:
    """Hive heating status maps to HA climate state."""
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert state.attributes["current_temperature"] == 19.2
    assert state.attributes[ATTR_TEMPERATURE] == 21
    assert state.attributes["min_temp"] == 5
    assert state.attributes["max_temp"] == 32
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE


@pytest.mark.parametrize(
    "platform_devices", [{"climate": [heating(mode="OFF", boost="ON")]}]
)
@pytest.mark.usefixtures("setup_integration")
async def test_climate_boost_shows_as_heat(hass: HomeAssistant) -> None:
    """While boosting, the mode reads heat and the preset reads boost."""
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_BOOST


@pytest.mark.parametrize("platform_devices", [{"climate": [heating(online=False)]}])
@pytest.mark.usefixtures("setup_integration")
async def test_climate_offline(hass: HomeAssistant) -> None:
    """An offline thermostat is unavailable."""
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("hvac_mode", "hive_mode"),
    [(HVACMode.AUTO, "SCHEDULE"), (HVACMode.HEAT, "MANUAL"), (HVACMode.OFF, "OFF")],
)
@pytest.mark.usefixtures("setup_integration")
async def test_set_hvac_mode(
    hass: HomeAssistant, mock_heating: MagicMock, hvac_mode: HVACMode, hive_mode: str
) -> None:
    """HVAC modes are sent to Hive as its own mode names."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    mock_heating.setMode.assert_awaited_once()
    assert mock_heating.setMode.await_args.args[1] == hive_mode


@pytest.mark.usefixtures("setup_integration")
async def test_set_temperature(hass: HomeAssistant, mock_heating: MagicMock) -> None:
    """The target temperature is sent to Hive."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.5},
        blocking=True,
    )

    assert mock_heating.setTargetTemperature.await_args.args[1] == 22.5


@pytest.mark.usefixtures("setup_integration")
async def test_boost_preset_on(hass: HomeAssistant, mock_heating: MagicMock) -> None:
    """The boost preset boosts for 30 minutes to half a degree above current."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_BOOST},
        blocking=True,
    )

    assert mock_heating.setBoostOn.await_args.args[1:] == (30, 19.5)


@pytest.mark.parametrize("platform_devices", [{"climate": [heating(boost="ON")]}])
@pytest.mark.usefixtures("setup_integration")
async def test_boost_preset_off(hass: HomeAssistant, mock_heating: MagicMock) -> None:
    """Choosing no preset while boosting turns boost off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    mock_heating.setBoostOff.assert_awaited_once()


@pytest.mark.usefixtures("setup_integration")
async def test_boost_heating_services(
    hass: HomeAssistant, mock_heating: MagicMock
) -> None:
    """hive.boost_heating_on/off call Hive with minutes and temperature."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_BOOST_HEATING_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, "time_period": "01:30:00", ATTR_TEMPERATURE: 23},
        blocking=True,
    )
    assert mock_heating.setBoostOn.await_args.args[1:] == (90, 23.0)

    await hass.services.async_call(
        DOMAIN, SERVICE_BOOST_HEATING_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_heating.setBoostOff.assert_awaited_once()
