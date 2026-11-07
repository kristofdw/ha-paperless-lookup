"""Pure functions that link documents to devices by model.

A document of a device category lists one or more models in a custom field, separated by ``;``
(for example ``RTCGQ11LM; MCCGQ11LM``). A device matches when one of those models equals,
after normalization, its ``model_id``, its ``model``, a part in parentheses of its ``model``
(Zigbee2MQTT style ``TRADFRI remote control (E1524/E1810)``), or one of these prefixed with the
manufacturer.
"""

from collections.abc import Iterable
from dataclasses import dataclass
import re
from typing import Final
from urllib.parse import quote

MODEL_SEPARATOR: Final = ";"
# Normalized models shorter than this are ignored: too likely to match by accident.
MIN_MODEL_LENGTH: Final = 3
ZIGBEE2MQTT_DEVICES_URL: Final = "https://www.zigbee2mqtt.io/devices/"

_IGNORED_CHARS = re.compile(r"[\s\-_/()]+")
_PARENTHESES = re.compile(r"\(([^()]*)\)")


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """The parts of a Home Assistant device that matter for matching."""

    id: str
    name: str
    manufacturer: str | None
    model: str | None
    model_id: str | None
    is_zigbee2mqtt: bool = False


def normalize(text: str) -> str:
    """Return a model in comparable form: case-insensitive, without spaces, ``-_/()``."""
    return _IGNORED_CHARS.sub("", text).casefold()


def split_models(value: object) -> tuple[str, ...]:
    """Return the models listed in a custom field value (``;``-separated)."""
    if not isinstance(value, str):
        return ()
    return tuple(part.strip() for part in value.split(MODEL_SEPARATOR) if part.strip())


def model_keys(models: Iterable[str]) -> frozenset[str]:
    """Return the normalized, long enough keys of document models."""
    keys = {normalize(model) for model in models}
    return frozenset(key for key in keys if len(key) >= MIN_MODEL_LENGTH)


def device_keys(device: DeviceInfo) -> frozenset[str]:
    """Return the normalized keys a document model may match for this device."""
    names: list[str] = []
    for value in (device.model_id, device.model):
        if value:
            names.append(value)
            names.extend(_PARENTHESES.findall(value))
    if device.manufacturer:
        names.extend([f"{device.manufacturer} {name}" for name in names])
    return model_keys(names)


def matches(document_keys: frozenset[str], device: DeviceInfo) -> bool:
    """Return whether a document (by its model keys) belongs to the device."""
    return not document_keys.isdisjoint(device_keys(device))


def zigbee2mqtt_url(device: DeviceInfo) -> str | None:
    """Return the Zigbee2MQTT documentation page of a Zigbee2MQTT device, if known."""
    model = device.model_id or device.model
    if not device.is_zigbee2mqtt or not model:
        return None
    page = re.sub(r"[\s/]+", "_", model.strip())
    return f"{ZIGBEE2MQTT_DEVICES_URL}{quote(page, safe='')}.html"
