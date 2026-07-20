import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "weewx/configure.py"
SPEC = importlib.util.spec_from_file_location("weewx_configure", MODULE_PATH)
configure = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(configure)


class WeeWXConfigureTests(unittest.TestCase):
    def test_load_options_merges_ui_values_with_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            options_file = Path(directory) / "options.json"
            options_file.write_text(json.dumps({"location": "Rome", "altitude": 21}))
            options = configure.load_options(options_file)
        self.assertEqual(options["location"], "Rome")
        self.assertEqual(options["altitude"], 21)
        self.assertEqual(options["driver"], "weewx.drivers.simulator")

    def test_new_station_uses_weewx_5_create_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = configure.station_command(configure.DEFAULTS, root)
        self.assertEqual(command[:3], ["weectl", "station", "create"])
        self.assertIn("--config=weewx.conf", command)
        self.assertIn("--altitude=0,meter", command)

    def test_existing_station_is_reconfigured_on_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "weewx.conf").touch()
            command = configure.station_command(configure.DEFAULTS, root)
        self.assertEqual(command[:3], ["weectl", "station", "reconfigure"])
        self.assertIn(f"--config={root / 'weewx.conf'}", command)
        self.assertIn("--no-backup", command)

    def test_home_assistant_mqtt_service_is_installed_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "home_assistant_mqtt.py").write_text("# service\n")
            (source / "mqtt_discovery.py").write_text("# discovery\n")
            config_file = root / "weewx.conf"
            config_file.write_text(
                "[Engine]\n"
                "    [[Services]]\n"
                "        process_services = weewx.engine.StdConvert\n"
            )

            configure.install_home_assistant_mqtt(config_file, root, source)
            configure.install_home_assistant_mqtt(config_file, root, source)

            installed = (root / "bin/user/home_assistant_mqtt.py").read_text()
            self.assertEqual(installed, "# service\n")
            config_text = config_file.read_text()
            self.assertEqual(
                config_text.count("user.home_assistant_mqtt.HomeAssistantMQTT"), 1
            )


if __name__ == "__main__":
    unittest.main()
