#!/usr/bin/env python3
"""Apply Home Assistant add-on options to a WeeWX 5 station."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from configobj import ConfigObj

DEFAULTS = {
    "driver": "weewx.drivers.simulator",
    "units": "metric",
    "location": "Home Assistant",
    "latitude": 0.0,
    "longitude": 0.0,
    "altitude": 0,
    "altitude_unit": "meter",
}


def load_options(path: Path) -> dict[str, object]:
    options = DEFAULTS.copy()
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} must contain a JSON object")
        options.update(loaded)
    return options


def station_command(options: dict[str, object], root: Path) -> list[str]:
    config = root / "weewx.conf"
    common = [
        "--no-prompt",
        f"--driver={options['driver']}",
        f"--units={options['units']}",
        f"--location={options['location']}",
        f"--latitude={options['latitude']}",
        f"--longitude={options['longitude']}",
        f"--altitude={options['altitude']},{options['altitude_unit']}",
    ]
    if config.exists():
        return [
            "weectl",
            "station",
            "reconfigure",
            *common,
            "--no-backup",
            f"--weewx-root={root}",
            f"--config={config}",
        ]
    return [
        "weectl",
        "station",
        "create",
        str(root),
        *common,
        "--config=weewx.conf",
    ]


def install_home_assistant_mqtt(
    config_file: Path, root: Path, source: Path
) -> None:
    """Install and enable the bundled Home Assistant MQTT service."""
    user_dir = root / "bin/user"
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "__init__.py").touch(exist_ok=True)
    for filename in ("home_assistant_mqtt.py", "mqtt_discovery.py"):
        shutil.copyfile(source / filename, user_dir / filename)

    config = ConfigObj(str(config_file), encoding="utf-8")
    services = config["Engine"]["Services"]
    configured = services.get("process_services", [])
    if isinstance(configured, str):
        configured = [configured]
    service = "user.home_assistant_mqtt.HomeAssistantMQTT"
    if service not in configured:
        configured.append(service)
    services["process_services"] = configured
    config.write()


def configure_console_logging(config_file: Path) -> None:
    """Send WeeWX logs to the container console instead of /dev/log."""
    config = ConfigObj(str(config_file), encoding="utf-8")
    if "Logging" not in config:
        config["Logging"] = {}
    if "root" not in config["Logging"]:
        config["Logging"]["root"] = {}
    config["Logging"]["root"]["handlers"] = ["console"]
    config.write()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--options", type=Path, default=Path("/data/options.json"))
    parser.add_argument("--root", type=Path, default=Path("/data/weewx"))
    parser.add_argument(
        "--mqtt-service-source", type=Path, default=Path("/opt/weewx-ha")
    )
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    subprocess.run(station_command(load_options(args.options), args.root), check=True)
    install_home_assistant_mqtt(
        args.root / "weewx.conf", args.root, args.mqtt_service_source
    )
    configure_console_logging(args.root / "weewx.conf")


if __name__ == "__main__":
    main()
