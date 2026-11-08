"""Serve the frontend bundle, register the card for every dashboard and the sidebar panel."""

from collections.abc import Collection
import hashlib
from pathlib import Path
from typing import Final

from homeassistant.components import frontend, panel_custom
from homeassistant.components.frontend.storage import async_user_store
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, NAME
from .store import LinkStore

FRONTEND_DIR: Final = Path(__file__).parent / "frontend"
FRONTEND_FILE: Final = "paperless-lookup.js"
STATIC_URL: Final = f"/{DOMAIN}_static"
PANEL_URL_PATH: Final = "paperless-lookup"
PANEL_COMPONENT: Final = "paperless-lookup-panel"
PANEL_ICON: Final = "mdi:file-search-outline"


def _bundle_hash() -> str:
    """Return a short hash of the bundle, for cache busting after updates."""
    return hashlib.sha256((FRONTEND_DIR / FRONTEND_FILE).read_bytes()).hexdigest()[:12]


async def async_register_frontend(hass: HomeAssistant) -> str:
    """Serve the bundle and load it on every page (the card works on any dashboard).

    Returns the versioned module URL.
    """
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=True)]
    )
    version = await hass.async_add_executor_job(_bundle_hash)
    url = f"{STATIC_URL}/{FRONTEND_FILE}?v={version}"
    frontend.add_extra_js_url(hass, url)
    return url


async def async_register_panel(hass: HomeAssistant, module_url: str) -> None:
    """Add the sidebar panel (documents are protected in the backend, per category)."""
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT,
        module_url=module_url,
        sidebar_title=NAME,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        config={},
    )


def async_remove_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar panel."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH)


async def async_sync_panel_visibility(
    hass: HomeAssistant, store: LinkStore, panel_users: Collection[str]
) -> None:
    """Show the sidebar item only to ``panel_users`` (empty: to everyone).

    Home Assistant has no per-user panels, but it does keep each user's hidden sidebar items on
    the server, and the sidebar follows them live. This only concerns the sidebar item: what a
    user may read is decided per category in ``access.py``. Only items hidden here are shown
    again, so an item a user hid personally stays hidden.
    """
    users = await hass.auth.async_get_users()
    tracked = set(store.data["panel_hidden_users"]) & {user.id for user in users}
    for user in users:
        if user.system_generated or not user.is_active:
            continue
        user_store = await async_user_store(hass, user.id)
        sidebar = dict(user_store.data.get("sidebar") or {})
        hidden = list(sidebar.get("hiddenPanels") or [])
        if panel_users and user.id not in panel_users:
            if PANEL_URL_PATH not in hidden:
                tracked.add(user.id)
                sidebar["hiddenPanels"] = [*hidden, PANEL_URL_PATH]
                await user_store.async_set_item("sidebar", sidebar)
        elif user.id in tracked:
            tracked.discard(user.id)
            if PANEL_URL_PATH in hidden:
                sidebar["hiddenPanels"] = [item for item in hidden if item != PANEL_URL_PATH]
                await user_store.async_set_item("sidebar", sidebar)
    await store.async_set_panel_hidden_users(tracked)
