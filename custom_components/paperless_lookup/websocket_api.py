"""Websocket API for the panel and the card.

Every command resolves the user's access through ``access.py`` first. Documents a user may not
see are reported as ``not_found``; device administration (link, unlink, ignore, devices without
manual) is for administrators only.
"""

from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from functools import wraps
import html
import re
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components import websocket_api
from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
import probatio

from .access import (
    DocumentNotFoundError,
    NotLoadedError,
    UserAccess,
    async_get_entry,
    get_document,
    user_access,
    visible_documents,
)
from .api import FileKind, PaperlessError
from .const import CONF_ZIGBEE2MQTT_FALLBACK, DOMAIN
from .coordinator import DocumentIndex, IndexedDocument, async_get_device, device_info
from .matching import DeviceInfo, zigbee2mqtt_url

if TYPE_CHECKING:
    from . import PaperlessLookupConfigEntry

ERR_NOT_LOADED: Final = "not_loaded"
ERR_CANNOT_CONNECT: Final = "cannot_connect"
SIGNED_PATH_EXPIRATION: Final = timedelta(seconds=60)
MAX_QUERY_LENGTH: Final = 200
MAX_SIGN_DOCUMENTS: Final = 100
DOCUMENT_PATH: Final = "/api/paperless_lookup/document/{document_id}/{kind}"

_HIGHLIGHT = re.compile(r"<b>(.*?)</b>", re.DOTALL)
_TAG = re.compile(r"<[^>]*>")

type Handler = Callable[
    [
        HomeAssistant,
        websocket_api.ActiveConnection,
        dict[str, Any],
        "PaperlessLookupConfigEntry",
        UserAccess,
    ],
    Awaitable[None],
]

_ID_LIST = probatio.All([probatio.Coerce(int)], probatio.Length(max=1000))


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the websocket commands."""
    for command in (
        ws_access,
        ws_filters,
        ws_search,
        ws_device_documents,
        ws_area_documents,
        ws_devices_without_manual,
        ws_link,
        ws_unlink,
        ws_ignore,
        ws_sign_documents,
    ):
        websocket_api.async_register_command(hass, command)


def _with_access(func: Handler) -> websocket_api.AsyncWebSocketCommandHandler:
    """Resolve the entry and the user's access, and turn errors into websocket errors."""

    @wraps(func)
    async def wrapper(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
    ) -> None:
        try:
            entry = async_get_entry(hass)
            await func(hass, connection, msg, entry, user_access(entry, connection.user))
        except NotLoadedError:
            connection.send_error(msg["id"], ERR_NOT_LOADED, "Paperless Lookup is not loaded")
        except DocumentNotFoundError:
            connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Not found")
        except PaperlessError:
            connection.send_error(
                msg["id"], ERR_CANNOT_CONNECT, "Failed to communicate with Paperless"
            )

    return wrapper


def _named(ids: set[int] | frozenset[int], names: dict[int, str]) -> list[dict[str, Any]]:
    """Return ``[{"id", "name"}]`` sorted by name, for ids that have a name."""
    items = [{"id": item, "name": names[item]} for item in ids if item in names]
    return sorted(items, key=lambda item: (str(item["name"]).casefold(), item["id"]))


def _document_json(doc: IndexedDocument, index: DocumentIndex) -> dict[str, Any]:
    """Return the metadata of a document for the frontend (never content)."""
    return {
        "id": doc.id,
        "title": doc.title,
        "category": doc.document_type,
        "category_name": index.document_types.get(doc.document_type),
        "correspondent": doc.correspondent,
        "correspondent_name": (
            index.correspondents.get(doc.correspondent) if doc.correspondent is not None else None
        ),
        "created": doc.created.isoformat() if doc.created else None,
        "mime_type": doc.mime_type,
        "models": list(doc.models),
    }


def highlight_segments(highlights: str | None) -> list[dict[str, Any]]:
    """Split a Paperless highlight snippet into plain-text segments.

    Paperless marks matches with ``<b>``. The result contains text only (no markup), so the
    frontend never has to render HTML from Paperless.
    """
    if not highlights:
        return []
    segments: list[dict[str, Any]] = []
    position = 0
    for match in _HIGHLIGHT.finditer(highlights):
        if match.start() > position:
            segments.append({"text": highlights[position : match.start()], "match": False})
        segments.append({"text": match.group(1), "match": True})
        position = match.end()
    if position < len(highlights):
        segments.append({"text": highlights[position:], "match": False})
    result = []
    for segment in segments:
        text = html.unescape(_TAG.sub("", segment["text"]))
        if text:
            result.append({"text": text, "match": segment["match"]})
    return result


def _device_json(
    entry: PaperlessLookupConfigEntry, access: UserAccess, device: DeviceInfo
) -> dict[str, Any]:
    """Return a device with the documents the user may see."""
    coordinator = entry.runtime_data.coordinator
    documents = visible_documents(access, coordinator.device_documents(device))
    has_manual = any(doc.document_type in coordinator.device_categories for doc in documents)
    fallback = entry.options.get(CONF_ZIGBEE2MQTT_FALLBACK, False) and not has_manual
    return {
        "device_id": device.id,
        "name": device.name,
        "documents": [_document_json(doc, coordinator.data) for doc in documents],
        "zigbee2mqtt_url": zigbee2mqtt_url(device) if fallback else None,
    }


def _get_device(hass: HomeAssistant, device_id: str) -> DeviceInfo:
    """Return a device or raise not found."""
    if (device := async_get_device(hass, device_id)) is None:
        raise DocumentNotFoundError
    return device


# ---- Commands for every user ----------------------------------------------------------------


@websocket_api.websocket_command({probatio.Required("type"): f"{DOMAIN}/access"})
@websocket_api.async_response
@_with_access
async def ws_access(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: PaperlessLookupConfigEntry,
    access: UserAccess,
) -> None:
    """Return what the user may see."""
    coordinator = entry.runtime_data.coordinator
    names = coordinator.data.document_types
    connection.send_result(
        msg["id"],
        {
            "allowed": access.allowed,
            "is_admin": access.is_admin,
            "categories": _named(access.categories, names),
            "device_categories": _named(coordinator.device_categories & access.categories, names),
            "zigbee2mqtt_fallback": bool(entry.options.get(CONF_ZIGBEE2MQTT_FALLBACK, False)),
        },
    )


@websocket_api.websocket_command({probatio.Required("type"): f"{DOMAIN}/filters"})
@websocket_api.async_response
@_with_access
async def ws_filters(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: PaperlessLookupConfigEntry,
    access: UserAccess,
) -> None:
    """Return the search filters: only categories and stores of visible documents."""
    index = entry.runtime_data.coordinator.data
    documents = [doc for doc in index.documents.values() if access.can_view(doc.document_type)]
    dates = [doc.created for doc in documents if doc.created]
    connection.send_result(
        msg["id"],
        {
            "categories": _named({doc.document_type for doc in documents}, index.document_types),
            "correspondents": _named(
                {doc.correspondent for doc in documents if doc.correspondent is not None},
                index.correspondents,
            ),
            "date_min": min(dates).isoformat() if dates else None,
            "date_max": max(dates).isoformat() if dates else None,
        },
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/search",
        probatio.Optional("query", default=""): probatio.All(
            str, probatio.Length(max=MAX_QUERY_LENGTH)
        ),
        probatio.Optional("categories"): _ID_LIST,
        probatio.Optional("correspondents"): _ID_LIST,
        probatio.Optional("date_from"): cv.date,
        probatio.Optional("date_to"): cv.date,
        probatio.Optional("page", default=1): probatio.All(int, probatio.Range(min=1, max=1000)),
        probatio.Optional("page_size", default=25): probatio.All(
            int, probatio.Range(min=1, max=100)
        ),
    }
)
@websocket_api.async_response
@_with_access
async def ws_search(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: PaperlessLookupConfigEntry,
    access: UserAccess,
) -> None:
    """Search the documents the user may see (live in Paperless), newest first."""
    coordinator = entry.runtime_data.coordinator
    categories = access.categories
    if "categories" in msg:
        categories = categories & set(msg["categories"])
    if coordinator.access_tag is None or not categories:
        connection.send_result(msg["id"], {"count": 0, "results": []})
        return
    created_from: date | None = msg.get("date_from")
    created_to: date | None = msg.get("date_to")
    result = await coordinator.client.async_search(
        msg["query"],
        access_tag_id=coordinator.access_tag,
        document_type_ids=categories,
        correspondent_ids=msg.get("correspondents"),
        created_from=created_from,
        created_to=created_to,
        page=msg["page"],
        page_size=msg["page_size"],
    )
    index = coordinator.data
    results = []
    for hit in result.hits:
        doc = hit.document
        # Third check: the client already dropped other types and documents without the tag.
        if (
            doc.document_type is None
            or not access.can_view(doc.document_type)
            or coordinator.access_tag not in doc.tags
        ):  # pragma: no cover - unreachable while the client checks the scope
            continue
        item = IndexedDocument(
            id=doc.id,
            title=doc.title,
            document_type=doc.document_type,
            correspondent=doc.correspondent,
            created=doc.created,
            mime_type=doc.mime_type,
        )
        results.append(
            {**_document_json(item, index), "highlights": highlight_segments(hit.highlights)}
        )
    connection.send_result(msg["id"], {"count": result.count, "results": results})


@websocket_api.websocket_command(
    {probatio.Required("type"): f"{DOMAIN}/device_documents", probatio.Required("device_id"): str}
)
@websocket_api.async_response
@_with_access
async def ws_device_documents(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: PaperlessLookupConfigEntry,
    access: UserAccess,
) -> None:
    """Return the documents of a device that the user may see."""
    device = _get_device(hass, msg["device_id"])
    connection.send_result(msg["id"], _device_json(entry, access, device))


@websocket_api.websocket_command(
    {probatio.Required("type"): f"{DOMAIN}/area_documents", probatio.Required("area_id"): str}
)
@websocket_api.async_response
@_with_access
async def ws_area_documents(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: PaperlessLookupConfigEntry,
    access: UserAccess,
) -> None:
    """Return the devices of an area that have documents the user may see."""
    registry = dr.async_get(hass)
    devices = [
        _device_json(entry, access, device_info(device))
        for device in dr.async_entries_for_area(registry, msg["area_id"])
        if isinstance(device, dr.DeviceEntry) and device.disabled_by is None
    ]
    connection.send_result(
        msg["id"],
        {
            "devices": sorted(
                (device for device in devices if device["documents"]),
                key=lambda device: (str(device["name"]).casefold(), device["device_id"]),
            )
        },
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/sign_documents",
        probatio.Required("document_ids"): probatio.All(
            [probatio.Coerce(int)], probatio.Length(min=1, max=MAX_SIGN_DOCUMENTS)
        ),
        probatio.Required("kind"): probatio.In([kind.value for kind in FileKind]),
    }
)
@websocket_api.async_response
@_with_access
async def ws_sign_documents(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: PaperlessLookupConfigEntry,
    access: UserAccess,
) -> None:
    """Return short-lived signed URLs for the documents the user may see (others are left out)."""
    paths: dict[str, str] = {}
    for document_id in msg["document_ids"]:
        try:
            get_document(entry, access, document_id)
        except DocumentNotFoundError:
            continue
        paths[str(document_id)] = async_sign_path(
            hass,
            DOCUMENT_PATH.format(document_id=document_id, kind=msg["kind"]),
            SIGNED_PATH_EXPIRATION,
            refresh_token_id=connection.refresh_token_id,
        )
    connection.send_result(msg["id"], {"paths": paths})


# ---- Commands for administrators ------------------------------------------------------------


@websocket_api.websocket_command({probatio.Required("type"): f"{DOMAIN}/devices_without_manual"})
@websocket_api.require_admin
@websocket_api.async_response
@_with_access
async def ws_devices_without_manual(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: PaperlessLookupConfigEntry,
    access: UserAccess,
) -> None:
    """Return the devices without a manual (not ignored)."""
    fallback = bool(entry.options.get(CONF_ZIGBEE2MQTT_FALLBACK, False))
    connection.send_result(
        msg["id"],
        {
            "devices": [
                {
                    "device_id": device.id,
                    "name": device.name,
                    "manufacturer": device.manufacturer,
                    "model": device.model,
                    "model_id": device.model_id,
                    "zigbee2mqtt_url": zigbee2mqtt_url(device) if fallback else None,
                }
                for device in entry.runtime_data.coordinator.devices_without_documents()
            ]
        },
    )


_LINK_SCHEMA: dict[str | probatio.Marker, Any] = {
    probatio.Required("device_id"): str,
    probatio.Required("document_id"): probatio.Coerce(int),
}


@websocket_api.websocket_command({probatio.Required("type"): f"{DOMAIN}/link", **_LINK_SCHEMA})
@websocket_api.require_admin
@websocket_api.async_response
@_with_access
async def ws_link(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: PaperlessLookupConfigEntry,
    access: UserAccess,
) -> None:
    """Link a document to a device."""
    device = _get_device(hass, msg["device_id"])
    document = get_document(entry, access, msg["document_id"])
    await entry.runtime_data.store.async_link(device.id, document.id)
    connection.send_result(msg["id"], _device_json(entry, access, device))


@websocket_api.websocket_command({probatio.Required("type"): f"{DOMAIN}/unlink", **_LINK_SCHEMA})
@websocket_api.require_admin
@websocket_api.async_response
@_with_access
async def ws_unlink(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: PaperlessLookupConfigEntry,
    access: UserAccess,
) -> None:
    """Remove a document from a device (also when it matched by model)."""
    device = _get_device(hass, msg["device_id"])
    document = get_document(entry, access, msg["document_id"])
    await entry.runtime_data.store.async_unlink(device.id, document.id)
    connection.send_result(msg["id"], _device_json(entry, access, device))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): f"{DOMAIN}/ignore",
        probatio.Required("device_id"): str,
        probatio.Required("ignored"): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@_with_access
async def ws_ignore(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    entry: PaperlessLookupConfigEntry,
    access: UserAccess,
) -> None:
    """Ignore a device (or stop ignoring it) in "devices without manual"."""
    device = _get_device(hass, msg["device_id"])
    await entry.runtime_data.store.async_set_ignored(device.id, msg["ignored"])
    connection.send_result(msg["id"], {"device_id": device.id, "ignored": msg["ignored"]})
