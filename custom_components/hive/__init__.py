"""Support for the Hive devices and services."""
from functools import wraps
import logging
import asyncio
import pyhiveapi
import voluptuous as vol
from aiohttp.web_exceptions import HTTPException

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_USERNAME,
    CONF_PASSWORD
)

from .const import DOMAIN


from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import Entity
from datetime import datetime, timedelta


_LOGGER = logging.getLogger(__name__)
SERVICES = ["heating", "hotwater", "trvcontrol"]
SERVICE_BOOST_HOT_WATER = "boost_hot_water"
SERVICE_BOOST_HEATING = "boost_heating"
ATTR_TIME_PERIOD = "time_period"
ATTR_MODE = "on_off"
SCAN_INTERVAL = timedelta(seconds=120)
PLATFORMS = ["binary_sensor", "climate",
             "light", "sensor", "switch", "water_heater"]

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

    def __init__(self, hass=None):
        """"""
        self.websession = aiohttp_client.async_get_clientsession(hass)
        self.entity_lookup = {}
        self.devices = None
        self.action = pyhiveapi.Action(self.websession)
        self.attributes = pyhiveapi.Attributes()
        self.heating = pyhiveapi.Heating(self.websession)
        self.hotwater = pyhiveapi.Hotwater(self.websession)
        self.light = pyhiveapi.Light(self.websession)
        self.sensor = pyhiveapi.Sensor(self.websession)
        self.session = pyhiveapi.Session(self.websession)
        self.switch = pyhiveapi.Plug(self.websession)


async def hive_data(hass):
    return Hive(hass)


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

    hive = await hive_data(hass)
    hive_config = dict(entry.data)
    hive_options = dict(entry.options)

    Tokens = hive_config.get("tokens", None)
    Username = hive_config["options"].get(CONF_USERNAME)
    Password = hive_config.get(CONF_PASSWORD)
    Update = "Y" if datetime.now() >= datetime.strptime(entry.data.get(
        "created"), '%Y-%m-%d %H:%M:%S.%f') + timedelta(minutes=60) else "N"

    # Update config entry options
    hive_options = hive_options if len(
        hive_options) > 0 else hive_config["options"]
    hass.config_entries.async_update_entry(entry, options=hive_options)
    hass.data[DOMAIN][entry.entry_id] = hive

    try:
        devices = await hive.session.start_session(Tokens,
                                                   Update,
                                                   hive_options)
    except HTTPException as error:
        _LOGGER.error("Could not connect to the internet: %s", error)
        raise ConfigEntryNotReady() from error

    if devices == "INVALID_REAUTH":
        return hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_REAUTH},
                data={"username": Username, "password": Password}
            )
        )

    async def heating_boost(service_call):
        """Handle the service call."""
        node_id = hive.entity_lookup.get(service_call.data[ATTR_ENTITY_ID])
        device = pyhiveapi.Hive_Helper.get_device_from_id(node_id)
        if not node_id:
            # log or raise error
            _LOGGER.error("Cannot boost entity id entered")
            return

        minutes = service_call.data[ATTR_TIME_PERIOD]
        temperature = service_call.data[ATTR_TEMPERATURE]

        await hive.heating.turn_boost_on(device, minutes, temperature)

    async def hot_water_boost(service_call):
        """Handle the service call."""
        node_id = hive.entity_lookup.get(service_call.data[ATTR_ENTITY_ID])
        device = pyhiveapi.Hive_Helper.get_device_from_id(node_id)
        if not node_id:
            # log or raise error
            _LOGGER.error("Cannot boost entity id entered")
            return
        minutes = service_call.data[ATTR_TIME_PERIOD]
        mode = service_call.data[ATTR_MODE]

        if mode == "on":
            await hive.hotwater.turn_boost_on(device, minutes)
        elif mode == "off":
            await hive.hotwater.turn_boost_off(device)

    hive.devices = devices
    for component in PLATFORMS:
        devicelist = devices.get(component)
        if devicelist:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(
                    entry, component)
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

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(
                    entry, component)
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
