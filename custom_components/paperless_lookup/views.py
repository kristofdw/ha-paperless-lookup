"""HTTP view that streams document files from Paperless to the browser.

``<img>`` and ``<iframe>`` cannot send an Authorization header, so the frontend asks for a
short-lived signed path over the websocket API (``sign_documents``). Home Assistant's auth
middleware validates the signature and sets the user; this view checks that user's access again.

Policy:
- Anything the user may not see, or that is no longer released in Paperless, is a 404.
- The document is looked up live in Paperless before streaming (access tag and category), so a
  tag removed since the last index refresh takes effect immediately.
- Only whitelisted content types are passed on, with ``nosniff`` and a neutral file name.
- Files are streamed with a size limit; nothing is stored in Home Assistant.
"""

from http import HTTPStatus
import logging
from typing import Final

from aiohttp import web
from homeassistant.components.http import KEY_HASS_USER, HomeAssistantView
from homeassistant.core import HomeAssistant

from .access import (
    DocumentNotFoundError,
    NotLoadedError,
    async_get_entry,
    get_document,
    user_access,
)
from .api import FileKind, PaperlessError, PaperlessFileTooLargeError, PaperlessNotFoundError
from .read_log import async_log_read

_LOGGER = logging.getLogger(__name__)

MAX_FILE_BYTES: Final = {
    FileKind.THUMB: 5 * 1024 * 1024,
    FileKind.PREVIEW: 100 * 1024 * 1024,
    FileKind.DOWNLOAD: 100 * 1024 * 1024,
}
_DOCUMENT_TYPES: Final = frozenset(
    {
        "application/pdf",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/tiff",
        "image/webp",
        "text/plain",
    }
)
ALLOWED_CONTENT_TYPES: Final = {
    FileKind.THUMB: frozenset({"image/jpeg", "image/png", "image/webp"}),
    FileKind.PREVIEW: _DOCUMENT_TYPES,
    FileKind.DOWNLOAD: _DOCUMENT_TYPES,
}
_EXTENSIONS: Final = {
    "application/pdf": "pdf",
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/tiff": "tiff",
    "image/webp": "webp",
    "text/plain": "txt",
}


class PaperlessDocumentView(HomeAssistantView):
    """Stream the preview, thumbnail or download of a released document."""

    url = "/api/paperless_lookup/document/{document_id}/{kind}"
    name = "api:paperless_lookup:document"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the view."""
        self.hass = hass

    async def get(self, request: web.Request, document_id: str, kind: str) -> web.StreamResponse:
        """Stream a document file."""
        if not document_id.isdecimal() or kind not in FileKind:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        try:
            return await self._async_stream(request, int(document_id), FileKind(kind))
        except NotLoadedError, DocumentNotFoundError, PaperlessNotFoundError:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        except PaperlessFileTooLargeError:
            return web.Response(status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        except PaperlessError:
            return web.Response(status=HTTPStatus.BAD_GATEWAY)

    async def _async_stream(
        self, request: web.Request, doc_id: int, kind: FileKind
    ) -> web.StreamResponse:
        """Check access (index and live) and stream the file.

        Raises:
            DocumentNotFoundError: The user may not see the document (now).
        """
        entry = async_get_entry(self.hass)
        user = request[KEY_HASS_USER]
        access = user_access(entry, user)
        get_document(entry, access, doc_id)
        coordinator = entry.runtime_data.coordinator
        client = coordinator.client
        live = await client.async_get_document(doc_id)
        if (
            coordinator.access_tag is None
            or coordinator.access_tag not in live.tags
            or not access.can_view(live.document_type)
        ):
            raise DocumentNotFoundError
        async with client.async_open_file(doc_id, kind, max_bytes=MAX_FILE_BYTES[kind]) as file:
            if file.content_type not in ALLOWED_CONTENT_TYPES[kind]:
                return web.Response(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            async_log_read(self.hass, entry, user, live, kind)
            response = web.StreamResponse(
                headers={
                    "Content-Type": file.content_type,
                    "Content-Disposition": _disposition(doc_id, kind, file.content_type),
                    "X-Content-Type-Options": "nosniff",
                    "Cache-Control": "private, max-age=300",
                }
            )
            if file.content_length is not None:
                response.content_length = file.content_length
            await response.prepare(request)
            try:
                async for chunk in file.iter_chunks():
                    await response.write(chunk)
            except PaperlessError:
                # Headers are sent already: end the connection instead of a partial file.
                _LOGGER.warning("Streaming document file from Paperless failed")
                if request.transport is not None:  # pragma: no branch
                    request.transport.close()
                return response
            await response.write_eof()
            return response


def _disposition(document_id: int, kind: FileKind, content_type: str) -> str:
    """Return a Content-Disposition with a neutral name (no title, no header injection)."""
    filename = f"document-{document_id}.{_EXTENSIONS.get(content_type, 'bin')}"
    disposition = "attachment" if kind is FileKind.DOWNLOAD else "inline"
    return f'{disposition}; filename="{filename}"'
