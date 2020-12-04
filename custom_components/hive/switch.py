"""Support for the Hive switches."""
from homeassistant.components.switch import SwitchEntity

from . import DOMAIN, HiveEntity, refresh_system
from .const import ICONURL

DEPENDENCIES = ["hive"]


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Hive Switch.

    No longer in use.
    """


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hive Switch based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.devices.get("switch")
    devs = []
    if devices:
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
                "identifiers": {(DOMAIN, self.device["device_id"])},
                "name": self.device["device_name"],
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
        """Return if the device is available"""
        return self.device["device_data"].get("online", True)

    @property
    def entity_picture(self):
        """Set icon for entity."""
        return ICONURL

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return self.attributes

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self.device["status"]["power_usage"]

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device["status"]["state"]

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
