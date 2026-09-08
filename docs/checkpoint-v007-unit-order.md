# v007 unit-order candidate

- Base: Japanese Rev. A, immutable SHA-256 `47360B90EE077C2DF7BB8F8BB6F46BBEA25D7E5B1FD975CDF507C1048D80B062`
- Output: `out/fixed-record-unit-order-v007.md`
- Output SHA-256: `D43118AD2B2F84BF6C37E9F94F6C6D02A4EAE1E7BA149CA7D82748AFA145C644`
- ROM size: 1,048,576 bytes (unchanged)
- Sega checksum: `0xF96C`
- Modified fixed records: 0
- Unexpected byte changes: 0

## Scope

The `부대순서` submenu was added by changing only the original 16x16 glyph bitmaps.
The original record addresses, byte lengths, DBF counters, token counts, spaces, and order remain unchanged.

| Japanese record | Fixed cells | Korean display |
| --- | ---: | --- |
| ` 番号順` | 4 | ` 번호순` |
| `タイプ順` | 4 | `타이프순` |
| ` 行動 ` | 4 | ` 행동 ` |

`タイプ順` deliberately uses four Korean cells (`타이프순`) instead of the shorter `타입순`, because fixed display-cell count is mandatory.

## Runtime acceptance still required

- initial display
- focus-in
- focus-out
- repeated up/down movement
- submenu exit and return to map
- Standard Scenario entry remains responsive
