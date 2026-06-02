from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CORE = (ROOT / "Core" / "EvokerAug.lua").read_text(encoding="utf-8")
CONFIG = (ROOT / "Core" / "Config.lua").read_text(encoding="utf-8")
TOC = (ROOT / "EvokerAug.toc").read_text(encoding="utf-8")
PKGMETA = (ROOT / ".pkgmeta").read_text(encoding="utf-8")
GITIGNORE = (ROOT / ".gitignore").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
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


def test_default_frame_starts_unlocked_for_initial_positioning():
    assert "headerunlock = true" in CONFIG

    drag_body = re.search(
        r'selectedPlayerFrameContainer:SetScript\("OnDragStart".*?end\)',
        CORE,
        re.S,
    )
    assert drag_body, "OnDragStart handler is missing"
    assert "self.db.profile.headerunlock" in drag_body.group(0)
    assert "sel:StartMoving()" in drag_body.group(0)


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


def test_party_frames_use_stable_identity_keys_not_short_names():
    assert "GetUnitIdentity" in CORE
    assert "GetPlayerFrameIndexByIdentity" in CORE
    assert "IsPlayerFrameByIdentity" in CORE

    add_home_body = function_body(CORE, "AddHomePartyInfo")
    assert "local identityKey, name = GetUnitIdentity(unit)" in add_home_body
    assert "identityKey = identityKey" in add_home_body

    create_body = function_body(CORE, "CreateSelectedPlayerFrame")
    assert "identityKey = identityKey or playerName" in create_body
    assert "selectedPlayerFrames[frameIndex].identityKey = identityKey" in create_body
    assert "checkboxStates[identityKey] = true" in create_body
    assert "checkboxStates[playerName] = true" not in create_body

    index_body = function_body(CORE, "GetPlayerFrameIndexByIdentity")
    assert "if not identityKey then" in index_body
    assert "frame.identityKey == identityKey" in index_body
    assert "frame.playerName == name" not in index_body

    delete_body = function_body(CORE, "DeleteSelectedPlayerFrame")
    assert "if not identityKey then" in delete_body
    assert "local playerIndex = GetPlayerFrameIndexByIdentity(identityKey)" in delete_body
    assert "checkboxStates[identityKey] = nil" in delete_body
    assert "checkboxStates[playerName] = false" not in CORE

    delete_all_body = function_body(CORE, "DeleteAllSelectedPlayerFrames")
    assert "frame.identityKey or frame.playerName" in delete_all_body

    for name in ("FrameAutoFill", "GroupUpdate", "RightMenu"):
        body = function_body(CORE, name)
        assert "member.identityKey" in body, name

    favorite_body = function_body(CORE, "AddFavoriteFrameForUnit")
    assert "identityKey" in favorite_body
    assert "IsPlayerFrameByIdentity(identityKey)" in favorite_body


def test_group_update_removes_frames_without_forward_ipairs_mutation():
    body = function_body(CORE, "GroupUpdate")
    assert "for i = #selectedPlayerFrames, 1, -1 do" in body
    assert "selectedPlayerFrames[i]" in body
    assert "for _, frame in ipairs(selectedPlayerFrames)" not in body


def test_group_update_refreshes_role_class_and_unit_changes():
    body = function_body(CORE, "GroupUpdate")
    assert "roleChanged" in body
    assert "classChanged" in body
    assert "frame.role ~= member.role" in body
    assert "frame.class ~= member.class" in body
    assert "unitCheckChanged or roleChanged or classChanged" in body
    assert "CreateSelectedPlayerFrame(memberName, memberClass, memberRole, unit, unittt, identityKey)" in body


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


def test_aura_icons_require_clean_expiration_and_duration():
    add_body = function_body(CORE, "AddBuffIcon")
    assert "not IsCleanPositiveNumber(timestamp)" in add_body
    assert "not IsCleanPositiveNumber(startTimer)" in add_body

    unit_aura_body = CORE[CORE.index('elseif event == "UNIT_AURA"') :]
    unit_aura_body = unit_aura_body[: unit_aura_body.index('elseif event == "UNIT_FLAGS"')]
    assert "ReconcileTrackedAurasForUnit(unit)" in unit_aura_body
    assert "info == nil" in unit_aura_body
    assert "info.isFullUpdate" in unit_aura_body

    reconcile_body = function_body(CORE, "ReconcileTrackedAurasForUnit")
    assert "ClearBuffIcons(selectedPlayerFrames[frameIndex])" in reconcile_body
    assert "AddBuffIcons(selectedPlayerFrames[frameIndex], unit)" in reconcile_body


def test_custom_spell_options_use_spell_name_and_icon_texture():
    classes_body = function_body(CORE, "GetClasses")
    assert "if spell and spell.name and spell.iconID then" in classes_body

    add_body = function_body(CORE, "SpellListAdd")
    option_body = function_body(CORE, "AddTrackedBuffOption")
    assert "Spell.name" in add_body
    assert "name = spellName" in option_body
    assert "image = iconID" in option_body
    assert "name = Spell.iconID" not in add_body
    assert "image = icon" not in add_body


def test_tracked_buffs_use_explicit_disabled_and_custom_state():
    assert "disabledBuffList = {}" in CONFIG
    assert "customBuffList = {}" in CONFIG

    set_body = function_body(CORE, "SetTrackedBuff")
    assert "addon.db.profile.disabledBuffList[spellID] = true" in set_body
    assert "addon.db.profile.disabledBuffList[spellID] = nil" in set_body
    assert "addon.db.profile.customBuffList[spellID] = spellName" in set_body
    assert "addon.db.profile.customBuffList[spellID] = nil" in set_body

    find_body = function_body(CORE, "FindTrackedAuraBySpellID")
    assert "IsTrackedBuffEnabled(aura.spellId)" in find_body

    add_icons_body = function_body(CORE, "AddBuffIcons")
    assert "IsTrackedBuffEnabled(k)" in add_icons_body

    unit_aura_body = CORE[CORE.index('elseif event == "UNIT_AURA"') :]
    unit_aura_body = unit_aura_body[: unit_aura_body.index('elseif event == "UNIT_FLAGS"')]
    assert "IsTrackedBuffEnabled(v.spellId)" in unit_aura_body
    assert "IsTrackedBuffEnabled(aura.spellId)" in unit_aura_body

    spell_add_body = function_body(CORE, "SpellListAdd")
    assert "SetTrackedBuff(spellId, Spell.name, true, true)" in spell_add_body
    assert "AddTrackedBuffOption(spellId, Spell.name, Spell.iconID, true" in spell_add_body

    options_body = function_body(CORE, "GetOptions")
    assert "SeedCustomBuffListFromBuffList()" in options_body
    assert "AddTrackedBuffOption(k, v.name, v.icon, false" in options_body
    assert "AddSavedCustomSpellOptions()" in options_body

    assert "addon.db.profile.buffList[k] = nil" not in CORE
    assert "addon.db.profile.buffList[spellId] = nil" not in CORE


def test_omnicd_toggle_uses_wow_reloadui_api():
    assert "C_UI.Reload" not in CORE
    assert "ReloadUI()" in CORE


def test_class_color_reads_have_unknown_class_fallback():
    assert "GetClassRGB" in CORE
    assert CORE.count("GetClassRGB(") >= 3
    assert "SetVertexColor(classR, classG, classB" in CORE
    assert "RAID_CLASS_COLORS" in CORE


def test_prescience_bar_uses_class_fill_over_dark_track():
    assert "local PRESCIENCE_ICON_ID = 5199639" in CORE
    assert "local PLAYER_FRAME_WIDTH = 150" in CORE
    assert "ApplyPrescienceBarFill" in CORE

    helper_body = function_body(CORE, "ApplyPrescienceBarFill")
    assert "PLAYER_FRAME_WIDTH * (remaining / startDuration)" in helper_body
    assert "math.min(PLAYER_FRAME_WIDTH" in helper_body
    assert "math.max(1" in helper_body
    assert "RefreshPrescienceBarFill" in CORE

    create_body = function_body(CORE, "CreateSelectedPlayerFrame")
    assert "SetBackdropColor(0.08, 0.08, 0.08" in create_body
    assert "ApplyPrescienceBarFill(selectedPlayerFrames[frameIndex], nil, nil)" in create_body

    add_body = function_body(CORE, "AddBuffIcon")
    assert "icon == PRESCIENCE_ICON_ID" in add_body
    assert "ApplyPrescienceBarFill(playerFrame, timestamp, startTimer)" in add_body

    remove_body = function_body(CORE, "RemoveBuffIcon")
    assert "iconFrame.iconid == PRESCIENCE_ICON_ID" in remove_body
    assert "ApplyPrescienceBarFill(playerFrame, nil, nil)" in remove_body

    clear_body = function_body(CORE, "ClearBuffIcons")
    assert "ApplyPrescienceBarFill(playerFrame, nil, nil)" in clear_body

    height_body = function_body(CORE, "ApplyButtonHeight")
    assert "RefreshPrescienceBarFill(frame)" in height_body

    options_body = function_body(CORE, "GetOptions")
    assert "RefreshPrescienceBarFill(frame)" in options_body


def test_buff_icon_spacing_tracks_icon_size_changes():
    reposition_body = function_body(CORE, "RepositionBuffIcons")
    assert "addon.db.profile.spellIconSize" in reposition_body
    assert "addon.db.profile.buttonHeight" not in reposition_body

    add_body = function_body(CORE, "AddBuffIcon")
    assert 'playerFrame["buff"].xOffset + addon.db.profile.spellIconSize' in add_body

    assert "ApplySpellIconSize" in CORE
    apply_body = function_body(CORE, "ApplySpellIconSize")
    assert "CanMutateProtectedFrames()" in apply_body
    assert "v2:SetSize(addon.db.profile.spellIconSize, addon.db.profile.spellIconSize)" in apply_body
    assert "RepositionBuffIcons(frame)" in apply_body

    options_body = function_body(CORE, "GetOptions")
    assert "ApplySpellIconSize()" in options_body

    regen_body = CORE[CORE.index('elseif event == "PLAYER_REGEN_ENABLED"') :]
    regen_body = regen_body[: regen_body.index('elseif event == "PLAYER_ENTERING_WORLD"')]
    assert "ApplySpellIconSize()" in regen_body


def test_distance_dimming_avoids_secure_frame_alpha_mutations():
    distance_body = function_body(CORE, "CheckDistance")
    assert "playerFrame:SetAlpha" not in distance_body
    assert "ApplyPlayerFrameVisualAlpha(playerFrame" in distance_body

    alpha_body = function_body(CORE, "ApplyPlayerFrameVisualAlpha")
    assert "playerFrame.visualAlpha = alpha" in alpha_body
    assert "playerFrame.texture:SetAlpha(alpha)" in alpha_body
    assert "playerFrame.playerNameText:SetAlpha(alpha)" in alpha_body
    assert 'string.match(tostring(key), "Text$")' in alpha_body
    assert "region:SetAlpha(alpha)" in alpha_body
    assert "playerFrame:SetAlpha" not in alpha_body

    add_body = function_body(CORE, "AddBuffIcon")
    assert "local visualAlpha = playerFrame.visualAlpha or 0.9" in add_body
    assert ":SetAlpha(visualAlpha)" in add_body


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


def test_instance_transitions_revalidate_latest_context():
    assert "local instanceContextGeneration = 0" in CORE
    assert "IsCurrentInstanceContext" in CORE

    handler_body = CORE[CORE.index('elseif event == "PLAYER_ENTERING_WORLD"') :]
    handler_body = handler_body[: handler_body.index('elseif event == "PLAYER_SPECIALIZATION_CHANGED"')]
    assert "instanceContextGeneration = instanceContextGeneration + 1" in handler_body
    assert "local generation = instanceContextGeneration" in handler_body
    assert 'IsCurrentInstanceContext(generation, "party")' in handler_body
    assert 'IsCurrentInstanceContext(generation, "none")' in handler_body
    assert "addon.db.profile.autoFrameFill" in handler_body


def test_instance_visibility_uses_shared_policy():
    assert "ShouldShowForInstanceType" in CORE
    assert "IsRuntimeVisibilityAllowed" in CORE
    assert "ApplyInstanceVisibilityPolicy" in CORE
    assert "elseif not addon.db.profile.showMythic" not in CORE

    visibility_body = function_body(CORE, "ApplyInstanceVisibilityPolicy")
    assert "ShouldShowForInstanceType(instanceType)" in visibility_body
    assert "IsRuntimeVisibilityAllowed()" in visibility_body
    assert "HideAllSubFrames()" in visibility_body

    enable_body = function_body(CORE, "EnableAllFrame")
    assert "IsRuntimeVisibilityAllowed()" in enable_body

    regen_body = CORE[CORE.index('elseif event == "PLAYER_REGEN_ENABLED"') :]
    regen_body = regen_body[: regen_body.index('elseif event == "PLAYER_ENTERING_WORLD"')]
    assert "if not ApplyInstanceVisibilityPolicy() then" in regen_body


def test_frame_visibility_option_uses_toggle_value():
    frame_hide_section = CORE[CORE.index("frameHide = {") : CORE.index("autoFrame = {")]
    assert 'name = "Show Frame"' in frame_hide_section
    assert "if value then" in frame_hide_section
    assert "EnableAllFrame()" in frame_hide_section
    assert "else" in frame_hide_section
    assert "HideAllSubFrames()" in frame_hide_section


def test_favorite_list_mutations_keep_compact_array():
    assert "NormalizeFavoriteList" in CORE
    assert "AddFavoriteName" in CORE
    assert "RemoveFavoriteName" in CORE

    ordered_body = function_body(CORE, "GetOrderedFavoriteList")
    assert "table.sort(keys)" in ordered_body
    assert "pairs(favList)" in ordered_body

    normalize_body = function_body(CORE, "NormalizeFavoriteList")
    assert "GetOrderedFavoriteList()" in normalize_body
    assert "favList[key] = nil" in normalize_body

    rank_body = function_body(CORE, "GetFavoriteRank")
    assert "GetOrderedFavoriteList()" in rank_body

    compare_body = function_body(CORE, "CompareFavoriteRank")
    assert "GetFavoriteRank(a.identityKey)" in compare_body
    assert "GetFavoriteRank(b.identityKey)" in compare_body

    for sort_name in ("sortFramesByName", "sortFramesByClass", "sortFramesByRole"):
        sort_body = function_body(CORE, sort_name)
        assert "CompareFavoriteRank(a, b)" in sort_body
        assert "ipairs(favList)" not in sort_body

    options_body = function_body(CORE, "GetOptions")
    assert "NormalizeFavoriteList()" in options_body
    assert "AddFavoriteName(v)" in options_body
    assert "RemoveFavoriteName(v)" in options_body
    assert "return IsFavoriteName(v)" in options_body
    assert "addon.db.profile.favoriPlayer[k] = nil" not in CORE

    menu_body = function_body(CORE, "MenuHandler")
    assert "AddFavoriteName(name)" in menu_body
    assert "RemoveFavoriteName(name)" in menu_body
    assert "table.insert(addon.db.profile.favoriPlayer" not in menu_body


def test_omnicd_support_toggle_persists_even_when_omnicd_unavailable():
    options_body = function_body(CORE, "GetOptions")
    omni_section = options_body[options_body.index("OmniCDSupport = {") :]
    omni_section = omni_section[: omni_section.index("profiles = profiles")]
    persist_index = omni_section.index("addon.db.profile.omniCDSupport = value")
    availability_index = omni_section.index("if loaded or state == 2 then")
    assert persist_index < availability_index
    assert "ReloadUI()" in omni_section


def test_context_menu_payload_is_guarded_before_favorite_action():
    body = function_body(CORE, "MenuHandler")
    assert "if not contextData or not contextData.name then" in body
    assert 'if not string.find(name, "-") then' in body
    assert 'contextData.server ~= ""' in body


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


def test_packager_uses_curated_changelog_for_release_notes():
    assert re.search(r"(?m)^manual-changelog:\s*$", PKGMETA)
    assert re.search(r"(?m)^  filename: CHANGELOG\.md\s*$", PKGMETA)
    assert re.search(r"(?m)^  markup-type: markdown\s*$", PKGMETA)
    assert "# manual-changelog" not in PKGMETA


def test_release_workflow_gates_packager_on_static_checks():
    assert re.search(r"(?m)^  preflight:\s*$", WORKFLOW)
    assert re.search(r"(?m)^  packager:\s*$", WORKFLOW)
    assert re.search(r"(?m)^    needs: preflight\s*$", WORKFLOW)
    assert "python -m pip install pytest" in WORKFLOW
    assert "python -m pytest tests/test_midnight_port_static.py -q" in WORKFLOW
    assert "sudo apt-get install -y lua5.1" in WORKFLOW
    assert "luac5.1 -p Core/Config.lua Core/EvokerAug.lua Core/SpellList.lua" in WORKFLOW


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
