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
# after a change, at its start or at its end, so a single refresh at that
# moment can still read the old state. Refresh a few more times over the next
# five minutes rather than waiting for the 30-minute poll.
CATCHUP_DELAYS = tuple(timedelta(seconds=s) for s in (30, 90, 180, 300))


class HiveHolidayModeData:
    """One config entry's holiday mode data, refresh signal and timers.

    get_holiday_mode() always makes a cloud API call, so the status, start and
    end sensors share one fetch: refreshes within a few seconds of each other
    use the cached result.

    Whenever a fetch shows holiday mode scheduled or active, a refresh is set
    for its start and end, followed by catch-up refreshes once it has passed,
    so the sensors follow the transitions however the holiday was set (these
    services, the Hive app) and across restarts.
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
        self._catch_up: list[CALLBACK_TYPE] = []
        self._transitions: dict[str, tuple[datetime, CALLBACK_TYPE]] = {}

    async def async_get(self) -> dict | None:
        """Return the holiday mode data, fetching it if the cache is stale."""
        async with self._lock:
            now = time.monotonic()
            if self._fetched_at is None or now - self._fetched_at > self._CACHE_SECONDS:
                self._data = await self.hive.hub.get_holiday_mode()
                self._fetched_at = now
                self._track_transitions(self._data)
            return self._data

    @callback
    def async_refresh(self, _now: datetime | None = None) -> None:
        """Ask the holiday mode sensors to refresh."""
        async_dispatcher_send(self.hass, self.signal)

    @callback
    def async_changed(self) -> None:
        """Refresh after holiday mode was set or cancelled.

        Drops the cached result so the next fetch sees the change, then
        refreshes now and a few times over the next few minutes. A future
        start or end is picked up from the fetched data.
        """
        self._fetched_at = None
        self._async_catch_up()

    @callback
    def async_cancel_timers(self) -> None:
        """Cancel pending refreshes."""
        self._cancel_catch_up()
        while self._transitions:
            self._transitions.popitem()[1][1]()

    @callback
    def _async_catch_up(self, _now: datetime | None = None) -> None:
        """Refresh now and at each catch-up delay, replacing earlier ones."""
        self._cancel_catch_up()
        now = dt_util.utcnow()
        self._catch_up.extend(
            async_track_point_in_utc_time(self.hass, self.async_refresh, now + delay)
            for delay in CATCHUP_DELAYS
        )
        self.async_refresh()

    def _cancel_catch_up(self) -> None:
        while self._catch_up:
            self._catch_up.pop()()

    def _track_transitions(self, data: dict | None) -> None:
        """Keep a refresh set for a scheduled or active holiday's start and end."""
        if not data:
            # Failed fetch: keep what we have until the next good one.
            return
        on = data.get("enabled") or data.get("active")
        now = dt_util.utcnow()
        for key in ("start", "end"):
            when: datetime | None = None
            if on:
                if (epoch_ms := data.get(key)) is None:
                    # Hive sometimes leaves fields out; keep the timer we have.
                    continue
                when = dt_util.utc_from_timestamp(epoch_ms / 1000)
                if when <= now:
                    when = None
            current = self._transitions.get(key)
            if current is not None and current[0] == when:
                continue
            if current is not None:
                reached, cancel = self._transitions.pop(key)
                cancel()
                if reached <= now:
                    # The start or end has passed, whether its timer or another
                    # refresh got here first. Hive may not have caught up yet,
                    # so keep refreshing for a few minutes.
                    self._async_catch_up()
            if when is not None:
                self._transitions[key] = (
                    when,
                    async_track_point_in_utc_time(self.hass, self.async_refresh, when),
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
