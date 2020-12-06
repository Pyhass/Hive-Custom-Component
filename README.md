# Hive Custom Component

This is a custom version of the Home Assistant Hive 
component. This version will setup the Home assitant
hive component, but will also take device attributes
within the hive system and set them up as individual
sensors e.g `Living Room Lamp Battery Level`

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

Issues and trouble reports should be reported in 
the issues tab:

[**>> Report issues here <<**](https://github.com/Pyhive/HA-Hive-Custom-Component/issues)


## Install
There are 2 ways to install the Hive custom component see below.

### HACS
The recommended way to is to install via [HACS](https://hacs.xyz/).
Once HACS has been installed and setup. You just need to navigate to the HACS panel and choose integrations.
This will show and option to add an integration click it and search for Hive in the presented popup.

Once installation is complete please follow the [setup section](#setup) to set the Hive integration up.

### Manally
To install the Hive integration manually you need to download the [latest version](https://github.com/Pyhive/HA-Hive-Custom-Component/releases/latest).
Once downloaded you will need to copy the Hive folder into the custom_components folder within your home assistant configuration, if this does not exist then the folder will need creating.

Once installation is complete please follow the [setup section](#setup) to set the Hive integration up.

## Setup

### UI
The component can be setup in the Home assistant UI by doing the following actions.

- 1 Navigate to the Home Assisatnt Configuration.
- 2 Open the integrations panel.
- 3 Click the add integrations option
- 4 Search for Hive
- 5 Follow onboarding insturctions to setup Hive.

### YAML
This component can be setup by adding the below into your home assistant 
configuration, replacing `<Your hive Username>` and `<Your hive Password>`
with your username and password used on the [Hive](https://hivehome.com/) website.
Once complete the integration will be setup and devices will be discovered and 
automatically added to Home Assistant.

```yaml
hive:
  username: <Your hive Username>
  password: <Your hive Password>
```

## Options
Once the integration is installed and configured with home assistant you will be able to 
change the below options from the Home Assistant integration page.

- 1 Scan Interval - 
This determines how often the integration should communicate with Hive to retrieve new data.
The defualt configuration is 120 seconds but can be reduced to as low as 15 seconds.

- 2 Debug Categories - 
This give you the flex ability to switch on debugging mode for individual categories e.g. Lights, Switches
It is switched off by default but can be enabled by updating the options withn the home assistant integrations page.
Home Assistant also neeeds to know that you want to debug the system so the below YAML will need to be added also.

```yaml
logger:
  default: warning
  logs:
    custom_components.hive: debug
    pyhiveapi: debug
```

## Update
Update instructions based on installation method.

### HACS
Hacs will auto notify you within the HACS panel that there is a pending update.

### Manally
To update to the next version download the [latest version](https://github.com/Pyhive/HA-Hive-Custom-Component/releases/latest) again
and replace the current hive folder with the newly downloaded one.

## Configuring

This component will retreive the hive data and 
update Home Assistant every 2 minutes by default.
This can updated in the integrations page by 
clicking the options button for the integration.
The scan interval is configured in seconds and 
can be reduced to a minimum of 15 second intervals.

:warning: **Setting up this custom version will overwrite the default integration.**
