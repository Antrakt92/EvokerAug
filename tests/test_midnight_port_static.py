from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CORE = (ROOT / "Core" / "EvokerAug.lua").read_text(encoding="utf-8")
CONFIG = (ROOT / "Core" / "Config.lua").read_text(encoding="utf-8")
TOC = (ROOT / "EvokerAug.toc").read_text(encoding="utf-8")
PKGMETA = (ROOT / ".pkgmeta").read_text(encoding="utf-8")
GITIGNORE = (ROOT / ".gitignore").read_text(encoding="utf-8")
CHANGELOG = ROOT / "CHANGELOG.md"
PACKAGE_SCRIPT = ROOT / "scripts" / "package-local.ps1"
INSTALL_SCRIPT = ROOT / "scripts" / "install-local-junction.ps1"


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


def test_secure_spell_buttons_define_action_template_and_modifier_types():
    create_body = function_body(CORE, "CreateSelectedPlayerFrame")
    assert "SecureActionButtonTemplate" in create_body
    assert "SecureUnitButtonTemplate" in create_body

    macro_body = function_body(CORE, "MacroUpdate")
    assert 'SetAttribute("type1", "spell")' in macro_body
    assert 'SetAttribute("spell1"' in macro_body
    assert 'SetAttribute("type2", "spell")' in macro_body
    assert 'SetAttribute("spell2"' in macro_body

    for modifier in ("alt", "shift", "ctrl"):
        assert f'SetAttribute("{modifier}-type1", "spell")' in macro_body
        assert f'SetAttribute("{modifier}-spell1"' in macro_body
        assert f'SetAttribute("{modifier}-type1", nil)' in macro_body
        assert f'SetAttribute("{modifier}-spell1", nil)' in macro_body


def test_party_member_unit_tokens_are_preserved_instead_of_rebuilt_from_indices():
    home_body = function_body(CORE, "GetHomePartyInfos")
    assert "GetNumSubgroupMembers()" in home_body
    assert 'AddHomePartyInfo(partyMembers, "player")' in home_body
    assert "unit = unit" in CORE
    assert "unit = i" not in home_body
    assert "unit = 1" not in home_body
    assert "fullName == nil" not in home_body

    for name in ("FrameAutoFill", "GroupUpdate", "RightMenu"):
        body = function_body(CORE, name)
        assert "member.unit" in body, name
        assert '"party" .. i' not in body, name
        assert '"raid" .. i' not in body, name


def test_group_update_removes_frames_without_forward_ipairs_mutation():
    body = function_body(CORE, "GroupUpdate")
    assert "for i = #selectedPlayerFrames, 1, -1 do" in body
    assert "selectedPlayerFrames[i]" in body
    assert "for _, frame in ipairs(selectedPlayerFrames)" not in body


def test_deleted_and_reconfigured_frames_clear_buff_tickers():
    assert "ClearBuffIcons" in CORE

    delete_body = function_body(CORE, "DeleteSelectedPlayerFrame")
    assert "ClearBuffIcons(selectedPlayerFrames[playerIndex])" in delete_body

    reconfigure_body = function_body(CORE, "addon:Reconfigure")
    assert "for i = #selectedPlayerFrames, 1, -1 do" in reconfigure_body
    assert "ClearBuffIcons(frame)" in reconfigure_body
    assert "string.match(i" not in reconfigure_body
    assert "break" not in reconfigure_body


def test_favorite_frames_use_real_party_unit_tokens():
    body = function_body(CORE, "AddFrameFavorite")
    assert "AddFavoriteFrameForUnit" in CORE
    assert "if IsInRaid() then" in body
    assert "elseif IsInGroup() then" in body
    assert "GetNumSubgroupMembers()" in body
    assert 'AddFavoriteFrameForUnit("raid" .. i)' in body
    assert 'AddFavoriteFrameForUnit("party" .. i)' in body
    assert "(IsInRaid() and" not in body


def test_buff_icon_removal_guards_missing_text_and_ticker():
    body = function_body(CORE, "RemoveBuffIcon")
    assert 'local buff = playerFrame and playerFrame["buff"]' in body
    assert 'local iconFrame = buff and buff[buffID]' in body
    assert 'local text = buff[buffID .. "Text"]' in body
    assert "if text then" in body
    assert "if text.ticker then" in body


def test_custom_spell_options_use_spell_name_and_icon_texture():
    classes_body = function_body(CORE, "GetClasses")
    assert "if spell and spell.name and spell.iconID then" in classes_body

    add_body = function_body(CORE, "SpellListAdd")
    assert "name = Spell.name" in add_body
    assert "image = Spell.iconID" in add_body
    assert "name = Spell.iconID" not in add_body
    assert "image = icon" not in add_body


def test_omnicd_toggle_uses_wow_reloadui_api():
    assert "C_UI.Reload" not in CORE
    assert "ReloadUI()" in CORE


def test_class_color_reads_have_unknown_class_fallback():
    assert "GetClassRGB" in CORE
    assert CORE.count("GetClassRGB(") >= 3
    assert "SetBackdropColor(classR, classG, classB" in CORE
    assert "RAID_CLASS_COLORS" in CORE


def test_settings_frame_mutations_are_combat_gated():
    progress_body = function_body(CORE, "CreateProgressBar")
    assert "CanMutateProtectedFrames()" in progress_body
    assert "MarkProtectedFrameRefreshPending()" in progress_body

    assert "ApplyButtonHeight" in CORE
    height_body = function_body(CORE, "ApplyButtonHeight")
    assert "CanMutateProtectedFrames()" in height_body
    assert "MarkProtectedFrameRefreshPending()" in height_body
    assert "frame:SetSize" in height_body
    assert "SortType()" in height_body

    options_body = function_body(CORE, "GetOptions")
    assert "ApplyButtonHeight()" in options_body


def test_addon_compartment_and_context_menu_hooks_are_guarded():
    assert "if AddonCompartmentFrame and AddonCompartmentFrame.RegisterAddon then" in CORE
    assert "MENU_LFG_FRAME_SEARCH_ENTRY" not in CORE
    assert "MENU_LFG_FRAME_MEMBER_APPLY" not in CORE


def test_packager_excludes_repo_only_files():
    assert "ignore:" in PKGMETA
    assert "- tests" in PKGMETA
    assert "- scripts" in PKGMETA
    assert "- .github" in PKGMETA
    assert "- .pytest_cache" in PKGMETA
    assert "- backups" in PKGMETA
    assert "dist/" in GITIGNORE
    assert "backups/" in GITIGNORE
    assert ".pytest_cache/" in GITIGNORE


def test_midnight_release_has_source_changelog():
    assert CHANGELOG.exists()
    changelog = CHANGELOG.read_text(encoding="utf-8")
    assert "## v1.0.24-midnight.1" in changelog
    assert "Midnight" in changelog


def test_local_package_script_documents_expected_zip_surface():
    assert PACKAGE_SCRIPT.exists()
    script = PACKAGE_SCRIPT.read_text(encoding="utf-8")
    assert "EvokerAug-v1.0.24-midnight.1.zip" in script
    assert "dist" in script
    for ignored in [".git", ".github", "tests", "scripts", ".pytest_cache", "dist", "backups", ".gitignore", ".pkgmeta"]:
        assert ignored in script


def test_local_install_script_uses_backup_and_junction():
    assert INSTALL_SCRIPT.exists()
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "C:\\Games\\World of Warcraft\\_retail_" in script
    assert "Interface\\AddOns" in script
    assert "backups" in script
    assert "Move-Item" in script
    assert "New-Item -ItemType Junction" in script
    assert "-Apply" in script
    assert "Resolve-Path" in script
