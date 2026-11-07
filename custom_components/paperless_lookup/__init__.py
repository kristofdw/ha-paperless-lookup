"""The Paperless Lookup integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = []


@dataclass(slots=True)
class PaperlessLookupData:
    """Runtime data of a Paperless Lookup config entry.

    Filled in later phases (API client, coordinator, store).
    """


type PaperlessLookupConfigEntry = ConfigEntry[PaperlessLookupData]


async def async_setup_entry(hass: HomeAssistant, entry: PaperlessLookupConfigEntry) -> bool:
    """Set up Paperless Lookup from a config entry."""
    entry.runtime_data = PaperlessLookupData()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PaperlessLookupConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
