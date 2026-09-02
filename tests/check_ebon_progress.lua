local file = assert(io.open("Core/EvokerAug.lua", "r"))
local source = file:read("*a")
file:close()
local first = assert(source:find("-- Ebon Might Proggres Bar", 1, true))
local last = assert(source:find("---- Player Buffs Icon -----", first, true))
local chunk = source:sub(first, last - 1)
local env = setmetatable({}, { __index = _G })
local reads, now, aura = 0, 100, { expirationTime = 120, duration = 20 }
local secret = {}
local function frame()
    return setmetatable({ shown = true, scripts = {} }, { __index = {
        IsShown = function(self) return self.shown end,
        Show = function(self) self.shown = true end,
        Hide = function(self) self.shown = false end,
        SetScript = function(self, key, fn) self.scripts[key] = fn end,
        SetValue = function(self, value) self.value = value end,
        CreateFontString = function() return frame() end,
        SetSize = function() end, SetPoint = function() end,
        SetMinMaxValues = function() end, SetStatusBarTexture = function() end,
        SetStatusBarColor = function() end, SetText = function() end,
    } })
end
env.addon = { db = { profile = { ebonmightProgressBarEnable = true } } }
env.selectedPlayerFrameContainer = frame()
env.CanMutateProtectedFrames = function() return true end
env.MarkProtectedFrameRefreshPending = function() error("unexpected protected mutation") end
env.CreateFrame = frame
env.GetTime = function() return now end
env.IsCleanPositiveNumber = function(value)
    return value ~= secret and type(value) == "number" and value > 0
end
env.FindFirstAuraBySpellIDs = function() reads = reads + 1; return aura end
local loader = assert(loadstring(chunk .. "\nreturn CreateProgressBar, SyncProgressBarVisibility"))
setfenv(loader, env)
local create, sync = loader()
create()
local tick = assert(env.selectedPlayerFrameContainer.scripts.OnUpdate)
for _ = 1, 144 do tick() end
assert(reads == 1, "stable aura must be read once, not every frame; reads=" .. reads)
assert(env.progressBar.value == 100)
now = 110
tick()
assert(env.progressBar.value == 50, "cached timing still animates each frame")
aura = { expirationTime = 140, duration = 30 }
env.progressBar.auraDirty = true
tick()
assert(reads == 2 and env.progressBar.value == 100, "dirty aura extension refreshes")
aura = nil
env.progressBar.auraDirty = true
tick()
assert(env.progressBar.value == 0, "aura removal clears the bar")
for _ = 1, 144 do tick() end
assert(reads == 3, "missing aura must not cause continuous polling")
aura = { expirationTime = secret, duration = 20 }
env.progressBar.auraDirty = true
tick()
assert(env.progressBar.value == 0, "secret timing never reaches arithmetic")
for _, invalid in ipairs({ math.huge, 0, -1 }) do
    aura = { expirationTime = 120, duration = invalid }
    env.progressBar.auraDirty = true
    tick()
    assert(env.progressBar.value == 0, "invalid timing is rejected")
end
aura = { expirationTime = 120, duration = 20 }
sync()
tick()
assert(env.progressBar.value == 50, "show resamples previously unreadable timing")
now = 121
tick()
assert(env.progressBar.value == 0, "expiry clears without an aura event")
env.addon.db.profile.ebonmightProgressBarEnable = false
create()
assert(env.selectedPlayerFrameContainer.scripts.OnUpdate == nil, "disabled bar has no ticker")
env.addon.db.profile.ebonmightProgressBarEnable = true
aura = { expirationTime = 141, duration = 20 }
create()
assert(env.selectedPlayerFrameContainer.scripts.OnUpdate, "reenabling restores the ticker")
env.selectedPlayerFrameContainer.scripts.OnUpdate()
assert(env.progressBar.value == 100, "reenabling reads current aura timing")
print("Ebon progress lifecycle and aura read budget passed")
