# Hive Custom Component

This is a custom version of the Home Assistant Hive component.
This version will take device attributes within the hive system
and set them up as individual sensors e.g `Living Room Lamp Battery Level`

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
configurstion. Once complete the integration will be setup and devices
will be discovered and automatically added to Home Assistant.

```yaml
hive:
  username: <Required:Your Username> -- This is your hive username used on hivehome.com
  password: <Required:Your Password> -- This is your hive password used on hivehome.com
  scan_interval: <Optional: 2> -- This is the peroid of times in minutes to update from Hive.
```

:warning: **Setting up this custom version will overwrite the default integration.**
