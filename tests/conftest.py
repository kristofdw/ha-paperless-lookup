"""Common fixtures for the Paperless Lookup tests."""

from http import HTTPStatus
import json
from pathlib import Path
from typing import Any

from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.paperless_lookup.const import (
    CONF_ACCESS_TAG,
    CONF_ADMINS_ALWAYS,
    CONF_CATEGORIES,
    CONF_DEVICE_CATEGORIES,
    CONF_MODEL_FIELD,
    CONF_PANEL_USERS,
    CONF_PAPERLESS_USER_ID,
    CONF_ZIGBEE2MQTT_FALLBACK,
    DOMAIN,
)

# Obviously fake test values. Never put real tokens or addresses in tests.
TEST_URL = "http://paperless.test:8000"
TEST_HTTPS_URL = "https://paperless.test"
TEST_TOKEN = "fake-test-token-0000"
PAPERLESS_USER_ID = 3  # "ha-lookup" in the fixtures
PAPERLESS_USERNAME = "ha-lookup"

MOCK_CONFIG: dict[str, Any] = {
    CONF_URL: TEST_URL,
    CONF_API_TOKEN: TEST_TOKEN,
    CONF_VERIFY_SSL: True,
    CONF_PAPERLESS_USER_ID: PAPERLESS_USER_ID,
}

# Matches the fixtures: tag HA = 1, types Manual 1, Receipt 2, Invoice 3, Warranty 4,
# Bank statement 5, custom field "HA model" = 1.
DEFAULT_OPTIONS: dict[str, Any] = {
    CONF_ACCESS_TAG: 1,
    CONF_CATEGORIES: {"1": [], "2": [], "3": [], "4": [], "5": []},
    CONF_ADMINS_ALWAYS: True,
    CONF_PANEL_USERS: [],
    CONF_DEVICE_CATEGORIES: [1],
    CONF_MODEL_FIELD: 1,
    CONF_ZIGBEE2MQTT_FALLBACK: False,
}

FIXTURES = Path(__file__).parent / "fixtures"


def load_json_fixture(name: str) -> Any:
    """Return a JSON fixture captured from the dev Paperless (see dev/capture_fixtures.py)."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def ui_settings(*, is_superuser: bool = False, permissions: list[str] | None = None) -> Any:
    """Return the ui_settings fixture with optional changes."""
    data = load_json_fixture("ui_settings")
    data["user"]["is_superuser"] = is_superuser
    if permissions is not None:
        data["permissions"] = permissions
    return data


def mock_paperless(
    aioclient_mock: AiohttpClientMocker,
    base: str = TEST_URL,
    *,
    user: Any = None,
    status: HTTPStatus = HTTPStatus.OK,
    **overrides: Any,
) -> None:
    """Register the Paperless endpoints used by setup and the flows.

    ``status`` applies to ``ui_settings``; ``overrides`` replace the JSON (or, as a status code,
    the response) of the other endpoints, e.g. ``tags=HTTPStatus.INTERNAL_SERVER_ERROR``.
    """
    headers = {"Content-Type": "application/json", "X-Api-Version": "10", "X-Version": "3.3.4"}
    aioclient_mock.get(
        f"{base}/api/ui_settings/",
        status=status,
        json=user if user is not None else ui_settings(),
        headers=headers,
    )
    for endpoint in ("tags", "document_types", "correspondents", "custom_fields"):
        value = overrides.get(endpoint, load_json_fixture(endpoint))
        if isinstance(value, HTTPStatus):
            aioclient_mock.get(f"{base}/api/{endpoint}/", status=value, json={}, headers=headers)
        else:
            aioclient_mock.get(f"{base}/api/{endpoint}/", json=value, headers=headers)
    # Documents: the two captured pages (9 documents with the HA tag), or one override page.
    documents = overrides.get("documents")
    if isinstance(documents, HTTPStatus):
        aioclient_mock.get(f"{base}/api/documents/", status=documents, json={}, headers=headers)
    elif documents is not None:
        aioclient_mock.get(f"{base}/api/documents/", json=documents, headers=headers)
    else:
        for page in (1, 2):
            aioclient_mock.get(
                f"{base}/api/documents/",
                params={"page": str(page)},
                json=load_json_fixture(f"documents_page_{page}"),
                headers=headers,
            )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for Paperless Lookup."""
    return MockConfigEntry(
        domain=DOMAIN,
        minor_version=3,
        title=PAPERLESS_USERNAME,
        unique_id=f"{TEST_URL}#{PAPERLESS_USER_ID}",
        data=dict(MOCK_CONFIG),
        options={**DEFAULT_OPTIONS, CONF_CATEGORIES: dict(DEFAULT_OPTIONS[CONF_CATEGORIES])},
    )
