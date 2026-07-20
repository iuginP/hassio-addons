import importlib.util
import json
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "onzo_smart_energy/discovery.py"
SPEC = importlib.util.spec_from_file_location("onzo_discovery", MODULE_PATH)
discovery = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(discovery)


class OnzoDiscoveryTests(unittest.TestCase):
    def test_each_meter_gets_a_distinct_home_assistant_device(self):
        first = [json.loads(payload) for _, payload in discovery.messages("00000001", "Kitchen")]
        second = [json.loads(payload) for _, payload in discovery.messages("00000002", "Garage")]
        self.assertEqual(
            {tuple(item["device"]["identifiers"]) for item in first},
            {("onzo_00000001",)},
        )
        self.assertEqual(
            {tuple(item["device"]["identifiers"]) for item in second},
            {("onzo_00000002",)},
        )
        self.assertTrue(all(item["device"]["name"] == "Kitchen" for item in first))
        self.assertTrue(all(item["device"]["name"] == "Garage" for item in second))
        self.assertFalse({topic for topic, _ in discovery.messages("00000001", "Kitchen")} & {topic for topic, _ in discovery.messages("00000002", "Garage")})

    def test_energy_and_power_metadata_support_long_term_statistics(self):
        payloads = {
            json.loads(payload)["object_id"]: json.loads(payload)
            for _, payload in discovery.messages("12345678", "House")
        }
        self.assertEqual(payloads["onzo_12345678_power"]["device_class"], "power")
        self.assertEqual(payloads["onzo_12345678_power"]["state_class"], "measurement")
        self.assertEqual(payloads["onzo_12345678_energy"]["device_class"], "energy")
        self.assertEqual(payloads["onzo_12345678_energy"]["state_class"], "total_increasing")
        self.assertEqual(payloads["onzo_12345678_power"]["availability_mode"], "all")
        self.assertEqual(
            payloads["onzo_12345678_power"]["availability"],
            [{"topic": "onzo/status"}, {"topic": "onzo/12345678/status"}],
        )

    def test_hid_path_is_a_disabled_by_default_diagnostic_sensor(self):
        payloads = {
            json.loads(payload)["object_id"]: json.loads(payload)
            for _, payload in discovery.messages("12345678", "House")
        }

        hid_path = payloads["onzo_12345678_hid_path"]
        self.assertEqual(hid_path["entity_category"], "diagnostic")
        self.assertFalse(hid_path["enabled_by_default"])
        self.assertEqual(hid_path["value_template"], "{{ value_json.hid_path }}")
        self.assertNotIn("device_class", hid_path)
        self.assertNotIn("state_class", hid_path)

        self.assertEqual(
            discovery.state_payload(
                {
                    "power": 42,
                    "clamp_serial": "12345678",
                    "hid_path": "/dev/hidraw0",
                }
            ),
            '{"power":42,"clamp_serial":"12345678","hid_path":"/dev/hidraw0"}',
        )

    def test_clamp_serial_is_an_enabled_diagnostic_sensor(self):
        payloads = {
            json.loads(payload)["object_id"]: json.loads(payload)
            for _, payload in discovery.messages("12345678", "House")
        }

        clamp_serial = payloads["onzo_12345678_clamp_serial"]
        self.assertEqual(clamp_serial["entity_category"], "diagnostic")
        self.assertTrue(clamp_serial["enabled_by_default"])
        self.assertEqual(
            clamp_serial["value_template"], "{{ value_json.clamp_serial }}"
        )

    def test_serial_name_overrides_are_normalized(self):
        overrides = discovery.name_overrides(
            [
                {"serial": "0x1a", "name": "House"},
                {"serial": "27", "name": "Workshop"},
            ]
        )
        self.assertEqual(
            overrides,
            {"0000001a": "House", "0000001b": "Workshop"},
        )


if __name__ == "__main__":
    unittest.main()
