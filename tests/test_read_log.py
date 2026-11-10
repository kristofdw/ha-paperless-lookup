"""Tests for the read log: logbook events for previews and downloads, per category and user."""

from datetime import timedelta
from http import HTTPStatus
import json
from pathlib import Path
from time import monotonic
from typing import Any

from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.translation import async_get_translations
import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser, async_capture_events
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator

from custom_components.paperless_lookup.const import CONF_FOLLOW_READS, DOMAIN
from custom_components.paperless_lookup.logbook import (
    FALLBACK_TEXTS,
    Describer,
    async_describe_events,
)
from custom_components.paperless_lookup.read_log import EVENT_DOCUMENT_OPENED, REPEAT_SECONDS

from .conftest import TEST_URL
from .security import (
    INVOICE,
    INVOICE_DOC,
    MANUAL,
    RECEIPT,
    RECEIPT_DOC,
    TRADFRI_DOC,
    Users,
    async_access_token,
    async_setup_entry,
    async_setup_users,
)

PDF = b"%PDF-1.4 synthetic test document\n"
STRINGS = Path(__file__).parents[1] / "custom_components" / "paperless_lookup" / "strings.json"


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
    """Set up the entry: the reader's receipts and the admin's invoices are logged."""
    await async_setup_entry(
        hass,
        aioclient_mock,
        mock_config_entry,
        users,
        **{CONF_FOLLOW_READS: {users.reader.id: [RECEIPT], users.admin.id: [INVOICE]}},
    )
    for doc_id, document_type in (
        (RECEIPT_DOC, RECEIPT),
        (INVOICE_DOC, INVOICE),
        (TRADFRI_DOC, MANUAL),
    ):
        aioclient_mock.get(
            f"{TEST_URL}/api/documents/{doc_id}/",
            json={"id": doc_id, "title": "x", "document_type": document_type, "tags": [1]},
        )
        for kind, content_type in (
            ("preview", "application/pdf"),
            ("download", "application/pdf"),
            ("thumb", "image/webp"),
        ):
            aioclient_mock.get(
                f"{TEST_URL}/api/documents/{doc_id}/{kind}/",
                content=PDF,
                headers={"Content-Type": content_type},
            )
    return mock_config_entry


async def open_file(
    hass: HomeAssistant, client: Any, user: Any, doc_id: int, kind: str = "preview"
) -> None:
    """Open a document file as a user and check that it was served."""
    refresh_token_id, _ = await async_access_token(hass, user)
    path = async_sign_path(
        hass,
        f"/api/paperless_lookup/document/{doc_id}/{kind}",
        timedelta(seconds=60),
        refresh_token_id=refresh_token_id,
    )
    response = await client.get(path)
    assert response.status == HTTPStatus.OK
    await response.read()


async def test_logged_per_category_and_user(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    setup: MockConfigEntry,
    users: Users,
) -> None:
    """Test that only the chosen users in the chosen categories are logged."""
    events = async_capture_events(hass, EVENT_DOCUMENT_OPENED)
    client = await hass_client_no_auth()

    await open_file(hass, client, users.reader, RECEIPT_DOC)
    await open_file(hass, client, users.reader, TRADFRI_DOC)  # Manuals are not followed.
    await open_file(hass, client, users.admin, RECEIPT_DOC)  # The admin's receipts are not.
    await open_file(hass, client, users.admin, INVOICE_DOC, "download")
    await hass.async_block_till_done()

    device = dr.async_get(hass).async_get(setup.runtime_data.device_id)
    assert isinstance(device, dr.DeviceEntry)
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert (DOMAIN, setup.entry_id) in device.identifiers
    assert [event.data for event in events] == [
        {
            "device_id": device.id,
            "document_id": RECEIPT_DOC,
            "document_type": RECEIPT,
            "category": "Receipt",
            "kind": "preview",
            "user_id": users.reader.id,
            "user_name": users.reader.name,
        },
        {
            "device_id": device.id,
            "document_id": INVOICE_DOC,
            "document_type": INVOICE,
            "category": "Invoice",
            "kind": "download",
            "user_id": users.admin.id,
            "user_name": users.admin.name,
        },
    ]
    # Never a title: the logbook is stored in the recorder database.
    assert all("title" not in event.data for event in events)


async def test_thumbnails_and_repeats_not_logged(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    setup: MockConfigEntry,
    users: Users,
) -> None:
    """Test that thumbnails are skipped and a repeated open within a minute is logged once."""
    events = async_capture_events(hass, EVENT_DOCUMENT_OPENED)
    client = await hass_client_no_auth()

    await open_file(hass, client, users.reader, RECEIPT_DOC, "thumb")
    await open_file(hass, client, users.reader, RECEIPT_DOC)
    await open_file(hass, client, users.reader, RECEIPT_DOC)
    await open_file(hass, client, users.reader, RECEIPT_DOC, "download")
    await hass.async_block_till_done()
    assert [event.data["kind"] for event in events] == ["preview", "download"]

    # Older than the repeat window: logged again, and the old entries are pruned.
    seen = setup.runtime_data.read_log_seen
    for key in seen:
        seen[key] = monotonic() - REPEAT_SECONDS
    await open_file(hass, client, users.reader, RECEIPT_DOC)
    await hass.async_block_till_done()
    assert [event.data["kind"] for event in events] == ["preview", "download", "preview"]
    assert len(seen) == 1


async def test_nothing_logged_by_default(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    users: Users,
) -> None:
    """Test that without the option nothing is logged."""
    await async_setup_entry(hass, aioclient_mock, mock_config_entry, users)
    aioclient_mock.get(
        f"{TEST_URL}/api/documents/{RECEIPT_DOC}/",
        json={"id": RECEIPT_DOC, "title": "x", "document_type": RECEIPT, "tags": [1]},
    )
    aioclient_mock.get(
        f"{TEST_URL}/api/documents/{RECEIPT_DOC}/preview/",
        content=PDF,
        headers={"Content-Type": "application/pdf"},
    )
    events = async_capture_events(hass, EVENT_DOCUMENT_OPENED)
    client = await hass_client_no_auth()

    await open_file(hass, client, users.reader, RECEIPT_DOC)
    await hass.async_block_till_done()

    assert events == []


def _describer(hass: HomeAssistant) -> Describer:
    """Return the logbook describer of the read event."""
    found: dict[str, Describer] = {}

    def collect(domain: str, event_type: str, describe: Describer) -> None:
        assert domain == DOMAIN
        found[event_type] = describe

    async_describe_events(hass, collect)
    return found[EVENT_DOCUMENT_OPENED]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            {"document_id": 5, "category": "Receipt", "kind": "preview", "user_name": "Alex"},
            {"name": "Alex", "message": "opened Paperless document 5 (Receipt)"},
        ),
        (
            {"document_id": 8, "category": "Invoice", "kind": "download", "user_name": "Sam"},
            {"name": "Sam", "message": "downloaded Paperless document 8 (Invoice)"},
        ),
        (
            {"document_id": 9, "category": None, "kind": "preview", "user_name": None},
            {"name": "Unknown user", "message": "opened Paperless document 9"},
        ),
    ],
)
async def test_logbook_description(
    hass: HomeAssistant, data: dict[str, Any], expected: dict[str, str]
) -> None:
    """Test the logbook text: user, verb, document number and category, no title."""
    describe = _describer(hass)

    assert describe(Event(EVENT_DOCUMENT_OPENED, data)) == expected


async def test_logbook_description_translated(hass: HomeAssistant) -> None:
    """Test that the logbook text follows the language of Home Assistant."""
    hass.config.language = "nl"
    await async_get_translations(hass, "nl", "common", {DOMAIN})
    describe = _describer(hass)

    opened = {"document_id": 5, "category": "Receipt", "kind": "preview", "user_name": None}
    downloaded = {"document_id": 8, "kind": "download", "user_name": "Sam"}

    assert describe(Event(EVENT_DOCUMENT_OPENED, opened)) == {
        "name": "Onbekende gebruiker",
        "message": "opende Paperless-document 5 (Receipt)",
    }
    assert describe(Event(EVENT_DOCUMENT_OPENED, downloaded))["message"] == (
        "downloadde Paperless-document 8"
    )


def test_fallback_texts_match_strings() -> None:
    """Test that the texts used before translations load are the English strings."""
    strings = json.loads(STRINGS.read_text(encoding="utf-8"))

    assert strings["common"] == FALLBACK_TEXTS
