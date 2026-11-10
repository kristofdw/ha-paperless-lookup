"""Tests for the Paperless Lookup options flow (a menu; Save and close stores the changes)."""

from http import HTTPStatus
from typing import Any

from homeassistant.config_entries import ConfigEntryState, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.paperless_lookup.config_flow import MENU_OPTIONS
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
    assert result["menu_options"] == MENU_OPTIONS
    return await choose(hass, result, step)


async def choose(hass: HomeAssistant, result: ConfigFlowResult, step: str) -> ConfigFlowResult:
    """Choose a menu item."""
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


async def submit(
    hass: HomeAssistant, result: ConfigFlowResult, user_input: dict[str, Any]
) -> ConfigFlowResult:
    """Submit a form; every step returns to the menu."""
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.options.async_configure(result["flow_id"], user_input)


async def save(hass: HomeAssistant, result: ConfigFlowResult) -> ConfigFlowResult:
    """Choose Save and close in the menu."""
    result = await choose(hass, result, "save")
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    return result


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


def field_names(result: ConfigFlowResult) -> list[str]:
    """Return the field names of a form."""
    schema = result["data_schema"]
    assert schema is not None
    return [str(key) for key in schema.schema]


def name_users(admin: MockUser, reader: MockUser) -> None:
    """Give the test users distinct names (both are called "Mock User")."""
    admin.name = "Admin"
    reader.name = "Reader"


def set_options(hass: HomeAssistant, entry: MockConfigEntry, **changes: Any) -> None:
    """Change the stored options of the entry."""
    hass.config_entries.async_update_entry(entry, options={**entry.options, **changes})


async def test_not_loaded(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test that the options need a loaded entry (live data from Paperless)."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_loaded"


async def test_access(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test choosing the access tag; stored only with Save and close, then the entry reloads."""
    result = await open_step(hass, loaded_entry, "access")
    assert result["step_id"] == "access"
    assert select_options(result, CONF_ACCESS_TAG) == [("2", "Finance"), ("1", "HA")]
    assert suggested(result) == {
        CONF_ACCESS_TAG: "1",
        CONF_ADMINS_ALWAYS: True,
        CONF_PANEL_USERS: [],
    }

    result = await submit(hass, result, {CONF_ACCESS_TAG: "2", CONF_ADMINS_ALWAYS: False})

    # Back in the menu; nothing is stored yet.
    assert result["type"] is FlowResultType.MENU
    assert loaded_entry.options == DEFAULT_OPTIONS

    await save(hass, result)
    assert loaded_entry.options == {
        **DEFAULT_OPTIONS,
        CONF_ACCESS_TAG: 2,
        CONF_ADMINS_ALWAYS: False,
        CONF_FOLLOW_READS: {},
    }
    assert loaded_entry.state is ConfigEntryState.LOADED


async def test_close_discards_changes(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test that closing the dialog without Save and close keeps the stored options."""
    result = await open_step(hass, loaded_entry, "access")
    result = await submit(hass, result, {CONF_ACCESS_TAG: "2", CONF_ADMINS_ALWAYS: False})

    hass.config_entries.options.async_abort(result["flow_id"])
    await hass.async_block_till_done()

    assert loaded_entry.options == DEFAULT_OPTIONS


async def test_panel_users(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test choosing who sees the sidebar item; removed users are not suggested."""
    set_options(hass, loaded_entry, **{CONF_PANEL_USERS: [hass_admin_user.id, "deleted-user"]})
    await hass.async_block_till_done()
    result = await open_step(hass, loaded_entry, "access")
    assert (hass_read_only_user.id, hass_read_only_user.name) in select_options(
        result, CONF_PANEL_USERS
    )
    assert suggested(result)[CONF_PANEL_USERS] == [hass_admin_user.id]

    result = await submit(
        hass,
        result,
        {CONF_ADMINS_ALWAYS: True, CONF_PANEL_USERS: [hass_read_only_user.id, hass_admin_user.id]},
    )
    await save(hass, result)

    assert loaded_entry.options[CONF_PANEL_USERS] == sorted(
        [hass_read_only_user.id, hass_admin_user.id]
    )


async def test_access_cleared(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test removing the access tag, and an unknown current tag."""
    set_options(hass, loaded_entry, **{CONF_ACCESS_TAG: 77})
    await hass.async_block_till_done()
    result = await open_step(hass, loaded_entry, "access")
    assert CONF_ACCESS_TAG not in suggested(result)

    result = await submit(hass, result, {CONF_ADMINS_ALWAYS: True})
    await save(hass, result)

    assert loaded_entry.options[CONF_ACCESS_TAG] is None


async def test_categories_and_users(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test choosing categories, then the users per category, then back to the menu."""
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

    result = await submit(hass, result, {CONF_CATEGORIES: ["2", "4"]})
    assert result["step_id"] == "category_users"
    user_options = select_options(result, "Receipt")
    assert (hass_admin_user.id, hass_admin_user.name) in user_options
    assert (hass_read_only_user.id, hass_read_only_user.name) in user_options
    assert set(field_names(result)) == {"Receipt", "Warranty"}

    result = await submit(hass, result, {"Receipt": [hass_read_only_user.id, hass_admin_user.id]})
    assert result["type"] is FlowResultType.MENU
    await save(hass, result)

    assert loaded_entry.options[CONF_CATEGORIES] == {
        "2": sorted([hass_read_only_user.id, hass_admin_user.id]),
        "4": [],
    }
    # Manual (1) is no longer a category, so it is no longer a device category either.
    assert loaded_entry.options[CONF_DEVICE_CATEGORIES] == []


async def test_category_users_from_menu(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, hass_read_only_user: MockUser
) -> None:
    """Test opening the users per category directly from the menu."""
    set_options(hass, loaded_entry, **{CONF_CATEGORIES: {"2": [], "3": []}})
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "category_users")

    assert result["step_id"] == "category_users"
    assert result["errors"] == {}
    assert field_names(result) == ["Receipt", "Invoice"]
    result = await submit(hass, result, {"Invoice": [hass_read_only_user.id]})
    await save(hass, result)
    assert loaded_entry.options[CONF_CATEGORIES] == {"2": [], "3": [hass_read_only_user.id]}


async def test_category_users_suggested(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    loaded_entry: MockConfigEntry,
    hass_read_only_user: MockUser,
) -> None:
    """Test that current users are suggested, and duplicate type names stay apart."""
    set_options(
        hass,
        loaded_entry,
        **{CONF_CATEGORIES: {"1": [hass_read_only_user.id, "deleted-user"], "6": []}},
    )
    await hass.async_block_till_done()
    types = load_json_fixture("document_types")
    types["results"].append({"id": 6, "name": "Manual"})
    aioclient_mock.clear_requests()
    mock_paperless(aioclient_mock, document_types=types)

    result = await open_step(hass, loaded_entry, "categories")
    assert sorted(suggested(result)[CONF_CATEGORIES]) == ["1", "6"]  # type: ignore[call-overload]
    result = await submit(hass, result, {CONF_CATEGORIES: ["1", "6"]})

    assert set(field_names(result)) == {"Manual", "Manual (6)"}
    assert suggested(result) == {"Manual": [hass_read_only_user.id], "Manual (6)": []}

    result = await submit(hass, result, {})
    await save(hass, result)
    assert loaded_entry.options[CONF_CATEGORIES] == {"1": [], "6": []}
    assert loaded_entry.options[CONF_DEVICE_CATEGORIES] == [1]


async def test_category_users_without_categories(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test that the users step explains that categories come first, and returns to the menu."""
    set_options(hass, loaded_entry, **{CONF_CATEGORIES: {}})
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "category_users")

    assert result["errors"] == {"base": "no_categories"}
    assert field_names(result) == []
    result = await submit(hass, result, {})
    assert result["type"] is FlowResultType.MENU


async def test_no_categories(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test removing all categories: back to the menu without the users step."""
    result = await open_step(hass, loaded_entry, "categories")

    result = await submit(hass, result, {CONF_CATEGORIES: []})

    assert result["type"] is FlowResultType.MENU
    await save(hass, result)
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

    result = await submit(
        hass, result, {CONF_DEVICE_CATEGORIES: ["4", "1"], CONF_ZIGBEE2MQTT_FALLBACK: True}
    )
    await save(hass, result)

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
    result = await submit(hass, result, {CONF_ZIGBEE2MQTT_FALLBACK: False})
    await save(hass, result)
    assert loaded_entry.options[CONF_MODEL_FIELD] is None


@pytest.mark.parametrize(
    ("step", "endpoint"),
    [
        ("access", "tags"),
        ("categories", "document_types"),
        ("category_users", "document_types"),
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


async def test_follow_reads(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test choosing, per user, the categories whose opened documents are logged."""
    name_users(hass_admin_user, hass_read_only_user)
    set_options(
        hass,
        loaded_entry,
        **{
            CONF_CATEGORIES: {
                "1": [hass_read_only_user.id],
                "2": [hass_read_only_user.id],
                "3": [],
            }
        },
    )
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "follow_reads")

    assert result["step_id"] == "follow_reads"
    assert result["errors"] == {}
    fields = field_names(result)
    assert "Admin" in fields
    assert "Reader" in fields
    # Each user only gets the categories they may open: administrators all, others their own.
    assert select_options(result, "Admin") == [("3", "Invoice"), ("1", "Manual"), ("2", "Receipt")]
    assert select_options(result, "Reader") == [("1", "Manual"), ("2", "Receipt")]
    assert "Reader" not in result["description_placeholders"]["without_access"]  # type: ignore[index]

    result = await submit(hass, result, {"Reader": ["2", "1"], "Admin": []})
    await save(hass, result)

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
    set_options(
        hass,
        loaded_entry,
        **{
            CONF_CATEGORIES: {"2": [], "7": [hass_read_only_user.id]},
            CONF_FOLLOW_READS: {hass_admin_user.id: [2, 7], "deleted-user": [2]},
        },
    )
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "follow_reads")

    assert "Reader" not in field_names(result)
    assert "Reader" in result["description_placeholders"]["without_access"]  # type: ignore[index]
    # Type 7 no longer exists in Paperless, so it is neither offered nor suggested.
    assert select_options(result, "Admin") == [("2", "Receipt")]
    assert suggested(result) == {"Admin": ["2"]}


async def test_follow_reads_uses_unsaved_users(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test that users given access earlier in the same dialog can be followed right away."""
    name_users(hass_admin_user, hass_read_only_user)
    set_options(hass, loaded_entry, **{CONF_CATEGORIES: {"2": [], "3": []}})
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "category_users")
    result = await submit(hass, result, {"Receipt": [hass_read_only_user.id]})
    result = await choose(hass, result, "follow_reads")

    assert select_options(result, "Reader") == [("2", "Receipt")]


async def test_follow_reads_duplicate_user_names(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test that two users with the same name get separate fields."""
    name_users(hass_admin_user, hass_read_only_user)
    twin = MockUser(name="Admin").add_to_hass(hass)
    set_options(hass, loaded_entry, **{CONF_CATEGORIES: {"2": [twin.id]}})
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "follow_reads")

    fields = field_names(result)
    assert fields.count("Admin") == 1
    assert len([key for key in fields if key.startswith("Admin (")]) == 1


async def test_follow_reads_without_categories(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test that following explains that categories come first."""
    set_options(hass, loaded_entry, **{CONF_CATEGORIES: {}})
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "follow_reads")

    assert result["errors"] == {"base": "no_categories"}
    result = await submit(hass, result, {})
    assert result["type"] is FlowResultType.MENU


async def test_follow_reads_without_users(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, hass_read_only_user: MockUser
) -> None:
    """Test that following explains that a user needs access first."""
    set_options(hass, loaded_entry, **{CONF_ADMINS_ALWAYS: False, CONF_CATEGORIES: {"2": []}})
    await hass.async_block_till_done()

    result = await open_step(hass, loaded_entry, "follow_reads")

    assert result["errors"] == {"base": "no_users"}
    assert field_names(result) == []


async def test_removed_access_drops_followed_reads(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test that a category the user may no longer see is no longer followed."""
    set_options(
        hass,
        loaded_entry,
        **{
            CONF_CATEGORIES: {"2": [hass_read_only_user.id], "3": [hass_read_only_user.id]},
            CONF_FOLLOW_READS: {
                hass_read_only_user.id: [2, 3],
                hass_admin_user.id: [3],
                "deleted-user": [3],
            },
        },
    )
    await hass.async_block_till_done()

    # Invoice (3) is no longer a category.
    result = await open_step(hass, loaded_entry, "categories")
    result = await submit(hass, result, {CONF_CATEGORIES: ["2"]})
    result = await submit(hass, result, {"Receipt": [hass_read_only_user.id]})
    await save(hass, result)
    assert loaded_entry.options[CONF_FOLLOW_READS] == {hass_read_only_user.id: [2]}

    # Administrators no longer see every category: the admin loses Receipt too.
    set_options(hass, loaded_entry, **{CONF_FOLLOW_READS: {hass_admin_user.id: [2]}})
    await hass.async_block_till_done()
    result = await open_step(hass, loaded_entry, "access")
    result = await submit(hass, result, {CONF_ACCESS_TAG: "1", CONF_ADMINS_ALWAYS: False})
    await save(hass, result)
    assert loaded_entry.options[CONF_FOLLOW_READS] == {}
