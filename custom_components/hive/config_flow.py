"""Config Flow for Hive."""

from __future__ import annotations

from collections.abc import Mapping
import copy
from typing import Any

from apyhiveapi import Auth
from apyhiveapi.helper.hive_exceptions import (
    HiveApiError,
    HiveInvalid2FACode,
    HiveInvalidPassword,
    HiveInvalidUsername,
)
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback
import logging

from . import HiveConfigEntry
from .const import (
    CONF_CODE,
    CONF_DEVICE_NAME,
    CONF_DISABLE_2FA_DEBUG,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of payload with sensitive values masked for logs."""

    def _mask(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if len(value) <= 8:
            return "***"
        return f"{value[:4]}...{value[-4:]}"

    def _walk(node: Any) -> Any:
        if isinstance(node, dict):
            result: dict[str, Any] = {}
            for key, value in node.items():
                key_lower = key.lower()
                if any(part in key_lower for part in ("password", "token", "secret", "code", "session")):
                    result[key] = _mask(value)
                else:
                    result[key] = _walk(value)
            return result
        if isinstance(node, list):
            return [_walk(item) for item in node]
        return node

    return _walk(copy.deepcopy(payload))


class HiveFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Hive config flow."""

    VERSION = CONFIG_ENTRY_VERSION
    hive_auth: Auth

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.tokens: dict[str, str] = {}
        self.device_registration: bool = False
        self.device_name = "Home Assistant"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt user input. Create or edit entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.data.update(
                {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_DISABLE_2FA_DEBUG: bool(
                        user_input.get(CONF_DISABLE_2FA_DEBUG, False)
                    ),
                }
            )
            self.hive_auth = Auth(
                username=self.data[CONF_USERNAME], password=self.data[CONF_PASSWORD]
            )

            await self.async_set_unique_id(self.data[CONF_USERNAME])
            if self.context["source"] != SOURCE_REAUTH:
                self._abort_if_unique_id_configured()

            try:
                self.tokens = await self.hive_auth.login()
                _LOGGER.debug(
                    "Hive login response (sanitized): %s",
                    _sanitize_payload(self.tokens),
                )
            except HiveInvalidUsername:
                errors["base"] = "invalid_username"
            except HiveInvalidPassword:
                errors["base"] = "invalid_password"
            except HiveApiError:
                errors["base"] = "no_internet_available"

            if self.tokens.get("ChallengeName") == "SMS_MFA":
                if self.data.get(CONF_DISABLE_2FA_DEBUG):
                    _LOGGER.warning(
                        "Hive returned SMS_MFA and disable_2fa_debug is enabled. "
                        "Skipping 2FA submission for debug. Challenge payload: %s",
                        _sanitize_payload(self.tokens),
                    )
                    errors["base"] = "twofa_bypassed_debug"
                else:
                    return await self.async_step_2fa()

            if not errors and "AuthenticationResult" in self.tokens:
                auth_result = self.tokens.get("AuthenticationResult", {})
                new_device = auth_result.get("NewDeviceMetadata") or {}
                access_token = auth_result.get("AccessToken")
                if new_device.get("DeviceGroupKey") and new_device.get("DeviceKey") and access_token:
                    # If Hive returned fresh device metadata directly from login, register it now
                    # so fallback device auth works when refresh tokens expire.
                    self.hive_auth.access_token = access_token
                    self.hive_auth.device_group_key = new_device["DeviceGroupKey"]
                    self.hive_auth.device_key = new_device["DeviceKey"]
                    try:
                        await self.hive_auth.device_registration(self.device_name)
                        self.data["device_data"] = await self.hive_auth.get_device_data()
                        _LOGGER.debug("Stored Hive device_data from login NewDeviceMetadata.")
                    except HiveApiError:
                        _LOGGER.warning("Hive device registration failed after login; continuing without device_data.")

                try:
                    return await self.async_setup_hive_entry()
                except UnknownHiveError:
                    errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_DISABLE_2FA_DEBUG, default=False): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_2fa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle 2fa step."""
        errors = {}

        if user_input and user_input["2fa"] == "0000":
            _LOGGER.debug("2FA resend requested (code 0000).")
            self.tokens = await self.hive_auth.login()
            _LOGGER.debug(
                "Hive login response after 2FA resend request (sanitized): %s",
                _sanitize_payload(self.tokens),
            )
        elif user_input:
            try:
                self.tokens = await self.hive_auth.sms_2fa(
                    user_input["2fa"], self.tokens
                )
                _LOGGER.debug(
                    "Hive 2FA response (sanitized): %s",
                    _sanitize_payload(self.tokens),
                )
            except HiveInvalid2FACode:
                errors["base"] = "invalid_code"
            except HiveApiError:
                errors["base"] = "no_internet_available"

            if not errors:
                if self.source == SOURCE_REAUTH:
                    return await self.async_setup_hive_entry()
                self.device_registration = True
                return await self.async_step_configuration()

        schema = vol.Schema({vol.Required(CONF_CODE): str})
        return self.async_show_form(step_id="2fa", data_schema=schema, errors=errors)

    async def async_step_configuration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle hive configuration step."""
        errors = {}

        if user_input:
            if self.device_registration:
                self.device_name = user_input["device_name"]
                await self.hive_auth.device_registration(user_input["device_name"])
                self.data["device_data"] = await self.hive_auth.get_device_data()

            try:
                return await self.async_setup_hive_entry()
            except UnknownHiveError:
                errors["base"] = "unknown"

        schema = vol.Schema(
            {vol.Optional(CONF_DEVICE_NAME, default=self.device_name): str}
        )
        return self.async_show_form(
            step_id="configuration", data_schema=schema, errors=errors
        )

    async def async_setup_hive_entry(self) -> ConfigFlowResult:
        """Finish setup and create the config entry."""

        if "AuthenticationResult" not in self.tokens:
            raise UnknownHiveError

        self.data["tokens"] = self.tokens
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                title=self.data["username"],
                data=self.data,
                reason="reauth_successful",
            )
        return self.async_create_entry(title=self.data["username"], data=self.data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Re Authenticate a user."""
        data = {
            CONF_USERNAME: entry_data[CONF_USERNAME],
            CONF_PASSWORD: entry_data[CONF_PASSWORD],
        }
        return await self.async_step_user(data)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: HiveConfigEntry,
    ) -> HiveOptionsFlowHandler:
        """Hive options callback."""
        return HiveOptionsFlowHandler(config_entry)


class HiveOptionsFlowHandler(OptionsFlow):
    """Config flow options for Hive."""

    config_entry: HiveConfigEntry

    def __init__(self, config_entry: HiveConfigEntry) -> None:
        """Initialize Hive options flow."""
        self.hive = None
        self.interval = config_entry.options.get(CONF_SCAN_INTERVAL, 120)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        self.hive = self.config_entry.runtime_data
        errors: dict[str, str] = {}
        if user_input is not None:
            new_interval = user_input.get(CONF_SCAN_INTERVAL)
            assert self.hive
            await self.hive.updateInterval(new_interval)
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=self.interval): vol.All(
                    vol.Coerce(int), vol.Range(min=30)
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class UnknownHiveError(Exception):
    """Catch unknown hive error."""
