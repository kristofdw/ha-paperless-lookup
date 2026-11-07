"""Persistent manual links between devices and documents.

Stored in Home Assistant's ``.storage`` (no document data, only ids):

- ``links``: device id -> document ids linked by hand,
- ``unlinks``: device id -> document ids that matched by model but were removed by hand,
- ``ignored``: device ids that never count as "without manual".
"""

from typing import Any, Final, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_VERSION: Final = 1
STORAGE_MINOR_VERSION: Final = 1


class LinksData(TypedDict):
    """Serialized store contents."""

    links: dict[str, list[int]]
    unlinks: dict[str, list[int]]
    ignored: list[str]


def _id_lists(raw: object) -> dict[str, list[int]]:
    """Return a clean ``device id -> sorted document ids`` mapping."""
    if not isinstance(raw, dict):
        return {}
    result: dict[str, list[int]] = {}
    for device_id, doc_ids in raw.items():
        if isinstance(device_id, str) and isinstance(doc_ids, list):
            ids = sorted({doc_id for doc_id in doc_ids if isinstance(doc_id, int)})
            if ids:
                result[device_id] = ids
    return result


def normalize_data(raw: object) -> LinksData:
    """Return valid store data, dropping anything malformed."""
    data = raw if isinstance(raw, dict) else {}
    ignored = data.get("ignored")
    return LinksData(
        links=_id_lists(data.get("links")),
        unlinks=_id_lists(data.get("unlinks")),
        ignored=sorted(
            {item for item in ignored if isinstance(item, str)}
            if isinstance(ignored, list)
            else set()
        ),
    )


class _LinksStore(Store[LinksData]):
    """Store with migrations."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> LinksData:
        """Migrate older data. Version 1.0 (pre-release) could lack keys; fill them in.

        Home Assistant itself refuses data of a newer major version.
        """
        return normalize_data(old_data)


class LinkStore:
    """Manual device/document links of one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the store."""
        self._store = _LinksStore(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry_id}",
            minor_version=STORAGE_MINOR_VERSION,
        )
        self._data = normalize_data(None)

    async def async_load(self) -> None:
        """Load the stored links."""
        self._data = normalize_data(await self._store.async_load())

    async def async_remove(self) -> None:
        """Delete the stored links (when the config entry is removed)."""
        await self._store.async_remove()

    @property
    def data(self) -> LinksData:
        """Return the current data (read-only use)."""
        return self._data

    def links(self, device_id: str) -> frozenset[int]:
        """Return the documents linked by hand to a device."""
        return frozenset(self._data["links"].get(device_id, ()))

    def unlinks(self, device_id: str) -> frozenset[int]:
        """Return the documents unlinked by hand from a device."""
        return frozenset(self._data["unlinks"].get(device_id, ()))

    def is_ignored(self, device_id: str) -> bool:
        """Return whether the device is ignored for "devices without manual"."""
        return device_id in self._data["ignored"]

    async def async_link(self, device_id: str, document_id: int) -> None:
        """Link a document to a device by hand."""
        _add(self._data["links"], device_id, document_id)
        _discard(self._data["unlinks"], device_id, document_id)
        await self._async_save()

    async def async_unlink(self, device_id: str, document_id: int) -> None:
        """Remove a document from a device, also when it matched by model."""
        _discard(self._data["links"], device_id, document_id)
        _add(self._data["unlinks"], device_id, document_id)
        await self._async_save()

    async def async_set_ignored(self, device_id: str, ignored: bool) -> None:
        """Ignore or stop ignoring a device."""
        current = set(self._data["ignored"])
        if ignored:
            current.add(device_id)
        else:
            current.discard(device_id)
        self._data["ignored"] = sorted(current)
        await self._async_save()

    async def async_remove_device(self, device_id: str) -> None:
        """Forget everything about a removed device."""
        changed = self._data["links"].pop(device_id, None) is not None
        changed |= self._data["unlinks"].pop(device_id, None) is not None
        if device_id in self._data["ignored"]:
            self._data["ignored"].remove(device_id)
            changed = True
        if changed:
            await self._async_save()

    async def _async_save(self) -> None:
        await self._store.async_save(self._data)


def _add(mapping: dict[str, list[int]], device_id: str, document_id: int) -> None:
    mapping[device_id] = sorted({*mapping.get(device_id, []), int(document_id)})


def _discard(mapping: dict[str, list[int]], device_id: str, document_id: int) -> None:
    remaining = [doc_id for doc_id in mapping.get(device_id, []) if doc_id != document_id]
    if remaining:
        mapping[device_id] = remaining
    else:
        mapping.pop(device_id, None)
