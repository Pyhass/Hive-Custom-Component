# Hive Custom Component

![Pylint](https://github.com/Pyhive/HA-Hive-Custom-Component/workflows/Pylint/badge.svg)
![GitHub Release](https://img.shields.io/github/v/release/Pyhive/HA-Hive-Custom-Component?display_name=tag&logo=Github)



This is a custom version of the Home Assistant Hive
component. This version will setup the Home Assistant
Hive component, but will also take device attributes
within the Hive system and set them up as individual
sensors e.g `Living Room Lamp Battery Level`

* Additional Sensor types:
  * Availability - Online/Offline
  * Mode - Manual/Schedule
  * Battery Level
  * Current Temperature - Heating/Hotwater only
  * Target Temperature - Heating/Hotwater only
  * Current State - Heating/Hotwater only
  * Boost State - Heating/Hotwater only

For details on what the Home Assistant Hive component supports, please see below:

[**>> Hive Component Documentation <<**](https://www.home-assistant.io/integrations/hive/)

Issues and trouble reports should be reported in
the issues tab:

[**>> Report issues here <<**](https://github.com/Pyhive/HA-Hive-Custom-Component/issues)

## Install

There are two ways to install the Hive custom component see below.

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

* 1  - Navigate to the Home Assistant [Configuration](https://my.home-assistant.io/redirect/config/).
* 2  - Open the [integrations](https://my.home-assistant.io/redirect/integrations/) panel.
* 3  - Click the add integrations option.
* 4  - Search for [Hive](https://my.home-assistant.io/redirect/config_flow_start/?domain=hive)
* 5  - Follow onboarding instructions to setup Hive.

## Options

Once the integration is installed and configured with Home Assistant you will be able to
change the below options from the Home Assistant integration page.

* 1 - **Scan Interval**
This determines how often the integration should communicate with Hive to retrieve new data.
The default configuration is 120 seconds but can be reduced to as low as 30 seconds.

## Update

Update instructions based on installation method.

### HACS Update

Hacs will auto notify you within the HACS panel that there is a pending update.

### Manual Update

To update to the next version download the [latest version](https://github.com/Pyhive/HA-Hive-Custom-Component/releases/latest) again
and replace the current hive folder with the newly downloaded one.


:warning: **Setting up this custom version will overwrite the default integration.**
