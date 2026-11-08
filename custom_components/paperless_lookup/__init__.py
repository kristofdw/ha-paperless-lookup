"""The Paperless Lookup integration."""

from dataclasses import dataclass

from homeassistant.auth import EVENT_USER_ADDED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .api import (
    PaperlessAuthError,
    PaperlessClient,
    PaperlessError,
    PaperlessPermissionError,
    PaperlessUnsupportedVersionError,
    PaperlessUser,
)
from .const import CONF_PANEL_USERS, CONF_PAPERLESS_USER_ID, DOMAIN
from .coordinator import PaperlessLookupCoordinator
from .helpers import create_client, missing_permissions
from .panel import (
    async_register_frontend,
    async_register_panel,
    async_remove_panel,
    async_sync_panel_visibility,
)
from .store import LinkStore
from .views import PaperlessDocumentView
from .websocket_api import async_register as async_register_websocket_api

PLATFORMS: list[Platform] = []
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
DATA_MODULE_URL: HassKey[str] = HassKey(f"{DOMAIN}_module_url")


@dataclass(slots=True)
class PaperlessLookupData:
    """Runtime data of a Paperless Lookup config entry."""

    client: PaperlessClient
    user: PaperlessUser
    coordinator: PaperlessLookupCoordinator
    store: LinkStore


type PaperlessLookupConfigEntry = ConfigEntry[PaperlessLookupData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the websocket API, the document view and the frontend bundle (once)."""
    async_register_websocket_api(hass)
    hass.http.register_view(PaperlessDocumentView(hass))
    hass.data[DATA_MODULE_URL] = await async_register_frontend(hass)
    return True


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

    store = LinkStore(hass, entry.entry_id)
    await store.async_load()
    coordinator = PaperlessLookupCoordinator(hass, entry, client, store)
    await coordinator.async_config_entry_first_refresh()
    # The coordinator only refreshes periodically while it has listeners; the index is used by
    # the websocket API and the panel, not by entities, so keep one listener for the lifetime.
    entry.async_on_unload(coordinator.async_add_listener(lambda: None))

    entry.runtime_data = PaperlessLookupData(
        client=client, user=user, coordinator=coordinator, store=store
    )

    @callback
    def _device_removed(event: Event[dr.EventDeviceRegistryUpdatedData]) -> None:
        """Forget the manual links of a removed device."""
        if event.data["action"] == "remove":
            entry.async_create_background_task(
                hass,
                store.async_remove_device(event.data["device_id"]),
                "paperless_lookup_remove_device_links",
            )

    entry.async_on_unload(hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, _device_removed))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_register_panel(hass, hass.data[DATA_MODULE_URL])
    entry.async_on_unload(lambda: async_remove_panel(hass))

    panel_users = list(entry.options.get(CONF_PANEL_USERS, []))
    await async_sync_panel_visibility(hass, store, panel_users)

    @callback
    def _user_added(_event: Event) -> None:
        """Apply the sidebar choice to a new user."""
        entry.async_create_background_task(
            hass,
            async_sync_panel_visibility(hass, store, panel_users),
            "paperless_lookup_sync_panel_visibility",
        )

    entry.async_on_unload(hass.bus.async_listen(EVENT_USER_ADDED, _user_added))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PaperlessLookupConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: PaperlessLookupConfigEntry) -> None:
    """Show the sidebar item again where it was hidden and delete the stored links."""
    store = LinkStore(hass, entry.entry_id)
    await store.async_load()
    await async_sync_panel_visibility(hass, store, [])
    await store.async_remove()
