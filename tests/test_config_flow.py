"""Tests for the Paperless Lookup config flow (user, reauth, reconfigure)."""

from http import HTTPStatus
from typing import Any
from unittest.mock import patch

from aiohttp import ClientConnectionError
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.paperless_lookup.const import CONF_PAPERLESS_USER_ID, DOMAIN

from .conftest import (
    DEFAULT_OPTIONS,
    PAPERLESS_USER_ID,
    PAPERLESS_USERNAME,
    TEST_HTTPS_URL,
    TEST_TOKEN,
    TEST_URL,
    load_json_fixture,
    mock_paperless,
    ui_settings,
)

HTTPS_INPUT = {CONF_URL: TEST_HTTPS_URL, CONF_API_TOKEN: TEST_TOKEN, CONF_VERIFY_SSL: True}
NEW_TOKEN = "fake-test-token-9999"


async def start_user_flow(hass: HomeAssistant) -> ConfigFlowResult:
    """Start the user flow."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


def suggested_values(result: ConfigFlowResult) -> dict[str, Any]:
    """Return the suggested values of a form."""
    schema = result["data_schema"]
    assert schema is not None
    return {
        str(key): key.description["suggested_value"]
        for key in schema.schema
        if key.description and "suggested_value" in key.description
    }


async def test_user_flow_https(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test a successful setup over https without warnings."""
    mock_paperless(aioclient_mock, TEST_HTTPS_URL)
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**HTTPS_INPUT, CONF_URL: "https://Paperless.test:443/", CONF_API_TOKEN: f" {TEST_TOKEN} "},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == PAPERLESS_USERNAME
    assert result["data"] == {
        CONF_URL: TEST_HTTPS_URL,
        CONF_API_TOKEN: TEST_TOKEN,
        CONF_VERIFY_SSL: True,
        CONF_PAPERLESS_USER_ID: PAPERLESS_USER_ID,
    }
    assert result["options"] == DEFAULT_OPTIONS
    assert result["result"].unique_id == f"{TEST_HTTPS_URL}#{PAPERLESS_USER_ID}"


async def test_user_flow_http_and_permissions_warnings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the warnings for http:// and a superuser, in that order."""
    mock_paperless(aioclient_mock, user=ui_settings(is_superuser=True))
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**HTTPS_INPUT, CONF_URL: TEST_URL}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "insecure_http"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "permissions_warning"
    assert result["description_placeholders"] == {"username": PAPERLESS_USERNAME}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_URL] == TEST_URL


async def test_user_flow_write_permission_warning(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the warning when the Paperless user may change documents."""
    permissions = [*load_json_fixture("ui_settings")["permissions"], "change_document"]
    mock_paperless(aioclient_mock, TEST_HTTPS_URL, user=ui_settings(permissions=permissions))
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], HTTPS_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "permissions_warning"


@pytest.mark.parametrize(
    ("status", "field", "error"),
    [
        (HTTPStatus.UNAUTHORIZED, CONF_API_TOKEN, "invalid_auth"),
        (HTTPStatus.FORBIDDEN, "base", "missing_permission"),
        (HTTPStatus.NOT_ACCEPTABLE, "base", "unsupported_version"),
        (HTTPStatus.NOT_FOUND, CONF_URL, "not_paperless"),
        (HTTPStatus.BAD_REQUEST, CONF_URL, "not_paperless"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, CONF_URL, "cannot_connect"),
    ],
)
async def test_user_flow_http_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
    field: str,
    error: str,
) -> None:
    """Test the errors for failing Paperless responses, then recover."""
    mock_paperless(aioclient_mock, TEST_HTTPS_URL, status=status)
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], HTTPS_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {field: error}
    # The token is never sent back to the frontend.
    assert suggested_values(result) == {CONF_URL: TEST_HTTPS_URL, CONF_VERIFY_SSL: True}
    if error == "missing_permission":
        assert result["description_placeholders"] == {"permissions": "view_uisettings"}

    aioclient_mock.clear_requests()
    mock_paperless(aioclient_mock, TEST_HTTPS_URL)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], HTTPS_INPUT)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an unreachable server."""
    aioclient_mock.get(f"{TEST_HTTPS_URL}/api/ui_settings/", exc=ClientConnectionError())
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], HTTPS_INPUT)

    assert result["errors"] == {CONF_URL: "cannot_connect"}


async def test_user_flow_unexpected_error(hass: HomeAssistant) -> None:
    """Test an unexpected exception."""
    result = await start_user_flow(hass)

    with patch(
        "custom_components.paperless_lookup.api.PaperlessClient.async_get_user",
        side_effect=RuntimeError("boom"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], HTTPS_INPUT)

    assert result["errors"] == {"base": "unknown"}


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        ({CONF_URL: "ftp://paperless.test"}, {CONF_URL: "invalid_url"}),
        ({CONF_URL: "paperless.test"}, {CONF_URL: "invalid_url"}),
        ({CONF_API_TOKEN: "   "}, {CONF_API_TOKEN: "invalid_auth"}),
    ],
)
async def test_user_flow_invalid_input(
    hass: HomeAssistant, user_input: dict[str, Any], errors: dict[str, str]
) -> None:
    """Test invalid URLs and an empty token, without any request."""
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**HTTPS_INPUT, **user_input}
    )

    assert result["errors"] == errors


async def test_user_flow_missing_permissions(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a Paperless user without the required view permissions."""
    mock_paperless(aioclient_mock, TEST_HTTPS_URL, user=ui_settings(permissions=["view_document"]))
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], HTTPS_INPUT)

    assert result["errors"] == {"base": "missing_permission"}
    assert result["description_placeholders"] == {
        "permissions": "view_tag, view_documenttype, view_correspondent, view_customfield, "
        "view_uisettings"
    }


async def test_user_flow_superuser_needs_no_permissions(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a superuser passes the permission check (but gets the warning)."""
    mock_paperless(
        aioclient_mock, TEST_HTTPS_URL, user=ui_settings(is_superuser=True, permissions=[])
    )
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], HTTPS_INPUT)

    assert result["step_id"] == "permissions_warning"


async def test_user_flow_defaults_fail(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an error while reading the tags for the default options."""
    mock_paperless(aioclient_mock, TEST_HTTPS_URL, tags=HTTPStatus.INTERNAL_SERVER_ERROR)
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], HTTPS_INPUT)

    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_defaults_without_matches(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the default options when Paperless has no HA tag, manual type or model field."""
    empty: dict[str, Any] = {"count": 0, "next": None, "results": []}
    mock_paperless(
        aioclient_mock, TEST_HTTPS_URL, tags=empty, document_types=empty, custom_fields=empty
    )
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], HTTPS_INPUT)
    await hass.async_block_till_done()

    assert result["options"] == {
        **DEFAULT_OPTIONS,
        "access_tag": None,
        "categories": {},
        "device_categories": [],
        "model_field": None,
    }


async def test_single_instance(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test that a second entry is refused (single_config_entry)."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


# ---- Reauth ---------------------------------------------------------------------------------


async def test_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> None:
    """Test replacing a rejected token (after a failed attempt)."""
    mock_config_entry.add_to_hass(hass)
    mock_paperless(aioclient_mock, status=HTTPStatus.UNAUTHORIZED)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: NEW_TOKEN}
    )
    assert result["errors"] == {CONF_API_TOKEN: "invalid_auth"}

    aioclient_mock.clear_requests()
    mock_paperless(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: NEW_TOKEN}
    )
    # The http:// warning applies to reauth too.
    assert result["step_id"] == "insecure_http"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_TOKEN] == NEW_TOKEN
    assert mock_config_entry.data[CONF_URL] == TEST_URL
    headers = aioclient_mock.mock_calls[0][3]
    assert headers["Authorization"] == f"Token {NEW_TOKEN}"


async def test_reauth_wrong_account(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a token of another Paperless user is refused."""
    mock_config_entry.add_to_hass(hass)
    other = ui_settings()
    other["user"]["id"] = 99
    mock_paperless(aioclient_mock, user=other)
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: NEW_TOKEN}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_config_entry.data[CONF_API_TOKEN] == TEST_TOKEN


# ---- Reconfigure ----------------------------------------------------------------------------


async def test_reconfigure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> None:
    """Test moving to an https URL (after a failed attempt)."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    assert suggested_values(result) == {CONF_URL: TEST_URL, CONF_VERIFY_SSL: True}

    aioclient_mock.get(f"{TEST_HTTPS_URL}/api/ui_settings/", exc=ClientConnectionError())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**HTTPS_INPUT, CONF_API_TOKEN: NEW_TOKEN}
    )
    assert result["errors"] == {CONF_URL: "cannot_connect"}
    assert suggested_values(result) == {CONF_URL: TEST_HTTPS_URL, CONF_VERIFY_SSL: True}

    aioclient_mock.clear_requests()
    mock_paperless(aioclient_mock, TEST_HTTPS_URL)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**HTTPS_INPUT, CONF_API_TOKEN: NEW_TOKEN, CONF_VERIFY_SSL: False}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_URL: TEST_HTTPS_URL,
        CONF_API_TOKEN: NEW_TOKEN,
        CONF_VERIFY_SSL: False,
        CONF_PAPERLESS_USER_ID: PAPERLESS_USER_ID,
    }
    assert mock_config_entry.unique_id == f"{TEST_HTTPS_URL}#{PAPERLESS_USER_ID}"
    assert mock_config_entry.options == DEFAULT_OPTIONS


async def test_reconfigure_wrong_account(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> None:
    """Test that reconfigure refuses another Paperless user."""
    mock_config_entry.add_to_hass(hass)
    other = ui_settings()
    other["user"]["id"] = 99
    mock_paperless(aioclient_mock, TEST_HTTPS_URL, user=other)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], HTTPS_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_config_entry.data[CONF_URL] == TEST_URL
