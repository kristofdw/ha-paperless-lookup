"""Tests for the document file view (signed paths, 404 policy, whitelist, size limit)."""

from datetime import timedelta
from http import HTTPStatus
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.paperless_lookup.api import FileKind
from custom_components.paperless_lookup.const import CONF_ACCESS_TAG
from custom_components.paperless_lookup.views import MAX_FILE_BYTES

from .conftest import TEST_URL
from .security import (
    INVOICE_DOC,
    RECEIPT,
    RECEIPT_DOC,
    TRADFRI_DOC,
    Users,
    async_access_token,
    async_setup_entry,
    async_setup_users,
)

PDF = b"%PDF-1.4 synthetic test document\n" * 100


@pytest.fixture
async def users(hass: HomeAssistant, hass_admin_user: MockUser) -> Users:
    """Return the test users."""
    return await async_setup_users(hass, hass_admin_user)


@pytest.fixture
async def setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    users: Users,
) -> MockConfigEntry:
    """Set up the entry with the access matrix."""
    await async_setup_entry(hass, aioclient_mock, mock_config_entry, users)
    return mock_config_entry


def mock_document(
    aioclient_mock: AiohttpClientMocker,
    doc_id: int,
    *,
    document_type: int,
    tags: list[int] | None = None,
    kind: str = "preview",
    content: bytes = PDF,
    headers: dict[str, str] | None = None,
    **kwargs: Any,
) -> None:
    """Register the live metadata and the file of a document."""
    aioclient_mock.get(
        f"{TEST_URL}/api/documents/{doc_id}/",
        json={"id": doc_id, "title": "x", "document_type": document_type, "tags": tags or [1]},
    )
    aioclient_mock.get(
        f"{TEST_URL}/api/documents/{doc_id}/{kind}/",
        content=content,
        headers=headers or {"Content-Type": "application/pdf", "Content-Length": str(len(content))},
        **kwargs,
    )


async def signed(hass: HomeAssistant, user: Any, path: str, seconds: int = 60) -> str:
    """Return a path signed for a user."""
    refresh_token_id, _ = await async_access_token(hass, user)
    return async_sign_path(
        hass, path, timedelta(seconds=seconds), refresh_token_id=refresh_token_id
    )


@pytest.mark.usefixtures("setup")
async def test_preview(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    users: Users,
) -> None:
    """Test streaming a preview with a signed path."""
    mock_document(aioclient_mock, RECEIPT_DOC, document_type=RECEIPT)
    client = await hass_client_no_auth()

    response = await client.get(
        await signed(hass, users.reader, f"/api/paperless_lookup/document/{RECEIPT_DOC}/preview")
    )

    assert response.status == HTTPStatus.OK
    assert await response.read() == PDF
    assert response.headers["Content-Type"] == "application/pdf"
    assert response.headers["Content-Length"] == str(len(PDF))
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert (
        response.headers["Content-Disposition"] == f'inline; filename="document-{RECEIPT_DOC}.pdf"'
    )
    # The token never reaches the browser; the request to Paperless carried it.
    assert "fake-test-token" not in str(dict(response.headers))


@pytest.mark.usefixtures("setup")
@pytest.mark.parametrize(
    ("kind", "content_type", "disposition"),
    [
        ("thumb", "image/webp", f'inline; filename="document-{TRADFRI_DOC}.webp"'),
        ("download", "application/pdf", f'attachment; filename="document-{TRADFRI_DOC}.pdf"'),
    ],
)
async def test_thumb_and_download(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    users: Users,
    kind: str,
    content_type: str,
    disposition: str,
) -> None:
    """Test the thumbnail and the download (chunked, without Content-Length)."""
    mock_document(
        aioclient_mock,
        TRADFRI_DOC,
        document_type=1,
        kind=kind,
        content=b"RIFF....WEBP",
        headers={"Content-Type": content_type},
    )
    client = await hass_client_no_auth()

    response = await client.get(
        await signed(hass, users.guest, f"/api/paperless_lookup/document/{TRADFRI_DOC}/{kind}")
    )

    assert response.status == HTTPStatus.OK
    assert await response.read() == b"RIFF....WEBP"
    assert response.headers["Content-Disposition"] == disposition


@pytest.mark.usefixtures("setup")
async def test_authentication_required(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    users: Users,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unsigned, forged, reused and expired signatures."""
    client = await hass_client_no_auth()
    path = f"/api/paperless_lookup/document/{RECEIPT_DOC}/preview"
    good = await signed(hass, users.admin, path)

    unsigned = await client.get(path)
    forged = await client.get(good[:-4] + "AAAA")
    other_document = await client.get(good.replace(f"/{RECEIPT_DOC}/", f"/{INVOICE_DOC}/"))
    other_kind = await client.get(good.replace("/preview", "/download"))
    freezer.tick(timedelta(seconds=61))
    expired = await client.get(good)

    for response in (unsigned, forged, other_document, other_kind, expired):
        assert response.status == HTTPStatus.UNAUTHORIZED


@pytest.mark.usefixtures("setup")
@pytest.mark.parametrize(
    ("user", "path"),
    [
        # The invoice category is not granted to the reader.
        ("reader", f"/api/paperless_lookup/document/{INVOICE_DOC}/preview"),
        # The guest may only see manuals.
        ("guest", f"/api/paperless_lookup/document/{RECEIPT_DOC}/thumb"),
        ("nobody", f"/api/paperless_lookup/document/{TRADFRI_DOC}/preview"),
        # Not in the index (no access tag), not even for admins.
        ("admin", "/api/paperless_lookup/document/10/preview"),
        ("admin", "/api/paperless_lookup/document/999/preview"),
        ("admin", "/api/paperless_lookup/document/abc/preview"),
        ("admin", f"/api/paperless_lookup/document/{RECEIPT_DOC}/original"),
    ],
)
async def test_not_found_policy(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    users: Users,
    user: str,
    path: str,
) -> None:
    """Test that everything a user may not see is a 404, without asking Paperless."""
    aioclient_mock.clear_requests()
    client = await hass_client_no_auth()

    response = await client.get(await signed(hass, getattr(users, user), path))

    assert response.status == HTTPStatus.NOT_FOUND
    assert aioclient_mock.call_count == 0


@pytest.mark.usefixtures("setup")
@pytest.mark.parametrize(
    ("live", "status"),
    [
        ({"tags": [2]}, HTTPStatus.NOT_FOUND),  # tag removed since the last refresh
        ({"document_type": 3}, HTTPStatus.NOT_FOUND),  # type changed to a hidden category
        ({"status": HTTPStatus.NOT_FOUND}, HTTPStatus.NOT_FOUND),  # deleted in Paperless
        ({"status": HTTPStatus.INTERNAL_SERVER_ERROR}, HTTPStatus.BAD_GATEWAY),
    ],
)
async def test_live_check(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    users: Users,
    live: dict[str, Any],
    status: HTTPStatus,
) -> None:
    """Test that the document is checked live in Paperless before streaming."""
    body = {"id": RECEIPT_DOC, "title": "x", "document_type": RECEIPT, "tags": [1]}
    response_status = live.pop("status", HTTPStatus.OK)
    aioclient_mock.get(
        f"{TEST_URL}/api/documents/{RECEIPT_DOC}/", json={**body, **live}, status=response_status
    )
    client = await hass_client_no_auth()

    response = await client.get(
        await signed(hass, users.reader, f"/api/paperless_lookup/document/{RECEIPT_DOC}/preview")
    )

    assert response.status == status
    assert not any("/preview/" in str(call[1]) for call in aioclient_mock.mock_calls)


async def test_live_check_without_access_tag(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    users: Users,
) -> None:
    """Test that nothing is streamed once the access tag is cleared (index still filled)."""
    await async_setup_entry(hass, aioclient_mock, mock_config_entry, users)
    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator.access_tag = None  # as if the options changed between refresh and request
    mock_document(aioclient_mock, RECEIPT_DOC, document_type=RECEIPT)
    client = await hass_client_no_auth()

    response = await client.get(
        await signed(hass, users.reader, f"/api/paperless_lookup/document/{RECEIPT_DOC}/preview")
    )

    assert response.status == HTTPStatus.NOT_FOUND
    assert mock_config_entry.options[CONF_ACCESS_TAG] == 1


@pytest.mark.usefixtures("setup")
@pytest.mark.parametrize(
    ("kind", "headers", "status"),
    [
        ("preview", {"Content-Type": "text/html"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE),
        ("preview", {"Content-Type": "image/svg+xml"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE),
        ("thumb", {"Content-Type": "application/pdf"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE),
        (
            "thumb",
            {
                "Content-Type": "image/webp",
                "Content-Length": str(MAX_FILE_BYTES[FileKind.THUMB] + 1),
            },
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        ),
    ],
)
async def test_content_type_and_size(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    users: Users,
    kind: str,
    headers: dict[str, str],
    status: HTTPStatus,
) -> None:
    """Test the content type whitelist and the size limit."""
    mock_document(aioclient_mock, RECEIPT_DOC, document_type=RECEIPT, kind=kind, headers=headers)
    client = await hass_client_no_auth()

    response = await client.get(
        await signed(hass, users.reader, f"/api/paperless_lookup/document/{RECEIPT_DOC}/{kind}")
    )

    assert response.status == status


@pytest.mark.usefixtures("setup")
async def test_stream_interrupted(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    users: Users,
) -> None:
    """Test that a failure while streaming ends the connection instead of a partial file."""
    mock_document(
        aioclient_mock,
        RECEIPT_DOC,
        document_type=RECEIPT,
        headers={"Content-Type": "application/pdf", "Content-Length": str(len(PDF))},
        closing=True,
    )
    client = await hass_client_no_auth()

    response = await client.get(
        await signed(hass, users.reader, f"/api/paperless_lookup/document/{RECEIPT_DOC}/preview")
    )

    assert response.status == HTTPStatus.OK
    with pytest.raises(Exception):  # noqa: B017, PT011 - the client sees a broken payload
        await response.read()


async def test_not_loaded(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    users: Users,
) -> None:
    """Test a 404 after the entry was unloaded."""
    await async_setup_entry(hass, aioclient_mock, mock_config_entry, users)
    path = await signed(hass, users.admin, f"/api/paperless_lookup/document/{RECEIPT_DOC}/preview")
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    client = await hass_client_no_auth()

    response = await client.get(path)

    assert response.status == HTTPStatus.NOT_FOUND
