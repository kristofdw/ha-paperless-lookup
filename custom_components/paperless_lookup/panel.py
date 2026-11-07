"""Serve the frontend bundle, register the card for every dashboard and the sidebar panel."""

import hashlib
from pathlib import Path
from typing import Final

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, NAME

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
    """Add the sidebar panel (every user sees it; access is checked in the backend)."""
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
