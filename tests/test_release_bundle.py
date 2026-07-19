from __future__ import annotations

import importlib.util
from pathlib import Path
import zipfile

import pytest


def _load_script(name: str, filename: str):
    path = Path(__file__).parents[1] / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_bundle_script = _load_script("evokeraug_release_bundle", "check-release-bundle.py")
_ref_script = _load_script("evokeraug_release_ref", "check-release-ref.py")
ReleaseBundleError = _bundle_script.ReleaseBundleError
validate_bundle = _bundle_script.validate_bundle
ReleaseRefError = _ref_script.ReleaseRefError
parse_remote_ref = _ref_script.parse_remote_ref


TAG = "v1.2.3-midnight.1"
COMMIT = "a" * 40


def _bundle(
    tmp_path: Path,
    *,
    toc_version: str = TAG,
    extra: dict[str, bytes] | None = None,
    omit: set[str] | None = None,
) -> Path:
    release_dir = tmp_path / ".release"
    release_dir.mkdir()
    archive_path = release_dir / f"EvokerAug-{TAG}.zip"
    files = {
        "EvokerAug/EvokerAug.toc": (
            "## Interface: 120005, 120007\n"
            f"## Version: {toc_version}\n"
            "## Title: |cff00ff7fEvokerAug|r\n"
            "embeds.xml\n"
            "Core\\Config.lua\n"
            "Core\\EvokerAug.lua\n"
            "Core\\SpellList.lua\n"
        ).encode(),
        "EvokerAug/CHANGELOG.md": b"# Changelog\n",
        "EvokerAug/Core/Config.lua": b"return {}\n",
        "EvokerAug/Core/EvokerAug.lua": b"return {}\n",
        "EvokerAug/Core/SpellList.lua": b"return {}\n",
        "EvokerAug/embeds.xml": b'<Ui><Script file="Libs\\Runtime.lua"/></Ui>\n',
        "EvokerAug/Libs/Runtime.lua": b"return {}\n",
        "EvokerAug/LICENSE": b"license\n",
        "EvokerAug/Media/augevoker-logo.tga": b"logo",
        "EvokerAug/Media/bar.tga": b"bar",
        "EvokerAug/README.md": b"# EvokerAug\n",
    }
    files.update(extra or {})
    for name in omit or set():
        files.pop(name, None)
    with zipfile.ZipFile(archive_path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return release_dir


def test_release_bundle_builds_exact_bigwigs_metadata(tmp_path: Path):
    release_dir = _bundle(tmp_path)

    _, metadata = validate_bundle(release_dir, TAG)

    assert metadata == {
        "releases": [
            {
                "name": "EvokerAug",
                "version": TAG,
                "filename": f"EvokerAug-{TAG}.zip",
                "nolib": False,
                "metadata": [
                    {"flavor": "mainline", "interface": 120005},
                    {"flavor": "mainline", "interface": 120007},
                ],
            }
        ]
    }


@pytest.mark.parametrize(
    "extra",
    [
        {"../escape.lua": b"bad"},
        {"EvokerAug/tests/private.py": b"bad"},
        {"EvokerAug/Tests/private.py": b"bad"},
        {"EvokerAug/AGENTS.md": b"bad"},
        {"EvokerAug/vendor.private/secret.txt": b"bad"},
        {"EvokerAug/Libs/Vendor/.pkgmeta": b"bad"},
        {"EvokerAug/core/config.lua": b"duplicate"},
    ],
)
def test_release_bundle_rejects_unsafe_or_private_entries(tmp_path: Path, extra: dict[str, bytes]):
    release_dir = _bundle(tmp_path, extra=extra)

    with pytest.raises(ReleaseBundleError):
        validate_bundle(release_dir, TAG)


def test_release_bundle_rejects_packaged_version_drift(tmp_path: Path):
    release_dir = _bundle(tmp_path, toc_version="v1.2.4")

    with pytest.raises(ReleaseBundleError, match="version"):
        validate_bundle(release_dir, TAG)


@pytest.mark.parametrize(
    "missing",
    [
        "EvokerAug/embeds.xml",
        "EvokerAug/Libs/Runtime.lua",
        "EvokerAug/Media/augevoker-logo.tga",
        "EvokerAug/Media/bar.tga",
        "EvokerAug/LICENSE",
    ],
)
def test_release_bundle_rejects_missing_runtime_or_public_surface(tmp_path: Path, missing: str):
    release_dir = _bundle(tmp_path, omit={missing})

    with pytest.raises(ReleaseBundleError, match="missing"):
        validate_bundle(release_dir, TAG)


def test_remote_ref_parser_prefers_peeled_annotated_target():
    output = f"{'b' * 40}\trefs/tags/{TAG}\n{COMMIT}\trefs/tags/{TAG}^{{}}\n"

    assert parse_remote_ref(output, TAG) == COMMIT


def test_remote_ref_parser_rejects_missing_or_unexpected_refs():
    with pytest.raises(ReleaseRefError, match="missing"):
        parse_remote_ref("", TAG)
    with pytest.raises(ReleaseRefError, match="unexpected"):
        parse_remote_ref(f"{COMMIT}\trefs/heads/main\n", TAG)
