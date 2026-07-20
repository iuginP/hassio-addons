import re
import struct
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_APP_KEYS = {"name", "version", "slug", "description", "arch"}
WEEWX_BUILTIN_DRIVERS = (
    "weewx.drivers.acurite",
    "weewx.drivers.cc3000",
    "weewx.drivers.fousb",
    "weewx.drivers.simulator",
    "weewx.drivers.te923",
    "weewx.drivers.ultimeter",
    "weewx.drivers.vantage",
    "weewx.drivers.wmr100",
    "weewx.drivers.wmr300",
    "weewx.drivers.wmr9x8",
    "weewx.drivers.ws1",
    "weewx.drivers.ws23xx",
    "weewx.drivers.ws28xx",
)


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as image:
        if image.read(8) != b"\x89PNG\r\n\x1a\n":
            raise AssertionError(f"{path} is not a PNG")
        length = struct.unpack(">I", image.read(4))[0]
        if image.read(4) != b"IHDR" or length < 8:
            raise AssertionError(f"{path} has no valid IHDR chunk")
        return struct.unpack(">II", image.read(8))


class RepositoryTests(unittest.TestCase):
    def test_repository_metadata(self):
        metadata = yaml.safe_load((ROOT / "repository.yaml").read_text())
        self.assertIsInstance(metadata["name"], str)
        self.assertTrue(metadata["name"])
        self.assertTrue(metadata["url"].startswith("https://"))

    def test_python_cache_uses_the_actual_dependency_file(self):
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/test.yml").read_text()
        )
        setup_python = next(
            step
            for step in workflow["jobs"]["test"]["steps"]
            if step.get("uses", "").startswith("actions/setup-python@")
        )
        self.assertEqual(
            setup_python["with"].get("cache-dependency-path"),
            "requirements-dev.txt",
        )

    def test_every_app_has_valid_metadata_and_files(self):
        apps = sorted(path.parent for path in ROOT.glob("*/config.yaml"))
        self.assertTrue(apps, "repository must contain at least one app")
        slugs = set()
        for app in apps:
            with self.subTest(app=app.name):
                config = yaml.safe_load((app / "config.yaml").read_text())
                self.assertFalse(REQUIRED_APP_KEYS - config.keys())
                self.assertEqual(config["slug"], app.name)
                self.assertNotIn(config["slug"], slugs)
                slugs.add(config["slug"])
                self.assertTrue(set(config["options"]) <= set(config["schema"]))
                self.assertTrue((app / "Dockerfile").is_file())
                self.assertTrue((app / "run.sh").is_file())
                self.assertTrue((app / "README.md").is_file())

    def test_every_app_has_home_assistant_branding(self):
        for config_path in ROOT.glob("*/config.yaml"):
            app = config_path.parent
            with self.subTest(app=app.name):
                self.assertEqual(png_dimensions(app / "icon.png"), (128, 128))
                self.assertEqual(png_dimensions(app / "logo.png"), (250, 100))

    def test_weewx_ui_options_match_weewx_5(self):
        config = yaml.safe_load((ROOT / "weewx/config.yaml").read_text())
        self.assertIn("mqtt:need", config["services"])
        self.assertEqual(
            config["schema"]["driver"],
            "list(%s)" % "|".join(WEEWX_BUILTIN_DRIVERS),
        )
        self.assertIn(config["options"]["driver"], WEEWX_BUILTIN_DRIVERS)
        self.assertEqual(config["schema"]["units"], "list(us|metric|metricwx)")
        self.assertEqual(config["schema"]["altitude_unit"], "list(meter|foot)")
        translations = yaml.safe_load(
            (ROOT / "weewx/translations/en.yaml").read_text()
        )["configuration"]
        self.assertEqual(set(config["schema"]), set(translations))

    def test_weewx_release_version_is_consistent(self):
        version = yaml.safe_load((ROOT / "weewx/config.yaml").read_text())["version"]
        dockerfile = (ROOT / "weewx/Dockerfile").read_text()
        mqtt_service = (ROOT / "weewx/home_assistant_mqtt.py").read_text()

        self.assertRegex(
            dockerfile,
            re.compile(rf"^ARG BUILD_VERSION={re.escape(version)}$", re.MULTILINE),
        )
        self.assertRegex(
            mqtt_service,
            re.compile(rf'^APP_VERSION = "{re.escape(version)}"$', re.MULTILINE),
        )

    def test_onzo_supports_mqtt_and_multiple_meter_overrides(self):
        config = yaml.safe_load((ROOT / "onzo_smart_energy/config.yaml").read_text())
        self.assertTrue(config["usb"])
        self.assertIn("mqtt:need", config["services"])
        self.assertEqual(config["options"]["meters"], [])
        self.assertEqual(
            config["schema"]["meters"],
            [{"serial": "str", "name": "str"}],
        )
        translations = yaml.safe_load(
            (ROOT / "onzo_smart_energy/translations/en.yaml").read_text()
        )["configuration"]
        self.assertEqual(set(config["schema"]), set(translations))

    def test_onzo_release_version_is_consistent(self):
        version = yaml.safe_load(
            (ROOT / "onzo_smart_energy/config.yaml").read_text()
        )["version"]
        dockerfile = (ROOT / "onzo_smart_energy/Dockerfile").read_text()
        main = (ROOT / "onzo_smart_energy/main.py").read_text()

        self.assertRegex(
            dockerfile,
            re.compile(rf"^ARG BUILD_VERSION={re.escape(version)}$", re.MULTILINE),
        )
        self.assertRegex(
            main,
            re.compile(rf'^APP_VERSION = "{re.escape(version)}"$', re.MULTILINE),
        )

    def test_weewx_release_version_is_consistent(self):
        version = yaml.safe_load((ROOT / "weewx/config.yaml").read_text())["version"]
        dockerfile = (ROOT / "weewx/Dockerfile").read_text()
        mqtt_service = (ROOT / "weewx/home_assistant_mqtt.py").read_text()

        self.assertRegex(
            dockerfile,
            re.compile(rf"^ARG BUILD_VERSION={re.escape(version)}$", re.MULTILINE),
        )
        self.assertRegex(
            mqtt_service,
            re.compile(rf'^APP_VERSION = "{re.escape(version)}"$', re.MULTILINE),
        )
if __name__ == "__main__":
    unittest.main()
