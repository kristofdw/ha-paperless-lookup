"""Repair issues for problems the user can fix in Paperless or in the options."""

from typing import Final

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

ISSUE_UNSUPPORTED_VERSION: Final = "unsupported_version"
ISSUE_MISSING_PERMISSION: Final = "missing_permission"
ISSUE_ACCESS_TAG_MISSING: Final = "access_tag_missing"

_ALL_ISSUES: Final = (
    ISSUE_UNSUPPORTED_VERSION,
    ISSUE_MISSING_PERMISSION,
    ISSUE_ACCESS_TAG_MISSING,
)


def _issue_id(entry_id: str, key: str) -> str:
    """Return the id of an issue of a config entry."""
    return f"{key}_{entry_id}"


@callback
def async_raise_issue(
    hass: HomeAssistant,
    entry_id: str,
    key: str,
    *,
    severity: ir.IssueSeverity = ir.IssueSeverity.ERROR,
    placeholders: dict[str, str] | None = None,
) -> None:
    """Create a repair issue, or update the existing one."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _issue_id(entry_id, key),
        is_fixable=False,
        severity=severity,
        translation_key=key,
        translation_placeholders=placeholders,
    )


@callback
def async_clear_issue(hass: HomeAssistant, entry_id: str, key: str) -> None:
    """Delete a repair issue once the problem is solved."""
    ir.async_delete_issue(hass, DOMAIN, _issue_id(entry_id, key))


@callback
def async_clear_all_issues(hass: HomeAssistant, entry_id: str) -> None:
    """Delete the repair issues of a removed config entry."""
    for key in _ALL_ISSUES:
        async_clear_issue(hass, entry_id, key)
