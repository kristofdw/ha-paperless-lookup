"""Tests for serving the frontend bundle, the card resource and the sidebar panel."""

from http import HTTPStatus

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, DATA_PANELS
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.paperless_lookup.panel import (
    FRONTEND_DIR,
    FRONTEND_FILE,
    PANEL_COMPONENT,
    PANEL_URL_PATH,
    STATIC_URL,
)

from .conftest import mock_paperless


async def test_panel_and_bundle(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the panel, the card resource and the static bundle; the panel goes on unload."""
    mock_paperless(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    panel = hass.data[DATA_PANELS][PANEL_URL_PATH]
    assert panel.component_name == "custom"
    assert panel.require_admin is False
    assert panel.sidebar_title == "Paperless Lookup"
    assert panel.config is not None
    custom = panel.config["_panel_custom"]
    assert custom["name"] == PANEL_COMPONENT
    module_url = custom["module_url"]
    assert module_url.startswith(f"{STATIC_URL}/{FRONTEND_FILE}?v=")
    # The card is loaded on every page, with the same versioned URL.
    assert module_url in hass.data[DATA_EXTRA_MODULE_URL].urls

    client = await hass_client_no_auth()
    response = await client.get(module_url)
    assert response.status == HTTPStatus.OK
    assert await response.read() == (FRONTEND_DIR / FRONTEND_FILE).read_bytes()
    assert "javascript" in response.headers["Content-Type"]

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert PANEL_URL_PATH not in hass.data[DATA_PANELS]

    # Reloading registers the panel again.
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert PANEL_URL_PATH in hass.data[DATA_PANELS]
