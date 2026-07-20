"""Pure runtime helpers shared by the Onzo manager and tests."""

from __future__ import annotations

import os


def device_paths(entries: list[dict]) -> dict[object, object]:
    """Return every unique usable HID path, keyed by a stable in-process value."""
    paths = {}
    for entry in entries:
        path = entry.get("path")
        if path is None:
            continue
        key = bytes(path) if isinstance(path, (bytes, bytearray)) else str(path)
        paths[key] = path
    return paths


def display_path(path: object) -> str:
    """Return a HID path suitable for logs and Home Assistant state."""
    if isinstance(path, (bytes, bytearray)):
        return os.fsdecode(path)
    return str(path)
