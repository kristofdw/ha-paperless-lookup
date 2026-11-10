"""Tests for the document index and the device links (with a mocked device registry)."""

from datetime import date, timedelta
from http import HTTPStatus
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.paperless_lookup import async_remove_entry
from custom_components.paperless_lookup.const import (
    CONF_ACCESS_TAG,
    CONF_CATEGORIES,
    CONF_DEVICE_CATEGORIES,
    CONF_MODEL_FIELD,
    DOMAIN,
    REFRESH_INTERVAL,
)
from custom_components.paperless_lookup.coordinator import (
    PaperlessLookupCoordinator,
    async_get_device,
    async_physical_devices,
)

from .conftest import load_json_fixture, mock_paperless

MANUAL, RECEIPT, INVOICE, WARRANTY, BANK = 1, 2, 3, 4, 5
TRADFRI_DOC, STYRBAR_DOC, AQARA_DOC, HUE_DOC = 1, 2, 3, 4
RECEIPT_DOC, WARRANTY_DOC = 5, 9


async def setup_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entry: MockConfigEntry,
    options: dict[str, Any] | None = None,
    **overrides: Any,
) -> PaperlessLookupCoordinator:
    """Set up the entry (with changed options) and return its coordinator."""
    mock_paperless(aioclient_mock, **overrides)
    entry.add_to_hass(hass)
    if options:
        hass.config_entries.async_update_entry(entry, options={**entry.options, **options})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator: PaperlessLookupCoordinator = entry.runtime_data.coordinator
    return coordinator


@pytest.fixture
def devices(hass: HomeAssistant) -> dict[str, str]:
    """Create Zigbee2MQTT-like and other devices; return name -> device id."""
    mqtt_entry = MockConfigEntry(domain="mqtt")
    mqtt_entry.add_to_hass(hass)
    other_entry = MockConfigEntry(domain="hue")
    other_entry.add_to_hass(hass)
    registry = dr.async_get(hass)

    def add(name: str, entry: MockConfigEntry, ident: str, **kwargs: Any) -> str:
        domain = "mqtt" if entry is mqtt_entry else "hue"
        return registry.async_get_or_create(
            config_entry_id=entry.entry_id, identifiers={(domain, ident)}, name=name, **kwargs
        ).id

    return {
        # Zigbee2MQTT: model = description, model_id = Zigbee model.
        "remote": add(
            "Living room remote",
            mqtt_entry,
            "zigbee2mqtt_0x0001",
            manufacturer="IKEA",
            model="TRADFRI remote control",
            model_id="E1524/E1810",
        ),
        # Older Zigbee2MQTT naming: "<description> (<model>)".
        "door": add(
            "Front door",
            mqtt_entry,
            "zigbee2mqtt_0x0002",
            manufacturer="Aqara",
            model="Door and window sensor (MCCGQ11LM)",
        ),
        "plug": add(
            "Coffee plug",
            mqtt_entry,
            "zigbee2mqtt_0x0003",
            manufacturer="Example",
            model="Smart plug",
            model_id="PLUG-01",
        ),
        "bulb": add(
            "Hallway bulb",
            other_entry,
            "bulb-1",
            manufacturer="Signify",
            model="Hue white ambiance",
            model_id="9290022169",
        ),
        "washer": add("Washing machine", other_entry, "washer-1", model="W800"),
        "bridge": add(
            "Bridge service",
            other_entry,
            "bridge",
            model="Bridge",
            entry_type=dr.DeviceEntryType.SERVICE,
        ),
        "no_model": add("No model", other_entry, "nomodel", manufacturer="X"),
        "disabled": add(
            "Disabled",
            other_entry,
            "disabled",
            model="Old",
            disabled_by=dr.DeviceEntryDisabler.USER,
        ),
    }


async def test_index(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> None:
    """Test the index built from the dev Paperless fixtures."""
    coordinator = await setup_entry(hass, aioclient_mock, mock_config_entry)

    index = coordinator.data
    assert len(index.documents) == 9
    assert index.document_types[MANUAL] == "Manual"
    assert index.correspondents[1] == "IKEA"
    aqara = index.documents[AQARA_DOC]
    assert aqara.models == ("RTCGQ11LM", "MCCGQ11LM")
    assert aqara.model_keys == {"rtcgq11lm", "mccgq11lm"}
    assert aqara.created == date(2023, 11, 20)
    # The warranty has a model, but Warranty is not a device category.
    assert index.documents[WARRANTY_DOC].models == ()
    assert index.documents[RECEIPT_DOC].correspondent == 4
    query = dict(aioclient_mock.mock_calls[-1][1].query)
    assert query["tags__id__all"] == "1"
    assert query["document_type__id__in"] == "1,2,3,4,5"


async def test_index_limited_to_categories(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> None:
    """Test that documents of other types or without the tag never enter the index."""
    page = load_json_fixture("documents_page_1")
    page["next"] = None
    page["results"].append({"id": 20, "title": "No type", "document_type": None, "tags": [1]})
    page["results"].append({"id": 21, "title": "Bank", "document_type": BANK, "tags": [1]})
    coordinator = await setup_entry(
        hass,
        aioclient_mock,
        mock_config_entry,
        {CONF_CATEGORIES: {"2": [], "4": []}, CONF_DEVICE_CATEGORIES: [1, 4]},
        documents=page,
    )

    assert set(coordinator.data.documents) == {7, 6, 5, WARRANTY_DOC}
    # Manual is not a category, so only Warranty counts as a device category.
    assert coordinator.device_categories == {WARRANTY}
    assert coordinator.data.documents[WARRANTY_DOC].models == ("W800",)


@pytest.mark.parametrize(
    "options",
    [{CONF_ACCESS_TAG: None}, {CONF_CATEGORIES: {}}],
)
async def test_index_without_tag_or_categories(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    options: dict[str, Any],
) -> None:
    """Test that nothing is requested without an access tag or categories."""
    coordinator = await setup_entry(hass, aioclient_mock, mock_config_entry, options)

    assert coordinator.data.documents == {}
    assert coordinator.data.document_types
    assert not any("/api/documents/" in str(call[1]) for call in aioclient_mock.mock_calls)
    assert coordinator.devices_without_documents() == []


async def test_access_tag_issue_follows_the_tag(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a tag Paperless no longer shows empties the index and raises a repair issue."""
    registry = ir.async_get(hass)
    issue_id = f"access_tag_missing_{mock_config_entry.entry_id}"
    coordinator = await setup_entry(hass, aioclient_mock, mock_config_entry)
    assert coordinator.diagnostics()["access_tag_visible"] is True
    assert registry.async_get_issue(DOMAIN, issue_id) is None

    async def refresh(tags: Any) -> None:
        aioclient_mock.clear_requests()
        mock_paperless(aioclient_mock, tags=tags)
        freezer.tick(REFRESH_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    await refresh({"count": 0, "next": None, "previous": None, "all": [], "results": []})
    assert coordinator.diagnostics()["access_tag_visible"] is False
    assert len(coordinator.data.documents) == 0
    assert not any("/api/documents/" in str(call[1]) for call in aioclient_mock.mock_calls)
    issue = registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "access_tag_missing"

    await refresh(load_json_fixture("tags"))
    assert len(coordinator.data.documents) == 9
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_no_access_tag_raises_issue_and_removal_clears_it(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> None:
    """Test the issue for an unset tag; removing the entry deletes it."""
    registry = ir.async_get(hass)
    issue_id = f"access_tag_missing_{mock_config_entry.entry_id}"
    await setup_entry(hass, aioclient_mock, mock_config_entry, {CONF_ACCESS_TAG: None})
    assert registry.async_get_issue(DOMAIN, issue_id) is not None

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_index_without_model_field(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> None:
    """Test that no models are read without a model field."""
    coordinator = await setup_entry(
        hass, aioclient_mock, mock_config_entry, {CONF_MODEL_FIELD: None}
    )

    assert all(doc.models == () for doc in coordinator.data.documents.values())


async def test_first_refresh_fails(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a failing first refresh retries the setup."""
    mock_paperless(aioclient_mock, documents=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_refresh_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the periodic refresh: interval, failure, then a rejected token (reauth)."""
    coordinator = await setup_entry(hass, aioclient_mock, mock_config_entry)
    assert coordinator.update_interval == timedelta(minutes=60) == REFRESH_INTERVAL

    aioclient_mock.clear_requests()
    mock_paperless(aioclient_mock, documents=HTTPStatus.BAD_GATEWAY)
    freezer.tick(REFRESH_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert len(coordinator.data.documents) == 9  # last good index is kept

    aioclient_mock.clear_requests()
    mock_paperless(aioclient_mock, document_types=HTTPStatus.UNAUTHORIZED)
    freezer.tick(REFRESH_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_device_documents(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    devices: dict[str, str],
) -> None:
    """Test matching by model, manual links and unlinks."""
    coordinator = await setup_entry(hass, aioclient_mock, mock_config_entry)

    def docs(name: str) -> list[int]:
        device = async_get_device(hass, devices[name])
        assert device is not None
        return [doc.id for doc in coordinator.device_documents(device)]

    assert docs("remote") == [TRADFRI_DOC]
    assert docs("door") == [AQARA_DOC]
    assert docs("bulb") == [HUE_DOC]
    assert docs("plug") == []
    # The warranty lists W800, but Warranty is not a device category.
    assert docs("washer") == []

    store = coordinator.store
    await store.async_link(devices["washer"], WARRANTY_DOC)
    await store.async_link(devices["washer"], 8)  # invoice, any category may be linked
    await store.async_link(devices["washer"], 999)  # not (or no longer) in the index
    await store.async_unlink(devices["remote"], TRADFRI_DOC)
    await store.async_link(devices["remote"], STYRBAR_DOC)

    assert docs("washer") == [WARRANTY_DOC, 8]  # newest first, then id
    assert docs("remote") == [STYRBAR_DOC]


async def test_devices_without_documents(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    devices: dict[str, str],
) -> None:
    """Test the list of devices without a manual."""
    coordinator = await setup_entry(hass, aioclient_mock, mock_config_entry)

    def names() -> list[str]:
        return [device.name for device in coordinator.devices_without_documents()]

    # Service devices, disabled devices and devices without a model are left out.
    assert names() == ["Coffee plug", "Washing machine"]

    await coordinator.store.async_set_ignored(devices["plug"], True)
    # A linked invoice is not a manual; a linked manual is.
    await coordinator.store.async_link(devices["washer"], 8)
    assert names() == ["Washing machine"]
    await coordinator.store.async_link(devices["washer"], HUE_DOC)
    assert names() == []

    await coordinator.store.async_unlink(devices["remote"], TRADFRI_DOC)
    assert names() == ["Living room remote"]

    plug = async_get_device(hass, devices["plug"])
    assert plug is not None
    assert plug.is_zigbee2mqtt
    assert {device.id for device in async_physical_devices(hass)} == {
        devices[name] for name in ("remote", "door", "plug", "bulb", "washer")
    }
    assert async_get_device(hass, "unknown") is None


async def test_removed_device_is_forgotten(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    devices: dict[str, str],
) -> None:
    """Test that the links of a removed device are deleted."""
    coordinator = await setup_entry(hass, aioclient_mock, mock_config_entry)
    store = coordinator.store
    await store.async_link(devices["plug"], RECEIPT_DOC)
    await store.async_set_ignored(devices["washer"], True)

    dr.async_get(hass).async_update_device(devices["washer"], name_by_user="Washer")
    dr.async_get(hass).async_remove_device(devices["plug"])
    await hass.async_block_till_done()

    assert store.links(devices["plug"]) == frozenset()
    assert store.is_ignored(devices["washer"])


async def test_remove_entry_deletes_links(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test that removing the config entry deletes the stored links."""
    coordinator = await setup_entry(hass, aioclient_mock, mock_config_entry)
    await coordinator.store.async_link("some-device", 1)
    key = f"{DOMAIN}.{mock_config_entry.entry_id}"
    assert key in hass_storage

    await async_remove_entry(hass, mock_config_entry)

    assert key not in hass_storage
