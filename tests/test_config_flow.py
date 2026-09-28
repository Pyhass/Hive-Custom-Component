"""Tests for the Hive config and options flows."""

from unittest.mock import AsyncMock, MagicMock

from apyhiveapi.helper.hive_exceptions import (
    HiveApiError,
    HiveInvalid2FACode,
    HiveInvalidPassword,
    HiveInvalidUsername,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hive.const import CONF_CODE, CONF_DEVICE_NAME, DOMAIN

from .conftest import DEVICE_DATA, PASSWORD, TOKENS, USERNAME

SMS_CHALLENGE = {"ChallengeName": "SMS_MFA", "Session": "session-token"}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def _start_user_flow(hass: HomeAssistant) -> dict:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )


async def test_user_flow_without_2fa(hass: HomeAssistant, mock_auth: MagicMock) -> None:
    """Login that returns tokens straight away creates the entry."""
    result = await _start_user_flow(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"]["tokens"] == TOKENS
    assert result["result"].unique_id == USERNAME
    mock_auth.device_registration.assert_not_awaited()


async def test_user_flow_registers_device_from_login_metadata(
    hass: HomeAssistant, mock_auth: MagicMock
) -> None:
    """NewDeviceMetadata in the login response is registered and stored."""
    mock_auth.login.return_value = {
        "AuthenticationResult": {
            **TOKENS["AuthenticationResult"],
            "NewDeviceMetadata": {"DeviceGroupKey": "group", "DeviceKey": "key"},
        }
    }

    result = await _start_user_flow(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["device_data"] == DEVICE_DATA
    mock_auth.device_registration.assert_awaited_once_with("Home Assistant")


async def test_user_flow_with_2fa(hass: HomeAssistant, mock_auth: MagicMock) -> None:
    """SMS 2FA goes through the code and device name steps."""
    mock_auth.login.return_value = SMS_CHALLENGE

    result = await _start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "2fa"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CODE: "123456"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configuration"
    mock_auth.sms_2fa.assert_awaited_once_with("123456", SMS_CHALLENGE)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_NAME: "My HA"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["device_data"] == DEVICE_DATA
    mock_auth.device_registration.assert_awaited_once_with("My HA")


async def test_2fa_resend_code(hass: HomeAssistant, mock_auth: MagicMock) -> None:
    """Entering 0000 requests a new SMS code."""
    mock_auth.login.return_value = SMS_CHALLENGE
    result = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CODE: "0000"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "2fa"
    assert mock_auth.login.await_count == 2
    mock_auth.sms_2fa.assert_not_awaited()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (HiveInvalid2FACode, "invalid_code"),
        (HiveApiError, "no_internet_available"),
    ],
)
async def test_2fa_errors(
    hass: HomeAssistant, mock_auth: MagicMock, exception: type[Exception], error: str
) -> None:
    """2FA failures keep the user on the code step."""
    mock_auth.login.return_value = SMS_CHALLENGE
    mock_auth.sms_2fa.side_effect = exception
    result = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CODE: "123456"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "2fa"
    assert result["errors"] == {"base": error}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (HiveInvalidUsername, "invalid_username"),
        (HiveInvalidPassword, "invalid_password"),
        (HiveApiError, "no_internet_available"),
    ],
)
async def test_user_flow_login_errors(
    hass: HomeAssistant, mock_auth: MagicMock, exception: type[Exception], error: str
) -> None:
    """Login failures are shown on the user step and can be retried."""
    mock_auth.login.side_effect = exception

    result = await _start_user_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_auth.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unexpected_login_response(
    hass: HomeAssistant, mock_auth: MagicMock
) -> None:
    """A login response without tokens or a challenge doesn't create an entry.

    The form is shown again without an error message; this pins current behaviour.
    """
    mock_auth.login.return_value = {}

    result = await _start_user_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_2fa_debug_bypass(hass: HomeAssistant, mock_auth: MagicMock) -> None:
    """The debug toggle stops at the SMS challenge instead of asking for a code."""
    mock_auth.login.return_value = SMS_CHALLENGE
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, "disable_2fa_debug": True},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "twofa_bypassed_debug"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_auth: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The same account can't be added twice."""
    mock_config_entry.add_to_hass(hass)

    result = await _start_user_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_auth.login.assert_not_awaited()


async def test_reauth(
    hass: HomeAssistant, mock_auth: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Reauth logs in again and updates the existing entry."""
    mock_config_entry.add_to_hass(hass)
    new_tokens = {"AuthenticationResult": {"AccessToken": "new-access-token"}}
    mock_auth.login.return_value = new_tokens

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data["tokens"] == new_tokens


async def test_reauth_with_2fa_on_registered_device(
    hass: HomeAssistant, mock_auth: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Reauth with 2FA skips device registration when the device is known."""
    mock_config_entry.add_to_hass(hass)
    mock_auth.login.return_value = SMS_CHALLENGE

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "2fa"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CODE: "123456"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_auth.device_registration.assert_not_awaited()


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The scan interval option is saved and pushed to the Hive client."""
    mock_config_entry.add_to_hass(hass)
    hive = MagicMock()
    hive.updateInterval = AsyncMock()
    mock_config_entry.runtime_data = hive

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_SCAN_INTERVAL: 60}
    hive.updateInterval.assert_awaited_once_with(60)
