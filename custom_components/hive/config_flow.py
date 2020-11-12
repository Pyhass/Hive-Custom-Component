"""Config Flow for Hive."""
from pyhiveapi import HiveAuth, Session
from collections import OrderedDict
from datetime import datetime
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv
from .const import (CONFIG_ENTRY_VERSION, DOMAIN, SET_CUSTOM_OPTIONS, CONF_CODE,
                    CONF_ADD_SENSORS, CONF_DEBUG, DEBUG_OPTIONS)

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class HiveFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Hive config flow."""

    VERSION = CONFIG_ENTRY_VERSION
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.hive_auth = None
        self.data = None
        self.tokens = None
        self.root_source = None

    async def _show_setup_form(self, user_input=None, errors=None, step_id="user"):
        """Show the setup form to the user."""

        data_schema = OrderedDict()

        if user_input is None:
            user_input = {}

        if step_id == "user":
            data_schema[vol.Required(CONF_USERNAME)] = str
            data_schema[vol.Required(CONF_PASSWORD)] = str
            data_schema[vol.Optional(
                CONF_SCAN_INTERVAL, default=120)] = int
            data_schema[vol.Optional(
                CONF_DEBUG, default=[])] = cv.multi_select(DEBUG_OPTIONS)
            data_schema[vol.Optional(
                CONF_ADD_SENSORS, default=True)] = bool
        elif step_id == "2fa":
            data_schema[vol.Required(CONF_CODE)] = str

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(data_schema),
            errors=errors
        )

    async def async_step_user(self, user_input=None):
        """Prompt user input. Create or edit entry."""
        errors = {}
        # Login to Hive with user data.
        if user_input is not None:
            self.data = user_input
            self.data.update({"options": {}})
            for k in SET_CUSTOM_OPTIONS:
                self.data["options"].update({k: self.data[k]})
                del self.data[k]
            self.data["options"].update(
                {CONF_USERNAME: self.data[CONF_USERNAME]})
            self.hive_auth = HiveAuth(
                username=self.data[CONF_USERNAME],
                password=self.data[CONF_PASSWORD])

            # Get user from existing entry and abort if already setup
            for entry in self._async_current_entries() and self.root_source != 'REAUTH':
                if entry.data.get(CONF_USERNAME) == self.data[CONF_USERNAME]:
                    return self.async_abort(reason="already_configured")

            # Login to the Hive.
            self.tokens = await self.hive_auth.login()

            # Check if the login was successful.
            if self.tokens == "INVALID_USER":
                errors["base"] = "invalid_username"
            elif self.tokens == "INVALID_PASSWORD":
                errors["base"] = "invalid_password"
            elif self.tokens == "CONNECTION_ERROR":
                errors["base"] = "no_internet_available"
            else:
                # Check if SMS 2fa is required.
                if self.tokens.get("ChallengeName") == "SMS_MFA":
                    # Complete SMS 2FA.
                    return await self.async_step_2fa()
                else:
                    # Complete the entry setup.
                    return await self.async_step_finish()

        # Show User Input form.
        return await self._show_setup_form(errors=errors)

    async def async_step_2fa(self, user_input=None):
        """Handle 2fa step."""
        sms_errors = {}
        result = None

        if user_input:
            result = await self.hive_auth.sms_2fa(user_input["2fa"], self.tokens)

            if result == 'INVALID_CODE':
                sms_errors["base"] = "invalid_code"
                return await self._show_setup_form(errors=sms_errors, step_id="2fa")
            elif result == "CONNECTION_ERROR":
                sms_errors["base"] = "no_internet_available"
            else:
                self.tokens = result
                return await self.async_step_finish()
        else:
            return await self._show_setup_form(errors=sms_errors, step_id="2fa")

    async def async_step_finish(self, user_input=None):
        """Finish setup and create the config entry."""
        self.data["tokens"] = self.tokens.get(
            "AuthenticationResult", "ERROR")

        if "AccessToken" in self.data["tokens"]:
            # Setup the config entry
            self.data.update({"created": str(datetime.now())})

            return self.async_create_entry(
                title=self.data["username"],
                data=self.data
            )
        else:
            return self.async_abort(reason="unknown")

    async def async_step_reauth(self, user_input=None):
        """"Re-Authenticate a user."""
        self.root_source = 'REAUTH'
        return await self.async_step_user()

    async def async_step_import(self, import_config):
        """Use auth from config (Username & Password)."""
        self.email_address = import_config["username"]
        self.password = import_config["password"]
        self.hive_auth = HiveAuth(
            username=self.email_address, password=self.password)

        # Get user from existing entry and abort if already setup
        for entry in self._async_current_entries():
            if entry.data.get(CONF_USERNAME) == self.email_address:
                _LOGGER.warning(
                    "Dupliate configuration - Please delete one of the duplicate configurations")
                return self.async_abort(reason="already_configured")

        # Login to the Hive.
        self.data = await self.hive_auth.login()

        if self.data == "INVALID_USER":
            _LOGGER.error(
                "Incorrrect username - Please update configuration and restart Home Assistant.")
            return self.async_abort(reason="incorrect_username")
        elif self.data == "INVALID_PASSWORD":
            _LOGGER.error(
                "Incorrrect password - Please update configuration and restart Home Assistant.")
            return self.async_abort(reason="incorrect_password")
        else:
            return await self.async_step_finish()

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
        self.debug_list = config_entry.options.get(CONF_DEBUG, [])

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            new_interval = user_input[CONF_SCAN_INTERVAL]
            if new_interval < 15:
                new_interval = 15
                user_input[CONF_SCAN_INTERVAL] = new_interval

            await self.hive.log.check_debuging(user_input[CONF_DEBUG])
            await self.hive.update_interval(new_interval)
            return self.async_create_entry(title="", data=user_input)

        data_schema = OrderedDict()
        data_schema[vol.Optional(
            CONF_SCAN_INTERVAL, default=self.interval)] = int
        data_schema[vol.Optional(
            CONF_DEBUG, default=self.debug_list)] = cv.multi_select(DEBUG_OPTIONS)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema)
        )
