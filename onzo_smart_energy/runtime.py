"""Pure runtime helpers shared by the Onzo manager and tests."""

from __future__ import annotations


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
