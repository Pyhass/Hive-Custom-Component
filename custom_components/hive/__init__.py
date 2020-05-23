"""Support for the Hive devices and services."""
from functools import wraps
import logging
import asyncio
import inspect

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ["pyhiveapi==0.2.17dev25"]
_LOGGER = logging.getLogger(__name__)
DOMAIN = "hive"
SERVICES = ["heating", "hotwater", "TRV"]
SERVICE_BOOST_HOT_WATER = "boost_hot_water"
SERVICE_BOOST_HEATING = "boost_heating"
ATTR_TIME_PERIOD = "time_period"
ATTR_MODE = "on_off"
PLATFORMS = ["binary_sensor", "climate", "light", "sensor", "switch", "water_heater"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_USERNAME): cv.string
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

BOOST_HEATING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_TIME_PERIOD): vol.All(
            cv.time_period, cv.positive_timedelta, lambda td: td.total_seconds() // 60
        ),
        vol.Optional(ATTR_TEMPERATURE, default="25.0"): vol.Coerce(float),
    }
)

BOOST_HOT_WATER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_TIME_PERIOD, default="00:30:00"): vol.All(
            cv.time_period, cv.positive_timedelta, lambda td: td.total_seconds() // 60
        ),
        vol.Required(ATTR_MODE): cv.string,
    }
)


class Hive:
    """Initiate Hive Session Class."""

    entity_lookup = {}
    devices = None
    action = None
    attributes = None
    heating = None
    hotwater = None
    light = None
    sensor = None
    session = None
    switch = None
    weather = None


async def async_setup(hass, config):
    """Set up the Hive Component."""
    hass.data[DOMAIN] = {}
    if DOMAIN not in config:
        return True

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"username": username, "password": password}
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Set up Hive from a config entry."""
    # Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)
    from pyhiveapi import Session

    async def heating_boost(service):
        """Handle the service call."""
        node_id = Hive.entity_lookup.get(service.data[ATTR_ENTITY_ID])
        if not node_id:
            # log or raise error
            _LOGGER.error("Cannot boost entity id entered")
            return

        minutes = service.data[ATTR_TIME_PERIOD]
        temperature = service.data[ATTR_TEMPERATURE]

        await Hive.heating.turn_boost_on(node_id, minutes, temperature)

    async def hot_water_boost(service):
        """Handle the service call."""
        node_id = Hive.entity_lookup.get(service.data[ATTR_ENTITY_ID])
        if not node_id:
            # log or raise error
            _LOGGER.error("Cannot boost entity id entered")
            return
        minutes = service.data[ATTR_TIME_PERIOD]
        mode = service.data[ATTR_MODE]

        if mode == "on":
            await Hive.hotwater.turn_boost_on(node_id, minutes)
        elif mode == "off":
            await Hive.hotwater.turn_boost_off(node_id)

    session = aiohttp_client.async_get_clientsession(hass)
    hive = Hive()
    hive.session = Session(session)
    Token = entry.data.get("token", None)
    Username = entry.data.get("username", None)
    Password = entry.data.get("password", None)
    interval = entry.options.get("scan_interval", 120)
    hass.data[DOMAIN][entry.entry_id] = hive

    devices = await hive.session.start_session(interval,
                                               Token,
                                               Username,
                                               Password)

    hive.devices = devices
    for component in PLATFORMS:
        devicelist = devices.get(component)
        if devicelist:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, component)
            )
            if component == "climate":
                hass.services.async_register(
                    DOMAIN,
                    SERVICE_BOOST_HEATING,
                    heating_boost,
                    schema=BOOST_HEATING_SCHEMA,
                )
            if component == "water_heater":
                hass.services.async_register(
                    DOMAIN,
                    SERVICE_BOOST_HOT_WATER,
                    hot_water_boost,
                    schema=BOOST_HOT_WATER_SCHEMA,
                )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Unload a config entry."""
    Token_id = entry.data.get("token_id", None)
    if Token_id is not None:
        from pyhiveapi import Hive_Async
        Token = entry.data.get("token", None)
        session = aiohttp_client.async_get_clientsession(hass)
        await Hive_Async.remove_token(Hive_Async(session), Token, Token_id)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def refresh_system(func):
    """Force update all entities after state change."""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        await func(self, *args, **kwargs)
        async_dispatcher_send(self.hass, DOMAIN)

    return wrapper


class HiveEntity(Entity):
    """Initiate Hive Base Class."""

    def __init__(self, hive, hive_device):
        """Initialize the instance."""
        self.hive = hive
        self.device = hive_device
        self.attributes = {}
        self._unique_id = f'{self.device["hive_id"]}-{self.device["hive_type"]}'

    async def async_added_to_hass(self):
        """When entity is added to Home Assistant."""
        async_dispatcher_connect(self.hass, DOMAIN, self._update_callback)
        if self.device["hive_type"] in SERVICES:
            self.hive.entity_lookup[self.entity_id] = self.device["hive_id"]

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state()
