"""Tests for the Hive Holiday Mode sensors and services."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
from apyhiveapi.helper.hive_exceptions import HiveApiError, HiveReauthRequired
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from custom_components.hive import holiday, sensor
from custom_components.hive.const import (
    DOMAIN,
    SERVICE_CANCEL_HOLIDAY_MODE,
    SERVICE_SET_HOLIDAY_MODE,
)

from .conftest import DEVICE_DATA, HUB_ID, PASSWORD, TOKENS

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
    monkeypatch.setattr(holiday.HiveHolidayModeData, "_CACHE_SECONDS", -1)


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


async def _refresh(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    async_dispatcher_send(hass, f"{DOMAIN}_holiday_{entry.entry_id}")
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
    await _refresh(hass, mock_config_entry)

    assert hass.states.get(_entity_id(hass, "Mode")).state == "active"


async def test_holiday_sensors_keep_values_on_partial_response(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A response missing start/end/temperature keeps the last known values."""
    mock_hive.hub.get_holiday_mode = AsyncMock(return_value=SCHEDULED)
    await _setup(hass, mock_config_entry)

    mock_hive.hub.get_holiday_mode.return_value = {"enabled": True, "active": True}
    await _refresh(hass, mock_config_entry)

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


@pytest.mark.parametrize("error", [TimeoutError(), HiveApiError(), ClientError()])
async def test_holiday_sensors_survive_fetch_error_at_setup(
    hass: HomeAssistant,
    mock_hive: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """A failed first fetch still adds the sensors, unavailable, and they recover."""
    mock_hive.hub.get_holiday_mode = AsyncMock(side_effect=error)
    await _setup(hass, mock_config_entry)

    for key in ("Mode", "DateStart", "DateEnd"):
        assert hass.states.get(_entity_id(hass, key)).state == STATE_UNAVAILABLE

    mock_hive.hub.get_holiday_mode = AsyncMock(return_value=SCHEDULED)
    await _refresh(hass, mock_config_entry)

    assert hass.states.get(_entity_id(hass, "Mode")).state == "scheduled"
    assert hass.states.get(_entity_id(hass, "DateStart")).state == START.isoformat()


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

    # Unloading cancels the pending catch-up refreshes; the services stay
    # registered (they belong to the integration, not the entry).
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert hass.services.has_service(DOMAIN, SERVICE_SET_HOLIDAY_MODE)
    assert hass.services.has_service(DOMAIN, SERVICE_CANCEL_HOLIDAY_MODE)
    assert not hass.data.get(holiday.DATA_HOLIDAY)


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
    [
        AsyncMock(return_value=False),
        AsyncMock(side_effect=HiveApiError),
        AsyncMock(side_effect=ClientError),
        AsyncMock(side_effect=TimeoutError),
    ],
    ids=["rejected", "api_error", "client_error", "timeout"],
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


async def _set(hass: HomeAssistant, **data) -> None:
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HOLIDAY_MODE,
        {"start": START.isoformat(), "end": END.isoformat(), "temperature": 12, **data},
        blocking=True,
    )


@pytest.mark.freeze_time("2026-12-01 12:00:00+00:00")
@pytest.mark.parametrize(
    ("start", "end", "key"),
    [
        (END, START, "end_before_start"),
        (START, START + timedelta(seconds=30), "end_before_start"),
        (
            datetime(2026, 11, 1, tzinfo=UTC),
            datetime(2026, 11, 30, tzinfo=UTC),
            "end_in_past",
        ),
    ],
)
async def test_set_holiday_mode_validates_window(
    hass: HomeAssistant,
    mock_hive: MagicMock,
    mock_config_entry: MockConfigEntry,
    start: datetime,
    end: datetime,
    key: str,
) -> None:
    """An end before (or in the same minute as) the start, or in the past, is rejected."""
    await _setup(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await _set(hass, start=start.isoformat(), end=end.isoformat())
    assert err.value.translation_key == key
    mock_hive.hub.set_holiday_mode.assert_not_awaited()


async def test_set_holiday_mode_naive_times_are_local(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Times without an offset use Home Assistant's time zone."""
    await hass.config.async_set_time_zone("Europe/London")
    await _setup(hass, mock_config_entry)

    # 20 June is BST (UTC+1).
    await _set(hass, start="2027-06-20 10:15:00", end="2027-06-27 18:30:00")

    start, end, _ = mock_hive.hub.set_holiday_mode.await_args.args
    assert start == datetime(2027, 6, 20, 9, 15, tzinfo=UTC)
    assert end == datetime(2027, 6, 27, 17, 30, tzinfo=UTC)
    assert start.utcoffset() == timedelta(hours=1)


@pytest.mark.parametrize(
    "service", [SERVICE_SET_HOLIDAY_MODE, SERVICE_CANCEL_HOLIDAY_MODE]
)
async def test_holiday_service_reauth(
    hass: HomeAssistant,
    mock_hive: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """A reauth-required error starts the reauth flow."""
    await _setup(hass, mock_config_entry)
    mock_hive.hub.set_holiday_mode.side_effect = HiveReauthRequired
    mock_hive.hub.cancel_holiday_mode.side_effect = HiveReauthRequired
    data = (
        {"start": START.isoformat(), "end": END.isoformat(), "temperature": 12}
        if service == SERVICE_SET_HOLIDAY_MODE
        else {}
    )

    with (
        patch.object(mock_config_entry, "async_start_reauth") as start_reauth,
        pytest.raises(HomeAssistantError) as err,
    ):
        await hass.services.async_call(DOMAIN, service, data, blocking=True)
    assert err.value.translation_key == "reauth_required"
    start_reauth.assert_called_once_with(hass)


async def test_holiday_sensor_reauth(
    hass: HomeAssistant,
    mock_hive: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A reauth-required error while polling starts reauth and goes unavailable."""
    mock_hive.hub.get_holiday_mode = AsyncMock(side_effect=HiveReauthRequired)
    with patch.object(mock_config_entry, "async_start_reauth") as start_reauth:
        await _setup(hass, mock_config_entry)

    assert hass.states.get(_entity_id(hass, "Mode")).state == STATE_UNAVAILABLE
    start_reauth.assert_called_with(hass)


async def test_service_call_skips_stale_cache(
    hass: HomeAssistant,
    mock_hive: MagicMock,
    mock_config_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A service call straight after a poll still shows the new state."""
    monkeypatch.setattr(holiday.HiveHolidayModeData, "_CACHE_SECONDS", 3600)
    await _setup(hass, mock_config_entry)
    assert hass.states.get(_entity_id(hass, "Mode")).state == "off"

    mock_hive.hub.get_holiday_mode.return_value = SCHEDULED
    await _set(hass)
    await hass.async_block_till_done()

    assert hass.states.get(_entity_id(hass, "Mode")).state == "scheduled"


@pytest.mark.freeze_time("2026-12-01 12:00:00+00:00")
async def test_catch_up_refreshes_replace_earlier_ones(
    hass: HomeAssistant,
    mock_hive: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Each call replaces the previous call's timers instead of adding more."""
    await _setup(hass, mock_config_entry)
    data = hass.data[holiday.DATA_HOLIDAY][mock_config_entry.entry_id]

    await _set(hass)
    # Refresh at the future start plus four catch-ups after it.
    assert len(data._timers) == 5
    await hass.services.async_call(
        DOMAIN, SERVICE_CANCEL_HOLIDAY_MODE, {}, blocking=True
    )
    assert len(data._timers) == 4

    calls = mock_hive.hub.get_holiday_mode.await_count
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # One fetch per sensor (the cache is off in these tests).
    assert mock_hive.hub.get_holiday_mode.await_count == calls + 3


async def test_holiday_services_with_two_entries(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """With two accounts the entry must be chosen; unloading one keeps the services."""
    second = MockConfigEntry(
        domain=DOMAIN,
        title="other@example.com",
        unique_id="other@example.com",
        data={
            "username": "other@example.com",
            "password": PASSWORD,
            "tokens": TOKENS,
            "device_data": DEVICE_DATA,
        },
    )
    await _setup(hass, mock_config_entry)
    await _setup(hass, second)

    with pytest.raises(ServiceValidationError) as err:
        await _set(hass)
    assert err.value.translation_key == "multiple_entries"

    await _set(hass, config_entry_id=second.entry_id)
    mock_hive.hub.set_holiday_mode.assert_awaited_once()

    assert await hass.config_entries.async_unload(second.entry_id)
    assert hass.services.has_service(DOMAIN, SERVICE_SET_HOLIDAY_MODE)
    assert hass.services.has_service(DOMAIN, SERVICE_CANCEL_HOLIDAY_MODE)

    with pytest.raises(ServiceValidationError) as err:
        await _set(hass, config_entry_id=second.entry_id)
    assert err.value.translation_key == "entry_not_loaded"

    # With one account left, the entry is optional again.
    await hass.services.async_call(
        DOMAIN, SERVICE_CANCEL_HOLIDAY_MODE, {}, blocking=True
    )
    mock_hive.hub.cancel_holiday_mode.assert_awaited_once()


async def test_holiday_services_without_loaded_entry(
    hass: HomeAssistant, mock_hive: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The services report a clear error when no account is loaded."""
    await _setup(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, SERVICE_CANCEL_HOLIDAY_MODE, {}, blocking=True
        )
    assert err.value.translation_key == "no_entry_loaded"
    with pytest.raises(ServiceValidationError) as err:
        await _set(hass, config_entry_id="missing")
    assert err.value.translation_key == "entry_not_found"
