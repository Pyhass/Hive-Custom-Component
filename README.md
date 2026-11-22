# Hive Custom Component

[![CI](https://github.com/Pyhass/Hive-Custom-Component/actions/workflows/ci.yml/badge.svg)](https://github.com/Pyhass/Hive-Custom-Component/actions/workflows/ci.yml)
[![Compatibility](https://github.com/Pyhass/Hive-Custom-Component/actions/workflows/compat.yml/badge.svg)](https://github.com/Pyhass/Hive-Custom-Component/actions/workflows/compat.yml)
![GitHub Release](https://img.shields.io/github/v/release/Pyhass/Hive-Custom-Component?display_name=tag&logo=Github)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.11.0%2B-41BDF5?logo=homeassistant)

An extended version of Home Assistant's built-in [Hive integration](https://www.home-assistant.io/integrations/hive/).
It sets up everything the built-in integration does, adds extra sensors and
options, and gets fixes and new versions of the Hive library sooner.

> [!IMPORTANT]
> This component **replaces** the built-in Hive integration (it uses the same
> `hive` domain). You can't run both at once. It needs **Home Assistant 2026.11.0
> or newer**.

## What you get on top of the built-in integration

| Feature | Details |
| --- | --- |
| **Boost ends** sensors | One for each heating zone and for hot water. Shows when the current boost finishes ("in 25 minutes"), and automations can trigger on it. Shows unknown when no boost is running. |
| **Availability** sensor | Whether each device is online or offline. |
| **Mode** sensor | The mode a device is in. |
| Extra heating attributes | On the current temperature sensor: today's min / max, min / max since restart, and how far the room is from its target. On the heating and hot water mode sensors: the schedule's **Now**, **Next** and **Later** slots. |
| Battery history | Battery levels record long-term statistics, so you can chart them. |
| Scan interval option | How often Hive is polled, from 30 seconds (default 120). The built-in integration's is fixed. |
| Earlier fixes | New versions of the Hive library ([`pyhive-integration`](https://pypi.org/project/pyhive-integration/)) usually ship here before they reach Home Assistant. |

Everything else (heating, hot water, TRVs, lights, plugs, sensors, the boost
actions) comes from the built-in integration unchanged, so its
[documentation](https://www.home-assistant.io/integrations/hive/) applies here too.

## Install

### HACS / new Marketplace (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Pyhass&repository=Hive-Custom-Component)

1. Click the button above, or search for **Hive** in [HACS](https://hacs.xyz/) / the new Marketplace.
2. Click **Download**.
3. Restart Home Assistant.

### Manually

1. Download `hive.zip` from the [latest release](https://github.com/Pyhass/Hive-Custom-Component/releases/latest).
2. Unzip it into `custom_components/hive` inside your Home Assistant configuration
   folder. Create the folders if they don't exist.
3. Restart Home Assistant.

## Set up

If you already use the built-in Hive integration, there's nothing to set up: see
[Switching from the built-in integration](#switching-from-the-built-in-integration).

1. Go to [**Settings → Devices & services**](https://my.home-assistant.io/redirect/integrations/).
2. Click **Add integration** and search for [**Hive**](https://my.home-assistant.io/redirect/config_flow_start/?domain=hive).
3. Sign in with your Hive account. If Hive sends you a code by text message, enter it.
4. Enter a **device name** (default "Home Assistant"). This registers Home Assistant
   as a trusted device on your Hive account, so it can stay signed in without asking
   for a new code.

> [!TIP]
> Use a device name that isn't already registered on your Hive account. If you set
> the integration up again, first remove the old Home Assistant device from the Hive
> app (see [Home Assistant loses its device registration](#home-assistant-loses-its-device-registration)).

### Options

Open the Hive integration and click **Configure** to change:

- **Scan interval:** how often to fetch new data from Hive, in seconds. The default is
  120, and the minimum is 30.

## Switching from the built-in integration

Because this component uses the same `hive` domain, it takes over your existing Hive
integration when you install it and restart. You don't have to sign in again, and
your devices, entities, entity IDs and automations stay as they are. The extra
sensors above are added alongside them.

To go back to the built-in integration, remove this component in HACS / Marketplace (or delete
`custom_components/hive`) and restart. The extra sensors become unavailable and can
be deleted from **Settings → Entities**.

## Updating

- **HACS / Marketplace:** it tells you when an update is available. Install it and restart.
- **Manually:** download the latest `hive.zip` again, replace the contents of
  `custom_components/hive` with it, and restart.

### Beta releases

Betas are a testing channel for the newest changes, including pre-release versions
of the Hive library. To get them, open this repository in HACS / Marketplace, choose **Redownload**,
and turn on **Show beta versions**. Stable releases only ever use stable library
versions. Please report anything a beta breaks.

## Troubleshooting

### Hive asks you to sign in again

When your Hive login expires, Home Assistant shows a **Reconfigure** prompt on the Hive integration. Click it and sign in, entering
the text message code if asked. Your devices and entities are kept, so don't delete
the integration.

### "Hive is already configured" when adding it

Look under **Settings → Devices &
services** for an ignored or disabled Hive entry. Re-enable it, or stop ignoring it,
instead of adding a new one.

### Home Assistant loses its device registration

If the integration keeps asking you to sign in, or reauth fails even with the right
code, Home Assistant may have lost its link to the device it registered on your Hive
account. Setting it up again with the same device name doesn't fix this while the old
registration is still there. To fix it:

1. In the Hive app, go to **Account settings → Security** and delete the device
   Home Assistant registered (the device name you entered during setup).
2. In Home Assistant, delete the Hive integration and add it again, following
   [Set up](#set-up).

### Turn on debug logs

Turn them on before reporting a problem. Either click **Enable debug
logging** on the Hive integration page, or add this to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.hive: debug
    apyhiveapi: debug
```

Remove your email address, tokens and device IDs before sharing logs.

## Reporting issues

Report bugs and ask for features in [this repository's issues](https://github.com/Pyhass/Hive-Custom-Component/issues).
Include the component version, the Home Assistant version and debug logs.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) to set up, test and open pull requests,
and [MAINTAINING.md](MAINTAINING.md) for releases and CI.
