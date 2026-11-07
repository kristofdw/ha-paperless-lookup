"""Tests for the Paperless Lookup config flow."""

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.paperless_lookup.const import DOMAIN, NAME

from .conftest import MOCK_CONFIG


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """Test the user step shows a form and creates an entry."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(result["flow_id"], dict(MOCK_CONFIG))
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == MOCK_CONFIG


async def test_single_instance(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test that a second entry is refused (single_config_entry)."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
