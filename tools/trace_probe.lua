local f = assert(io.open([[C:\Users\Public\unit-trace-probe.txt]], "w"))
f:write("started\n")
f:close()
while true do emu.frameadvance() end
