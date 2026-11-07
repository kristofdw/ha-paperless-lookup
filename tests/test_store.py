"""Tests for the manual link store."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import UnsupportedStorageVersionError
import pytest

from custom_components.paperless_lookup.store import LinkStore, normalize_data

ENTRY_ID = "entry-1"
KEY = f"paperless_lookup.{ENTRY_ID}"


async def test_link_unlink_ignore(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test linking, unlinking and ignoring, and that it is saved."""
    store = LinkStore(hass, ENTRY_ID)
    await store.async_load()
    assert store.links("dev-a") == frozenset()
    assert not store.is_ignored("dev-a")

    await store.async_link("dev-a", 5)
    await store.async_link("dev-a", 3)
    await store.async_link("dev-a", 5)
    assert store.links("dev-a") == {3, 5}

    await store.async_unlink("dev-a", 5)
    await store.async_unlink("dev-a", 9)  # e.g. a document that matched by model
    assert store.links("dev-a") == {3}
    assert store.unlinks("dev-a") == {5, 9}

    await store.async_link("dev-a", 9)  # linking again cancels the unlink
    assert store.unlinks("dev-a") == {5}

    await store.async_set_ignored("dev-b", True)
    await store.async_set_ignored("dev-b", True)
    assert store.is_ignored("dev-b")

    saved = hass_storage[KEY]
    assert saved["version"] == 1
    assert saved["minor_version"] == 1
    assert saved["data"] == {
        "links": {"dev-a": [3, 9]},
        "unlinks": {"dev-a": [5]},
        "ignored": ["dev-b"],
    }

    reloaded = LinkStore(hass, ENTRY_ID)
    await reloaded.async_load()
    assert reloaded.data == store.data

    await store.async_set_ignored("dev-b", False)
    await store.async_unlink("dev-a", 3)
    await store.async_link("dev-a", 5)
    assert hass_storage[KEY]["data"] == {
        "links": {"dev-a": [5, 9]},
        "unlinks": {"dev-a": [3]},
        "ignored": [],
    }


async def test_remove_device(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test forgetting a removed device."""
    store = LinkStore(hass, ENTRY_ID)
    await store.async_load()
    await store.async_link("dev-a", 1)
    await store.async_unlink("dev-a", 2)
    await store.async_set_ignored("dev-a", True)
    await store.async_link("dev-b", 1)

    await store.async_remove_device("dev-a")
    await store.async_remove_device("dev-unknown")

    assert hass_storage[KEY]["data"] == {
        "links": {"dev-b": [1]},
        "unlinks": {},
        "ignored": [],
    }


async def test_remove_store(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test deleting the stored links."""
    store = LinkStore(hass, ENTRY_ID)
    await store.async_link("dev-a", 1)
    assert KEY in hass_storage

    await store.async_remove()

    assert KEY not in hass_storage


async def test_migrate_older_minor_version(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading data of an older minor version with missing and invalid parts."""
    hass_storage[KEY] = {
        "version": 1,
        "minor_version": 0,
        "key": KEY,
        "data": {"links": {"dev-a": [2, 1, "x", 2], "dev-b": [], 3: [1]}, "ignored": "dev-c"},
    }
    store = LinkStore(hass, ENTRY_ID)

    await store.async_load()

    assert store.data == {"links": {"dev-a": [1, 2]}, "unlinks": {}, "ignored": []}


async def test_newer_major_version(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test that data from a newer major version is not silently discarded."""
    hass_storage[KEY] = {"version": 2, "minor_version": 1, "key": KEY, "data": {}}
    store = LinkStore(hass, ENTRY_ID)

    with pytest.raises(UnsupportedStorageVersionError):
        await store.async_load()


@pytest.mark.parametrize("raw", [None, [], "x", {"links": "x", "unlinks": None, "ignored": [1]}])
def test_normalize_garbage(raw: object) -> None:
    """Test that malformed data becomes empty data."""
    assert normalize_data(raw) == {"links": {}, "unlinks": {}, "ignored": []}
