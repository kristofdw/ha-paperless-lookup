"""Read-only client for the Paperless-ngx REST API.

Pure aiohttp, no Home Assistant imports: the caller passes the shared client session.

Security notes:
- The API token is only ever sent in the ``Authorization`` header. It never appears in URLs,
  exception messages, log messages or ``repr()``.
- Redirects are not followed, so the token cannot be forwarded to another host. Pagination
  never follows the ``next`` link from a response either: pages are requested by number.
- Document listings and searches always filter on the access tag server side, and the client
  drops anything outside the requested scope a second time.
- Document ``content`` (OCR text) is never requested; only the metadata fields in
  ``DOCUMENT_FIELDS``.
- ``/api/profile/`` is never used, because it returns the user's API token.
"""

from collections.abc import AsyncIterator, Collection, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import logging
from typing import Any, Final

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout
from yarl import URL

_LOGGER = logging.getLogger(__name__)

# API version 10 was introduced in Paperless-ngx 3.0.0 (which supports versions 9 and 10).
# Paperless answers 406 Not Acceptable when it does not support the requested version.
API_VERSION: Final = 10
MIN_PAPERLESS_VERSION: Final = "3.0.0"

REQUEST_TIMEOUT: Final = ClientTimeout(total=30)
FILE_TIMEOUT: Final = ClientTimeout(total=300, sock_connect=10, sock_read=60)
PAGE_SIZE: Final = 100
# Upper bound on pages fetched for one listing (100 000 objects), against endless pagination.
MAX_PAGES: Final = 1000
CHUNK_SIZE: Final = 64 * 1024
DEFAULT_MAX_FILE_BYTES: Final = 100 * 1024 * 1024

DOCUMENT_FIELDS: Final = "id,title,document_type,correspondent,created,tags,custom_fields,mime_type"


class PaperlessError(Exception):
    """Base class for all Paperless client errors."""


class PaperlessConnectionError(PaperlessError):
    """Paperless cannot be reached, timed out, redirected or returned a server error."""


class PaperlessAuthError(PaperlessError):
    """The API token was rejected (HTTP 401)."""


class PaperlessPermissionError(PaperlessError):
    """The Paperless user lacks a permission (HTTP 403)."""


class PaperlessNotFoundError(PaperlessError):
    """The object does not exist or the Paperless user may not see it (HTTP 404)."""


class PaperlessUnsupportedVersionError(PaperlessError):
    """The server does not support the API version of this client (HTTP 406)."""


class PaperlessResponseError(PaperlessError):
    """Paperless returned an unexpected status code or an invalid response body."""


class PaperlessFileTooLargeError(PaperlessError):
    """A document file is larger than the allowed maximum."""


class FileKind(StrEnum):
    """The file variants of a Paperless document."""

    PREVIEW = "preview"  # Archived (OCR'd PDF) version, inline.
    THUMB = "thumb"  # Thumbnail image (WebP in Paperless-ngx 3).
    DOWNLOAD = "download"  # Archived version as attachment.


@dataclass(frozen=True, slots=True)
class PaperlessUser:
    """The Paperless user the API token belongs to."""

    id: int
    username: str
    is_staff: bool
    is_superuser: bool
    permissions: frozenset[str]


@dataclass(frozen=True, slots=True)
class PaperlessObject:
    """A named Paperless object: tag, document type or correspondent."""

    id: int
    name: str


@dataclass(frozen=True, slots=True)
class PaperlessCustomField:
    """A custom field definition."""

    id: int
    name: str
    data_type: str


@dataclass(frozen=True, slots=True)
class PaperlessDocument:
    """Document metadata (never the content)."""

    id: int
    title: str
    document_type: int | None
    correspondent: int | None
    created: date | None
    tags: frozenset[int]
    custom_fields: Mapping[int, Any]
    mime_type: str | None


@dataclass(frozen=True, slots=True)
class PaperlessSearchHit:
    """A search result.

    ``highlights`` is a content snippet from Paperless with ``<b>`` markup around the matched
    words. It is untrusted text and must be escaped before it is rendered.
    """

    document: PaperlessDocument
    score: float | None
    highlights: str | None


@dataclass(frozen=True, slots=True)
class PaperlessSearchResult:
    """One page of search results."""

    count: int
    hits: list[PaperlessSearchHit]


@dataclass(slots=True)
class PaperlessFile:
    """An open document file. Valid only inside ``PaperlessClient.async_open_file``."""

    content_type: str
    content_length: int | None
    _response: ClientResponse
    _max_bytes: int

    async def iter_chunks(self) -> AsyncIterator[bytes]:
        """Yield the file in chunks, enforcing the size limit while streaming."""
        received = 0
        try:
            async for chunk in self._response.content.iter_chunked(CHUNK_SIZE):
                received += len(chunk)
                if received > self._max_bytes:
                    raise PaperlessFileTooLargeError("Document file exceeds the size limit")
                yield chunk
        except (ClientError, TimeoutError) as err:
            raise PaperlessConnectionError(
                f"Reading the document file failed ({type(err).__name__})"
            ) from None


class PaperlessClient:
    """Read-only Paperless-ngx API client."""

    def __init__(self, session: ClientSession, url: str, token: str) -> None:
        """Initialize the client.

        Args:
            session: The aiohttp session (Home Assistant's shared session in practice).
            url: Base URL of Paperless, e.g. ``http://paperless.local:8000`` or
                ``https://example.org/paperless``.
            token: API token of the (view-only) Paperless user.
        """
        base = URL(url.strip().rstrip("/"))
        if base.scheme not in ("http", "https") or not base.host:
            raise ValueError("The Paperless URL must be an http(s) URL with a host")
        if base.query_string or base.fragment:
            raise ValueError("The Paperless URL must not contain a query or fragment")
        token = token.strip()
        if not token:
            raise ValueError("The API token must not be empty")
        self._session = session
        self._base = base
        self._headers = {
            "Authorization": f"Token {token}",
            "Accept": f"application/json; version={API_VERSION}",
        }
        self.server_version: str | None = None

    def __repr__(self) -> str:
        """Return a representation without the token."""
        return f"<PaperlessClient {self._base}>"

    @property
    def base_url(self) -> str:
        """Return the normalized base URL."""
        return str(self._base)

    # ---- Public API -------------------------------------------------------------------------

    async def async_get_user(self) -> PaperlessUser:
        """Return the user the token belongs to (needs the ``view_uisettings`` permission).

        Also validates the token, the connection and the API version.
        """
        data = await self._get_json("ui_settings/")
        try:
            user = data["user"]
            return PaperlessUser(
                id=int(user["id"]),
                username=str(user["username"]),
                is_staff=bool(user.get("is_staff", False)),
                is_superuser=bool(user.get("is_superuser", False)),
                permissions=frozenset(str(perm) for perm in data.get("permissions", [])),
            )
        except KeyError, TypeError, ValueError:
            raise PaperlessResponseError("Unexpected user settings response") from None

    async def async_get_tags(self) -> list[PaperlessObject]:
        """Return all tags the user can see."""
        return [_parse_object(raw) for raw in await self._get_all("tags/")]

    async def async_get_document_types(self) -> list[PaperlessObject]:
        """Return all document types the user can see."""
        return [_parse_object(raw) for raw in await self._get_all("document_types/")]

    async def async_get_correspondents(self) -> list[PaperlessObject]:
        """Return all correspondents the user can see."""
        return [_parse_object(raw) for raw in await self._get_all("correspondents/")]

    async def async_get_custom_fields(self) -> list[PaperlessCustomField]:
        """Return all custom field definitions."""
        return [_parse_custom_field(raw) for raw in await self._get_all("custom_fields/")]

    async def async_get_documents(
        self,
        *,
        access_tag_id: int,
        document_type_ids: Collection[int] | None = None,
    ) -> list[PaperlessDocument]:
        """Return the metadata of all documents with the access tag, newest first.

        Args:
            access_tag_id: Only documents with this tag are returned.
            document_type_ids: Restrict to these document types. ``None`` means all types; an
                empty collection returns nothing without a request.
        """
        if document_type_ids is not None and not document_type_ids:
            return []
        params = _scope_params(access_tag_id, document_type_ids)
        params |= {"fields": DOCUMENT_FIELDS, "ordering": "-created"}
        documents = [_parse_document(raw) for raw in await self._get_all("documents/", params)]
        return _in_scope(documents, access_tag_id, document_type_ids)

    async def async_search(  # noqa: PLR0913 (keyword-only filters)
        self,
        text: str | None,
        *,
        access_tag_id: int,
        document_type_ids: Collection[int] | None = None,
        correspondent_ids: Collection[int] | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> PaperlessSearchResult:
        """Search documents with the access tag, newest first.

        Args:
            text: Full-text search (title and content, whole words). Empty or ``None`` lists
                the matching documents without a text search.
            access_tag_id: Only documents with this tag are returned.
            document_type_ids: Restrict to these document types (``None`` = all, empty = none).
            correspondent_ids: Restrict to these correspondents (``None`` or empty = all).
            created_from: Earliest creation date (inclusive).
            created_to: Latest creation date (inclusive).
            page: Page number, starting at 1.
            page_size: Results per page (1 to 100).
        """
        if page < 1 or not 1 <= page_size <= PAGE_SIZE:
            raise ValueError("Invalid page or page size")
        if document_type_ids is not None and not document_type_ids:
            return PaperlessSearchResult(count=0, hits=[])
        params = _scope_params(access_tag_id, document_type_ids)
        if text := (text or "").strip():
            params["text"] = text
        if correspondent_ids:
            params["correspondent__id__in"] = _id_list(correspondent_ids)
        if created_from is not None:
            params["created__gte"] = created_from.isoformat()
        if created_to is not None:
            params["created__lte"] = created_to.isoformat()
        params |= {
            "fields": DOCUMENT_FIELDS,
            "ordering": "-created",
            "page": str(page),
            "page_size": str(page_size),
        }
        data = await self._get_json("documents/", params)
        try:
            count = int(data["count"])
            results = data["results"]
            hits = [_parse_hit(raw) for raw in results]
        except KeyError, TypeError, ValueError:
            raise PaperlessResponseError("Unexpected search response") from None
        documents = _in_scope([hit.document for hit in hits], access_tag_id, document_type_ids)
        allowed = {doc.id for doc in documents}
        return PaperlessSearchResult(
            count=count, hits=[hit for hit in hits if hit.document.id in allowed]
        )

    async def async_get_document(self, document_id: int) -> PaperlessDocument:
        """Return the metadata of one document.

        The caller must check the access tag and document type before using the result.
        """
        data = await self._get_json(f"documents/{int(document_id)}/", {"fields": DOCUMENT_FIELDS})
        return _parse_document(data)

    @asynccontextmanager
    async def async_open_file(
        self,
        document_id: int,
        kind: FileKind,
        *,
        max_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ) -> AsyncIterator[PaperlessFile]:
        """Open a document file for streaming.

        The caller must check the access tag and document type of the document first.

        Raises:
            PaperlessFileTooLargeError: When ``Content-Length`` exceeds ``max_bytes`` (also
                raised by ``PaperlessFile.iter_chunks`` when the body turns out larger).
        """
        path = f"documents/{int(document_id)}/{FileKind(kind).value}/"
        async with self._open(path, request_timeout=FILE_TIMEOUT) as response:
            content_type = (
                response.headers.get("Content-Type", "application/octet-stream")
                .split(";")[0]
                .strip()
                .lower()
            )
            length_header = response.headers.get("Content-Length")
            content_length = (
                int(length_header) if length_header and length_header.isdigit() else None
            )
            if content_length is not None and content_length > max_bytes:
                raise PaperlessFileTooLargeError("Document file exceeds the size limit")
            yield PaperlessFile(
                content_type=content_type,
                content_length=content_length,
                _response=response,
                _max_bytes=max_bytes,
            )

    # ---- Internals --------------------------------------------------------------------------

    @asynccontextmanager
    async def _open(
        self,
        path: str,
        params: Mapping[str, str] | None = None,
        *,
        request_timeout: ClientTimeout = REQUEST_TIMEOUT,
    ) -> AsyncIterator[ClientResponse]:
        """Send a GET request to ``/api/<path>`` and yield the successful response."""
        url = URL(f"{self._base}/api/{path}")
        try:
            async with self._session.get(
                url,
                params=params,
                headers=self._headers,
                timeout=request_timeout,
                allow_redirects=False,
            ) as response:
                self._remember_version(response)
                _check_status(response.status, path)
                yield response
        except (ClientError, TimeoutError) as err:
            # Not chained: aiohttp errors can carry request details.
            raise PaperlessConnectionError(
                f"Cannot communicate with Paperless ({type(err).__name__})"
            ) from None

    async def _get_json(self, path: str, params: Mapping[str, str] | None = None) -> Any:
        """Return the decoded JSON object of a GET request."""
        async with self._open(path, params) as response:
            try:
                data = await response.json(content_type=None)
            except ValueError:
                raise PaperlessResponseError(f"Invalid JSON from /api/{path}") from None
        if not isinstance(data, dict):
            raise PaperlessResponseError(f"Unexpected response from /api/{path}")
        return data

    async def _get_all(
        self, path: str, params: Mapping[str, str] | None = None
    ) -> list[dict[str, Any]]:
        """Return the results of all pages of a list endpoint."""
        results: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            data = await self._get_json(
                path, {**(params or {}), "page": str(page), "page_size": str(PAGE_SIZE)}
            )
            page_results = data.get("results")
            if not isinstance(page_results, list) or not all(
                isinstance(item, dict) for item in page_results
            ):
                raise PaperlessResponseError(f"Unexpected list response from /api/{path}")
            results.extend(page_results)
            if not data.get("next") or not page_results:
                return results
        raise PaperlessResponseError(f"Too many pages from /api/{path}")

    def _remember_version(self, response: ClientResponse) -> None:
        """Store the Paperless version reported by the server."""
        if version := response.headers.get("X-Version"):
            self.server_version = version


def _check_status(status: int, path: str) -> None:
    """Raise the matching exception for an unsuccessful HTTP status."""
    if 200 <= status < 300:
        return
    endpoint = f"/api/{path}"
    if 300 <= status < 400:
        raise PaperlessConnectionError(
            f"Paperless redirected {endpoint} (HTTP {status}); configure the final URL"
        )
    if status == 401:
        raise PaperlessAuthError("The Paperless API token was rejected")
    if status == 403:
        raise PaperlessPermissionError(f"The Paperless user may not access {endpoint}")
    if status == 404:
        raise PaperlessNotFoundError(f"Not found: {endpoint}")
    if status == 406:
        raise PaperlessUnsupportedVersionError(
            f"Paperless does not support API version {API_VERSION}; "
            f"Paperless-ngx {MIN_PAPERLESS_VERSION} or newer is required"
        )
    if status >= 500:
        raise PaperlessConnectionError(f"Paperless server error (HTTP {status}) on {endpoint}")
    raise PaperlessResponseError(f"Unexpected HTTP {status} from {endpoint}")


def _id_list(ids: Collection[int]) -> str:
    """Return ids as a comma-separated query value."""
    return ",".join(str(int(item)) for item in sorted(ids))


def _scope_params(access_tag_id: int, document_type_ids: Collection[int] | None) -> dict[str, str]:
    """Return the query parameters that restrict a listing to the allowed documents."""
    params = {"tags__id__all": str(int(access_tag_id))}
    if document_type_ids is not None:
        params["document_type__id__in"] = _id_list(document_type_ids)
    return params


def _in_scope(
    documents: list[PaperlessDocument],
    access_tag_id: int,
    document_type_ids: Collection[int] | None,
) -> list[PaperlessDocument]:
    """Drop documents outside the requested scope (second check after the server filter)."""
    allowed = [
        doc
        for doc in documents
        if access_tag_id in doc.tags
        and (document_type_ids is None or doc.document_type in document_type_ids)
    ]
    if len(allowed) != len(documents):
        _LOGGER.warning(
            "Paperless returned %d document(s) outside the requested scope; they were dropped",
            len(documents) - len(allowed),
        )
    return allowed


def _parse_object(raw: dict[str, Any]) -> PaperlessObject:
    """Parse a tag, document type or correspondent."""
    try:
        return PaperlessObject(id=int(raw["id"]), name=str(raw["name"]))
    except KeyError, TypeError, ValueError:
        raise PaperlessResponseError("Unexpected object in Paperless response") from None


def _parse_custom_field(raw: dict[str, Any]) -> PaperlessCustomField:
    """Parse a custom field definition."""
    try:
        return PaperlessCustomField(
            id=int(raw["id"]), name=str(raw["name"]), data_type=str(raw["data_type"])
        )
    except KeyError, TypeError, ValueError:
        raise PaperlessResponseError("Unexpected custom field in Paperless response") from None


def _optional_id(value: Any) -> int | None:
    """Return an optional object id."""
    return None if value is None else int(value)


def _parse_date(value: Any) -> date | None:
    """Parse ``YYYY-MM-DD`` (API v9+); tolerate a datetime string or a missing value."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_document(raw: Any) -> PaperlessDocument:
    """Parse document metadata."""
    try:
        return PaperlessDocument(
            id=int(raw["id"]),
            title=str(raw["title"]),
            document_type=_optional_id(raw.get("document_type")),
            correspondent=_optional_id(raw.get("correspondent")),
            created=_parse_date(raw.get("created")),
            tags=frozenset(int(tag) for tag in raw.get("tags") or []),
            custom_fields={
                int(item["field"]): item.get("value") for item in raw.get("custom_fields") or []
            },
            mime_type=str(raw["mime_type"]) if raw.get("mime_type") else None,
        )
    except KeyError, TypeError, ValueError, AttributeError:
        raise PaperlessResponseError("Unexpected document in Paperless response") from None


def _parse_hit(raw: Any) -> PaperlessSearchHit:
    """Parse a search result (document plus optional ``__search_hit__``)."""
    document = _parse_document(raw)
    hit = raw.get("__search_hit__")
    if not isinstance(hit, dict):
        hit = {}
    score = hit.get("score")
    highlights = hit.get("highlights")
    return PaperlessSearchHit(
        document=document,
        score=float(score) if isinstance(score, int | float) else None,
        highlights=highlights if isinstance(highlights, str) else None,
    )
