#!/usr/bin/env python3
"""Pin a published WiPcam Bridge revision and bump the add-on version."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def replace_once(text: str, pattern: str, replacement: str, path: Path) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"expected exactly one match in {path} for {pattern!r}")
    return updated


def sync(root: Path, commit: str) -> str | None:
    if not SHA_PATTERN.fullmatch(commit):
        raise ValueError("commit must be a lowercase 40-character Git SHA")

    app = root / "wipcam_bridge"
    config_path = app / "config.yaml"
    dockerfile_path = app / "Dockerfile"
    readme_path = app / "README.md"

    config = config_path.read_text()
    dockerfile = dockerfile_path.read_text()
    readme = readme_path.read_text()

    current_commit_match = re.search(
        r"^ARG WIPCAM_COMMIT=([0-9a-f]{40})$", dockerfile, re.MULTILINE
    )
    if current_commit_match is None:
        raise ValueError(f"could not find WIPCAM_COMMIT in {dockerfile_path}")
    if current_commit_match.group(1) == commit:
        return None

    version_match = re.search(r"^version: ([^\s]+)$", config, re.MULTILINE)
    if version_match is None:
        raise ValueError(f"could not find add-on version in {config_path}")
    version = version_match.group(1)
    parts = VERSION_PATTERN.fullmatch(version)
    if parts is None:
        raise ValueError(f"add-on version is not major.minor.patch: {version}")
    next_version = f"{parts.group(1)}.{parts.group(2)}.{int(parts.group(3)) + 1}"

    config = replace_once(
        config,
        rf"^version: {re.escape(version)}$",
        f"version: {next_version}",
        config_path,
    )
    dockerfile = replace_once(
        dockerfile,
        rf"^ARG BUILD_VERSION={re.escape(version)}$",
        f"ARG BUILD_VERSION={next_version}",
        dockerfile_path,
    )
    dockerfile = replace_once(
        dockerfile,
        r"^ARG WIPCAM_COMMIT=[0-9a-f]{40}$",
        f"ARG WIPCAM_COMMIT={commit}",
        dockerfile_path,
    )
    readme = replace_once(
        readme,
        r"(^- WiPcam Bridge `[^`]+`, pinned to commit\n  `)[0-9a-f]{40}(`$)",
        rf"\g<1>{commit}\g<2>",
        readme_path,
    )

    config_path.write_text(config)
    dockerfile_path.write_text(dockerfile)
    readme_path.write_text(readme)
    return next_version


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()

    version = sync(args.root.resolve(), args.commit)
    print("unchanged" if version is None else f"updated={version}")


if __name__ == "__main__":
    main()
