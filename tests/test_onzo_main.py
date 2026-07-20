import importlib.util
import logging
import sys
import time
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


class _ReceiverConnection:
    def __init__(self, path):
        self.path = path

    def connect(self):
        pass

    def disconnect(self):
        pass


class _PoweredOffClamp:
    def __init__(self, connection):
        pass

    def get_serial(self):
        return 0

    def get_power(self):
        raise TimeoutError("Timed out waiting for an Onzo HID response")


class _RecordingPublisher:
    def __init__(self):
        self.registered = []
        self.states = []
        self.offline_serials = []

    def register(self, serial, name):
        self.registered.append((serial, name))

    def state(self, serial, values):
        self.states.append((serial, values))

    def offline(self, serial):
        self.offline_serials.append(serial)


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

    def test_powered_off_clamp_does_not_disconnect_receiver_worker(self):
        publisher = _RecordingPublisher()
        worker = main.MeterWorker(b"1-1.2:1.0", publisher, {}, 0.001)

        with mock.patch.object(main, "Connection", _ReceiverConnection):
            with mock.patch.object(main, "Clamp", _PoweredOffClamp):
                with self.assertLogs("onzo", logging.WARNING) as captured:
                    worker.start()
                    deadline = time.monotonic() + 0.2
                    while not publisher.states and time.monotonic() < deadline:
                        time.sleep(0.001)
                    self.assertTrue(worker.is_alive())
                    worker.stop()
                    worker.join(timeout=0.2)

        self.assertIn("clamp may be off", "\n".join(captured.output))
        self.assertEqual(publisher.registered, [("00000000", "Onzo 00000000")])
        self.assertEqual(
            publisher.states[0],
            (
                "00000000",
                {"clamp_serial": "00000000", "hid_path": "1-1.2:1.0"},
            ),
        )


if __name__ == "__main__":
    unittest.main()
