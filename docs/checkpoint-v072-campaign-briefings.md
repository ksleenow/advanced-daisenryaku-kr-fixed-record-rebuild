# Checkpoint v072: campaign briefing records

## Result

- Output: `out/project-05-campaign-briefings-v072.md`
- Size: 2 MiB
- SHA-256: `B0CE232CF9E847352C09CB95109C9C44371A06A13181B9474F09343F25EAFB42`
- Mega Drive checksum: `0x84D8`

## Preserved structure

- All 44 Japanese scenario offsets are preserved.
- All 415 original row/control records are preserved: 405 text rows and 10
  page-break controls.
- Scenario 43 continues to share scenario 13's record at offset `0x0931`.
- No Korean row exceeds the 20-glyph renderer width.
- Short translations are blank-padded inside the existing row topology; no
  record is allowed to grow beyond its original decompressed capacity.

## Relocation

The original compressed stream at `0x023EB6` is not modified. The rebuilt
stream is stored at `0x140000`, and only the verified pointer operand at
`0x00230E` is redirected. The builder immediately decompresses and compares
the finished stream and every decoded record before accepting the ROM.

Relative to approved v071, the only changes below 1 MiB are the checksum word
and the three changed bytes of the briefing-stream pointer. Title assets and
all 8x8 banks remain untouched.

## Verification

- `tools/audit_campaign_briefings.py`: 44 records, zero row-count or width
  violations.
- Builder round-trip: packed 15,704 bytes, unpacked 13,957 bytes, exact match.
- Existing runtime smoke states: map and development screens still render.
- Campaign briefing entry remains a manual acceptance item because BizHawk's
  Lua controller injection did not drive this title's menu reliably. Do not
  treat an automated load-screen capture as briefing evidence.
