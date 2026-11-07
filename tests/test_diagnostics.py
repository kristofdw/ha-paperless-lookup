"""Tests for the Paperless Lookup diagnostics and translations."""

import json
from pathlib import Path
from typing import Any

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.paperless_lookup.const import CONF_CATEGORIES
from custom_components.paperless_lookup.diagnostics import async_get_config_entry_diagnostics

from .conftest import PAPERLESS_USERNAME, TEST_TOKEN, mock_paperless

INTEGRATION = Path(__file__).parent.parent / "custom_components" / "paperless_lookup"


async def test_diagnostics_redacted(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_config_entry: MockConfigEntry
) -> None:
    """Test that diagnostics contain no token, URL, user names or user ids."""
    mock_paperless(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_CATEGORIES: {"1": ["ha-user-id-a", "ha-user-id-b"], "2": []},
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    text = json.dumps(diagnostics)
    for secret in (TEST_TOKEN, "paperless.test", PAPERLESS_USERNAME, "ha-user-id-a"):
        assert secret not in text
    entry = diagnostics["entry"]
    assert entry["title"] == REDACTED
    assert entry["unique_id"] == REDACTED
    assert entry["data"] == {
        "url": REDACTED,
        "api_token": REDACTED,
        "verify_ssl": True,
        "paperless_user_id": REDACTED,
    }
    assert entry["options"][CONF_CATEGORIES] == {"1": 2, "2": 0}
    assert diagnostics["paperless"]["server_version"] == "3.3.4"
    assert diagnostics["paperless"]["api_version"] == 10
    assert diagnostics["paperless"]["user"]["has_write_access"] is False
    assert diagnostics["paperless"]["user"]["missing_permissions"] == []
    assert diagnostics["index"] == {
        "last_update_success": True,
        "documents": 7,
        "documents_per_category": {"1": 4, "2": 3},
        "documents_with_models": 4,
        "devices_with_links": 0,
        "devices_with_unlinks": 0,
        "ignored_devices": 0,
    }
    for title in ("receipt", "manual", "Washing"):
        assert title not in text


def _keys(data: Any, prefix: str = "") -> set[str]:
    """Return the flattened keys of a translation file."""
    if not isinstance(data, dict):
        return {prefix}
    return {key for name, value in data.items() for key in _keys(value, f"{prefix}.{name}")}


def test_translations_complete() -> None:
    """Test that strings.json equals en.json and nl.json has the same keys."""
    strings = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))
    english = json.loads((INTEGRATION / "translations" / "en.json").read_text(encoding="utf-8"))
    dutch = json.loads((INTEGRATION / "translations" / "nl.json").read_text(encoding="utf-8"))

    assert strings == english
    assert _keys(dutch) == _keys(english)
