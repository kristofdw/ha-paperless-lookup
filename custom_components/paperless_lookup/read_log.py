"""Log document reads in the Home Assistant logbook.

Opt-in per category and per Home Assistant user (option `read_log`). Only previews and downloads
are logged, not thumbnails. The event holds ids, the category name and the user, never a document
title or content: the logbook is stored in the recorder database.
"""

from time import monotonic
from typing import TYPE_CHECKING, Final

from homeassistant.auth.models import User
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .api import FileKind, PaperlessDocument
from .const import CONF_READ_LOG, DOMAIN, NAME

if TYPE_CHECKING:
    from . import PaperlessLookupConfigEntry

EVENT_DOCUMENT_OPENED: Final = f"{DOMAIN}_document_opened"
LOGGED_KINDS: Final = frozenset({FileKind.PREVIEW, FileKind.DOWNLOAD})
# A browser that opens the same file again within this time is not logged twice.
REPEAT_SECONDS: Final = 60.0


@callback
def async_service_device(hass: HomeAssistant, entry: PaperlessLookupConfigEntry) -> str:
    """Create or return the service device that the logbook entries belong to."""
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        entry_type=dr.DeviceEntryType.SERVICE,
        name=NAME,
        manufacturer="Paperless-ngx",
    )
    return device.id


@callback
def async_log_read(
    hass: HomeAssistant,
    entry: PaperlessLookupConfigEntry,
    user: User,
    document: PaperlessDocument,
    kind: FileKind,
) -> bool:
    """Fire a logbook event when this user's reads in this category are followed.

    Only ids, the category name and the user go into the event, never the title.
    Returns whether an event was fired.
    """
    document_id, document_type = document.id, document.document_type
    followed = entry.options.get(CONF_READ_LOG, {}).get(str(document_type), [])
    # A document without a type is never visible, so it is never logged either.
    if kind not in LOGGED_KINDS or document_type is None or user.id not in followed:
        return False
    data = entry.runtime_data
    now = monotonic()
    seen = data.read_log_seen
    for key in [key for key, when in seen.items() if now - when >= REPEAT_SECONDS]:
        del seen[key]
    key = (user.id, document_id, kind)
    if key in seen:
        return False
    seen[key] = now
    hass.bus.async_fire(
        EVENT_DOCUMENT_OPENED,
        {
            "device_id": data.device_id,
            "document_id": document_id,
            "document_type": document_type,
            "category": data.coordinator.data.document_types.get(document_type),
            "kind": str(kind),
            "user_id": user.id,
            "user_name": user.name,
        },
        # No user in the context: the logbook would then add "by <user>" next to the name, and
        # only for users linked to a person. The name is part of the entry instead.
    )
    return True
