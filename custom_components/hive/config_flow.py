"""Config Flow for Hive."""
from collections import OrderedDict
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_SCAN_INTERVAL
from homeassistant.helpers import aiohttp_client
from .const import CONFIG_ENTRY_VERSION, DOMAIN
from pyhiveapi import Hive_Async, Session

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
        self.email_address = None
        self.password = None

    async def async_step_user(self, user_input=None):
        """Prompt user input. Create or edit entry."""
        errors = {}
        # Login to Hive with user data.
        if user_input is not None:
            self.websession = aiohttp_client.async_get_clientsession(self.hass)
            self.hive = Hive_Async(self.websession)
            self.email_address = user_input[CONF_USERNAME]
            self.password = user_input[CONF_PASSWORD]

            # Login to the Hive API
            is_login = await self.hive.login(self.email_address,
                                             self.password)

            # Check if the login was successful.
            if is_login["original"] in (400, 401, 403):
                errors["base"] = "failed_login"
            elif is_login["original"] == 408:
                errors["base"] = "login_timeout"
            else:
                # Login Successful
                login_token = is_login["parsed"]["token"]
                # Abort if token not found.
                if not login_token:
                    return self.async_abort(reason="login_error")

                # Get token from existing entry
                c_entries = self.hass.config_entries.async_entries(DOMAIN)
                if c_entries:
                    for entry in c_entries:
                        c_entry_user = entry.data["username"]
                        if self.email_address == c_entry_user:
                            # Abort an entry already exists with a created token
                            return self.async_abort(reason="already_configured")

                # Create long lived token
                token_request = await self.hive.create_token(login_token)

                if token_request["original"] != 200:
                    return self.async_abort(reason="long_lived_error")
                else:
                    # Store long lived token for future use.
                    token = token_request["parsed"]["accessTokens"][0]["token"]
                    token_id = token_request["parsed"]["accessTokens"][0]["id"]

                    # Create entry.
                    return self.async_create_entry(
                        title=self.email_address,
                        data={"username": self.email_address,
                              "token": token,
                              "token_id": token_id}
                    )

        # Show User Input form.
        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_USERNAME)] = str
        data_schema[vol.Required(CONF_PASSWORD)] = str

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
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

    @staticmethod
    @callback
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
