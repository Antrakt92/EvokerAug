#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


def _read(root: Path, relative_path: str) -> str:
    return (root / relative_path).read_text(encoding="utf-8")


def _require_match(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, re.M)
    if not match:
        raise ValueError(f"{label}: version metadata is missing")
    return match.group(1)


def _tagged_config_version(raw_version: str) -> str:
    return raw_version if raw_version.startswith("v") else f"v{raw_version}"


def _collect_versions(root: Path) -> dict[str, str]:
    toc = _read(root, "EvokerAug.toc")
    config = _read(root, "Core/Config.lua")
    changelog = _read(root, "CHANGELOG.md")
    package_script = _read(root, "scripts/package-local.ps1")

    package_param_version = _require_match(
        r'\[string\]\$Version\s*=\s*"(v[^"]+)"',
        package_script,
        "scripts/package-local.ps1 default Version parameter",
    )
    package_zip_version = _require_match(
        r'\$defaultZipName\s*=\s*"EvokerAug-(v[^"]+)\.zip"',
        package_script,
        "scripts/package-local.ps1 default zip name",
    )

    return {
        "EvokerAug.toc ## Version": _require_match(r"^## Version:\s*(\S+)\s*$", toc, "EvokerAug.toc"),
        "Core/Config.lua addon.Config version": _tagged_config_version(
            _require_match(r'\["version"\]\s*=\s*"([^"]+)"', config, "Core/Config.lua")
        ),
        "CHANGELOG.md top heading": _require_match(r"^##\s+(v\S+)\s+", changelog, "CHANGELOG.md"),
        "scripts/package-local.ps1 default Version parameter": package_param_version,
        "scripts/package-local.ps1 default zip name": package_zip_version,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify release tag matches addon version metadata.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to the current directory.")
    parser.add_argument("--tag", default=os.environ.get("GITHUB_REF_NAME"), help="Release tag, usually GITHUB_REF_NAME.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    tag = args.tag
    if not tag:
        print("Release tag is required via --tag or GITHUB_REF_NAME.", file=sys.stderr)
        return 2

    try:
        versions = _collect_versions(root)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    mismatches = [(label, version) for label, version in versions.items() if version != tag]
    if mismatches:
        print(f"Release tag {tag} does not match addon version metadata:", file=sys.stderr)
        for label, version in mismatches:
            print(f"- {label}: {version}", file=sys.stderr)
        return 1

    print(f"Release metadata matches {tag}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
