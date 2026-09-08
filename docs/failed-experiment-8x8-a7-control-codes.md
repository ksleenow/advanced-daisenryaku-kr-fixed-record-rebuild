# Failed experiment: direct 8x8 codes A7-AA

## Symptom

The v004/v005 candidates stopped when entering Standard Scenario.

## Proven delta

- Parent: approved v003, SHA-256 `ABDC2109AC7AEC9A04A95CE1D1B7DB7E987F14BCC6000A2CDD0BDC46C6EC31F2`
- Candidate v005 changed only checksum bytes, four 8x8 glyph slots, and two exact 8-byte armament records.
- No record grew or moved.

## Root cause

Codes `A7-FF` are not safe ordinary single-byte glyph codes in the relevant normal-row renderer. They are interpreted as multibyte/control values. Putting `A7-AA` into an armament record can corrupt parsing before the armament screen is displayed and caused Standard Scenario entry to stop.

## Rule

- Never allocate compact-font text codes in `A7-FF`.
- Do not reuse this failed candidate as a parent.
- Any future 8x8 mapping must remain in the renderer-safe range below `A7`, preserve original Latin slots that remain visible, and be audited across every initial/focused/unfocused path sharing that font bank.
- Current runtime baseline is v003.
