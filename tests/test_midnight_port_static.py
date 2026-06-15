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
        rf"(?:local\s+)?function\s+{re.escape(name)}\b|^{re.escape(name)}\s*=\s*function\b|^addon\.{re.escape(name)}\s*=\s*function\b",
        source,
        re.M,
    )
    assert match, f"{name} is missing"
    next_match = re.search(
        r"\n(?:(?:local\s+)?function\s+[\w:]+|(?:[A-Za-z_][A-Za-z0-9_]*\.)?[A-Za-z_][A-Za-z0-9_]*\s*=\s*function)",
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

    role_body = function_body(CORE, "GetUnitCombatRole")
    assert "UnitGroupRolesAssigned(unit)" in role_body
    assert "NormalizeCombatRole(combatRole)" in role_body
    assert "GetInspectSpecializationCombatRole(unit)" in role_body

    add_home_body = function_body(CORE, "AddHomePartyInfo")
    assert "GetUnitClassToken(unit)" in add_home_body
    assert "GetUnitCombatRole(unit)" in add_home_body
    assert 'class = strupper(string.gsub(class, "%s+", ""))' in add_home_body

    favorite_body = function_body(CORE, "AddFavoriteFrameForUnit")
    assert "GetUnitClassToken(unitID)" in favorite_body
    assert "GetUnitCombatRole(unitID)" in favorite_body

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
    assert "addon.UnitExistsClean(unit)" in helper_body
    assert "addon.UnitIsConnectedClean(unit)" in helper_body

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
    supported_classes = set(re.findall(r'class = "([A-Z]+)"', SPELL_LIST))
    assert supported_classes == {
        "DEATHKNIGHT",
        "DEMONHUNTER",
        "DRUID",
        "EVOKER",
        "HUNTER",
        "MAGE",
        "MONK",
        "PALADIN",
        "PRIEST",
        "ROGUE",
        "SHAMAN",
        "WARLOCK",
        "WARRIOR",
    }

    for spell_id, name in {
        51271: "Pillar of Frost",
        162264: "Metamorphosis",
        1217607: "Void Metamorphosis",
        194223: "Celestial Alignment",
        375087: "Dragonrage",
        19574: "Bestial Wrath",
        190319: "Combustion",
        365362: "Arcane Surge",
        1249625: "Zenith",
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


def test_midnight_dps_specs_have_curated_main_burst_defaults():
    expected_by_spec = {
        "Frost Death Knight": {51271, 1249658},
        "Unholy Death Knight": {63560, 207289},
        "Havoc Demon Hunter": {162264},
        "Devourer Demon Hunter": {1217607},
        "Balance Druid": {194223, 102560},
        "Feral Druid": {106951, 102543},
        "Devastation Evoker": {375087},
        "Augmentation Evoker": {403631},
        "Beast Mastery Hunter": {19574, 359844},
        "Marksmanship Hunter": {288613},
        "Survival Hunter": {1253860},
        "Arcane Mage": {365362},
        "Fire Mage": {190319},
        "Frost Mage": {208141},
        "Windwalker Monk": {1249625, 443028, 123904},
        "Retribution Paladin": {31884},
        "Shadow Priest": {10060, 228260, 391109},
        "Assassination Rogue": {360194, 385627},
        "Outlaw Rogue": {13750, 51690},
        "Subtlety Rogue": {185422, 212283, 121471},
        "Elemental Shaman": {1219480, 114051, 191634},
        "Enhancement Shaman": {384352, 444995, 1219480, 114051},
        "Affliction Warlock": {205180, 442726},
        "Demonology Warlock": {265273},
        "Destruction Warlock": {1122, 442726},
        "Arms Warrior": {107574, 227847},
        "Fury Warrior": {1719, 107574},
    }

    for spec_name, spell_ids in expected_by_spec.items():
        for spell_id in spell_ids:
            assert f"[{spell_id}] = " in SPELL_LIST, f"{spec_name} missing {spell_id}"

    death_knight_section = SPELL_LIST[
        SPELL_LIST.index('[51271] = { name = "Pillar of Frost"') :
        SPELL_LIST.index('[162264] = { name = "Metamorphosis"')
    ]
    for noisy_spell_id in {47568, 49206, 42650, 439843, 275699}:
        assert f"[{noisy_spell_id}] = " not in death_knight_section


def test_rogue_offensive_defaults_cover_cast_based_burst_windows():
    for spell_id, name in {
        360194: "Deathmark",
        385627: "Kingsbane",
        384631: "Flagellation",
        51690: "Killing Spree",
        280719: "Secret Technique",
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


def test_death_knight_offensive_defaults_cover_cast_based_burst_windows():
    for spell_id, name in {
        51271: "Pillar of Frost",
        1249658: "Breath of Sindragosa",
        63560: "Dark Transformation",
        207289: "Unholy Assault",
    }.items():
        assert f"[{spell_id}] = " in SPELL_LIST
        assert f'name = "{name}"' in SPELL_LIST

    death_knight_section = SPELL_LIST[
        SPELL_LIST.index('[51271] = { name = "Pillar of Frost"') :
        SPELL_LIST.index('[162264] = { name = "Metamorphosis"')
    ]
    assert 'class = "DEATHKNIGHT"' in death_knight_section
    assert 'name = "Dark Transformation", class = "DEATHKNIGHT", tier = "major", castWindow = 15' in death_knight_section
    assert 'name = "Unholy Assault", class = "DEATHKNIGHT", tier = "major", castWindow = 20' in death_knight_section


def test_offensive_cast_windows_use_spellcast_events_not_cooldown_apis():
    assert 'RegisterEvent("UNIT_SPELLCAST_SUCCEEDED")' in CORE
    assert "RecordOffensiveCastWindow(unit, spellID)" in CORE
    assert "GetOffensiveCastWindowStateForUnit(unit)" in function_body(CORE, "GetOffensiveStateForUnit")
    assert "C_Spell.GetSpellCooldown" not in CORE
    assert "C_Spell.GetSpellCharges" not in CORE
    assert "COMBAT_LOG_EVENT_UNFILTERED" not in CORE

    record_body = function_body(CORE, "RecordOffensiveCastWindow")
    assert "addon.UnitExistsClean(unit)" in record_body
    assert 'addon.UnitIsUnitClean(unit, "player")' in record_body
    assert "UnitExists(unit)" not in record_body
    assert "UnitIsUnit(unit" not in record_body
    assert "GetOffensiveBuffDefinitionForCastSpellID(spellID)" in record_body
    assert "addon.GetUnitStateKey(unit)" in record_body
    assert "addon.DEFAULT_OFFENSIVE_MAJOR_CAST_WINDOW" in record_body
    assert "addon.DEFAULT_OFFENSIVE_MINOR_CAST_WINDOW" in record_body
    assert "GetTime() + castWindow" in record_body
    assert "icon = addon.GetOffensiveBuffIcon(auraSpellID, definition)" in record_body
    assert "C_Timer.After(castWindow" in record_body
    assert "RefreshOffensiveHighlightSurfacesForUnit(unit)" in record_body

    window_body = function_body(CORE, "GetOffensiveCastWindowStateForUnit")
    assert "addon.UnitExistsClean(unit)" in window_body
    assert "UnitExists(unit)" not in window_body
    assert "window.icon" in window_body

    definition_body = function_body(CORE, "GetOffensiveBuffDefinitionForCastSpellID")
    assert "local auraSpellIDValue = GetCleanPositiveSpellID(auraSpellID)" in definition_body
    assert "castSpellID == spellID or auraSpellIDValue == spellID" in definition_body


def test_prescience_thin_tracker_predicts_player_casts_when_combat_hides_party_auras():
    assert 'RegisterUnitEvent("UNIT_SPELLCAST_SENT", "player")' in CORE
    assert "RecordPendingPrescienceCastTarget(unit, info, spellID, maybeSpellID)" in CORE
    assert "RecordPrescienceCastSucceeded(unit, info, spellID)" in CORE
    assert "pendingPrescienceCastTargetsByCastGUID" in CORE
    assert "addon.PRESCIENCE_PREDICTED_DURATION" in CORE

    sent_body = function_body(CORE, "RecordPendingPrescienceCastTarget")
    assert "GetCleanPositiveSpellID(spellID) ~= 409311" in sent_body
    assert "FindGroupUnitBySpellcastTarget(targetName)" in sent_body
    assert "addon.pendingPrescienceCastTargetsByCastGUID[castGUID] = targetUnit" in sent_body
    assert "tostring" not in sent_body

    success_body = function_body(CORE, "RecordPrescienceCastSucceeded")
    assert "GetCleanPositiveSpellID(spellID) ~= 409311" in success_body
    assert "addon.pendingPrescienceCastTargetsByCastGUID[castGUID]" in success_body
    assert "addon.RecordPredictedPrescienceThinTrackerAuraState(targetUnit)" in success_body
    assert "RefreshPrescienceThinTrackerAuras(targetUnit)" in success_body
    assert "C_Timer.After(addon.PRESCIENCE_PREDICTED_DURATION" in success_body

    predicted_body = function_body(CORE, "RecordPredictedPrescienceThinTrackerAuraState")
    assert "expirationTime = GetTime() + addon.PRESCIENCE_PREDICTED_DURATION" in predicted_body
    assert "duration = addon.PRESCIENCE_PREDICTED_DURATION" in predicted_body
    assert "aura.name" not in predicted_body


def test_unit_boolean_api_results_are_secret_safe():
    assert "addon.GetCleanBooleanValue" in CORE
    assert "addon.GetCleanBooleanResult" in CORE
    assert "addon.UnitExistsClean" in CORE
    assert "addon.UnitIsUnitClean" in CORE
    assert "addon.UnitInRangeClean" in CORE
    assert "addon.UnitIsDeadOrGhostClean" in CORE

    clean_body = function_body(CORE, "GetCleanBooleanValue")
    assert "pcall(issecretvalue, value)" in clean_body
    assert "pcall(function() return value == true end)" in clean_body
    assert "pcall(function() return value == false end)" in clean_body
    assert "if value then" not in clean_body
    assert "not value" not in clean_body

    result_body = function_body(CORE, "GetCleanBooleanResult")
    assert "pcall(fn, ...)" in result_body
    assert "addon.GetCleanBooleanValue(value)" in result_body


def test_unit_guid_table_keys_are_secret_safe():
    assert "GetCleanUnitGUID" in CORE

    guid_body = function_body(CORE, "GetCleanUnitGUID")
    assert "pcall(UnitGUID, unit)" in guid_body
    assert "not ok or not guid" not in guid_body
    assert "pcall(issecretvalue, guid)" in guid_body
    assert 'type(guid) ~= "string"' in guid_body

    role_inspect_body = function_body(CORE, "RequestInspectRoleForUnit")
    assert "GetCleanUnitGUID(unit)" in role_inspect_body
    assert not re.search(r"(?<!Clean)UnitGUID\(unit\)", role_inspect_body)


def test_combat_state_tables_use_cached_identity_when_unit_guid_is_secret():
    assert "unitStateKeysByUnit" in CORE

    cache_body = function_body(CORE, "CacheUnitStateKey")
    assert '"identity:" .. identityKey' in cache_body
    assert "addon.unitStateKeysByUnit[unit] = stateKey" in cache_body

    state_key_body = function_body(CORE, "GetUnitStateKey")
    assert "addon.unitStateKeysByUnit[unit]" in state_key_body
    assert '"guid:" .. guid' in state_key_body
    assert "addon.GetCleanUnitGUID(unit)" in state_key_body

    for name in [
        "RecordOffensiveCastWindow",
        "GetOffensiveCastWindowStateForUnit",
        "RecordOffensiveAuraState",
        "RemoveOffensiveAuraStateByInstanceID",
        "GetObservedOffensiveAuraStateForUnit",
        "RecordPrescienceThinTrackerAuraState",
        "RecordPredictedPrescienceThinTrackerAuraState",
        "RemovePrescienceThinTrackerAuraStateByInstanceID",
        "GetObservedPrescienceThinTrackerAuraForUnit",
    ]:
        body = function_body(CORE, name)
        assert "GetUnitStateKey(unit)" in body, name
        assert "GetCleanUnitGUID(unit)" not in body, name
        assert not re.search(r"(?<!Clean)UnitGUID\(unit\)", body), name

    for name in ["AddHomePartyInfo", "CreateSelectedPlayerFrame", "CreatePrescienceThinTrackerRow"]:
        assert "CacheUnitStateKey(" in function_body(CORE, name), name


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
    assert 'addon.UnitIsUnitClean(unit, "player")' in eligibility_body
    assert "local combatRole = addon.GetUnitCombatRole(unit)" in eligibility_body
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
    assert "RefreshOffensiveBuffHighlight(selectedPlayerFrame, unit)" in unit_aura_body
    assert "GetAuraDataBySpellName" not in unit_aura_body
    assert "string.find" not in unit_aura_body
    assert "string.match" not in unit_aura_body


def test_unit_aura_payload_records_offensive_state_for_party_combat():
    assert "offensiveAuraStatesByGUID" in CORE
    assert "RecordOffensiveAuraState(unit, v)" in CORE
    assert "RecordOffensiveAuraState(unit, aura)" in CORE
    assert "RemoveOffensiveAuraStateByInstanceID(unit, instance)" in CORE

    unit_aura_body = CORE[CORE.index('elseif event == "UNIT_AURA"') :]
    unit_aura_body = unit_aura_body[: unit_aura_body.index('elseif event == "UNIT_SPELLCAST_SUCCEEDED"')]
    assert "local selectedPlayerFrame = selectedPlayerFrames[frameIndex]" in unit_aura_body
    assert "if info.addedAuras and #info.addedAuras > 0 then" in unit_aura_body
    assert "if info.updatedAuraInstanceIDs and #info.updatedAuraInstanceIDs > 0 then" in unit_aura_body
    assert "if info.removedAuraInstanceIDs and #info.removedAuraInstanceIDs > 0 then" in unit_aura_body

    record_body = function_body(CORE, "RecordOffensiveAuraState")
    assert "IsUsableAuraData(aura)" in record_body
    assert "GetOffensiveBuffDefinition(spellID)" in record_body
    assert "IsOffensiveBuffEnabled(spellID)" in record_body
    assert "auraInstanceID = aura.auraInstanceID" in record_body
    assert "expires = aura.expirationTime" in record_body
    assert "icon = addon.GetOffensiveBuffIcon(spellID, definition, aura)" in record_body
    assert "aura.name" not in record_body
    assert "string." not in record_body

    state_body = function_body(CORE, "GetOffensiveStateForUnit")
    assert "GetObservedOffensiveAuraStateForUnit(unit)" in state_body
    assert "observedAuraIcon" in state_body


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


def test_prescience_thin_tracker_defaults_are_independent_from_legacy_frames():
    assert "prescienceThinTracker = {" in CONFIG
    assert "position = {" in CONFIG
    assert "rowWidth = 170" in CONFIG
    assert "rowHeight = 12" in CONFIG
    assert "rowSpacing = 3" in CONFIG
    assert "locked = false" in CONFIG

    normalize_body = function_body(CORE, "NormalizeProfileShape")
    assert 'EnsureProfileTable(profile, defaults, "prescienceThinTracker")' in normalize_body
    assert 'EnsureProfileTable(profile.prescienceThinTracker, defaults.prescienceThinTracker, "position")' in normalize_body
    assert 'ClampNumberSetting(profile.prescienceThinTracker, defaults.prescienceThinTracker, "rowWidth", 100, 260)' in normalize_body
    assert 'ClampNumberSetting(profile.prescienceThinTracker, defaults.prescienceThinTracker, "rowHeight", 8, 22)' in normalize_body
    assert 'ClampNumberSetting(profile.prescienceThinTracker, defaults.prescienceThinTracker, "rowSpacing", 0, 10)' in normalize_body


def test_prescience_thin_tracker_is_visual_only_and_movable_separately():
    assert "prescienceThinTrackerFrame" in CORE
    assert "prescienceThinTrackerRows" in CORE
    assert "CreatePrescienceThinTrackerFrame" in CORE

    create_body = function_body(CORE, "CreatePrescienceThinTrackerFrame")
    assert 'CreateFrame("Frame", "EvokerAugPrescienceThinTracker", UIParent, BackdropTemplateMixin and "BackdropTemplate")' in create_body
    assert "SecureActionButtonTemplate" not in create_body
    assert "SecureUnitButtonTemplate" not in create_body
    assert "prescienceThinTrackerFrame:SetMovable(true)" in create_body
    assert "LoadPositionFromTable(prescienceThinTrackerFrame, addon.db.profile.prescienceThinTracker.position)" in create_body
    assert "SavePositionToTable(prescienceThinTrackerFrame, addon.db.profile.prescienceThinTracker.position)" in create_body
    assert "addon.db.profile.prescienceThinTracker.locked" in create_body


def test_prescience_thin_tracker_tracks_dps_prescience_only():
    assert "RefreshPrescienceThinTrackerRoster" in CORE
    assert "RefreshPrescienceThinTrackerAuras" in CORE
    assert "UpdatePrescienceThinTrackerRows" in CORE

    roster_body = function_body(CORE, "RefreshPrescienceThinTrackerRoster")
    assert "GetHomePartyInfos()" in roster_body
    assert 'member.role == "DPS"' in roster_body
    assert 'addon.UnitIsUnitClean(member.unit, "player")' in roster_body
    assert "CreatePrescienceThinTrackerRow(member)" in roster_body

    aura_body = function_body(CORE, "RefreshPrescienceThinTrackerAuras")
    assert "FindAuraBySpellID(row.unit, 410089)" in aura_body
    assert "GetObservedPrescienceThinTrackerAuraForUnit(row.unit)" in aura_body
    assert "FindTrackedAuraBySpellID(row.unit, 410089)" not in aura_body
    assert "FindAuraBySpellID(row.unit, 395152)" not in aura_body
    assert "FindAuraBySpellID(row.unit, 395296)" not in aura_body
    assert "GetOffensiveStateForUnit" not in aura_body

    update_body = function_body(CORE, "UpdatePrescienceThinTrackerRows")
    assert "row.fill:SetWidth(width)" in update_body
    assert "remaining / duration" in update_body
    assert "row.fill:Hide()" in update_body


def test_prescience_thin_tracker_uses_unit_aura_payload_cache_for_party_combat():
    assert "prescienceThinTrackerAuraStatesByGUID" in CORE
    assert "RecordPrescienceThinTrackerAuraState(unit, v)" in CORE
    assert "RecordPrescienceThinTrackerAuraState(unit, aura)" in CORE
    assert "RemovePrescienceThinTrackerAuraStateByInstanceID(unit, instance)" in CORE

    record_body = function_body(CORE, "RecordPrescienceThinTrackerAuraState")
    assert "GetCleanPositiveSpellID(aura.spellId) ~= 410089" in record_body
    assert "IsUsableAuraData(aura)" in record_body
    assert "auraInstanceID = aura.auraInstanceID" in record_body
    assert "expirationTime = aura.expirationTime" in record_body
    assert "duration = aura.duration" in record_body
    assert "aura.name" not in record_body
    assert "string." not in record_body

    observed_body = function_body(CORE, "GetObservedPrescienceThinTrackerAuraForUnit")
    assert "state.expirationTime > GetTime()" in observed_body
    assert "prescienceThinTrackerAuraStatesByGUID[stateKey] = nil" in observed_body


def test_prescience_thin_tracker_rows_show_range_state():
    assert "PRESCIENCE_THIN_TRACKER_RANGE_COLORS" in CORE
    assert "PRESCIENCE_THIN_TRACKER_RANGE_MARKER_WIDTH = 4" in CORE
    assert "ApplyPrescienceThinTrackerRangeState" in CORE

    create_body = function_body(CORE, "CreatePrescienceThinTrackerRow")
    assert "local rangeMarker = frame:CreateTexture(nil, \"OVERLAY\")" in create_body
    assert "rangeMarker:SetWidth(PRESCIENCE_THIN_TRACKER_RANGE_MARKER_WIDTH)" in create_body
    assert "row.rangeMarker = rangeMarker" in create_body

    range_body = function_body(CORE, "ApplyPrescienceThinTrackerRangeState")
    assert "prescienceThinTrackerTestMode and row.isTestRow" in range_body
    assert "addon.UnitExistsClean(row.unit)" in range_body
    assert "addon.UnitInRangeClean(row.unit)" in range_body
    assert "UnitExists(row.unit)" not in range_body
    assert "UnitInRange(row.unit)" not in range_body
    assert "issecretvalue(inRange)" not in range_body
    assert "inRange == true" in range_body
    assert "inRange == false" in range_body
    assert "if inRange then" not in range_body
    assert 'rangeState = "outOfRange"' in range_body
    assert 'rangeState = "inRange"' in range_body
    assert "row.rangeMarker:SetColorTexture" in range_body
    assert "row.frame:SetAlpha" in range_body

    update_body = function_body(CORE, "UpdatePrescienceThinTrackerRows")
    assert "ApplyPrescienceThinTrackerRangeState(row)" in update_body


def test_prescience_thin_tracker_reuses_offensive_burst_state_for_glow():
    assert "OFFENSIVE_THIN_TRACKER_MAJOR_GLOW_KEY" in CORE
    assert "ApplyPrescienceThinTrackerOffensiveState" in CORE
    assert "RefreshPrescienceThinTrackerOffensiveStateForUnit" in CORE

    create_body = function_body(CORE, "CreatePrescienceThinTrackerRow")
    assert "local offensiveMinorMarker = frame:CreateTexture(nil, \"OVERLAY\")" in create_body
    assert "row.offensiveMinorMarker = offensiveMinorMarker" in create_body
    assert "local offensiveIconFrame = CreateFrame(\"Frame\", nil, frame" in create_body
    assert "local offensiveIcon = offensiveIconFrame:CreateTexture(nil, \"ARTWORK\")" in create_body
    assert "row.offensiveIconFrame = offensiveIconFrame" in create_body
    assert "row.offensiveIcon = offensiveIcon" in create_body

    apply_body = function_body(CORE, "ApplyPrescienceThinTrackerOffensiveState")
    assert "icon = icon or nil" in apply_body
    assert "row.offensiveIcon:SetTexture(icon)" in apply_body
    assert "row.offensiveIconFrame:Show()" in apply_body
    assert "row.offensiveIconFrame:Hide()" in apply_body
    assert "LibCustomGlow.PixelGlow_Start(row.frame, OFFENSIVE_MAJOR_GLOW_COLOR" in apply_body
    assert "LibCustomGlow.PixelGlow_Start(row.offensiveIconFrame, OFFENSIVE_MAJOR_GLOW_COLOR" in apply_body
    assert "OFFENSIVE_THIN_TRACKER_MAJOR_GLOW_KEY" in apply_body
    assert "LibCustomGlow.PixelGlow_Stop(row.frame, OFFENSIVE_THIN_TRACKER_MAJOR_GLOW_KEY)" in apply_body
    assert 'LibCustomGlow.PixelGlow_Stop(row.offensiveIconFrame, OFFENSIVE_THIN_TRACKER_MAJOR_GLOW_KEY .. "Icon")' in apply_body
    assert "row.offensiveMinorMarker:Show()" in apply_body
    assert "row.offensiveMinorMarker:Hide()" in apply_body
    assert "row.offensiveState = state" in apply_body
    assert "row.offensiveIconTexture = icon" in apply_body

    refresh_body = function_body(CORE, "RefreshPrescienceThinTrackerOffensiveStateForUnit")
    assert "prescienceThinTrackerTestMode and row.isTestRow" in refresh_body
    assert "row.testOffensiveState" in refresh_body
    assert "row.testOffensiveIcon" in refresh_body
    assert "local state, icon = OFFENSIVE_STATE_NONE, nil" in refresh_body
    assert "state, icon = GetOffensiveStateForUnit(row.unit)" in refresh_body
    assert "ApplyPrescienceThinTrackerOffensiveState(row, state, icon)" in refresh_body

    state_body = function_body(CORE, "GetOffensiveStateForUnit")
    assert "majorIcon" in state_body
    assert "minorIcon" in state_body
    assert "addon.GetOffensiveBuffIcon(spellID" in state_body
    assert "return OFFENSIVE_STATE_MAJOR, majorIcon" in state_body
    assert "return OFFENSIVE_STATE_MINOR, minorIcon" in state_body

    surfaces_body = function_body(CORE, "RefreshOffensiveHighlightSurfacesForUnit")
    assert "RefreshPrescienceThinTrackerOffensiveStateForUnit(unit)" in surfaces_body

    enabled_body = function_body(CORE, "SetOffensiveBuffEnabled")
    assert "RefreshPrescienceThinTrackerOffensiveStateForUnit()" in enabled_body

    options_body = function_body(CORE, "GetOptions")
    assert "RefreshPrescienceThinTrackerOffensiveStateForUnit()" in options_body

    aura_body = function_body(CORE, "RefreshPrescienceThinTrackerAuras")
    assert "RefreshPrescienceThinTrackerOffensiveStateForUnit(unit)" in aura_body

    update_body = function_body(CORE, "UpdatePrescienceThinTrackerRows")
    assert "GetOffensiveStateForUnit" not in update_body


def test_prescience_thin_tracker_wires_into_existing_events_without_replacing_old_frames():
    on_enable_body = function_body(CORE, "addon:OnEnable")
    assert "CreatePrescienceThinTrackerFrame()" in on_enable_body
    assert "RefreshPrescienceThinTrackerRoster()" in on_enable_body
    assert "RefreshPrescienceThinTrackerAuras(unit)" in on_enable_body
    assert "UpdatePrescienceThinTrackerVisibility()" in on_enable_body

    group_body = CORE[CORE.index('if event == "GROUP_ROSTER_UPDATE"') :]
    group_body = group_body[: group_body.index('elseif event == "PLAYER_REGEN_DISABLED"')]
    assert "RefreshRuntimeFrames()" in group_body
    assert "RefreshPrescienceThinTrackerRoster()" in group_body

    aura_event_body = CORE[CORE.index('elseif event == "UNIT_AURA"') :]
    aura_event_body = aura_event_body[: aura_event_body.index('elseif event == "UNIT_SPELLCAST_SUCCEEDED"')]
    assert "RefreshPrescienceThinTrackerAuras(unit)" in aura_event_body
    assert "RefreshOffensiveBuffHighlight(selectedPlayerFrame, unit)" in aura_event_body


def test_prescience_thin_tracker_retries_party_roster_without_autofill_gate():
    assert "SchedulePrescienceThinTrackerRosterRefresh" in CORE

    scheduler_body = function_body(CORE, "SchedulePrescienceThinTrackerRosterRefresh")
    assert 'if expectedInstanceType == "raid" then' in scheduler_body
    assert "IsCurrentInstanceContext(generation, expectedInstanceType)" in scheduler_body
    assert "RefreshPrescienceThinTrackerRoster()" in scheduler_body
    assert "UpdatePrescienceThinTrackerVisibility()" in scheduler_body
    assert "C_Timer.After(0.5, retry)" in scheduler_body
    assert "C_Timer.After(1.0, retry)" in scheduler_body
    assert "addon.db.profile.autoFrameFill" not in scheduler_body

    entering_body = CORE[CORE.index('elseif event == "PLAYER_ENTERING_WORLD"') :]
    entering_body = entering_body[: entering_body.index('elseif event == "PLAYER_SPECIALIZATION_CHANGED"')]
    assert "local _, instanceType = IsInInstance()" in entering_body
    schedule_call = "SchedulePrescienceThinTrackerRosterRefresh(generation, instanceType)"
    assert schedule_call in entering_body
    assert entering_body.index(schedule_call) < entering_body.index("if addon.db.profile.autoFrameFill then")

    group_body = CORE[CORE.index('if event == "GROUP_ROSTER_UPDATE"') :]
    group_body = group_body[: group_body.index('elseif event == "UNIT_CONNECTION"')]
    assert "SchedulePrescienceThinTrackerRosterRefresh(instanceContextGeneration, instanceType)" in group_body


def test_unknown_party_roles_fall_back_to_inspect_specialization():
    assert "addon.pendingRoleInspectGUIDs = addon.pendingRoleInspectGUIDs or {}" in CORE
    assert "addon.roleInspectQueue = addon.roleInspectQueue or {}" in CORE
    assert "addon.roleInspectActiveGUID" in CORE
    assert "NormalizeCombatRole" in CORE
    assert "GetInspectSpecializationCombatRole" in CORE
    assert "DrainRoleInspectQueue" in CORE
    assert "RequestInspectRoleForUnit" in CORE
    assert "GetUnitCombatRole" in CORE

    normalize_body = function_body(CORE, "NormalizeCombatRole")
    assert 'combatRole == "DAMAGER"' in normalize_body
    assert 'return "DPS"' in normalize_body
    assert 'combatRole == "DPS" or combatRole == "TANK" or combatRole == "HEALER"' in normalize_body
    assert "return nil" in normalize_body

    inspect_body = function_body(CORE, "GetInspectSpecializationCombatRole")
    assert 'addon.UnitIsUnitClean(unit, "player")' in inspect_body
    assert "GetSpecialization()" in inspect_body
    assert "GetSpecializationInfo(specializationIndex)" in inspect_body
    assert "GetInspectSpecialization(unit)" in inspect_body
    assert "GetSpecializationInfoByID(specID)" in inspect_body
    assert "NormalizeCombatRole(role)" in inspect_body

    drain_body = function_body(CORE, "DrainRoleInspectQueue")
    assert "addon.roleInspectActiveGUID" in drain_body
    assert "table.remove(addon.roleInspectQueue, 1)" in drain_body
    assert "NotifyInspect(unit)" in drain_body
    assert "C_Timer.After(6.0" in drain_body
    assert "ClearInspectPlayer()" in drain_body
    assert "addon.DrainRoleInspectQueue()" in drain_body

    request_body = function_body(CORE, "RequestInspectRoleForUnit")
    assert 'addon.UnitIsUnitClean(unit, "player")' in request_body
    assert "InCombatLockdown()" in request_body
    assert "addon.CanInspectClean(unit)" in request_body
    assert "NotifyInspect(unit)" not in request_body
    assert "addon.pendingRoleInspectGUIDs[guid] = unit" in request_body
    assert "table.insert(addon.roleInspectQueue, guid)" in request_body
    assert "addon.DrainRoleInspectQueue()" in request_body

    role_body = function_body(CORE, "GetUnitCombatRole")
    assert "local combatRole = UnitGroupRolesAssigned(unit)" in role_body
    assert "combatRole = addon.NormalizeCombatRole(combatRole)" in role_body
    assert "local inspectRole = addon.GetInspectSpecializationCombatRole(unit)" in role_body
    assert "addon.RequestInspectRoleForUnit(unit)" in role_body
    assert "return inspectRole" in role_body

    add_home_body = function_body(CORE, "AddHomePartyInfo")
    assert "local combatRole = addon.GetUnitCombatRole(unit)" in add_home_body

    compact_body = function_body(CORE, "IsUnitEligibleForBlizzardCompactHighlight")
    assert "addon.GetUnitCombatRole(unit)" in compact_body
    assert "UnitGroupRolesAssigned(unit)" not in compact_body


def test_inspect_ready_refreshes_thin_tracker_after_role_resolution():
    on_enable_body = function_body(CORE, "addon:OnEnable")
    assert 'selectedPlayerFrameContainer:RegisterEvent("INSPECT_READY")' in on_enable_body

    inspect_ready_body = CORE[CORE.index('elseif event == "INSPECT_READY"') :]
    inspect_ready_body = inspect_ready_body[: inspect_ready_body.index('elseif event == "PLAYER_REGEN_DISABLED"')]
    assert "local guid = unit" in inspect_ready_body
    assert "addon.pendingRoleInspectGUIDs[guid]" in inspect_ready_body
    assert "addon.pendingRoleInspectGUIDs[guid] = nil" in inspect_ready_body
    assert "addon.roleInspectActiveGUID == guid" in inspect_ready_body
    assert "ClearInspectPlayer()" in inspect_ready_body
    assert "RefreshRuntimeFrames()" in inspect_ready_body
    assert "RefreshPrescienceThinTrackerRoster()" in inspect_ready_body
    assert "UpdatePrescienceThinTrackerVisibility()" in inspect_ready_body
    assert "addon.DrainRoleInspectQueue()" in inspect_ready_body


def test_prescience_thin_tracker_test_mode_is_runtime_only():
    assert "prescienceThinTrackerTestMode" in CORE
    assert "PRESCIENCE_THIN_TRACKER_TEST_MEMBERS" in CORE
    assert "prescienceThinTrackerTestMode" not in CONFIG

    assert "SetPrescienceThinTrackerTestMode" in CORE
    mode_body = function_body(CORE, "SetPrescienceThinTrackerTestMode")
    assert "prescienceThinTrackerTestMode = enabled == true" in mode_body
    assert "addon.db.profile.prescienceThinTracker.test" not in mode_body
    assert "RefreshPrescienceThinTrackerRoster()" in mode_body
    assert "UpdatePrescienceThinTrackerVisibility()" in mode_body


def test_prescience_thin_tracker_test_mode_builds_preview_rows_without_aura_reads():
    assert "RefreshPrescienceThinTrackerTestRows" in CORE

    assert CORE.count('identityKey = "test-thin-tracker-') == 2
    assert 'name = "Test Mage"' in CORE
    assert 'name = "Test Rogue"' in CORE
    assert 'testRangeState = "inRange"' in CORE
    assert 'testRangeState = "outOfRange"' in CORE
    assert 'testOffensiveState = OFFENSIVE_STATE_MAJOR' in CORE
    assert 'testOffensiveState = OFFENSIVE_STATE_MINOR' in CORE
    assert "testOffensiveIcon =" in CORE
    assert 'name = "Test Hunter"' not in CORE

    test_body = function_body(CORE, "RefreshPrescienceThinTrackerTestRows")
    assert "ClearPrescienceThinTrackerRows()" in test_body
    assert "PRESCIENCE_THIN_TRACKER_TEST_MEMBERS" in test_body
    assert "CreatePrescienceThinTrackerRow(member)" in test_body
    assert "GetTime()" in test_body
    assert "row.isTestRow = true" in test_body
    assert "row.testRangeState = member.testRangeState" in test_body
    assert "row.testOffensiveState = member.testOffensiveState" in test_body
    assert "row.testOffensiveIcon = member.testOffensiveIcon" in test_body
    assert "row.duration = PRESCIENCE_THIN_TRACKER_TEST_DURATION" in test_body
    assert "row.expirationTime = now + remaining" in test_body
    assert "FindTrackedAuraBySpellID" not in test_body

    roster_body = function_body(CORE, "RefreshPrescienceThinTrackerRoster")
    assert "if prescienceThinTrackerTestMode then" in roster_body
    assert "RefreshPrescienceThinTrackerTestRows()" in roster_body
    assert "row.testOffensiveIcon = nil" in roster_body

    aura_body = function_body(CORE, "RefreshPrescienceThinTrackerAuras")
    assert "if prescienceThinTrackerTestMode then" in aura_body
    assert "UpdatePrescienceThinTrackerRows()" in aura_body
    assert "RefreshPrescienceThinTrackerTestRows()\n        return" not in aura_body


def test_prescience_thin_tracker_test_mode_cycles_and_empty_live_anchor_stays_hidden():
    update_body = function_body(CORE, "UpdatePrescienceThinTrackerRows")
    assert "prescienceThinTrackerTestMode and row.isTestRow" in update_body
    assert "row.expirationTime = now + duration" in update_body
    assert "settings.rowWidth * (remaining / duration)" in update_body

    visibility_body = function_body(CORE, "UpdatePrescienceThinTrackerVisibility")
    assert "if prescienceThinTrackerTestMode then" in visibility_body
    assert "prescienceThinTrackerFrame:Show()" in visibility_body
    assert "IsPrescienceThinTrackerRuntimeAllowed() and hasRows" in visibility_body
    assert "(hasRows or not settings.locked)" not in visibility_body


def test_prescience_thin_tracker_test_mode_turns_off_when_real_combat_starts():
    regen_disabled_body = CORE[CORE.index('elseif event == "PLAYER_REGEN_DISABLED"') :]
    regen_disabled_body = regen_disabled_body[: regen_disabled_body.index('elseif event == "PLAYER_LOGOUT"')]
    assert "combatLockdown = true" in regen_disabled_body
    assert "SetPrescienceThinTrackerTestMode(false)" in regen_disabled_body


def test_prescience_thin_tracker_options_include_test_mode_button():
    options_body = function_body(CORE, "GetOptions")
    assert "prescienceThinTrackerTestMode" in options_body
    assert 'name = "Test Thin Tracker"' in options_body
    assert 'desc = "Show simulated DPS Prescience bars so you can position and tune the tracker."' in options_body
    assert "SetPrescienceThinTrackerTestMode(value)" in options_body
    assert "addon.db.profile.prescienceThinTracker.test" not in options_body


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
    assert "addon.UnitExistsClean(unit)" in distance_body
    assert "addon.UnitInRangeClean(unit)" in distance_body
    assert "UnitExists(unit)" not in distance_body
    assert "UnitInRange(unit)" not in distance_body
    assert "issecretvalue(inRange)" not in distance_body
    assert "inRange == true" in distance_body
    assert "inRange == false" in distance_body
    assert "if inRange then" not in distance_body
    assert "ApplyPlayerFrameVisualAlpha(playerFrame" in distance_body

    unit_flags_body = CORE[CORE.index('elseif event == "UNIT_FLAGS"') :]
    unit_flags_body = unit_flags_body[: unit_flags_body.index("end\n    end)")]
    assert "addon.UnitIsDeadOrGhostClean(unit)" in unit_flags_body
    assert "UnitIsDeadOrGhost(unit)" not in unit_flags_body

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
