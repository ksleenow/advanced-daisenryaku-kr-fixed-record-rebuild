# Project constraints

- Preserve the Japanese source ROM and never edit it in place.
- Do not import executable patches, relocated tables, render hooks, or VRAM
  workarounds from the previous rebuild.
- Translation records must remain byte-for-byte equal in length to their
  Japanese records unless a separately reviewed fixed-size font-code mapping
  proves equivalent geometry.
- Preserve Japanese-original English text.
- Every dynamic string requires initial, focus-in, focus-out, re-entry, and
  return-to-map verification before acceptance.
- Make one bounded screen change at a time and save a rollback checkpoint only
  after runtime verification.

