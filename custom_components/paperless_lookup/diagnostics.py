"""Diagnostics for Paperless Lookup.

Never contains the token, the URL, user names or document titles/content. Home Assistant user
ids are replaced by counts; Paperless object ids (tags, types, fields) are kept.
"""

from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_API_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant

from . import PaperlessLookupConfigEntry
from .api import API_VERSION
from .const import CONF_CATEGORIES, CONF_PAPERLESS_USER_ID
from .helpers import has_write_access, missing_permissions

TO_REDACT = {CONF_API_TOKEN, CONF_URL, CONF_PAPERLESS_USER_ID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PaperlessLookupConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    options = dict(entry.options)
    categories = options.get(CONF_CATEGORIES, {})
    options[CONF_CATEGORIES] = {type_id: len(users) for type_id, users in categories.items()}
    data = entry.runtime_data
    return {
        "entry": {
            "title": REDACTED,
            "unique_id": REDACTED,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": options,
        },
        "paperless": {
            "server_version": data.client.server_version,
            "api_version": API_VERSION,
            "user": {
                "is_staff": data.user.is_staff,
                "is_superuser": data.user.is_superuser,
                "has_write_access": has_write_access(data.user),
                "missing_permissions": missing_permissions(data.user),
                "permissions": sorted(data.user.permissions),
            },
        },
        "index": data.coordinator.diagnostics(),
    }
