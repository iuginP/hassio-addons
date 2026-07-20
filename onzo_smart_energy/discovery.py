"""MQTT discovery and identity helpers for Onzo meters."""

from __future__ import annotations

import json
from typing import Any

SENSORS = {
    "power": ("Power", "power", "W", "measurement"),
    "reactive_power": ("Reactive power", "reactive_power", "var", "measurement"),
    "apparent_power": ("Apparent power", "apparent_power", "VA", "measurement"),
    "energy": ("Energy", "energy", "kWh", "total_increasing"),
    "battery_voltage": ("Clamp battery", "voltage", "V", "measurement"),
    "temperature": ("Clamp temperature", "temperature", "°C", "measurement"),
    "mains_voltage": ("Mains voltage", "voltage", "V", "measurement"),
}


def normalize_serial(value: str | int) -> str:
    text = str(value).strip().lower()
    if text.startswith("0x"):
        number = int(text, 16)
    elif any(character in "abcdef" for character in text):
        number = int(text, 16)
    else:
        number = int(text, 10)
    return f"{number:08x}"


def name_overrides(configured: list[dict[str, str]]) -> dict[str, str]:
    return {
        normalize_serial(item["serial"]): item["name"].strip()
        for item in configured
        if item.get("serial") and item.get("name", "").strip()
    }


def state_topic(serial: str) -> str:
    return f"onzo/{serial}/state"


def availability_topic(serial: str) -> str:
    return f"onzo/{serial}/status"


def app_availability_topic() -> str:
    return "onzo/status"


def messages(serial: str, name: str, app_version: str = "1.0.0") -> list[tuple[str, str]]:
    device_id = f"onzo_{serial}"
    device = {
        "identifiers": [device_id],
        "name": name,
        "manufacturer": "Onzo",
        "model": "Smart Energy Meter",
        "serial_number": serial,
    }
    origin = {
        "name": "Onzo Smart Energy Home Assistant app",
        "sw_version": app_version,
        "support_url": "https://github.com/iuginP/hassio-addons/tree/main/onzo_smart_energy",
    }
    result = []
    for key, (label, device_class, unit, state_class) in SENSORS.items():
        object_id = f"{device_id}_{key}"
        payload: dict[str, Any] = {
            "name": label,
            "object_id": object_id,
            "unique_id": object_id,
            "state_topic": state_topic(serial),
            "availability": [
                {"topic": app_availability_topic()},
                {"topic": availability_topic(serial)},
            ],
            "availability_mode": "all",
            "value_template": "{{ value_json.%s }}" % key,
            "device_class": device_class,
            "unit_of_measurement": unit,
            "state_class": state_class,
            "device": device,
            "origin": origin,
        }
        topic = f"homeassistant/sensor/{device_id}/{key}/config"
        result.append((topic, json.dumps(payload, ensure_ascii=False, separators=(",", ":"))))
    clamp_serial_id = f"{device_id}_clamp_serial"
    clamp_serial_payload = {
        "name": "Clamp serial",
        "object_id": clamp_serial_id,
        "unique_id": clamp_serial_id,
        "state_topic": state_topic(serial),
        "availability": [
            {"topic": app_availability_topic()},
            {"topic": availability_topic(serial)},
        ],
        "availability_mode": "all",
        "value_template": "{{ value_json.clamp_serial }}",
        "entity_category": "diagnostic",
        "enabled_by_default": True,
        "device": device,
        "origin": origin,
    }
    result.append(
        (
            f"homeassistant/sensor/{device_id}/clamp_serial/config",
            json.dumps(
                clamp_serial_payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
    )
    hid_path_id = f"{device_id}_hid_path"
    hid_path_payload = {
        "name": "HID path",
        "object_id": hid_path_id,
        "unique_id": hid_path_id,
        "state_topic": state_topic(serial),
        "availability": [
            {"topic": app_availability_topic()},
            {"topic": availability_topic(serial)},
        ],
        "availability_mode": "all",
        "value_template": "{{ value_json.hid_path }}",
        "entity_category": "diagnostic",
        "enabled_by_default": False,
        "device": device,
        "origin": origin,
    }
    result.append(
        (
            f"homeassistant/sensor/{device_id}/hid_path/config",
            json.dumps(hid_path_payload, ensure_ascii=False, separators=(",", ":")),
        )
    )
    return result


def state_payload(values: dict[str, Any]) -> str:
    state_keys = (*SENSORS, "clamp_serial", "hid_path")
    state = {key: values[key] for key in state_keys if values.get(key) is not None}
    return json.dumps(state, allow_nan=False, separators=(",", ":"))
