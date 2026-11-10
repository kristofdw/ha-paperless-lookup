"""Describe Paperless Lookup events in the logbook."""

from collections.abc import Callable
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.translation import async_get_cached_translations

from .const import DOMAIN
from .read_log import EVENT_DOCUMENT_OPENED

type Describer = Callable[[Event], dict[str, str]]

# Used until the translations are loaded; the same as the "common" strings in strings.json.
FALLBACK_TEXTS: dict[str, str] = {
    "document_opened": "opened Paperless document {document_id}",
    "document_downloaded": "downloaded Paperless document {document_id}",
    "unknown_user": "Unknown user",
}


def _text(hass: HomeAssistant, key: str) -> str:
    """Return a logbook text in the language of Home Assistant (English when not loaded)."""
    strings = async_get_cached_translations(hass, hass.config.language, "common", DOMAIN)
    return strings.get(f"component.{DOMAIN}.common.{key}", FALLBACK_TEXTS[key])


@callback
def async_describe_events(
    hass: HomeAssistant, async_describe_event: Callable[[str, str, Describer], None]
) -> None:
    """Describe the document read events."""

    @callback
    def describe_document_opened(event: Event) -> dict[str, str]:
        data: dict[str, Any] = dict(event.data)
        key = "document_downloaded" if data.get("kind") == "download" else "document_opened"
        message = _text(hass, key).replace("{document_id}", str(data.get("document_id")))
        if data.get("category"):
            message += f" ({data['category']})"
        return {"name": data.get("user_name") or _text(hass, "unknown_user"), "message": message}

    async_describe_event(DOMAIN, EVENT_DOCUMENT_OPENED, describe_document_opened)
