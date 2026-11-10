"""Tests for serving the frontend bundle, the card resource and the sidebar panel."""

from http import HTTPStatus
from typing import Any

from homeassistant.auth import EVENT_USER_ADDED
from homeassistant.auth.models import User
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, DATA_PANELS
from homeassistant.components.frontend.storage import async_user_store
from homeassistant.core import HomeAssistant
from pytest_homeassistant.common import MockConfigEntry, MockUser
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator

from custom_components.paperless_lookup import async_remove_entry
from custom_components.paperless_lookup.const import CONF_PANEL_USERS
from custom_components.paperless_lookup.panel import (
    FRONTEND_DIR,
    FRONTEND_FILE,
    PANEL_COMPONENT,
    PANEL_URL_PATH,
    STATIC_URL,
)

from .conftest import mock_paperless
from .security import async_setup_entry, async_setup_users, async_user


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


async def sidebar(hass: HomeAssistant, user: User) -> dict[str, Any]:
    """Return the sidebar settings Home Assistant keeps for a user."""
    data: dict[str, Any] = (await async_user_store(hass, user.id)).data.get("sidebar") or {}
    return data


async def test_panel_visible_for_chosen_users_only(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    hass_admin_user: MockUser,
) -> None:
    """Test hiding the sidebar item per user, keeping the user's own sidebar settings."""
    users = await async_setup_users(hass, hass_admin_user)
    guest_store = await async_user_store(hass, users.guest.id)
    await guest_store.async_set_item("sidebar", {"panelOrder": ["map"], "hiddenPanels": ["energy"]})
    allowed = [users.admin.id, users.reader.id]

    await async_setup_entry(
        hass, aioclient_mock, mock_config_entry, users, **{CONF_PANEL_USERS: allowed}
    )

    assert await sidebar(hass, users.admin) == {}
    assert await sidebar(hass, users.reader) == {}
    assert await sidebar(hass, users.guest) == {
        "panelOrder": ["map"],
        "hiddenPanels": ["energy", PANEL_URL_PATH],
    }
    assert (await sidebar(hass, users.nobody))["hiddenPanels"] == [PANEL_URL_PATH]
    store = mock_config_entry.runtime_data.store
    assert set(store.data["panel_hidden_users"]) >= {users.guest.id, users.nobody.id}

    # A new user is covered too.
    new_user = await async_user(hass, "New")
    hass.bus.async_fire(EVENT_USER_ADDED, {"user_id": new_user.id})
    await hass.async_block_till_done()
    assert (await sidebar(hass, new_user))["hiddenPanels"] == [PANEL_URL_PATH]

    # Reloading changes nothing.
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (await sidebar(hass, users.guest))["hiddenPanels"] == ["energy", PANEL_URL_PATH]


async def test_panel_shown_again(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    hass_admin_user: MockUser,
) -> None:
    """Test showing the item again, except where a user hid it personally."""
    users = await async_setup_users(hass, hass_admin_user)
    reader_store = await async_user_store(hass, users.reader.id)
    await reader_store.async_set_item("sidebar", {"hiddenPanels": [PANEL_URL_PATH]})
    await async_setup_entry(
        hass, aioclient_mock, mock_config_entry, users, **{CONF_PANEL_USERS: [users.admin.id]}
    )
    assert (await sidebar(hass, users.guest))["hiddenPanels"] == [PANEL_URL_PATH]
    # This user brought the item back personally in the meantime.
    nobody_store = await async_user_store(hass, users.nobody.id)
    await nobody_store.async_set_item("sidebar", {"hiddenPanels": []})
    hass.config_entries.async_update_entry(
        mock_config_entry, options={**mock_config_entry.options, CONF_PANEL_USERS: []}
    )
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (await sidebar(hass, users.guest))["hiddenPanels"] == []
    assert (await sidebar(hass, users.nobody))["hiddenPanels"] == []
    # The reader hid it personally, before the integration ever did: that stays.
    assert (await sidebar(hass, users.reader))["hiddenPanels"] == [PANEL_URL_PATH]
    assert mock_config_entry.runtime_data.store.data["panel_hidden_users"] == []


async def test_personal_choice_is_kept(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    hass_admin_user: MockUser,
) -> None:
    """Test that without a choice nothing is touched, also not a personally hidden item."""
    users = await async_setup_users(hass, hass_admin_user)
    reader_store = await async_user_store(hass, users.reader.id)
    await reader_store.async_set_item("sidebar", {"hiddenPanels": [PANEL_URL_PATH]})

    await async_setup_entry(hass, aioclient_mock, mock_config_entry, users)

    assert (await sidebar(hass, users.reader))["hiddenPanels"] == [PANEL_URL_PATH]
    assert await sidebar(hass, users.guest) == {}


async def test_remove_entry_restores_sidebar(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    hass_admin_user: MockUser,
) -> None:
    """Test that removing the integration shows the item again where it was hidden."""
    users = await async_setup_users(hass, hass_admin_user)
    await async_setup_entry(
        hass, aioclient_mock, mock_config_entry, users, **{CONF_PANEL_USERS: [users.admin.id]}
    )
    assert (await sidebar(hass, users.guest))["hiddenPanels"] == [PANEL_URL_PATH]

    await async_remove_entry(hass, mock_config_entry)

    assert (await sidebar(hass, users.guest))["hiddenPanels"] == []
