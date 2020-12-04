"""
Support for the Hive devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.hive/
"""

from . import DOMAIN, HiveEntity
from homeassistant.const import (TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

from . import DATA_HIVE, DOMAIN, HiveEntity

DEPENDENCIES = ['hive']
DEVICETYPE = {'CurrentTemperature': {'icon': 'mdi:thermometer', 'unit': TEMP_CELSIUS, 'type': 'temperature'},
              'TargetTemperature': {'icon': 'mdi:thermometer', 'unit': TEMP_CELSIUS, 'type': 'temperature'},
              'Heating_State': {'icon': 'mdi:radiator', 'type': 'None'},
              'Heating_Mode': {'icon': 'mdi:radiator', 'type': 'None'},
              'Heating_Boost': {'icon': 'mdi:radiator', 'type': 'None'},
              'Hotwater_State': {'icon': 'mdi:water-pump', 'type': 'None'},
              'Hotwater_Mode': {'icon': 'mdi:water-pump', 'type': 'None'},
              'Hotwater_Boost': {'icon': 'mdi:water-pump', 'type': 'None'},
              'Mode': {'icon': 'mdi:eye', 'type': 'None'},
              'Battery': {'icon': 'mdi:thermometer', 'unit': ' % ', 'type': 'battery'},
              'Availability': {'icon': 'None', 'type': 'None'}
              }


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Hive Sensor.

    No longer in use.
    """


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Hive Sensor based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.devices.get("sensor")
    devs = []
    if devices:
        for dev in devices:
            devs.append(HiveSensorEntity(hive, dev))
    async_add_entities(devs, True)


class HiveSensorEntity(HiveEntity, Entity):
    """Hive Sensor Entity."""

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
    def available(self):
        """Return if sensor is available"""
        if self.device["hive_type"] not in ("sense", "Availability"):
            return self.device.get("device_data", {}).get("online", True)
        return True

    @property
    def device_class(self):
        """Device class of the entity."""
        return DEVICETYPE[self.device["hive_type"]].get('type', None)

    @property
    def icon(self):
        """Return the icon to use."""
        if self.device["hive_type"] == "Battery":
            return icon_for_battery_level(battery_level=self.device["status"]["state"])
        else:
            return DEVICETYPE[self.device["hive_type"]]['icon']

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return DEVICETYPE[self.device["hive_type"]].get('unit', None)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.device["ha_name"]

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device["status"]["state"]

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self.attributes

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        if self.device["custom"] in ("Heating_TargetTemperature", "Availability", "Mode", "Battery"):
            return True

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.update_data(self.device)
        self.device = await self.hive.sensor.get_sensor(self.device)
        if self.device["hive_type"] == "CurrentTemperature":
            self.attributes = await self.get_current_temp_sa()
        elif self.device["hive_type"] == "Heating_State":
            self.attributes = await self.get_heating_state_sa()
        elif self.device["hive_type"] == "Heating_Mode":
            self.attributes = await self.get_heating_state_sa()
        elif self.device["hive_type"] == "Heating_Boost":
            s_a = {}
            if await self.hive.heating.boost(self.device) == "ON":
                minsend = await self.hive.heating.get_boost_time(self.device)
                s_a.update({"Boost ends in":
                            (str(minsend) + " minutes")})
            self.attributes = s_a
        elif self.device["hive_type"] == "Hotwater_State":
            self.attributes = await self.get_hotwater_state_sa()
        elif self.device["hive_type"] == "Hotwater_Mode":
            self.attributes = await self.get_hotwater_state_sa()
        elif self.device["hive_type"] == "Hotwater_Boost":
            s_a = {}
            if await self.hive.hotwater.get_boost(self.device) == "ON":
                endsin = await self.hive.hotwater.get_boost_time(self.device)
                s_a.update({"Boost ends in":
                            (str(endsin) + " minutes")})
            self.attributes = s_a

    async def get_current_temp_sa(self):
        """Get current heating temperature state attributes."""
        s_a = {}
        temp_current = 0
        temperature_target = 0
        temperature_difference = 0

        minmax_temps = await self.hive.heating.minmax_temperatures(self.device)
        if minmax_temps is not None:
            s_a.update({"Today Min / Max":
                        str(minmax_temps['TodayMin']) + " °C" + " / "
                        + str(minmax_temps['TodayMax']) + " °C"})

            s_a.update({"Restart Min / Max":
                        str(minmax_temps['RestartMin']) + " °C" + " / "
                        + str(minmax_temps['RestartMax']) + " °C"})

        temp_current = await self.hive.heating.current_temperature(self.device)
        temperature_target = await self.hive.heating.target_temperature(self.device)

        if temperature_target > temp_current:
            temperature_difference = temperature_target - temp_current
            temperature_difference = round(temperature_difference, 2)

            s_a.update({"Current Temperature":
                        temp_current})
            s_a.update({"Target Temperature":
                        temperature_target})
            s_a.update({"Temperature Difference":
                        temperature_difference})

        return s_a

    async def get_heating_state_sa(self):
        """Get current heating state, state attributes."""
        s_a = {}

        snan = await self.hive.heating.get_schedule_now_next_later(self.device)
        if snan is not None:
            if 'now' in snan:
                if ('value' in snan["now"] and
                        'start' in snan["now"] and
                        'Start_DateTime' in snan["now"] and
                        'End_DateTime' in snan["now"] and
                        'target' in snan["now"]["value"]):
                    now_target = str(snan["now"]["value"]["target"]) + " °C"
                    nstrt = snan["now"]["Start_DateTime"].strftime("%H:%M")
                    now_end = snan["now"]["End_DateTime"].strftime("%H:%M")

                    sa_string = (now_target
                                 + " : "
                                 + nstrt
                                 + " - "
                                 + now_end)
                    s_a.update({"Now": sa_string})

            if 'next' in snan:
                if ('value' in snan["next"] and
                        'start' in snan["next"] and
                        'Start_DateTime' in snan["next"] and
                        'End_DateTime' in snan["next"] and
                        'target' in snan["next"]["value"]):
                    next_target = str(snan["next"]["value"]["target"]) + " °C"
                    nxtstrt = snan["next"]["Start_DateTime"].strftime("%H:%M")
                    next_end = snan["next"]["End_DateTime"].strftime("%H:%M")

                    sa_string = (next_target
                                 + " : "
                                 + nxtstrt
                                 + " - "
                                 + next_end)
                    s_a.update({"Next": sa_string})

            if 'later' in snan:
                if ('value' in snan["later"] and
                        'start' in snan["later"] and
                        'Start_DateTime' in snan["later"] and
                        'End_DateTime' in snan["later"] and
                        'target' in snan["later"]["value"]):
                    ltarg = str(snan["later"]["value"]["target"]) + " °C"
                    lstrt = snan["later"]["Start_DateTime"].strftime("%H:%M")
                    lend = snan["later"]["End_DateTime"].strftime("%H:%M")

                    sa_string = (ltarg
                                 + " : "
                                 + lstrt
                                 + " - "
                                 + lend)
                    s_a.update({"Later": sa_string})
        else:
            s_a.update({"Schedule not active": ""})

        return s_a

    async def get_hotwater_state_sa(self):
        """Get current hotwater state, state attributes."""
        s_a = {}

        snan = await self.hive.hotwater.get_schedule_now_next_later(self.device)
        if snan is not None:
            if 'now' in snan:
                if ('value' in snan["now"] and
                        'start' in snan["now"] and
                        'Start_DateTime' in snan["now"] and
                        'End_DateTime' in snan["now"] and
                        'status' in snan["now"]["value"]):
                    now_status = snan["now"]["value"]["status"]
                    now_start = snan["now"]["Start_DateTime"].strftime("%H:%M")
                    now_end = snan["now"]["End_DateTime"].strftime("%H:%M")

                    sa_string = (now_status
                                 + " : "
                                 + now_start
                                 + " - "
                                 + now_end)
                    s_a.update({"Now": sa_string})

            if 'next' in snan:
                if ('value' in snan["next"] and
                        'start' in snan["next"] and
                        'Start_DateTime' in snan["next"] and
                        'End_DateTime' in snan["next"] and
                        'status' in snan["next"]["value"]):
                    next_status = snan["next"]["value"]["status"]
                    nxtstrt = snan["next"]["Start_DateTime"].strftime("%H:%M")
                    next_end = snan["next"]["End_DateTime"].strftime("%H:%M")

                    sa_string = (next_status
                                 + " : "
                                 + nxtstrt
                                 + " - "
                                 + next_end)
                    s_a.update({"Next": sa_string})
            if 'later' in snan:
                if ('value' in snan["later"] and
                        'start' in snan["later"] and
                        'Start_DateTime' in snan["later"] and
                        'End_DateTime' in snan["later"] and
                        'status' in snan["later"]["value"]):
                    later_status = snan["later"]["value"]["status"]
                    later_start = (snan["later"]
                                   ["Start_DateTime"].strftime("%H:%M"))
                    later_end = snan["later"]["End_DateTime"].strftime("%H:%M")

                    sa_string = (later_status
                                 + " : "
                                 + later_start
                                 + " - "
                                 + later_end)
                    s_a.update({"Later": sa_string})
        else:
            s_a.update({"Schedule not active": ""})

        return s_a
