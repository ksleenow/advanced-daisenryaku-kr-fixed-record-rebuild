# v060 production-screen 16x16 labels

- Base: immutable `fixed-record-8x8-katakana-complete-v029.md`
- Scope: production-screen 16x16 labels only
- `生産画面` -> `생산화면` (4 cells)
- `配置` -> `배치` (2 cells, both direct draw references)
- ground label -> `지상` (3-cell initial path and 2-cell focused path)
- The shared original glyph slots were not edited. Each label was relocated as
  an isolated fixed-length record so unrelated screens cannot regress.
- Build guards: original records modified 0, English records modified 0,
  unexpected locked-prefix changes 0.
- ROM: `out/project-04-start16-v060.md`
- SHA-256: `F5AF8B0D742A66ECCC6D1EFD1993CC80C9D63E9FF41E5EA4C7522556BC0A72F4`
- Genesis checksum: `0x0C5F`
