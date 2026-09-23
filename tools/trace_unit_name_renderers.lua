-- Read-only tracer for every invocation of the stock 8x8/16x16 text renderer.
-- It never writes RAM, ROM, VRAM, registers, or savestates.

-- Lua's narrow-path io.open cannot reliably create files below a Korean
-- Windows user-name path, so use the ASCII-only public directory.
local output_path = [[C:\Users\Public\unit-name-renderer-trace.log]]
local output = assert(io.open(output_path, "w"))
local seen = {}

local function reg(name)
  return emu.getregister("M68K " .. name) & 0x00FFFFFF
end

local function bytes_at(address, count)
  local parts = {}
  for index = 0, count - 1 do
    local ok, value = pcall(memory.read_u8, (address + index) & 0x00FFFFFF)
    parts[#parts + 1] = ok and string.format("%02X", value) or "??"
  end
  return table.concat(parts, " ")
end

local function trace(label)
  local a0 = reg("A0")
  local a1 = reg("A1")
  local a7 = reg("A7")
  local d7 = emu.getregister("M68K D7") & 0xFFFFFFFF
  local ok, return_address = pcall(memory.read_u32_be, a7)
  return_address = ok and (return_address & 0x00FFFFFF) or 0xFFFFFF
  local key = string.format("%s:%06X:%06X:%08X:%s", label, return_address, a0, d7, bytes_at(a0, 8))
  if seen[key] then return end
  seen[key] = true
  local line = string.format(
    "frame=%d entry=%s caller=%06X a0=%06X a1=%06X d7=%08X bytes=%s\n",
    emu.framecount(), label, return_address, a0, a1, d7, bytes_at(a0, 8))
  output:write(line)
  output:flush()
  console.log(line)
end

event.onmemoryexecute(function() trace("8124") end, 0x008124, "unit_text_8124")
event.onmemoryexecute(function() trace("8162") end, 0x008162, "unit_text_8162")
event.onmemoryexecute(function() trace("816A") end, 0x00816A, "unit_text_816A")

-- Expansion-only unit-name proof paths. These callbacks are inert on the
-- approved v076 ROM and let the v078 run prove which private wrapper/renderer
-- actually executes before a later stock draw can reuse the same VRAM tiles.
event.onmemoryexecute(function() trace("1D0100-wrapper-evolution") end, 0x1D0100, "unit_private_evolution")
event.onmemoryexecute(function() trace("1D0140-wrapper-map") end, 0x1D0140, "unit_private_map")
event.onmemoryexecute(function() trace("1D0160-wrapper-list") end, 0x1D0160, "unit_private_list")
event.onmemoryexecute(function() trace("1D003E-render8") end, 0x1D003E, "unit_private_render8")
event.onmemoryexecute(function() trace("1D0120-wrapper-16") end, 0x1D0120, "unit_private_16")
event.onmemoryexecute(function() trace("1D0046-render16") end, 0x1D0046, "unit_private_render16")

event.onexit(function()
  output:flush()
  output:close()
end, "close_unit_name_trace")

local automation_start = emu.framecount()
output:write(string.format("trace-start frame=%d\n", automation_start))
local ok_pad, pad = pcall(joypad.get)
if ok_pad then
  local names = {}
  for name, _ in pairs(pad) do names[#names + 1] = name end
  table.sort(names)
  output:write("joypad-keys=" .. table.concat(names, ",") .. "\n")
end
output:flush()
pcall(client.unpause)
while true do
  -- A single harmless cursor pulse makes a loaded map redraw its HUD, which
  -- gives the tracer deterministic coverage without changing game data.
  local elapsed = emu.framecount() - automation_start
  local buttons = {}
  -- QuickSave2 is parked on headquarters.  Move three hexes upward to the
  -- visible tank and select it so the map unit-name renderer is exercised.
  if (elapsed >= 20 and elapsed <= 22)
      or (elapsed >= 30 and elapsed <= 32)
      or (elapsed >= 40 and elapsed <= 42) then
    buttons["P1 Up"] = true
  elseif elapsed >= 60 and elapsed <= 62 then
    buttons["P1 A"] = true
  end
  pcall(joypad.set, buttons)
  if elapsed == 60 then
    output:write(string.format("heartbeat frame=%d\n", emu.framecount()))
    output:flush()
  end
  if elapsed == 100 then
    pcall(client.screenshot, [[C:\Users\Public\unit-name-runtime.png]])
  end
  emu.frameadvance()
end
