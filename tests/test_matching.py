"""Tests for matching documents to devices (pure functions)."""

import pytest

from custom_components.paperless_lookup.matching import (
    DeviceInfo,
    device_keys,
    matches,
    model_keys,
    normalize,
    split_models,
    zigbee2mqtt_url,
)


def device(
    model: str | None = None,
    model_id: str | None = None,
    manufacturer: str | None = None,
    *,
    zigbee2mqtt: bool = False,
) -> DeviceInfo:
    """Return a device for the tests."""
    return DeviceInfo(
        id="dev",
        name="Device",
        manufacturer=manufacturer,
        model=model,
        model_id=model_id,
        is_zigbee2mqtt=zigbee2mqtt,
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("E1524/E1810", "e1524e1810"),
        (" rtcgq11lm ", "rtcgq11lm"),
        ("LCT-015_v2 / EU", "lct015v2eu"),
        ("Hue white  ambiance", "huewhiteambiance"),
        ("ÄQARA", "äqara"),
    ],
)
def test_normalize(text: str, expected: str) -> None:
    """Test case, spaces, - _ / are ignored."""
    assert normalize(text) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("RTCGQ11LM; MCCGQ11LM", ("RTCGQ11LM", "MCCGQ11LM")),
        ("E1524/E1810", ("E1524/E1810",)),
        (" ; W800 ;; ", ("W800",)),
        ("", ()),
        (None, ()),
        (42, ()),
    ],
)
def test_split_models(value: object, expected: tuple[str, ...]) -> None:
    """Test splitting the custom field on ;."""
    assert split_models(value) == expected


def test_model_keys_skip_short() -> None:
    """Test that very short models are ignored."""
    assert model_keys(["A1", "a-1", "W800", "w 800"]) == frozenset({"w800"})


@pytest.mark.parametrize(
    ("dev", "models", "expected"),
    [
        # Zigbee2MQTT (current): model is the description, model_id the Zigbee model.
        (device("TRADFRI remote control", "E1524/E1810", "IKEA"), ["E1524/E1810"], True),
        # Zigbee2MQTT (older): model "<description> (<model>)".
        (device("TRADFRI remote control (E1524/E1810)", None, "IKEA"), ["e1524 e1810"], True),
        # Several models per document.
        (device("Door sensor", "MCCGQ11LM", "Aqara"), ["RTCGQ11LM", "MCCGQ11LM"], True),
        # Manufacturer prefix in the document.
        (device("Hue bulb", "9290022169", "Philips"), ["Philips 9290022169"], True),
        # Match on the model name itself.
        (device("W800", None, "Demo Electronics"), ["w-800"], True),
        (device("STYRBAR remote", "E2001/E2002", "IKEA"), ["E1524/E1810"], False),
        (device(None, None, "IKEA"), ["IKEA"], False),
        (device("TRADFRI remote control", "E1524/E1810", "IKEA"), [], False),
    ],
)
def test_matches(dev: DeviceInfo, models: list[str], expected: bool) -> None:
    """Test device/document matching."""
    assert matches(model_keys(models), dev) is expected


def test_device_keys() -> None:
    """Test the keys of a Zigbee2MQTT style device."""
    keys = device_keys(device("Remote (E1524/E1810)", "E1524/E1810", "IKEA"))

    assert keys == {"remotee1524e1810", "e1524e1810", "ikeae1524e1810", "ikearemotee1524e1810"}


@pytest.mark.parametrize(
    ("dev", "expected"),
    [
        (
            device("TRADFRI remote control", "E1524/E1810", "IKEA", zigbee2mqtt=True),
            "https://www.zigbee2mqtt.io/devices/E1524_E1810.html",
        ),
        (
            device("RTCGQ11LM", None, zigbee2mqtt=True),
            "https://www.zigbee2mqtt.io/devices/RTCGQ11LM.html",
        ),
        (
            device("Odd model#1", None, zigbee2mqtt=True),
            "https://www.zigbee2mqtt.io/devices/Odd_model%231.html",
        ),
        (device("TRADFRI remote control", "E1524/E1810", "IKEA"), None),
        (device(None, None, zigbee2mqtt=True), None),
    ],
)
def test_zigbee2mqtt_url(dev: DeviceInfo, expected: str | None) -> None:
    """Test the Zigbee2MQTT fallback link."""
    assert zigbee2mqtt_url(dev) == expected
