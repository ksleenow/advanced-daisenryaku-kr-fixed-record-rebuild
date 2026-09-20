local out = "C:/Users/이광선/Documents/Codex/2026-07-20/apr/advanced-daisenryaku-kr-fixed-record-rebuild/evidence/runtime/demo-opening-v068"
client.speedmode(6400)
for frame = 0, 2100 do
    if frame % 60 == 0 then
        client.screenshot(string.format("%s/frame_%05d.png", out, frame))
    end
    emu.frameadvance()
end
client.exit()
