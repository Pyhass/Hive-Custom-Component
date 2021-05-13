"""Support for the Hive binary sensors."""
from datetime import timedelta

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)

from . import HiveEntity
from .const import DOMAIN

ICON = "mdi:security"
PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)
HIVETOHA = {
    "home": STATE_ALARM_DISARMED,
    "asleep": STATE_ALARM_ARMED_NIGHT,
    "away": STATE_ALARM_ARMED_AWAY,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hive thermostat based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("alarm_control_panel")
    entities = []
    if devices:
        for dev in devices:
            entities.append(HiveAlarmControlPanelEntity(hive, dev))
    async_add_entities(entities, True)


class HiveAlarmControlPanelEntity(HiveEntity, AlarmControlPanelEntity):
    """Representation of a Hive alarm."""

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
            "model": self.device["deviceData"]["model"],
            "manufacturer": self.device["deviceData"]["manufacturer"],
            "sw_version": self.device["deviceData"]["version"],
            "via_device": (DOMAIN, self.device["parentDevice"]),
        }

    @property
    def name(self):
        """Return the name of the alarm."""
        return self.device["haName"]

    @property
    def icon(self):
        return ICON

    @property
    def available(self):
        """Return if the device is available."""
        return self.device["deviceData"]["online"]

    @property
    def state(self):
        """Return state of alarm."""
        if self.device["status"]["state"]:
            return STATE_ALARM_TRIGGERED
        return HIVETOHA[self.device["status"]["mode"]]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_NIGHT | SUPPORT_ALARM_ARM_AWAY

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        await self.hive.alarm.setMode(self.device, "home")

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command."""
        await self.hive.alarm.setMode(self.device, "asleep")

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        await self.hive.alarm.setMode(self.device, "away")

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.alarm.getAlarm(self.device)
