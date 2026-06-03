local addonName = ...
---@class EvokerAug: AceConsole-3.0
local addon = LibStub("AceAddon-3.0"):GetAddon(addonName)
---@cast addon +AceConsole-3.0
local AceConfigDialog = LibStub("AceConfigDialog-3.0")
local AceConfigRegistry = LibStub("AceConfigRegistry-3.0")
local icon = LibStub("LibDBIcon-1.0")
local EvokerAugOptions = {}
local checkboxStates = {}
local selectedPlayerFrames = {}
local selectedPlayerFrameContainer
local distanceTimer
local progressBar
local addonNameText
local combatLockdown = false
local isCombatButton = false
local discordLinkDialog = "EvokerAUG_General_Settings_Discord_Dialog"
local LibCustomGlow = LibStub("LibCustomGlow-1.0")
local DeadorGhostData = {}
local issecretvalue = _G.issecretvalue or function() return false end
local EBON_MIGHT_SPELL_IDS = { 395296, 395152 }
local PRESCIENCE_ICON_ID = 5199639
addon.SENSE_POWER_CAST_SPELL_ID = 361021
addon.SENSE_POWER_AURA_SPELL_ID = 361022
local PLAYER_FRAME_WIDTH = 150
local OFFENSIVE_TIER_MAJOR = "major"
local OFFENSIVE_TIER_MINOR = "minor"
local OFFENSIVE_TIER_LABELS = { major = "Major", minor = "Minor" }
local OFFENSIVE_STATE_NONE = "none"
local OFFENSIVE_STATE_MINOR = "minor"
local OFFENSIVE_STATE_MAJOR = "major"
local OFFENSIVE_STATE_BOTH = "both"
local OFFENSIVE_MAJOR_GLOW_KEY = "EvokerAugOffensiveMajor"
local OFFENSIVE_THIN_TRACKER_MAJOR_GLOW_KEY = "EvokerAugThinTrackerOffensiveMajor"
local OFFENSIVE_MAJOR_GLOW_COLOR = { 1, 0.76, 0.18, 1 }
local OFFENSIVE_MINOR_MARKER_COLOR = { 0.2, 0.95, 1, 0.9 }
local BLIZZARD_COMPACT_MAJOR_GLOW_KEY = "EvokerAugBlizzardCompactMajor"
local BLIZZARD_COMPACT_MINOR_MARKER_WIDTH = 4
local PRESCIENCE_THIN_TRACKER_RANGE_MARKER_WIDTH = 4
local PRESCIENCE_THIN_TRACKER_RANGE_COLORS = {
    inRange = { 0.18, 1, 0.32, 0.95 },
    outOfRange = { 1, 0.16, 0.12, 0.95 },
    unknown = { 0.72, 0.72, 0.72, 0.82 },
}
local pendingProtectedFrameRefresh = false
local pendingActiveProfileApply = false
local blizzardCompactFrameRefreshPending = false
local instanceContextGeneration = 0
local blizzardCompactFrameOverlays = {}
local offensiveCastWindowsByGUID = {}
addon.pendingRoleInspectGUIDs = addon.pendingRoleInspectGUIDs or {}
addon.roleInspectQueue = addon.roleInspectQueue or {}
addon.roleInspectActiveGUID = nil
local prescienceThinTrackerFrame
local prescienceThinTrackerRows = {}
local prescienceThinTrackerRowOrder = {}
local prescienceThinTrackerUpdateElapsed = 0
local prescienceThinTrackerTestMode = false
local PRESCIENCE_THIN_TRACKER_TEST_DURATION = 18
local PRESCIENCE_THIN_TRACKER_TEST_MEMBERS = {
    { identityKey = "test-thin-tracker-mage", name = "Test Mage", class = "MAGE", unit = "player", remaining = 17, testRangeState = "inRange", testOffensiveState = OFFENSIVE_STATE_MAJOR },
    { identityKey = "test-thin-tracker-rogue", name = "Test Rogue", class = "ROGUE", unit = "player", remaining = 10, testRangeState = "outOfRange", testOffensiveState = OFFENSIVE_STATE_MINOR },
}
local CheckShoworHide
local HideAllSubFrames
local EnableAllFrame
local ReconcileTrackedAurasForAllSelectedUnits
local RefreshRuntimeFrames
local RefreshBlizzardCompactFrameHighlightsForAllUnits
local RefreshBlizzardCompactFrameHighlightsForUnit
local GetUnitClassToken
local GetHomePartyInfos
local RightMenu
local IsFavorite
local AddItemsWithMenu
local EnsureOffensiveBuffStateTables
local RefreshOffensiveBuffHighlight
local RefreshOffensiveBuffHighlightsForAllSelectedUnits
local CreatePrescienceThinTrackerFrame
local RefreshPrescienceThinTrackerRoster
local RefreshPrescienceThinTrackerAuras
local UpdatePrescienceThinTrackerRows
local UpdatePrescienceThinTrackerVisibility
local RefreshPrescienceThinTrackerOffensiveStateForUnit
local VALID_FRAME_POINTS = {
    TOPLEFT = true,
    TOP = true,
    TOPRIGHT = true,
    LEFT = true,
    CENTER = true,
    RIGHT = true,
    BOTTOMLEFT = true,
    BOTTOM = true,
    BOTTOMRIGHT = true,
}

local function IsCleanNumber(value)
    return type(value) == "number" and not issecretvalue(value)
end

local function IsCleanPositiveNumber(value)
    return IsCleanNumber(value) and value > 0
end

local function GetCleanPositiveSpellID(value)
    if issecretvalue(value) then
        return nil
    end

    local valueType = type(value)
    if valueType ~= "number" and valueType ~= "string" then
        return nil
    end

    local spellID = tonumber(value)
    if spellID and spellID > 0 then
        return spellID
    end
    return nil
end

local function IsCleanAuraIcon(value)
    if issecretvalue(value) then
        return false
    end

    local valueType = type(value)
    return valueType == "number" or valueType == "string"
end

local function IsUsableAuraData(aura)
    return aura
        and GetCleanPositiveSpellID(aura.spellId) ~= nil
        and IsCleanPositiveNumber(aura.auraInstanceID)
        and IsCleanPositiveNumber(aura.expirationTime)
        and IsCleanPositiveNumber(aura.duration)
        and IsCleanAuraIcon(aura.icon)
end

local function CanMutateProtectedFrames()
    return not combatLockdown and not (InCombatLockdown and InCombatLockdown())
end

local function MarkProtectedFrameRefreshPending()
    pendingProtectedFrameRefresh = true
    isCombatButton = true
    if addonNameText then
        addonNameText:SetText(addonName .. " (Waiting for combat to end)")
    end
end

local function IsCurrentInstanceContext(generation, expectedInstanceType)
    if generation ~= instanceContextGeneration then
        return false
    end

    local _, instanceType = IsInInstance()
    return instanceType == expectedInstanceType
end

local function ShouldShowForInstanceType(instanceType)
    if instanceType == "raid" and not addon.db.profile.showRaid then
        return false
    end
    if instanceType == "party" and not addon.db.profile.showMythic then
        return false
    end
    return true
end

local function IsRuntimeContextAllowed()
    if GetUnitClassToken("player") ~= "EVOKER" then
        return false
    end

    local currentSpec = GetSpecialization()
    if currentSpec and currentSpec ~= 3 then
        return false
    end

    local _, instanceType = IsInInstance()
    return ShouldShowForInstanceType(instanceType)
end

local function IsRuntimeVisibilityAllowed()
    if GetUnitClassToken("player") ~= "EVOKER" then
        return false
    end

    if addon.db and addon.db.profile and addon.db.profile.enabled == false then
        return false
    end

    local currentSpec = GetSpecialization()
    if currentSpec and currentSpec ~= 3 then
        return false
    end

    local _, instanceType = IsInInstance()
    return ShouldShowForInstanceType(instanceType)
end

GetUnitClassToken = function(unit)
    local _, classToken = UnitClass(unit)
    return classToken
end

local function FindAuraBySpellID(unit, spellID)
    spellID = GetCleanPositiveSpellID(spellID)
    if not unit or not spellID or not UnitExists(unit) then
        return nil
    end

    if C_UnitAuras and C_UnitAuras.GetUnitAuraBySpellID then
        local aura = C_UnitAuras.GetUnitAuraBySpellID(unit, spellID)
        if IsUsableAuraData(aura) and GetCleanPositiveSpellID(aura.spellId) == spellID then
            return aura
        end
    end

    if AuraUtil and AuraUtil.ForEachAura then
        local foundAura
        AuraUtil.ForEachAura(unit, "HELPFUL", nil, function(aura)
            if IsUsableAuraData(aura) and GetCleanPositiveSpellID(aura.spellId) == spellID then
                foundAura = aura
                return true
            end
            return false
        end, true)
        return foundAura
    end

    return nil
end

local function HasHelpfulAuraBySpellID(unit, spellID)
    spellID = GetCleanPositiveSpellID(spellID)
    if not unit or not spellID or not UnitExists(unit) then
        return false
    end

    if C_UnitAuras and C_UnitAuras.GetUnitAuraBySpellID then
        local aura = C_UnitAuras.GetUnitAuraBySpellID(unit, spellID)
        if aura and GetCleanPositiveSpellID(aura.spellId) == spellID then
            return true
        end
    end

    if AuraUtil and AuraUtil.ForEachAura then
        local found = false
        AuraUtil.ForEachAura(unit, "HELPFUL", nil, function(aura)
            if aura and GetCleanPositiveSpellID(aura.spellId) == spellID then
                found = true
                return true
            end
            return false
        end, true)
        return found
    end

    return false
end

local function EnsureTrackedBuffStateTables()
    if not addon.db or not addon.db.profile then
        return
    end

    addon.db.profile.buffList = addon.db.profile.buffList or {}
    addon.db.profile.disabledBuffList = addon.db.profile.disabledBuffList or {}
    addon.db.profile.customBuffList = addon.db.profile.customBuffList or {}
end

local function IsCoreBuffOption(spellID)
    spellID = tonumber(spellID)
    if not spellID then
        return false
    end

    local defaultBuffs = addon.DefaultProfile and addon.DefaultProfile.profile and addon.DefaultProfile.profile.buffList
    if defaultBuffs and defaultBuffs[spellID] ~= nil then
        return true
    end

    return addon.AllSpellList and addon.AllSpellList["Augmentation"] and addon.AllSpellList["Augmentation"][spellID] ~= nil
end

local function IsTrackedBuffEnabled(spellID)
    spellID = GetCleanPositiveSpellID(spellID)
    if not spellID or not addon.db or not addon.db.profile then
        return false
    end

    local disabledBuffList = addon.db.profile.disabledBuffList or {}
    if disabledBuffList[spellID] then
        return false
    end

    local buffList = addon.db.profile.buffList or {}
    return buffList[spellID] ~= nil
end

local function SetTrackedBuff(spellID, spellName, enabled, isCustom)
    spellID = GetCleanPositiveSpellID(spellID)
    if not spellID or not spellName then
        return
    end

    EnsureTrackedBuffStateTables()
    local isCore = IsCoreBuffOption(spellID)

    if enabled then
        addon.db.profile.disabledBuffList[spellID] = nil
        addon.db.profile.buffList[spellID] = spellName
        if isCustom and not isCore then
            addon.db.profile.customBuffList[spellID] = spellName
        end
    else
        addon.db.profile.buffList[spellID] = nil
        if isCore then
            addon.db.profile.disabledBuffList[spellID] = true
        else
            addon.db.profile.disabledBuffList[spellID] = nil
            addon.db.profile.customBuffList[spellID] = nil
        end
    end

    if ReconcileTrackedAurasForAllSelectedUnits then
        ReconcileTrackedAurasForAllSelectedUnits()
    end
end

local function SeedCustomBuffListFromBuffList()
    EnsureTrackedBuffStateTables()
    if not addon.db or not addon.db.profile then
        return
    end

    for spellID, spellName in pairs(addon.db.profile.buffList) do
        local numericSpellID = tonumber(spellID)
        if numericSpellID and not IsCoreBuffOption(numericSpellID) and type(spellName) == "string" then
            addon.db.profile.customBuffList[numericSpellID] = spellName
        end
    end
end

local function IsTrackedAuraData(aura)
    local spellID = aura and GetCleanPositiveSpellID(aura.spellId)
    return spellID and IsUsableAuraData(aura) and IsTrackedBuffEnabled(spellID)
end

local function FindTrackedAuraBySpellID(unit, spellID)
    local aura = FindAuraBySpellID(unit, spellID)
    if IsTrackedAuraData(aura) then
        return aura
    end
    return nil
end

local function FindFirstAuraBySpellIDs(unit, spellIDs)
    for _, spellID in ipairs(spellIDs) do
        local aura = FindAuraBySpellID(unit, spellID)
        if aura then
            return aura
        end
    end
    return nil
end

local function NormalizeOffensiveTier(tier)
    if tier == OFFENSIVE_TIER_MAJOR or tier == OFFENSIVE_TIER_MINOR then
        return tier
    end
    return nil
end

local function GetOffensiveBuffDefinition(spellID)
    spellID = GetCleanPositiveSpellID(spellID)
    if not spellID or not addon.db or not addon.db.profile then
        return nil
    end

    EnsureOffensiveBuffStateTables()
    local offensiveBuffs = addon.db.profile.offensiveBuffs
    local custom = offensiveBuffs.custom or {}
    local defaults = addon.OffensiveBuffList or {}
    local definition = custom[spellID] or defaults[spellID]
    if type(definition) ~= "table" then
        return nil
    end

    local tiers = offensiveBuffs.tiers or {}
    local tier = NormalizeOffensiveTier(tiers[spellID]) or NormalizeOffensiveTier(definition.tier) or
        OFFENSIVE_TIER_MINOR
    return definition, tier
end

local function IsOffensiveBuffEnabled(spellID)
    spellID = GetCleanPositiveSpellID(spellID)
    if not spellID or not addon.db or not addon.db.profile then
        return false
    end

    EnsureOffensiveBuffStateTables()
    local offensiveBuffs = addon.db.profile.offensiveBuffs
    if offensiveBuffs.enabled == false or offensiveBuffs.disabled[spellID] then
        return false
    end

    return GetOffensiveBuffDefinition(spellID) ~= nil
end

local function SetOffensiveBuffEnabled(spellID, enabled, isCustom)
    spellID = GetCleanPositiveSpellID(spellID)
    if not spellID or not addon.db or not addon.db.profile then
        return
    end

    EnsureOffensiveBuffStateTables()
    local offensiveBuffs = addon.db.profile.offensiveBuffs
    if enabled then
        offensiveBuffs.disabled[spellID] = nil
        if isCustom and not offensiveBuffs.custom[spellID] then
            offensiveBuffs.custom[spellID] = {
                name = "Custom Offensive Buff",
                tier = OFFENSIVE_TIER_MINOR,
            }
        end
    elseif isCustom then
        offensiveBuffs.custom[spellID] = nil
        offensiveBuffs.tiers[spellID] = nil
        offensiveBuffs.disabled[spellID] = nil
    else
        offensiveBuffs.disabled[spellID] = true
    end

    if RefreshOffensiveBuffHighlightsForAllSelectedUnits then
        RefreshOffensiveBuffHighlightsForAllSelectedUnits()
    end
    if RefreshBlizzardCompactFrameHighlightsForAllUnits then
        RefreshBlizzardCompactFrameHighlightsForAllUnits()
    end
    if RefreshPrescienceThinTrackerOffensiveStateForUnit then
        RefreshPrescienceThinTrackerOffensiveStateForUnit()
    end
end

local function SetOffensiveBuffTier(spellID, tier)
    spellID = GetCleanPositiveSpellID(spellID)
    tier = NormalizeOffensiveTier(tier)
    if not spellID or not tier or not addon.db or not addon.db.profile then
        return
    end

    EnsureOffensiveBuffStateTables()
    addon.db.profile.offensiveBuffs.tiers[spellID] = tier
    if addon.db.profile.offensiveBuffs.custom[spellID] then
        addon.db.profile.offensiveBuffs.custom[spellID].tier = tier
    end

    if RefreshOffensiveBuffHighlightsForAllSelectedUnits then
        RefreshOffensiveBuffHighlightsForAllSelectedUnits()
    end
    if RefreshBlizzardCompactFrameHighlightsForAllUnits then
        RefreshBlizzardCompactFrameHighlightsForAllUnits()
    end
    if RefreshPrescienceThinTrackerOffensiveStateForUnit then
        RefreshPrescienceThinTrackerOffensiveStateForUnit()
    end
end

local function SetCustomOffensiveBuff(spellID, spellName, tier)
    spellID = GetCleanPositiveSpellID(spellID)
    tier = NormalizeOffensiveTier(tier) or OFFENSIVE_TIER_MINOR
    if not spellID or not spellName or not addon.db or not addon.db.profile then
        return
    end

    EnsureOffensiveBuffStateTables()
    addon.db.profile.offensiveBuffs.custom[spellID] = {
        name = spellName,
        tier = tier,
    }
    addon.db.profile.offensiveBuffs.disabled[spellID] = nil
    addon.db.profile.offensiveBuffs.tiers[spellID] = tier

    if RefreshOffensiveBuffHighlightsForAllSelectedUnits then
        RefreshOffensiveBuffHighlightsForAllSelectedUnits()
    end
    if RefreshBlizzardCompactFrameHighlightsForAllUnits then
        RefreshBlizzardCompactFrameHighlightsForAllUnits()
    end
    if RefreshPrescienceThinTrackerOffensiveStateForUnit then
        RefreshPrescienceThinTrackerOffensiveStateForUnit()
    end
end
-- Map Icon ---

---@diagnostic disable-next-line: missing-fields
local miniButton = LibStub("LibDataBroker-1.1"):NewDataObject(addonName,
    {
        type = "launcher",
        text = addonName,
        icon = "Interface\\AddOns\\EvokerAug\\Media\\augevoker-logo",
        OnClick = function(self, btn)
            if btn == "LeftButton" then
                if CanMutateProtectedFrames() then
                    addon:OpenOptions()
                end
            elseif btn == "RightButton" then
                if CanMutateProtectedFrames() then
                    CheckShoworHide()
                end
            end
        end,
        OnTooltipShow = function(tooltip)
            if not tooltip or not tooltip.AddLine then return end
            tooltip:AddLine(addonName)
            tooltip:AddLine(" ")
            tooltip:AddLine("|cffeda55fLeft Click|r to open settings.", 0.2, 1, 0.2)
            tooltip:AddLine("|cffeda55fRight Click|r to show/hide frame.", 0.2, 1, 0.2)
        end,
    })

if AddonCompartmentFrame and AddonCompartmentFrame.RegisterAddon then
    AddonCompartmentFrame:RegisterAddon({
        text = addonName,
        icon = "Interface\\AddOns\\EvokerAug\\Media\\augevoker-logo",
        notCheckable = true,
        func = function()
            if CanMutateProtectedFrames() then
                addon:OpenOptions()
            end
        end,
    })
end

local function GetFavoriteList()
    if addon.db and addon.db.profile and addon.db.profile.favoriPlayer then
        return addon.db.profile.favoriPlayer
    end

    return {}
end

local function GetOrderedFavoriteList()
    local favList = GetFavoriteList()
    local keys = {}
    local names = {}
    local seen = {}

    for key, value in pairs(favList) do
        if type(key) == "number" and type(value) == "string" and value ~= "" then
            table.insert(keys, key)
        end
    end

    table.sort(keys)

    for _, key in ipairs(keys) do
        local name = favList[key]
        if not seen[name] then
            table.insert(names, name)
            seen[name] = true
        end
    end

    return names
end

local function NormalizeFavoriteList()
    local favList = GetFavoriteList()
    local names = GetOrderedFavoriteList()

    for key in pairs(favList) do
        favList[key] = nil
    end

    for index, name in ipairs(names) do
        favList[index] = name
    end

    return favList
end

local function IsFavoriteName(name)
    if not name then
        return false
    end

    for _, favoriteName in ipairs(GetOrderedFavoriteList()) do
        if favoriteName == name then
            return true
        end
    end

    return false
end

local function AddFavoriteName(name)
    if type(name) ~= "string" or name == "" then
        return
    end

    local favList = NormalizeFavoriteList()
    if not IsFavoriteName(name) then
        table.insert(favList, name)
    end
end

local function RemoveFavoriteName(name)
    if not name then
        return
    end

    local favList = NormalizeFavoriteList()
    for index = #favList, 1, -1 do
        if favList[index] == name then
            table.remove(favList, index)
        end
    end
end

local function GetFavoriteRank(identityKey)
    if not identityKey then
        return nil
    end

    for index, favoriteName in ipairs(GetOrderedFavoriteList()) do
        if favoriteName == identityKey then
            return index
        end
    end

    return nil
end

local function CompareFavoriteRank(a, b)
    local aRank = GetFavoriteRank(a.identityKey)
    local bRank = GetFavoriteRank(b.identityKey)
    if aRank and bRank then
        return aRank < bRank
    end
    if aRank then
        return true
    end
    if bRank then
        return false
    end
    return nil
end

local function sortFramesByName(a, b)
    local favoriteOrder = CompareFavoriteRank(a, b)
    if favoriteOrder ~= nil then
        return favoriteOrder
    end
    if a.playerName == b.playerName then
        return (a.identityKey or a.playerName) < (b.identityKey or b.playerName)
    end
    return a.playerName < b.playerName
end

local function sortFramesByClass(a, b)
    local favoriteOrder = CompareFavoriteRank(a, b)
    if favoriteOrder ~= nil then
        return favoriteOrder
    end
    if a.class == b.class then
        return sortFramesByName(a, b)
    end
    return a.class < b.class
end

local function sortFramesByRole(a, b)
    local favoriteOrder = CompareFavoriteRank(a, b)
    if favoriteOrder ~= nil then
        return favoriteOrder
    end
    if a.role == b.role then
        return sortFramesByName(a, b)
    end
    return a.role < b.role
end

local isFound
local changelog = (addon.Config["changelog"]:gsub("^[ \t\n]*", "|cff99cdff"):gsub("\n\nv([%d%.]+)", function(ver)
    if not isFound and ver ~= addon.Config["version"] then
        isFound = true
        return "|cff808080\n\nv" .. ver
    end
end):gsub("\t", "\32\32\32\32\32\32\32\32") or "|cff808080\n\nv") .. "|r"

local sortTypes = {
    ["NAME"] = sortFramesByName,
    ["CLASS"] = sortFramesByClass,
    ["ROLE"] = sortFramesByRole,
}

local function CopyDefaultValue(value)
    if type(value) ~= "table" then
        return value
    end

    local copy = {}
    for k, v in pairs(value) do
        copy[k] = CopyDefaultValue(v)
    end
    return copy
end

local function EnsureProfileTable(profile, defaults, key)
    if type(profile[key]) ~= "table" then
        profile[key] = CopyDefaultValue(defaults[key] or {})
    end
    return profile[key]
end

local function EnsureDefaultTableFields(profileTable, defaultTable)
    if type(profileTable) ~= "table" or type(defaultTable) ~= "table" then
        return
    end

    for key, defaultValue in pairs(defaultTable) do
        if type(defaultValue) == "table" then
            if type(profileTable[key]) ~= "table" then
                profileTable[key] = CopyDefaultValue(defaultValue)
            else
                EnsureDefaultTableFields(profileTable[key], defaultValue)
            end
        elseif profileTable[key] == nil or type(profileTable[key]) ~= type(defaultValue) then
            profileTable[key] = defaultValue
        end
    end
end

local function ClampNumberSetting(profile, defaults, key, minValue, maxValue)
    local value = profile[key]
    if type(value) ~= "number" or value ~= value then
        value = defaults[key]
    end
    if type(value) ~= "number" then
        value = minValue
    end

    if value < minValue then
        value = minValue
    elseif value > maxValue then
        value = maxValue
    end
    profile[key] = value
end

EnsureOffensiveBuffStateTables = function()
    if not addon.db or not addon.db.profile then
        return
    end

    local profile = addon.db.profile
    local defaults = addon.DefaultProfile and addon.DefaultProfile.profile
    if type(defaults) ~= "table" then
        return
    end

    EnsureProfileTable(profile, defaults, "offensiveBuffs")
    EnsureProfileTable(profile.offensiveBuffs, defaults.offensiveBuffs, "disabled")
    EnsureProfileTable(profile.offensiveBuffs, defaults.offensiveBuffs, "custom")
    EnsureProfileTable(profile.offensiveBuffs, defaults.offensiveBuffs, "tiers")
end

local function EnsureBlizzardFrameHighlightState()
    if not addon.db or not addon.db.profile then
        return
    end

    local profile = addon.db.profile
    local defaults = addon.DefaultProfile and addon.DefaultProfile.profile
    if type(defaults) ~= "table" then
        return
    end

    EnsureProfileTable(profile, defaults, "blizzardFrameHighlights")
    EnsureDefaultTableFields(profile.blizzardFrameHighlights, defaults.blizzardFrameHighlights)

    if type(profile.blizzardFrameHighlights.enabled) ~= "boolean" then
        profile.blizzardFrameHighlights.enabled = defaults.blizzardFrameHighlights.enabled
    end
    if type(profile.blizzardFrameHighlights.showRaid) ~= "boolean" then
        profile.blizzardFrameHighlights.showRaid = defaults.blizzardFrameHighlights.showRaid
    end
end

local function NormalizeOffensiveBuffState()
    EnsureOffensiveBuffStateTables()
    if not addon.db or not addon.db.profile then
        return
    end

    local defaults = addon.DefaultProfile and addon.DefaultProfile.profile
    local offensiveBuffs = addon.db.profile.offensiveBuffs
    if type(defaults) ~= "table" or type(offensiveBuffs) ~= "table" then
        return
    end

    if type(offensiveBuffs.enabled) ~= "boolean" then
        offensiveBuffs.enabled = defaults.offensiveBuffs.enabled
    end
    for spellID in pairs(offensiveBuffs.disabled) do
        if not GetCleanPositiveSpellID(spellID) then
            offensiveBuffs.disabled[spellID] = nil
        end
    end

    for spellID, tier in pairs(offensiveBuffs.tiers) do
        if not GetCleanPositiveSpellID(spellID) or not NormalizeOffensiveTier(tier) then
            offensiveBuffs.tiers[spellID] = nil
        end
    end

    for spellID, definition in pairs(offensiveBuffs.custom) do
        local cleanSpellID = GetCleanPositiveSpellID(spellID)
        if not cleanSpellID or type(definition) ~= "table" then
            offensiveBuffs.custom[spellID] = nil
        else
            definition.name = type(definition.name) == "string" and definition.name ~= "" and definition.name or
                "Custom Offensive Buff"
            definition.tier = NormalizeOffensiveTier(definition.tier) or OFFENSIVE_TIER_MINOR
            if cleanSpellID ~= spellID then
                offensiveBuffs.custom[cleanSpellID] = definition
                offensiveBuffs.custom[spellID] = nil
            end
        end
    end
end

local function NormalizeSensePowerSpellIDs(profile)
    if type(profile) ~= "table" then
        return
    end

    if type(profile.charSpell) == "table" and profile.charSpell[addon.SENSE_POWER_AURA_SPELL_ID] == "Sense Power" then
        if not profile.charSpell[addon.SENSE_POWER_CAST_SPELL_ID] then
            profile.charSpell[addon.SENSE_POWER_CAST_SPELL_ID] = profile.charSpell[addon.SENSE_POWER_AURA_SPELL_ID]
        end
        profile.charSpell[addon.SENSE_POWER_AURA_SPELL_ID] = nil
    end

    local macroKeys = { "LeftSpell", "RightSpell", "ShiftSpell", "CtrlSpell", "AltSpell" }
    local macroTables = { profile.tankMacros, profile.dpsMacros }
    for _, macroTable in ipairs(macroTables) do
        if type(macroTable) == "table" then
            for _, key in ipairs(macroKeys) do
                if macroTable[key] == addon.SENSE_POWER_AURA_SPELL_ID then
                    macroTable[key] = addon.SENSE_POWER_CAST_SPELL_ID
                end
            end
        end
    end
end

local function NormalizeProfileShape()
    if not addon.db or not addon.db.profile then
        return
    end

    local profile = addon.db.profile
    local defaults = addon.DefaultProfile and addon.DefaultProfile.profile
    if type(defaults) ~= "table" then
        return
    end

    EnsureProfileTable(profile, defaults, "buffList")
    EnsureProfileTable(profile, defaults, "disabledBuffList")
    EnsureProfileTable(profile, defaults, "customBuffList")
    EnsureProfileTable(profile, defaults, "favoriPlayer")
    EnsureProfileTable(profile, defaults, "macro")
    EnsureProfileTable(profile, defaults, "tankMacros")
    EnsureProfileTable(profile, defaults, "dpsMacros")
    EnsureProfileTable(profile, defaults, "charSpell")
    EnsureProfileTable(profile, defaults, "minimap")
    EnsureProfileTable(profile, defaults, "positions")
    EnsureProfileTable(profile, defaults, "offensiveBuffs")
    EnsureProfileTable(profile, defaults, "blizzardFrameHighlights")
    EnsureProfileTable(profile, defaults, "prescienceThinTracker")
    EnsureProfileTable(profile.prescienceThinTracker, defaults.prescienceThinTracker, "position")

    EnsureDefaultTableFields(profile.macro, defaults.macro)
    EnsureDefaultTableFields(profile.tankMacros, defaults.tankMacros)
    EnsureDefaultTableFields(profile.dpsMacros, defaults.dpsMacros)
    EnsureDefaultTableFields(profile.minimap, defaults.minimap)
    EnsureDefaultTableFields(profile.prescienceThinTracker, defaults.prescienceThinTracker)
    EnsureBlizzardFrameHighlightState()
    NormalizeSensePowerSpellIDs(profile)
    NormalizeOffensiveBuffState()

    ClampNumberSetting(profile, defaults, "buttonHeight", 20, 40)
    ClampNumberSetting(profile, defaults, "spellIconSize", 20, 40)
    ClampNumberSetting(profile, defaults, "spellIconTextSize", 12, 20)
    ClampNumberSetting(profile.prescienceThinTracker, defaults.prescienceThinTracker, "rowWidth", 100, 260)
    ClampNumberSetting(profile.prescienceThinTracker, defaults.prescienceThinTracker, "rowHeight", 8, 22)
    ClampNumberSetting(profile.prescienceThinTracker, defaults.prescienceThinTracker, "rowSpacing", 0, 10)

    if type(profile.prescienceThinTracker.enabled) ~= "boolean" then
        profile.prescienceThinTracker.enabled = defaults.prescienceThinTracker.enabled
    end
    if type(profile.prescienceThinTracker.locked) ~= "boolean" then
        profile.prescienceThinTracker.locked = defaults.prescienceThinTracker.locked
    end

    if not sortTypes[profile.sortType] then
        profile.sortType = defaults.sortType
    end
end

-- Minimap Icon

CheckShoworHide = function()
    if selectedPlayerFrameContainer and selectedPlayerFrameContainer:IsShown() then
        addon.db.profile.enabled = false
        HideAllSubFrames()
    else
        addon.db.profile.enabled = true
        RefreshRuntimeFrames()
        EnableAllFrame()
    end
end

local function createMiniMapIcon()
    ---@diagnostic disable-next-line: param-type-mismatch
    icon:Register(addonName, miniButton, addon.db.profile.minimap)
end

-- Ebon Might Proggres Bar

local function SyncProgressBarVisibility()
    if not progressBar then
        return
    end

    local shouldShow = addon.db.profile.ebonmightProgressBarEnable
        and selectedPlayerFrameContainer
        and selectedPlayerFrameContainer:IsShown()

    if shouldShow then
        progressBar:Show()
        if progressBar.text then
            progressBar.text:Show()
        end
    else
        progressBar:Hide()
        if progressBar.text then
            progressBar.text:Hide()
        end
    end
end

local function CreateProgressBar()
    if not CanMutateProtectedFrames() then
        MarkProtectedFrameRefreshPending()
        return
    end

    if addon.db.profile.ebonmightProgressBarEnable then
        if not progressBar then
            progressBar = CreateFrame("StatusBar", nil, UIParent)
            progressBar:SetSize(200, 20)
            progressBar:SetPoint("CENTER", selectedPlayerFrameContainer, "CENTER", 0, 20)
            progressBar:SetMinMaxValues(0, 100)
            progressBar:SetValue(0)
            progressBar:SetStatusBarTexture("Interface\\TARGETINGFRAME\\UI-StatusBar")
            progressBar:SetStatusBarColor(0, 1, 0)

            progressBar.text = progressBar:CreateFontString(nil, "OVERLAY", "GameFontNormal")
            progressBar.text:SetPoint("CENTER", progressBar, "CENTER")
            progressBar.text:SetText("Ebon Might")
        end


        selectedPlayerFrameContainer:SetScript("OnUpdate", function()
            local aura = FindFirstAuraBySpellIDs("player", EBON_MIGHT_SPELL_IDS)
            if not aura or not IsCleanPositiveNumber(aura.expirationTime) or not IsCleanPositiveNumber(aura.duration) then
                progressBar:SetValue(0)
                return
            end

            local remainingTime = aura.expirationTime - GetTime()
            if remainingTime <= 0 then
                progressBar:SetValue(0)
                return
            end

            progressBar:SetValue((remainingTime / aura.duration) * 100)
        end)
    elseif not addon.db.profile.ebonmightProgressBarEnable then
        selectedPlayerFrameContainer:SetScript("OnUpdate", nil)
    end

    SyncProgressBarVisibility()
end

---- Player Buffs Icon -----
local function GetCharacterName(fullName)
    if fullName then
        local characterName = string.match(fullName, "([^%-]+)")
        return characterName
    else
        return nil
    end
end

local function BuildIdentityKey(name, realm)
    if not name or name == "" then
        return nil, nil
    end

    if string.find(name, "-") then
        return name, GetCharacterName(name)
    end

    if not realm or realm == "" then
        realm = GetRealmName()
    end

    if realm and realm ~= "" then
        return name .. "-" .. realm, name
    end

    return name, name
end

local function GetUnitIdentity(unit)
    local name, realm = UnitName(unit)
    return BuildIdentityKey(name, realm)
end

local function IsEligibleGroupUnit(unit)
    if not unit or not UnitExists(unit) then
        return false
    end

    return UnitIsConnected(unit)
end

addon.NormalizeCombatRole = function(combatRole)
    if combatRole == "DAMAGER" then
        return "DPS"
    end
    if combatRole == "DPS" or combatRole == "TANK" or combatRole == "HEALER" then
        return combatRole
    end
    return nil
end

addon.GetInspectSpecializationCombatRole = function(unit)
    if not unit or not UnitExists(unit) then
        return nil
    end

    if UnitIsUnit and UnitIsUnit(unit, "player") then
        if not GetSpecialization or not GetSpecializationInfo then
            return nil
        end
        local specializationIndex = GetSpecialization()
        if not specializationIndex then
            return nil
        end
        local _, _, _, _, role = GetSpecializationInfo(specializationIndex)
        return addon.NormalizeCombatRole(role)
    end

    if not GetInspectSpecialization or not GetSpecializationInfoByID then
        return nil
    end

    local specID = GetInspectSpecialization(unit)
    if not IsCleanPositiveNumber(specID) then
        return nil
    end

    local _, _, _, _, role = GetSpecializationInfoByID(specID)
    return addon.NormalizeCombatRole(role)
end

addon.DrainRoleInspectQueue = function()
    if addon.roleInspectActiveGUID then
        return
    end

    if combatLockdown or (InCombatLockdown and InCombatLockdown()) then
        return
    end
    if not NotifyInspect then
        return
    end

    while #addon.roleInspectQueue > 0 do
        local guid = table.remove(addon.roleInspectQueue, 1)
        local unit = addon.pendingRoleInspectGUIDs[guid]
        if UnitTokenFromGUID then
            unit = UnitTokenFromGUID(guid) or unit
        end

        if unit and UnitExists(unit) and UnitIsConnected(unit) and (not CanInspect or CanInspect(unit, false)) then
            addon.pendingRoleInspectGUIDs[guid] = unit
            addon.roleInspectActiveGUID = guid
            NotifyInspect(unit)
            if C_Timer and C_Timer.After then
                C_Timer.After(6.0, function()
                    if addon.roleInspectActiveGUID == guid then
                        addon.roleInspectActiveGUID = nil
                        addon.pendingRoleInspectGUIDs[guid] = nil
                        if ClearInspectPlayer then
                            ClearInspectPlayer()
                        end
                        addon.DrainRoleInspectQueue()
                    end
                end)
            end
            return
        end

        addon.pendingRoleInspectGUIDs[guid] = nil
    end
end

addon.RequestInspectRoleForUnit = function(unit)
    if not unit or not UnitExists(unit) then
        return
    end
    if UnitIsUnit and UnitIsUnit(unit, "player") then
        return
    end
    if IsInRaid() then
        return
    end
    if combatLockdown or (InCombatLockdown and InCombatLockdown()) then
        return
    end
    if not NotifyInspect then
        return
    end
    if CanInspect and not CanInspect(unit, false) then
        return
    end

    -- WHY: manually formed M+ parties can report role NONE until inspect spec data is cached.
    local guid = UnitGUID and UnitGUID(unit)
    if not guid or addon.pendingRoleInspectGUIDs[guid] then
        return
    end

    addon.pendingRoleInspectGUIDs[guid] = unit
    table.insert(addon.roleInspectQueue, guid)
    addon.DrainRoleInspectQueue()
end

addon.GetUnitCombatRole = function(unit)
    if not unit or not UnitExists(unit) then
        return nil
    end

    local combatRole = UnitGroupRolesAssigned(unit)
    combatRole = addon.NormalizeCombatRole(combatRole)
    if combatRole then
        return combatRole
    end

    local inspectRole = addon.GetInspectSpecializationCombatRole(unit)
    if inspectRole then
        return inspectRole
    end

    addon.RequestInspectRoleForUnit(unit)
    return inspectRole
end

local function SanitizePosition(position)
    position = type(position) == "table" and position or {}
    local point = position.point
    if not VALID_FRAME_POINTS[position.point] then
        point = "CENTER"
    end

    local xOffset = type(position.xOffset) == "number" and position.xOffset or 0
    local yOffset = type(position.yOffset) == "number" and position.yOffset or 0
    return point, xOffset, yOffset
end

local function CanSetUserPlaced(frame)
    return frame
        and ((frame.IsMovable and frame:IsMovable()) or (frame.IsResizable and frame:IsResizable()))
end

local function LoadPosition(frame)
    addon.db.profile.positions = addon.db.profile.positions or {}
    local point, xOffset, yOffset = SanitizePosition(addon.db.profile.positions)
    addon.db.profile.positions.point = point
    addon.db.profile.positions.xOffset = xOffset
    addon.db.profile.positions.yOffset = yOffset

    frame:ClearAllPoints()
    frame:SetPoint(point, UIParent, point, xOffset, yOffset)
    if frame.SetUserPlaced and CanSetUserPlaced(frame) then
        frame:SetUserPlaced(true)
    end
end

local function LoadPositionFromTable(frame, position)
    if not frame or type(position) ~= "table" then
        return
    end

    local point, xOffset, yOffset = SanitizePosition(position)
    position.point = point
    position.xOffset = xOffset
    position.yOffset = yOffset
    frame:ClearAllPoints()
    frame:SetPoint(point, UIParent, point, xOffset, yOffset)
    if frame.SetUserPlaced and CanSetUserPlaced(frame) then
        frame:SetUserPlaced(true)
    end
end

local function SavePosition(frame)
    if not frame or not addon.db or not addon.db.profile then
        return
    end

    local point, _, _, xOffset, yOffset = frame:GetPoint()
    if not point then
        return
    end

    addon.db.profile.positions = addon.db.profile.positions or {}
    local savedPoint, savedXOffset, savedYOffset = SanitizePosition({
        point = point,
        xOffset = xOffset,
        yOffset = yOffset,
    })
    addon.db.profile.positions.point = savedPoint
    addon.db.profile.positions.xOffset = savedXOffset
    addon.db.profile.positions.yOffset = savedYOffset
end

local function SavePositionToTable(frame, position)
    if not frame or type(position) ~= "table" then
        return
    end

    local point, _, _, xOffset, yOffset = frame:GetPoint()
    if not point then
        return
    end

    local savedPoint, savedXOffset, savedYOffset = SanitizePosition({
        point = point,
        xOffset = xOffset,
        yOffset = yOffset,
    })
    position.point = savedPoint
    position.xOffset = savedXOffset
    position.yOffset = savedYOffset
end

local function GetClassRGB(class)
    local classColor = class and RAID_CLASS_COLORS and RAID_CLASS_COLORS[class]
    if classColor then
        if classColor.GetRGB then
            return classColor:GetRGB()
        end
        if classColor.r and classColor.g and classColor.b then
            return classColor.r, classColor.g, classColor.b
        end
    end

    if type(GetClassColor) == "function" and class then
        local r, g, b = GetClassColor(class)
        if r and g and b then
            return r, g, b
        end
    end

    return 0.24, 0.24, 0.24
end

local function RepositionBuffIcons(playerFrame)
    playerFrame["buff"].xOffset = 0
    for k, icon in pairs(playerFrame["buff"]) do
        if type(icon) == "table" and not string.match(k, "Text$") then
            icon:SetPoint("LEFT", playerFrame, "RIGHT", playerFrame["buff"].xOffset, 0)
            playerFrame["buff"].xOffset = playerFrame["buff"].xOffset + addon.db.profile.spellIconSize
        end
    end
end

local function ApplyPrescienceBarFill(playerFrame, expirationTime, startDuration)
    if not playerFrame or not playerFrame.texture then
        return
    end

    local width = addon.db.profile.prescienceBarEnable and 1 or PLAYER_FRAME_WIDTH
    if addon.db.profile.prescienceBarEnable and IsCleanPositiveNumber(expirationTime) and IsCleanPositiveNumber(startDuration) then
        local remaining = expirationTime - GetTime()
        if remaining > 0 then
            width = PLAYER_FRAME_WIDTH * (remaining / startDuration)
            width = math.max(1, math.min(PLAYER_FRAME_WIDTH, width))
        end
    end

    playerFrame.texture:SetSize(width, addon.db.profile.buttonHeight)
end

local function RefreshPrescienceBarFill(playerFrame)
    local buff = playerFrame and playerFrame["buff"]
    if not buff then
        ApplyPrescienceBarFill(playerFrame, nil, nil)
        return
    end

    for auraInstanceID, iconFrame in pairs(buff) do
        if type(iconFrame) == "table" and iconFrame.iconid == PRESCIENCE_ICON_ID then
            local text = buff[auraInstanceID .. "Text"]
            if text then
                ApplyPrescienceBarFill(playerFrame, text.timestamp, text.starttimestamp)
                return
            end
        end
    end

    ApplyPrescienceBarFill(playerFrame, nil, nil)
end

local function ApplyPlayerFrameVisualAlpha(playerFrame, alpha)
    if not playerFrame then
        return
    end

    playerFrame.visualAlpha = alpha

    if playerFrame.texture then
        playerFrame.texture:SetAlpha(alpha)
    end
    if playerFrame.playerNameText then
        playerFrame.playerNameText:SetAlpha(alpha)
    end
    if playerFrame.offensiveMinorMarker then
        playerFrame.offensiveMinorMarker:SetAlpha(alpha)
    end

    local buff = playerFrame["buff"]
    if buff then
        for key, region in pairs(buff) do
            if type(region) == "table" and region.SetAlpha then
                if key ~= "xOffset" or string.match(tostring(key), "Text$") then
                    region:SetAlpha(alpha)
                end
            end
        end
    end
end

local function CreateOffensiveMinorMarker(playerFrame)
    if not playerFrame or playerFrame.offensiveMinorMarker then
        return
    end

    local marker = playerFrame:CreateTexture(nil, "OVERLAY")
    marker:SetColorTexture(OFFENSIVE_MINOR_MARKER_COLOR[1], OFFENSIVE_MINOR_MARKER_COLOR[2],
        OFFENSIVE_MINOR_MARKER_COLOR[3], OFFENSIVE_MINOR_MARKER_COLOR[4])
    marker:SetPoint("TOPLEFT", playerFrame, "TOPLEFT", -3, 0)
    marker:SetPoint("BOTTOMLEFT", playerFrame, "BOTTOMLEFT", -3, 0)
    marker:SetWidth(4)
    marker:Hide()
    playerFrame.offensiveMinorMarker = marker
end

local function ApplyOffensiveBuffVisualState(playerFrame, state)
    if not playerFrame then
        return
    end

    if state ~= OFFENSIVE_STATE_MINOR and state ~= OFFENSIVE_STATE_MAJOR and state ~= OFFENSIVE_STATE_BOTH then
        state = OFFENSIVE_STATE_NONE
    end

    local hasMajor = state == OFFENSIVE_STATE_MAJOR or state == OFFENSIVE_STATE_BOTH
    local hasMinor = state == OFFENSIVE_STATE_MINOR or state == OFFENSIVE_STATE_BOTH

    if hasMajor then
        LibCustomGlow.PixelGlow_Start(playerFrame, OFFENSIVE_MAJOR_GLOW_COLOR, 8, 0.35, 10, 3, 0, 0, true,
            OFFENSIVE_MAJOR_GLOW_KEY)
    else
        LibCustomGlow.PixelGlow_Stop(playerFrame, OFFENSIVE_MAJOR_GLOW_KEY)
    end

    if not playerFrame.offensiveMinorMarker and CanMutateProtectedFrames() then
        CreateOffensiveMinorMarker(playerFrame)
    end

    if playerFrame.offensiveMinorMarker then
        if hasMinor then
            playerFrame.offensiveMinorMarker:SetColorTexture(OFFENSIVE_MINOR_MARKER_COLOR[1],
                OFFENSIVE_MINOR_MARKER_COLOR[2], OFFENSIVE_MINOR_MARKER_COLOR[3], OFFENSIVE_MINOR_MARKER_COLOR[4])
            playerFrame.offensiveMinorMarker:SetAlpha(playerFrame.visualAlpha or 0.9)
            playerFrame.offensiveMinorMarker:Show()
        else
            playerFrame.offensiveMinorMarker:Hide()
        end
    end

    playerFrame.offensiveState = state
end

local function GetOffensiveCastWindowStateForUnit(unit)
    if not unit or not UnitExists(unit) then
        return OFFENSIVE_STATE_NONE
    end

    local guid = UnitGUID(unit)
    local windows = guid and offensiveCastWindowsByGUID[guid]
    if not windows then
        return OFFENSIVE_STATE_NONE
    end

    local now = GetTime()
    local hasMajor = false
    local hasMinor = false
    local hasAnyWindow = false

    for spellID, window in pairs(windows) do
        if type(window) == "table" and IsCleanNumber(window.expires) and window.expires > now and
            IsOffensiveBuffEnabled(spellID) then
            hasAnyWindow = true
            if window.tier == OFFENSIVE_TIER_MAJOR then
                hasMajor = true
            elseif window.tier == OFFENSIVE_TIER_MINOR then
                hasMinor = true
            end
        else
            windows[spellID] = nil
        end
    end

    if not hasAnyWindow then
        offensiveCastWindowsByGUID[guid] = nil
        return OFFENSIVE_STATE_NONE
    end
    if hasMajor and hasMinor then
        return OFFENSIVE_STATE_BOTH
    end
    if hasMajor then
        return OFFENSIVE_STATE_MAJOR
    end
    if hasMinor then
        return OFFENSIVE_STATE_MINOR
    end
    return OFFENSIVE_STATE_NONE
end

local function GetOffensiveStateForUnit(unit)
    if not unit or not addon.db or not addon.db.profile then
        return OFFENSIVE_STATE_NONE
    end

    EnsureOffensiveBuffStateTables()
    if addon.db.profile.offensiveBuffs.enabled == false then
        return OFFENSIVE_STATE_NONE
    end

    local hasMajor = false
    local hasMinor = false
    local defaultList = addon.OffensiveBuffList or {}

    for spellID in pairs(defaultList) do
        if IsOffensiveBuffEnabled(spellID) and HasHelpfulAuraBySpellID(unit, spellID) then
            local _, tier = GetOffensiveBuffDefinition(spellID)
            if tier == OFFENSIVE_TIER_MAJOR then
                hasMajor = true
            elseif tier == OFFENSIVE_TIER_MINOR then
                hasMinor = true
            end
        end
    end

    local custom = addon.db.profile.offensiveBuffs.custom or {}
    for spellID in pairs(custom) do
        if not defaultList[spellID] and IsOffensiveBuffEnabled(spellID) and HasHelpfulAuraBySpellID(unit, spellID) then
            local _, tier = GetOffensiveBuffDefinition(spellID)
            if tier == OFFENSIVE_TIER_MAJOR then
                hasMajor = true
            elseif tier == OFFENSIVE_TIER_MINOR then
                hasMinor = true
            end
        end
    end

    local castWindowState = GetOffensiveCastWindowStateForUnit(unit)
    if castWindowState == OFFENSIVE_STATE_BOTH then
        hasMajor = true
        hasMinor = true
    elseif castWindowState == OFFENSIVE_STATE_MAJOR then
        hasMajor = true
    elseif castWindowState == OFFENSIVE_STATE_MINOR then
        hasMinor = true
    end

    if hasMajor and hasMinor then
        return OFFENSIVE_STATE_BOTH
    end
    if hasMajor then
        return OFFENSIVE_STATE_MAJOR
    end
    if hasMinor then
        return OFFENSIVE_STATE_MINOR
    end
    return OFFENSIVE_STATE_NONE
end

RefreshOffensiveBuffHighlight = function(playerFrame, unit)
    if not playerFrame or not unit then
        return
    end
    ApplyOffensiveBuffVisualState(playerFrame, GetOffensiveStateForUnit(unit))
end

local function RefreshOffensiveHighlightSurfacesForUnit(unit)
    if RefreshOffensiveBuffHighlightsForAllSelectedUnits then
        RefreshOffensiveBuffHighlightsForAllSelectedUnits()
    end
    if RefreshBlizzardCompactFrameHighlightsForUnit then
        RefreshBlizzardCompactFrameHighlightsForUnit(unit)
    elseif RefreshBlizzardCompactFrameHighlightsForAllUnits then
        RefreshBlizzardCompactFrameHighlightsForAllUnits()
    end
    if RefreshPrescienceThinTrackerOffensiveStateForUnit then
        RefreshPrescienceThinTrackerOffensiveStateForUnit(unit)
    end
end

local function GetOffensiveBuffDefinitionForCastSpellID(spellID)
    spellID = GetCleanPositiveSpellID(spellID)
    if not spellID then
        return nil
    end

    for auraSpellID, definition in pairs(addon.OffensiveBuffList or {}) do
        if type(definition) == "table" then
            local castSpellID = GetCleanPositiveSpellID(definition.castSpellID) or GetCleanPositiveSpellID(auraSpellID)
            if castSpellID == spellID and IsOffensiveBuffEnabled(auraSpellID) then
                local tier = NormalizeOffensiveTier(definition.tier) or OFFENSIVE_TIER_MINOR
                return auraSpellID, definition, tier
            end
        end
    end

    return nil
end

local function RecordOffensiveCastWindow(unit, spellID)
    if not unit or not UnitExists(unit) or (UnitIsUnit and UnitIsUnit(unit, "player")) then
        return
    end

    local auraSpellID, definition, tier = GetOffensiveBuffDefinitionForCastSpellID(spellID)
    if not auraSpellID or type(definition) ~= "table" then
        return
    end

    local castWindow = definition.castWindow
    if not IsCleanPositiveNumber(castWindow) then
        return
    end

    local guid = UnitGUID(unit)
    if not guid then
        return
    end

    offensiveCastWindowsByGUID[guid] = offensiveCastWindowsByGUID[guid] or {}
    offensiveCastWindowsByGUID[guid][auraSpellID] = {
        tier = tier,
        expires = GetTime() + castWindow,
    }

    RefreshOffensiveHighlightSurfacesForUnit(unit)
    if C_Timer and C_Timer.After then
        C_Timer.After(castWindow, function()
            RefreshOffensiveHighlightSurfacesForUnit(unit)
        end)
    end
end

local function BlizzardCompactFrameRefreshPending()
    blizzardCompactFrameRefreshPending = true
end

local function SetBlizzardCompactFrameVisualState(frame, state)
    local overlay = frame and blizzardCompactFrameOverlays[frame]
    if not overlay then
        return
    end

    if state ~= OFFENSIVE_STATE_MINOR and state ~= OFFENSIVE_STATE_MAJOR and state ~= OFFENSIVE_STATE_BOTH then
        state = OFFENSIVE_STATE_NONE
    end

    local hasMajor = state == OFFENSIVE_STATE_MAJOR or state == OFFENSIVE_STATE_BOTH
    local hasMinor = state == OFFENSIVE_STATE_MINOR or state == OFFENSIVE_STATE_BOTH
    local alpha = frame.IsShown and frame:IsShown() and 1 or 0

    overlay.majorGlowAnchor:SetAlpha(hasMajor and alpha or 0)
    overlay.minorMarker:SetAlpha(hasMinor and alpha or 0)
    overlay.offensiveState = state
end

local function EnsureBlizzardCompactFrameOverlay(frame)
    if not frame or (frame.IsForbidden and frame:IsForbidden()) then
        return nil
    end

    local overlay = blizzardCompactFrameOverlays[frame]
    if overlay then
        return overlay
    end

    if not CanMutateProtectedFrames() then
        BlizzardCompactFrameRefreshPending()
        return nil
    end

    overlay = CreateFrame("Frame", nil, UIParent)
    overlay:EnableMouse(false)
    overlay:SetPoint("TOPLEFT", frame, "TOPLEFT", -2, 2)
    overlay:SetPoint("BOTTOMRIGHT", frame, "BOTTOMRIGHT", 2, -2)
    if frame.GetFrameStrata then
        overlay:SetFrameStrata(frame:GetFrameStrata())
    end
    if frame.GetFrameLevel then
        overlay:SetFrameLevel(frame:GetFrameLevel() + 30)
    end

    local majorGlowAnchor = CreateFrame("Frame", nil, overlay)
    majorGlowAnchor:SetAllPoints(overlay)
    majorGlowAnchor:SetAlpha(0)
    overlay.majorGlowAnchor = majorGlowAnchor
    LibCustomGlow.PixelGlow_Start(majorGlowAnchor, OFFENSIVE_MAJOR_GLOW_COLOR, 8, 0.35, 10, 3, 0, 0, true,
        BLIZZARD_COMPACT_MAJOR_GLOW_KEY)

    local minorMarker = overlay:CreateTexture(nil, "OVERLAY")
    minorMarker:SetColorTexture(OFFENSIVE_MINOR_MARKER_COLOR[1], OFFENSIVE_MINOR_MARKER_COLOR[2],
        OFFENSIVE_MINOR_MARKER_COLOR[3], OFFENSIVE_MINOR_MARKER_COLOR[4])
    minorMarker:SetPoint("TOPLEFT", overlay, "TOPLEFT", -1, 0)
    minorMarker:SetPoint("BOTTOMLEFT", overlay, "BOTTOMLEFT", -1, 0)
    minorMarker:SetWidth(BLIZZARD_COMPACT_MINOR_MARKER_WIDTH)
    minorMarker:SetAlpha(0)
    overlay.minorMarker = minorMarker

    blizzardCompactFrameOverlays[frame] = overlay
    return overlay
end

local function IsUnitEligibleForBlizzardCompactHighlight(unit)
    if not unit or not UnitExists(unit) then
        return false
    end
    if UnitIsUnit and UnitIsUnit(unit, "player") then
        return false
    end

    local combatRole = addon.GetUnitCombatRole(unit)

    return combatRole == "DPS"
end

local function UpdateBlizzardCompactFrameHighlight(frame, unit)
    if not frame or not addon.db or not addon.db.profile then
        return
    end

    EnsureBlizzardFrameHighlightState()
    local settings = addon.db.profile.blizzardFrameHighlights
    if settings.enabled == false then
        SetBlizzardCompactFrameVisualState(frame, OFFENSIVE_STATE_NONE)
        return
    end
    if not IsRuntimeVisibilityAllowed() then
        SetBlizzardCompactFrameVisualState(frame, OFFENSIVE_STATE_NONE)
        return
    end

    unit = unit or frame.displayedUnit or frame.unit
    if IsInRaid() and not settings.showRaid then
        SetBlizzardCompactFrameVisualState(frame, OFFENSIVE_STATE_NONE)
        return
    end
    if not IsUnitEligibleForBlizzardCompactHighlight(unit) then
        SetBlizzardCompactFrameVisualState(frame, OFFENSIVE_STATE_NONE)
        return
    end

    if not EnsureBlizzardCompactFrameOverlay(frame) then
        return
    end

    SetBlizzardCompactFrameVisualState(frame, GetOffensiveStateForUnit(unit))
end

local function UpdateNamedBlizzardCompactFrame(prefix, index)
    local frame = _G[prefix .. index]
    if frame then
        UpdateBlizzardCompactFrameHighlight(frame)
    end
end

local function ClearBlizzardCompactFrameHighlights()
    for frame in pairs(blizzardCompactFrameOverlays) do
        SetBlizzardCompactFrameVisualState(frame, OFFENSIVE_STATE_NONE)
    end
end

RefreshBlizzardCompactFrameHighlightsForUnit = function(unit)
    if not unit then
        return
    end
    if not addon.db or not addon.db.profile then
        return
    end
    EnsureBlizzardFrameHighlightState()

    for index = 1, 5 do
        local frame = _G["CompactPartyFrameMember" .. index]
        if frame and (frame.displayedUnit == unit or frame.unit == unit) then
            UpdateBlizzardCompactFrameHighlight(frame, unit)
        end
    end

    if addon.db.profile.blizzardFrameHighlights.showRaid then
        for index = 1, 40 do
            local frame = _G["CompactRaidFrame" .. index]
            if frame and (frame.displayedUnit == unit or frame.unit == unit) then
                UpdateBlizzardCompactFrameHighlight(frame, unit)
            end
        end
    end
end

RefreshBlizzardCompactFrameHighlightsForAllUnits = function()
    if not addon.db or not addon.db.profile then
        return
    end

    EnsureBlizzardFrameHighlightState()
    if addon.db.profile.blizzardFrameHighlights.enabled == false then
        ClearBlizzardCompactFrameHighlights()
        return
    end

    for index = 1, 5 do
        UpdateNamedBlizzardCompactFrame("CompactPartyFrameMember", index)
    end

    if addon.db.profile.blizzardFrameHighlights.showRaid then
        for index = 1, 40 do
            UpdateNamedBlizzardCompactFrame("CompactRaidFrame", index)
        end
    end
end

local function ClearBuffIcons(playerFrame)
    local buff = playerFrame and playerFrame["buff"]
    if not buff then
        return
    end

    local keys = {}
    for key in pairs(buff) do
        if key ~= "xOffset" then
            table.insert(keys, key)
        end
    end

    for _, key in ipairs(keys) do
        local region = buff[key]
        if type(region) == "table" then
            if string.match(tostring(key), "Text$") and region.ticker then
                region.ticker:Cancel()
            end
            if region.Hide then
                region:Hide()
            end
            if region.ClearAllPoints then
                region:ClearAllPoints()
            end
            if region.SetParent then
                region:SetParent(nil)
            end
        end
        buff[key] = nil
    end

    buff.xOffset = 0
    ApplyPrescienceBarFill(playerFrame, nil, nil)
end

local function RemoveBuffIcon(playerFrame, buffID)
    local buff = playerFrame and playerFrame["buff"]
    local iconFrame = buff and buff[buffID]
    if not iconFrame then
        return
    end

    local isPrescience = iconFrame.iconid == PRESCIENCE_ICON_ID
    if isPrescience and addon.db.profile.prescienceBuffSoundName ~= "None" then
        PlaySoundFile(addon.db.profile.prescienceBuffSoundFile, "Master")
    end
    if iconFrame.glow then
        LibCustomGlow.PixelGlow_Stop(playerFrame)
    end

    local text = buff[buffID .. "Text"]
    if text then
        if text.ticker then
            text.ticker:Cancel()
        end
        text:Hide()
        text:ClearAllPoints()
        buff[buffID .. "Text"] = nil
    end

    iconFrame:Hide()
    iconFrame:ClearAllPoints()
    iconFrame:SetParent(nil)
    buff[buffID] = nil

    if isPrescience then
        ApplyPrescienceBarFill(playerFrame, nil, nil)
    end

    RepositionBuffIcons(playerFrame)
end

local function AddBuffIcon(playerFrame, auraInstanceID, timestamp, icon, startTimer, spellID)
    if playerFrame == nil or not playerFrame["buff"] then
        return
    end
    local cleanSpellID = GetCleanPositiveSpellID(spellID)
    if not IsCleanPositiveNumber(auraInstanceID) or not IsCleanPositiveNumber(timestamp) or not IsCleanPositiveNumber(startTimer)
        or not IsCleanAuraIcon(icon) or not cleanSpellID then
        return
    end

    if playerFrame["buff"][auraInstanceID] then
        if playerFrame["buff"][auraInstanceID .. "Text"] then
            playerFrame["buff"][auraInstanceID .. "Text"].timestamp = timestamp
            playerFrame["buff"][auraInstanceID .. "Text"].starttimestamp = startTimer
        end
        if icon == PRESCIENCE_ICON_ID then
            ApplyPrescienceBarFill(playerFrame, timestamp, startTimer)
        end
        return
    end
    playerFrame["buff"][auraInstanceID] = playerFrame:CreateTexture(nil, "OVERLAY")
    playerFrame["buff"][auraInstanceID].iconid = icon
    playerFrame["buff"][auraInstanceID].glow = false
    playerFrame["buff"][auraInstanceID]:SetTexture(icon)
    playerFrame["buff"][auraInstanceID]:SetSize(addon.db.profile.spellIconSize, addon.db.profile.spellIconSize)
    playerFrame["buff"][auraInstanceID]:SetPoint("LEFT", playerFrame, "RIGHT", playerFrame["buff"].xOffset, 0)
    playerFrame["buff"][auraInstanceID]:SetVertexColor(1, 1, 1, 1)
    playerFrame["buff"][auraInstanceID]:Show()
    playerFrame["buff"][auraInstanceID .. "Text"] = playerFrame:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    playerFrame["buff"][auraInstanceID .. "Text"]:SetPoint("CENTER", playerFrame["buff"][auraInstanceID], "CENTER", 0, 0)
    playerFrame["buff"][auraInstanceID .. "Text"]:SetTextColor(1, 1, 1)
    playerFrame["buff"][auraInstanceID .. "Text"]:SetFont("Fonts\\ARIALN.TTF", addon.db.profile.spellIconTextSize,
        "OUTLINE")
    playerFrame["buff"][auraInstanceID .. "Text"]:Show()
    local visualAlpha = playerFrame.visualAlpha or 0.9
    playerFrame["buff"][auraInstanceID]:SetAlpha(visualAlpha)
    playerFrame["buff"][auraInstanceID .. "Text"]:SetAlpha(visualAlpha)
    playerFrame["buff"][auraInstanceID .. "Text"].timestamp = timestamp
    playerFrame["buff"][auraInstanceID .. "Text"].starttimestamp = startTimer
    if icon == PRESCIENCE_ICON_ID then
        ApplyPrescienceBarFill(playerFrame, timestamp, startTimer)
    end
    playerFrame["buff"][auraInstanceID .. "Text"].ticker = C_Timer.NewTicker(1, function()
        local buff = playerFrame["buff"]
        local text = buff and buff[auraInstanceID .. "Text"]
        if text == nil then
            return
        end
        local expirationTime = text.timestamp
        local startDuration = text.starttimestamp
        if not IsCleanPositiveNumber(expirationTime) or not IsCleanPositiveNumber(startDuration) then
            text:SetText(nil)
            return
        end

        local duration = expirationTime - GetTime()
        if icon == PRESCIENCE_ICON_ID then
            ApplyPrescienceBarFill(playerFrame, expirationTime, startDuration)
        end
        if duration > 10 then
            text:SetTextColor(1, 1, 1)
        else
            text:SetTextColor(1, 0, 0)
        end
        if duration <= 0 then
            text:Hide()
            if text.ticker then
                text.ticker:Cancel()
            end
            RemoveBuffIcon(playerFrame, auraInstanceID)
        elseif duration <= 20 then
            text:SetText(math.floor(duration))
        else
            text:SetText(nil)
        end
    end)
    playerFrame["buff"].xOffset = playerFrame["buff"].xOffset + addon.db.profile.spellIconSize

    if cleanSpellID == addon.SENSE_POWER_AURA_SPELL_ID then
        playerFrame["buff"][auraInstanceID].glow = true
        LibCustomGlow.PixelGlow_Start(playerFrame, { 0.95, 0.95, 0.32, 1 }, 8, 0.25, 10, 3, 0, 0, true, nil)
    end
end

local function AddBuffIcons(playerFrame, unit)
    if not playerFrame["buff"] then
        playerFrame["buff"] = {}
        playerFrame["buff"].xOffset = 0
    end

    for k in pairs(addon.db.profile.buffList) do
        if IsTrackedBuffEnabled(k) then
            local spellTable = FindTrackedAuraBySpellID(unit, k)
            if spellTable then
                if IsCleanPositiveNumber(spellTable.expirationTime) then
                    AddBuffIcon(playerFrame, spellTable.auraInstanceID, spellTable.expirationTime, spellTable.icon,
                        spellTable.duration, spellTable.spellId)
                end
            end
        end
    end
end

local function IsPrescienceThinTrackerRuntimeAllowed()
    if not addon.db or not addon.db.profile then
        return false
    end

    local settings = addon.db.profile.prescienceThinTracker
    if type(settings) ~= "table" then
        return false
    end

    if prescienceThinTrackerTestMode then
        return true
    end

    if settings.enabled == false then
        return false
    end

    if GetUnitClassToken("player") ~= "EVOKER" then
        return false
    end

    local currentSpec = GetSpecialization()
    if currentSpec and currentSpec ~= 3 then
        return false
    end

    local _, instanceType = IsInInstance()
    if instanceType == "raid" then
        return false
    end
    return ShouldShowForInstanceType(instanceType)
end

local function SchedulePrescienceThinTrackerRosterRefresh(generation, expectedInstanceType)
    if expectedInstanceType == "raid" then
        return
    end

    local attempts = 0
    local function retry()
        if not IsCurrentInstanceContext(generation, expectedInstanceType) then
            return
        end
        if not IsPrescienceThinTrackerRuntimeAllowed() then
            return
        end

        RefreshPrescienceThinTrackerRoster()
        UpdatePrescienceThinTrackerVisibility()

        attempts = attempts + 1
        if attempts < 6 then
            C_Timer.After(1.0, retry)
        end
    end

    C_Timer.After(0.5, retry)
end

local function ClearPrescienceThinTrackerRows()
    for _, row in pairs(prescienceThinTrackerRows) do
        if row.frame then
            LibCustomGlow.PixelGlow_Stop(row.frame, OFFENSIVE_THIN_TRACKER_MAJOR_GLOW_KEY)
            row.frame:Hide()
            row.frame:ClearAllPoints()
            row.frame:SetParent(nil)
        end
    end
    prescienceThinTrackerRows = {}
    prescienceThinTrackerRowOrder = {}
end

local function LayoutPrescienceThinTrackerRows()
    if not prescienceThinTrackerFrame or not addon.db or not addon.db.profile then
        return
    end

    local settings = addon.db.profile.prescienceThinTracker
    local rowWidth = settings.rowWidth
    local rowHeight = settings.rowHeight
    local rowSpacing = settings.rowSpacing
    local rowCount = #prescienceThinTrackerRowOrder
    local totalHeight = rowHeight
    if rowCount > 0 then
        totalHeight = (rowCount * rowHeight) + ((rowCount - 1) * rowSpacing)
    end

    prescienceThinTrackerFrame:SetSize(rowWidth, totalHeight)
    for index, row in ipairs(prescienceThinTrackerRowOrder) do
        row.frame:ClearAllPoints()
        row.frame:SetSize(rowWidth, rowHeight)
        row.track:SetAllPoints(row.frame)
        row.fill:SetHeight(rowHeight)
        row.nameText:ClearAllPoints()
        row.nameText:SetPoint("CENTER", row.frame, "CENTER", 0, 0)
        if index == 1 then
            row.frame:SetPoint("TOP", prescienceThinTrackerFrame, "TOP", 0, 0)
        else
            row.frame:SetPoint("TOP", prescienceThinTrackerRowOrder[index - 1].frame, "BOTTOM", 0, -rowSpacing)
        end
    end
end

local function CreatePrescienceThinTrackerRow(member)
    if not member or not member.identityKey or not prescienceThinTrackerFrame then
        return nil
    end

    local row = prescienceThinTrackerRows[member.identityKey]
    if not row then
        local frame = CreateFrame("Frame", nil, prescienceThinTrackerFrame, BackdropTemplateMixin and "BackdropTemplate")
        frame:SetBackdrop({
            bgFile = [=[Interface\Tooltips\UI-Tooltip-Background]=],
            insets = { top = 0, left = 0, bottom = 0, right = 0 }
        })
        frame:SetBackdropColor(0.03, 0.03, 0.03, 0.78)

        local track = frame:CreateTexture(nil, "BACKGROUND")
        track:SetColorTexture(0.02, 0.02, 0.02, 0.82)

        local rangeMarker = frame:CreateTexture(nil, "OVERLAY")
        rangeMarker:SetPoint("TOPLEFT", frame, "TOPLEFT", 0, 0)
        rangeMarker:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", 0, 0)
        rangeMarker:SetWidth(PRESCIENCE_THIN_TRACKER_RANGE_MARKER_WIDTH)
        rangeMarker:SetColorTexture(PRESCIENCE_THIN_TRACKER_RANGE_COLORS.unknown[1],
            PRESCIENCE_THIN_TRACKER_RANGE_COLORS.unknown[2], PRESCIENCE_THIN_TRACKER_RANGE_COLORS.unknown[3],
            PRESCIENCE_THIN_TRACKER_RANGE_COLORS.unknown[4])

        local offensiveMinorMarker = frame:CreateTexture(nil, "OVERLAY")
        offensiveMinorMarker:SetPoint("TOPRIGHT", frame, "TOPRIGHT", 0, 0)
        offensiveMinorMarker:SetPoint("BOTTOMRIGHT", frame, "BOTTOMRIGHT", 0, 0)
        offensiveMinorMarker:SetWidth(4)
        offensiveMinorMarker:SetColorTexture(OFFENSIVE_MINOR_MARKER_COLOR[1], OFFENSIVE_MINOR_MARKER_COLOR[2],
            OFFENSIVE_MINOR_MARKER_COLOR[3], OFFENSIVE_MINOR_MARKER_COLOR[4])
        offensiveMinorMarker:Hide()

        local fill = frame:CreateTexture(nil, "ARTWORK")
        fill:SetTexture(addon.db.profile.backgroundTextTexture)
        fill:SetPoint("TOPLEFT", frame, "TOPLEFT", 0, 0)
        fill:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", 0, 0)
        fill:Hide()

        local nameText = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
        nameText:SetJustifyH("CENTER")
        nameText:SetJustifyV("MIDDLE")

        row = {
            frame = frame,
            track = track,
            fill = fill,
            nameText = nameText,
        }
        row.rangeMarker = rangeMarker
        row.offensiveMinorMarker = offensiveMinorMarker
        prescienceThinTrackerRows[member.identityKey] = row
    end

    local classR, classG, classB = GetClassRGB(member.class)
    row.identityKey = member.identityKey
    row.unit = member.unit
    row.name = member.name
    row.class = member.class
    row.fill:SetVertexColor(classR, classG, classB, 0.95)
    row.nameText:SetText(member.name or "")
    row.nameText:SetTextColor(1, 1, 1, 0.95)
    row.frame:Show()
    return row
end

local function ApplyPrescienceThinTrackerOffensiveState(row, state)
    if not row or not row.frame then
        return
    end

    if state ~= OFFENSIVE_STATE_MINOR and state ~= OFFENSIVE_STATE_MAJOR and state ~= OFFENSIVE_STATE_BOTH then
        state = OFFENSIVE_STATE_NONE
    end
    if row.offensiveState == state then
        return
    end

    local hasMajor = state == OFFENSIVE_STATE_MAJOR or state == OFFENSIVE_STATE_BOTH
    local hasMinor = state == OFFENSIVE_STATE_MINOR or state == OFFENSIVE_STATE_BOTH

    if hasMajor then
        LibCustomGlow.PixelGlow_Start(row.frame, OFFENSIVE_MAJOR_GLOW_COLOR, 8, 0.35, 10, 3, 0, 0, true,
            OFFENSIVE_THIN_TRACKER_MAJOR_GLOW_KEY)
    else
        LibCustomGlow.PixelGlow_Stop(row.frame, OFFENSIVE_THIN_TRACKER_MAJOR_GLOW_KEY)
    end

    if row.offensiveMinorMarker then
        if hasMinor then
            row.offensiveMinorMarker:Show()
        else
            row.offensiveMinorMarker:Hide()
        end
    end

    row.offensiveState = state
end

RefreshPrescienceThinTrackerOffensiveStateForUnit = function(unit)
    if not prescienceThinTrackerFrame then
        return
    end

    for _, row in ipairs(prescienceThinTrackerRowOrder) do
        if not unit or row.unit == unit or (prescienceThinTrackerTestMode and row.isTestRow) then
            local state = OFFENSIVE_STATE_NONE
            if prescienceThinTrackerTestMode and row.isTestRow then
                state = row.testOffensiveState or OFFENSIVE_STATE_NONE
            elseif row.unit then
                state = GetOffensiveStateForUnit(row.unit)
            end
            ApplyPrescienceThinTrackerOffensiveState(row, state)
        end
    end
end

local function ApplyPrescienceThinTrackerRangeState(row)
    if not row or not row.rangeMarker then
        return
    end

    local rangeState = "unknown"
    if prescienceThinTrackerTestMode and row.isTestRow then
        rangeState = row.testRangeState or "unknown"
    elseif row.unit and UnitExists(row.unit) then
        local inRange = UnitInRange(row.unit)
        if inRange then
            rangeState = "inRange"
        elseif inRange == false then
            rangeState = "outOfRange"
        end
    end

    local color = PRESCIENCE_THIN_TRACKER_RANGE_COLORS[rangeState] or PRESCIENCE_THIN_TRACKER_RANGE_COLORS.unknown
    row.rangeMarker:SetColorTexture(color[1], color[2], color[3], color[4])
    if row.frame then
        row.frame:SetAlpha(rangeState == "outOfRange" and 0.55 or 1)
    end
end

UpdatePrescienceThinTrackerRows = function()
    if not prescienceThinTrackerFrame or not addon.db or not addon.db.profile then
        return
    end

    local settings = addon.db.profile.prescienceThinTracker
    local now = GetTime()
    for _, row in ipairs(prescienceThinTrackerRowOrder) do
        ApplyPrescienceThinTrackerRangeState(row)

        local width = 0
        local expirationTime = row.expirationTime
        local duration = row.duration
        if IsCleanPositiveNumber(expirationTime) and IsCleanPositiveNumber(duration) then
            local remaining = expirationTime - now
            if remaining <= 0 and prescienceThinTrackerTestMode and row.isTestRow then
                row.expirationTime = now + duration
                remaining = duration
            end
            if remaining > 0 then
                width = settings.rowWidth * (remaining / duration)
                width = math.max(1, math.min(settings.rowWidth, width))
            end
        end

        if width > 0 then
            row.fill:SetWidth(width)
            row.fill:Show()
        else
            row.fill:SetWidth(1)
            row.fill:Hide()
        end
    end
end

local function RefreshPrescienceThinTrackerTestRows()
    CreatePrescienceThinTrackerFrame()
    if not prescienceThinTrackerFrame then
        return
    end

    ClearPrescienceThinTrackerRows()
    local now = GetTime()
    for _, member in ipairs(PRESCIENCE_THIN_TRACKER_TEST_MEMBERS) do
        local row = CreatePrescienceThinTrackerRow(member)
        if row then
            local remaining = member.remaining or PRESCIENCE_THIN_TRACKER_TEST_DURATION
            row.isTestRow = true
            row.testRangeState = member.testRangeState
            row.testOffensiveState = member.testOffensiveState
            row.duration = PRESCIENCE_THIN_TRACKER_TEST_DURATION
            row.expirationTime = now + remaining
            table.insert(prescienceThinTrackerRowOrder, row)
        end
    end

    LayoutPrescienceThinTrackerRows()
    RefreshPrescienceThinTrackerOffensiveStateForUnit()
    UpdatePrescienceThinTrackerRows()
end

RefreshPrescienceThinTrackerAuras = function(unit)
    if prescienceThinTrackerTestMode then
        UpdatePrescienceThinTrackerRows()
        return
    end

    if not prescienceThinTrackerFrame then
        return
    end

    for _, row in ipairs(prescienceThinTrackerRowOrder) do
        if not unit or row.unit == unit then
            local aura = FindTrackedAuraBySpellID(row.unit, 410089)
            if aura and IsCleanPositiveNumber(aura.expirationTime) and IsCleanPositiveNumber(aura.duration) then
                row.expirationTime = aura.expirationTime
                row.duration = aura.duration
            else
                row.expirationTime = nil
                row.duration = nil
            end
        end
    end
    RefreshPrescienceThinTrackerOffensiveStateForUnit(unit)
    UpdatePrescienceThinTrackerRows()
end

UpdatePrescienceThinTrackerVisibility = function()
    if not prescienceThinTrackerFrame or not addon.db or not addon.db.profile then
        return
    end

    local hasRows = #prescienceThinTrackerRowOrder > 0
    if prescienceThinTrackerTestMode then
        prescienceThinTrackerFrame:Show()
    elseif IsPrescienceThinTrackerRuntimeAllowed() and hasRows then
        prescienceThinTrackerFrame:Show()
    else
        prescienceThinTrackerFrame:Hide()
    end
end

RefreshPrescienceThinTrackerRoster = function()
    if not addon.db or not addon.db.profile then
        return
    end

    CreatePrescienceThinTrackerFrame()
    if prescienceThinTrackerTestMode then
        RefreshPrescienceThinTrackerTestRows()
        UpdatePrescienceThinTrackerVisibility()
        return
    end

    if not IsPrescienceThinTrackerRuntimeAllowed() then
        ClearPrescienceThinTrackerRows()
        UpdatePrescienceThinTrackerVisibility()
        return
    end

    local seenRows = {}
    prescienceThinTrackerRowOrder = {}
    local partyMembers = GetHomePartyInfos()
    for _, member in ipairs(partyMembers) do
        if member.role == "DPS" and not UnitIsUnit(member.unit, "player") then
            local row = CreatePrescienceThinTrackerRow(member)
            if row then
                row.isTestRow = nil
                row.testRangeState = nil
                row.testOffensiveState = nil
                seenRows[member.identityKey] = true
                table.insert(prescienceThinTrackerRowOrder, row)
            end
        end
    end

    for identityKey, row in pairs(prescienceThinTrackerRows) do
        if not seenRows[identityKey] then
            if row.frame then
                LibCustomGlow.PixelGlow_Stop(row.frame, OFFENSIVE_THIN_TRACKER_MAJOR_GLOW_KEY)
                row.frame:Hide()
                row.frame:ClearAllPoints()
                row.frame:SetParent(nil)
            end
            prescienceThinTrackerRows[identityKey] = nil
        end
    end

    LayoutPrescienceThinTrackerRows()
    RefreshPrescienceThinTrackerAuras()
    UpdatePrescienceThinTrackerVisibility()
end

local function SetPrescienceThinTrackerTestMode(enabled)
    prescienceThinTrackerTestMode = enabled == true
    RefreshPrescienceThinTrackerRoster()
    UpdatePrescienceThinTrackerVisibility()
end

CreatePrescienceThinTrackerFrame = function()
    if prescienceThinTrackerFrame or not addon.db or not addon.db.profile then
        return
    end

    local settings = addon.db.profile.prescienceThinTracker
    prescienceThinTrackerFrame = CreateFrame("Frame", "EvokerAugPrescienceThinTracker", UIParent, BackdropTemplateMixin and "BackdropTemplate")
    prescienceThinTrackerFrame:SetSize(settings.rowWidth, settings.rowHeight)
    prescienceThinTrackerFrame:SetMovable(true)
    LoadPositionFromTable(prescienceThinTrackerFrame, addon.db.profile.prescienceThinTracker.position)
    prescienceThinTrackerFrame:EnableMouse(true)
    prescienceThinTrackerFrame:RegisterForDrag("LeftButton")
    prescienceThinTrackerFrame:SetBackdrop({
        bgFile = [=[Interface\Tooltips\UI-Tooltip-Background]=],
        insets = { top = 0, left = 0, bottom = 0, right = 0 }
    })
    prescienceThinTrackerFrame:SetBackdropColor(0.02, 0.02, 0.02, 0.35)

    prescienceThinTrackerFrame:SetScript("OnDragStart", function(frame)
        if not addon.db.profile.prescienceThinTracker.locked then
            frame.evokerAugIsMoving = true
            frame:StartMoving()
        end
    end)
    prescienceThinTrackerFrame:SetScript("OnDragStop", function(frame)
        if frame.evokerAugIsMoving then
            frame.evokerAugIsMoving = nil
            frame:StopMovingOrSizing()
            SavePositionToTable(prescienceThinTrackerFrame, addon.db.profile.prescienceThinTracker.position)
        end
    end)
    prescienceThinTrackerFrame:SetScript("OnMouseUp", function(_, button)
        if button == "RightButton" then
            addon.db.profile.prescienceThinTracker.locked = not addon.db.profile.prescienceThinTracker.locked
            UpdatePrescienceThinTrackerVisibility()
        end
    end)
    prescienceThinTrackerFrame:SetScript("OnUpdate", function(_, elapsed)
        prescienceThinTrackerUpdateElapsed = prescienceThinTrackerUpdateElapsed + (elapsed or 0)
        if prescienceThinTrackerUpdateElapsed < 0.05 then
            return
        end
        prescienceThinTrackerUpdateElapsed = 0
        UpdatePrescienceThinTrackerRows()
    end)

    UpdatePrescienceThinTrackerVisibility()
end

--- Create Player Frame ----

local function CheckDistance(playerFrame)
    local unit = playerFrame.unit
    if unit ~= "player" and UnitExists(unit) then
        local inRange = UnitInRange(unit)
        if inRange then
            ApplyPlayerFrameVisualAlpha(playerFrame, 0.9)
        else
            ApplyPlayerFrameVisualAlpha(playerFrame, 0.3)
        end
    end
end

local function UpdateDistance()
    for _, playerFrame in ipairs(selectedPlayerFrames) do
        CheckDistance(playerFrame)
    end
end

local function MacroUpdate(frame)
    local macroProfile = frame.role == "TANK" and addon.db.profile.tankMacros or addon.db.profile.dpsMacros
    local spellProfile = addon.db.profile.charSpell
    local leftSpell = spellProfile[macroProfile.LeftSpell]

    frame:SetAttribute("type", "spell")
    frame:SetAttribute("type1", "spell")
    frame:SetAttribute("spell", leftSpell)
    frame:SetAttribute("spell1", leftSpell)

    if addon.db.profile.macro.AltClick then
        frame:SetAttribute("alt-type1", "spell")
        frame:SetAttribute("alt-spell1", spellProfile[macroProfile.AltSpell])
    else
        frame:SetAttribute("alt-type1", nil)
        frame:SetAttribute("alt-spell1", nil)
    end

    if addon.db.profile.macro.ShiftClick then
        frame:SetAttribute("shift-type1", "spell")
        frame:SetAttribute("shift-spell1", spellProfile[macroProfile.ShiftSpell])
    else
        frame:SetAttribute("shift-type1", nil)
        frame:SetAttribute("shift-spell1", nil)
    end

    if addon.db.profile.macro.CtrlClick then
        frame:SetAttribute("ctrl-type1", "spell")
        frame:SetAttribute("ctrl-spell1", spellProfile[macroProfile.CtrlSpell])
    else
        frame:SetAttribute("ctrl-type1", nil)
        frame:SetAttribute("ctrl-spell1", nil)
    end

    frame:SetAttribute("ctrl-type2", nil)
    frame:SetAttribute("ctrl-spell2", nil)
    frame:SetAttribute("alt-type2", nil)
    frame:SetAttribute("alt-spell2", nil)
    frame:SetAttribute("shift-type2", nil)
    frame:SetAttribute("shift-spell2", nil)

    frame:SetAttribute("type2", "spell")
    if addon.db.profile.macro.RightClick then
        frame:SetAttribute("spell2", spellProfile[macroProfile.RightSpell])
    else
        frame:SetAttribute("spell2", "")
    end
end

local function UpdatePlayerFrame()
    if not CanMutateProtectedFrames() then
        MarkProtectedFrameRefreshPending()
        return
    end

    for i, frame in ipairs(selectedPlayerFrames) do
        MacroUpdate(frame)
    end
end

local function SortType()
    if not CanMutateProtectedFrames() then
        MarkProtectedFrameRefreshPending()
        return
    end

    table.sort(selectedPlayerFrames, sortTypes[addon.db.profile.sortType])
    local tankCount = 0
    for i, frame in ipairs(selectedPlayerFrames) do
        if frame.role == "TANK" then
            tankCount = tankCount + 1
            frame:ClearAllPoints()
            local ebonMightCount = addon.db.profile.ebonmightProgressBarEnable and 20 or 0
            frame:SetPoint("TOP", selectedPlayerFrameContainer, "TOP", 0,
                ebonMightCount + (tankCount * addon.db.profile.buttonHeight))
        else
            frame:ClearAllPoints()
            frame:SetPoint("BOTTOM", selectedPlayerFrameContainer, "BOTTOM", 0,
                (i - tankCount) * -addon.db.profile.buttonHeight)
        end
    end
end

local function ApplyButtonHeight()
    if not CanMutateProtectedFrames() then
        MarkProtectedFrameRefreshPending()
        return
    end

    for _, frame in ipairs(selectedPlayerFrames) do
        frame:SetSize(PLAYER_FRAME_WIDTH, addon.db.profile.buttonHeight)
        RefreshPrescienceBarFill(frame)
    end
    SortType()
end

local function ApplySpellIconSize()
    if not CanMutateProtectedFrames() then
        MarkProtectedFrameRefreshPending()
        return
    end

    for _, frame in ipairs(selectedPlayerFrames) do
        if frame["buff"] then
            for k2, v2 in pairs(frame["buff"]) do
                if type(v2) == "table" and not string.match(k2, "Text$") then
                    v2:SetSize(addon.db.profile.spellIconSize, addon.db.profile.spellIconSize)
                end
            end
            RepositionBuffIcons(frame)
        end
    end
end

local function CreateSelectedPlayerFrame(playerName, class, PlayerRole, unitIndex, unittt, identityKey)
    if not CanMutateProtectedFrames() then
        MarkProtectedFrameRefreshPending()
        return
    end
    identityKey = identityKey or playerName
    local frameIndex = #selectedPlayerFrames + 1
    checkboxStates[identityKey] = true
    selectedPlayerFrames[frameIndex] = CreateFrame("Button", "EvokerAugPartyFrame" .. unittt, UIParent,
        BackdropTemplateMixin and "BackdropTemplate,SecureActionButtonTemplate,SecureUnitButtonTemplate" or
        "SecureActionButtonTemplate,SecureUnitButtonTemplate")
    selectedPlayerFrames[frameIndex]:SetSize(PLAYER_FRAME_WIDTH, addon.db.profile.buttonHeight)
    selectedPlayerFrames[frameIndex]["buff"] = {}
    selectedPlayerFrames[frameIndex]["buff"].xOffset = 0
    selectedPlayerFrames[frameIndex].playerName = playerName
    selectedPlayerFrames[frameIndex].identityKey = identityKey
    selectedPlayerFrames[frameIndex].class = class
    selectedPlayerFrames[frameIndex].role = PlayerRole
    selectedPlayerFrames[frameIndex].texture = selectedPlayerFrames[frameIndex]:CreateTexture()
    selectedPlayerFrames[frameIndex].unit = unitIndex
    selectedPlayerFrames[frameIndex]:RegisterForClicks("AnyDown")

    selectedPlayerFrames[frameIndex]:SetAttribute('unitName', playerName)
    selectedPlayerFrames[frameIndex]:SetAttribute('unitID', unitIndex)
    selectedPlayerFrames[frameIndex]:SetAttribute("unit", unitIndex);
    selectedPlayerFrames[frameIndex]:SetAttribute("type", "spell")
    selectedPlayerFrames[frameIndex]:SetAttribute("type2", "spell")

    MacroUpdate(selectedPlayerFrames[frameIndex])

    selectedPlayerFrames[frameIndex]:SetBackdrop({
        bgFile = [=[Interface\Tooltips\UI-Tooltip-Background]=],
        insets = { top = -1, left = -1, bottom = -1, right = -1 }
    })
    local classR, classG, classB = GetClassRGB(class)
    selectedPlayerFrames[frameIndex]:SetBackdropColor(0.08, 0.08, 0.08, 0.82)
    selectedPlayerFrames[frameIndex].texture:SetVertexColor(classR, classG, classB, 0.9)

    selectedPlayerFrames[frameIndex].texture:SetPoint('TOP', selectedPlayerFrames[frameIndex], 'TOP')
    selectedPlayerFrames[frameIndex].texture:SetPoint('BOTTOM', selectedPlayerFrames[frameIndex], 'BOTTOM')
    selectedPlayerFrames[frameIndex].texture:SetPoint('LEFT', selectedPlayerFrames[frameIndex], 'LEFT')
    selectedPlayerFrames[frameIndex].texture:SetTexture(addon.db.profile.backgroundTextTexture)
    CreateOffensiveMinorMarker(selectedPlayerFrames[frameIndex])
    ApplyPrescienceBarFill(selectedPlayerFrames[frameIndex], nil, nil)
    AddBuffIcons(selectedPlayerFrames[frameIndex], unitIndex)
    RefreshOffensiveBuffHighlight(selectedPlayerFrames[frameIndex], unitIndex)


    selectedPlayerFrames[frameIndex].playerNameText = selectedPlayerFrames[frameIndex]:CreateFontString(nil, "OVERLAY",
        "GameFontHighlight")
    selectedPlayerFrames[frameIndex].playerNameText:SetPoint("CENTER", selectedPlayerFrames[frameIndex], "CENTER", 0, 0)
    selectedPlayerFrames[frameIndex].playerNameText:SetText(playerName)
    selectedPlayerFrames[frameIndex].playerNameText:SetJustifyH("CENTER")
    selectedPlayerFrames[frameIndex].playerNameText:SetJustifyV("MIDDLE")
    CheckDistance(selectedPlayerFrames[frameIndex])

    SortType()

    if distanceTimer == nil then
        distanceTimer = C_Timer.NewTicker(1, UpdateDistance)
    end
end

local function GetPlayerFrameIndexByUnit(unit)
    for i, frame in ipairs(selectedPlayerFrames) do
        if frame.unit == unit then
            return i
        end
    end
    return nil
end

local function ReconcileTrackedAurasForUnit(unit)
    local frameIndex = GetPlayerFrameIndexByUnit(unit)
    if not frameIndex or not selectedPlayerFrames[frameIndex] then
        return
    end

    ClearBuffIcons(selectedPlayerFrames[frameIndex])
    AddBuffIcons(selectedPlayerFrames[frameIndex], unit)
    RefreshOffensiveBuffHighlight(selectedPlayerFrames[frameIndex], unit)
end

ReconcileTrackedAurasForAllSelectedUnits = function()
    for _, frame in ipairs(selectedPlayerFrames) do
        if frame.unit then
            ReconcileTrackedAurasForUnit(frame.unit)
        end
    end
end

RefreshOffensiveBuffHighlightsForAllSelectedUnits = function()
    for _, frame in ipairs(selectedPlayerFrames) do
        if frame.unit then
            RefreshOffensiveBuffHighlight(frame, frame.unit)
        end
    end
end

local function GetPlayerFrameIndexByIdentity(identityKey)
    if not identityKey then
        return nil
    end

    for i, frame in ipairs(selectedPlayerFrames) do
        if frame.identityKey == identityKey then
            return i
        end
    end
    return nil
end

local function IsPlayerFrameByIdentity(identityKey)
    return GetPlayerFrameIndexByIdentity(identityKey) ~= nil
end

local function DeleteSelectedPlayerFrame(identityKey, skipSort)
    if not CanMutateProtectedFrames() then
        MarkProtectedFrameRefreshPending()
        return
    end
    if not identityKey then
        return
    end

    local playerIndex = GetPlayerFrameIndexByIdentity(identityKey)
    if playerIndex and selectedPlayerFrames[playerIndex] then
        ClearBuffIcons(selectedPlayerFrames[playerIndex])
        ApplyOffensiveBuffVisualState(selectedPlayerFrames[playerIndex], OFFENSIVE_STATE_NONE)
        selectedPlayerFrames[playerIndex]:Hide()
        selectedPlayerFrames[playerIndex]:ClearAllPoints()
        selectedPlayerFrames[playerIndex]:SetParent(nil)
        table.remove(selectedPlayerFrames, playerIndex)
        checkboxStates[identityKey] = nil
        if not skipSort then
            SortType()
        end
    end

    if #selectedPlayerFrames == 0 then
        if distanceTimer then
            distanceTimer:Cancel()
            distanceTimer = nil
        end
    end
end

local function DeleteAllSelectedPlayerFrames()
    for i = #selectedPlayerFrames, 1, -1 do
        local frame = selectedPlayerFrames[i]
        DeleteSelectedPlayerFrame(frame.identityKey or frame.playerName, true)
    end
    SortType()
end

local function ApplyInstanceVisibilityPolicy()
    local _, instanceType = IsInInstance()
    if ShouldShowForInstanceType(instanceType) and IsRuntimeVisibilityAllowed() then
        return true
    end

    -- WHY: manual Show Frame off hides rows without clearing the user's selected/favorite frame state.
    if IsRuntimeContextAllowed() then
        HideAllSubFrames()
        return false
    end

    DeleteAllSelectedPlayerFrames()
    HideAllSubFrames()
    return false
end

local function AddFavoriteFrameForUnit(unitID)
    if not IsEligibleGroupUnit(unitID) then
        return
    end

    local identityKey, name = GetUnitIdentity(unitID)
    local class = GetUnitClassToken(unitID)
    if not identityKey or not name or not class then
        return
    end

    if not IsFavorite(identityKey) then
        return
    end

    local combatRole = addon.GetUnitCombatRole(unitID)

    if name and combatRole and not IsPlayerFrameByIdentity(identityKey) then
        class = strupper(string.gsub(class, "%s+", ""))
        CreateSelectedPlayerFrame(name, class, combatRole, unitID, unitID, identityKey)
    end
end

local function AddFrameFavorite()
    if not CanMutateProtectedFrames() then
        MarkProtectedFrameRefreshPending()
        return
    end

    --- Favorite Check
    if IsInRaid() then
        for i = 1, GetNumGroupMembers() do
            AddFavoriteFrameForUnit("raid" .. i)
        end
    elseif IsInGroup() then
        AddFavoriteFrameForUnit("player")
        for i = 1, GetNumSubgroupMembers() do
            AddFavoriteFrameForUnit("party" .. i)
        end
    end
end

local function FrameAutoFill()
    if not CanMutateProtectedFrames() then
        MarkProtectedFrameRefreshPending()
        return
    end
    local partyMembers = GetHomePartyInfos()
    if not IsInRaid() then
        for _, member in ipairs(partyMembers) do
            local memberInParty = false
            local unit = member.unit
            if member.role == "DPS" and unit ~= "player" then
                for _, frame in ipairs(selectedPlayerFrames) do
                    if frame.identityKey == member.identityKey then
                        memberInParty = true
                        break
                    end
                end
                if not memberInParty then
                    CreateSelectedPlayerFrame(member.name, member.class, member.role, unit, member.unit, member.identityKey)
                end
            end
        end
    end
end

local function GroupUpdate()
    if not CanMutateProtectedFrames() then
        MarkProtectedFrameRefreshPending()
        return
    end

    local partyMembers = GetHomePartyInfos()
    local needsSort = false

    for i = #selectedPlayerFrames, 1, -1 do
        local frame = selectedPlayerFrames[i]
        local identityKey = frame.identityKey or frame.playerName
        local memberInParty = false
        local unitCheckChanged = false
        local roleChanged = false
        local classChanged = false
        local memberName
        local memberClass
        local memberRole
        local unittt
        local unit

        for _, member in ipairs(partyMembers) do
            if member.identityKey == identityKey then
                memberInParty = true
                unit = member.unit
                unittt = unit
                memberName = member.name
                memberClass = member.class
                memberRole = member.role
                roleChanged = frame.role ~= member.role
                classChanged = frame.class ~= member.class
                if not unitCheckChanged then
                    if frame.unit ~= unit then
                        unitCheckChanged = true
                    end
                end
                break
            end
        end

        if memberInParty then
            if unitCheckChanged or roleChanged or classChanged then
                DeleteSelectedPlayerFrame(identityKey, true)
                CreateSelectedPlayerFrame(memberName, memberClass, memberRole, unit, unittt, identityKey)
                needsSort = true
            end
        else
            DeleteSelectedPlayerFrame(identityKey, true)
            needsSort = true
        end
    end

    if needsSort then
        SortType()
    end
end

local function SyncRuntimeFrameVisibility()
    if IsRuntimeVisibilityAllowed() then
        EnableAllFrame()
    else
        HideAllSubFrames()
    end
end

RefreshRuntimeFrames = function()
    if not selectedPlayerFrameContainer then
        return
    end

    if not ApplyInstanceVisibilityPolicy() then
        return
    end

    GroupUpdate()
    AddFrameFavorite()
    if addon.db.profile.autoFrameFill then
        FrameAutoFill()
    end
    SyncRuntimeFrameVisibility()
    RefreshBlizzardCompactFrameHighlightsForAllUnits()
end

local function GetClasses()
    local Augment = {}
    local augmentationSpells = addon.AllSpellList and addon.AllSpellList["Augmentation"]
    if not augmentationSpells then
        return Augment
    end

    for k, v in pairs(augmentationSpells) do
        local spell = C_Spell.GetSpellInfo(k)
        if spell and spell.name and spell.iconID then
            Augment[k] = { icon = spell.iconID, name = spell.name }
        end
    end

    return Augment
end

local function AddTrackedBuffOption(spellId, spellName, iconID, isCustom, order)
    if not EvokerAugOptions.args or not EvokerAugOptions.args.customSpells then
        return
    end

    EvokerAugOptions.args.customSpells.args.buffList.args[spellName .. "" .. spellId] = {
        order = order,
        type = 'toggle',
        name = spellName,
        imageCoords = { 0.07, 0.93, 0.07, 0.93 },
        image = iconID,
        arg = spellId,
        set = function(_, value)
            SetTrackedBuff(spellId, spellName, value, isCustom)
        end,
        get = function()
            return IsTrackedBuffEnabled(spellId)
        end,
    }
end

local function AddOffensiveBuffOption(spellID, definition, isCustom, order)
    if not EvokerAugOptions.args or not EvokerAugOptions.args.offensiveBuffs then
        return
    end

    spellID = GetCleanPositiveSpellID(spellID)
    if not spellID or type(definition) ~= "table" then
        return
    end

    local spell = C_Spell.GetSpellInfo(spellID)
    local spellName = spell and spell.name or definition.name or ("Spell " .. spellID)
    local iconID = spell and spell.iconID
    local optionKey = "offensive" .. spellID

    EvokerAugOptions.args.offensiveBuffs.args.offensiveBuffList.args[optionKey] = {
        order = order,
        type = 'group',
        name = spellName,
        inline = true,
        args = {
            enabled = {
                order = 1,
                type = 'toggle',
                name = spellName,
                imageCoords = { 0.07, 0.93, 0.07, 0.93 },
                image = iconID,
                set = function(_, value)
                    SetOffensiveBuffEnabled(spellID, value, isCustom)
                    AceConfigRegistry:NotifyChange(addonName)
                end,
                get = function()
                    return IsOffensiveBuffEnabled(spellID)
                end,
            },
            tier = {
                order = 2,
                type = 'select',
                name = "Tier",
                values = OFFENSIVE_TIER_LABELS,
                set = function(_, value)
                    SetOffensiveBuffTier(spellID, value)
                end,
                get = function()
                    local _, tier = GetOffensiveBuffDefinition(spellID)
                    return tier or OFFENSIVE_TIER_MINOR
                end,
            },
        },
    }

    if isCustom then
        EvokerAugOptions.args.offensiveBuffs.args.offensiveBuffList.args[optionKey].args.remove = {
            order = 3,
            type = 'execute',
            name = "Remove",
            func = function()
                SetOffensiveBuffEnabled(spellID, false, true)
                EvokerAugOptions.args.offensiveBuffs.args.offensiveBuffList.args[optionKey] = nil
                AceConfigRegistry:NotifyChange(addonName)
            end,
        }
    end
end

local function AddSavedCustomSpellOptions()
    EnsureTrackedBuffStateTables()
    for spellId, savedName in pairs(addon.db.profile.customBuffList) do
        local numericSpellID = tonumber(spellId)
        if numericSpellID and not IsCoreBuffOption(numericSpellID) then
            local spell = C_Spell.GetSpellInfo(numericSpellID)
            local spellName = spell and spell.name or savedName
            local iconID = spell and spell.iconID
            if spellName then
                AddTrackedBuffOption(numericSpellID, spellName, iconID, true, numericSpellID)
            end
        end
    end
end

local function AddSavedCustomOffensiveBuffOptions()
    EnsureOffensiveBuffStateTables()
    for spellID, definition in pairs(addon.db.profile.offensiveBuffs.custom) do
        local numericSpellID = GetCleanPositiveSpellID(spellID)
        if numericSpellID then
            AddOffensiveBuffOption(numericSpellID, definition, true, 100000 + numericSpellID)
        end
    end
end

local function SpellListAdd(spellId)
    if spellId then
        local Spell = C_Spell.GetSpellInfo(spellId)
        if Spell and Spell.name then
            SetTrackedBuff(spellId, Spell.name, true, true)
            AddTrackedBuffOption(spellId, Spell.name, Spell.iconID, true, spellId)
            AceConfigRegistry:NotifyChange(addonName)
        end
    end
end

local function OffensiveBuffListAdd(spellID)
    spellID = GetCleanPositiveSpellID(spellID)
    if spellID then
        local Spell = C_Spell.GetSpellInfo(spellID)
        if Spell and Spell.name then
            local definition = { name = Spell.name, tier = OFFENSIVE_TIER_MINOR }
            SetCustomOffensiveBuff(spellID, Spell.name, OFFENSIVE_TIER_MINOR)
            AddOffensiveBuffOption(spellID, definition, true, 100000 + spellID)
            AceConfigRegistry:NotifyChange(addonName)
        end
    end
end

local function GetOptions()
    local profiles = LibStub('AceDBOptions-3.0'):GetOptionsTable(addon.db)
    profiles.order = 600
    profiles.disabled = false
    local favList = NormalizeFavoriteList()
    SeedCustomBuffListFromBuffList()
    local orderNumber = 2
    EvokerAugOptions = {
        name = addonName,
        type = "group",
        childGroups = "tab",
        args = {
            home = {
                order = 1,
                name = "EvokerAug",
                type = "group",
                args = {
                    evokerAug = {
                        order = 0,
                        image = "Interface\\Addons\\EvokerAug\\Media\\augevoker-logo",
                        imageWidth = 64,
                        imageHeight = 64,
                        imageCoords = { 0, 1, 0, 1 },
                        type = "description",
                        name = "EvokerAug",
                        fontSize = "large",
                    },
                    pd1 = {
                        name = "\n\n\n", order = 1, type = "description",
                    },
                    version = {
                        name = "|cffffff00 Version |r |cff00ff00 " .. addon.Config["version"] .. "|r",
                        order = 2,
                        type = "description",
                    },
                    author = {
                        name = "|cffffff00 Author |r |cff00ff00  Xenknight |r",
                        order = 3,
                        type = "description",
                    },
                    discord = {
                        name = "|cffffff00 Discord |r |cff00ff00 https://discord.gg/D9jb6zwn3j |r",
                        order = 3,
                        type = "description",
                    },
                    discordcopy = {
                        type = "execute",
                        name = "Join the Discord",
                        order = 4,
                        func = function()
                            StaticPopup_Show(discordLinkDialog)
                            addon:OpenOptions()
                        end,
                    },
                    pd2 = {
                        name = "\n\n", order = 5, type = "description",
                    },
                    h1 = {
                        type = 'header',
                        name = 'Changelog',
                        order = 5,
                    },
                    changenlog = {
                        type = "group",
                        name = " ",
                        inline = true,
                        order = 6,
                        args = {
                            pd3 = {
                                name = "\n", order = 1, type = "description",
                            },
                            changelog = {
                                order = 1,
                                type = "description",
                                name = changelog,
                            },
                        },
                    },
                }
            },
            settings = {
                order = 2,
                name = "Settings",
                type = "group",
                args = {
                    h1 = {
                        type = 'header',
                        name = 'Settings',
                        order = 10,
                    },
                    sortType = {
                        order = 11,
                        type = 'select',
                        name = "Sort Type",
                        desc = "Choose which attribute to sort player frames by",
                        values = {
                            ["NAME"] = "Name",
                            ["CLASS"] = "Class",
                            ["ROLE"] = "Role",
                        },
                        get = function() return addon.db.profile.sortType end,
                        set = function(info, value)
                            addon.db.profile.sortType = value
                            SortType()
                        end,
                    },
                    l8 = {
                        type = 'description',
                        width = 0.15,
                        name = '',
                        order = 12,
                    },
                    buttontexture = {
                        order = 13,
                        type = 'select',
                        name = "Button Texture",
                        desc = "Change Texture",
                        values = AceGUIWidgetLSMlists.statusbar,
                        dialogControl = 'LSM30_Statusbar',
                        get = function() return addon.db.profile.backgroundTextTexture2 or "EvokerAug" end,
                        set = function(info, key)
                            addon.db.profile.backgroundTextTexture = AceGUIWidgetLSMlists.statusbar[key]
                            addon.db.profile.backgroundTextTexture2 = key
                            if addon.db.profile.backgroundTextTexture and #selectedPlayerFrames ~= 0 then
                                for i, frame in ipairs(selectedPlayerFrames) do
                                    frame.texture:SetTexture(addon.db.profile.backgroundTextTexture)
                                end
                            end
                        end
                    },

                    buttonHeight = {
                        type = 'range',
                        name = 'Frame Height',
                        desc = 'Set Frame height',
                        min = 20,
                        max = 40,
                        step = 1,
                        get = function() return addon.db.profile.buttonHeight end,
                        set = function(info, value)
                            addon.db.profile.buttonHeight = value
                            ApplyButtonHeight()
                        end,
                        order = 14,
                    },
                    l9 = {
                        type = 'description',
                        width = 0.15,
                        name = '',
                        order = 15,
                    },
                    IconbuttonHeight = {
                        type = 'range',
                        name = 'Icon Size',
                        desc = 'Set icon size',
                        min = 20,
                        max = 40,
                        step = 1,
                        get = function() return addon.db.profile.spellIconSize end,
                        set = function(info, value)
                            addon.db.profile.spellIconSize = value
                            ApplySpellIconSize()
                        end,
                        order = 16,
                    },
                    IconTextSize = {
                        type = 'range',
                        name = 'Timer Text Size',
                        desc = 'Set the size of the text in the icon',
                        min = 12,
                        max = 20,
                        step = 1,
                        get = function() return addon.db.profile.spellIconTextSize end,
                        set = function(info, value)
                            addon.db.profile.spellIconTextSize = value

                            for k, v in pairs(selectedPlayerFrames) do
                                if v["buff"] then
                                    for k2, v2 in pairs(selectedPlayerFrames[k]["buff"]) do
                                        if type(v2) == "table" and string.match(k2, "Text$") then
                                            v2:SetFont("Fonts\\ARIALN.TTF", addon.db.profile.spellIconTextSize, "OUTLINE")
                                        end
                                    end
                                end
                            end
                        end,
                        order = 16,
                    },
                    h3 = {
                        type = 'description',
                        name = '    ',
                        order = 17,
                        width = 3
                    },
                    unlockHeader = {
                        order = 18,
                        type = 'toggle',
                        name = "UnLock Frame",
                        desc = "Unlock the frame to move it",
                        get = function()
                            return
                                addon.db.profile.headerunlock
                        end,
                        set = function(info, value)
                            addon.db.profile.headerunlock = value
                        end,
                    },
                    frameHide = {
                        order = 19,
                        type = 'toggle',
                        name = "Show Frame",
                        desc = "Show or hide the frame",
                        get = function()
                            if not selectedPlayerFrameContainer then
                                return false
                            end
                            return selectedPlayerFrameContainer:IsShown()
                        end,
                        set = function(info, value)
                            addon.db.profile.enabled = value
                            if value then
                                RefreshRuntimeFrames()
                                EnableAllFrame()
                            else
                                HideAllSubFrames()
                            end
                        end,
                    },
                    autoFrame = {
                        order = 20,
                        type = 'toggle',
                        name = "Auto Frame Fill",
                        desc =
                        "When you enter the dungeon, it will automatically fill the frame and delete it when you exit.",
                        get = function()
                            return addon.db.profile.autoFrameFill
                        end,
                        set = function(info, value)
                            addon.db.profile.autoFrameFill = value
                            RefreshRuntimeFrames()
                        end,
                    },
                    raid = {
                        order = 21,
                        type = 'toggle',
                        name = "Show Raid",
                        desc = "Show Raid",
                        get = function()
                            return addon.db.profile.showRaid
                        end,
                        set = function(info, value)
                            addon.db.profile.showRaid = value
                            RefreshRuntimeFrames()
                        end,
                    },
                    mythic = {
                        order = 21,
                        type = 'toggle',
                        name = "Show Mythic+",
                        desc = "Show Mythic+",
                        get = function()
                            return addon.db.profile.showMythic
                        end,
                        set = function(info, value)
                            addon.db.profile.showMythic = value
                            RefreshRuntimeFrames()
                        end,
                    },
                    h5 = {
                        type = 'header',
                        name = 'Prescience Buff',
                        order = 22,
                    },
                    presciencebar = {
                        order = 23,
                        type = 'toggle',
                        name = "Prescience Bar",
                        desc = "When enabled for Prescience, the dynamic bar is shown; when disabled, it is hidden.",
                        get = function()
                            return
                                addon.db.profile.prescienceBarEnable
                        end,
                        set = function(info, value)
                            addon.db.profile.prescienceBarEnable = value
                            for _, frame in ipairs(selectedPlayerFrames) do
                                RefreshPrescienceBarFill(frame)
                            end
                        end,
                    },
                    prescienceSound = {
                        order = 24,
                        type = 'select',
                        name = "Prescience Sound",
                        desc = "The sound to be heard when Buff is finished",
                        values = AceGUIWidgetLSMlists.sound,
                        dialogControl = 'LSM30_Sound',
                        get = function() return addon.db.profile.prescienceBuffSoundName or "None" end,
                        set = function(info, key)
                            addon.db.profile.prescienceBuffSoundFile = AceGUIWidgetLSMlists.sound[key]
                            addon.db.profile.prescienceBuffSoundName = key
                        end
                    },
                    prescienceThinTrackerHeader = {
                        type = 'header',
                        name = 'Prescience Thin Tracker',
                        order = 25,
                    },
                    prescienceThinTrackerEnabled = {
                        order = 26,
                        type = 'toggle',
                        name = "Enable Thin Tracker",
                        desc = "Show a separate compact Prescience-only tracker for party DPS.",
                        get = function()
                            return addon.db.profile.prescienceThinTracker.enabled
                        end,
                        set = function(info, value)
                            addon.db.profile.prescienceThinTracker.enabled = value
                            RefreshPrescienceThinTrackerRoster()
                            UpdatePrescienceThinTrackerVisibility()
                        end,
                    },
                    prescienceThinTrackerLocked = {
                        order = 27,
                        type = 'toggle',
                        name = "Lock Thin Tracker",
                        desc = "Lock the compact Prescience tracker position.",
                        get = function()
                            return addon.db.profile.prescienceThinTracker.locked
                        end,
                        set = function(info, value)
                            addon.db.profile.prescienceThinTracker.locked = value
                            UpdatePrescienceThinTrackerVisibility()
                        end,
                    },
                    prescienceThinTrackerTestMode = {
                        order = 28,
                        type = 'toggle',
                        name = "Test Thin Tracker",
                        desc = "Show simulated DPS Prescience bars so you can position and tune the tracker.",
                        get = function()
                            return prescienceThinTrackerTestMode
                        end,
                        set = function(info, value)
                            SetPrescienceThinTrackerTestMode(value)
                        end,
                    },
                    prescienceThinTrackerWidth = {
                        order = 29,
                        type = 'range',
                        name = "Thin Tracker Width",
                        desc = "Set the compact Prescience tracker row width.",
                        min = 100,
                        max = 260,
                        step = 1,
                        get = function()
                            return addon.db.profile.prescienceThinTracker.rowWidth
                        end,
                        set = function(info, value)
                            addon.db.profile.prescienceThinTracker.rowWidth = value
                            LayoutPrescienceThinTrackerRows()
                            UpdatePrescienceThinTrackerRows()
                            UpdatePrescienceThinTrackerVisibility()
                        end,
                    },
                    prescienceThinTrackerHeight = {
                        order = 30,
                        type = 'range',
                        name = "Thin Tracker Height",
                        desc = "Set the compact Prescience tracker row height.",
                        min = 8,
                        max = 22,
                        step = 1,
                        get = function()
                            return addon.db.profile.prescienceThinTracker.rowHeight
                        end,
                        set = function(info, value)
                            addon.db.profile.prescienceThinTracker.rowHeight = value
                            LayoutPrescienceThinTrackerRows()
                            UpdatePrescienceThinTrackerRows()
                            UpdatePrescienceThinTrackerVisibility()
                        end,
                    },
                    prescienceThinTrackerSpacing = {
                        order = 31,
                        type = 'range',
                        name = "Thin Tracker Spacing",
                        desc = "Set the gap between compact Prescience tracker rows.",
                        min = 0,
                        max = 10,
                        step = 1,
                        get = function()
                            return addon.db.profile.prescienceThinTracker.rowSpacing
                        end,
                        set = function(info, value)
                            addon.db.profile.prescienceThinTracker.rowSpacing = value
                            LayoutPrescienceThinTrackerRows()
                            UpdatePrescienceThinTrackerVisibility()
                        end,
                    },
                    ebonmight = {
                        order = 32,
                        type = 'toggle',
                        name = "Ebon Might Progress Bar",
                        desc = "When enabled for Ebon Might, the dynamic bar is shown; when disabled, it is hidden.",
                        get = function()
                            return
                                addon.db.profile.ebonmightProgressBarEnable
                        end,
                        set = function(info, value)
                            addon.db.profile.ebonmightProgressBarEnable = value
                            CreateProgressBar()
                        end,
                    },
                    h2 = {
                        type = 'header',
                        name = 'Macros',
                        order = 40,
                    },
                    allowModifierAlt = {
                        name = "Alt Key usage",
                        type = "toggle",
                        order = 41,
                        get = function(info) return addon.db.profile.macro.AltClick end,
                        set = function(_, value)
                            addon.db.profile.macro.AltClick = value
                            UpdatePlayerFrame()
                        end,
                        width = 0.8,
                    },
                    l1 = {
                        type = 'description',
                        width = 0.3,
                        name = '',
                        order = 42,
                    },
                    allowModifierShift = {
                        name = "Shift Key usage",
                        type = "toggle",
                        order = 43,
                        get = function(info) return addon.db.profile.macro.ShiftClick end,
                        set = function(_, value)
                            addon.db.profile.macro.ShiftClick = value
                            UpdatePlayerFrame()
                        end,
                        width = 0.8,
                    },
                    allowModifierCtrl = {
                        name = "Ctrl Key usage",
                        type = "toggle",
                        order = 44,
                        get = function(info) return addon.db.profile.macro.CtrlClick end,
                        set = function(_, value)
                            addon.db.profile.macro.CtrlClick = value
                            UpdatePlayerFrame()
                        end,
                        width = 0.8,
                    },
                    l2 = {
                        type = 'description',
                        width = 0.3,
                        name = '',
                        order = 45,
                    },
                    rightModifier = {
                        name = "Right Key Usage",
                        type = "toggle",
                        order = 46,
                        get = function(info) return addon.db.profile.macro.RightClick end,
                        set = function(_, value)
                            addon.db.profile.macro.RightClick = value
                            UpdatePlayerFrame()
                        end,
                        width = 0.8,
                    },

                    tankClickSpell = {
                        name = "Tank click",
                        type = "select",
                        values = addon.db.profile.charSpell,
                        order = 47,
                        desc = "Select the spell to be used when left click key is pressed",
                        set = function(info, value)
                            addon.db.profile.tankMacros.LeftSpell = value
                            UpdatePlayerFrame()
                        end,
                        get = function() return addon.db.profile.tankMacros.LeftSpell end,
                    },
                    l3 = {
                        type = 'description',
                        width = 0.15,
                        name = '',
                        order = 48,
                    },
                    dpsClickSpell = {
                        name = "DPS click",
                        type = "select",
                        values = addon.db.profile.charSpell,
                        order = 49,
                        desc = "Select the spell to be used when left click key is pressed",
                        set = function(info, value)
                            addon.db.profile.dpsMacros.LeftSpell = value
                            UpdatePlayerFrame()
                        end,
                        get = function() return addon.db.profile.dpsMacros.LeftSpell end,
                    },

                    RightttankClickSpell = {
                        name = "Right Tank click",
                        type = "select",
                        values = addon.db.profile.charSpell,
                        order = 50,
                        desc = "Select the spell to be used when right click key is pressed",
                        set = function(info, value)
                            addon.db.profile.tankMacros.RightSpell = value
                            UpdatePlayerFrame()
                        end,
                        get = function() return addon.db.profile.tankMacros.RightSpell end,
                    },
                    l4 = {
                        type = 'description',
                        width = 0.15,
                        name = '',
                        order = 51,
                    },
                    RighttdpsClickSpell = {
                        name = "Right DPS click",
                        type = "select",
                        values = addon.db.profile.charSpell,
                        order = 52,
                        desc = "Select the spell to be used when right click key is pressed",
                        set = function(info, value)
                            addon.db.profile.dpsMacros.RightSpell = value
                            UpdatePlayerFrame()
                        end,
                        get = function() return addon.db.profile.dpsMacros.RightSpell end,
                    },


                    ShifttankClickSpell = {
                        name = "Shift Tank click",
                        type = "select",
                        values = addon.db.profile.charSpell,
                        order = 53,
                        desc = "Select the spell to be used when shift click key is pressed",
                        set = function(info, value)
                            addon.db.profile.tankMacros.ShiftSpell = value
                            UpdatePlayerFrame()
                        end,
                        get = function() return addon.db.profile.tankMacros.ShiftSpell end,
                    },
                    l5 = {
                        type = 'description',
                        width = 0.15,
                        name = '',
                        order = 54,
                    },
                    ShiftdpsClickSpell = {
                        name = "Shift DPS click",
                        type = "select",
                        values = addon.db.profile.charSpell,
                        order = 55,
                        desc = "Select the spell to be used when shift click key is pressed",
                        set = function(info, value)
                            addon.db.profile.dpsMacros.ShiftSpell = value
                            UpdatePlayerFrame()
                        end,
                        get = function() return addon.db.profile.dpsMacros.ShiftSpell end,
                    },


                    CtrlttankClickSpell = {
                        name = "Ctrl Tank click",
                        type = "select",
                        values = addon.db.profile.charSpell,
                        order = 56,
                        desc = "Select the spell to be used when ctrl click key is pressed",
                        set = function(info, value)
                            addon.db.profile.tankMacros.CtrlSpell = value
                            UpdatePlayerFrame()
                        end,
                        get = function() return addon.db.profile.tankMacros.CtrlSpell end,
                    },
                    l6 = {
                        type = 'description',
                        width = 0.15,
                        name = '',
                        order = 57,
                    },
                    CtrltdpsClickSpell = {
                        name = "Ctrl DPS click",
                        type = "select",
                        values = addon.db.profile.charSpell,
                        order = 58,
                        desc = "Select the spell to be used when ctrl click key is pressed",
                        set = function(info, value)
                            addon.db.profile.dpsMacros.CtrlSpell = value
                            UpdatePlayerFrame()
                        end,
                        get = function() return addon.db.profile.dpsMacros.CtrlSpell end,
                    },

                    AltttankClickSpell = {
                        name = "Alt Tank click",
                        type = "select",
                        values = addon.db.profile.charSpell,
                        order = 59,
                        desc = "Select the spell to be used when alt click key is pressed",
                        set = function(info, value)
                            addon.db.profile.tankMacros.AltSpell = value
                            UpdatePlayerFrame()
                        end,
                        get = function() return addon.db.profile.tankMacros.AltSpell end,
                    },
                    l7 = {
                        type = 'description',
                        width = 0.15,
                        name = '',
                        order = 60,
                    },
                    AlttdpsClickSpell = {
                        name = "Alt DPS click",
                        type = "select",
                        values = addon.db.profile.charSpell,
                        order = 61,
                        desc = "Select the spell to be used when alt click key is pressed",
                        set = function(info, value)
                            addon.db.profile.dpsMacros.AltSpell = value
                            UpdatePlayerFrame()
                        end,
                        get = function() return addon.db.profile.dpsMacros.AltSpell end,
                    },

                },
            },
            favPlayerList = {
                order = 3,
                name = "Favorite Player List",
                type = "group",
                args = {
                    h1 = {
                        type = 'header',
                        name = 'Favorite Player List',
                        order = 1,
                    },
                },
            },
            customSpells = {
                order = 5,
                name = "Spell",
                type = "group",
                args = {
                    spellId_info = {
                        order = 1,
                        type = "description",
                        name = "You can add any spells you want and see these spells on the frame",
                    },
                    spellId = {
                        name = "Spell ID",
                        type = "input",
                        order = 2,
                        desc = "Spell ID",
                        validate = function(_, value)
                            local num = tonumber(value)
                            if num then
                                return true
                            else
                                return "Please enter a number"
                            end
                        end,
                        set = function(_, state)
                            local spellId = tonumber(state)
                            SpellListAdd(spellId)
                        end,
                    },
                    buffList = {
                        type = 'group',
                        name = 'Spell List',
                        inline = true,
                        order = 3,
                        args = {
                            h1 = {
                                type = 'header',
                                name = 'Buff List',
                                order = 1,
                            },
                        },
                    },
                    OmniCDSupport = {
                        order = 4,
                        type = 'toggle',
                        name = "OmniCD Support",
                        desc = "If you have OmniCD installed, you can see the cooldowns of the spells you have added.",
                        get = function() return addon.db.profile.omniCDSupport end,
                        set = function(_, value)
                            addon.db.profile.omniCDSupport = value
                            local loaded = C_AddOns and C_AddOns.IsAddOnLoaded and C_AddOns.IsAddOnLoaded("OmniCD")
                            local state = C_AddOns and C_AddOns.GetAddOnEnableState and
                                C_AddOns.GetAddOnEnableState("OmniCD", UnitGUID("player"))
                            if loaded or state == 2 then
                                ReloadUI()
                            end
                        end,
                    }
                },
            },
            offensiveBuffs = {
                order = 6,
                name = "Offensive Buffs",
                type = "group",
                args = {
                    offensiveBuffInfo = {
                        order = 1,
                        type = "description",
                        name = "Highlight party members when visible offensive buffs are active.",
                    },
                    enabled = {
                        order = 2,
                        type = 'toggle',
                        name = "Enable Offensive Highlights",
                        get = function()
                            EnsureOffensiveBuffStateTables()
                            return addon.db.profile.offensiveBuffs.enabled
                        end,
                        set = function(_, value)
                            EnsureOffensiveBuffStateTables()
                            addon.db.profile.offensiveBuffs.enabled = value
                            RefreshOffensiveBuffHighlightsForAllSelectedUnits()
                            RefreshBlizzardCompactFrameHighlightsForAllUnits()
                            RefreshPrescienceThinTrackerOffensiveStateForUnit()
                        end,
                    },
                    blizzardFrames = {
                        order = 3,
                        type = 'group',
                        inline = true,
                        name = "Blizzard Frames",
                        args = {
                            enabled = {
                                order = 1,
                                type = 'toggle',
                                name = "Highlight Blizzard Frames",
                                get = function()
                                    EnsureBlizzardFrameHighlightState()
                                    return addon.db.profile.blizzardFrameHighlights.enabled
                                end,
                                set = function(_, value)
                                    EnsureBlizzardFrameHighlightState()
                                    addon.db.profile.blizzardFrameHighlights.enabled = value
                                    RefreshBlizzardCompactFrameHighlightsForAllUnits()
                                end,
                            },
                            showRaid = {
                                order = 2,
                                type = 'toggle',
                                name = "Include Raid Groups",
                                desc = "Also highlight Blizzard raid frames outside 5-player groups.",
                                get = function()
                                    EnsureBlizzardFrameHighlightState()
                                    return addon.db.profile.blizzardFrameHighlights.showRaid
                                end,
                                set = function(_, value)
                                    EnsureBlizzardFrameHighlightState()
                                    addon.db.profile.blizzardFrameHighlights.showRaid = value
                                    RefreshBlizzardCompactFrameHighlightsForAllUnits()
                                end,
                            },
                        },
                    },
                    spellId = {
                        order = 4,
                        type = "input",
                        name = "Custom Offensive Spell ID",
                        desc = "Add a visible helpful aura spell ID to highlight as a minor offensive buff.",
                        validate = function(_, value)
                            local num = tonumber(value)
                            if num then
                                return true
                            else
                                return "Please enter a number"
                            end
                        end,
                        set = function(_, state)
                            OffensiveBuffListAdd(tonumber(state))
                        end,
                    },
                    offensiveBuffList = {
                        type = 'group',
                        name = 'Offensive Buff List',
                        inline = true,
                        order = 4,
                        args = {
                            h1 = {
                                type = 'header',
                                name = 'Offensive Buff List',
                                order = 1,
                            },
                        },
                    },
                },
            },
            profiles = profiles,
        },
    }

    for k, v in pairs(GetClasses()) do
        AddTrackedBuffOption(k, v.name, v.icon, false, orderNumber)
        orderNumber = orderNumber + 1
    end
    AddSavedCustomSpellOptions()
    for spellID, definition in pairs(addon.OffensiveBuffList or {}) do
        AddOffensiveBuffOption(spellID, definition, false, spellID)
    end
    AddSavedCustomOffensiveBuffOptions()

    orderNumber = 2
    for k, v in pairs(favList) do
        EvokerAugOptions.args.favPlayerList.args[v .. "" .. k] = {
            order = orderNumber,
            type = 'toggle',
            name = v,
            arg = k,
            set = function(_, value)
                if value then
                    AddFavoriteName(v)
                else
                    RemoveFavoriteName(v)
                end
                AceConfigRegistry:NotifyChange(addonName)
            end,
            get = function()
                return IsFavoriteName(v)
            end,
        }

        orderNumber = orderNumber + 1
    end

    return EvokerAugOptions
end

local function PopulateCharSpellDefaults()
    addon.db.profile.charSpell = addon.db.profile.charSpell or {}
    local spells = addon.SpellList and addon.SpellList["EVOKER"] and addon.SpellList["EVOKER"]["AUGMENTATION"]
    if not spells then
        return
    end

    for _, spell in ipairs(spells) do
        local spellInfo = C_Spell.GetSpellInfo(spell.spellID)
        local spellName = spellInfo and spellInfo.name or spell.name
        addon.db.profile.charSpell[spell.spellID] = spellName
    end
end

local function RegisterOmniCDFrameData()
    if addon.db.profile.omniCDSupport then
        local ofunc = OmniCD and OmniCD.AddUnitFrameData
        if ofunc then
            ofunc("EvokerAug", "EvokerAugPartyFrame", "unit", 1)
        end
    end
end

local function ClearSelectedFrameState()
    for i = #selectedPlayerFrames, 1, -1 do
        local frame = selectedPlayerFrames[i]
        ClearBuffIcons(frame)
        ApplyOffensiveBuffVisualState(frame, OFFENSIVE_STATE_NONE)
        frame:Hide()
        frame:ClearAllPoints()
        frame:SetParent(nil)
        selectedPlayerFrames[i] = nil
    end
    checkboxStates = {}
    selectedPlayerFrames = {}
    DeadorGhostData = {}
    if distanceTimer then
        distanceTimer:Cancel()
        distanceTimer = nil
    end
end

local function ApplyActiveProfile()
    NormalizeProfileShape()
    EnsureTrackedBuffStateTables()
    SeedCustomBuffListFromBuffList()
    NormalizeFavoriteList()
    PopulateCharSpellDefaults()
    AceConfigRegistry:NotifyChange(addonName)
    RegisterOmniCDFrameData()

    if not selectedPlayerFrameContainer then
        return
    end

    if not CanMutateProtectedFrames() then
        pendingActiveProfileApply = true
        MarkProtectedFrameRefreshPending()
        return
    end

    pendingActiveProfileApply = false
    pendingProtectedFrameRefresh = false
    isCombatButton = false
    if addonNameText then
        addonNameText:SetText(addonName)
    end

    ClearSelectedFrameState()
    LoadPosition(selectedPlayerFrameContainer)
    CreatePrescienceThinTrackerFrame()
    LoadPositionFromTable(prescienceThinTrackerFrame, addon.db.profile.prescienceThinTracker.position)

    selectedPlayerFrameContainer:RegisterEvent("PLAYER_ENTERING_WORLD")

    ApplyButtonHeight()
    ApplySpellIconSize()
    CreateProgressBar()
    RefreshPrescienceThinTrackerRoster()
    UpdatePrescienceThinTrackerVisibility()
    if ApplyInstanceVisibilityPolicy() then
        AddFrameFavorite()
        if addon.db.profile.autoFrameFill then
            FrameAutoFill()
        end
        RefreshBlizzardCompactFrameHighlightsForAllUnits()
    end
end

function addon:OnInitialize()
    self.db = LibStub('AceDB-3.0'):New(addonName .. "DB", self.DefaultProfile, true)
    NormalizeProfileShape()
    SeedCustomBuffListFromBuffList()
    self.db.RegisterCallback(self, "OnProfileReset", "Reconfigure")
    self.db.RegisterCallback(self, "OnProfileChanged", "Reconfigure")
    self.db.RegisterCallback(self, "OnProfileCopied", "Reconfigure")
    self:RegisterChatCommand("aug", function(cmd)
        addon:OpenOptions(strsplit(' ', cmd or ""))
    end, true)
    createMiniMapIcon()

    StaticPopupDialogs[discordLinkDialog] = {
        text = "CTRL+C to copy",
        button1 = "Done",
        hasEditBox = true,
        OnShow = function(dialog)
            local function HidePopup()
                dialog:Hide();
            end
            dialog.editBox:SetScript("OnEscapePressed", HidePopup)
            dialog.editBox:SetScript("OnKeyUp", function(_, key)
                if IsControlKeyDown() and key == "C" then
                    HidePopup()
                end
            end)
            dialog.editBox:SetText("https://discord.gg/D9jb6zwn3j")
            dialog.editBox:SetFocus()
            dialog.editBox:HighlightText()
        end,
        OnHide = function() addon:OpenOptions() end,
        editBoxWidth = 230,
        timeout = 0,
        hideOnEscape = true,
        whileDead = true,
    }
end

function addon:OnEnable() -- PLAYER_LOGIN
    local lib = LibStub("LibSharedMedia-3.0")
    lib:Register(lib.MediaType.STATUSBAR, "EvokerAug", [[Interface\AddOns\EvokerAug\Media\bar]])

    selectedPlayerFrameContainer = CreateFrame("Frame", "EvokerAug", UIParent,
        BackdropTemplateMixin and "BackdropTemplate")
    selectedPlayerFrameContainer:SetSize(200, 20)
    selectedPlayerFrameContainer:SetMovable(true)
    LoadPosition(selectedPlayerFrameContainer)
    CreatePrescienceThinTrackerFrame()
    selectedPlayerFrameContainer:EnableMouse(true)
    selectedPlayerFrameContainer:RegisterForDrag("LeftButton")
    selectedPlayerFrameContainer:RegisterEvent("GROUP_ROSTER_UPDATE")
    selectedPlayerFrameContainer:RegisterEvent("PLAYER_REGEN_ENABLED")
    selectedPlayerFrameContainer:RegisterEvent("PLAYER_REGEN_DISABLED")
    selectedPlayerFrameContainer:RegisterEvent("UNIT_AURA")
    selectedPlayerFrameContainer:RegisterEvent("UNIT_CONNECTION")
    selectedPlayerFrameContainer:RegisterEvent("UNIT_FLAGS")
    selectedPlayerFrameContainer:RegisterEvent("UNIT_SPELLCAST_SUCCEEDED")
    selectedPlayerFrameContainer:RegisterEvent("INSPECT_READY")
    selectedPlayerFrameContainer:RegisterEvent("PLAYER_SPECIALIZATION_CHANGED")
    selectedPlayerFrameContainer:RegisterEvent("PLAYER_LOGOUT")
    selectedPlayerFrameContainer:RegisterEvent("PLAYER_ENTERING_WORLD")

    if hooksecurefunc and CompactUnitFrame_UpdateAll then
        hooksecurefunc("CompactUnitFrame_UpdateAll", function(frame)
            UpdateBlizzardCompactFrameHighlight(frame)
        end)
    end

    local addonNameTexture = selectedPlayerFrameContainer:CreateTexture(nil, "OVERLAY")
    addonNameTexture:SetAllPoints()
    addonNameTexture:SetTexture("Interface\\Addons\\EvokerAug\\Media\\bar")
    addonNameTexture:SetVertexColor(0.24, 0.24, 0.24, 1.0)

    addonNameText = selectedPlayerFrameContainer:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    addonNameText:SetPoint("CENTER", selectedPlayerFrameContainer, "CENTER", 0, 0)
    addonNameText:SetText(addonName)
    addonNameText:SetJustifyH("CENTER")
    addonNameText:SetJustifyV("MIDDLE")

    selectedPlayerFrameContainer:SetScript("OnDragStart", function(sel)
        if self.db.profile.headerunlock and CanMutateProtectedFrames() then
            sel.evokerAugIsMoving = true
            sel:StartMoving()
        end
    end)

    selectedPlayerFrameContainer:SetScript("OnDragStop", function(sel)
        if sel.evokerAugIsMoving then
            sel.evokerAugIsMoving = nil
            sel:StopMovingOrSizing()
            if CanMutateProtectedFrames() then
                SavePosition(selectedPlayerFrameContainer)
            end
        end
    end)

    selectedPlayerFrameContainer:SetScript("OnEvent", function(self, event, unit, info, spellID)
        if event == "GROUP_ROSTER_UPDATE" then
            local _, instanceType = IsInInstance()
            RefreshRuntimeFrames()
            RefreshPrescienceThinTrackerRoster()
            SchedulePrescienceThinTrackerRosterRefresh(instanceContextGeneration, instanceType)
        elseif event == "UNIT_CONNECTION" then
            RefreshRuntimeFrames()
            RefreshPrescienceThinTrackerRoster()
        elseif event == "INSPECT_READY" then
            local guid = unit
            if addon.pendingRoleInspectGUIDs[guid] then
                addon.pendingRoleInspectGUIDs[guid] = nil
                if addon.roleInspectActiveGUID == guid then
                    addon.roleInspectActiveGUID = nil
                end
                if ClearInspectPlayer then
                    ClearInspectPlayer()
                end
                RefreshRuntimeFrames()
                RefreshPrescienceThinTrackerRoster()
                UpdatePrescienceThinTrackerVisibility()
                addon.DrainRoleInspectQueue()
            end
        elseif event == "PLAYER_REGEN_DISABLED" then
            combatLockdown = true
            if prescienceThinTrackerTestMode then
                SetPrescienceThinTrackerTestMode(false)
            end
        elseif event == "PLAYER_LOGOUT" then
            SavePosition(selectedPlayerFrameContainer)
            SavePositionToTable(prescienceThinTrackerFrame, addon.db.profile.prescienceThinTracker.position)
        elseif event == "PLAYER_REGEN_ENABLED" then
            combatLockdown = false
            if pendingActiveProfileApply then
                ApplyActiveProfile()
            end
            if isCombatButton or pendingProtectedFrameRefresh then
                addonNameText:SetText(addonName)
                isCombatButton = false
                pendingProtectedFrameRefresh = false
                if not ApplyInstanceVisibilityPolicy() then
                    return
                end
                GroupUpdate()
                AddFrameFavorite()
                if addon.db.profile.autoFrameFill then
                    FrameAutoFill()
                end
                ApplyButtonHeight()
                ApplySpellIconSize()
                CreateProgressBar()
            end
            if blizzardCompactFrameRefreshPending then
                blizzardCompactFrameRefreshPending = false
                RefreshBlizzardCompactFrameHighlightsForAllUnits()
            end
            RefreshPrescienceThinTrackerRoster()
            UpdatePrescienceThinTrackerVisibility()
        elseif event == "PLAYER_ENTERING_WORLD" then
            instanceContextGeneration = instanceContextGeneration + 1
            local generation = instanceContextGeneration
            local _, instanceType = IsInInstance()
            SchedulePrescienceThinTrackerRosterRefresh(generation, instanceType)
            if addon.db.profile.autoFrameFill then
                if instanceType == "party" then
                    C_Timer.After(4.5, function()
                        if not addon.db.profile.autoFrameFill or not IsCurrentInstanceContext(generation, "party") then
                            return
                        end
                        local size = GetNumGroupMembers()
                        if size > 0 then
                            RefreshRuntimeFrames()
                        end
                    end)
                elseif instanceType == "none" then
                    C_Timer.After(4.5, function()
                        if not addon.db.profile.autoFrameFill or not IsCurrentInstanceContext(generation, "none") then
                            return
                        end
                        DeleteAllSelectedPlayerFrames()
                    end)
                end
            end
            ApplyInstanceVisibilityPolicy()
            RefreshBlizzardCompactFrameHighlightsForAllUnits()
            RefreshPrescienceThinTrackerRoster()
            UpdatePrescienceThinTrackerVisibility()
        elseif event == "PLAYER_SPECIALIZATION_CHANGED" then
            if unit == "player" then
                local currentSpec = GetSpecialization()
                if currentSpec then
                    if currentSpec ~= 3 then
                        HideAllSubFrames()
                        ClearBlizzardCompactFrameHighlights()
                        UpdatePrescienceThinTrackerVisibility()
                    else
                        RefreshRuntimeFrames()
                        SyncRuntimeFrameVisibility()
                        RefreshPrescienceThinTrackerRoster()
                    end
                end
            end
        elseif event == "UNIT_AURA" then
            if info == nil or info.isFullUpdate then
                ReconcileTrackedAurasForUnit(unit)
                RefreshBlizzardCompactFrameHighlightsForUnit(unit)
                RefreshPrescienceThinTrackerAuras(unit)
                return
            end
            local frameIndex = GetPlayerFrameIndexByUnit(unit)
            if info.addedAuras and #info.addedAuras > 0 and selectedPlayerFrames[frameIndex] then
                for _, v in ipairs(info.addedAuras) do
                    if IsTrackedAuraData(v) then
                        AddBuffIcon(selectedPlayerFrames[frameIndex], v.auraInstanceID, v.expirationTime, v.icon,
                            v.duration, v.spellId)
                    end
                end
            end
            if info.updatedAuraInstanceIDs and #info.updatedAuraInstanceIDs > 0 and selectedPlayerFrames[frameIndex] then
                for _, v in ipairs(info.updatedAuraInstanceIDs) do
                    local aura = C_UnitAuras.GetAuraDataByAuraInstanceID(unit, v)
                    if IsTrackedAuraData(aura) then
                        AddBuffIcon(selectedPlayerFrames[frameIndex], aura.auraInstanceID, aura.expirationTime,
                            aura.icon, aura.duration, aura.spellId)
                    end
                end
            end
            if info.removedAuraInstanceIDs and #info.removedAuraInstanceIDs > 0 and selectedPlayerFrames[frameIndex] then
                for _, instance in ipairs(info.removedAuraInstanceIDs) do
                    RemoveBuffIcon(selectedPlayerFrames[frameIndex], instance)
                end
            end
            if selectedPlayerFrames[frameIndex] then
                RefreshOffensiveBuffHighlight(selectedPlayerFrames[frameIndex], unit)
            end
            RefreshBlizzardCompactFrameHighlightsForUnit(unit)
            RefreshPrescienceThinTrackerAuras(unit)
        elseif event == "UNIT_SPELLCAST_SUCCEEDED" then
            RecordOffensiveCastWindow(unit, spellID)
        elseif event == "UNIT_FLAGS" then
            if unit ~= "player" then
                local isDeadOrGhost = UnitIsDeadOrGhost(unit)
                if isDeadOrGhost then
                    local frameIndex = GetPlayerFrameIndexByUnit(unit)
                    if selectedPlayerFrames[frameIndex] then
                        local frame = selectedPlayerFrames[frameIndex]
                        DeadorGhostData[unit] = true
                        frame:SetBackdropColor(0.5, 0.5, 0.5, 0.5)
                        frame.texture:SetVertexColor(0.5, 0.5, 0.5, 0.5)
                        frame.playerNameText:SetText(frame.playerName .. " (Dead)")
                    end
                elseif DeadorGhostData[unit] then
                    local frameIndex = GetPlayerFrameIndexByUnit(unit)
                    if selectedPlayerFrames[frameIndex] then
                        local frame = selectedPlayerFrames[frameIndex]
                        local clasxs = frame.class
                        local classR, classG, classB = GetClassRGB(clasxs)
                        frame:SetBackdropColor(0.08, 0.08, 0.08, 0.82)
                        frame.texture:SetVertexColor(classR, classG, classB, 0.9)
                        frame.playerNameText:SetText(frame.playerName)
                        DeadorGhostData[unit] = nil
                    end
                end
            end
        end
    end)

    selectedPlayerFrameContainer:SetScript("OnMouseUp", function(sel, button)
        if not CanMutateProtectedFrames() then
            return
        end

        if button == "RightButton" and MenuUtil and MenuUtil.CreateContextMenu then
            MenuUtil.CreateContextMenu(UIParent, RightMenu)
        elseif button == "LeftButton" then
            addon:OpenOptions()
        end
    end)

    PopulateCharSpellDefaults()
    RegisterOmniCDFrameData()


    -----------------------------
    if addon.db.profile.ebonmightProgressBarEnable then
        CreateProgressBar()
    end

    local class = GetUnitClassToken("player")
    if class ~= "EVOKER" then
        HideAllSubFrames()
    else
        local currentSpec = GetSpecialization()
        if currentSpec then
            if currentSpec ~= 3 then
                HideAllSubFrames()
            else
                AddFrameFavorite()
            end
        end

        AddItemsWithMenu()
    end

    RefreshPrescienceThinTrackerRoster()
    UpdatePrescienceThinTrackerVisibility()
end

function addon:Reconfigure()
    ApplyActiveProfile()
end

local function AddHomePartyInfo(partyMembers, unit)
    if not IsEligibleGroupUnit(unit) then
        return
    end

    local identityKey, name = GetUnitIdentity(unit)
    local class = GetUnitClassToken(unit)
    if not identityKey or not name or not class then
        return
    end

    local combatRole = addon.GetUnitCombatRole(unit)

    if name and combatRole then
        table.insert(partyMembers,
            { name = name, identityKey = identityKey, class = strupper(string.gsub(class, "%s+", "")), role = combatRole, unit = unit })
    end
end

GetHomePartyInfos = function()
    local partyMembers = {}
    if IsInRaid() then
        for i = 1, GetNumGroupMembers() do
            AddHomePartyInfo(partyMembers, "raid" .. i)
        end
    elseif IsInGroup() then
        AddHomePartyInfo(partyMembers, "player")
        for i = 1, GetNumSubgroupMembers() do
            AddHomePartyInfo(partyMembers, "party" .. i)
        end
    else
        local identityKey, name = GetUnitIdentity("player")
        local class = GetUnitClassToken("player")
        local combatRole = addon.GetUnitCombatRole("player")
        if identityKey and name and class and combatRole then
            table.insert(partyMembers,
                { name = name, identityKey = identityKey, class = strupper(string.gsub(class, "%s+", "")), role = combatRole, unit = "player" })
        end
    end

    return partyMembers
end

RightMenu = function(owner, MenuDesc)
    MenuDesc:SetTag("AUGEVOKER_RIGHT_MENU");
    local PartyList = {}
    local partyMembers = GetHomePartyInfos()

    for i, member in ipairs(partyMembers) do
        table.insert(PartyList, {
            text = member.name .. ' (' .. member.role .. ')',
            checked = function() return checkboxStates[member.identityKey] end,
            func = function(xxxx, arg1, arg2)
                if checkboxStates[member.identityKey] then
                    DeleteSelectedPlayerFrame(member.identityKey)
                else
                    local unit = member.unit
                    CreateSelectedPlayerFrame(member.name, member.class, member.role, unit, member.unit, member.identityKey)
                end
            end,
            index = i,
        })
    end

    MenuDesc:CreateTitle(addonName)
    local party = MenuDesc:CreateButton("Party members")
    for i, v in ipairs(PartyList) do
        party:CreateCheckbox(v.text, v.checked, v.func, v.index)
    end
    MenuDesc:CreateButton('Auto Fill (M+)', function() FrameAutoFill() end)
    MenuDesc:CreateButton('Clear Frame', function()
        DeleteAllSelectedPlayerFrames()
    end)
    MenuDesc:CreateDivider()
    MenuDesc:CreateTitle('Setting')
    MenuDesc:CreateButton('Setting panel', function() addon:OpenOptions() end)

    local function IsSelected()
        return addon.db.profile.headerunlock;
    end
    local function SetSelected()
        addon.db.profile.headerunlock = not addon.db.profile.headerunlock
    end
    MenuDesc:CreateCheckbox('Unlock Frame', IsSelected, SetSelected)
end

LibStub("AceConfig-3.0"):RegisterOptionsTable(addonName, GetOptions)
function addon:OpenOptions(...)
    if CanMutateProtectedFrames() then
        AceConfigDialog:SetDefaultSize(addonName, 460, 750)
        if select('#', ...) > 0 then
            AceConfigDialog:Open(addonName)
            AceConfigDialog:SelectGroup(addonName, ...)
        elseif not AceConfigDialog:Close(addonName) then
            AceConfigDialog:Open(addonName)
        end
    end
end

HideAllSubFrames = function()
    if not CanMutateProtectedFrames() then
        MarkProtectedFrameRefreshPending()
        return
    end

    for i, frame in pairs(selectedPlayerFrames) do
        frame:Hide()
    end
    if selectedPlayerFrameContainer then
        selectedPlayerFrameContainer:Hide()
    end
    if addonNameText then
        addonNameText:Hide()
    end
    if progressBar then
        progressBar:Hide()
        progressBar.text:Hide()
    end
end

EnableAllFrame = function()
    if not CanMutateProtectedFrames() then
        MarkProtectedFrameRefreshPending()
        return
    end
    if not IsRuntimeVisibilityAllowed() then
        return
    end

    for i, frame in pairs(selectedPlayerFrames) do
        frame:Show()
    end
    if selectedPlayerFrameContainer then
        selectedPlayerFrameContainer:Show()
    end
    if addonNameText then
        addonNameText:Show()
    end
    SyncProgressBarVisibility()
end

IsFavorite = function(name)
    return IsFavoriteName(name)
end

local function MenuHandler(owner, rootDescription, contextData)
    if not contextData or not contextData.name then
        return
    end

    local name = contextData.name
    if contextData.server and contextData.server ~= "" then
        name = name .. "-" .. contextData.server
    elseif not string.find(name, "-") then
        name = name .. "-" .. GetRealmName()
    end
    rootDescription:CreateDivider();
    rootDescription:CreateTitle("EvokerAug");
    local text = IsFavoriteName(name) and "Remove from Favorite" or "Add to favorite"
    rootDescription:CreateButton(text, function()
        if not IsFavoriteName(name) then
            AddFavoriteName(name)
        else
            RemoveFavoriteName(name)
        end
    end)
end

AddItemsWithMenu = function()
    if not Menu or not Menu.ModifyMenu then return end

    local menuTags = {
        ["MENU_UNIT_PLAYER"] = true,
        ["MENU_UNIT_ENEMY_PLAYER"] = true,
        ["MENU_UNIT_PARTY"] = true,
        ["MENU_UNIT_RAID_PLAYER"] = true,
        ["MENU_UNIT_FRIEND"] = true,
        ["MENU_UNIT_COMMUNITIES_GUILD_MEMBER"] = true,
        ["MENU_UNIT_COMMUNITIES_MEMBER"] = true,
    }

    for tag, enabled in pairs(menuTags) do
        if enabled then
            Menu.ModifyMenu(tag, MenuHandler)
        end
    end
end
