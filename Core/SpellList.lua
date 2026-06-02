local addonName = ...
local addon = LibStub("AceAddon-3.0"):GetAddon(addonName)

addon.SpellList = {
    ["EVOKER"] = {
        ["AUGMENTATION"] = {
            { ["name"] = "Rescue", ["iconID"] = 4622460, ["spellID"] = 370665,  },
            { ["name"] = "Cauterizing Flame", ["iconID"] = 4630446, ["spellID"] = 374251 },
            { ["name"] = "Verdant Embrace", ["iconID"] = 4622471, ["spellID"] = 360995 },
            { ["name"] = "Expunge", ["iconID"] = 4630445, ["spellID"] = 365585 },
            { ["name"] = "Blistering Scales", ["iconID"] = 5199621, ["spellID"] = 360827 },
            { ["name"] = "Ebon Might", ["iconID"] = 5061347, ["spellID"] = 395152 },
            { ["name"] = "Prescience", ["iconID"] = 5199639, ["spellID"] = 409311 },
            { ["name"] = "Living Flame", ["iconID"] = 4622464, ["spellID"] = 361469 },
            { ["name"] = "Emerald Blossom", ["iconID"] = 4622457, ["spellID"] = 355913 },
            { ["name"] = "Return", ["iconID"] = 4622472, ["spellID"] = 361227 },
            { ["name"] = "Source of Magic", ["iconID"] = 4630412, ["spellID"] = 369459 },
            { ["name"] = "Sense Power", ["iconID"] = 132160, ["spellID"] = 361022 },
        }
    }
}

addon.AllSpellList = {
    ["Augmentation"] = {
        [363916] = "Obsidian Scales",
        [369459] = "Source of Magic",
        [395296] = "Ebon Might",
        [395152] = "Ebon Might",
        [410089] = "Prescience",
        [374227] = "Zephyr",
        [381748] = "Blessing of the Bronze",
        [360827] = "Blistering Scales",
        [406732] = "Spatial Paradox",
        [374348] = "Renewing Blaze",
        [403631] = "Breath of Eons",
        [370553] = "Tip the Scales",
        [361022] = "Sense Power"
    },
}

addon.OffensiveBuffList = {
    [51271] = { name = "Pillar of Frost", class = "DEATHKNIGHT", tier = "major" },
    [47568] = { name = "Empower Rune Weapon", class = "DEATHKNIGHT", tier = "major" },
    [63560] = { name = "Dark Transformation", class = "DEATHKNIGHT", tier = "major" },
    [207289] = { name = "Unholy Assault", class = "DEATHKNIGHT", tier = "major" },
    [49206] = { name = "Summon Gargoyle", class = "DEATHKNIGHT", tier = "major" },
    [42650] = { name = "Army of the Dead", class = "DEATHKNIGHT", tier = "major" },
    [1249658] = { name = "Breath of Sindragosa", class = "DEATHKNIGHT", tier = "major" },

    [162264] = { name = "Metamorphosis", class = "DEMONHUNTER", tier = "major" },
    [1217607] = { name = "Void Metamorphosis", class = "DEMONHUNTER", tier = "major" },
    [1256301] = { name = "Voidfall", class = "DEMONHUNTER", tier = "minor" },
    [452412] = { name = "Student of Suffering", class = "DEMONHUNTER", tier = "minor" },
    [258860] = { name = "Essence Break", class = "DEMONHUNTER", tier = "minor" },

    [102543] = { name = "Incarnation: Avatar of Ashamane", class = "DRUID", tier = "major" },
    [102560] = { name = "Incarnation: Chosen of Elune", class = "DRUID", tier = "major" },
    [194223] = { name = "Celestial Alignment", class = "DRUID", tier = "major" },
    [106951] = { name = "Berserk", class = "DRUID", tier = "major" },
    [391528] = { name = "Convoke the Spirits", class = "DRUID", tier = "major" },
    [5217] = { name = "Tiger's Fury", class = "DRUID", tier = "minor" },

    [375087] = { name = "Dragonrage", class = "EVOKER", tier = "major" },
    [403631] = { name = "Breath of Eons", class = "EVOKER", tier = "major" },

    [19574] = { name = "Bestial Wrath", class = "HUNTER", tier = "major" },
    [288613] = { name = "Trueshot", class = "HUNTER", tier = "major" },
    [360952] = { name = "Coordinated Assault", class = "HUNTER", tier = "major" },
    [360966] = { name = "Spearhead", class = "HUNTER", tier = "major" },
    [359844] = { name = "Call of the Wild", class = "HUNTER", tier = "major" },
    [466904] = { name = "Harrier's Cry", class = "HUNTER", tier = "major" },
    [321530] = { name = "Bloodshed", class = "HUNTER", tier = "minor" },

    [190319] = { name = "Combustion", class = "MAGE", tier = "major" },
    [12472] = { name = "Icy Veins", class = "MAGE", tier = "major" },
    [365362] = { name = "Arcane Surge", class = "MAGE", tier = "major" },
    [198144] = { name = "Ice Form", class = "MAGE", tier = "major" },
    [205025] = { name = "Presence of Mind", class = "MAGE", tier = "minor" },

    [137639] = { name = "Storm, Earth, and Fire", class = "MONK", tier = "major" },
    [123904] = { name = "Invoke Xuen, the White Tiger", class = "MONK", tier = "major" },
    [387184] = { name = "Weapons of Order", class = "MONK", tier = "major" },
    [113656] = { name = "Fists of Fury", class = "MONK", tier = "minor" },

    [31884] = { name = "Avenging Wrath", class = "PALADIN", tier = "major" },
    [231895] = { name = "Crusade", class = "PALADIN", tier = "major" },
    [389539] = { name = "Sentinel", class = "PALADIN", tier = "major" },
    [388007] = { name = "Blessing of Summer", class = "PALADIN", tier = "minor" },

    [10060] = { name = "Power Infusion", class = "PRIEST", tier = "major" },
    [228260] = { name = "Void Eruption", class = "PRIEST", tier = "major" },
    [391109] = { name = "Dark Ascension", class = "PRIEST", tier = "major" },
    [263165] = { name = "Void Torrent", class = "PRIEST", tier = "minor" },

    [13750] = { name = "Adrenaline Rush", class = "ROGUE", tier = "major" },
    [121471] = { name = "Shadow Blades", class = "ROGUE", tier = "major" },
    [185422] = { name = "Shadow Dance", class = "ROGUE", tier = "major" },
    [212283] = { name = "Symbols of Death", class = "ROGUE", tier = "major" },
    [315508] = { name = "Roll the Bones", class = "ROGUE", tier = "minor" },
    [381989] = { name = "Keep It Rolling", class = "ROGUE", tier = "minor" },

    [1219480] = { name = "Ascendance", class = "SHAMAN", tier = "major" },
    [114051] = { name = "Ascendance", class = "SHAMAN", tier = "major" },
    [191634] = { name = "Stormkeeper", class = "SHAMAN", tier = "major" },
    [384352] = { name = "Doom Winds", class = "SHAMAN", tier = "major" },
    [333957] = { name = "Feral Spirit", class = "SHAMAN", tier = "major" },

    [265273] = { name = "Summon Demonic Tyrant", class = "WARLOCK", tier = "major" },
    [1122] = { name = "Summon Infernal", class = "WARLOCK", tier = "major" },
    [205180] = { name = "Summon Darkglare", class = "WARLOCK", tier = "major" },
    [442726] = { name = "Malevolence", class = "WARLOCK", tier = "major" },
    [267171] = { name = "Demonic Strength", class = "WARLOCK", tier = "minor" },

    [107574] = { name = "Avatar", class = "WARRIOR", tier = "major" },
    [1719] = { name = "Recklessness", class = "WARRIOR", tier = "major" },
    [227847] = { name = "Bladestorm", class = "WARRIOR", tier = "major" },
}
