"""Access control: the one place that decides what a Home Assistant user may see.

Rules:
- Only documents in the index are reachable. The index only holds documents with the access tag
  in an enabled category (document type).
- A user sees a category when listed for it in the options, or when the user is an
  administrator and "administrators see all categories" is on.
- System-generated and inactive users see nothing.
- Anything a user may not see is reported as "not found" (never "forbidden"), so its existence
  does not leak.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.auth.models import User
from homeassistant.core import HomeAssistant

from .const import CONF_ADMINS_ALWAYS, CONF_CATEGORIES, DEFAULT_ADMINS_ALWAYS, DOMAIN
from .coordinator import IndexedDocument

if TYPE_CHECKING:
    from . import PaperlessLookupConfigEntry


class NotLoadedError(Exception):
    """The integration is not set up (or not reachable)."""


class DocumentNotFoundError(Exception):
    """The document does not exist, is not released, or the user may not see it."""


@dataclass(frozen=True, slots=True)
class UserAccess:
    """What one user may see."""

    categories: frozenset[int]
    is_admin: bool

    @property
    def allowed(self) -> bool:
        """Return whether the user sees at least one category."""
        return bool(self.categories)

    def can_view(self, document_type: int | None) -> bool:
        """Return whether the user may see documents of this type."""
        return document_type is not None and document_type in self.categories


def async_get_entry(hass: HomeAssistant) -> PaperlessLookupConfigEntry:
    """Return the loaded config entry (there is at most one)."""
    entries: list[PaperlessLookupConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise NotLoadedError
    return entries[0]


def visible_categories(options: Mapping[str, Any], user: User) -> frozenset[int]:
    """Return the categories an active, non-system user may see with these options.

    Also used by the options flow with options that are not stored yet.
    """
    categories: dict[str, list[str]] = options.get(CONF_CATEGORIES, {})
    if user.is_admin and options.get(CONF_ADMINS_ALWAYS, DEFAULT_ADMINS_ALWAYS):
        return frozenset(int(type_id) for type_id in categories)
    return frozenset(
        int(type_id) for type_id, user_ids in categories.items() if user.id in user_ids
    )


def user_access(entry: PaperlessLookupConfigEntry, user: User | None) -> UserAccess:
    """Return the categories a user may see; inactive and system users get nothing."""
    if user is None or not user.is_active or user.system_generated:
        return UserAccess(categories=frozenset(), is_admin=False)
    return UserAccess(categories=visible_categories(entry.options, user), is_admin=user.is_admin)


def get_document(
    entry: PaperlessLookupConfigEntry, access: UserAccess, document_id: int
) -> IndexedDocument:
    """Return a document from the index when the user may see it.

    Raises:
        DocumentNotFoundError: In every other case.
    """
    document = entry.runtime_data.coordinator.data.documents.get(document_id)
    if document is None or not access.can_view(document.document_type):
        raise DocumentNotFoundError
    return document


def visible_documents(
    access: UserAccess, documents: list[IndexedDocument]
) -> list[IndexedDocument]:
    """Return only the documents the user may see."""
    return [doc for doc in documents if access.can_view(doc.document_type)]
