"""The Paperless Lookup integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady

from .api import (
    PaperlessAuthError,
    PaperlessClient,
    PaperlessError,
    PaperlessPermissionError,
    PaperlessUnsupportedVersionError,
    PaperlessUser,
)
from .const import CONF_PAPERLESS_USER_ID, DOMAIN
from .helpers import create_client, missing_permissions

PLATFORMS: list[Platform] = []


@dataclass(slots=True)
class PaperlessLookupData:
    """Runtime data of a Paperless Lookup config entry."""

    client: PaperlessClient
    user: PaperlessUser


type PaperlessLookupConfigEntry = ConfigEntry[PaperlessLookupData]


async def async_setup_entry(hass: HomeAssistant, entry: PaperlessLookupConfigEntry) -> bool:
    """Set up Paperless Lookup from a config entry."""
    client = create_client(hass, entry.data)
    try:
        user = await client.async_get_user()
    except PaperlessAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except PaperlessUnsupportedVersionError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="unsupported_version"
        ) from err
    except PaperlessPermissionError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="missing_permission",
            translation_placeholders={"permissions": "view_uisettings"},
        ) from err
    except PaperlessError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err

    if user.id != entry.data[CONF_PAPERLESS_USER_ID]:
        # The token now belongs to another Paperless user: ask for the right one.
        raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="wrong_account")
    if missing := missing_permissions(user):
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="missing_permission",
            translation_placeholders={"permissions": ", ".join(missing)},
        )

    entry.runtime_data = PaperlessLookupData(client=client, user=user)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PaperlessLookupConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
