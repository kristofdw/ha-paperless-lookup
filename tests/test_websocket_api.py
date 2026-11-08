"""Tests for the websocket API: every command, allowed and denied."""

from dataclasses import replace
from http import HTTPStatus
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.paperless_lookup.const import CONF_ACCESS_TAG, CONF_ADMINS_ALWAYS
from custom_components.paperless_lookup.websocket_api import async_register, highlight_segments

from .conftest import TEST_URL, load_json_fixture, mock_paperless
from .security import (
    AQARA_DOC,
    INVOICE_DOC,
    MANUAL,
    RECEIPT,
    RECEIPT_DOC,
    TRADFRI_DOC,
    WARRANTY_DOC,
    Users,
    async_access_token,
    async_setup_entry,
    async_setup_users,
)

type Call = Any


@pytest.fixture
async def users(hass: HomeAssistant, hass_admin_user: MockUser) -> Users:
    """Return the test users."""
    return await async_setup_users(hass, hass_admin_user)


@pytest.fixture
def devices(hass: HomeAssistant) -> dict[str, str]:
    """Create a Zigbee2MQTT remote, a plug and a washer in an area."""
    mqtt_entry = MockConfigEntry(domain="mqtt")
    mqtt_entry.add_to_hass(hass)
    area = ar.async_get(hass).async_create("Kitchen")
    registry = dr.async_get(hass)

    def add(ident: str, **kwargs: Any) -> str:
        return registry.async_get_or_create(
            config_entry_id=mqtt_entry.entry_id, identifiers={("mqtt", ident)}, **kwargs
        ).id

    remote = add(
        "zigbee2mqtt_0x01",
        name="Remote",
        manufacturer="IKEA",
        model="TRADFRI remote control",
        model_id="E1524/E1810",
    )
    plug = add("zigbee2mqtt_0x02", name="Plug", model="Smart plug", model_id="PLUG-01")
    washer = add("washer", name="Washer", model="W800")
    for device_id in (remote, plug, washer):
        registry.async_update_device(device_id, area_id=area.id)
    return {"remote": remote, "plug": plug, "washer": washer, "area": area.id}


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


async def call(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, user: Any, **msg: Any
) -> dict[str, Any]:
    """Send one command as a user and return the response."""
    _, token = await async_access_token(hass, user)
    client = await hass_ws_client(hass, token)
    await client.send_json_auto_id(msg)
    response: dict[str, Any] = await client.receive_json()
    return response


def ids(documents: list[dict[str, Any]]) -> list[int]:
    """Return the document ids of a result."""
    return [doc["id"] for doc in documents]


async def test_not_loaded(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, users: Users
) -> None:
    """Test the error when the integration is not loaded (commands registered by a stub)."""
    async_register(hass)

    response = await call(hass, hass_ws_client, users.admin, type="paperless_lookup/access")

    assert response["error"]["code"] == "not_loaded"


@pytest.mark.usefixtures("setup")
async def test_access(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, users: Users
) -> None:
    """Test the access command per user."""
    admin = await call(hass, hass_ws_client, users.admin, type="paperless_lookup/access")
    reader = await call(hass, hass_ws_client, users.reader, type="paperless_lookup/access")
    nobody = await call(hass, hass_ws_client, users.nobody, type="paperless_lookup/access")

    assert admin["result"]["is_admin"] is True
    assert len(admin["result"]["categories"]) == 5
    assert reader["result"] == {
        "allowed": True,
        "is_admin": False,
        "categories": [{"id": MANUAL, "name": "Manual"}, {"id": RECEIPT, "name": "Receipt"}],
        "device_categories": [{"id": MANUAL, "name": "Manual"}],
        "zigbee2mqtt_fallback": True,
    }
    assert nobody["result"]["allowed"] is False
    assert nobody["result"]["categories"] == []


@pytest.mark.usefixtures("setup")
async def test_filters(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, users: Users
) -> None:
    """Test that filters only show categories and stores of visible documents."""
    guest = await call(hass, hass_ws_client, users.guest, type="paperless_lookup/filters")
    reader = await call(hass, hass_ws_client, users.reader, type="paperless_lookup/filters")
    nobody = await call(hass, hass_ws_client, users.nobody, type="paperless_lookup/filters")

    assert guest["result"] == {
        "categories": [{"id": MANUAL, "name": "Manual"}],
        "correspondents": [
            {"id": 2, "name": "Aqara", "categories": [MANUAL]},
            {"id": 1, "name": "IKEA", "categories": [MANUAL]},
            {"id": 3, "name": "Philips Hue", "categories": [MANUAL]},
        ],
        "date_min": "2022-08-14",
        "date_max": "2024-05-10",
    }
    reader_stores = {item["name"] for item in reader["result"]["correspondents"]}
    assert {"Sample Supermarket", "Demo Electronics"} <= reader_stores
    # Only categories the user may see are listed per store.
    demo = next(
        item for item in reader["result"]["correspondents"] if item["name"] == "Demo Electronics"
    )
    assert demo["categories"] == [RECEIPT]
    assert nobody["result"] == {
        "categories": [],
        "correspondents": [],
        "date_min": None,
        "date_max": None,
    }


async def test_filters_skip_documents_without_store(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    setup: MockConfigEntry,
    users: Users,
) -> None:
    """Test that a store only listed through documents without one disappears."""
    documents = setup.runtime_data.coordinator.data.documents
    for doc_id in (TRADFRI_DOC, 2):  # the two IKEA manuals
        documents[doc_id] = replace(documents[doc_id], correspondent=None)

    response = await call(hass, hass_ws_client, users.guest, type="paperless_lookup/filters")

    assert "IKEA" not in {item["name"] for item in response["result"]["correspondents"]}


async def test_search(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup: MockConfigEntry,
    users: Users,
) -> None:
    """Test a search as admin: live in Paperless, with highlight segments."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{TEST_URL}/api/documents/", json=load_json_fixture("search"))

    response = await call(
        hass,
        hass_ws_client,
        users.admin,
        type="paperless_lookup/search",
        query="washing",
        correspondents=[4],
        date_from="2025-01-01",
        date_to="2025-12-31",
    )

    result = response["result"]
    assert result["count"] == 2
    assert set(ids(result["results"])) == {INVOICE_DOC, WARRANTY_DOC}
    warranty = next(doc for doc in result["results"] if doc["id"] == WARRANTY_DOC)
    assert warranty["category_name"] == "Warranty"
    assert warranty["correspondent_name"] == "Demo Electronics"
    assert warranty["highlights"][0] == {"text": "Washing", "match": True}
    assert "<" not in str(warranty["highlights"])
    query = dict(aioclient_mock.mock_calls[0][1].query)
    assert query["text"] == "washing"
    assert query["tags__id__all"] == "1"
    assert query["document_type__id__in"] == "1,2,3,4,5"
    assert query["correspondent__id__in"] == "4"
    assert query["created__gte"] == "2025-01-01"


async def test_search_refreshes_index_for_new_documents(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup: MockConfigEntry,
    users: Users,
) -> None:
    """Test that a result missing from the index (new in Paperless) refreshes the index."""
    new_doc = {
        "id": 20,
        "title": "Coffee machine receipt",
        "document_type": RECEIPT,
        "correspondent": 6,
        "created": "2026-11-07",
        "tags": [1],
        "custom_fields": [],
        "mime_type": "application/pdf",
    }
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{TEST_URL}/api/documents/",
        params={"text": "coffee"},
        json={"count": 1, "next": None, "results": [new_doc]},
    )
    documents = [
        *load_json_fixture("documents_page_1")["results"],
        *load_json_fixture("documents_page_2")["results"],
        new_doc,
    ]
    mock_paperless(
        aioclient_mock, documents={"count": len(documents), "next": None, "results": documents}
    )
    sign = {"type": "paperless_lookup/sign_documents", "document_ids": [20], "kind": "thumb"}
    before = await call(hass, hass_ws_client, users.reader, **sign)
    assert before["result"]["paths"] == {}

    response = await call(
        hass, hass_ws_client, users.reader, type="paperless_lookup/search", query="coffee"
    )

    assert ids(response["result"]["results"]) == [20]
    assert response["result"]["results"][0]["correspondent_name"] == "Sample Supermarket"
    after = await call(hass, hass_ws_client, users.reader, **sign)
    assert set(after["result"]["paths"]) == {"20"}


async def test_search_restricted_to_allowed_categories(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup: MockConfigEntry,
    users: Users,
) -> None:
    """Test that a user only searches (and gets) the allowed categories."""
    aioclient_mock.clear_requests()
    # The mocked server ignores the filters and returns an invoice and a warranty.
    aioclient_mock.get(f"{TEST_URL}/api/documents/", json=load_json_fixture("search"))

    response = await call(
        hass,
        hass_ws_client,
        users.reader,
        type="paperless_lookup/search",
        query="washing",
        categories=[RECEIPT, 3, 4],
    )

    assert response["result"]["results"] == []
    query = dict(aioclient_mock.mock_calls[0][1].query)
    assert query["document_type__id__in"] == str(RECEIPT)


@pytest.mark.parametrize(
    ("user", "msg", "options"),
    [
        ("nobody", {}, {}),
        ("guest", {"categories": [RECEIPT]}, {}),
        ("admin", {}, {CONF_ACCESS_TAG: None}),
        ("admin", {}, {CONF_ADMINS_ALWAYS: False}),
    ],
)
async def test_search_nothing_allowed(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    users: Users,
    user: str,
    msg: dict[str, Any],
    options: dict[str, Any],
) -> None:
    """Test that a search without allowed categories (or tag) never reaches Paperless."""
    await async_setup_entry(hass, aioclient_mock, mock_config_entry, users, **options)
    aioclient_mock.clear_requests()

    response = await call(
        hass, hass_ws_client, getattr(users, user), type="paperless_lookup/search", **msg
    )

    assert response["result"] == {"count": 0, "results": []}
    assert aioclient_mock.call_count == 0


async def test_search_errors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup: MockConfigEntry,
    users: Users,
) -> None:
    """Test a Paperless failure and invalid input."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{TEST_URL}/api/documents/", status=HTTPStatus.BAD_GATEWAY)

    failed = await call(hass, hass_ws_client, users.admin, type="paperless_lookup/search")
    too_long = await call(
        hass, hass_ws_client, users.admin, type="paperless_lookup/search", query="x" * 201
    )
    bad_date = await call(
        hass, hass_ws_client, users.admin, type="paperless_lookup/search", date_from="yesterday"
    )

    assert failed["error"]["code"] == "cannot_connect"
    assert TEST_URL not in failed["error"]["message"]
    assert too_long["error"]["code"] == "invalid_format"
    assert bad_date["error"]["code"] == "invalid_format"


@pytest.mark.usefixtures("setup")
async def test_device_documents(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    users: Users,
    devices: dict[str, str],
) -> None:
    """Test device documents per user, links of other categories and the Z2M fallback."""
    entry = hass.config_entries.async_entries("paperless_lookup")[0]
    await entry.runtime_data.store.async_link(devices["washer"], INVOICE_DOC)
    await entry.runtime_data.store.async_link(devices["washer"], RECEIPT_DOC)

    async def docs(user: Any, device: str) -> dict[str, Any]:
        response = await call(
            hass,
            hass_ws_client,
            user,
            type="paperless_lookup/device_documents",
            device_id=devices[device],
        )
        result: dict[str, Any] = response["result"]
        return result

    guest_remote = await docs(users.guest, "remote")
    assert ids(guest_remote["documents"]) == [TRADFRI_DOC]
    assert guest_remote["documents"][0]["models"] == ["E1524/E1810"]
    assert guest_remote["zigbee2mqtt_url"] is None
    nobody_remote = await docs(users.nobody, "remote")
    assert nobody_remote["documents"] == []
    assert nobody_remote["zigbee2mqtt_url"] == "https://www.zigbee2mqtt.io/devices/E1524_E1810.html"

    assert ids((await docs(users.admin, "washer"))["documents"]) == [RECEIPT_DOC, INVOICE_DOC]
    # The invoice category is not granted to the reader.
    assert ids((await docs(users.reader, "washer"))["documents"]) == [RECEIPT_DOC]
    assert (await docs(users.reader, "washer"))["zigbee2mqtt_url"] is None  # not a Z2M device

    unknown = await call(
        hass, hass_ws_client, users.admin, type="paperless_lookup/device_documents", device_id="x"
    )
    assert unknown["error"]["code"] == "not_found"


@pytest.mark.usefixtures("setup")
async def test_area_documents(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    users: Users,
    devices: dict[str, str],
) -> None:
    """Test that an area lists only devices with visible documents."""
    guest = await call(
        hass,
        hass_ws_client,
        users.guest,
        type="paperless_lookup/area_documents",
        area_id=devices["area"],
    )
    nobody = await call(
        hass,
        hass_ws_client,
        users.nobody,
        type="paperless_lookup/area_documents",
        area_id=devices["area"],
    )

    assert [device["name"] for device in guest["result"]["devices"]] == ["Remote"]
    assert nobody["result"] == {"devices": []}


@pytest.mark.usefixtures("setup")
async def test_sign_documents(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, users: Users
) -> None:
    """Test that only visible documents get a signed path."""
    response = await call(
        hass,
        hass_ws_client,
        users.reader,
        type="paperless_lookup/sign_documents",
        document_ids=[TRADFRI_DOC, RECEIPT_DOC, INVOICE_DOC, 10, 999],
        kind="thumb",
    )

    paths = response["result"]["paths"]
    assert set(paths) == {str(TRADFRI_DOC), str(RECEIPT_DOC)}
    assert paths[str(TRADFRI_DOC)].startswith("/api/paperless_lookup/document/1/thumb?authSig=")

    bad_kind = await call(
        hass,
        hass_ws_client,
        users.reader,
        type="paperless_lookup/sign_documents",
        document_ids=[TRADFRI_DOC],
        kind="original",
    )
    too_many = await call(
        hass,
        hass_ws_client,
        users.reader,
        type="paperless_lookup/sign_documents",
        document_ids=list(range(101)),
        kind="thumb",
    )
    assert bad_kind["error"]["code"] == "invalid_format"
    assert too_many["error"]["code"] == "invalid_format"


@pytest.mark.usefixtures("setup")
@pytest.mark.parametrize(
    "msg",
    [
        {"type": "paperless_lookup/devices_without_manual"},
        {"type": "paperless_lookup/link", "device_id": "x", "document_id": 1},
        {"type": "paperless_lookup/unlink", "device_id": "x", "document_id": 1},
        {"type": "paperless_lookup/ignore", "device_id": "x", "ignored": True},
    ],
)
async def test_admin_commands_refused(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, users: Users, msg: dict[str, Any]
) -> None:
    """Test that device administration is for administrators only."""
    response = await call(hass, hass_ws_client, users.reader, **msg)

    assert response["error"]["code"] == "unauthorized"


@pytest.mark.usefixtures("setup")
async def test_admin_device_management(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    users: Users,
    devices: dict[str, str],
) -> None:
    """Test devices without manual, link, unlink and ignore."""
    without = await call(
        hass, hass_ws_client, users.admin, type="paperless_lookup/devices_without_manual"
    )
    assert [device["name"] for device in without["result"]["devices"]] == ["Plug", "Washer"]
    plug = without["result"]["devices"][0]
    assert plug["zigbee2mqtt_url"] == "https://www.zigbee2mqtt.io/devices/PLUG-01.html"

    linked = await call(
        hass,
        hass_ws_client,
        users.admin,
        type="paperless_lookup/link",
        device_id=devices["washer"],
        document_id=AQARA_DOC,
    )
    assert ids(linked["result"]["documents"]) == [AQARA_DOC]

    unlinked = await call(
        hass,
        hass_ws_client,
        users.admin,
        type="paperless_lookup/unlink",
        device_id=devices["remote"],
        document_id=TRADFRI_DOC,
    )
    assert unlinked["result"]["documents"] == []

    ignored = await call(
        hass,
        hass_ws_client,
        users.admin,
        type="paperless_lookup/ignore",
        device_id=devices["plug"],
        ignored=True,
    )
    assert ignored["result"] == {"device_id": devices["plug"], "ignored": True}

    without = await call(
        hass, hass_ws_client, users.admin, type="paperless_lookup/devices_without_manual"
    )
    assert [device["name"] for device in without["result"]["devices"]] == ["Remote"]

    # Documents outside the index and unknown devices are not found.
    for msg in (
        {"type": "paperless_lookup/link", "device_id": devices["washer"], "document_id": 10},
        {"type": "paperless_lookup/link", "device_id": "unknown", "document_id": AQARA_DOC},
        {"type": "paperless_lookup/ignore", "device_id": "unknown", "ignored": True},
    ):
        response = await call(hass, hass_ws_client, users.admin, **msg)
        assert response["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    ("snippet", "expected"),
    [
        (None, []),
        ("", []),
        (
            "<b>Washing</b> machine &amp; <i>dryer</i>\n<b>W800</b>",
            [
                {"text": "Washing", "match": True},
                {"text": " machine & dryer\n", "match": False},
                {"text": "W800", "match": True},
            ],
        ),
        ("<script>alert(1)</script> text", [{"text": "alert(1) text", "match": False}]),
        ("&lt;b&gt;not bold&lt;/b&gt;", [{"text": "<b>not bold</b>", "match": False}]),
        ("a<b></b>b", [{"text": "a", "match": False}, {"text": "b", "match": False}]),
    ],
)
def test_highlight_segments(snippet: str | None, expected: list[dict[str, Any]]) -> None:
    """Test that highlights become plain-text segments."""
    assert highlight_segments(snippet) == expected
