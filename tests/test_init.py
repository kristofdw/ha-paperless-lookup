"""Tests for setting up and unloading Paperless Lookup."""

from http import HTTPStatus

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.paperless_lookup import PaperlessLookupData
from custom_components.paperless_lookup.const import DOMAIN

from .conftest import (
    DEFAULT_OPTIONS,
    MOCK_CONFIG,
    PAPERLESS_USERNAME,
    TEST_URL,
    mock_paperless,
    ui_settings,
)


async def test_setup_and_unload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the entry sets up, gets runtime data and unloads."""
    mock_paperless(aioclient_mock)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    data = mock_config_entry.runtime_data
    assert isinstance(data, PaperlessLookupData)
    assert data.user.username == PAPERLESS_USERNAME
    assert data.client.base_url == TEST_URL
    assert data.client.server_version == "3.3.4"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("status", "state", "reauth"),
    [
        (HTTPStatus.UNAUTHORIZED, ConfigEntryState.SETUP_ERROR, True),
        (HTTPStatus.FORBIDDEN, ConfigEntryState.SETUP_ERROR, False),
        (HTTPStatus.NOT_ACCEPTABLE, ConfigEntryState.SETUP_ERROR, False),
        (HTTPStatus.INTERNAL_SERVER_ERROR, ConfigEntryState.SETUP_RETRY, False),
        (HTTPStatus.NOT_FOUND, ConfigEntryState.SETUP_RETRY, False),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    status: HTTPStatus,
    state: ConfigEntryState,
    reauth: bool,
) -> None:
    """Test the setup result for failing Paperless responses."""
    mock_paperless(aioclient_mock, status=status)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is state
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert bool(flows) is reauth
    if reauth:
        assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_setup_wrong_account(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a token of another Paperless user starts a reauth."""
    other = ui_settings()
    other["user"]["id"] = 99
    mock_paperless(aioclient_mock, user=other)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_setup_missing_permissions(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a Paperless user that lost a required permission."""
    mock_paperless(aioclient_mock, user=ui_settings(permissions=["view_document"]))
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.reason is not None
    assert "view_customfield" in mock_config_entry.reason


@pytest.mark.parametrize(
    ("status", "user", "key", "permission"),
    [
        (HTTPStatus.NOT_ACCEPTABLE, None, "unsupported_version", None),
        (HTTPStatus.FORBIDDEN, None, "missing_permission", "view_uisettings"),
        (HTTPStatus.OK, ["view_document"], "missing_permission", "view_customfield"),
    ],
)
async def test_setup_problem_raises_issue_until_solved(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    status: HTTPStatus,
    user: list[str] | None,
    key: str,
    permission: str | None,
) -> None:
    """Test that a problem the user can fix gives a repair issue, gone after a good setup."""
    registry = ir.async_get(hass)
    issue_id = f"{key}_{mock_config_entry.entry_id}"
    mock_paperless(
        aioclient_mock,
        status=status,
        user=ui_settings(permissions=user) if user else None,
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    issue = registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_key == key
    if permission:
        assert issue.translation_placeholders is not None
        assert permission in issue.translation_placeholders["permissions"]

    aioclient_mock.clear_requests()
    mock_paperless(aioclient_mock)
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get_issue(DOMAIN, issue_id) is None
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_connection_error_raises_no_issue(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> None:
    """Test that an outage, which fixes itself, is not a repair issue."""
    mock_paperless(aioclient_mock, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not ir.async_get(hass).issues


async def test_migrate_removes_refresh_interval(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the former refresh interval option disappears from an older entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        minor_version=1,
        data=dict(MOCK_CONFIG),
        options={**DEFAULT_OPTIONS, "refresh_interval": 15},
    )
    mock_paperless(aioclient_mock)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.options == DEFAULT_OPTIONS


async def test_migrate_keeps_newer_minor_version(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that an entry of a newer minor version is not changed."""
    entry = MockConfigEntry(
        domain=DOMAIN, minor_version=3, data=dict(MOCK_CONFIG), options=dict(DEFAULT_OPTIONS)
    )
    mock_paperless(aioclient_mock)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 3
    assert entry.state is ConfigEntryState.LOADED


async def test_migrate_refuses_newer_version(hass: HomeAssistant) -> None:
    """Test that an entry of a newer major version is left alone."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=dict(MOCK_CONFIG))
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
