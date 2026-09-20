# Project 05: campaign briefing reconstruction

## Scope

- Target: the 44 Japanese campaign/scenario briefing records shown after a
  scenario starts.
- Base ROM: approved v071 (`f26445c`).
- Japanese Rev A is the sole structural and translation source.  The English
  ROM may only be consulted to identify a renderer or pointer.
- Main-title assets and every 8x8 bank are frozen during this phase.

## Original format audit

- Offset table: `0x023E5E`, 44 big-endian 16-bit offsets.
- Compressed stream: starts at `0x023EB6`; LZSS output is 13,957 bytes.
- Record rows use a one-byte control followed by variable-width glyph codes.
- Bit 7 denotes a page break; bit 6 denotes the last row of a record; the low
  six bits store `glyph_count - 1`.
- The original data contains 415 row/control records: 405 text rows and 10
  page breaks.
- Scenario 43 deliberately shares the scenario-13 record at offset `0x0931`.
  The two approved Korean translations are identical and must remain shared.

The machine-readable audit is generated at
`evidence/static/campaign-briefing-audit.json` by
`tools/audit_campaign_briefings.py`.

## Safety rules

1. Do not edit the original compressed stream, original 16x16 bank, title
   graphics, fixed-record bank, or 8x8 bank in place.
2. Relocate the rebuilt compressed stream to a declared, non-overlapping
   expansion range and change only its verified pointer operand.
3. Preserve all 44 original offsets unless a later proof requires rebuilding
   the table.  In particular, preserve the 13/43 shared offset.
4. Preserve each record's original count of text rows, page-break controls,
   and final-row control.  Short Korean records receive blank padded rows.
5. Reject any translation with more rows than the corresponding Japanese
   record, any row over the renderer width, any undeclared prefix mutation, or
   any overlap with an established expansion range.
6. Verify by decompressing the finished ROM and decoding every rebuilt record.
7. Runtime acceptance begins with scenario 0 and must cover page transitions,
   exit to the map, and a second entry before broader scenario sampling.

## Approved source material

The existing 44-entry Korean translation file was imported as text source only
and is now tracked locally at:

`assets/campaign-briefings-ko.json`

No executable code, ROM image, font hook, or global renderer patch from the
old rebuild is inherited.
