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
    return result


def state_payload(values: dict[str, Any]) -> str:
    state = {key: values[key] for key in SENSORS if values.get(key) is not None}
    return json.dumps(state, allow_nan=False, separators=(",", ":"))
