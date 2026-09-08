# v009 full katakana phonetic candidate

## Immutable base

- Runtime-safe base: `runtime-safe-v008`
- Japanese Rev. A records remain byte-identical.
- No string relocation, no pointer changes, and no counter changes.

## Scope

All stock 16x16 katakana glyphs at indices `0x049..0x09A` are replaced one-for-one by their Korean phonetic equivalents. The long-vowel mark is rendered as `-`.

Examples:

- `セーブ` -> `세-브`
- `ロード` -> `로-도`
- `タイプ` -> `타이프`
- `ゲーム` -> `게-무`

Small kana and the moraic/sokuon glyphs retain one display cell each. This is intentionally a mechanical phonetic layer, not a polished contextual translation.

Kanji are not expanded in this candidate. They will be handled as a separate stage so regressions can be attributed and rolled back independently.
