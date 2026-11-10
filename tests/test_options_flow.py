"""Tests for the Paperless Lookup options flow."""

from http import HTTPStatus
from typing import Any

from homeassistant.config_entries import ConfigEntryState, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.paperless_lookup.const import (
    CONF_ACCESS_TAG,
    CONF_ADMINS_ALWAYS,
    CONF_CATEGORIES,
    CONF_DEVICE_CATEGORIES,
    CONF_FOLLOW_READS,
    CONF_MODEL_FIELD,
    CONF_PANEL_USERS,
    CONF_ZIGBEE2MQTT_FALLBACK,
)

from .conftest import DEFAULT_OPTIONS, load_json_fixture, mock_paperless


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Return a loaded config entry."""
    mock_paperless(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


async def open_step(hass: HomeAssistant, entry: MockConfigEntry, step: str) -> ConfigFlowResult:
    """Open the options menu and choose a step."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["access", "categories", "devices", "follow_reads"]
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


def select_options(result: ConfigFlowResult, key: str) -> list[tuple[str, str]]:
    """Return (value, label) of a select field in a form."""
    schema = result["data_schema"]
    assert schema is not None
    for marker, selector in schema.schema.items():
        if str(marker) == key:
            return [(opt["value"], opt["label"]) for opt in selector.config["options"]]
    raise AssertionError(f"{key} not in form")


def suggested(result: ConfigFlowResult) -> dict[str, object]:
    """Return the suggested values of a form."""
    schema = result["data_schema"]
    assert schema is not None
    return {
        str(key): key.description["suggested_value"]
        for key in schema.schema
        if key.description and "suggested_value" in key.description
    }


async def test_not_loaded(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test that the options need a loaded entry (live data from Paperless)."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_loaded"


async def test_access(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test choosing the access tag; the entry reloads."""
    result = await open_step(hass, loaded_entry, "access")
    assert result["step_id"] == "access"
    assert select_options(result, CONF_ACCESS_TAG) == [("2", "Finance"), ("1", "HA")]
    assert suggested(result) == {
        CONF_ACCESS_TAG: "1",
        CONF_ADMINS_ALWAYS: True,
        CONF_PANEL_USERS: [],
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ACCESS_TAG: "2", CONF_ADMINS_ALWAYS: False}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert loaded_entry.options == {
        **DEFAULT_OPTIONS,
        CONF_ACCESS_TAG: 2,
        CONF_ADMINS_ALWAYS: False,
    }
    assert loaded_entry.state is ConfigEntryState.LOADED


async def test_panel_users(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test choosing who sees the sidebar item; removed users are not suggested."""
    hass.config_entries.async_update_entry(
        loaded_entry,
        options={**loaded_entry.options, CONF_PANEL_USERS: [hass_admin_user.id, "deleted-user"]},
    )
    await hass.async_block_till_done()
    result = await open_step(hass, loaded_entry, "access")
    assert (hass_read_only_user.id, hass_read_only_user.name) in select_options(
        result, CONF_PANEL_USERS
    )
    assert suggested(result)[CONF_PANEL_USERS] == [hass_admin_user.id]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ADMINS_ALWAYS: True,
            CONF_PANEL_USERS: [hass_read_only_user.id, hass_admin_user.id],
        },
    )
    await hass.async_block_till_done()

    assert loaded_entry.options[CONF_PANEL_USERS] == sorted(
        [hass_read_only_user.id, hass_admin_user.id]
    )


async def test_access_cleared(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test removing the access tag, and an unknown current tag."""
    hass.config_entries.async_update_entry(
        loaded_entry, options={**loaded_entry.options, CONF_ACCESS_TAG: 77}
    )
    await hass.async_block_till_done()
    result = await open_step(hass, loaded_entry, "access")
    assert CONF_ACCESS_TAG not in suggested(result)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ADMINS_ALWAYS: True}
    )

    assert loaded_entry.options[CONF_ACCESS_TAG] is None


async def test_categories_and_users(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test choosing categories and the users per category."""
    result = await open_step(hass, loaded_entry, "categories")
    assert result["step_id"] == "categories"
    assert [label for _, label in select_options(result, CONF_CATEGORIES)] == [
        "Bank statement",
        "Invoice",
        "Manual",
        "Receipt",
        "Warranty",
    ]
    assert sorted(suggested(result)[CONF_CATEGORIES]) == ["1", "2", "3", "4", "5"]  # type: ignore[call-overload]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CATEGORIES: ["2", "4"]}
    )
    assert result["step_id"] == "category_users"
    user_options = select_options(result, "Receipt")
    assert (hass_admin_user.id, hass_admin_user.name) in user_options
    assert (hass_read_only_user.id, hass_read_only_user.name) in user_options
    assert {str(key) for key in result["data_schema"].schema} == {"Receipt", "Warranty"}  # type: ignore[union-attr]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"Receipt": [hass_read_only_user.id, hass_admin_user.id]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert loaded_entry.options[CONF_CATEGORIES] == {
        "2": sorted([hass_read_only_user.id, hass_admin_user.id]),
        "4": [],
    }
    # Manual (1) is no longer a category, so it is no longer a device category either.
    assert loaded_entry.options[CONF_DEVICE_CATEGORIES] == []


async def test_category_users_suggested(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    loaded_entry: MockConfigEntry,
    hass_read_only_user: MockUser,
) -> None:
    """Test that current users are suggested, and duplicate type names stay apart."""
    hass.config_entries.async_update_entry(
        loaded_entry,
        options={
            **loaded_entry.options,
            CONF_CATEGORIES: {"1": [hass_read_only_user.id, "deleted-user"], "6": []},
        },
    )
    await hass.async_block_till_done()
    types = load_json_fixture("document_types")
    types["results"].append({"id": 6, "name": "Manual"})
    aioclient_mock.clear_requests()
    mock_paperless(aioclient_mock, document_types=types)

    result = await open_step(hass, loaded_entry, "categories")
    assert sorted(suggested(result)[CONF_CATEGORIES]) == ["1", "6"]  # type: ignore[call-overload]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CATEGORIES: ["1", "6"]}
    )

    assert {str(key) for key in result["data_schema"].schema} == {"Manual", "Manual (6)"}  # type: ignore[union-attr]
    assert suggested(result) == {"Manual": [hass_read_only_user.id], "Manual (6)": []}

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert loaded_entry.options[CONF_CATEGORIES] == {"1": [], "6": []}
    assert loaded_entry.options[CONF_DEVICE_CATEGORIES] == [1]


async def test_no_categories(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test removing all categories."""
    result = await open_step(hass, loaded_entry, "categories")

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CATEGORIES: []}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert loaded_entry.options[CONF_CATEGORIES] == {}
    assert loaded_entry.options[CONF_DEVICE_CATEGORIES] == []


async def test_devices(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test the device options."""
    result = await open_step(hass, loaded_entry, "devices")
    assert result["step_id"] == "devices"
    assert len(select_options(result, CONF_DEVICE_CATEGORIES)) == 5
    assert select_options(result, CONF_MODEL_FIELD) == [("1", "HA model")]
    assert suggested(result) == {
        CONF_DEVICE_CATEGORIES: ["1"],
        CONF_MODEL_FIELD: "1",
        CONF_ZIGBEE2MQTT_FALLBACK: False,
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_DEVICE_CATEGORIES: ["4", "1"], CONF_ZIGBEE2MQTT_FALLBACK: True},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert loaded_entry.options[CONF_DEVICE_CATEGORIES] == [1, 4]
    assert loaded_entry.options[CONF_MODEL_FIELD] is None
    assert loaded_entry.options[CONF_ZIGBEE2MQTT_FALLBACK] is True


async def test_devices_only_string_fields(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, loaded_entry: MockConfigEntry
) -> None:
    """Test that only text custom fields can be the model field."""
    fields = load_json_fixture("custom_fields")
    fields["results"][0]["data_type"] = "monetary"
    aioclient_mock.clear_requests()
    mock_paperless(aioclient_mock, custom_fields=fields)

    result = await open_step(hass, loaded_entry, "devices")

    assert select_options(result, CONF_MODEL_FIELD) == []
    assert CONF_MODEL_FIELD not in suggested(result)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ZIGBEE2MQTT_FALLBACK: False}
    )
    assert loaded_entry.options[CONF_MODEL_FIELD] is None


@pytest.mark.parametrize(
    ("step", "endpoint"),
    [
        ("access", "tags"),
        ("categories", "document_types"),
        ("devices", "custom_fields"),
        ("follow_reads", "document_types"),
    ],
)
async def test_cannot_connect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    loaded_entry: MockConfigEntry,
    step: str,
    endpoint: str,
) -> None:
    """Test that a step aborts when Paperless cannot be read."""
    aioclient_mock.clear_requests()
    overrides: dict[str, Any] = {endpoint: HTTPStatus.INTERNAL_SERVER_ERROR}
    mock_paperless(aioclient_mock, **overrides)

    result = await open_step(hass, loaded_entry, step)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


def name_users(admin: MockUser, reader: MockUser) -> None:
    """Give the test users distinct names (both are called "Mock User")."""
    admin.name = "Admin"
    reader.name = "Reader"


async def test_follow_reads(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test choosing, per user, the categories whose opened documents are logged."""
    name_users(hass_admin_user, hass_read_only_user)
    hass.config_entries.async_update_entry(
        loaded_entry,
        options={
            **loaded_entry.options,
            CONF_CATEGORIES: {
                "1": [hass_read_only_user.id],
                "2": [hass_read_only_user.id],
                "3": [],
            },
        },
    )
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "follow_reads")

    assert result["step_id"] == "follow_reads"
    fields = [str(key) for key in result["data_schema"].schema]  # type: ignore[union-attr]
    assert "Admin" in fields
    assert "Reader" in fields
    # Each user only gets the categories they may open: administrators all, others their own.
    assert select_options(result, "Admin") == [("3", "Invoice"), ("1", "Manual"), ("2", "Receipt")]
    assert select_options(result, "Reader") == [("1", "Manual"), ("2", "Receipt")]
    assert "Reader" not in result["description_placeholders"]["without_access"]  # type: ignore[index]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"Reader": ["2", "1"], "Admin": []}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Only users with categories are stored.
    assert loaded_entry.options[CONF_FOLLOW_READS] == {hass_read_only_user.id: [1, 2]}


async def test_follow_reads_users_without_access(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test that users who may not see any category are named instead of listed."""
    name_users(hass_admin_user, hass_read_only_user)
    hass.config_entries.async_update_entry(
        loaded_entry,
        options={
            **loaded_entry.options,
            CONF_CATEGORIES: {"2": [], "7": [hass_read_only_user.id]},
            CONF_FOLLOW_READS: {hass_admin_user.id: [2, 7], "deleted-user": [2]},
        },
    )
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "follow_reads")

    fields = [str(key) for key in result["data_schema"].schema]  # type: ignore[union-attr]
    assert "Reader" not in fields
    assert "Reader" in result["description_placeholders"]["without_access"]  # type: ignore[index]
    # Type 7 no longer exists in Paperless, so it is neither offered nor suggested.
    assert select_options(result, "Admin") == [("2", "Receipt")]
    assert suggested(result) == {"Admin": ["2"]}


async def test_follow_reads_duplicate_user_names(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test that two users with the same name get separate fields."""
    name_users(hass_admin_user, hass_read_only_user)
    twin = MockUser(name="Admin").add_to_hass(hass)
    hass.config_entries.async_update_entry(
        loaded_entry, options={**loaded_entry.options, CONF_CATEGORIES: {"2": [twin.id]}}
    )
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "follow_reads")

    fields = [str(key) for key in result["data_schema"].schema]  # type: ignore[union-attr]
    assert fields.count("Admin") == 1
    assert len([key for key in fields if key.startswith("Admin (")]) == 1


async def test_follow_reads_without_categories(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test that following needs categories first."""
    hass.config_entries.async_update_entry(
        loaded_entry, options={**loaded_entry.options, CONF_CATEGORIES: {}}
    )
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "follow_reads")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_categories"


async def test_follow_reads_without_users(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, hass_read_only_user: MockUser
) -> None:
    """Test that following needs a user who may see a category."""
    hass.config_entries.async_update_entry(
        loaded_entry,
        options={**loaded_entry.options, CONF_ADMINS_ALWAYS: False, CONF_CATEGORIES: {"2": []}},
    )
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "follow_reads")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_users"


async def test_removed_category_drops_followed_reads(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, hass_read_only_user: MockUser
) -> None:
    """Test that a category that is no longer chosen is no longer followed."""
    hass.config_entries.async_update_entry(
        loaded_entry,
        options={
            **loaded_entry.options,
            CONF_FOLLOW_READS: {hass_read_only_user.id: [2, 3], "other-user": [3]},
        },
    )
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "categories")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CATEGORIES: ["2"]}
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert loaded_entry.options[CONF_FOLLOW_READS] == {hass_read_only_user.id: [2]}
