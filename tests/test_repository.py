import os
import re
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_APP_KEYS = {"name", "version", "slug", "description", "arch"}
IMAGE_PREFIX = "ghcr.io/iuginp/hassio-"
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

    def test_every_app_uses_its_prebuilt_multi_arch_image(self):
        for config_path in ROOT.glob("*/config.yaml"):
            config = yaml.safe_load(config_path.read_text())
            with self.subTest(app=config["slug"]):
                self.assertEqual(
                    config.get("image"),
                    f"{IMAGE_PREFIX}{config['slug'].replace('_', '-')}",
                )

    def test_builder_workflow_builds_and_publishes_changed_apps(self):
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/builder.yaml").read_text()
        )
        build_job = workflow["jobs"]["build-app"]

        self.assertEqual(
            build_job["uses"],
            "./.github/workflows/build-app.yaml",
        )
        self.assertEqual(build_job["permissions"]["packages"], "write")
        self.assertIn("push", build_job["with"]["publish"])

        reusable = yaml.safe_load(
            (ROOT / ".github/workflows/build-app.yaml").read_text()
        )
        steps = [
            step
            for job in reusable["jobs"].values()
            for step in job.get("steps", [])
        ]
        actions = {step.get("uses") for step in steps}
        self.assertIn(
            "home-assistant/builder/actions/build-image@2026.06.0",
            actions,
        )
        self.assertIn(
            "home-assistant/builder/actions/publish-multi-arch-manifest@2026.06.0",
            actions,
        )

    def test_builder_strips_json_quotes_from_app_information(self):
        reusable = yaml.safe_load(
            (ROOT / ".github/workflows/build-app.yaml").read_text()
        )
        prepare = reusable["jobs"]["prepare"]
        normalize = next(
            step
            for step in prepare["steps"]
            if step["name"] == "Normalize app information"
        )

        expected = {
            "image_name": "hassio-weewx",
            "registry_prefix": "ghcr.io/iuginp",
            "version": "9.8.7",
            "name": "WeeWX",
            "description": "Weather station",
            "url": "https://example.com/weewx",
        }
        raw = {
            "INFO_IMAGE": '"ghcr.io/iuginp/hassio-weewx"',
            "INFO_VERSION": '"9.8.7"',
            "INFO_NAME": '"WeeWX"',
            "INFO_DESCRIPTION": '"Weather station"',
            "INFO_URL": '"https://example.com/weewx"',
        }
        with tempfile.NamedTemporaryFile() as output:
            subprocess.run(
                ["bash", "-c", normalize["run"]],
                check=True,
                env={**os.environ, **raw, "GITHUB_OUTPUT": output.name},
            )
            output.seek(0)
            actual = dict(
                line.decode().rstrip().split("=", 1)
                for line in output
                if b"=" in line
            )

        self.assertEqual(actual, expected)
        for key in ("version", "name", "description", "url"):
            self.assertEqual(
                prepare["outputs"][key],
                f"${{{{ steps.normalize.outputs.{key} }}}}",
            )

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
        self.assertIn("/dev/hidraw0", config["devices"])
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

    def test_onzo_builds_hidapi_with_the_hidraw_backend(self):
        dockerfile = (ROOT / "onzo_smart_energy/Dockerfile").read_text()
        self.assertIn("--no-binary=hidapi", dockerfile)
        self.assertIn("hidapi==0.14.0.post2", dockerfile)
        self.assertIn("libudev-dev", dockerfile)
        self.assertIn("pkg-config", dockerfile)

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

    def test_wipcam_bridge_has_a_minimal_host_network_contract(self):
        app = ROOT / "wipcam_bridge"
        config = yaml.safe_load((app / "config.yaml").read_text())

        self.assertEqual(config["slug"], "wipcam_bridge")
        self.assertEqual(config["version"], "0.1.3")
        self.assertEqual(set(config["arch"]), {"aarch64", "amd64"})
        self.assertTrue(config["host_network"])
        self.assertEqual(config["options"]["lan_bind_ip"], None)
        self.assertEqual(config["options"]["basic_password"], None)
        self.assertEqual(config["schema"]["basic_password"], "password")
        self.assertEqual(config["webui"], "http://[HOST]:[PORT:18080]/")
        self.assertEqual(
            config["watchdog"],
            "http://[HOST]:[PORT:18080]/healthz",
        )
        self.assertEqual(config["ports"]["18080/tcp"], 18080)
        for capability in (
            "docker_api",
            "full_access",
            "hassio_api",
            "homeassistant_api",
            "host_dbus",
            "host_ipc",
            "host_pid",
            "host_uts",
            "privileged",
        ):
            self.assertFalse(config.get(capability), capability)

        translations = yaml.safe_load(
            (app / "translations/en.yaml").read_text()
        )["configuration"]
        self.assertEqual(set(config["schema"]), set(translations))

    def test_wipcam_bridge_release_inputs_are_pinned_and_consistent(self):
        app = ROOT / "wipcam_bridge"
        version = yaml.safe_load((app / "config.yaml").read_text())["version"]
        dockerfile = (app / "Dockerfile").read_text()

        self.assertRegex(
            dockerfile,
            re.compile(rf"^ARG BUILD_VERSION={re.escape(version)}$", re.MULTILINE),
        )
        self.assertRegex(
            dockerfile,
            re.compile(r"^ARG WIPCAM_COMMIT=[0-9a-f]{40}$", re.MULTILINE),
        )
        self.assertIn(
            "ARG WIPCAM_COMMIT=0959ece54cea5829057ecc9a02d0de1416bb746e",
            dockerfile,
        )
        self.assertIn("FROM bluenviron/mediamtx:1.18.2 AS mediamtx", dockerfile)

    def test_wipcam_bridge_documents_home_assistant_camera_setup(self):
        readme = (ROOT / "wipcam_bridge" / "README.md").read_text()

        self.assertIn("Home Assistant Generic Camera", readme)
        self.assertIn("Still Image URL", readme)
        self.assertIn("Stream Source URL", readme)
        self.assertIn("Stream source is not supported by go2rtc", readme)
        self.assertIn("ffmpeg", readme)

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
