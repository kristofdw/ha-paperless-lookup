"""Tests for the Paperless API client (HTTP mocked with fixtures from the dev Paperless)."""

from collections.abc import Callable
from datetime import date
from http import HTTPStatus
from typing import Any

from aiohttp import ClientConnectionError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from yarl import URL

from custom_components.paperless_lookup import api
from custom_components.paperless_lookup.api import (
    API_VERSION,
    DOCUMENT_FIELDS,
    FileKind,
    PaperlessAuthError,
    PaperlessClient,
    PaperlessConnectionError,
    PaperlessCustomField,
    PaperlessDocument,
    PaperlessError,
    PaperlessFileTooLargeError,
    PaperlessNotFoundError,
    PaperlessObject,
    PaperlessPermissionError,
    PaperlessResponseError,
    PaperlessUnsupportedVersionError,
    PaperlessUser,
)

from .conftest import load_json_fixture

BASE = "http://paperless.test:8000"
TOKEN = "fake-test-token-1234"
ACCESS_TAG = 1  # "HA" in the dev Paperless
INVOICE, WARRANTY = 3, 4
VERSION_HEADERS = {"X-Api-Version": "10", "X-Version": "3.3.4"}

type ClientFactory = Callable[..., PaperlessClient]


@pytest.fixture
def make_client(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> ClientFactory:
    """Return a factory for clients that use the mocked session."""

    def factory(url: str = BASE, token: str = TOKEN) -> PaperlessClient:
        return PaperlessClient(async_get_clientsession(hass), url, token)

    return factory


@pytest.fixture
def client(make_client: ClientFactory) -> PaperlessClient:
    """Return a client for the fake test URL."""
    return make_client()


def mock_json(
    aioclient_mock: AiohttpClientMocker,
    path: str,
    fixture: str | None = None,
    *,
    json: Any = None,
    params: dict[str, str] | None = None,
    **kwargs: Any,
) -> None:
    """Register a JSON response for ``/api/<path>``."""
    aioclient_mock.get(
        f"{BASE}/api/{path}",
        params=params,
        json=load_json_fixture(fixture) if fixture else json,
        headers={"Content-Type": "application/json", **VERSION_HEADERS},
        **kwargs,
    )


def request_query(aioclient_mock: AiohttpClientMocker, index: int = -1) -> dict[str, str]:
    """Return the query of a recorded request."""
    url: URL = aioclient_mock.mock_calls[index][1]
    return dict(url.query)


# ---- Construction ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://paperless.test:8000", "http://paperless.test:8000"),
        ("http://paperless.test:8000/", "http://paperless.test:8000"),
        ("  https://paperless.test/sub/path/ ", "https://paperless.test/sub/path"),
    ],
)
def test_base_url_normalized(make_client: ClientFactory, url: str, expected: str) -> None:
    """Test that the base URL is normalized."""
    assert make_client(url).base_url == expected


@pytest.mark.parametrize(
    "url",
    ["ftp://paperless.test", "paperless.test:8000", "http://", "http://h.test/?a=1", "http://h#x"],
)
def test_invalid_url(make_client: ClientFactory, url: str) -> None:
    """Test that invalid URLs are refused."""
    with pytest.raises(ValueError, match="URL"):
        make_client(url)


def test_empty_token(make_client: ClientFactory) -> None:
    """Test that an empty token is refused."""
    with pytest.raises(ValueError, match="token"):
        make_client(token="   ")


def test_repr_hides_token(client: PaperlessClient) -> None:
    """Test that repr() does not contain the token."""
    assert TOKEN not in repr(client)
    assert BASE in repr(client)


# ---- Requests -------------------------------------------------------------------------------


async def test_get_user_and_headers(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the user lookup, the auth/version headers and the server version."""
    mock_json(aioclient_mock, "ui_settings/", "ui_settings")

    user = await client.async_get_user()

    assert user == PaperlessUser(
        id=3,
        username="ha-lookup",
        is_staff=False,
        is_superuser=False,
        permissions=frozenset(
            {
                "view_tag",
                "view_note",
                "view_documenttype",
                "view_correspondent",
                "view_document",
                "view_uisettings",
                "view_customfield",
            }
        ),
    )
    assert client.server_version == "3.3.4"
    method, url, _, headers = aioclient_mock.mock_calls[0]
    assert method.lower() == "get"
    assert str(url) == f"{BASE}/api/ui_settings/"
    assert headers == {
        "Authorization": f"Token {TOKEN}",
        "Accept": f"application/json; version={API_VERSION}",
    }
    # The token is only sent in the header, never in the URL.
    assert TOKEN not in str(url)


async def test_get_user_with_sub_path(
    make_client: ClientFactory, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a base URL with a path prefix is kept."""
    aioclient_mock.get(
        "https://paperless.test/sub/api/ui_settings/", json=load_json_fixture("ui_settings")
    )
    client = make_client("https://paperless.test/sub/")

    user = await client.async_get_user()

    assert user.username == "ha-lookup"
    assert client.server_version is None


@pytest.mark.parametrize(
    "body",
    [{"settings": {}}, {"user": {"id": "x", "username": "a"}}, {"user": None}],
)
async def test_get_user_invalid(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker, body: dict[str, Any]
) -> None:
    """Test an unexpected user settings response."""
    mock_json(aioclient_mock, "ui_settings/", json=body)

    with pytest.raises(PaperlessResponseError):
        await client.async_get_user()


async def test_get_objects(client: PaperlessClient, aioclient_mock: AiohttpClientMocker) -> None:
    """Test tags, document types, correspondents and custom fields."""
    mock_json(aioclient_mock, "tags/", "tags")
    mock_json(aioclient_mock, "document_types/", "document_types")
    mock_json(aioclient_mock, "correspondents/", "correspondents")
    mock_json(aioclient_mock, "custom_fields/", "custom_fields")

    tags = await client.async_get_tags()
    types = await client.async_get_document_types()
    correspondents = await client.async_get_correspondents()
    fields = await client.async_get_custom_fields()

    assert set(tags) == {PaperlessObject(1, "HA"), PaperlessObject(2, "Finance")}
    assert {t.name for t in types} == {"Manual", "Receipt", "Invoice", "Warranty", "Bank statement"}
    assert len(correspondents) == 7
    assert PaperlessObject(2, "Aqara") in correspondents
    assert fields == [PaperlessCustomField(1, "HA model", "string")]
    assert request_query(aioclient_mock, 0) == {"page": "1", "page_size": "100"}


async def test_get_documents_paginated(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test listing all documents with the access tag over two pages."""
    mock_json(aioclient_mock, "documents/", "documents_page_1", params={"page": "1"})
    mock_json(aioclient_mock, "documents/", "documents_page_2", params={"page": "2"})

    documents = await client.async_get_documents(access_tag_id=ACCESS_TAG)

    assert len(documents) == 9
    assert aioclient_mock.call_count == 2
    query = request_query(aioclient_mock, 0)
    assert query == {
        "tags__id__all": "1",
        "fields": DOCUMENT_FIELDS,
        "ordering": "-created",
        "page": "1",
        "page_size": "100",
    }
    # Pages are requested by number; the host in the "next" link is never used.
    assert str(aioclient_mock.mock_calls[1][1]).startswith(f"{BASE}/api/documents/?")
    assert request_query(aioclient_mock, 1)["page"] == "2"
    assert documents[0] == PaperlessDocument(
        id=7,
        title="Groceries receipt",
        document_type=2,
        correspondent=6,
        created=date(2026, 10, 30),
        tags=frozenset({1}),
        custom_fields={},
        mime_type="application/pdf",
    )
    manuals = {doc.title: doc for doc in documents if doc.document_type == 1}
    assert manuals["Aqara motion and door sensor manual"].custom_fields == {
        1: "RTCGQ11LM; MCCGQ11LM"
    }
    assert all(ACCESS_TAG in doc.tags for doc in documents)


async def test_get_documents_by_type(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the document type filter and the second scope check."""
    page = load_json_fixture("documents_page_1")
    page["next"] = None
    mock_json(aioclient_mock, "documents/", json=page)

    # The (mocked) server ignores the filter: the client drops the other types itself.
    receipts = await client.async_get_documents(access_tag_id=ACCESS_TAG, document_type_ids=[2])

    assert request_query(aioclient_mock)["document_type__id__in"] == "2"
    assert {doc.document_type for doc in receipts} == {2}
    assert len(receipts) == 3


async def test_get_documents_drops_documents_without_tag(
    client: PaperlessClient,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that documents without the access tag never leave the client."""
    page = load_json_fixture("documents_page_2")
    page["results"].append(
        {"id": 10, "title": "Bank statement (no HA tag, shared)", "document_type": 5, "tags": [2]}
    )
    mock_json(aioclient_mock, "documents/", json=page)

    documents = await client.async_get_documents(access_tag_id=ACCESS_TAG)

    assert 10 not in {doc.id for doc in documents}
    assert len(documents) == 4
    assert "1 document(s) outside the requested scope" in caplog.text
    assert "Bank statement" not in caplog.text


async def test_get_documents_no_types(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that an empty type list returns nothing without asking Paperless."""
    assert await client.async_get_documents(access_tag_id=ACCESS_TAG, document_type_ids=[]) == []
    assert aioclient_mock.call_count == 0


async def test_get_all_empty_page_stops(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that an empty page ends the pagination even with a next link."""
    mock_json(
        aioclient_mock,
        "tags/",
        json={"count": 0, "next": f"{BASE}/api/tags/?page=2", "results": []},
    )

    assert await client.async_get_tags() == []
    assert aioclient_mock.call_count == 1


async def test_get_all_too_many_pages(
    client: PaperlessClient,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that endless pagination is cut off."""
    monkeypatch.setattr(api, "MAX_PAGES", 3)
    mock_json(
        aioclient_mock,
        "tags/",
        json={"count": 9, "next": "x", "results": [{"id": 1, "name": "HA"}]},
    )

    with pytest.raises(PaperlessResponseError, match="Too many pages"):
        await client.async_get_tags()
    assert aioclient_mock.call_count == 3


@pytest.mark.parametrize(
    "body",
    [
        {"count": 1, "next": None},
        {"count": 1, "next": None, "results": "x"},
        {"count": 1, "next": None, "results": [1]},
    ],
)
async def test_get_all_invalid(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker, body: dict[str, Any]
) -> None:
    """Test an invalid list response."""
    mock_json(aioclient_mock, "tags/", json=body)

    with pytest.raises(PaperlessResponseError, match="Unexpected list response"):
        await client.async_get_tags()


@pytest.mark.parametrize(
    ("path", "method", "item"),
    [
        ("tags/", "async_get_tags", {"id": 1}),
        ("custom_fields/", "async_get_custom_fields", {"id": 1, "name": "x"}),
        ("documents/", "async_get_documents", {"id": "x", "title": "t"}),
        ("documents/", "async_get_documents", {"id": 1, "title": "t", "custom_fields": [1]}),
    ],
)
async def test_invalid_items(
    client: PaperlessClient,
    aioclient_mock: AiohttpClientMocker,
    path: str,
    method: str,
    item: dict[str, Any],
) -> None:
    """Test invalid objects in list responses."""
    mock_json(aioclient_mock, path, json={"count": 1, "next": None, "results": [item]})
    kwargs = {"access_tag_id": ACCESS_TAG} if path == "documents/" else {}

    with pytest.raises(PaperlessResponseError, match="Unexpected"):
        await getattr(client, method)(**kwargs)


async def test_search(client: PaperlessClient, aioclient_mock: AiohttpClientMocker) -> None:
    """Test a full-text search with all filters."""
    mock_json(aioclient_mock, "documents/", "search")

    result = await client.async_search(
        " washing ",
        access_tag_id=ACCESS_TAG,
        document_type_ids={WARRANTY, INVOICE},
        correspondent_ids=[4],
        created_from=date(2025, 1, 1),
        created_to=date(2025, 12, 31),
        page=1,
        page_size=25,
    )

    assert request_query(aioclient_mock) == {
        "text": "washing",
        "tags__id__all": "1",
        "document_type__id__in": "3,4",
        "correspondent__id__in": "4",
        "created__gte": "2025-01-01",
        "created__lte": "2025-12-31",
        "fields": DOCUMENT_FIELDS,
        "ordering": "-created",
        "page": "1",
        "page_size": "25",
    }
    assert result.count == 2
    assert {hit.document.title for hit in result.hits} == {
        "Washing machine warranty",
        "Washing machine invoice",
    }
    warranty = next(hit for hit in result.hits if hit.document.id == 9)
    assert warranty.score is not None
    assert warranty.highlights is not None
    assert "<b>Washing</b>" in warranty.highlights
    assert warranty.document.custom_fields == {1: "W800"}


async def test_search_without_text(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test listing by filters only: no text parameter, no search hit data."""
    mock_json(aioclient_mock, "documents/", "documents_page_2")

    result = await client.async_search("  ", access_tag_id=ACCESS_TAG, page=2, page_size=5)

    query = request_query(aioclient_mock)
    assert "text" not in query
    assert "document_type__id__in" not in query
    assert "correspondent__id__in" not in query
    assert query["page"] == "2"
    assert query["page_size"] == "5"
    assert result.count == 9
    assert len(result.hits) == 4
    assert all(hit.score is None and hit.highlights is None for hit in result.hits)


async def test_search_drops_out_of_scope(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that search results with another type or without the tag are dropped."""
    body = load_json_fixture("search")
    body["results"][0]["document_type"] = 5
    body["results"][1]["tags"] = [2]
    body["results"][1]["__search_hit__"] = "garbage"
    mock_json(aioclient_mock, "documents/", json=body)

    result = await client.async_search(
        "washing", access_tag_id=ACCESS_TAG, document_type_ids=[INVOICE, WARRANTY]
    )

    assert result.hits == []


async def test_search_no_types(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a search with no allowed types returns nothing without a request."""
    result = await client.async_search("washing", access_tag_id=ACCESS_TAG, document_type_ids=())

    assert result.count == 0
    assert result.hits == []
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(("page", "page_size"), [(0, 25), (1, 0), (1, 101)])
async def test_search_invalid_paging(client: PaperlessClient, page: int, page_size: int) -> None:
    """Test that invalid paging is refused."""
    with pytest.raises(ValueError, match="page"):
        await client.async_search(None, access_tag_id=ACCESS_TAG, page=page, page_size=page_size)


@pytest.mark.parametrize(
    "body",
    [{"results": []}, {"count": 1, "results": None}, {"count": 1, "results": [{"id": 1}]}],
)
async def test_search_invalid(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker, body: dict[str, Any]
) -> None:
    """Test an invalid search response."""
    mock_json(aioclient_mock, "documents/", json=body)

    with pytest.raises(PaperlessResponseError):
        await client.async_search("x", access_tag_id=ACCESS_TAG)


async def test_get_document(client: PaperlessClient, aioclient_mock: AiohttpClientMocker) -> None:
    """Test fetching one document's metadata."""
    mock_json(aioclient_mock, "documents/9/", "document")

    document = await client.async_get_document(9)

    assert document.title == "Washing machine warranty"
    assert document.document_type == WARRANTY
    assert document.created == date(2025, 2, 17)
    assert request_query(aioclient_mock) == {"fields": DOCUMENT_FIELDS}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"created": "2025-02-17T10:00:00+01:00"}, date(2025, 2, 17)),
        ({"created": "not a date"}, None),
        ({"created": None}, None),
        ({}, None),
    ],
)
async def test_document_created_variants(
    client: PaperlessClient,
    aioclient_mock: AiohttpClientMocker,
    raw: dict[str, Any],
    expected: date | None,
) -> None:
    """Test lenient parsing of minimal documents."""
    mock_json(aioclient_mock, "documents/1/", json={"id": 1, "title": "t", **raw})

    document = await client.async_get_document(1)

    assert document.created == expected
    assert document.document_type is None
    assert document.correspondent is None
    assert document.tags == frozenset()
    assert document.mime_type is None


# ---- Files ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "content_type", "expected_type"),
    [
        (FileKind.PREVIEW, "application/pdf", "application/pdf"),
        (FileKind.DOWNLOAD, "application/pdf", "application/pdf"),
        (FileKind.THUMB, "image/webp; charset=binary", "image/webp"),
    ],
)
async def test_open_file(
    client: PaperlessClient,
    aioclient_mock: AiohttpClientMocker,
    kind: FileKind,
    content_type: str,
    expected_type: str,
) -> None:
    """Test streaming a document file."""
    body = b"%PDF-1.4 synthetic" * 10_000
    aioclient_mock.get(
        f"{BASE}/api/documents/1/{kind.value}/",
        content=body,
        headers={"Content-Type": content_type, "Content-Length": str(len(body))},
    )

    async with client.async_open_file(1, kind) as file:
        assert file.content_type == expected_type
        assert file.content_length == len(body)
        received = b"".join([chunk async for chunk in file.iter_chunks()])

    assert received == body


async def test_open_file_without_headers(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test defaults when Content-Type and Content-Length are missing."""
    aioclient_mock.get(f"{BASE}/api/documents/1/download/", content=b"data")

    async with client.async_open_file(1, FileKind.DOWNLOAD) as file:
        assert file.content_type == "application/octet-stream"
        assert file.content_length is None
        assert [chunk async for chunk in file.iter_chunks()] == [b"data"]


async def test_open_file_too_large_by_header(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that a too large Content-Length is refused before streaming."""
    aioclient_mock.get(
        f"{BASE}/api/documents/1/preview/",
        content=b"x" * 11,
        headers={"Content-Type": "application/pdf", "Content-Length": "11"},
    )

    with pytest.raises(PaperlessFileTooLargeError):
        async with client.async_open_file(1, FileKind.PREVIEW, max_bytes=10):
            pytest.fail("The file must not be opened")


async def test_open_file_too_large_while_streaming(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the size limit is enforced without a Content-Length header."""
    aioclient_mock.get(f"{BASE}/api/documents/1/preview/", content=b"x" * 11)

    async with client.async_open_file(1, FileKind.PREVIEW, max_bytes=10) as file:
        with pytest.raises(PaperlessFileTooLargeError):
            _ = [chunk async for chunk in file.iter_chunks()]


async def test_open_file_connection_lost(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a connection error while streaming."""
    aioclient_mock.get(f"{BASE}/api/documents/1/preview/", content=b"x", closing=True)

    async with client.async_open_file(1, FileKind.PREVIEW) as file:
        with pytest.raises(PaperlessConnectionError, match="Reading the document file failed"):
            _ = [chunk async for chunk in file.iter_chunks()]


async def test_open_file_not_found(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a missing (or invisible) document file."""
    aioclient_mock.get(f"{BASE}/api/documents/999/thumb/", status=HTTPStatus.NOT_FOUND)

    with pytest.raises(PaperlessNotFoundError):
        async with client.async_open_file(999, FileKind.THUMB):
            pytest.fail("The file must not be opened")


# ---- Errors ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "error", "message"),
    [
        (HTTPStatus.FOUND, PaperlessConnectionError, "redirected"),
        (HTTPStatus.BAD_REQUEST, PaperlessResponseError, "Unexpected HTTP 400"),
        (HTTPStatus.UNAUTHORIZED, PaperlessAuthError, "token was rejected"),
        (HTTPStatus.FORBIDDEN, PaperlessPermissionError, "may not access"),
        (HTTPStatus.NOT_FOUND, PaperlessNotFoundError, "Not found"),
        (HTTPStatus.NOT_ACCEPTABLE, PaperlessUnsupportedVersionError, "3.0.0 or newer"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, PaperlessConnectionError, "server error"),
        (HTTPStatus.BAD_GATEWAY, PaperlessConnectionError, "server error"),
    ],
)
async def test_http_errors(
    client: PaperlessClient,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
    error: type[PaperlessError],
    message: str,
) -> None:
    """Test the mapping of HTTP errors to exceptions."""
    mock_json(aioclient_mock, "ui_settings/", json={"detail": "x"}, status=status)

    with pytest.raises(error, match=message) as exc_info:
        await client.async_get_user()

    assert TOKEN not in str(exc_info.value)


@pytest.mark.parametrize("exc", [TimeoutError(), ClientConnectionError(f"Token {TOKEN}")])
async def test_connection_errors(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker, exc: Exception
) -> None:
    """Test that network errors and timeouts become connection errors without details."""
    aioclient_mock.get(f"{BASE}/api/ui_settings/", exc=exc)

    with pytest.raises(PaperlessConnectionError, match="Cannot communicate") as exc_info:
        await client.async_get_user()

    assert TOKEN not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__


@pytest.mark.parametrize(
    "kwargs", [{"text": "<html>not json</html>"}, {"json": [1, 2]}, {"json": "text"}]
)
async def test_invalid_json(
    client: PaperlessClient, aioclient_mock: AiohttpClientMocker, kwargs: dict[str, Any]
) -> None:
    """Test responses that are not a JSON object."""
    aioclient_mock.get(f"{BASE}/api/ui_settings/", **kwargs)

    with pytest.raises(PaperlessResponseError):
        await client.async_get_user()
