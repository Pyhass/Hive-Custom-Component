"""Support for the Hive devices and services."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from datetime import datetime, timedelta
from functools import wraps
import logging
from typing import Any, Concatenate

from aiohttp.web_exceptions import HTTPException
from apyhiveapi import Auth, Hive
from apyhiveapi.helper.hive_exceptions import HiveApiError, HiveReauthRequired
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    PLATFORM_LOOKUP,
    PLATFORMS,
    SERVICE_CANCEL_HOLIDAY_MODE,
    SERVICE_SET_HOLIDAY_MODE,
)
from .entity import HiveEntity

_LOGGER = logging.getLogger(__name__)

type HiveConfigEntry = ConfigEntry[Hive]

# Hive's backend can take a few minutes to actually flip a schedule to
# active/off even after the requested start/cancel has technically taken
# effect, so a single refresh right after the service call (or even right
# at "start") can still catch a stale read. Poll a few extra times over
# the following five minutes to pick up the eventual transition sooner
# than the sensor's normal 30-minute interval would.
HOLIDAY_MODE_CATCHUP_DELAYS = (30, 90, 180, 300)

SET_HOLIDAY_MODE_SCHEMA = vol.Schema(
    {
        vol.Required("start"): cv.datetime,
        vol.Required("end"): cv.datetime,
        vol.Required("temperature"): vol.All(
            vol.Coerce(float), vol.Range(min=7, max=35)
        ),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: HiveConfigEntry) -> bool:
    """Set up Hive from a config entry."""
    web_session = aiohttp_client.async_get_clientsession(hass)
    hive_config = dict(entry.data)
    hive = Hive(web_session)

    hive_config["options"] = {}
    hive_config["options"].update(
        {CONF_SCAN_INTERVAL: dict(entry.options).get(CONF_SCAN_INTERVAL, 120)}
    )
    entry.runtime_data = hive

    try:
        devices = await hive.session.startSession(hive_config)
    except HTTPException as error:
        _LOGGER.error("Could not connect to the internet: %s", error)
        raise ConfigEntryNotReady from error
    except HiveReauthRequired as err:
        raise ConfigEntryAuthFailed from err

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, devices["parent"][0]["device_id"])},
        name=devices["parent"][0]["hiveName"],
        model=devices["parent"][0]["deviceData"]["model"],
        sw_version=devices["parent"][0]["deviceData"]["version"],
        manufacturer=devices["parent"][0]["deviceData"]["manufacturer"],
    )

    await hass.config_entries.async_forward_entry_setups(
        entry,
        [
            ha_type
            for ha_type, hive_type in PLATFORM_LOOKUP.items()
            if devices.get(hive_type)
        ],
    )

    @callback
    def _async_refresh_holiday_sensor(_now: datetime | None = None) -> None:
        async_dispatcher_send(hass, DOMAIN)

    def _schedule_holiday_catchup_refreshes(anchor: datetime) -> None:
        """Schedule a few extra refreshes after `anchor`."""
        for delay in HOLIDAY_MODE_CATCHUP_DELAYS:
            entry.async_on_unload(
                async_track_point_in_utc_time(
                    hass,
                    _async_refresh_holiday_sensor,
                    anchor + timedelta(seconds=delay),
                )
            )

    async def _async_set_holiday_mode(call: ServiceCall) -> None:
        """Handle the set_holiday_mode service call."""
        # The Hive app itself only works to minute precision; truncate here
        # so every caller (this integration's automations, a manual service
        # call, anything else) gets the same clean minute-aligned start/end
        # rather than whatever arbitrary seconds happened to be on the
        # clock when the caller computed "now".
        start = call.data["start"].replace(second=0, microsecond=0)
        end = call.data["end"].replace(second=0, microsecond=0)
        try:
            success = await hive.hub.set_holiday_mode(
                start, end, call.data["temperature"]
            )
        except (HTTPException, HiveApiError, HiveReauthRequired) as err:
            raise HomeAssistantError(f"Failed to set Hive holiday mode: {err}") from err
        if not success:
            raise HomeAssistantError("Hive rejected the set holiday mode request.")
        async_dispatcher_send(hass, DOMAIN)

        # The Holiday Mode sensor otherwise only refreshes on its 30-minute
        # poll or after a service call, so a scheduled -> active transition
        # that happens purely because "start" has passed can sit stale for
        # up to 30 minutes. Refresh right at "start" for a future-dated
        # schedule, then run the catch-up burst anchored at whichever of
        # "start" or now is later (covers both a future start and a
        # start-now request, where Hive's own backend is typically the
        # slower part of the transition).
        start_utc = dt_util.as_utc(start)
        now_utc = dt_util.utcnow()
        if start_utc > now_utc:
            entry.async_on_unload(
                async_track_point_in_utc_time(
                    hass, _async_refresh_holiday_sensor, start_utc
                )
            )
        _schedule_holiday_catchup_refreshes(max(start_utc, now_utc))

    async def _async_cancel_holiday_mode(call: ServiceCall) -> None:
        """Handle the cancel_holiday_mode service call."""
        try:
            success = await hive.hub.cancel_holiday_mode()
        except (HTTPException, HiveApiError, HiveReauthRequired) as err:
            raise HomeAssistantError(
                f"Failed to cancel Hive holiday mode: {err}"
            ) from err
        if not success:
            raise HomeAssistantError("Hive rejected the cancel holiday mode request.")
        async_dispatcher_send(hass, DOMAIN)
        _schedule_holiday_catchup_refreshes(dt_util.utcnow())

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOLIDAY_MODE,
        _async_set_holiday_mode,
        schema=SET_HOLIDAY_MODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_HOLIDAY_MODE, _async_cancel_holiday_mode
    )

    @callback
    def _async_remove_holiday_services() -> None:
        hass.services.async_remove(DOMAIN, SERVICE_SET_HOLIDAY_MODE)
        hass.services.async_remove(DOMAIN, SERVICE_CANCEL_HOLIDAY_MODE)

    entry.async_on_unload(_async_remove_holiday_services)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HiveConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: HiveConfigEntry) -> None:
    """Remove a config entry."""
    hive = Auth(entry.data["username"], entry.data["password"])
    await hive.forget_device(
        entry.data["tokens"]["AuthenticationResult"]["AccessToken"],
        entry.data["device_data"][1],
    )


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: HiveConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


def refresh_system[_HiveEntityT: HiveEntity, **_P](
    func: Callable[Concatenate[_HiveEntityT, _P], Awaitable[Any]],
) -> Callable[Concatenate[_HiveEntityT, _P], Coroutine[Any, Any, None]]:
    """Force update all entities after state change."""

    @wraps(func)
    async def wrapper(self: _HiveEntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        await func(self, *args, **kwargs)
        async_dispatcher_send(self.hass, DOMAIN)

    return wrapper
