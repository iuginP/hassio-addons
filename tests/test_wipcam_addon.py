import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "wipcam_addon_launcher",
    ROOT / "wipcam_bridge" / "launcher.py",
)
assert SPEC is not None and SPEC.loader is not None
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class WipcamAddonLauncherTests(unittest.TestCase):
    def test_partial_rtsp_credentials_are_rejected(self):
        with self.assertRaisesRegex(
            launcher.ConfigurationError,
            "rtsp_read_username and rtsp_read_password must be set together",
        ):
            launcher.build_environments(
                {
                    "lan_bind_ip": "192.168.1.10",
                    "basic_username": "admin",
                    "basic_password": "management-secret",
                    "rtsp_read_username": "viewer",
                }
            )

    def test_options_are_translated_for_both_services(self):
        environments = launcher.build_environments(
            {
                "lan_bind_ip": "192.168.1.10",
                "basic_username": "camera-admin",
                "basic_password": "management-secret",
                "rtsp_read_username": "viewer",
                "rtsp_read_password": "stream-secret",
                "log_level": "DEBUG",
                "low_stream_enabled": False,
                "low_stream_width": 640,
                "low_stream_height": 360,
                "low_stream_fps": 12,
                "low_stream_bitrate": "768k",
                "low_stream_preset": "faster",
                "telnet_username": "root",
                "telnet_password": "camera-secret",
                "experimental_camera_writes_enabled": True,
            }
        )

        self.assertEqual(
            environments.wipcam["WIPCAM_LAN_BIND_IP"], "192.168.1.10"
        )
        self.assertEqual(environments.wipcam["WIPCAM_AUTH_MODE"], "basic")
        self.assertEqual(
            environments.wipcam["WIPCAM_BASIC_PASSWORD"], "management-secret"
        )
        self.assertEqual(environments.wipcam["WIPCAM_LOW_STREAM_ENABLED"], "false")
        self.assertEqual(environments.wipcam["WIPCAM_LOW_STREAM_HEIGHT"], "360")
        self.assertEqual(
            environments.wipcam["WIPCAM_EXPERIMENTAL_CAMERA_WRITES_ENABLED"],
            "true",
        )
        self.assertEqual(
            environments.mediamtx["MTX_AUTHINTERNALUSERS_1_USER"], "viewer"
        )
        self.assertEqual(
            environments.mediamtx["MTX_AUTHINTERNALUSERS_1_PASS"], "stream-secret"
        )

    def test_options_are_loaded_from_home_assistant_data(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "options.json"
            path.write_text(json.dumps({"lan_bind_ip": "192.168.1.10"}))

            self.assertEqual(
                launcher.load_options(path),
                {"lan_bind_ip": "192.168.1.10"},
            )

    def test_both_services_start_with_their_own_environment(self):
        calls = []

        def fake_popen(command, *, env):
            calls.append((command, env))
            return object()

        environments = launcher.ServiceEnvironments(
            wipcam={"WIPCAM_LAN_BIND_IP": "192.168.1.10"},
            mediamtx={"MTX_RTSPADDRESS": ":8554"},
        )

        processes = launcher.start_services(
            environments,
            base_environment={"PATH": "/usr/bin"},
            popen=fake_popen,
        )

        self.assertEqual(len(processes), 2)
        self.assertEqual(calls[0][0], ["mediamtx", "/etc/mediamtx.yml"])
        self.assertEqual(
            calls[1][0], ["python", "-m", "wipcam_bridge.service"]
        )
        self.assertEqual(calls[0][1]["MTX_RTSPADDRESS"], ":8554")
        self.assertEqual(calls[0][1]["MTX_RTSPTRANSPORTS"], "tcp")
        for unused_protocol in ("MTX_HLS", "MTX_RTMP", "MTX_SRT", "MTX_WEBRTC"):
            self.assertEqual(calls[0][1][unused_protocol], "false")
        self.assertNotIn("WIPCAM_LAN_BIND_IP", calls[0][1])
        self.assertEqual(calls[1][1]["WIPCAM_LAN_BIND_IP"], "192.168.1.10")
        self.assertNotIn("MTX_RTSPADDRESS", calls[1][1])

    def test_when_one_service_exits_the_other_is_stopped(self):
        class FakeProcess:
            def __init__(self, return_code):
                self.return_code = return_code
                self.terminated = False

            def poll(self):
                return self.return_code

            def terminate(self):
                self.terminated = True
                self.return_code = 0

            def wait(self, timeout=None):
                return self.return_code

            def kill(self):
                raise AssertionError("graceful termination should be enough")

        mediamtx = FakeProcess(None)
        wipcam = FakeProcess(7)

        self.assertEqual(
            launcher.supervise([mediamtx, wipcam], sleep=lambda _seconds: None),
            7,
        )
        self.assertTrue(mediamtx.terminated)


if __name__ == "__main__":
    unittest.main()
