# Checkpoint v073: pre-game country name

## Result

- Output: `out/project-05-campaign-briefings-v073.md`
- Size: 2 MiB
- SHA-256: `DCF8C4EA649C6C3A54CD1921D06EF3FEEB92A9A6B0D4688A98A19EC5EAF1141D`
- Mega Drive checksum: `0x60AF`

## Change

- The pre-game campaign-information country name now renders as `독일제국`.
- The four Korean 16x16 cells occupy the original eight-byte display field;
  no RAM copy length, record stride, or following weather/date field changed.
- The full 81-entry Japanese faction table was cloned from `0x0233F1` to
  `0x149000`. Only faction ID 1 was changed, and the verified table pointer at
  `0x0065C8` was redirected to the clone.
- Every cloned record retains its original nine-byte structure: eight display
  bytes followed by `0x07`.

## Preserved scope

- The approved v072 campaign briefing stream, all 44 offsets, and its
  row/page-control topology are unchanged.
- The original faction table is untouched.
- The 8x8 font bank remains byte-identical to the approved source clone.
- Main-title assets remain frozen.

## Runtime handoff

The ROM was launched in BizHawk 2.11.1 at normal speed on the left monitor for
manual confirmation of the pre-game information screen.
