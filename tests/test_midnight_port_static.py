from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CORE = (ROOT / "Core" / "EvokerAug.lua").read_text(encoding="utf-8")
CONFIG = (ROOT / "Core" / "Config.lua").read_text(encoding="utf-8")
TOC = (ROOT / "EvokerAug.toc").read_text(encoding="utf-8")
PKGMETA = (ROOT / ".pkgmeta").read_text(encoding="utf-8")
GITIGNORE = (ROOT / ".gitignore").read_text(encoding="utf-8")


def function_body(source: str, name: str) -> str:
    match = re.search(rf"(?:local\s+)?function\s+{re.escape(name)}\b", source)
    assert match, f"{name} is missing"
    next_match = re.search(r"\n(?:local\s+)?function\s+\w+", source[match.end() :])
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


def test_toc_is_ready_for_local_midnight_install():
    assert "## Interface: 120005, 120007" in TOC
    assert "@project-version@" not in TOC
    assert "## Version: v1.0.24-midnight.1" in TOC


def test_config_version_matches_toc():
    assert '["version"] = "1.0.24-midnight.1"' in CONFIG


def test_aura_tracking_is_spell_id_based_for_midnight():
    assert "GetAuraDataBySpellName" not in CORE
    assert "FindTrackedAuraBySpellID" in CORE
    assert "EBON_MIGHT_SPELL_IDS" in CORE
    assert "issecretvalue" in CORE
    assert "IsCleanPositiveNumber" in CORE


def test_localized_class_names_are_not_used_as_class_tokens():
    assert "GetUnitClassToken" in CORE
    assert CORE.count("UnitClass(") == 1


def test_protected_frame_mutations_are_combat_gated():
    assert "CanMutateProtectedFrames" in CORE
    for name in [
        "CreateSelectedPlayerFrame",
        "DeleteSelectedPlayerFrame",
        "SortType",
        "UpdatePlayerFrame",
        "HideAllSubFrames",
        "EnableAllFrame",
    ]:
        body = function_body(CORE, name)
        assert "CanMutateProtectedFrames()" in body, name


def test_addon_compartment_and_context_menu_hooks_are_guarded():
    assert "if AddonCompartmentFrame and AddonCompartmentFrame.RegisterAddon then" in CORE
    assert "MENU_LFG_FRAME_SEARCH_ENTRY" not in CORE
    assert "MENU_LFG_FRAME_MEMBER_APPLY" not in CORE


def test_packager_excludes_repo_only_files():
    assert "ignore:" in PKGMETA
    assert "- tests" in PKGMETA
    assert "- .github" in PKGMETA
    assert "- .pytest_cache" in PKGMETA
    assert ".pytest_cache/" in GITIGNORE
