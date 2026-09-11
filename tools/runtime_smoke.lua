-- Read-only BizHawk smoke-test helper.
-- Usage: EmuHawk.exe --lua=tools/runtime_smoke.lua ROM

for _ = 1, 120 do
  emu.frameadvance()
end

for slot = 1, 3 do
  local state_path = string.format(
    [[R:\work\BizHawk-2.11.1\Genesis\State\advanced-daisenryaku-kr.Genplus-gx.QuickSave%d.State]],
    slot)
  local capture_path = string.format([[R:\work\v017-runtime-state%d.png]], slot)
  local ok = savestate.load(state_path, true)
  console.log("runtime_smoke state" .. slot .. "_load=" .. tostring(ok))
  for _ = 1, 30 do
    emu.frameadvance()
  end
  client.screenshot(capture_path)
  console.log("runtime_smoke capture=" .. capture_path)
end
client.pause()
