-- Automated attract-demo validation for v069.
-- Captures enough frames to cover credits, title, and the complete 1919-1939
-- chronology, then restores normal speed before closing BizHawk.
local out = "C:/Users/이광선/Documents/Codex/2026-07-20/apr/advanced-daisenryaku-kr-fixed-record-rebuild/evidence/runtime/demo-timeline-v069"
client.speedmode(6400)
for frame = 0, 12000 do
    if frame % 60 == 0 then
        client.screenshot(string.format("%s/frame_%05d.png", out, frame))
    end
    emu.frameadvance()
end
client.speedmode(100)
client.exit()
