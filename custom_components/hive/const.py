"""Constants for Hive."""
CONFIG_ENTRY_VERSION = 1
DEFAULT_NAME = "Hive"
DOMAIN = "hive"
CONF_CODE = "2fa"
CONF_ADD_SENSORS = "add_sensors"
CONF_DEBUG = "debug"
CONF_DEBUG_LEVEL = "debug_level"  # Currently ununsed
ICONURL = "https://www.hivehome.com/assets/hive-primary-logo-7d08f9ec5f0b7902cbbc8a1c4fc410c4de53999c135ef3c8c65cfe37ba739637.svg"
SET_CUSTOM_OPTIONS = ["scan_interval",
                      CONF_DEBUG]
SET_OPTIONS = ["scan_interval"]
DEBUG_OPTIONS = ["All",
                 "Action",
                 "Attribute",
                 "API",
                 "ERROR",
                 "Extra",
                 "Heating",
                 "Hotwater",
                 "Light",
                 "Sensor",
                 "Session",
                 "Switch"]
DEBUG_LEVEL_OPTIONS = ["critical", "error",
                       "warning", "info", "debug"]  # Currently ununsed
