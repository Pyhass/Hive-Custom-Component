"""Services for the Hive integration."""

from typing import TYPE_CHECKING

from apyhiveapi.helper.hive_exceptions import HiveReauthRequired
import probatio

from homeassistant.components.hive.services import *  # noqa: F403
from homeassistant.components.hive.services import (
    async_setup_services as async_setup_core_services,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SERVICE_CANCEL_HOLIDAY_MODE, SERVICE_SET_HOLIDAY_MODE
from .holiday import HIVE_HOLIDAY_ERRORS, async_get_holiday_data

if TYPE_CHECKING:
    from . import HiveConfigEntry

ATTR_START = "start"
ATTR_END = "end"
ATTR_TEMPERATURE = "temperature"

CONFIG_ENTRY_SCHEMA = {probatio.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}

SET_HOLIDAY_MODE_SCHEMA = probatio.Schema(
    {
        **CONFIG_ENTRY_SCHEMA,
        probatio.Required(ATTR_START): cv.datetime,
        probatio.Required(ATTR_END): cv.datetime,
        probatio.Required(ATTR_TEMPERATURE): probatio.All(
            probatio.Coerce(float), probatio.Range(min=7, max=35)
        ),
    }
)
CANCEL_HOLIDAY_MODE_SCHEMA = probatio.Schema(CONFIG_ENTRY_SCHEMA)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Hive integration.

    Core's services (the boost_* entity services) are registered unchanged;
    the holiday mode services are added alongside them.
    """
    async_setup_core_services(hass)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HOLIDAY_MODE,
        _async_set_holiday_mode,
        schema=SET_HOLIDAY_MODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_HOLIDAY_MODE,
        _async_cancel_holiday_mode,
        schema=CANCEL_HOLIDAY_MODE_SCHEMA,
    )


def _get_entry(call: ServiceCall) -> HiveConfigEntry:
    """Return the loaded Hive entry the call is for.

    The entry can be given; with only one Hive account loaded it is optional.
    """
    hass = call.hass
    if entry_id := call.data.get(ATTR_CONFIG_ENTRY_ID):
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_found",
                translation_placeholders={"entry_id": entry_id},
            )
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
                translation_placeholders={"title": entry.title},
            )
        return entry

    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_entry_loaded"
        )
    if len(entries) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="multiple_entries"
        )
    return entries[0]


async def _async_set_holiday_mode(call: ServiceCall) -> None:
    """Schedule holiday mode."""
    entry = _get_entry(call)
    # The Hive app works to the minute, so drop seconds here: every caller
    # gets the same minute-aligned window. Naive times are Home Assistant's
    # local time (pyhive would otherwise use the host's time zone).
    start = dt_util.as_local(call.data[ATTR_START]).replace(second=0, microsecond=0)
    end = dt_util.as_local(call.data[ATTR_END]).replace(second=0, microsecond=0)
    if end <= start:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="end_before_start"
        )
    if end <= dt_util.now():
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="end_in_past"
        )

    try:
        success = await entry.runtime_data.hub.set_holiday_mode(
            start, end, call.data[ATTR_TEMPERATURE]
        )
    except HiveReauthRequired as err:
        entry.async_start_reauth(call.hass)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="reauth_required"
        ) from err
    except HIVE_HOLIDAY_ERRORS as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_holiday_mode_failed",
            translation_placeholders={"error": repr(err)},
        ) from err
    if not success:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="set_holiday_mode_rejected"
        )
    async_get_holiday_data(call.hass, entry).async_changed()


async def _async_cancel_holiday_mode(call: ServiceCall) -> None:
    """Cancel scheduled or active holiday mode."""
    entry = _get_entry(call)
    try:
        success = await entry.runtime_data.hub.cancel_holiday_mode()
    except HiveReauthRequired as err:
        entry.async_start_reauth(call.hass)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="reauth_required"
        ) from err
    except HIVE_HOLIDAY_ERRORS as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cancel_holiday_mode_failed",
            translation_placeholders={"error": repr(err)},
        ) from err
    if not success:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="cancel_holiday_mode_rejected"
        )
    async_get_holiday_data(call.hass, entry).async_changed()
