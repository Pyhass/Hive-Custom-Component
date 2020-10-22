"""Config Flow for Hive."""
from collections import OrderedDict
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_SCAN_INTERVAL
from homeassistant.helpers import aiohttp_client
from .const import CONFIG_ENTRY_VERSION, DOMAIN, CONF_CODE
from pyhiveapi import Hive_Async, Session, HiveAuth

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class HiveFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Hive config flow."""

    VERSION = CONFIG_ENTRY_VERSION
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""

        self.websession = None
        self.hive = None
        self.hive_auth = None
        self.email_address = None
        self.password = None

    async def async_step_user(self, user_input=None):
        """Prompt user input. Create or edit entry."""
        errors = {}
        # Login to Hive with user data.
        if user_input is not None:
            self.email_address = user_input[CONF_USERNAME]
            self.password = user_input[CONF_PASSWORD]
            self.websession = aiohttp_client.async_get_clientsession(self.hass)
            self.hive = Hive_Async(self.websession)
            self.hive_auth = HiveAuth(
                username=self.email_address, password=self.password)

            # Check if the hive account is already setup.
            c_entries = self.hass.config_entries.async_entries(DOMAIN)
            if c_entries:
                for entry in c_entries:
                    c_entry_user = entry.data["username"]
                    if self.email_address == c_entry_user:
                        # Abort an entry already exists with a created token
                        return self.async_abort(reason="already_configured")

            # Login to the Hive.
            resp = await self.hive_auth.login()

            if resp == "INVALID_USER":
                errors["base"] = "invalid_user"
            elif resp == "INVALID_PASSWORD":
                errors["base"] = "invalid_password"
            else:
                # Check if the login was successful.
                if resp["ChallengeName"] == "SMS_MFA":
                    # Complete SMS 2FA.
                    resp = await self.async_step_2fa(resp=resp)

                if resp["ChallengeName"] is None:
                    # Setup the config entry
                    return self.async_create_entry(
                        title=self.email_address,
                        data={"username": self.email_address,
                              "password": self.password
                              }
                    )
                else:
                    errors["base"] = "unknown"

        # Show User Input form.
        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_USERNAME)] = str
        data_schema[vol.Required(CONF_PASSWORD)] = str

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )

    async def async_step_2fa(self, user_input=None, resp=None):
        """Handle 2fa step."""
        sms_errors = {}

        if user_input:
            result = await self.hive_auth.sms_2fa(user_input["2fa"], resp)

            if result == 'INVAlID_CODE':
                errors["base"] = "invalid_code"
            else:
                return result

        sms_data_schema = OrderedDict()
        sms_data_schema[vol.Required(CONF_CODE)] = str

        return self.async_show_form(
            step_id="2fa",
            data_schema=vol.Schema(sms_data_schema),
            errors=sms_errors
        )

    async def async_step_import(self, info):
        """Use auth from config (Username & Password)."""

        # Get user from existing entry and abort if already setup
        c_entries = self.hass.config_entries.async_entries(DOMAIN)
        if c_entries:
            for entry in c_entries:
                c_entry_user = entry.data["username"]
                if info["username"] == c_entry_user:
                    # Abort an entry already exists with a created token
                    return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title=info["username"],
            data={"username": info["username"],
                  "password": info["password"]}
        )

    @ staticmethod
    @ callback
    def async_get_options_flow(config_entry):
        """Hive options callback."""
        return HiveOptionsFlowHandler(config_entry)


class HiveOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for Hive."""

    def __init__(self, config_entry):
        """Initialize Hive options flow."""
        self.hive = Session()
        self.interval = config_entry.options.get(CONF_SCAN_INTERVAL, 120)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            new_interval = user_input.get(CONF_SCAN_INTERVAL, 120)
            if new_interval < 15:
                new_interval = 15
                user_input[CONF_SCAN_INTERVAL] = new_interval
            await self.hive.update_interval(new_interval)
            return self.async_create_entry(title="", data=user_input)

        data_schema = OrderedDict()
        data_schema[vol.Optional(
            CONF_SCAN_INTERVAL, default=self.interval)] = int

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema))
