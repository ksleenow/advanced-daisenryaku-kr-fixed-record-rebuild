# Unit-name dual-font fixed-record plan

## Invariant

- The unit record begins at `0x02B368`, has a stride of `0x22`, and reserves
  exactly eight bytes for the displayed name.
- The same eight bytes are consumed by the map/HUD 8x8 path and the unit
  performance-screen 16x16 path.
- In the isolated gameplay codebook one visible glyph occupies one byte.
  Unused bytes in the eight-byte field remain stock blank code `0x14`.
- No record may be expanded, contracted, or allowed to overwrite byte 8.

## Translation audit

`tools/audit_unit_names.py` generates:

- `out/unit-name-fixed8-audit.json`
- `out/unit-name-fixed8-audit.csv`
- `out/unit-name-over-8-review.csv`

An over-eight-byte candidate is never written to a ROM. It must first be
reviewed and shortened explicitly.

## Renderer safety gate

The global 8x8 bank is shared by unrelated UI, focus-in/focus-out redraws,
and map restoration. Reassigning a global kana slot for a missing Korean
syllable can therefore repair one unit name while corrupting another screen.

For that reason, a translated name is classified as
`font_isolation_required` whenever it needs a syllable that is not already
identical in both approved shared banks. Such names are withheld until both
unit-name call paths have dedicated, matching codebooks. This specifically
prevents repeating the earlier full-screen VRAM corruption.

## 8x8 renderer failure and verified fix

The first proof ROM translated only record 623 but redirected every 8x8 unit
name call to the private Korean font.  Untouched Japanese records therefore
used their original byte values against the unrelated private codebook.  The
visible result looked like decimal strings or broken glyphs on the map, while
the one translated evolution-table entry happened to look correct.

Runtime tracing proved the map path itself was not missing: `$C8B0` reached
the private wrapper and `$1D003E` renderer.  The bad input was an untranslated
record (for example record 658 at `$030ACC`) being interpreted as private font
codes.  The production fix has two parts:

1. every audited unit record is encoded with one shared private codebook; and
2. a dispatcher at `$1D0200` selects the private renderer only for the two
   audited record ranges (`560..563`, `608..668`).  Every other record is sent
   back to the stock `$8162` renderer.

This address-range guard must remain in place when more unit names are added.
Extend its ranges (or replace it with a generated lookup) rather than globally
redirecting all names.  The same fixed eight-byte record is shared by the map,
evolution list, and other 8x8 views; the 16x16 performance view uses the same
record through its separate private 16x16 renderer.

The first requested name, `39식보병`, occupies five bytes and receives three
blank bytes. Its `식` glyph currently requires the isolated dual-font path;
the record must not be patched alone.
