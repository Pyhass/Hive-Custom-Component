# Hive Custom Component

This is a custom version of the Home Assistant Hive 
component. This version will setup the Home assitant
hive component, but will also take device attributes
within the hive system and set them up as individual
sensors e.g `Living Room Lamp Battery Level`

For details on what the home assistant hive 
component supports please see below:

[**>> Hive Component Documentation <<**](https://www.home-assistant.io/integrations/hive/)

Issues and trouble reports should be reported in 
the issues tab:

[**>> Report issues here <<**](https://github.com/Pyhive/HA-Hive-Custom-Component/issues)


## Installing

I recommend that you install this component
via [HACS](https://hacs.xyz/), that way you
get updates automatically. But you can just
copy and paste the files into the 
custom component directory.

## Setting up

This component can be setup via 2 methods the
first is via integrations page. This will 
prompt you to enter your hive username and 
password. Once complete the integration will be
setup and devices will be discovered and
automatically added to Home Assistant. 
The second option is to add the below into your 
Home Assistant confguration.

```yaml
hive:
  username: <Your Username>
  password: <Your Password>
```

## Configuring

This component will retreive the hive data and 
update Home Assistant every 2 minutes by default.
This can updated in the integrations page by 
clicking the options button for the integration.
The scan interval is configured in seconds and 
can be reduced to a minimum of 15 second intervals.

:warning: **Setting up this custom version will overwrite the default integration.**




!! Setting up this custom version will overwrite the default integration.
