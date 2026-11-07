"""Index of the documents released to Home Assistant, and their links to devices."""

from dataclasses import dataclass, field
from datetime import date, timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PaperlessAuthError, PaperlessClient, PaperlessDocument, PaperlessError
from .const import (
    CONF_ACCESS_TAG,
    CONF_CATEGORIES,
    CONF_DEVICE_CATEGORIES,
    CONF_MODEL_FIELD,
    CONF_REFRESH_INTERVAL,
    DEFAULT_REFRESH_INTERVAL,
    DOMAIN,
)
from .matching import DeviceInfo, matches, model_keys as build_model_keys, split_models
from .store import LinkStore

if TYPE_CHECKING:
    from . import PaperlessLookupConfigEntry

_LOGGER = logging.getLogger(__name__)

ZIGBEE2MQTT_IDENTIFIER_PREFIX = "zigbee2mqtt_"


@dataclass(frozen=True, slots=True)
class IndexedDocument:
    """A released document in the index (metadata only)."""

    id: int
    title: str
    document_type: int
    correspondent: int | None
    created: date | None
    mime_type: str | None
    models: tuple[str, ...] = ()
    model_keys: frozenset[str] = frozenset()


@dataclass(slots=True)
class DocumentIndex:
    """All documents with the access tag in an enabled category."""

    documents: dict[int, IndexedDocument] = field(default_factory=dict)
    document_types: dict[int, str] = field(default_factory=dict)
    correspondents: dict[int, str] = field(default_factory=dict)


class PaperlessLookupCoordinator(DataUpdateCoordinator[DocumentIndex]):
    """Refresh the document index periodically."""

    config_entry: PaperlessLookupConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PaperlessLookupConfigEntry,
        client: PaperlessClient,
        store: LinkStore,
    ) -> None:
        """Initialize the coordinator."""
        options = entry.options
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                minutes=int(options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL))
            ),
        )
        self.client = client
        self.store = store
        access_tag = options.get(CONF_ACCESS_TAG)
        self.access_tag: int | None = int(access_tag) if access_tag is not None else None
        self.categories: frozenset[int] = frozenset(
            int(type_id) for type_id in options.get(CONF_CATEGORIES, {})
        )
        self.device_categories: frozenset[int] = (
            frozenset(int(type_id) for type_id in options.get(CONF_DEVICE_CATEGORIES, []))
            & self.categories
        )
        model_field = options.get(CONF_MODEL_FIELD)
        self.model_field: int | None = int(model_field) if model_field is not None else None

    async def _async_update_data(self) -> DocumentIndex:
        """Fetch the index from Paperless."""
        try:
            document_types = await self.client.async_get_document_types()
            correspondents = await self.client.async_get_correspondents()
            documents = (
                await self.client.async_get_documents(
                    access_tag_id=self.access_tag, document_type_ids=self.categories
                )
                if self.access_tag is not None and self.categories
                else []
            )
        except PaperlessAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except PaperlessError as err:
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="update_failed") from err
        return DocumentIndex(
            documents={
                doc.id: indexed
                for doc in documents
                if (indexed := self._index_document(doc)) is not None
            },
            document_types={obj.id: obj.name for obj in document_types},
            correspondents={obj.id: obj.name for obj in correspondents},
        )

    def _index_document(self, doc: PaperlessDocument) -> IndexedDocument | None:
        """Return the index entry of a document, or None when it is out of scope."""
        if (
            self.access_tag is None
            or self.access_tag not in doc.tags
            or doc.document_type is None
            or doc.document_type not in self.categories
        ):  # pragma: no cover - the client already drops these; kept as a last check
            return None
        models: tuple[str, ...] = ()
        if self.model_field is not None and doc.document_type in self.device_categories:
            models = split_models(doc.custom_fields.get(self.model_field))
        return IndexedDocument(
            id=doc.id,
            title=doc.title,
            document_type=doc.document_type,
            correspondent=doc.correspondent,
            created=doc.created,
            mime_type=doc.mime_type,
            models=models,
            model_keys=build_model_keys(models),
        )

    # ---- Devices ----------------------------------------------------------------------------

    def device_documents(self, device: DeviceInfo) -> list[IndexedDocument]:
        """Return the documents of a device: model matches plus manual links, minus unlinks.

        Manual links may point to documents of any category; matching by model only uses
        device categories. Not filtered by user access: the caller must do that.
        """
        documents = self.data.documents
        unlinked = self.store.unlinks(device.id)
        matched = {
            doc.id
            for doc in documents.values()
            if doc.model_keys and doc.id not in unlinked and matches(doc.model_keys, device)
        }
        linked = {doc_id for doc_id in self.store.links(device.id) if doc_id in documents}
        return sorted(
            (documents[doc_id] for doc_id in matched | linked),
            key=lambda doc: (doc.created or date.min, doc.id),
            reverse=True,
        )

    def devices_without_documents(self) -> list[DeviceInfo]:
        """Return the devices without a document of a device category (not ignored)."""
        if not self.device_categories:
            return []
        without = [
            device
            for device in async_physical_devices(self.hass)
            if not self.store.is_ignored(device.id)
            and not any(
                doc.document_type in self.device_categories for doc in self.device_documents(device)
            )
        ]
        return sorted(without, key=lambda device: (device.name.casefold(), device.id))

    def diagnostics(self) -> dict[str, Any]:
        """Return counts only (no titles)."""
        per_type: dict[str, int] = {}
        for doc in self.data.documents.values():
            per_type[str(doc.document_type)] = per_type.get(str(doc.document_type), 0) + 1
        store = self.store.data
        documents = self.data.documents.values()
        with_correspondent = [doc for doc in documents if doc.correspondent is not None]
        return {
            "last_update_success": self.last_update_success,
            # Objects the Paperless user can see (owned objects must be shared with it).
            "document_types_visible": len(self.data.document_types),
            "correspondents_visible": len(self.data.correspondents),
            "documents": len(self.data.documents),
            "documents_per_category": dict(sorted(per_type.items())),
            "documents_with_correspondent": len(with_correspondent),
            # A correspondent the Paperless user cannot see: no store name or store filter.
            "documents_with_hidden_correspondent": sum(
                1 for doc in with_correspondent if doc.correspondent not in self.data.correspondents
            ),
            "documents_with_models": sum(
                1 for doc in self.data.documents.values() if doc.model_keys
            ),
            "devices_with_links": len(store["links"]),
            "devices_with_unlinks": len(store["unlinks"]),
            "ignored_devices": len(store["ignored"]),
        }


def device_info(device: dr.DeviceEntry) -> DeviceInfo:
    """Return the matching view of a device registry entry."""
    return DeviceInfo(
        id=device.id,
        name=device.name_by_user or device.name or "",
        manufacturer=device.manufacturer,
        model=device.model,
        model_id=device.model_id,
        is_zigbee2mqtt=_is_zigbee2mqtt(device.identifiers),
    )


def _is_zigbee2mqtt(identifiers: set[tuple[str, str]]) -> bool:
    return any(
        domain == "mqtt" and value.startswith(ZIGBEE2MQTT_IDENTIFIER_PREFIX)
        for domain, value in identifiers
    )


def async_physical_devices(hass: HomeAssistant) -> list[DeviceInfo]:
    """Return enabled, non-service devices that have a model (child devices have none)."""
    return [
        device_info(device)
        for device in dr.async_get(hass).devices
        if device.disabled_by is None
        and device.entry_type is None
        and (device.model or device.model_id)
    ]


def async_get_device(hass: HomeAssistant, device_id: str) -> DeviceInfo | None:
    """Return a device by id, or None when it does not exist or is a child device."""
    device = dr.async_get(hass).async_get(device_id)
    return device_info(device) if isinstance(device, dr.DeviceEntry) else None
