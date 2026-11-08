"""Config and options flow for the Paperless Lookup integration."""

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any, override

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import probatio

from .api import (
    PaperlessAuthError,
    PaperlessClient,
    PaperlessConnectionError,
    PaperlessError,
    PaperlessNotFoundError,
    PaperlessObject,
    PaperlessPermissionError,
    PaperlessResponseError,
    PaperlessUnsupportedVersionError,
    PaperlessUser,
)
from .const import (
    CONF_ACCESS_TAG,
    CONF_ADMINS_ALWAYS,
    CONF_CATEGORIES,
    CONF_DEVICE_CATEGORIES,
    CONF_MODEL_FIELD,
    CONF_PANEL_USERS,
    CONF_PAPERLESS_USER_ID,
    CONF_REFRESH_INTERVAL,
    CONF_ZIGBEE2MQTT_FALLBACK,
    DEFAULT_ADMINS_ALWAYS,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_ZIGBEE2MQTT_FALLBACK,
    DOMAIN,
    MAX_REFRESH_INTERVAL,
    MIN_REFRESH_INTERVAL,
)
from .helpers import (
    async_default_options,
    build_unique_id,
    create_client,
    has_write_access,
    missing_permissions,
)

if TYPE_CHECKING:
    from . import PaperlessLookupConfigEntry

_LOGGER = logging.getLogger(__name__)

STEP_INSECURE_HTTP = "insecure_http"
STEP_PERMISSIONS_WARNING = "permissions_warning"

_URL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.URL))
_TOKEN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): _URL_SELECTOR,
        probatio.Required(CONF_API_TOKEN): _TOKEN_SELECTOR,
        probatio.Required(CONF_VERIFY_SSL, default=True): BooleanSelector(),
    }
)
STEP_REAUTH_DATA_SCHEMA = probatio.Schema({probatio.Required(CONF_API_TOKEN): _TOKEN_SELECTOR})


class PaperlessLookupConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Paperless Lookup."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._data: dict[str, Any] = {}
        self._options: dict[str, Any] = {}
        self._user: PaperlessUser | None = None
        self._warnings: list[str] = []

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return PaperlessLookupOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            client, user = await self._async_validate(user_input, errors, placeholders)
            if client is not None and user is not None:
                await self.async_set_unique_id(build_unique_id(client.base_url, user.id))
                self._abort_if_unique_id_configured()
                try:
                    self._options = await async_default_options(client)
                except PaperlessError:
                    errors["base"] = "cannot_connect"
                else:
                    return await self._async_accept(client, user, user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, _without_token(user_input)
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start reauthentication after the token was rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API token."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            flow_input = {**entry.data, CONF_API_TOKEN: user_input[CONF_API_TOKEN]}
            client, user = await self._async_validate(flow_input, errors, placeholders)
            if client is not None and user is not None:
                self._abort_if_wrong_account(entry, user)
                return await self._async_accept(client, user, flow_input)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the URL, token or TLS verification."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            client, user = await self._async_validate(user_input, errors, placeholders)
            if client is not None and user is not None:
                self._abort_if_wrong_account(entry, user)
                return await self._async_accept(client, user, user_input)
        suggested = user_input or {
            CONF_URL: entry.data[CONF_URL],
            CONF_VERIFY_SSL: entry.data[CONF_VERIFY_SSL],
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, _without_token(suggested)
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_insecure_http(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Warn that the connection to Paperless is not encrypted."""
        if user_input is not None:
            self._warnings.remove(STEP_INSECURE_HTTP)
            return await self._async_next()
        return self.async_show_form(step_id=STEP_INSECURE_HTTP)

    async def async_step_permissions_warning(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Warn that the Paperless user can do more than read."""
        if user_input is not None:
            self._warnings.remove(STEP_PERMISSIONS_WARNING)
            return await self._async_next()
        return self.async_show_form(
            step_id=STEP_PERMISSIONS_WARNING,
            description_placeholders={"username": self._user_or_raise().username},
        )

    async def _async_validate(
        self,
        flow_input: Mapping[str, Any],
        errors: dict[str, str],
        placeholders: dict[str, str],
    ) -> tuple[PaperlessClient | None, PaperlessUser | None]:
        """Connect to Paperless and fill ``errors`` when that fails."""
        try:
            client = create_client(self.hass, flow_input)
        except ValueError:
            if str(flow_input.get(CONF_API_TOKEN, "")).strip():
                errors[CONF_URL] = "invalid_url"
            else:
                errors[CONF_API_TOKEN] = "invalid_auth"
            return None, None
        try:
            user = await client.async_get_user()
        except PaperlessAuthError:
            errors[CONF_API_TOKEN] = "invalid_auth"
        except PaperlessPermissionError:
            errors["base"] = "missing_permission"
            placeholders["permissions"] = "view_uisettings"
        except PaperlessUnsupportedVersionError:
            errors["base"] = "unsupported_version"
        except PaperlessNotFoundError, PaperlessResponseError:
            errors[CONF_URL] = "not_paperless"
        except PaperlessConnectionError:
            errors[CONF_URL] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error while connecting to Paperless")
            errors["base"] = "unknown"
        else:
            if missing := missing_permissions(user):
                errors["base"] = "missing_permission"
                placeholders["permissions"] = ", ".join(missing)
                return None, None
            return client, user
        return None, None

    def _abort_if_wrong_account(self, entry: ConfigEntry, user: PaperlessUser) -> None:
        """Abort when the token belongs to another Paperless user than before."""
        if user.id != entry.data[CONF_PAPERLESS_USER_ID]:
            raise AbortFlow("wrong_account")

    async def _async_accept(
        self, client: PaperlessClient, user: PaperlessUser, flow_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Store the validated input and show the warnings that apply."""
        self._user = user
        self._data = {
            CONF_URL: client.base_url,
            CONF_API_TOKEN: str(flow_input[CONF_API_TOKEN]).strip(),
            CONF_VERIFY_SSL: bool(flow_input.get(CONF_VERIFY_SSL, True)),
            CONF_PAPERLESS_USER_ID: user.id,
        }
        self._warnings = []
        if client.base_url.startswith("http://"):
            self._warnings.append(STEP_INSECURE_HTTP)
        if has_write_access(user):
            self._warnings.append(STEP_PERMISSIONS_WARNING)
        return await self._async_next()

    async def _async_next(self) -> ConfigFlowResult:
        """Show the next warning, or finish the flow."""
        if self._warnings:
            if self._warnings[0] == STEP_INSECURE_HTTP:
                return await self.async_step_insecure_http()
            return await self.async_step_permissions_warning()
        user = self._user_or_raise()
        unique_id = build_unique_id(self._data[CONF_URL], user.id)
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=self._data
            )
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), unique_id=unique_id, data_updates=self._data
            )
        return self.async_create_entry(title=user.username, data=self._data, options=self._options)

    def _user_or_raise(self) -> PaperlessUser:
        """Return the validated Paperless user."""
        if self._user is None:  # pragma: no cover - the steps always run after validation
            raise AbortFlow("unknown")
        return self._user


class PaperlessLookupOptionsFlow(OptionsFlowWithReload):
    """Options: access tag, categories and users, devices, refresh interval."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._document_types: dict[int, str] = {}
        self._selected_categories: list[int] = []
        self._user_field_keys: dict[str, int] = {}

    @property
    def _client(self) -> PaperlessClient:
        entry: PaperlessLookupConfigEntry = self.config_entry
        return entry.runtime_data.client

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the options menu."""
        if self.config_entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="not_loaded")
        return self.async_show_menu(
            step_id="init", menu_options=["access", "categories", "devices", "general"]
        )

    async def async_step_access(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the access tag and whether administrators see every category."""
        if user_input is not None:
            tag = user_input.get(CONF_ACCESS_TAG)
            return self._async_save(
                {
                    CONF_ACCESS_TAG: int(tag) if tag else None,
                    CONF_ADMINS_ALWAYS: user_input[CONF_ADMINS_ALWAYS],
                    CONF_PANEL_USERS: sorted(user_input.get(CONF_PANEL_USERS, [])),
                }
            )
        try:
            tags = await self._client.async_get_tags()
        except PaperlessError:
            return self.async_abort(reason="cannot_connect")
        options = self.config_entry.options
        user_selector, user_ids = await self._async_user_selector()
        schema = probatio.Schema(
            {
                probatio.Optional(CONF_ACCESS_TAG): _select(tags),
                probatio.Required(CONF_ADMINS_ALWAYS): BooleanSelector(),
                probatio.Optional(CONF_PANEL_USERS): user_selector,
            }
        )
        current_tag = options.get(CONF_ACCESS_TAG)
        suggested: dict[str, Any] = {
            CONF_ADMINS_ALWAYS: options.get(CONF_ADMINS_ALWAYS, DEFAULT_ADMINS_ALWAYS),
            CONF_PANEL_USERS: [uid for uid in options.get(CONF_PANEL_USERS, []) if uid in user_ids],
        }
        if current_tag in {tag.id for tag in tags}:
            suggested[CONF_ACCESS_TAG] = str(current_tag)
        return self.async_show_form(
            step_id="access", data_schema=self.add_suggested_values_to_schema(schema, suggested)
        )

    async def async_step_categories(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose which document types are categories in Home Assistant."""
        if user_input is not None:
            self._selected_categories = sorted(int(value) for value in user_input[CONF_CATEGORIES])
            if not self._selected_categories:
                return self._async_save_categories({})
            return await self.async_step_category_users()
        try:
            document_types = await self._client.async_get_document_types()
        except PaperlessError:
            return self.async_abort(reason="cannot_connect")
        self._document_types = {doc_type.id: doc_type.name for doc_type in document_types}
        current = [key for key in self._categories() if int(key) in self._document_types]
        schema = probatio.Schema(
            {probatio.Required(CONF_CATEGORIES): _select(document_types, multiple=True)}
        )
        return self.async_show_form(
            step_id="categories",
            data_schema=self.add_suggested_values_to_schema(schema, {CONF_CATEGORIES: current}),
        )

    async def async_step_category_users(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the Home Assistant users per category."""
        if user_input is not None:
            return self._async_save_categories(
                {
                    str(type_id): sorted(user_input.get(key, []))
                    for key, type_id in self._user_field_keys.items()
                }
            )
        user_selector, user_ids = await self._async_user_selector()
        self._user_field_keys = {}
        for type_id in self._selected_categories:
            key = self._document_types[type_id]
            if key in self._user_field_keys:
                key = f"{key} ({type_id})"
            self._user_field_keys[key] = type_id
        categories = self._categories()
        schema = probatio.Schema(
            {probatio.Optional(key): user_selector for key in self._user_field_keys}
        )
        suggested = {
            key: [uid for uid in categories.get(str(type_id), []) if uid in user_ids]
            for key, type_id in self._user_field_keys.items()
        }
        return self.async_show_form(
            step_id="category_users",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the device categories, the model field and the Zigbee2MQTT fallback."""
        if user_input is not None:
            field = user_input.get(CONF_MODEL_FIELD)
            return self._async_save(
                {
                    CONF_DEVICE_CATEGORIES: sorted(
                        int(value) for value in user_input.get(CONF_DEVICE_CATEGORIES, [])
                    ),
                    CONF_MODEL_FIELD: int(field) if field else None,
                    CONF_ZIGBEE2MQTT_FALLBACK: user_input[CONF_ZIGBEE2MQTT_FALLBACK],
                }
            )
        try:
            document_types = await self._client.async_get_document_types()
            custom_fields = await self._client.async_get_custom_fields()
        except PaperlessError:
            return self.async_abort(reason="cannot_connect")
        categories = self._categories()
        category_types = [doc_type for doc_type in document_types if str(doc_type.id) in categories]
        string_fields = [
            PaperlessObject(field.id, field.name)
            for field in custom_fields
            if field.data_type == "string"
        ]
        options = self.config_entry.options
        schema = probatio.Schema(
            {
                probatio.Optional(CONF_DEVICE_CATEGORIES): _select(category_types, multiple=True),
                probatio.Optional(CONF_MODEL_FIELD): _select(string_fields),
                probatio.Required(CONF_ZIGBEE2MQTT_FALLBACK): BooleanSelector(),
            }
        )
        suggested: dict[str, Any] = {
            CONF_DEVICE_CATEGORIES: [
                str(type_id)
                for type_id in options.get(CONF_DEVICE_CATEGORIES, [])
                if str(type_id) in categories
            ],
            CONF_ZIGBEE2MQTT_FALLBACK: options.get(
                CONF_ZIGBEE2MQTT_FALLBACK, DEFAULT_ZIGBEE2MQTT_FALLBACK
            ),
        }
        if options.get(CONF_MODEL_FIELD) in {field.id for field in string_fields}:
            suggested[CONF_MODEL_FIELD] = str(options[CONF_MODEL_FIELD])
        return self.async_show_form(
            step_id="devices", data_schema=self.add_suggested_values_to_schema(schema, suggested)
        )

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the refresh interval."""
        if user_input is not None:
            return self._async_save({CONF_REFRESH_INTERVAL: int(user_input[CONF_REFRESH_INTERVAL])})
        schema = probatio.Schema(
            {
                probatio.Required(CONF_REFRESH_INTERVAL): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_REFRESH_INTERVAL,
                        max=MAX_REFRESH_INTERVAL,
                        step=1,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.BOX,
                    )
                )
            }
        )
        suggested = {
            CONF_REFRESH_INTERVAL: self.config_entry.options.get(
                CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL
            )
        }
        return self.async_show_form(
            step_id="general", data_schema=self.add_suggested_values_to_schema(schema, suggested)
        )

    async def _async_user_selector(self) -> tuple[SelectSelector, set[str]]:
        """Return a multi-select of the Home Assistant users, and their ids."""
        users = [
            SelectOptionDict(value=user.id, label=user.name or user.id)
            for user in await self.hass.auth.async_get_users()
            if user.is_active and not user.system_generated
        ]
        selector = SelectSelector(
            SelectSelectorConfig(options=users, multiple=True, mode=SelectSelectorMode.LIST)
        )
        return selector, {option["value"] for option in users}

    def _categories(self) -> dict[str, list[str]]:
        """Return the current categories option."""
        return dict(self.config_entry.options.get(CONF_CATEGORIES, {}))

    def _async_save_categories(self, categories: dict[str, list[str]]) -> ConfigFlowResult:
        """Save the categories and drop device categories that are no longer categories."""
        device_categories = [
            type_id
            for type_id in self.config_entry.options.get(CONF_DEVICE_CATEGORIES, [])
            if str(type_id) in categories
        ]
        return self._async_save(
            {CONF_CATEGORIES: categories, CONF_DEVICE_CATEGORIES: device_categories}
        )

    def _async_save(self, changes: dict[str, Any]) -> ConfigFlowResult:
        """Merge changes into the options and finish."""
        return self.async_create_entry(data={**self.config_entry.options, **changes})


def _without_token(values: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return form values without the token: it is never sent back to the frontend."""
    return {key: value for key, value in (values or {}).items() if key != CONF_API_TOKEN}


def _select(objects: list[PaperlessObject], *, multiple: bool = False) -> SelectSelector:
    """Return a dropdown with Paperless objects (values are ids as strings)."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=str(obj.id), label=obj.name)
                for obj in sorted(objects, key=lambda obj: obj.name.casefold())
            ],
            multiple=multiple,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )
