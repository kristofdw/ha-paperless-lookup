"""The Paperless Lookup integration."""

from dataclasses import dataclass, field

from homeassistant.auth import EVENT_USER_ADDED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .api import (
    FileKind,
    PaperlessAuthError,
    PaperlessClient,
    PaperlessError,
    PaperlessPermissionError,
    PaperlessUnsupportedVersionError,
    PaperlessUser,
)
from .const import CONF_FOLLOW_READS, CONF_PANEL_USERS, CONF_PAPERLESS_USER_ID, DOMAIN
from .coordinator import PaperlessLookupCoordinator
from .helpers import create_client, missing_permissions
from .issues import (
    ISSUE_MISSING_PERMISSION,
    ISSUE_UNSUPPORTED_VERSION,
    async_clear_all_issues,
    async_clear_issue,
    async_raise_issue,
)
from .panel import (
    async_register_frontend,
    async_register_panel,
    async_remove_panel,
    async_sync_panel_visibility,
)
from .read_log import async_service_device
from .store import LinkStore
from .views import PaperlessDocumentView
from .websocket_api import async_register as async_register_websocket_api

PLATFORMS: list[Platform] = []
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
DATA_MODULE_URL: HassKey[str] = HassKey(f"{DOMAIN}_module_url")
_LEGACY_REFRESH_INTERVAL = "refresh_interval"  # Option removed in config entry version 1.2.
# {"<document type id>": [user ids]}, replaced in config entry version 1.3 by follow_reads per user.
_LEGACY_READ_LOG = "read_log"


@dataclass(slots=True)
class PaperlessLookupData:
    """Runtime data of a Paperless Lookup config entry."""

    client: PaperlessClient
    user: PaperlessUser
    coordinator: PaperlessLookupCoordinator
    store: LinkStore
    # Service device that the logbook entries of document reads belong to.
    device_id: str
    # (user id, document id, file kind) -> monotonic time of the last logged read.
    read_log_seen: dict[tuple[str, int, FileKind], float] = field(default_factory=dict)


type PaperlessLookupConfigEntry = ConfigEntry[PaperlessLookupData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the websocket API, the document view and the frontend bundle (once)."""
    async_register_websocket_api(hass)
    hass.http.register_view(PaperlessDocumentView(hass))
    hass.data[DATA_MODULE_URL] = await async_register_frontend(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: PaperlessLookupConfigEntry) -> bool:
    """Migrate an older config entry (Home Assistant refuses newer major versions itself)."""
    if entry.minor_version < 2:
        options = {
            key: value for key, value in entry.options.items() if key != _LEGACY_REFRESH_INTERVAL
        }
        hass.config_entries.async_update_entry(entry, options=options, minor_version=2)
    if entry.minor_version < 3:
        options = dict(entry.options)
        follow: dict[str, set[int]] = {}
        for type_id, user_ids in options.pop(_LEGACY_READ_LOG, {}).items():
            for user_id in user_ids:
                follow.setdefault(user_id, set()).add(int(type_id))
        if follow:
            options[CONF_FOLLOW_READS] = {
                user_id: sorted(type_ids) for user_id, type_ids in follow.items()
            }
        hass.config_entries.async_update_entry(entry, options=options, minor_version=3)
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
        async_raise_issue(hass, entry.entry_id, ISSUE_UNSUPPORTED_VERSION)
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="unsupported_version"
        ) from err
    except PaperlessPermissionError as err:
        async_raise_issue(
            hass,
            entry.entry_id,
            ISSUE_MISSING_PERMISSION,
            placeholders={"permissions": "view_uisettings"},
        )
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="missing_permission",
            translation_placeholders={"permissions": "view_uisettings"},
        ) from err
    except PaperlessError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err

    async_clear_issue(hass, entry.entry_id, ISSUE_UNSUPPORTED_VERSION)
    if user.id != entry.data[CONF_PAPERLESS_USER_ID]:
        # The token now belongs to another Paperless user: ask for the right one.
        raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="wrong_account")
    if missing := missing_permissions(user):
        permissions = ", ".join(missing)
        async_raise_issue(
            hass,
            entry.entry_id,
            ISSUE_MISSING_PERMISSION,
            placeholders={"permissions": permissions},
        )
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="missing_permission",
            translation_placeholders={"permissions": permissions},
        )
    async_clear_issue(hass, entry.entry_id, ISSUE_MISSING_PERMISSION)

    store = LinkStore(hass, entry.entry_id)
    await store.async_load()
    coordinator = PaperlessLookupCoordinator(hass, entry, client, store)
    await coordinator.async_config_entry_first_refresh()
    # The coordinator only refreshes periodically while it has listeners; the index is used by
    # the websocket API and the panel, not by entities, so keep one listener for the lifetime.
    entry.async_on_unload(coordinator.async_add_listener(lambda: None))

    entry.runtime_data = PaperlessLookupData(
        client=client,
        user=user,
        coordinator=coordinator,
        store=store,
        device_id=async_service_device(hass, entry),
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
    """Show the sidebar item again where it was hidden and delete what the entry stored."""
    async_clear_all_issues(hass, entry.entry_id)
    store = LinkStore(hass, entry.entry_id)
    await store.async_load()
    await async_sync_panel_visibility(hass, store, [])
    await store.async_remove()
