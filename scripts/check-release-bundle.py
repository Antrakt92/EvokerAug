#!/usr/bin/env python3
"""Validate an exact EvokerAug archive and its GitHub release metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import xml.etree.ElementTree as ET
import zipfile


ADDON_NAME = "EvokerAug"
_TAG = re.compile(
    r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)?$"
)
_REQUIRED = {
    "EvokerAug/CHANGELOG.md",
    "EvokerAug/EvokerAug.toc",
    "EvokerAug/LICENSE",
    "EvokerAug/Media/augevoker-logo.tga",
    "EvokerAug/Media/bar.tga",
    "EvokerAug/README.md",
    "EvokerAug/Core/Config.lua",
    "EvokerAug/Core/EvokerAug.lua",
    "EvokerAug/Core/SpellList.lua",
    "EvokerAug/embeds.xml",
}
_FORBIDDEN_PARTS = {
    ".git",
    ".github",
    ".pytest_cache",
    "backups",
    "dist",
    "scripts",
    "tests",
}
_FORBIDDEN_FILES = {
    ".editorconfig",
    ".gitignore",
    ".luarc.json",
    ".pkgmeta",
    "AGENTS.md",
    "AUDIT.md",
    "CLAUDE.md",
    "NOTES.md",
    "PLAN.md",
    "TODO.md",
    "cspell.json",
}
_FORBIDDEN_PARTS_CASEFOLD = {part.casefold() for part in _FORBIDDEN_PARTS}
_FORBIDDEN_FILES_CASEFOLD = {name.casefold() for name in _FORBIDDEN_FILES}


class ReleaseBundleError(ValueError):
    """The exact-tag release bundle is unsafe or internally inconsistent."""


def _toc_field(toc: str, field: str) -> str:
    matches = re.findall(rf"(?m)^##\s*{re.escape(field)}:\s*(.+?)\s*$", toc)
    if len(matches) != 1:
        raise ReleaseBundleError(f"packaged TOC must contain exactly one {field} field")
    return matches[0]


def _metadata(toc: str, tag: str, archive_name: str) -> dict[str, object]:
    raw_title = _toc_field(toc, "Title")
    title = re.sub(r"\|c[0-9A-Fa-f]{8}", "", raw_title).replace("|r", "").strip()
    if not title:
        raise ReleaseBundleError("packaged TOC title is empty after colour removal")
    interface_parts = [part.strip() for part in _toc_field(toc, "Interface").split(",")]
    if (
        not interface_parts
        or any(not part.isascii() or not part.isdigit() for part in interface_parts)
        or len(interface_parts) != len(set(interface_parts))
    ):
        raise ReleaseBundleError("packaged TOC Interface must contain unique ASCII integers")
    return {
        "releases": [
            {
                "name": title,
                "version": tag,
                "filename": archive_name,
                "nolib": False,
                "metadata": [
                    {"flavor": "mainline", "interface": int(interface)}
                    for interface in interface_parts
                ],
            }
        ]
    }


def _normalize_reference(base: PurePosixPath, raw_reference: str) -> str:
    reference = raw_reference.replace("\\", "/")
    normalized = posixpath.normpath(str(base.parent / reference))
    path = PurePosixPath(normalized)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ReleaseBundleError(f"unsafe XML/TOC file reference: {raw_reference}")
    return f"{ADDON_NAME}/{path.as_posix()}"


def _validate_runtime_closure(archive: zipfile.ZipFile, files: dict[str, zipfile.ZipInfo], toc: str) -> None:
    pending_xml: list[str] = []
    for raw_line in toc.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        required = _normalize_reference(PurePosixPath("EvokerAug.toc"), line)
        if required not in files:
            raise ReleaseBundleError(f"TOC references a missing runtime file: {line}")
        if required.casefold().endswith(".xml"):
            pending_xml.append(required)

    visited: set[str] = set()
    while pending_xml:
        xml_name = pending_xml.pop()
        if xml_name in visited:
            continue
        visited.add(xml_name)
        try:
            root = ET.fromstring(archive.read(xml_name))
        except (ET.ParseError, UnicodeError) as error:
            raise ReleaseBundleError(f"runtime XML is malformed: {xml_name}: {error}") from error
        relative_xml = PurePosixPath(xml_name).relative_to(ADDON_NAME)
        for element in root.iter():
            kind = element.tag.rsplit("}", 1)[-1]
            if kind not in {"Include", "Script"}:
                continue
            raw_reference = element.attrib.get("file", "").strip()
            if not raw_reference:
                raise ReleaseBundleError(f"runtime XML has an empty {kind} reference: {xml_name}")
            required = _normalize_reference(relative_xml, raw_reference)
            if required not in files:
                raise ReleaseBundleError(
                    f"runtime XML {xml_name} references a missing file: {raw_reference}"
                )
            if kind == "Include" or required.casefold().endswith(".xml"):
                pending_xml.append(required)


def validate_bundle(release_dir: Path, tag: str) -> tuple[Path, dict[str, object]]:
    if not _TAG.fullmatch(tag):
        raise ReleaseBundleError("release tag must use canonical vMAJOR.MINOR.PATCH format")
    archive_name = f"{ADDON_NAME}-{tag}.zip"
    archive_path = release_dir / archive_name
    if not archive_path.is_file():
        raise ReleaseBundleError(f"exact-tag archive is missing: {archive_path}")

    with zipfile.ZipFile(archive_path) as archive:
        files: dict[str, zipfile.ZipInfo] = {}
        folded: set[str] = set()
        for info in archive.infolist():
            name = info.filename
            path = PurePosixPath(name)
            if (
                "\\" in name
                or path.is_absolute()
                or not path.parts
                or ".." in path.parts
                or path.parts[0] != ADDON_NAME
            ):
                raise ReleaseBundleError(f"unsafe or misplaced archive entry: {name}")
            if any(
                part.casefold() in _FORBIDDEN_PARTS_CASEFOLD
                or part.casefold().endswith(".private")
                for part in path.parts
            ):
                raise ReleaseBundleError(f"developer-only path leaked into archive: {name}")
            if (
                path.name.casefold() in _FORBIDDEN_FILES_CASEFOLD
                or path.name.casefold().endswith(".private.md")
            ):
                raise ReleaseBundleError(f"developer-only file leaked into archive: {name}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ReleaseBundleError(f"archive contains a symbolic link: {name}")
            if info.is_dir():
                continue
            folded_name = name.casefold()
            if folded_name in folded:
                raise ReleaseBundleError(f"archive contains a case-insensitive duplicate: {name}")
            folded.add(folded_name)
            files[name] = info
        missing = sorted(_REQUIRED - set(files))
        if missing:
            raise ReleaseBundleError(f"archive is missing required files: {', '.join(missing)}")
        toc = archive.read("EvokerAug/EvokerAug.toc").decode("utf-8-sig")
        _validate_runtime_closure(archive, files, toc)

    if _toc_field(toc, "Version") != tag:
        raise ReleaseBundleError("packaged TOC version does not match the release tag")
    return archive_path, _metadata(toc, tag, archive_name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--write-metadata", action="store_true")
    args = parser.parse_args()

    release_dir = args.release_dir.resolve()
    archive_path, expected = validate_bundle(release_dir, args.tag)
    metadata_path = release_dir / "release.json"
    if args.write_metadata:
        metadata_path.write_text(
            json.dumps(expected, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    else:
        try:
            actual = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ReleaseBundleError(f"release metadata is missing or malformed: {error}") from error
        if actual != expected:
            raise ReleaseBundleError("release metadata does not match the exact-tag archive")
    print(f"Verified exact-tag release bundle: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
