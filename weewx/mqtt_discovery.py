"""Home Assistant MQTT discovery definitions for WeeWX observations."""

from __future__ import annotations

import json
import math
from typing import Any

STATE_TOPIC = "weewx/weather/state"
AVAILABILITY_TOPIC = "weewx/weather/status"
DEVICE_ID = "weewx_weather_station"

SENSORS = {
    "outTemp": (
        "Outside temperature", "temperature", "°C", "measurement", None
    ),
    "outHumidity": (
        "Outside humidity", "humidity", "%", "measurement", None
    ),
    "inTemp": ("Indoor temperature", "temperature", "°C", "measurement", None),
    "inHumidity": ("Indoor humidity", "humidity", "%", "measurement", None),
    "inDewpoint": ("Indoor dew point", "temperature", "°C", "measurement", None),
    "appTemp": ("Apparent temperature", "temperature", "°C", "measurement", None),
    "humidex": ("Humidex", "temperature", "°C", "measurement", None),
    "dewpoint": ("Dew point", "temperature", "°C", "measurement", None),
    "windchill": ("Wind chill", "temperature", "°C", "measurement", None),
    "heatindex": ("Heat index", "temperature", "°C", "measurement", None),
    "pressure": (
        "Station pressure", "atmospheric_pressure", "hPa", "measurement", None
    ),
    "barometer": (
        "Barometric pressure", "atmospheric_pressure", "hPa", "measurement", None
    ),
    "altimeter": (
        "Altimeter setting", "atmospheric_pressure", "hPa", "measurement", None
    ),
    "cloudbase": ("Cloud base", "distance", "m", "measurement", None),
    "windSpeed": ("Wind speed", "wind_speed", "m/s", "measurement", None),
    "windGust": ("Wind gust", "wind_speed", "m/s", "measurement", None),
    "windDir": (
        "Wind direction", "wind_direction", "°", "measurement_angle", None
    ),
    "rainRate": (
        "Rain rate", "precipitation_intensity", "mm/h", "measurement", None
    ),
    "rain": ("Rain", "precipitation", "mm", "measurement", None),
    "dayRain": (
        "Daily rain", "precipitation", "mm", "total_increasing", None
    ),
    "rainTotal": (
        "Cumulative rain", "precipitation", "mm", "total_increasing", None
    ),
    "windrun": ("Wind run", "distance", "km", "measurement", None),
    "radiation": (
        "Solar radiation", "irradiance", "W/m²", "measurement", None
    ),
    "UV": ("UV index", None, None, "measurement", "mdi:sun-wireless"),
    "rxCheckPercent": (
        "Reception quality", None, "%", "measurement", "mdi:signal"
    ),
}

DIAGNOSTIC_SENSORS = {"rxCheckPercent"}

BINARY_SENSORS = {
    "outTempBatteryStatus": ("Outdoor sensor battery", "battery", "1", "0"),
}


def _slug(observation: str) -> str:
    characters = []
    for character in observation:
        if character.isupper() and characters:
            characters.append("_")
        characters.append(character.lower())
    return "".join(characters)


def discovery_messages(location: str, app_version: str) -> list[tuple[str, str]]:
    """Return retained discovery topic/payload pairs for all supported sensors."""
    messages = []
    device = {
        "identifiers": [DEVICE_ID],
        "name": location,
        "manufacturer": "WeeWX",
        "model": "Weather station",
        "sw_version": "5.4.0",
    }
    origin = {
        "name": "WeeWX Home Assistant app",
        "sw_version": app_version,
        "support_url": "https://github.com/iuginP/hassio-addons/tree/main/weewx",
    }
    for observation, (name, device_class, unit, state_class, icon) in SENSORS.items():
        object_id = f"weewx_{_slug(observation)}"
        payload: dict[str, Any] = {
            "name": name,
            "object_id": object_id,
            "unique_id": object_id,
            "state_topic": STATE_TOPIC,
            "availability_topic": AVAILABILITY_TOPIC,
            "value_template": "{{ value_json.%s }}" % observation,
            "state_class": state_class,
            "device": device,
            "origin": origin,
        }
        if device_class:
            payload["device_class"] = device_class
        if unit:
            payload["unit_of_measurement"] = unit
        if icon:
            payload["icon"] = icon
        if observation in DIAGNOSTIC_SENSORS:
            payload["entity_category"] = "diagnostic"
        topic = f"homeassistant/sensor/{DEVICE_ID}/{_slug(observation)}/config"
        messages.append(
            (topic, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        )
    for observation, (
        name,
        device_class,
        payload_on,
        payload_off,
    ) in BINARY_SENSORS.items():
        object_id = f"weewx_{_slug(observation)}"
        payload = {
            "name": name,
            "object_id": object_id,
            "unique_id": object_id,
            "state_topic": STATE_TOPIC,
            "availability_topic": AVAILABILITY_TOPIC,
            "value_template": (
                f"{{% if value_json.{observation} is defined %}}"
                f"{{{{ value_json.{observation} | int }}}}"
                "{% endif %}"
            ),
            "device_class": device_class,
            "entity_category": "diagnostic",
            "payload_on": payload_on,
            "payload_off": payload_off,
            "device": device,
            "origin": origin,
        }
        topic = (
            f"homeassistant/binary_sensor/{DEVICE_ID}/{_slug(observation)}/config"
        )
        messages.append(
            (topic, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        )
    return messages


def state_payload(record: dict[str, Any]) -> str:
    """Serialize supported, finite observations from a METRICWX LOOP packet."""
    state = {}
    for observation in SENSORS | BINARY_SENSORS:
        value = record.get(observation)
        if value is None:
            continue
        if isinstance(value, float) and not math.isfinite(value):
            continue
        state[observation] = value
    return json.dumps(state, allow_nan=False, separators=(",", ":"))
