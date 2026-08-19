from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path
from typing import Any


RELEASE_TAG_PATTERN = re.compile(r"^v?(?P<version>[0-9]+(?:\.[0-9]+)+(?:[A-Za-z0-9.-]+)?)$")


def project_version(pyproject_path: Path) -> str:
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    version = str(payload.get("project", {}).get("version", "")).strip()
    if not version:
        raise ValueError(f"Project version is missing from {pyproject_path}.")
    return version


def version_from_release_tag(tag: str) -> str:
    normalized = tag.strip()
    if normalized.startswith("refs/tags/"):
        normalized = normalized.removeprefix("refs/tags/")
    match = RELEASE_TAG_PATTERN.fullmatch(normalized)
    if not match:
        raise ValueError(f"Release tag must be a version tag such as v0.4.3: {tag!r}")
    return match.group("version")


def validate_release_tag(tag: str, package_version: str) -> None:
    tag_version = version_from_release_tag(tag)
    if tag_version != package_version:
        raise ValueError(
            f"Release tag version {tag_version!r} does not match package version {package_version!r}."
        )


def validate_plugin_manifest(manifest_path: Path) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    required_strings = ("name", "version", "description", "license", "skills")
    missing = [key for key in required_strings if not str(payload.get(key, "")).strip()]
    if missing:
        raise ValueError(f"Plugin manifest is missing required fields: {', '.join(missing)}")

    plugin_root = (
        manifest_path.parent.parent
        if manifest_path.parent.name == ".codex-plugin"
        else manifest_path.parent
    )
    skills_path = plugin_root / str(payload["skills"])
    if not skills_path.is_dir() or not any(skills_path.rglob("SKILL.md")):
        raise ValueError(f"Plugin skills directory is missing or empty: {skills_path}")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate release metadata before building a package.")
    parser.add_argument("--tag", help="Release tag to compare with the project version.")
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    parser.add_argument("--plugin-manifest", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    version = project_version(args.pyproject)
    if args.tag:
        validate_release_tag(args.tag, version)
        print(f"Release tag matches package version {version}.")
    if args.plugin_manifest:
        payload = validate_plugin_manifest(args.plugin_manifest)
        print(f"Plugin manifest is valid: {payload['name']} {payload['version']}.")
    if not args.tag and not args.plugin_manifest:
        raise ValueError("Provide --tag, --plugin-manifest, or both.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
