import importlib.util
import json
import math
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "weewx/mqtt_discovery.py"
SPEC = importlib.util.spec_from_file_location("mqtt_discovery", MODULE_PATH)
discovery = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(discovery)


class MQTTDiscoveryTests(unittest.TestCase):
    def test_discovery_groups_unique_sensors_under_one_device(self):
        messages = discovery.discovery_messages("Back Garden", "1.2.0")
        self.assertGreaterEqual(len(messages), 10)
        self.assertEqual(len({topic for topic, _ in messages}), len(messages))
        payloads = [json.loads(payload) for _, payload in messages]
        self.assertEqual(
            {tuple(payload["device"]["identifiers"]) for payload in payloads},
            {("weewx_weather_station",)},
        )
        self.assertTrue(
            all(payload["device"]["name"] == "Back Garden" for payload in payloads)
        )
        self.assertTrue(
            all(payload["state_topic"] == "weewx/weather/state" for payload in payloads)
        )
        self.assertTrue(
            all(
                payload["availability_topic"] == "weewx/weather/status"
                for payload in payloads
            )
        )

    def test_metric_sensor_metadata_matches_home_assistant(self):
        payloads = {
            json.loads(payload)["object_id"]: json.loads(payload)
            for _, payload in discovery.discovery_messages("Station", "1.2.0")
        }
        self.assertEqual(payloads["weewx_out_temp"]["device_class"], "temperature")
        self.assertEqual(payloads["weewx_out_temp"]["unit_of_measurement"], "°C")
        self.assertEqual(payloads["weewx_wind_speed"]["unit_of_measurement"], "m/s")
        self.assertEqual(
            payloads["weewx_wind_dir"]["state_class"], "measurement_angle"
        )
        self.assertEqual(payloads["weewx_rain_rate"]["unit_of_measurement"], "mm/h")
        self.assertEqual(
            payloads["weewx_day_rain"]["state_class"], "total_increasing"
        )

    def test_state_payload_omits_missing_and_non_finite_values(self):
        payload = json.loads(
            discovery.state_payload(
                {"outTemp": 21.5, "outHumidity": None, "UV": math.nan, "noise": 9}
            )
        )
        self.assertEqual(payload, {"outTemp": 21.5})

    def test_indoor_rain_and_pressure_observations_are_discovered_and_published(self):
        record = {
            "inTemp": 29.2,
            "inHumidity": 64.0,
            "pressure": 1008.4,
            "altimeter": 1012.1,
            "rain": 0.2,
            "rainTotal": 148.6,
            "rxCheckPercent": 100.0,
        }

        state = json.loads(discovery.state_payload(record))
        payloads = {
            json.loads(payload)["object_id"]: json.loads(payload)
            for _, payload in discovery.discovery_messages("Station", "1.3.0")
        }

        self.assertEqual(state, record)
        self.assertEqual(payloads["weewx_in_temp"]["device_class"], "temperature")
        self.assertEqual(payloads["weewx_pressure"]["unit_of_measurement"], "hPa")
        self.assertEqual(
            payloads["weewx_rain_total"]["state_class"], "total_increasing"
        )
        self.assertEqual(
            payloads["weewx_rx_check_percent"]["entity_category"], "diagnostic"
        )

    def test_outdoor_sensor_battery_is_a_diagnostic_binary_sensor(self):
        messages = discovery.discovery_messages("Station", "1.3.0")
        topic, payload_json = next(
            (topic, payload)
            for topic, payload in messages
            if topic.endswith("/out_temp_battery_status/config")
        )
        payload = json.loads(payload_json)

        self.assertIn("/binary_sensor/", topic)
        self.assertEqual(payload["device_class"], "battery")
        self.assertEqual(payload["entity_category"], "diagnostic")
        self.assertEqual(payload["payload_on"], "1")
        self.assertEqual(payload["payload_off"], "0")
        self.assertEqual(
            payload["value_template"],
            "{% if value_json.outTempBatteryStatus is defined %}"
            "{{ value_json.outTempBatteryStatus | int }}"
            "{% endif %}",
        )
        self.assertEqual(
            json.loads(discovery.state_payload({"outTempBatteryStatus": 0.0})),
            {"outTempBatteryStatus": 0.0},
        )


if __name__ == "__main__":
    unittest.main()
