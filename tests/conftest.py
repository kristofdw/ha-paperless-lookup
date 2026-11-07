"""Common fixtures for the Paperless Lookup tests."""

from typing import Any

from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.paperless_lookup.const import DOMAIN, NAME

# Obviously fake test values. Never put real tokens or addresses in tests.
MOCK_CONFIG: dict[str, Any] = {
    CONF_URL: "http://paperless.test:8000",
    CONF_API_TOKEN: "fake-test-token-0000",
    CONF_VERIFY_SSL: True,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for Paperless Lookup."""
    return MockConfigEntry(domain=DOMAIN, title=NAME, data=dict(MOCK_CONFIG))
