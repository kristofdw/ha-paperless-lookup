"""Capture JSON test fixtures from the DEV Paperless-ngx (synthetic data only).

Standard library only. Run it after seeding (see dev/README.md):

    python -I dev/capture_fixtures.py

It sends the same requests as ``PaperlessClient`` with the token of the view-only ``ha-lookup``
user and writes the responses to ``tests/fixtures/``. Pagination links are rewritten to the fake
test URL. The token is never printed, and the script refuses to write a fixture that contains it.

Environment: PAPERLESS_URL (default http://localhost:8011), SEED_TOKEN_FILE
(default dev/data/ha-lookup.token).
"""

import json
import os
from pathlib import Path
import sys
from typing import Any
import urllib.error
from urllib.parse import urlencode
import urllib.request

API_VERSION = 10
TEST_URL = "http://paperless.test:8000"
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
DOCUMENT_FIELDS = "id,title,document_type,correspondent,created,tags,custom_fields,mime_type"

# Ids from the seed script: tag HA = 1, Invoice = 3, Warranty = 4.
REQUESTS: dict[str, tuple[str, dict[str, str]]] = {
    "ui_settings": ("ui_settings/", {}),
    "tags": ("tags/", {"page": "1", "page_size": "100"}),
    "document_types": ("document_types/", {"page": "1", "page_size": "100"}),
    "correspondents": ("correspondents/", {"page": "1", "page_size": "100"}),
    "custom_fields": ("custom_fields/", {"page": "1", "page_size": "100"}),
    "documents_page_1": (
        "documents/",
        {
            "tags__id__all": "1",
            "fields": DOCUMENT_FIELDS,
            "ordering": "-created",
            "page": "1",
            "page_size": "5",
        },
    ),
    "documents_page_2": (
        "documents/",
        {
            "tags__id__all": "1",
            "fields": DOCUMENT_FIELDS,
            "ordering": "-created",
            "page": "2",
            "page_size": "5",
        },
    ),
    "search": (
        "documents/",
        {
            "text": "washing",
            "tags__id__all": "1",
            "document_type__id__in": "3,4",
            "fields": DOCUMENT_FIELDS,
            "ordering": "-created",
            "page": "1",
            "page_size": "25",
        },
    ),
    "document": ("documents/9/", {"fields": DOCUMENT_FIELDS}),
}


def fetch(base: str, token: str, path: str, params: dict[str, str]) -> Any:
    """Return the decoded JSON response of one API request."""
    query = f"?{urlencode(params)}" if params else ""
    req = urllib.request.Request(f"{base}/api/{path}{query}")
    req.add_header("Authorization", f"Token {token}")
    req.add_header("Accept", f"application/json; version={API_VERSION}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"GET /api/{path} -> HTTP {err.code}") from None


def main() -> int:
    """Capture all fixtures."""
    base = os.environ.get("PAPERLESS_URL", "http://localhost:8011").rstrip("/")
    if not base.startswith(("http://localhost", "http://127.0.0.1", "http://paperless:")):
        print("Refusing to capture from anything but the local dev Paperless.")
        return 1
    token_file = Path(os.environ.get("SEED_TOKEN_FILE", "dev/data/ha-lookup.token"))
    token = token_file.read_text(encoding="utf-8").strip()

    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, (path, params) in REQUESTS.items():
        text = json.dumps(fetch(base, token, path, params), indent=2, ensure_ascii=False)
        text = text.replace(base, TEST_URL)
        if token in text:
            raise RuntimeError(f"Fixture {name} contains the API token")
        (FIXTURES / f"{name}.json").write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"Wrote tests/fixtures/{name}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
