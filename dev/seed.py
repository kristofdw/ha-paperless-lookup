"""Seed the dev Paperless-ngx with SYNTHETIC data for Paperless Lookup.

Standard library only. Idempotent: existing objects (matched by name/title) are reused.

Creates:
- a view-only user ``ha-lookup`` and its API token (written to SEED_TOKEN_FILE, never printed),
- the access tag ``HA`` plus an unrelated tag,
- document types (Manual, Receipt, Invoice, Warranty, Bank statement),
- a string custom field ``HA model``,
- generated PDFs, including documents WITHOUT the ``HA`` tag for leak tests.

Environment: PAPERLESS_URL, PAPERLESS_ADMIN_USER, PAPERLESS_ADMIN_PASSWORD, SEED_TOKEN_FILE.
"""

from base64 import b64encode
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import secrets
import sys
import time
from typing import Any, cast
import urllib.error
from urllib.parse import quote
import urllib.request
import uuid

HA_USER = "ha-lookup"
ACCESS_TAG = "HA"
CUSTOM_FIELD = "HA model"
VIEW_PERMISSIONS = [
    "view_document",
    "view_tag",
    "view_documenttype",
    "view_correspondent",
    "view_customfield",
    "view_note",
]

TAGS = [ACCESS_TAG, "Finance"]
DOCUMENT_TYPES = ["Manual", "Receipt", "Invoice", "Warranty", "Bank statement"]
CORRESPONDENTS = [
    "IKEA",
    "Aqara",
    "Philips Hue",
    "Demo Electronics",
    "Example Hardware Store",
    "Sample Supermarket",
    "Fictional Bank",
]


@dataclass(frozen=True, slots=True)
class SeedDocument:
    """A synthetic document."""

    title: str
    document_type: str
    correspondent: str
    created: str
    lines: list[str]
    tags: list[str] = field(default_factory=lambda: [ACCESS_TAG])
    ha_model: str | None = None
    # Whether ha-lookup gets view permission on this object (False = owner only).
    shared: bool = True


DOCUMENTS = [
    SeedDocument(
        "TRADFRI remote control manual",
        "Manual",
        "IKEA",
        "2024-03-02",
        ["TRADFRI remote control E1524/E1810", "Pairing: press the pairing button 4 times."],
        ha_model="E1524/E1810",
    ),
    SeedDocument(
        "STYRBAR remote manual",
        "Manual",
        "IKEA",
        "2024-05-10",
        ["STYRBAR remote control E2001/E2002", "Reset: hold the back button for 10 seconds."],
        ha_model="E2001/E2002",
    ),
    SeedDocument(
        "Aqara motion and door sensor manual",
        "Manual",
        "Aqara",
        "2023-11-20",
        ["Covers RTCGQ11LM and MCCGQ11LM.", "Reset: hold the button for 5 seconds."],
        ha_model="RTCGQ11LM; MCCGQ11LM",
    ),
    SeedDocument(
        "Hue white ambiance bulb manual",
        "Manual",
        "Philips Hue",
        "2022-08-14",
        ["Model 9290022169", "Reset: switch on and off five times."],
        ha_model="9290022169",
    ),
    SeedDocument(
        "Vacuum cleaner receipt",
        "Receipt",
        "Demo Electronics",
        "2025-06-01",
        ["Demo Electronics - receipt 0001", "Vacuum cleaner X100   EUR 199.00"],
    ),
    SeedDocument(
        "Paint and brushes receipt",
        "Receipt",
        "Example Hardware Store",
        "2025-09-12",
        ["Example Hardware Store - receipt 0042", "Wall paint white 5 l   EUR 39.95"],
    ),
    SeedDocument(
        "Groceries receipt",
        "Receipt",
        "Sample Supermarket",
        "2026-10-30",
        ["Sample Supermarket - receipt 7777", "Coffee beans 1 kg   EUR 12.49"],
    ),
    SeedDocument(
        "Washing machine invoice",
        "Invoice",
        "Demo Electronics",
        "2025-02-17",
        ["Demo Electronics - invoice 2025-017", "Washing machine W800   EUR 649.00"],
    ),
    SeedDocument(
        "Washing machine warranty",
        "Warranty",
        "Demo Electronics",
        "2025-02-17",
        ["Warranty certificate W800", "Valid until 2027-02-17"],
        ha_model="W800",
    ),
    # Leak-test documents: never visible through Home Assistant.
    SeedDocument(
        "Bank statement (no HA tag, shared)",
        "Bank statement",
        "Fictional Bank",
        "2026-09-30",
        ["Fictional Bank - statement 09/2026", "LEAKTEST-SHARED-NO-TAG"],
        tags=["Finance"],
    ),
    SeedDocument(
        "Bank statement (no HA tag, not shared)",
        "Bank statement",
        "Fictional Bank",
        "2026-08-31",
        ["Fictional Bank - statement 08/2026", "LEAKTEST-PRIVATE-NO-TAG"],
        tags=["Finance"],
        shared=False,
    ),
    SeedDocument(
        "Old manual (no HA tag)",
        "Manual",
        "IKEA",
        "2019-01-05",
        ["An old manual that was not released to Home Assistant.", "LEAKTEST-MANUAL-NO-TAG"],
        tags=[],
        ha_model="E1524/E1810",
    ),
]


def make_pdf(lines: list[str]) -> bytes:
    """Return a minimal one-page PDF with the given ASCII text lines."""

    def escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    text_ops = " T* ".join(f"({escape(line)}) Tj" for line in lines)
    stream = f"BT /F1 14 Tf 50 780 Td 20 TL {text_ops} ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


class Paperless:
    """Tiny Paperless-ngx REST client (admin, basic auth)."""

    def __init__(self, url: str, user: str, password: str) -> None:
        """Store the connection settings."""
        if not url.startswith(("http://", "https://")):
            raise ValueError("PAPERLESS_URL must be http(s)")
        self.url = url.rstrip("/")
        credentials = b64encode(f"{user}:{password}".encode()).decode()
        self._auth = f"Basic {credentials}"

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        raw: bytes | None = None,
        content_type: str = "application/json",
        auth: str | None = None,
    ) -> Any:
        """Send a request and return the decoded JSON response."""
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(f"{self.url}{path}", data=data, method=method)
        req.add_header("Authorization", auth or self._auth)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = resp.read()
        except urllib.error.HTTPError as err:
            detail = err.read().decode(errors="replace")[:300]
            raise RuntimeError(f"{method} {path} -> HTTP {err.code}: {detail}") from None
        return json.loads(payload) if payload else None

    def wait_until_ready(self, timeout: float = 300) -> None:
        """Wait until the API answers."""
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.request("GET", "/api/ui_settings/")
            except (OSError, RuntimeError) as err:
                if time.monotonic() > deadline:
                    raise RuntimeError("Paperless did not become ready") from err
                time.sleep(3)
            else:
                return

    def find(self, endpoint: str, name_field: str, name: str) -> dict[str, Any] | None:
        """Return the object with exactly this name, if any."""
        result = self.request("GET", f"/api/{endpoint}/?{name_field}__iexact={quote(name)}")
        matches = [obj for obj in result["results"] if obj[name_field] == name]
        return cast(dict[str, Any], matches[0]) if matches else None

    def ensure(self, endpoint: str, name: str, extra: dict[str, Any]) -> int:
        """Return the id of the named object, creating it when missing."""
        existing = self.find(endpoint, "name", name)
        if existing is not None:
            return int(existing["id"])
        created = self.request("POST", f"/api/{endpoint}/", {"name": name, **extra})
        return int(created["id"])


def view_permissions(user_id: int | None) -> dict[str, Any]:
    """Return a set_permissions payload granting view to the given user."""
    users = [user_id] if user_id is not None else []
    return {
        "view": {"users": users, "groups": []},
        "change": {"users": [], "groups": []},
    }


def ensure_ha_user(api: Paperless) -> tuple[int, str]:
    """Create or update the view-only HA user and return (id, token)."""
    password = secrets.token_urlsafe(24)
    fields = {
        "password": password,
        "is_staff": False,
        "is_superuser": False,
        "user_permissions": VIEW_PERMISSIONS,
    }
    existing = api.find("users", "username", HA_USER)
    if existing is None:
        user = api.request("POST", "/api/users/", {"username": HA_USER, **fields})
    else:
        user = api.request("PATCH", f"/api/users/{existing['id']}/", fields)
    response = api.request(
        "POST",
        "/api/token/",
        raw=f"username={quote(HA_USER)}&password={quote(password)}".encode(),
        content_type="application/x-www-form-urlencoded",
    )
    return int(user["id"]), str(response["token"])


def upload(api: Paperless, doc: SeedDocument, ids: dict[str, int]) -> int:
    """Upload a document and return its id once Paperless has consumed it."""
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )

    add_field("title", doc.title)
    add_field("created", doc.created)
    add_field("document_type", str(ids[f"type:{doc.document_type}"]))
    add_field("correspondent", str(ids[f"correspondent:{doc.correspondent}"]))
    for tag in doc.tags:
        add_field("tags", str(ids[f"tag:{tag}"]))
    filename = doc.title.lower().replace(" ", "-").replace("(", "").replace(")", "") + ".pdf"
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="document"; '
        f'filename="{filename}"\r\nContent-Type: application/pdf\r\n\r\n'.encode()
        + make_pdf([doc.title, *doc.lines])
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    task_id = api.request(
        "POST",
        "/api/documents/post_document/",
        raw=b"".join(parts),
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        tasks = api.request("GET", f"/api/tasks/?task_id={task_id}")
        if isinstance(tasks, dict):  # paginated in newer API versions
            tasks = tasks["results"]
        status = str(tasks[0]["status"]).lower() if tasks else ""
        if status == "success":
            task = tasks[0]
            if "related_document_ids" in task:  # Paperless 3.x (API v10)
                return int(task["related_document_ids"][0])
            return int(task["related_document"])
        if status == "failure":
            raise RuntimeError(f"Consuming {doc.title!r} failed")
        time.sleep(2)
    raise RuntimeError(f"Timed out consuming {doc.title!r}")


def main() -> int:
    """Seed the dev Paperless."""
    api = Paperless(
        os.environ.get("PAPERLESS_URL", "http://localhost:8011"),
        os.environ.get("PAPERLESS_ADMIN_USER", "admin"),
        os.environ["PAPERLESS_ADMIN_PASSWORD"],
    )
    print(f"Waiting for Paperless at {api.url} ...")
    api.wait_until_ready()

    ha_user_id, token = ensure_ha_user(api)
    shared = {"set_permissions": view_permissions(ha_user_id)}

    ids: dict[str, int] = {}
    for tag in TAGS:
        ids[f"tag:{tag}"] = api.ensure(
            "tags", tag, {"matching_algorithm": 0, "is_inbox_tag": False, **shared}
        )
    for doc_type in DOCUMENT_TYPES:
        ids[f"type:{doc_type}"] = api.ensure(
            "document_types", doc_type, {"matching_algorithm": 0, **shared}
        )
    for correspondent in CORRESPONDENTS:
        ids[f"correspondent:{correspondent}"] = api.ensure(
            "correspondents", correspondent, {"matching_algorithm": 0, **shared}
        )
    field_id = api.ensure("custom_fields", CUSTOM_FIELD, {"data_type": "string"})

    created = 0
    for doc in DOCUMENTS:
        existing = api.find("documents", "title", doc.title)
        if existing is None:
            doc_id = upload(api, doc, ids)
            created += 1
        else:
            doc_id = int(existing["id"])
        patch: dict[str, Any] = {
            "set_permissions": view_permissions(ha_user_id if doc.shared else None)
        }
        patch["custom_fields"] = (
            [{"field": field_id, "value": doc.ha_model}] if doc.ha_model is not None else []
        )
        api.request("PATCH", f"/api/documents/{doc_id}/", patch)

    token_file = Path(os.environ.get("SEED_TOKEN_FILE", "dev/data/ha-lookup.token"))
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(token + "\n", encoding="utf-8")
    token_file.chmod(0o600)

    with_tag = sum(ACCESS_TAG in doc.tags for doc in DOCUMENTS)
    print(
        f"Done: {len(DOCUMENTS)} documents ({created} new), {with_tag} with tag {ACCESS_TAG!r}, "
        f"{len(DOCUMENTS) - with_tag} without (leak tests)."
    )
    print(f"API token of {HA_USER!r} written to dev/data/{token_file.name} (git-ignored).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
