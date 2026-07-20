import importlib.util
import logging
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


APP_DIR = Path(__file__).resolve().parents[1] / "onzo_smart_energy"
sys.path.insert(0, str(APP_DIR))
sys.modules.setdefault("hid", types.SimpleNamespace(enumerate=lambda vid, pid: []))
SPEC = importlib.util.spec_from_file_location("onzo_main", APP_DIR / "main.py")
main = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(main)


class _PublishResult:
    rc = main.mqtt.MQTT_ERR_NO_CONN


class _DisconnectedClient:
    def publish(self, *args, **kwargs):
        return _PublishResult()


class OnzoMainTests(unittest.TestCase):
    def test_failed_mqtt_publish_is_visible_in_the_log(self):
        publisher = main.Publisher.__new__(main.Publisher)
        publisher.client = _DisconnectedClient()

        with self.assertLogs("onzo", logging.ERROR) as captured:
            publisher.state("12345678", {"power": 42})

        self.assertIn("MQTT publish failed", "\n".join(captured.output))

    def test_startup_is_logged_before_external_services_are_contacted(self):
        with mock.patch.object(
            main, "supervisor_mqtt_service", side_effect=RuntimeError("unavailable")
        ):
            with self.assertLogs("onzo", logging.INFO) as captured:
                with self.assertRaisesRegex(RuntimeError, "unavailable"):
                    main.main()

        self.assertIn("Starting Onzo Smart Energy Meter", "\n".join(captured.output))


if __name__ == "__main__":
    unittest.main()
