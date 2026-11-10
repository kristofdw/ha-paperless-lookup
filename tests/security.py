"""Shared setup for the access, websocket and view tests.

Users and their categories (document types of the dev Paperless fixtures):

| user   | Manual (1) | Receipt (2) | Invoice (3) | Warranty (4) | Bank statement (5) |
|--------|------------|-------------|-------------|--------------|--------------------|
| admin  | yes (admins always see all categories, unless switched off)          |
| reader | yes        | yes         | -           | -            | -                  |
| guest  | yes        | -           | -           | -            | -                  |
| nobody | -          | -           | -           | -            | -                  |
"""

from dataclasses import dataclass
from typing import Any

from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_USER
from homeassistant.auth.models import User
from homeassistant.core import HomeAssistant
from pytest_homeassistant.common import MockConfigEntry, MockUser
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.paperless_lookup.const import CONF_CATEGORIES, CONF_ZIGBEE2MQTT_FALLBACK

from .conftest import mock_paperless

MANUAL, RECEIPT, INVOICE, WARRANTY, BANK = 1, 2, 3, 4, 5
TRADFRI_DOC, AQARA_DOC, RECEIPT_DOC, INVOICE_DOC, WARRANTY_DOC = 1, 3, 5, 8, 9
CLIENT_ID = "https://example.com/app"


@dataclass
class Users:
    """The test users."""

    admin: User
    reader: User
    guest: User
    nobody: User


async def async_user(hass: HomeAssistant, name: str, *, admin: bool = False, **kwargs: Any) -> User:
    """Create a user in the admin or the user group."""
    group = await hass.auth.async_get_group(GROUP_ID_ADMIN if admin else GROUP_ID_USER)
    assert group is not None
    return MockUser(name=name, groups=[group], **kwargs).add_to_hass(hass)


async def async_setup_users(hass: HomeAssistant, admin: User) -> Users:
    """Create the non-admin test users."""
    return Users(
        admin=admin,
        reader=await async_user(hass, "Reader"),
        guest=await async_user(hass, "Guest"),
        nobody=await async_user(hass, "Nobody"),
    )


async def async_access_token(hass: HomeAssistant, user: User) -> tuple[str, str]:
    """Return (refresh token id, access token) for a user."""
    refresh_token = await hass.auth.async_create_refresh_token(user, CLIENT_ID)
    return refresh_token.id, hass.auth.async_create_access_token(refresh_token)


async def async_setup_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entry: MockConfigEntry,
    users: Users,
    **options: Any,
) -> None:
    """Set up the entry with the access matrix of this module."""
    mock_paperless(aioclient_mock)
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            CONF_CATEGORIES: {
                str(MANUAL): [users.reader.id, users.guest.id],
                str(RECEIPT): [users.reader.id],
                str(INVOICE): [],
                str(WARRANTY): [],
                str(BANK): [],
            },
            CONF_ZIGBEE2MQTT_FALLBACK: True,
            **options,
        },
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
