"""Support for the Hive sensors."""
from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HiveEntity
from .const import DOMAIN

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="Heating_Current_Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="Heating_Target_Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
    ),
    SensorEntityDescription(
        key="Heating_State",
        icon="mdi:radiator",
    ),
    SensorEntityDescription(
        key="Heating_Mode",
        icon="mdi:radiator",
    ),
    SensorEntityDescription(
        key="Heating_Boost",
        icon="mdi:radiator",
    ),
    SensorEntityDescription(
        key="Hotwater_State",
        icon="mdi:water-pump",
    ),
    SensorEntityDescription(
        key="Hotwater_Mode",
        icon="mdi:water-pump",
    ),
    SensorEntityDescription(
        key="Hotwater_Boost",
        icon="mdi:water-pump",
    ),
    SensorEntityDescription(
        key="Mode",
        icon="mdi:eye",
    ),
    SensorEntityDescription(
        key="Availability",
        icon="mdi:check-circle"
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hive thermostat based on a config entry."""
    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("sensor")
    entities = []
    if devices:
        for description in SENSOR_TYPES:
            for dev in devices:
                if dev["hiveType"] == description.key:
                    entities.append(HiveSensorEntity(hive, dev, description))
    async_add_entities(entities, True)


class HiveSensorEntity(HiveEntity, SensorEntity):
    """Hive Sensor Entity."""

    def __init__(self, hive, hive_device, entity_description):
        """Initialise hive sensor."""
        super().__init__(hive, hive_device)
        self.entity_description = entity_description

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.sensor.getSensor(self.device)
        
        if self.device["hiveType"] == "CurrentTemperature":
            self._attr_extra_state_attributes = await self.get_current_temp_sa()
        elif self.device["hiveType"] == "Heating_State":
            self._attr_extra_state_attributes = await self.get_heating_state_sa()
        elif self.device["hiveType"] == "Heating_Mode":
            self._attr_extra_state_attributes = await self.get_heating_state_sa()
        elif self.device["hiveType"] == "Heating_Boost":
            s_a = {}
            if await self.hive.heating.getBoostStatus(self.device) == "ON":
                minsend = await self.hive.heating.getBoostTime(self.device)
                s_a.update({"Boost ends in": (str(minsend) + " minutes")})
            self._attr_extra_state_attributes = s_a
        elif self.device["hiveType"] == "Hotwater_State":
            self._attr_extra_state_attributes = await self.get_hotwater_state_sa()
        elif self.device["hiveType"] == "Hotwater_Mode":
            self._attr_extra_state_attributes = await self.get_hotwater_state_sa()
        elif self.device["hiveType"] == "Hotwater_Boost":
            s_a = {}
            if await self.hive.hotwater.getBoost(self.device) == "ON":
                endsin = await self.hive.hotwater.getBoostTime(self.device)
                s_a.update({"Boost ends in": (str(endsin) + " minutes")})
            self._attr_extra_state_attributes = s_a
        
        if self.device["hiveType"] not in ("sense", "Availability"):
            self._attr_available = self.device.get("deviceData", {}).get("online", True)
        else:
            self._attr_available = True
        
        if self._attr_available:
            self._attr_native_value = self.device["status"]["state"]

    async def get_current_temp_sa(self):
        """Get current heating temperature state attributes."""
        s_a = {}
        temp_current = 0
        temperature_target = 0
        temperature_difference = 0

        minmax_temps = await self.hive.heating.minmaxTemperature(self.device)
        if minmax_temps is not None:
            s_a.update(
                {
                    "Today Min / Max": str(minmax_temps["TodayMin"])
                    + " °C"
                    + " / "
                    + str(minmax_temps["TodayMax"])
                    + " °C"
                }
            )

            s_a.update(
                {
                    "Restart Min / Max": str(minmax_temps["RestartMin"])
                    + " °C"
                    + " / "
                    + str(minmax_temps["RestartMax"])
                    + " °C"
                }
            )

        temp_current = await self.hive.heating.currentTemperature(self.device)
        temperature_target = await self.hive.heating.targetTemperature(self.device)

        if temperature_target > temp_current:
            temperature_difference = temperature_target - temp_current
            temperature_difference = round(temperature_difference, 2)

            s_a.update({"Current Temperature": temp_current})
            s_a.update({"Target Temperature": temperature_target})
            s_a.update({"Temperature Difference": temperature_difference})

        return s_a

    async def get_heating_state_sa(self):
        """Get current heating state, state attributes."""
        s_a = {}

        snan = await self.hive.heating.getScheduleNowNextLater(self.device)
        if snan is not None:
            if "now" in snan:
                if (
                    "value" in snan["now"]
                    and "start" in snan["now"]
                    and "Start_DateTime" in snan["now"]
                    and "End_DateTime" in snan["now"]
                    and "target" in snan["now"]["value"]
                ):
                    now_target = str(snan["now"]["value"]["target"]) + " °C"
                    nstrt = snan["now"]["Start_DateTime"].strftime("%H:%M")
                    now_end = snan["now"]["End_DateTime"].strftime("%H:%M")

                    sa_string = now_target + " : " + nstrt + " - " + now_end
                    s_a.update({"Now": sa_string})

            if "next" in snan:
                if (
                    "value" in snan["next"]
                    and "start" in snan["next"]
                    and "Start_DateTime" in snan["next"]
                    and "End_DateTime" in snan["next"]
                    and "target" in snan["next"]["value"]
                ):
                    next_target = str(snan["next"]["value"]["target"]) + " °C"
                    nxtstrt = snan["next"]["Start_DateTime"].strftime("%H:%M")
                    next_end = snan["next"]["End_DateTime"].strftime("%H:%M")

                    sa_string = next_target + " : " + nxtstrt + " - " + next_end
                    s_a.update({"Next": sa_string})

            if "later" in snan:
                if (
                    "value" in snan["later"]
                    and "start" in snan["later"]
                    and "Start_DateTime" in snan["later"]
                    and "End_DateTime" in snan["later"]
                    and "target" in snan["later"]["value"]
                ):
                    ltarg = str(snan["later"]["value"]["target"]) + " °C"
                    lstrt = snan["later"]["Start_DateTime"].strftime("%H:%M")
                    lend = snan["later"]["End_DateTime"].strftime("%H:%M")

                    sa_string = ltarg + " : " + lstrt + " - " + lend
                    s_a.update({"Later": sa_string})
        else:
            s_a.update({"Schedule not active": ""})

        return s_a

    async def get_hotwater_state_sa(self):
        """Get current hotwater state, state attributes."""
        s_a = {}

        snan = await self.hive.hotwater.getScheduleNowNextLater(self.device)
        if snan is not None:
            if "now" in snan:
                if (
                    "value" in snan["now"]
                    and "start" in snan["now"]
                    and "Start_DateTime" in snan["now"]
                    and "End_DateTime" in snan["now"]
                    and "status" in snan["now"]["value"]
                ):
                    now_status = snan["now"]["value"]["status"]
                    now_start = snan["now"]["Start_DateTime"].strftime("%H:%M")
                    now_end = snan["now"]["End_DateTime"].strftime("%H:%M")

                    sa_string = now_status + " : " + now_start + " - " + now_end
                    s_a.update({"Now": sa_string})

            if "next" in snan:
                if (
                    "value" in snan["next"]
                    and "start" in snan["next"]
                    and "Start_DateTime" in snan["next"]
                    and "End_DateTime" in snan["next"]
                    and "status" in snan["next"]["value"]
                ):
                    next_status = snan["next"]["value"]["status"]
                    nxtstrt = snan["next"]["Start_DateTime"].strftime("%H:%M")
                    next_end = snan["next"]["End_DateTime"].strftime("%H:%M")

                    sa_string = next_status + " : " + nxtstrt + " - " + next_end
                    s_a.update({"Next": sa_string})
            if "later" in snan:
                if (
                    "value" in snan["later"]
                    and "start" in snan["later"]
                    and "Start_DateTime" in snan["later"]
                    and "End_DateTime" in snan["later"]
                    and "status" in snan["later"]["value"]
                ):
                    later_status = snan["later"]["value"]["status"]
                    later_start = snan["later"]["Start_DateTime"].strftime(
                        "%H:%M")
                    later_end = snan["later"]["End_DateTime"].strftime("%H:%M")

                    sa_string = later_status + " : " + later_start + " - " + later_end
                    s_a.update({"Later": sa_string})
        else:
            s_a.update({"Schedule not active": ""})

        return s_a
