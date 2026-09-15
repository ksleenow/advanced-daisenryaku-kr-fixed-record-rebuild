# Original 8x8 font safety audit

- ROM SHA-256: `47360B90EE077C2DF7BB8F8BB6F46BBEA25D7E5B1FD975CDF507C1048D80B062`
- Uploaded font block: `0x03850E` / `0x548` bytes / 169 glyphs (`0x00-0xA8`)
- Renderer-safe audit range: `0x00-0xA6`
- Hard exclusion: `0xA7-0xFF` (control/multibyte regression proven)
- 68K proof: loaders at `0x0081FE` and `0x0106AC` pass `D3=0x547`; the upload loop consumes `D3+1=0x548` bytes
- Direct ROM pointer references: 0x008146, 0x008200, 0x0106AE
- Codes unused by the known unit+armament tables: 20
- Blank codes among those candidates: 0

## Important limitation

An unused code in the known unit and armament tables is only a candidate. It is not globally safe until every renderer path and dynamic/focus state using the shared font bank is traced.

## Candidate codes

`0x38 0x3F 0x44 0x46 0x47 0x5F 0x60 0x6F 0x70 0x72 0x73 0x77 0x89 0x9C 0x9F 0xA0 0xA1 0xA2 0xA3 0xA4`

## Blank candidate codes

`none`
