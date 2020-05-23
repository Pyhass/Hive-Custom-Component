"""Support for the Hive switches."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers import aiohttp_client

from . import DOMAIN, HiveEntity, refresh_system

DEPENDENCIES = ["hive"]


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Hive Switch.

    No longer in use.
    """


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hive Switch based on a config entry."""
    from pyhiveapi import Action
    from pyhiveapi import Plug

    session = aiohttp_client.async_get_clientsession(hass)
    hive = hass.data[DOMAIN][entry.entry_id]
    hive.action = Action(session)
    hive.switch = Plug(session)
    devices = hive.devices.get("switch")
    if devices:
        devs = []
        for dev in devices:
            devs.append(HiveDevicePlug(hive, dev))
    async_add_entities(devs, True)


class HiveDevicePlug(HiveEntity, SwitchEntity):
    """Hive Active Plug."""

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        if self.device["hive_type"] == "activeplug":
            return {
                "identifiers": {(DOMAIN, self.device["hive_id"])},
                "name": self.device["hive_name"],
                "model": self.device["device_data"]["model"],
                "manufacturer": self.device["device_data"]["manufacturer"],
                "sw_version": self.device["device_data"]["version"],
                "via_device": (DOMAIN, self.device["parent_device"])
            }

    @property
    def name(self):
        """Return the name of this Switch device if any."""
        return self.device["ha_name"]

    @property
    def available(self):
        """Return if the device is availble"""
        return self.attributes.get("available", True)

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return self.attributes

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self.device["power_usage"]

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device["state"]

    @refresh_system
    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        if self.device["hive_type"] == "activeplug":
            await self.hive.switch.turn_on(self.device)
        elif self.device["hive_type"] == "action":
            await self.hive.action.turn_on(self.device)

    @refresh_system
    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        if self.device["hive_type"] == "activeplug":
            await self.hive.switch.turn_off(self.device)
        elif self.device["hive_type"] == "action":
            await self.hive.action.turn_off(self.device)

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.update_data(self.device)
        if self.device["hive_type"] == "activeplug":
            self.device = await self.hive.switch.get_plug(self.device)
        elif self.device["hive_type"] == "action":
            self.device = await self.hive.action.get_action(self.device)
        self.attributes.update(self.device.get("attributes", {}))
