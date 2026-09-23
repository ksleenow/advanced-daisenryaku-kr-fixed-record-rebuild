-- Read-only deterministic screenshot helper for a loaded BizHawk savestate.
pcall(client.unpause)
for _ = 1, 20 do emu.frameadvance() end
pcall(client.screenshot, [[C:\Users\Public\unit-name-runtime.png]])
while true do emu.frameadvance() end
