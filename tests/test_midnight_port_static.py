from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CORE = (ROOT / "Core" / "EvokerAug.lua").read_text(encoding="utf-8")
CONFIG = (ROOT / "Core" / "Config.lua").read_text(encoding="utf-8")
SPELL_LIST = (ROOT / "Core" / "SpellList.lua").read_text(encoding="utf-8")
TOC = (ROOT / "EvokerAug.toc").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
PKGMETA = (ROOT / ".pkgmeta").read_text(encoding="utf-8")
GITIGNORE = (ROOT / ".gitignore").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
CHANGELOG = ROOT / "CHANGELOG.md"
PACKAGE_SCRIPT = ROOT / "scripts" / "package-local.ps1"
INSTALL_SCRIPT = ROOT / "scripts" / "install-local-junction.ps1"
RELEASE_VERSION_SCRIPT = ROOT / "scripts" / "check-release-version.py"


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"(?:local\s+)?function\s+{re.escape(name)}\b|^{re.escape(name)}\s*=\s*function\b",
        source,
        re.M,
    )
    assert match, f"{name} is missing"
    next_match = re.search(
        r"\n(?:(?:local\s+)?function\s+[\w:]+|[A-Za-z_][A-Za-z0-9_]*\s*=\s*function)",
        source[match.end() :],
    )
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
    assert "CanMutateProtectedFrames()" in drag_body.group(0)
    assert "sel:StartMoving()" in drag_body.group(0)


def test_aura_tracking_is_spell_id_based_for_midnight():
    assert "GetAuraDataBySpellName" not in CORE
    assert "COMBAT_LOG_EVENT_UNFILTERED" not in CORE
    assert "GetSpellCooldown" not in CORE
    assert "GetSpellCharges" not in CORE
    assert "FindTrackedAuraBySpellID" in CORE
    assert "EBON_MIGHT_SPELL_IDS" in CORE
    assert "issecretvalue" in CORE
    assert "IsCleanPositiveNumber" in CORE

    find_body = function_body(CORE, "FindAuraBySpellID")
    assert "GetUnitAuraBySpellID" in find_body
    assert "GetAuraDataByIndex" not in find_body
    assert "for index = 1, 40" not in find_body

    exists_body = function_body(CORE, "HasHelpfulAuraBySpellID")
    assert "GetUnitAuraBySpellID" in exists_body
    assert "AuraUtil.ForEachAura" in exists_body
    assert "IsUsableAuraData" not in exists_body


def test_localized_class_names_are_not_used_as_class_tokens():
    assert "GetUnitClassToken" in CORE
    assert CORE.count("UnitClass(") == 1


def test_midnight_devourer_uses_generic_demon_hunter_dps_path():
    """Devourer DH is a Midnight DPS spec; EvokerAug should not need a specID whitelist."""
    assert "1480" not in CORE
    assert "Devourer" not in CORE
    assert "Havoc" not in CORE
    assert "Vengeance" not in CORE
    assert "DEMONHUNTER" not in CORE

    add_home_body = function_body(CORE, "AddHomePartyInfo")
    assert "GetUnitClassToken(unit)" in add_home_body
    assert 'UnitGroupRolesAssigned(unit)' in add_home_body
    assert 'if combatRole == "DAMAGER" then' in add_home_body
    assert 'combatRole = "DPS"' in add_home_body
    assert 'class = strupper(string.gsub(class, "%s+", ""))' in add_home_body

    favorite_body = function_body(CORE, "AddFavoriteFrameForUnit")
    assert "GetUnitClassToken(unitID)" in favorite_body
    assert 'UnitGroupRolesAssigned(unitID)' in favorite_body
    assert 'combatRole = "DPS"' in favorite_body

    autofill_body = function_body(CORE, "FrameAutoFill")
    assert 'member.role == "DPS"' in autofill_body
    assert 'member.role ~= "HEALER"' not in autofill_body

    macro_body = function_body(CORE, "MacroUpdate")
    assert 'frame.role == "TANK" and addon.db.profile.tankMacros or addon.db.profile.dpsMacros' in macro_body


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


def test_disconnected_units_are_filtered_across_refresh_paths():
    assert "IsEligibleGroupUnit" in CORE

    helper_body = function_body(CORE, "IsEligibleGroupUnit")
    assert "UnitExists(unit)" in helper_body
    assert "UnitIsConnected(unit)" in helper_body

    add_home_body = function_body(CORE, "AddHomePartyInfo")
    assert "if not IsEligibleGroupUnit(unit) then" in add_home_body
    assert "UnitExists(unit)" not in add_home_body
    assert "UnitIsConnected(unit)" not in add_home_body

    favorite_body = function_body(CORE, "AddFavoriteFrameForUnit")
    assert "if not IsEligibleGroupUnit(unitID) then" in favorite_body
    assert "UnitExists(unitID)" not in favorite_body
    assert "UnitIsConnected(unitID)" not in favorite_body

    group_body = function_body(CORE, "GroupUpdate")
    assert "local partyMembers = GetHomePartyInfos()" in group_body
    assert "UnitIsConnected" not in group_body

    on_enable_body = function_body(CORE, "addon:OnEnable")
    assert 'selectedPlayerFrameContainer:RegisterEvent("UNIT_CONNECTION")' in on_enable_body

    connection_body = CORE[CORE.index('elseif event == "UNIT_CONNECTION"') :]
    connection_body = connection_body[: connection_body.index('elseif event == "PLAYER_ENTERING_WORLD"')]
    assert "RefreshRuntimeFrames()" in connection_body


def test_deleted_and_reconfigured_frames_clear_buff_tickers():
    assert "ClearBuffIcons" in CORE

    delete_body = function_body(CORE, "DeleteSelectedPlayerFrame")
    assert "ClearBuffIcons(selectedPlayerFrames[playerIndex])" in delete_body

    clear_body = function_body(CORE, "ClearSelectedFrameState")
    assert "for i = #selectedPlayerFrames, 1, -1 do" in clear_body
    assert "ClearBuffIcons(frame)" in clear_body
    assert "string.match(i" not in clear_body
    assert "break" not in clear_body


def test_profile_callbacks_use_single_combat_aware_apply_path():
    assert "local pendingActiveProfileApply = false" in CORE
    assert "ApplyActiveProfile" in CORE
    assert "PopulateCharSpellDefaults" in CORE

    init_body = function_body(CORE, "addon:OnInitialize")
    assert 'self.db.RegisterCallback(self, "OnProfileReset", "Reconfigure")' in init_body
    assert 'self.db.RegisterCallback(self, "OnProfileChanged", "Reconfigure")' in init_body
    assert 'self.db.RegisterCallback(self, "OnProfileCopied", "Reconfigure")' in init_body

    reconfigure_body = function_body(CORE, "addon:Reconfigure")
    assert "ApplyActiveProfile()" in reconfigure_body
    assert "copytable" not in reconfigure_body

    apply_body = function_body(CORE, "ApplyActiveProfile")
    assert "PopulateCharSpellDefaults()" in apply_body
    assert "SeedCustomBuffListFromBuffList()" in apply_body
    assert "NormalizeFavoriteList()" in apply_body
    assert "AceConfigRegistry:NotifyChange(addonName)" in apply_body
    assert "if not CanMutateProtectedFrames() then" in apply_body
    assert "pendingActiveProfileApply = true" in apply_body
    assert "ClearSelectedFrameState()" in apply_body
    assert "LoadPosition(selectedPlayerFrameContainer)" in apply_body
    assert "selectedPlayerFrameContainer:RegisterEvent(\"PLAYER_ENTERING_WORLD\")" in apply_body
    assert "selectedPlayerFrameContainer:UnregisterEvent(\"PLAYER_ENTERING_WORLD\")" not in apply_body
    assert "RegisterOmniCDFrameData()" in apply_body
    assert "CreateProgressBar()" in apply_body

    regen_body = CORE[CORE.index('elseif event == "PLAYER_REGEN_ENABLED"') :]
    regen_body = regen_body[: regen_body.index('elseif event == "PLAYER_ENTERING_WORLD"')]
    assert "if pendingActiveProfileApply then" in regen_body
    assert "ApplyActiveProfile()" in regen_body


def test_malformed_savedvariables_are_normalized_before_profile_use():
    assert "NormalizeProfileShape" in CORE

    normalize_body = function_body(CORE, "NormalizeProfileShape")
    for table_key in (
        "buffList",
        "disabledBuffList",
        "customBuffList",
        "favoriPlayer",
        "macro",
        "tankMacros",
        "dpsMacros",
        "charSpell",
        "minimap",
        "positions",
    ):
        assert f'EnsureProfileTable(profile, defaults, "{table_key}")' in normalize_body

    assert 'ClampNumberSetting(profile, defaults, "buttonHeight", 20, 40)' in normalize_body
    assert 'ClampNumberSetting(profile, defaults, "spellIconSize", 20, 40)' in normalize_body
    assert 'ClampNumberSetting(profile, defaults, "spellIconTextSize", 12, 20)' in normalize_body
    assert 'if not sortTypes[profile.sortType] then' in normalize_body
    assert "profile.sortType = defaults.sortType" in normalize_body

    init_body = function_body(CORE, "addon:OnInitialize")
    assert "NormalizeProfileShape()" in init_body
    assert init_body.index("NormalizeProfileShape()") < init_body.index("SeedCustomBuffListFromBuffList()")

    apply_body = function_body(CORE, "ApplyActiveProfile")
    assert "NormalizeProfileShape()" in apply_body
    assert apply_body.index("NormalizeProfileShape()") < apply_body.index("SeedCustomBuffListFromBuffList()")


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


def test_core_spell_labels_use_spell_info_with_corrected_fallbacks():
    assert "Sourceof Magic" not in SPELL_LIST
    assert "Source of Magic" in SPELL_LIST

    populate_body = function_body(CORE, "PopulateCharSpellDefaults")
    assert "C_Spell.GetSpellInfo(spell.spellID)" in populate_body
    assert "spellInfo and spellInfo.name or spell.name" in populate_body
    assert "addon.db.profile.charSpell[spell.spellID] = spellName" in populate_body


def test_sense_power_uses_cast_spell_id_separate_from_visible_aura():
    castable_spell_block = SPELL_LIST[
        SPELL_LIST.index('addon.SpellList = {') : SPELL_LIST.index('addon.AllSpellList = {')
    ]
    assert '["name"] = "Sense Power", ["iconID"] = 132160, ["spellID"] = 361021' in castable_spell_block
    assert '["name"] = "Sense Power", ["iconID"] = 132160, ["spellID"] = 361022' not in castable_spell_block

    tracked_buff_section = SPELL_LIST[SPELL_LIST.index('addon.AllSpellList = {') :]
    assert '[361022] = "Sense Power"' in tracked_buff_section
    assert '[361022] = "Sense Power"' in CONFIG

    normalize_body = function_body(CORE, "NormalizeSensePowerSpellIDs")
    assert "addon.SENSE_POWER_CAST_SPELL_ID = 361021" in CORE
    assert "addon.SENSE_POWER_AURA_SPELL_ID = 361022" in CORE
    assert "profile.charSpell[addon.SENSE_POWER_AURA_SPELL_ID] = nil" in normalize_body
    assert "macroTable[key] = addon.SENSE_POWER_CAST_SPELL_ID" in normalize_body
    assert "NormalizeSensePowerSpellIDs(profile)" in function_body(CORE, "NormalizeProfileShape")


def test_tracked_buffs_use_explicit_disabled_and_custom_state():
    assert "disabledBuffList = {}" in CONFIG
    assert "customBuffList = {}" in CONFIG

    set_body = function_body(CORE, "SetTrackedBuff")
    assert "addon.db.profile.disabledBuffList[spellID] = true" in set_body
    assert "addon.db.profile.disabledBuffList[spellID] = nil" in set_body
    assert "addon.db.profile.customBuffList[spellID] = spellName" in set_body
    assert "addon.db.profile.customBuffList[spellID] = nil" in set_body

    find_body = function_body(CORE, "FindTrackedAuraBySpellID")
    assert "IsTrackedAuraData(aura)" in find_body

    add_icons_body = function_body(CORE, "AddBuffIcons")
    assert "IsTrackedBuffEnabled(k)" in add_icons_body

    unit_aura_body = CORE[CORE.index('elseif event == "UNIT_AURA"') :]
    unit_aura_body = unit_aura_body[: unit_aura_body.index('elseif event == "UNIT_FLAGS"')]
    assert "IsTrackedAuraData(v)" in unit_aura_body
    assert "IsTrackedAuraData(aura)" in unit_aura_body

    spell_add_body = function_body(CORE, "SpellListAdd")
    assert "SetTrackedBuff(spellId, Spell.name, true, true)" in spell_add_body
    assert "AddTrackedBuffOption(spellId, Spell.name, Spell.iconID, true" in spell_add_body

    options_body = function_body(CORE, "GetOptions")
    assert "SeedCustomBuffListFromBuffList()" in options_body
    assert "AddTrackedBuffOption(k, v.name, v.icon, false" in options_body
    assert "AddSavedCustomSpellOptions()" in options_body

    assert "addon.db.profile.buffList[k] = nil" not in CORE
    assert "addon.db.profile.buffList[spellId] = nil" not in CORE


def test_tracked_buff_setting_changes_reconcile_active_icons():
    assert "ReconcileTrackedAurasForAllSelectedUnits" in CORE

    set_body = function_body(CORE, "SetTrackedBuff")
    assert "ReconcileTrackedAurasForAllSelectedUnits()" in set_body

    reconcile_all_body = function_body(CORE, "ReconcileTrackedAurasForAllSelectedUnits")
    assert "for _, frame in ipairs(selectedPlayerFrames)" in reconcile_all_body
    assert "if frame.unit then" in reconcile_all_body
    assert "ReconcileTrackedAurasForUnit(frame.unit)" in reconcile_all_body


def test_offensive_buff_defaults_cover_major_visible_burst_windows():
    assert "addon.OffensiveBuffList = {" in SPELL_LIST
    assert "OFFENSIVE_TIER_MAJOR" in CORE
    assert "OFFENSIVE_TIER_MINOR" in CORE

    for spell_id, name in {
        51271: "Pillar of Frost",
        162264: "Metamorphosis",
        1217607: "Void Metamorphosis",
        194223: "Celestial Alignment",
        375087: "Dragonrage",
        19574: "Bestial Wrath",
        190319: "Combustion",
        365362: "Arcane Surge",
        137639: "Storm, Earth, and Fire",
        31884: "Avenging Wrath",
        10060: "Power Infusion",
        13750: "Adrenaline Rush",
        114051: "Ascendance",
        265273: "Summon Demonic Tyrant",
        107574: "Avatar",
    }.items():
        assert f"[{spell_id}] = " in SPELL_LIST
        assert f'name = "{name}"' in SPELL_LIST

    assert 'tier = "major"' in SPELL_LIST
    assert 'tier = "minor"' in SPELL_LIST
    assert "Devourer" not in SPELL_LIST
    assert "1480" not in SPELL_LIST


def test_rogue_offensive_defaults_cover_cast_based_burst_windows():
    for spell_id, name in {
        360194: "Deathmark",
        385627: "Kingsbane",
        384631: "Flagellation",
        51690: "Killing Spree",
        280719: "Secret Technique",
        382245: "Cold Blood",
        426591: "Goremaw's Bite",
    }.items():
        assert f"[{spell_id}] = " in SPELL_LIST
        assert f'name = "{name}"' in SPELL_LIST

    rogue_section = SPELL_LIST[
        SPELL_LIST.index('[13750] = { name = "Adrenaline Rush"') :
        SPELL_LIST.index('[1219480] = { name = "Ascendance"')
    ]
    assert 'castWindow = 16' in rogue_section
    assert 'castWindow = 14' in rogue_section
    assert 'castWindow = 12' in rogue_section
    assert 'castSpellID = 185313' in rogue_section


def test_offensive_cast_windows_use_spellcast_events_not_cooldown_apis():
    assert 'RegisterEvent("UNIT_SPELLCAST_SUCCEEDED")' in CORE
    assert "RecordOffensiveCastWindow(unit, spellID)" in CORE
    assert "GetOffensiveCastWindowStateForUnit(unit)" in function_body(CORE, "GetOffensiveStateForUnit")
    assert "C_Spell.GetSpellCooldown" not in CORE
    assert "C_Spell.GetSpellCharges" not in CORE
    assert "COMBAT_LOG_EVENT_UNFILTERED" not in CORE

    record_body = function_body(CORE, "RecordOffensiveCastWindow")
    assert "GetOffensiveBuffDefinitionForCastSpellID(spellID)" in record_body
    assert "UnitGUID(unit)" in record_body
    assert "GetTime() + castWindow" in record_body
    assert "C_Timer.After(castWindow" in record_body
    assert "RefreshOffensiveHighlightSurfacesForUnit(unit)" in record_body


def test_offensive_buff_profile_state_is_separate_from_tracked_buff_icons():
    assert "offensiveBuffs = {" in CONFIG
    assert "disabled = {}" in CONFIG
    assert "custom = {}" in CONFIG
    assert "tiers = {}" in CONFIG

    normalize_body = function_body(CORE, "NormalizeProfileShape")
    assert 'EnsureProfileTable(profile, defaults, "offensiveBuffs")' in normalize_body
    assert "NormalizeOffensiveBuffState()" in normalize_body

    ensure_body = function_body(CORE, "EnsureOffensiveBuffStateTables")
    assert 'EnsureProfileTable(profile.offensiveBuffs, defaults.offensiveBuffs, "disabled")' in ensure_body
    assert 'EnsureProfileTable(profile.offensiveBuffs, defaults.offensiveBuffs, "custom")' in ensure_body
    assert 'EnsureProfileTable(profile.offensiveBuffs, defaults.offensiveBuffs, "tiers")' in ensure_body

    definition_body = function_body(CORE, "GetOffensiveBuffDefinition")
    assert "addon.OffensiveBuffList" in definition_body
    assert "offensiveBuffs.custom" in definition_body
    assert "GetCleanPositiveSpellID(spellID)" in definition_body

    assert "offensiveBuffs" not in function_body(CORE, "AddBuffIcons")


def test_offensive_buff_state_mapping_and_visual_layers_are_explicit():
    assert "OFFENSIVE_STATE_NONE" in CORE
    assert "OFFENSIVE_STATE_MINOR" in CORE
    assert "OFFENSIVE_STATE_MAJOR" in CORE
    assert "OFFENSIVE_STATE_BOTH" in CORE
    assert "OFFENSIVE_MAJOR_GLOW_KEY" in CORE

    state_body = function_body(CORE, "GetOffensiveStateForUnit")
    assert "HasHelpfulAuraBySpellID(unit, spellID)" in state_body
    assert "IsOffensiveBuffEnabled(spellID)" in state_body
    assert "return OFFENSIVE_STATE_BOTH" in state_body
    assert "return OFFENSIVE_STATE_MAJOR" in state_body
    assert "return OFFENSIVE_STATE_MINOR" in state_body
    assert "return OFFENSIVE_STATE_NONE" in state_body

    apply_body = function_body(CORE, "ApplyOffensiveBuffVisualState")
    assert "LibCustomGlow.PixelGlow_Start" in apply_body
    assert "LibCustomGlow.PixelGlow_Stop(playerFrame, OFFENSIVE_MAJOR_GLOW_KEY)" in apply_body
    assert "playerFrame.offensiveMinorMarker" in apply_body
    assert "OFFENSIVE_MINOR_MARKER_COLOR" in apply_body
    assert "playerFrame.offensiveState = state" in apply_body


def test_blizzard_compact_frame_highlights_reuse_offensive_state():
    assert "blizzardFrameHighlights = {" in CONFIG
    assert "blizzardCompactFrameOverlays = {}" in CORE
    assert "BLIZZARD_COMPACT_MAJOR_GLOW_KEY" in CORE
    assert "RefreshBlizzardCompactFrameHighlightsForAllUnits" in CORE

    ensure_body = function_body(CORE, "EnsureBlizzardCompactFrameOverlay")
    assert "if not CanMutateProtectedFrames() then" in ensure_body
    assert 'CreateFrame("Frame", nil, UIParent)' in ensure_body
    assert "LibCustomGlow.PixelGlow_Start(majorGlowAnchor" in ensure_body
    assert "majorGlowAnchor:SetAlpha(0)" in ensure_body

    update_body = function_body(CORE, "UpdateBlizzardCompactFrameHighlight")
    assert "frame.displayedUnit or frame.unit" in update_body
    assert "GetOffensiveStateForUnit(unit)" in update_body
    assert "SetBlizzardCompactFrameVisualState" in update_body
    assert "EnsureBlizzardCompactFrameOverlay(frame)" in update_body

    eligibility_body = function_body(CORE, "IsUnitEligibleForBlizzardCompactHighlight")
    assert 'UnitIsUnit(unit, "player")' in eligibility_body
    assert 'if combatRole == "DAMAGER" then' in eligibility_body
    assert 'return combatRole == "DPS"' in eligibility_body

    refresh_body = function_body(CORE, "RefreshBlizzardCompactFrameHighlightsForAllUnits")
    assert 'UpdateNamedBlizzardCompactFrame("CompactPartyFrameMember"' in refresh_body
    assert 'UpdateNamedBlizzardCompactFrame("CompactRaidFrame"' in refresh_body
    assert "addon.db.profile.blizzardFrameHighlights.showRaid" in refresh_body


def test_blizzard_compact_frame_highlights_are_combat_safe_and_event_driven():
    options_body = function_body(CORE, "GetOptions")
    assert "blizzardFrames = {" in options_body
    assert "addon.db.profile.blizzardFrameHighlights.enabled = value" in options_body
    assert "RefreshBlizzardCompactFrameHighlightsForAllUnits()" in options_body

    handler_body = CORE[CORE.index('selectedPlayerFrameContainer:SetScript("OnEvent"') :]
    assert 'hooksecurefunc("CompactUnitFrame_UpdateAll"' in CORE
    assert "RefreshBlizzardCompactFrameHighlightsForAllUnits()" in handler_body
    assert "RefreshBlizzardCompactFrameHighlightsForUnit(unit)" in handler_body
    assert "BlizzardCompactFrameRefreshPending()" in CORE

    regen_body = CORE[CORE.index('elseif event == "PLAYER_REGEN_ENABLED"') :]
    regen_body = regen_body[: regen_body.index('elseif event == "PLAYER_ENTERING_WORLD"')]
    assert "if blizzardCompactFrameRefreshPending then" in regen_body
    assert "RefreshBlizzardCompactFrameHighlightsForAllUnits()" in regen_body


def test_unit_aura_reconciles_offensive_highlights_without_name_scans():
    reconcile_body = function_body(CORE, "ReconcileTrackedAurasForUnit")
    assert "RefreshOffensiveBuffHighlight(selectedPlayerFrames[frameIndex], unit)" in reconcile_body

    unit_aura_body = CORE[CORE.index('elseif event == "UNIT_AURA"') :]
    unit_aura_body = unit_aura_body[: unit_aura_body.index('elseif event == "UNIT_FLAGS"')]
    assert "RefreshOffensiveBuffHighlight(selectedPlayerFrames[frameIndex], unit)" in unit_aura_body
    assert "GetAuraDataBySpellName" not in unit_aura_body
    assert "string.find" not in unit_aura_body
    assert "string.match" not in unit_aura_body


def test_offensive_buff_options_have_global_toggle_and_tier_controls():
    options_body = function_body(CORE, "GetOptions")
    assert 'offensiveBuffs = {' in options_body
    assert 'name = "Offensive Buffs"' in options_body
    assert 'addon.db.profile.offensiveBuffs.enabled = value' in options_body
    assert "AddOffensiveBuffOption" in options_body
    assert "AddSavedCustomOffensiveBuffOptions()" in options_body

    option_body = function_body(CORE, "AddOffensiveBuffOption")
    assert "SetOffensiveBuffEnabled(spellID, value, isCustom)" in option_body
    assert "SetOffensiveBuffTier(spellID, value)" in option_body
    assert "values = OFFENSIVE_TIER_LABELS" in option_body


def test_aura_payload_fields_are_secret_guarded_before_use():
    assert "GetCleanPositiveSpellID" in CORE
    assert "IsCleanAuraIcon" in CORE
    assert "IsUsableAuraData" in CORE
    assert "IsTrackedAuraData" in CORE

    enabled_body = function_body(CORE, "IsTrackedBuffEnabled")
    assert "GetCleanPositiveSpellID(spellID)" in enabled_body
    assert "tonumber(spellID)" not in enabled_body

    usable_body = function_body(CORE, "IsUsableAuraData")
    for field in ("aura.spellId", "aura.auraInstanceID", "aura.expirationTime", "aura.duration", "aura.icon"):
        assert field in usable_body
    assert "IsCleanAuraIcon(aura.icon)" in usable_body

    add_body = function_body(CORE, "AddBuffIcon")
    assert "not IsCleanPositiveNumber(auraInstanceID)" in add_body
    assert "not IsCleanAuraIcon(icon)" in add_body
    assert "local cleanSpellID = GetCleanPositiveSpellID(spellID)" in add_body
    assert "cleanSpellID == addon.SENSE_POWER_AURA_SPELL_ID" in add_body


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


def test_saved_frame_position_is_sanitized_and_saved_on_logout():
    assert "VALID_FRAME_POINTS" in CORE
    assert "SanitizePosition" in CORE
    assert "CanSetUserPlaced" in CORE
    assert "LoadPosition" in CORE
    assert "SavePosition" in CORE

    user_placed_body = function_body(CORE, "CanSetUserPlaced")
    assert "frame:IsMovable()" in user_placed_body
    assert "frame:IsResizable()" in user_placed_body

    sanitize_body = function_body(CORE, "SanitizePosition")
    assert "VALID_FRAME_POINTS[position.point]" in sanitize_body
    assert 'point = "CENTER"' in sanitize_body
    assert "type(position.xOffset) == \"number\"" in sanitize_body
    assert "type(position.yOffset) == \"number\"" in sanitize_body

    load_body = function_body(CORE, "LoadPosition")
    assert "frame:ClearAllPoints()" in load_body
    assert "frame:SetPoint(point, UIParent, point, xOffset, yOffset)" in load_body
    assert "CanSetUserPlaced(frame)" in load_body
    assert "frame:SetUserPlaced(true)" in load_body

    save_body = function_body(CORE, "SavePosition")
    assert "local point, _, _, xOffset, yOffset = frame:GetPoint()" in save_body
    assert "if not point then" in save_body
    assert "SanitizePosition" in save_body

    on_enable_body = function_body(CORE, "addon:OnEnable")
    assert "LoadPosition(selectedPlayerFrameContainer)" in on_enable_body
    assert on_enable_body.index("selectedPlayerFrameContainer:SetMovable(true)") < on_enable_body.index(
        "LoadPosition(selectedPlayerFrameContainer)"
    )
    assert 'selectedPlayerFrameContainer:RegisterEvent("PLAYER_LOGOUT")' in on_enable_body
    assert 'selectedPlayerFrameContainer:RegisterEvent("PLAYER_ENTERING_WORLD")' in on_enable_body
    assert "SavePosition(selectedPlayerFrameContainer)" in on_enable_body
    assert "self.db.profile.positions.point, self.db.profile.positions.xOffset" not in on_enable_body

    apply_body = function_body(CORE, "ApplyActiveProfile")
    assert "LoadPosition(selectedPlayerFrameContainer)" in apply_body
    assert "addon.db.profile.positions.point, addon.db.profile.positions.xOffset" not in apply_body


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
    assert "RefreshRuntimeFrames" in CORE
    assert "elseif not addon.db.profile.showMythic" not in CORE

    runtime_body = function_body(CORE, "IsRuntimeVisibilityAllowed")
    assert 'GetUnitClassToken("player")' in runtime_body
    assert '"EVOKER"' in runtime_body
    assert "addon.db.profile.enabled" in runtime_body

    visibility_body = function_body(CORE, "ApplyInstanceVisibilityPolicy")
    assert "ShouldShowForInstanceType(instanceType)" in visibility_body
    assert "IsRuntimeVisibilityAllowed()" in visibility_body
    assert "HideAllSubFrames()" in visibility_body

    enable_body = function_body(CORE, "EnableAllFrame")
    assert "IsRuntimeVisibilityAllowed()" in enable_body
    assert "SyncProgressBarVisibility()" in enable_body

    regen_body = CORE[CORE.index('elseif event == "PLAYER_REGEN_ENABLED"') :]
    regen_body = regen_body[: regen_body.index('elseif event == "PLAYER_ENTERING_WORLD"')]
    assert "if not ApplyInstanceVisibilityPolicy() then" in regen_body

    group_body = CORE[CORE.index('if event == "GROUP_ROSTER_UPDATE"') :]
    group_body = group_body[: group_body.index('elseif event == "PLAYER_REGEN_DISABLED"')]
    assert "RefreshRuntimeFrames()" in group_body
    assert "GroupUpdate()" not in group_body
    assert "AddFrameFavorite()" not in group_body

    entering_body = CORE[CORE.index('elseif event == "PLAYER_ENTERING_WORLD"') :]
    entering_body = entering_body[: entering_body.index('elseif event == "PLAYER_SPECIALIZATION_CHANGED"')]
    party_timer_body = entering_body[entering_body.index('if instanceType == "party"') :]
    party_timer_body = party_timer_body[: party_timer_body.index('elseif instanceType == "none"')]
    assert "RefreshRuntimeFrames()" in party_timer_body
    assert "FrameAutoFill()" not in party_timer_body


def test_mythic_visibility_and_auto_fill_options_refresh_runtime_frames():
    assert "autoFrameFill = true" in CONFIG

    refresh_body = function_body(CORE, "RefreshRuntimeFrames")
    assert "ApplyInstanceVisibilityPolicy()" in refresh_body
    assert "GroupUpdate()" in refresh_body
    assert "AddFrameFavorite()" in refresh_body
    assert "if addon.db.profile.autoFrameFill then" in refresh_body
    assert "FrameAutoFill()" in refresh_body
    assert "SyncRuntimeFrameVisibility()" in refresh_body

    options_body = function_body(CORE, "GetOptions")
    auto_section = options_body[options_body.index("autoFrame = {") : options_body.index("raid = {")]
    assert "addon.db.profile.autoFrameFill = value" in auto_section
    assert "RegisterEvent" not in auto_section
    assert "UnregisterEvent" not in auto_section
    assert "RefreshRuntimeFrames()" in auto_section

    raid_section = options_body[options_body.index("raid = {") : options_body.index("mythic = {")]
    assert "addon.db.profile.showRaid = value" in raid_section
    assert "RefreshRuntimeFrames()" in raid_section

    mythic_section = options_body[options_body.index("mythic = {") : options_body.index("h5 = {")]
    assert "addon.db.profile.showMythic = value" in mythic_section
    assert "RefreshRuntimeFrames()" in mythic_section

    spec_body = CORE[CORE.index('elseif event == "PLAYER_SPECIALIZATION_CHANGED"') :]
    spec_body = spec_body[: spec_body.index('elseif event == "UNIT_AURA"')]
    assert "RefreshRuntimeFrames()" in spec_body
    assert "SyncRuntimeFrameVisibility()" in spec_body


def test_frame_visibility_option_uses_toggle_value():
    frame_hide_section = CORE[CORE.index("frameHide = {") : CORE.index("autoFrame = {")]
    assert 'name = "Show Frame"' in frame_hide_section
    assert "addon.db.profile.enabled = value" in frame_hide_section
    assert "if value then" in frame_hide_section
    assert "EnableAllFrame()" in frame_hide_section
    assert "else" in frame_hide_section
    assert "HideAllSubFrames()" in frame_hide_section


def test_ebon_progress_bar_visibility_follows_setting_on_show_paths():
    assert "SyncProgressBarVisibility" in CORE

    sync_body = function_body(CORE, "SyncProgressBarVisibility")
    assert "addon.db.profile.ebonmightProgressBarEnable" in sync_body
    assert "progressBar:Show()" in sync_body
    assert "progressBar:Hide()" in sync_body
    assert "progressBar.text:Show()" in sync_body
    assert "progressBar.text:Hide()" in sync_body

    create_body = function_body(CORE, "CreateProgressBar")
    assert "SyncProgressBarVisibility()" in create_body
    assert "progressBar:Show()" not in create_body
    assert "progressBar:Hide()" not in create_body

    hide_body = function_body(CORE, "HideAllSubFrames")
    assert "SyncProgressBarVisibility()" not in hide_body
    assert "progressBar:Hide()" in hide_body

    enable_body = function_body(CORE, "EnableAllFrame")
    assert "SyncProgressBarVisibility()" in enable_body
    assert "progressBar:Show()" not in enable_body


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


def test_first_party_state_does_not_leak_bare_globals():
    assert re.search(r"(?m)^spell_list\s*=", SPELL_LIST) is None
    assert re.search(r"(?m)^AllSpellList\s*=", SPELL_LIST) is None
    assert "addon.SpellList = {" in SPELL_LIST
    assert "addon.AllSpellList = {" in SPELL_LIST

    assert "addon.SpellList" in CORE
    assert "addon.AllSpellList" in CORE
    assert "MyProgressBar" not in CORE
    assert 'CreateFrame("StatusBar", nil, UIParent)' in CORE

    global_helpers = set(re.findall(r"(?m)^function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", CORE))
    assert global_helpers.isdisjoint(
        {
            "CheckShoworHide",
            "CreateProgressBar",
            "GetCharacterName",
            "GetHomePartyInfos",
            "RightMenu",
            "HideAllSubFrames",
            "EnableAllFrame",
            "IsFavorite",
            "MenuHandler",
            "AddItemsWithMenu",
        }
    )


def test_packager_excludes_repo_only_files():
    assert "ignore:" in PKGMETA
    assert "- tests" in PKGMETA
    assert "- scripts" in PKGMETA
    assert "- .github" in PKGMETA
    assert "- .pytest_cache" in PKGMETA
    assert "- backups" in PKGMETA
    assert "- AUDIT.md" in PKGMETA
    assert "- Libs/LibCustomGlow-1.0/.editorconfig" in PKGMETA
    assert "- Libs/LibCustomGlow-1.0/.luarc.json" in PKGMETA
    assert "- Libs/LibCustomGlow-1.0/.pkgmeta" in PKGMETA
    assert "- Libs/LibCustomGlow-1.0/cspell.json" in PKGMETA
    assert "- Libs/AceGUI-3.0-SharedMediaWidgets/Libs" in PKGMETA
    assert "dist/" in GITIGNORE
    assert "backups/" in GITIGNORE
    assert ".pytest_cache/" in GITIGNORE
    assert "AUDIT.md" not in GITIGNORE


def test_midnight_release_has_source_changelog():
    assert CHANGELOG.exists()
    changelog = CHANGELOG.read_text(encoding="utf-8")
    assert "## v1.0.24-midnight.1" in changelog
    assert "Midnight" in changelog


def test_public_copy_describes_midnight_buff_tracking():
    stale_copy = [
        "current number of evokers",
        "evokers in the zone",
        "list of all the evokers",
    ]
    for phrase in stale_copy:
        assert phrase not in TOC
        assert phrase not in README

    assert "Midnight" in README
    assert "Augmentation" in README
    assert "Prescience" in README
    assert "party" in README.lower()
    assert "Prescience" in TOC
    assert "Augmentation" in TOC


def test_public_copy_does_not_ship_internal_release_gate_language():
    changelog = CHANGELOG.read_text(encoding="utf-8")
    forbidden_phrases = [
        "before public release",
        "should still be verified",
        "needs in-game",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in README.lower()
        assert phrase not in changelog.lower()


def test_packager_uses_curated_changelog_for_release_notes():
    assert re.search(r"(?m)^manual-changelog:\s*$", PKGMETA)
    assert re.search(r"(?m)^  filename: CHANGELOG\.md\s*$", PKGMETA)
    assert re.search(r"(?m)^  markup-type: markdown\s*$", PKGMETA)
    assert "# manual-changelog" not in PKGMETA


def test_release_workflow_gates_packager_on_static_checks():
    assert re.search(r"(?m)^  preflight:\s*$", WORKFLOW)
    assert re.search(r"(?m)^  packager:\s*$", WORKFLOW)
    assert re.search(r"(?m)^    needs: preflight\s*$", WORKFLOW)
    assert 'python scripts/check-release-version.py --tag "$GITHUB_REF_NAME"' in WORKFLOW
    assert "python -m pip install pytest" in WORKFLOW
    assert "python -m pytest tests/test_midnight_port_static.py -q" in WORKFLOW
    assert "sudo apt-get install -y lua5.1" in WORKFLOW
    assert "luac5.1 -p Core/Config.lua Core/EvokerAug.lua Core/SpellList.lua" in WORKFLOW


def test_release_workflow_pins_packager_action():
    assert "BigWigsMods/packager@master" not in WORKFLOW
    assert re.search(r"uses:\s+BigWigsMods/packager@[0-9a-f]{40}", WORKFLOW)


def test_release_version_preflight_accepts_matching_metadata():
    result = subprocess.run(
        [
            sys.executable,
            str(RELEASE_VERSION_SCRIPT),
            "--root",
            str(ROOT),
            "--tag",
            "v1.0.24-midnight.1",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_release_version_preflight_rejects_mismatched_tag():
    result = subprocess.run(
        [
            sys.executable,
            str(RELEASE_VERSION_SCRIPT),
            "--root",
            str(ROOT),
            "--tag",
            "v9.9.9",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "EvokerAug.toc" in result.stderr
    assert "Core/Config.lua" in result.stderr
    assert "CHANGELOG.md" in result.stderr
    assert "scripts/package-local.ps1" in result.stderr


def test_local_package_script_documents_expected_zip_surface():
    assert PACKAGE_SCRIPT.exists()
    script = PACKAGE_SCRIPT.read_text(encoding="utf-8")
    assert "EvokerAug-v1.0.24-midnight.1.zip" in script
    assert "dist" in script
    for ignored in [
        ".git",
        ".github",
        "tests",
        "scripts",
        ".pytest_cache",
        "dist",
        "backups",
        ".gitignore",
        ".pkgmeta",
        "AGENTS.md",
        "AUDIT.md",
        "PLAN.md",
        "NOTES.md",
        "TODO.md",
        "CLAUDE.md",
    ]:
        assert ignored in script
    assert '$ignoredFilePatterns = @(' in script
    assert '"*.private.md"' in script
    assert '$ignoredDirectoryPatterns = @(' in script
    assert '"*.private"' in script
    assert "Test-AnyWildcardMatch -Value $item.Name -Patterns $ignoredFilePatterns" in script
    assert "Test-AnyWildcardMatch -Value $item.Name -Patterns $ignoredDirectoryPatterns" in script
    assert '$ignoredRelativeDirectories = @(' in script
    assert '"Libs\\AceGUI-3.0-SharedMediaWidgets\\Libs"' in script
    assert "$excludedPath = Resolve-ChildPath -BasePath $addonRoot -ChildPath $relativeDirectory" in script
    assert 'Assert-PathInsideRoot -Path $excludedPath -RootPath $addonRoot -Label "ignoredRelativeDirectory"' in script


def test_local_package_script_bounds_destructive_paths():
    script = PACKAGE_SCRIPT.read_text(encoding="utf-8")
    assert "function Resolve-ChildPath" in script
    assert "function Assert-PathInsideRoot" in script
    assert "$outputRoot = Resolve-ChildPath -BasePath $repoRoot -ChildPath $OutputDirectory" in script
    assert 'Assert-PathInsideRoot -Path $outputRoot -RootPath $repoRoot -Label "OutputDirectory"' in script
    assert 'Assert-PathInsideRoot -Path $stagingRoot -RootPath $outputRoot -Label "stagingRoot"' in script
    assert 'Assert-PathInsideRoot -Path $zipPath -RootPath $outputRoot -Label "zipPath"' in script


def test_removed_nested_vendor_metadata_stays_out_of_repo_and_packages():
    for path in [
        ROOT / "Libs" / "LibCustomGlow-1.0" / ".editorconfig",
        ROOT / "Libs" / "LibCustomGlow-1.0" / ".luarc.json",
        ROOT / "Libs" / "LibCustomGlow-1.0" / ".pkgmeta",
        ROOT / "Libs" / "LibCustomGlow-1.0" / "cspell.json",
    ]:
        assert not path.exists()


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


def test_local_install_script_bounds_move_and_junction_paths():
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "function Resolve-ChildPath" in script
    assert "function Assert-PathInsideRoot" in script
    assert "$backupRootPath = Resolve-ChildPath -BasePath $repoRoot -ChildPath $BackupRoot" in script
    assert 'Assert-PathInsideRoot -Path $backupRootPath -RootPath $repoRoot -Label "BackupRoot"' in script
    assert 'Assert-PathInsideRoot -Path $installedAddonPath -RootPath $addonsRoot -Label "installedAddonPath"' in script
    assert 'Assert-PathInsideRoot -Path $backupPath -RootPath $backupRootPath -Label "backupPath"' in script
