"""Tests for setting up and unloading Paperless Lookup."""

from http import HTTPStatus

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.paperless_lookup import PaperlessLookupData
from custom_components.paperless_lookup.const import DOMAIN

from .conftest import PAPERLESS_USERNAME, TEST_URL, mock_paperless, ui_settings


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
