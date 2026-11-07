"""Tests for the central access check (user x category x document)."""

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.paperless_lookup.access import (
    DocumentNotFoundError,
    NotLoadedError,
    async_get_entry,
    get_document,
    user_access,
)
from custom_components.paperless_lookup.const import CONF_ADMINS_ALWAYS

from .security import (
    AQARA_DOC,
    BANK,
    INVOICE,
    INVOICE_DOC,
    MANUAL,
    RECEIPT,
    RECEIPT_DOC,
    TRADFRI_DOC,
    WARRANTY,
    WARRANTY_DOC,
    async_setup_entry,
    async_setup_users,
    async_user,
)

ALL = {MANUAL, RECEIPT, INVOICE, WARRANTY, BANK}


async def test_not_loaded(hass: HomeAssistant) -> None:
    """Test that nothing is reachable without a loaded entry."""
    with pytest.raises(NotLoadedError):
        async_get_entry(hass)


@pytest.mark.parametrize(
    ("admins_always", "expected"),
    [
        (
            True,
            {
                "admin": ALL,
                "reader": {MANUAL, RECEIPT},
                "guest": {MANUAL},
                "nobody": set(),
            },
        ),
        (
            False,
            {
                "admin": set(),
                "reader": {MANUAL, RECEIPT},
                "guest": {MANUAL},
                "nobody": set(),
            },
        ),
    ],
)
async def test_access_matrix(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    hass_admin_user: MockUser,
    admins_always: bool,
    expected: dict[str, set[int]],
) -> None:
    """Test the categories and documents per user, with and without admin access."""
    users = await async_setup_users(hass, hass_admin_user)
    await async_setup_entry(
        hass, aioclient_mock, mock_config_entry, users, **{CONF_ADMINS_ALWAYS: admins_always}
    )
    entry = async_get_entry(hass)
    documents = {
        TRADFRI_DOC: MANUAL,
        AQARA_DOC: MANUAL,
        RECEIPT_DOC: RECEIPT,
        INVOICE_DOC: INVOICE,
        WARRANTY_DOC: WARRANTY,
    }

    for name, categories in expected.items():
        access = user_access(entry, getattr(users, name))
        assert access.categories == categories, name
        assert access.allowed is bool(categories)
        assert access.is_admin is (name == "admin")
        for doc_id, doc_type in documents.items():
            if doc_type in categories:
                assert get_document(entry, access, doc_id).id == doc_id
            else:
                with pytest.raises(DocumentNotFoundError):
                    get_document(entry, access, doc_id)
        # Not in the index (no access tag, or not released): never visible, not even to admins.
        for doc_id in (10, 11, 12, 999):
            with pytest.raises(DocumentNotFoundError):
                get_document(entry, access, doc_id)


async def test_inactive_system_and_missing_users(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    hass_admin_user: MockUser,
) -> None:
    """Test that inactive, system-generated and missing users see nothing."""
    users = await async_setup_users(hass, hass_admin_user)
    await async_setup_entry(hass, aioclient_mock, mock_config_entry, users)
    entry = async_get_entry(hass)
    inactive_admin = await async_user(hass, "Inactive", admin=True, is_active=False)
    system = await async_user(hass, "System", admin=True, system_generated=True)

    for user in (inactive_admin, system, None):
        access = user_access(entry, user)
        assert access.categories == frozenset()
        assert not access.can_view(MANUAL)
        assert not access.can_view(None)
