"""Tests for the Hive Holiday Mode sensors and services."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from apyhiveapi.helper.hive_exceptions import HiveApiError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from custom_components.hive import sensor
from custom_components.hive.const import (
    DOMAIN,
    SERVICE_CANCEL_HOLIDAY_MODE,
    SERVICE_SET_HOLIDAY_MODE,
)

from .conftest import HUB_ID

START = datetime(2026, 12, 20, 10, 15, tzinfo=UTC)
END = datetime(2027, 1, 3, 18, 30, tzinfo=UTC)
START_MS = int(START.timestamp() * 1000)
END_MS = int(END.timestamp() * 1000)
SCHEDULED = {
    "enabled": True,
    "active": False,
    "start": START_MS,
    "end": END_MS,
    "temperature": 12.0,
}


@pytest.fixture(autouse=True)
def no_holiday_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fetch fresh holiday data on every refresh so tests can change it."""
    monkeypatch.setattr(sensor._HiveHolidayModeData, "_CACHE_SECONDS", -1)


def _entity_id(hass: HomeAssistant, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{HUB_ID}-Holiday{key}"
    )
    assert entity_id is not None
    return entity_id


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _refresh(hass: HomeAssistant) -> None:
    async_dispatcher_send(hass, DOMAIN)
    await hass.async_block_till_done()


async def test_holiday_sensors_off(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The hub gets Holiday Mode, Start and End sensors; off has no dates."""
    await _setup(hass, mock_config_entry)

    assert hass.states.get(_entity_id(hass, "Mode")).state == "off"
    assert hass.states.get(_entity_id(hass, "DateStart")).state == "unknown"
    assert hass.states.get(_entity_id(hass, "DateEnd")).state == "unknown"


async def test_holiday_sensors_scheduled_then_active(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Status, attributes and dates follow the Hive response."""
    mock_hive.hub.get_holiday_mode = AsyncMock(return_value=SCHEDULED)
    await _setup(hass, mock_config_entry)

    mode = hass.states.get(_entity_id(hass, "Mode"))
    assert mode.state == "scheduled"
    assert mode.attributes["start"] == START.isoformat()
    assert mode.attributes["end"] == END.isoformat()
    assert mode.attributes["temperature"] == 12.0
    assert hass.states.get(_entity_id(hass, "DateStart")).state == START.isoformat()
    assert hass.states.get(_entity_id(hass, "DateEnd")).state == END.isoformat()

    mock_hive.hub.get_holiday_mode.return_value = {**SCHEDULED, "active": True}
    await _refresh(hass)

    assert hass.states.get(_entity_id(hass, "Mode")).state == "active"


async def test_holiday_sensors_keep_values_on_partial_response(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A response missing start/end/temperature keeps the last known values."""
    mock_hive.hub.get_holiday_mode = AsyncMock(return_value=SCHEDULED)
    await _setup(hass, mock_config_entry)

    mock_hive.hub.get_holiday_mode.return_value = {"enabled": True, "active": True}
    await _refresh(hass)

    mode = hass.states.get(_entity_id(hass, "Mode"))
    assert mode.state == "active"
    assert mode.attributes["start"] == START.isoformat()
    assert mode.attributes["temperature"] == 12.0
    assert hass.states.get(_entity_id(hass, "DateEnd")).state == END.isoformat()


async def test_holiday_sensors_unavailable_without_data(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The sensors go unavailable when Hive returns no holiday data."""
    mock_hive.hub.get_holiday_mode = AsyncMock(return_value=None)
    await _setup(hass, mock_config_entry)

    for key in ("Mode", "DateStart", "DateEnd"):
        assert hass.states.get(_entity_id(hass, key)).state == STATE_UNAVAILABLE


async def test_set_holiday_mode(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The service truncates to the minute and refreshes the sensors."""
    await _setup(hass, mock_config_entry)
    mock_hive.hub.get_holiday_mode.return_value = SCHEDULED

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HOLIDAY_MODE,
        {
            "start": "2026-12-20T10:15:42+00:00",
            "end": "2027-01-03T18:30:59.5+00:00",
            "temperature": "12",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_hive.hub.set_holiday_mode.assert_awaited_once_with(START, END, 12.0)
    assert hass.states.get(_entity_id(hass, "Mode")).state == "scheduled"

    # Unloading cancels the pending catch-up refreshes and removes the services.
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert not hass.services.has_service(DOMAIN, SERVICE_SET_HOLIDAY_MODE)
    assert not hass.services.has_service(DOMAIN, SERVICE_CANCEL_HOLIDAY_MODE)


async def test_cancel_holiday_mode(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The cancel service calls Hive and refreshes the sensors."""
    mock_hive.hub.get_holiday_mode = AsyncMock(return_value=SCHEDULED)
    await _setup(hass, mock_config_entry)
    mock_hive.hub.get_holiday_mode.return_value = {"enabled": False, "active": False}

    await hass.services.async_call(
        DOMAIN, SERVICE_CANCEL_HOLIDAY_MODE, {}, blocking=True
    )
    await hass.async_block_till_done()

    mock_hive.hub.cancel_holiday_mode.assert_awaited_once_with()
    assert hass.states.get(_entity_id(hass, "Mode")).state == "off"
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "data", "method"),
    [
        (
            SERVICE_SET_HOLIDAY_MODE,
            {"start": START.isoformat(), "end": END.isoformat(), "temperature": 12},
            "set_holiday_mode",
        ),
        (SERVICE_CANCEL_HOLIDAY_MODE, {}, "cancel_holiday_mode"),
    ],
)
@pytest.mark.parametrize(
    "outcome",
    [AsyncMock(return_value=False), AsyncMock(side_effect=HiveApiError)],
    ids=["rejected", "api_error"],
)
async def test_holiday_service_failures(
    hass: HomeAssistant,
    mock_hive: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    data: dict,
    method: str,
    outcome: AsyncMock,
) -> None:
    """A rejected request or an API error surfaces as HomeAssistantError."""
    await _setup(hass, mock_config_entry)
    setattr(mock_hive.hub, method, outcome)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, service, data, blocking=True)


async def test_set_holiday_mode_rejects_bad_temperature(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Temperatures outside Hive's 7-35 range are rejected before calling Hive."""
    await _setup(hass, mock_config_entry)

    with pytest.raises(Exception, match="temperature"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_HOLIDAY_MODE,
            {"start": START.isoformat(), "end": END.isoformat(), "temperature": 40},
            blocking=True,
        )
    mock_hive.hub.set_holiday_mode.assert_not_awaited()


async def test_no_holiday_sensors_without_hub(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Without a hub, only the device sensors are added."""
    hive = MagicMock()
    hive.session.deviceList = {"sensor": []}
    hive.session.hub_id = None
    mock_config_entry.runtime_data = hive
    add_entities = MagicMock()

    await sensor.async_setup_entry(hass, mock_config_entry, add_entities)

    add_entities.assert_not_called()
