"""Constants for the Paperless Lookup integration."""

from typing import Final

DOMAIN: Final = "paperless_lookup"
NAME: Final = "Paperless Lookup"

# Config entry data (besides url, api_token and verify_ssl).
CONF_PAPERLESS_USER_ID: Final = "paperless_user_id"

# Options.
CONF_ACCESS_TAG: Final = "access_tag"  # Paperless tag id, or None.
# {"<document type id>": [Home Assistant user ids]}; the keys are the enabled categories.
CONF_CATEGORIES: Final = "categories"
CONF_ADMINS_ALWAYS: Final = "admins_always"
# Home Assistant user ids that see the sidebar item; empty means every user.
CONF_PANEL_USERS: Final = "panel_users"
CONF_DEVICE_CATEGORIES: Final = "device_categories"  # Document type ids (subset of categories).
CONF_MODEL_FIELD: Final = "model_field"  # Paperless custom field id, or None.
CONF_ZIGBEE2MQTT_FALLBACK: Final = "zigbee2mqtt_fallback"
CONF_REFRESH_INTERVAL: Final = "refresh_interval"  # Minutes.

# Defaults, matched case-insensitively against the names in Paperless when the entry is created.
DEFAULT_ACCESS_TAG_NAME: Final = "HA"
DEFAULT_DEVICE_CATEGORY_NAMES: Final = frozenset(
    {"manual", "manuals", "handleiding", "handleidingen"}
)
DEFAULT_MODEL_FIELD_NAME: Final = "HA model"
DEFAULT_ADMINS_ALWAYS: Final = True
DEFAULT_ZIGBEE2MQTT_FALLBACK: Final = False
DEFAULT_REFRESH_INTERVAL: Final = 60
MIN_REFRESH_INTERVAL: Final = 5
MAX_REFRESH_INTERVAL: Final = 1440

# Paperless model permissions the integration needs (it never writes).
REQUIRED_PERMISSIONS: Final = (
    "view_document",
    "view_tag",
    "view_documenttype",
    "view_correspondent",
    "view_customfield",
    "view_uisettings",
)
WRITE_PERMISSION_PREFIXES: Final = ("add_", "change_", "delete_")
