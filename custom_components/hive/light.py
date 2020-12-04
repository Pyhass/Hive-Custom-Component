"""
Support for the Hive devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.hive/
"""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
import homeassistant.util.color as color_util
from . import DOMAIN, HiveEntity, refresh_system

DEPENDENCIES = ["hive"]


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Hive Light.

    No longer in use.
    """


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hive Light based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.devices.get("light")
    devs = []
    if devices:
        for dev in devices:
            devs.append(HiveDeviceLight(hive, dev))
    async_add_entities(devs, True)


class HiveDeviceLight(HiveEntity, LightEntity):
    """Hive Active Light Device."""

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
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
        """Return the display name of this light."""
        return self.device["ha_name"]

    @property
    def available(self):
        """Return if the device is available"""
        return self.device["device_data"]["online"]

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return self.attributes

    @property
    def brightness(self):
        """Brightness of the light (an integer in the range 1-255)."""
        return self.device["status"]["brightness"]

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return self.device.get("min_mireds", None)

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return self.device.get("max_mireds", None)

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        return self.device["status"].get("color_temp", None)

    @property
    def hs_color(self) -> tuple:
        """Return the hs color value."""
        rgb = self.device["status"].get("hs_color", None)
        return color_util.color_RGB_to_hs(*rgb)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.device["status"]["state"]

    @refresh_system
    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        new_brightness = None
        new_color_temp = None
        new_color = None
        if ATTR_BRIGHTNESS in kwargs:
            tmp_new_brightness = kwargs.get(ATTR_BRIGHTNESS)
            percentage_brightness = (tmp_new_brightness / 255) * 100
            new_brightness = int(round(percentage_brightness / 5.0) * 5.0)
            if new_brightness == 0:
                new_brightness = 5
        if ATTR_COLOR_TEMP in kwargs:
            tmp_new_color_temp = kwargs.get(ATTR_COLOR_TEMP)
            new_color_temp = round(1000000 / tmp_new_color_temp)
        if ATTR_HS_COLOR in kwargs:
            get_new_color = kwargs.get(ATTR_HS_COLOR)
            hue = int(get_new_color[0])
            saturation = int(get_new_color[1])
            new_color = (hue, saturation, 100)

        await self.hive.light.turn_on(self.device, new_brightness, new_color_temp, new_color)

    @refresh_system
    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self.hive.light.turn_off(self.device)

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = None
        if self.device["hive_type"] == "warmwhitelight":
            supported_features = SUPPORT_BRIGHTNESS
        elif self.device["hive_type"] == "tuneablelight":
            supported_features = SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP
        elif self.device["hive_type"] == "colourtuneablelight":
            supported_features = SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_COLOR

        return supported_features

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.update_data(self.device)
        self.device = await self.hive.light.get_light(self.device)
        self.attributes.update(self.device.get("attributes", {}))
