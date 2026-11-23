"""Holiday mode state shared by the Hive sensors and services."""

import asyncio
from datetime import datetime, timedelta
import time

from aiohttp import ClientError
from aiohttp.web_exceptions import HTTPException
from apyhiveapi.helper.hive_exceptions import HiveApiError, NoApiToken

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

# What a holiday mode call can raise apart from HiveReauthRequired, which
# callers handle separately so they can start a reauth flow. pyhive raises
# aiohttp.web_exceptions.HTTPError when a request fails outright.
HIVE_HOLIDAY_ERRORS = (
    TimeoutError,
    ClientError,
    HTTPException,
    HiveApiError,
    NoApiToken,
)

# Hive's backend can take a few minutes to flip holiday mode to active or off
# after a change, so a single refresh straight after a service call (or at
# "start") can still read the old state. Refresh a few more times over the
# next five minutes rather than waiting for the 30-minute poll.
CATCHUP_DELAYS = tuple(timedelta(seconds=s) for s in (30, 90, 180, 300))


class HiveHolidayModeData:
    """One config entry's holiday mode data, refresh signal and timers.

    get_holiday_mode() always makes a cloud API call, so the status, start and
    end sensors share one fetch: refreshes within a few seconds of each other
    use the cached result.
    """

    _CACHE_SECONDS = 5

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the holiday mode data."""
        self.hass = hass
        self.hive = entry.runtime_data
        self.signal = f"{DOMAIN}_holiday_{entry.entry_id}"
        self._data: dict | None = None
        self._fetched_at: float | None = None
        self._lock = asyncio.Lock()
        self._timers: list[CALLBACK_TYPE] = []

    async def async_get(self) -> dict | None:
        """Return the holiday mode data, fetching it if the cache is stale."""
        async with self._lock:
            now = time.monotonic()
            if self._fetched_at is None or now - self._fetched_at > self._CACHE_SECONDS:
                self._data = await self.hive.hub.get_holiday_mode()
                self._fetched_at = now
            return self._data

    @callback
    def async_refresh(self, _now: datetime | None = None) -> None:
        """Ask the holiday mode sensors to refresh."""
        async_dispatcher_send(self.hass, self.signal)

    @callback
    def async_changed(self, start: datetime | None = None) -> None:
        """Refresh after holiday mode was set or cancelled.

        Drops the cached result so the next fetch sees the change, refreshes
        now, at a future start, and a few times after whichever is later.
        Replaces the timers from any earlier call.
        """
        self._fetched_at = None
        self.async_cancel_timers()
        anchor = now = dt_util.utcnow()
        if start is not None and (start := dt_util.as_utc(start)) > now:
            self._track(start)
            anchor = start
        for delay in CATCHUP_DELAYS:
            self._track(anchor + delay)
        self.async_refresh()

    @callback
    def async_cancel_timers(self) -> None:
        """Cancel pending refreshes."""
        while self._timers:
            self._timers.pop()()

    def _track(self, when: datetime) -> None:
        self._timers.append(
            async_track_point_in_utc_time(self.hass, self.async_refresh, when)
        )


DATA_HOLIDAY: HassKey[dict[str, HiveHolidayModeData]] = HassKey(f"{DOMAIN}_holiday")


@callback
def async_get_holiday_data(
    hass: HomeAssistant, entry: ConfigEntry
) -> HiveHolidayModeData:
    """Return the holiday mode data for a config entry, creating it once."""
    entries = hass.data.setdefault(DATA_HOLIDAY, {})
    if (data := entries.get(entry.entry_id)) is None:
        data = entries[entry.entry_id] = HiveHolidayModeData(hass, entry)

        @callback
        def _async_unload() -> None:
            data.async_cancel_timers()
            entries.pop(entry.entry_id, None)

        entry.async_on_unload(_async_unload)
    return data
