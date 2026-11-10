"""Describe Paperless Lookup events in the logbook."""

from collections.abc import Callable
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN
from .read_log import EVENT_DOCUMENT_OPENED

type Describer = Callable[[Event], dict[str, str]]


@callback
def async_describe_events(
    hass: HomeAssistant, async_describe_event: Callable[[str, str, Describer], None]
) -> None:
    """Describe the document read events."""

    @callback
    def describe_document_opened(event: Event) -> dict[str, str]:
        data: dict[str, Any] = dict(event.data)
        verb = "downloaded" if data.get("kind") == "download" else "opened"
        category = f" ({data['category']})" if data.get("category") else ""
        return {
            "name": data.get("user_name") or "Unknown user",
            "message": f"{verb} Paperless document {data.get('document_id')}{category}",
        }

    async_describe_event(DOMAIN, EVENT_DOCUMENT_OPENED, describe_document_opened)
