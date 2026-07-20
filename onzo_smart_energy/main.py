#!/usr/bin/env python3
"""Auto-discover and publish one Home Assistant device per Onzo meter."""

from __future__ import annotations

import json
import logging
import math
import os
import signal
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

import hid
import paho.mqtt.client as mqtt

import discovery
import runtime
from protocol import Clamp, Connection

APP_VERSION = "1.0.1"
LOG = logging.getLogger("onzo")


def load_options(path: Path = Path("/data/options.json")) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "vid": "04d8",
        "pid": "003f",
        "scan_interval": 10,
        "poll_interval": 2,
        "meters": [],
    }
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("options.json must contain an object")
        defaults.update(loaded)
    return defaults


def usb_id(value: str | int) -> int:
    return int(str(value).lower().removeprefix("0x"), 16)


def supervisor_mqtt_service() -> dict[str, Any]:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN is unavailable")
    request = urllib.request.Request(
        "http://supervisor/services/mqtt",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.load(response)
    service = payload.get("data", payload)
    if not isinstance(service, dict) or not service.get("host"):
        raise RuntimeError("Supervisor returned no usable MQTT service")
    return service


class Publisher:
    def __init__(self, service: dict[str, Any]):
        self.meters: dict[str, str] = {}
        self.lock = threading.Lock()
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="onzo-smart-energy",
            protocol=mqtt.MQTTv311,
        )
        if service.get("username"):
            self.client.username_pw_set(service["username"], service.get("password"))
        if service.get("ssl"):
            self.client.tls_set()
        self.client.will_set(
            discovery.app_availability_topic(), "offline", qos=1, retain=True
        )
        self.client.on_connect = self._on_connect
        self.client.on_connect_fail = self._on_connect_fail
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.enable_logger(LOG)
        LOG.info(
            "Connecting to MQTT service at %s:%s (TLS: %s)",
            service["host"],
            service.get("port", 1883),
            bool(service.get("ssl")),
        )
        self.client.connect_async(
            str(service["host"]), int(service.get("port", 1883)), keepalive=60
        )
        self.client.loop_start()

    def _publish(self, topic: str, payload: str, *, qos: int, retain: bool) -> None:
        result = self.client.publish(topic, payload, qos=qos, retain=retain)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            LOG.error(
                "MQTT publish failed for %s: %s",
                topic,
                mqtt.error_string(result.rc),
            )

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            LOG.error("MQTT connection failed: %s", reason_code)
            return
        LOG.info("Connected to the Home Assistant MQTT service")
        self._publish(
            discovery.app_availability_topic(), "online", qos=1, retain=True
        )
        client.subscribe("homeassistant/status", qos=1)
        self.publish_all_discovery()

    def _on_connect_fail(self, client, userdata):
        LOG.error("Could not connect to the Home Assistant MQTT service; retrying")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        if reason_code != 0:
            LOG.warning("Disconnected from MQTT: %s; retrying", reason_code)

    def _on_message(self, client, userdata, message):
        if message.topic == "homeassistant/status" and message.payload == b"online":
            self.publish_all_discovery()

    def register(self, serial: str, name: str) -> None:
        with self.lock:
            self.meters[serial] = name
        self.publish_discovery(serial, name)

    def publish_discovery(self, serial: str, name: str) -> None:
        for topic, payload in discovery.messages(serial, name, APP_VERSION):
            self._publish(topic, payload, qos=1, retain=True)
        self._publish(
            discovery.availability_topic(serial), "online", qos=1, retain=True
        )

    def publish_all_discovery(self) -> None:
        with self.lock:
            meters = tuple(self.meters.items())
        for serial, name in meters:
            self.publish_discovery(serial, name)

    def state(self, serial: str, values: dict[str, Any]) -> None:
        self._publish(
            discovery.state_topic(serial),
            discovery.state_payload(values),
            qos=0,
            retain=True,
        )

    def offline(self, serial: str) -> None:
        self._publish(
            discovery.availability_topic(serial), "offline", qos=1, retain=True
        )

    def close(self) -> None:
        with self.lock:
            serials = tuple(self.meters)
        for serial in serials:
            self.offline(serial)
        self.client.publish(
            discovery.app_availability_topic(), "offline", qos=1, retain=True
        ).wait_for_publish(timeout=2)
        self.client.disconnect()
        self.client.loop_stop()


class MeterWorker(threading.Thread):
    def __init__(self, path, publisher: Publisher, names: dict[str, str], poll_interval: float):
        super().__init__(daemon=True)
        self.path = path
        self.publisher = publisher
        self.names = names
        self.poll_interval = poll_interval
        self.stop_event = threading.Event()
        self.serial = None

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        connection = Connection(self.path)
        try:
            connection.connect()
            clamp = Clamp(connection)
            self.serial = discovery.normalize_serial(clamp.get_serial())
            name = self.names.get(self.serial, f"Onzo {self.serial}")
            LOG.info("Discovered %s on HID path %r", name, self.path)
            self.publisher.register(self.serial, name)
            reactive_power = None
            battery_voltage = None
            temperature = None
            next_reactive = 0.0
            next_slow = 0.0
            while not self.stop_event.is_set():
                now = time.monotonic()
                power = clamp.get_power()
                if now >= next_reactive or reactive_power is None:
                    reactive_power = clamp.get_powervars()
                    next_reactive = now + 15
                if now >= next_slow or battery_voltage is None:
                    battery_voltage = clamp.get_batteryvolts()
                    temperature = clamp.get_temperature()
                    next_slow = now + 600
                values = {
                    "power": power,
                    "reactive_power": reactive_power,
                    "apparent_power": round(math.hypot(power, reactive_power)),
                    "energy": clamp.get_cumulative_kwh(),
                    "battery_voltage": battery_voltage,
                    "temperature": temperature,
                    "mains_voltage": clamp.get_voltage(),
                }
                self.publisher.state(self.serial, values)
                self.stop_event.wait(self.poll_interval)
        except Exception:
            LOG.exception("Onzo meter on HID path %r disconnected", self.path)
        finally:
            if self.serial:
                self.publisher.offline(self.serial)
            connection.disconnect()


class MeterManager:
    def __init__(self, options: dict[str, Any], publisher: Publisher):
        self.vid = usb_id(options["vid"])
        self.pid = usb_id(options["pid"])
        self.scan_interval = float(options["scan_interval"])
        self.poll_interval = float(options["poll_interval"])
        self.names = discovery.name_overrides(options.get("meters", []))
        self.publisher = publisher
        self.workers: dict[object, MeterWorker] = {}
        self.stop_event = threading.Event()

    def run(self) -> None:
        while not self.stop_event.is_set():
            paths = runtime.device_paths(hid.enumerate(self.vid, self.pid))
            for key, worker in tuple(self.workers.items()):
                if key not in paths or not worker.is_alive():
                    worker.stop()
                    worker.join(timeout=2)
                    del self.workers[key]
            for key, path in paths.items():
                if key not in self.workers:
                    worker = MeterWorker(path, self.publisher, self.names, self.poll_interval)
                    self.workers[key] = worker
                    worker.start()
            if not paths:
                LOG.info("No Onzo USB meters found; scanning again in %s seconds", self.scan_interval)
            self.stop_event.wait(self.scan_interval)

    def stop(self) -> None:
        self.stop_event.set()
        for worker in self.workers.values():
            worker.stop()
        for worker in self.workers.values():
            worker.join(timeout=5)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    options = load_options()
    LOG.info(
        "Starting Onzo Smart Energy Meter %s (USB %04x:%04x, scan every %ss, poll every %ss)",
        APP_VERSION,
        usb_id(options["vid"]),
        usb_id(options["pid"]),
        options["scan_interval"],
        options["poll_interval"],
    )
    LOG.info("Requesting MQTT connection details from Supervisor")
    publisher = Publisher(supervisor_mqtt_service())
    manager = MeterManager(options, publisher)

    def stop(signum, frame):
        manager.stop_event.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        manager.run()
    finally:
        manager.stop()
        publisher.close()


if __name__ == "__main__":
    main()
