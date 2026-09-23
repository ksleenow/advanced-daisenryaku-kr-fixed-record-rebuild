local path = [[C:\Users\Public\pregame-country-trace.log]]
local out = assert(io.open(path, "w"))
local seen = {}

local function reg(name)
  return emu.getregister("M68K " .. name) & 0x00FFFFFF
end

local function bytes(address, before, count)
  local t = {}
  for i = -before, count - before - 1 do
    local ok, value = pcall(memory.read_u8, (address + i) & 0x00FFFFFF)
    t[#t + 1] = ok and string.format("%02X", value) or "??"
  end
  return table.concat(t, " ")
end

local function trace(label)
  local a0, a1, a7 = reg("A0"), reg("A1"), reg("A7")
  local ok, caller = pcall(memory.read_u32_be, a7)
  caller = ok and (caller & 0x00FFFFFF) or 0xFFFFFF
  local sample = bytes(a0, 10, 32)
  local key = string.format("%s:%06X:%06X:%s", label, caller, a0, sample)
  if seen[key] then return end
  seen[key] = true
  local line = string.format("frame=%d entry=%s caller=%06X a0=%06X a1=%06X around=%s\n",
    emu.framecount(), label, caller, a0, a1, sample)
  out:write(line); out:flush(); console.log(line)
end

event.onmemoryexecute(function() trace("hook") end, 0x149400, "pregame_country_hook")
event.onexit(function() out:flush(); out:close() end, "close_pregame_trace")
pcall(client.unpause)
while true do emu.frameadvance() end
