# Hive Custom Component

This is a custom version of the Home Assistant Hive component.
This version will setup the Home assistant hive component, but will
also take device attributes within the hive system and set them up 
as individual sensors e.g `Living Room Lamp Battery Level`

* Additional Sensor types.
  * Availability - online/offline
  * Mode - Manual/Schedule
  * Battery Level
  * Current Temperature - Heating/Hotwater only
  * Target Tenperature - Heating/Hotwater only
  * Current State - Heating/Hotwater only
  * Boost State - Heating/Hotwater only



For details on what the home assistant hive component supports please see below:

[**>> Hive Component Documentation <<**](https://www.home-assistant.io/integrations/hive/)

Issues and trouble reports should be reported in the issues tab:

[**>> Report issues here <<**](https://github.com/Pyhive/HA-Hive-Custom-Component/issues)


## Installing

I recommend that you install this component via [HACS](https://hacs.xyz/),
that way you get updates automatically. But you can just copy and paste the 
files into the custom component directory.

## Setting up

This component can be setup by adding the below into your home assistant 
configuration, replacing `<Your hive Username>` and `<Your hive Password>`
with your username and password used on the [Hive](https://hivehome.com/) website.
The scan interval is a time period set in minutes and this controls the interval
as to how often the integration shold pull new data from hive.Once complete the
integration will be setup and devices will be discovered and automatically added
to Home Assistant.

```yaml
hive:
  username: <Your hive Username>
  password: <Your hive Password>
  scan_interval: 2 
```

:warning: **Setting up this custom version will overwrite the default integration.**
