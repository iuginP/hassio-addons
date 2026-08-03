#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Mapping, NamedTuple


OPTIONS_PATH = Path("/data/options.json")
MEDIAMTX_CONFIG_PATH = "/etc/mediamtx.yml"


class ConfigurationError(ValueError):
    pass


class ServiceEnvironments(NamedTuple):
    wipcam: dict[str, str]
    mediamtx: dict[str, str]


def load_options(path: Path = OPTIONS_PATH) -> dict[str, object]:
    try:
        options = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(options, dict):
        raise ConfigurationError(f"{path} must contain a JSON object")
    return options


def _required(options: Mapping[str, object], name: str) -> str:
    value = str(options.get(name) or "").strip()
    if not value:
        raise ConfigurationError(f"{name} is required")
    return value


def _string(options: Mapping[str, object], name: str, default: str = "") -> str:
    return str(options.get(name, default) or "").strip()


def _boolean(value: object) -> str:
    return "true" if value is True else "false"


def build_environments(options: Mapping[str, object]) -> ServiceEnvironments:
    rtsp_username = _string(options, "rtsp_read_username")
    rtsp_password = _string(options, "rtsp_read_password")
    if bool(rtsp_username) != bool(rtsp_password):
        raise ConfigurationError(
            "rtsp_read_username and rtsp_read_password must be set together"
        )

    wipcam = {
        "WIPCAM_DATABASE_PATH": "/data/wipcam.sqlite3",
        "WIPCAM_LAN_BIND_IP": _required(options, "lan_bind_ip"),
        "WIPCAM_AUTH_MODE": "basic",
        "WIPCAM_BASIC_USERNAME": _required(options, "basic_username"),
        "WIPCAM_BASIC_PASSWORD": _required(options, "basic_password"),
        "WIPCAM_LOG_LEVEL": _string(options, "log_level", "INFO").upper(),
        "WIPCAM_WEB_BIND_HOST": "0.0.0.0",
        "WIPCAM_WEB_PORT": "8080",
        "WIPCAM_RTSP_PORT": "8554",
        "WIPCAM_MEDIAMTX_API_URL": "http://127.0.0.1:19997",
        "WIPCAM_LOW_STREAM_ENABLED": _boolean(
            options.get("low_stream_enabled", True)
        ),
        "WIPCAM_LOW_STREAM_WIDTH": _string(options, "low_stream_width", "640"),
        "WIPCAM_LOW_STREAM_HEIGHT": _string(options, "low_stream_height", "480"),
        "WIPCAM_LOW_STREAM_FPS": _string(options, "low_stream_fps", "10"),
        "WIPCAM_LOW_STREAM_BITRATE": _string(
            options, "low_stream_bitrate", "512k"
        ),
        "WIPCAM_LOW_STREAM_PRESET": _string(
            options, "low_stream_preset", "veryfast"
        ),
        "WIPCAM_GATEWAY_TELNET_USER": _string(
            options, "telnet_username", "root"
        ),
        "WIPCAM_EXPERIMENTAL_CAMERA_WRITES_ENABLED": _boolean(
            options.get("experimental_camera_writes_enabled", False)
        ),
    }
    telnet_password = _string(options, "telnet_password")
    if telnet_password:
        wipcam["WIPCAM_GATEWAY_TELNET_PASSWORD"] = telnet_password
    if rtsp_username:
        wipcam["WIPCAM_RTSP_READ_USERNAME"] = rtsp_username
        wipcam["WIPCAM_RTSP_READ_PASSWORD"] = rtsp_password

    mediamtx = {
        "MTX_LOGLEVEL": "info",
        "MTX_READTIMEOUT": "60s",
        "MTX_WRITETIMEOUT": "60s",
        "MTX_RTSPADDRESS": ":8554",
        "MTX_API": "true",
        "MTX_APIADDRESS": "127.0.0.1:19997",
        "MTX_AUTHMETHOD": "internal",
        "MTX_AUTHINTERNALUSERS_0_USER": "any",
        "MTX_AUTHINTERNALUSERS_0_PASS": "",
        "MTX_AUTHINTERNALUSERS_0_IPS": "127.0.0.1,::1",
        "MTX_AUTHINTERNALUSERS_0_PERMISSIONS_0_ACTION": "publish",
        "MTX_AUTHINTERNALUSERS_0_PERMISSIONS_1_ACTION": "api",
        "MTX_AUTHINTERNALUSERS_0_PERMISSIONS_2_ACTION": "api",
        "MTX_AUTHINTERNALUSERS_1_USER": rtsp_username or "any",
        "MTX_AUTHINTERNALUSERS_1_PASS": rtsp_password,
        "MTX_AUTHINTERNALUSERS_1_IPS": "0.0.0.0/0,::/0",
        "MTX_AUTHINTERNALUSERS_1_PERMISSIONS_0_ACTION": "read",
        "MTX_AUTHINTERNALUSERS_1_PERMISSIONS_1_ACTION": "read",
        "MTX_AUTHINTERNALUSERS_1_PERMISSIONS_2_ACTION": "read",
        "MTX_PATHDEFAULTS_SOURCE": "publisher",
        "MTX_PATHDEFAULTS_OVERRIDEPUBLISHER": "false",
    }
    return ServiceEnvironments(wipcam=wipcam, mediamtx=mediamtx)


def start_services(
    environments: ServiceEnvironments,
    *,
    base_environment: Mapping[str, str] | None = None,
    popen: Callable[..., object] = subprocess.Popen,
) -> list[object]:
    base = dict(os.environ if base_environment is None else base_environment)
    mediamtx_environment = {
        **base,
        "MTX_HLS": "false",
        "MTX_RTMP": "false",
        "MTX_RTSPTRANSPORTS": "tcp",
        "MTX_SRT": "false",
        "MTX_WEBRTC": "false",
        **environments.mediamtx,
    }
    wipcam_environment = {**base, **environments.wipcam}
    processes: list[object] = []
    try:
        processes.append(
            popen(["mediamtx", MEDIAMTX_CONFIG_PATH], env=mediamtx_environment)
        )
        processes.append(
            popen(
                ["python", "-m", "wipcam_bridge.service"],
                env=wipcam_environment,
            )
        )
    except BaseException:
        for process in processes:
            process.terminate()
        raise
    return processes


def supervise(
    processes: list[object],
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    exit_code = 0
    try:
        while True:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    exit_code = int(return_code)
                    return exit_code
            sleep(0.25)
    except KeyboardInterrupt:
        return exit_code
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def _handle_shutdown(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def main() -> int:
    try:
        environments = build_environments(load_options())
    except ConfigurationError as exc:
        print(f"WiPcam Bridge configuration error: {exc}", file=sys.stderr)
        return 2
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    return supervise(start_services(environments))


if __name__ == "__main__":
    raise SystemExit(main())
