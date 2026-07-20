#!/usr/bin/env python3
"""Apply Home Assistant add-on options to a WeeWX 5 station."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--options", type=Path, default=Path("/data/options.json"))
    parser.add_argument("--root", type=Path, default=Path("/data/weewx"))
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    subprocess.run(station_command(load_options(args.options), args.root), check=True)


if __name__ == "__main__":
    main()
