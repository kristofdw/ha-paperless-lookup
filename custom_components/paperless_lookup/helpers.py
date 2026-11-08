"""Helpers shared by the setup and the config flow."""

from collections.abc import Mapping
from typing import Any

from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from yarl import URL

from .api import PaperlessClient, PaperlessUser
from .const import (
    CONF_ACCESS_TAG,
    CONF_ADMINS_ALWAYS,
    CONF_CATEGORIES,
    CONF_DEVICE_CATEGORIES,
    CONF_MODEL_FIELD,
    CONF_PANEL_USERS,
    CONF_REFRESH_INTERVAL,
    CONF_ZIGBEE2MQTT_FALLBACK,
    DEFAULT_ACCESS_TAG_NAME,
    DEFAULT_ADMINS_ALWAYS,
    DEFAULT_DEVICE_CATEGORY_NAMES,
    DEFAULT_MODEL_FIELD_NAME,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_ZIGBEE2MQTT_FALLBACK,
    REQUIRED_PERMISSIONS,
    WRITE_PERMISSION_PREFIXES,
)

_DEFAULT_PORTS = {"http": 80, "https": 443}


def create_client(hass: HomeAssistant, data: Mapping[str, Any]) -> PaperlessClient:
    """Return a Paperless client for config entry data (or flow input).

    Raises:
        ValueError: The URL or token is invalid.
    """
    session = async_get_clientsession(hass, verify_ssl=bool(data.get(CONF_VERIFY_SSL, True)))
    return PaperlessClient(session, str(data[CONF_URL]), str(data[CONF_API_TOKEN]))


def normalize_url(url: str) -> str:
    """Return a canonical form of a Paperless base URL (for the unique ID)."""
    parsed = URL(url.strip())
    scheme = parsed.scheme.lower()
    host = (parsed.host or "").lower()
    port = "" if parsed.port in (None, _DEFAULT_PORTS.get(scheme)) else f":{parsed.port}"
    return f"{scheme}://{host}{port}{parsed.path.rstrip('/')}"


def build_unique_id(url: str, user_id: int) -> str:
    """Return the unique ID of a config entry: Paperless server plus Paperless user."""
    return f"{normalize_url(url)}#{user_id}"


def missing_permissions(user: PaperlessUser) -> list[str]:
    """Return the required Paperless permissions the user lacks."""
    if user.is_superuser:
        return []
    return [perm for perm in REQUIRED_PERMISSIONS if perm not in user.permissions]


def has_write_access(user: PaperlessUser) -> bool:
    """Return whether the Paperless user can change data or sees everything."""
    return user.is_superuser or any(
        perm.startswith(WRITE_PERMISSION_PREFIXES) for perm in user.permissions
    )


async def async_default_options(client: PaperlessClient) -> dict[str, Any]:
    """Return the initial options, based on the names found in Paperless.

    Every document type becomes a category without extra users, so only administrators see
    documents until access is granted in the options.
    """
    tags = await client.async_get_tags()
    document_types = await client.async_get_document_types()
    custom_fields = await client.async_get_custom_fields()
    access_tag = next(
        (tag.id for tag in tags if tag.name.casefold() == DEFAULT_ACCESS_TAG_NAME.casefold()),
        None,
    )
    model_field = next(
        (
            field.id
            for field in custom_fields
            if field.name.casefold() == DEFAULT_MODEL_FIELD_NAME.casefold()
            and field.data_type == "string"
        ),
        None,
    )
    return {
        CONF_ACCESS_TAG: access_tag,
        CONF_CATEGORIES: {str(doc_type.id): [] for doc_type in document_types},
        CONF_ADMINS_ALWAYS: DEFAULT_ADMINS_ALWAYS,
        CONF_PANEL_USERS: [],
        CONF_DEVICE_CATEGORIES: [
            doc_type.id
            for doc_type in document_types
            if doc_type.name.casefold() in DEFAULT_DEVICE_CATEGORY_NAMES
        ],
        CONF_MODEL_FIELD: model_field,
        CONF_ZIGBEE2MQTT_FALLBACK: DEFAULT_ZIGBEE2MQTT_FALLBACK,
        CONF_REFRESH_INTERVAL: DEFAULT_REFRESH_INTERVAL,
    }
