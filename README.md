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


## Installing the integration
There are 2 ways you can install the Custom component, via HACS 
or by manually copying the hive files into your configuration

### HACS
The first and recommend way to install this custom component
is via HACS please follow this guide on how to intsall it if you have not already. - [Link to HACS](https://hacs.xyz/)

On completion of the installation via HACS you will need to navigate
to the integrations section within HACS and then install the latest version.

### Manually
This option requires you to manually copy the hive folder from the [latest release](https://github.com/Pyhive/HA-Hive-Custom-Component/releases/latest)
into the custom_component folder with your Home Assistant Configuration.

If this folder does not exist it will need creating before you copy 
the Hive folder from the release over.


## Setting up the integration
The integration can be setup in 2 ways see below

### Home Assistant UI
The first and recommend way is to setup the hive custom integration via the UI
to achieve this complete the following actions in the home assistant configuration.

Integrations >> Add Integration >> Hive

Once selecting the Hive integration a dialog flow will appear and ask you for your
Hive credentials and 2FA code if this is enabled, once finished Hive will be setup.

### Home Assistat YAML files
Setting this component up via YAML files requires adding the below into your home assistant 
configuration, replacing `<Your hive Username>` and `<Your hive Password>`
with your username and password used on the [Hive](https://hivehome.com/) website.
Once complete the integration will be setup and devices will be discovered and automatically added
to Home Assistant.

```yaml
hive:
  username: <Your hive Username>
  password: <Your hive Password>
```


If 2FA authentication is enabled on your account there is an extra step required to autheticate.
Once home assistant has started up there will be a notification advising that new device have dicovered.
Actioning this notificatin will take you through to the integrations confgiuration where you will be
required to complete the setup and enter a 2FA code.

## Updating the integration
Update are commited and released to github below is how to update based on your installation method.

### Update via HACS
Updating after installation is easy just navigate to the HACS panel and you will be notified of an available update.


### Update Manually
To update to the latest version manually it is required to delete the hive folder within custom_components.
Once completed copy the [latest release](https://github.com/Pyhive/HA-Hive-Custom-Component/releases/latest) back into the custom_compoents folder and restart home assistant.

:warning: **Setting up this custom version will overwrite the default integration.**
