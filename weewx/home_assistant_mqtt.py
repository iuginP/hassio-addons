"""WeeWX service that publishes observations using Home Assistant discovery."""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Any

import paho.mqtt.client as mqtt
import weewx
import weewx.units
from weewx.engine import StdService

from user import mqtt_discovery

LOG = logging.getLogger(__name__)
APP_VERSION = "1.3.1"


def supervisor_mqtt_service() -> dict[str, Any]:
    """Fetch the broker connection supplied to this app by Supervisor."""
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


class HomeAssistantMQTT(StdService):
    """Publish processed WeeWX LOOP packets and discovery metadata."""

    def __init__(self, engine: Any, config_dict: dict[str, Any]) -> None:
        super().__init__(engine, config_dict)
        service = supervisor_mqtt_service()
        self.location = str(config_dict.get("Station", {}).get("location", "WeeWX"))
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="weewx-home-assistant",
            protocol=mqtt.MQTTv311,
        )
        username = service.get("username")
        if username:
            self.client.username_pw_set(username, service.get("password"))
        if service.get("ssl"):
            self.client.tls_set()
        self.client.will_set(
            mqtt_discovery.AVAILABILITY_TOPIC, "offline", qos=1, retain=True
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.enable_logger(LOG)
        self.client.connect_async(
            str(service["host"]), int(service.get("port", 1883)), keepalive=60
        )
        self.client.loop_start()
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)

    def _publish_discovery(self) -> None:
        for topic, payload in mqtt_discovery.discovery_messages(
            self.location, APP_VERSION
        ):
            self.client.publish(topic, payload, qos=1, retain=True)
        self.client.publish(
            mqtt_discovery.AVAILABILITY_TOPIC, "online", qos=1, retain=True
        )

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code != 0:
            LOG.error("MQTT connection failed: %s", reason_code)
            return
        LOG.info("Connected to the Home Assistant MQTT service")
        client.subscribe("homeassistant/status", qos=1)
        self._publish_discovery()

    def _on_message(
        self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        if message.topic == "homeassistant/status" and message.payload == b"online":
            self._publish_discovery()

    def new_loop_packet(self, event: Any) -> None:
        metric_record = weewx.units.to_std_system(
            dict(event.packet), weewx.METRICWX
        )
        payload = mqtt_discovery.state_payload(metric_record)
        if payload != "{}":
            self.client.publish(
                mqtt_discovery.STATE_TOPIC, payload, qos=0, retain=True
            )

    def shutDown(self) -> None:
        message = self.client.publish(
            mqtt_discovery.AVAILABILITY_TOPIC, "offline", qos=1, retain=True
        )
        message.wait_for_publish(timeout=2)
        self.client.disconnect()
        self.client.loop_stop()
