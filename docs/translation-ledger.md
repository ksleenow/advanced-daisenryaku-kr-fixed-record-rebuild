# 고정 길이 번역 원장

모든 항목은 ROM 적용 전에 일본판 원문과 고정 길이를 확정한다.

| 화면 | 원문 | 원본 바이트 | 표시 칸 | 번역 | 패딩 | 초기 | 선택 | 해제 | 복귀 |
|---|---|---:|---:|---|---:|---|---|---|---|

## 조사 규칙

- 주소 하나만 보고 문자열로 간주하지 않는다. 다음 레코드 경계까지의 제어값을 포함해 보존한다.
- 원문 해독 전에는 원시 바이트와 길이만 확정하며 ROM에 쓰지 않는다.
- 같은 문구의 초기 표시, 포커스 인, 포커스 아웃이 별도 레코드인지 먼저 조사한다.

## 1차 확인: 메인 모드 선택 레코드

- `0xEF12F`부터의 앞 1바이트는 68000 `DBF` 계열 반복 횟수로 보이며,
  실제 표시 칸 수는 값에 1을 더한 수와 일치한다.
- `CONTINUE`, `STANDARD`, `CAMPAIGN` 등 일본판에서 이미 영문인 항목은 새
  원칙에 따라 번역 대상에서 제외한다.
- 이 영역은 구조 확인용 기준 자료로만 사용하며 ROM 변경 대상으로 삼지 않는다.

## 2차 확인: 일본어 2칸 행동 메뉴

- 일본어 글리프는 1바이트 코드와 `FD xx`/`FE xx` 2바이트 확장 코드가 혼용된다.
- 바이트 수가 아니라 글리프 토큰 수가 화면 칸 수이다. 예를 들어 이동은
  `01 | FD 0A | FD 0B`로 5바이트지만 화면에는 정확히 2칸을 쓴다.
- 따라서 새 번역은 원본 레코드의 전체 바이트 수와 2칸 표시를 모두 지켜야 한다.

### 원문 글리프 시트 교정

- `FD 10 | AA`는 `戦闘`가 아니라 `武装`이므로 번역은 `무장`이다.
- 두 번째 유닛 메뉴 원문은 `性能 / 処分 / 進化 / 改良 / 行軍`이며,
  각각 `성능 / 처분 / 진화 / 개량 / 행군`으로 2칸을 유지한다.
- 원본 폰트에는 `軍`이 `0x0FF`와 `0x116`에 중복된다. 이 메뉴의 `行軍`
  레코드는 `01 | FD 13 | FD 02`, 즉 `0x110`과 `0x0FF`를 참조한다.
  화면만 보고 중복 슬롯 `0x116`을 수정하면 변화가 없으므로 반드시 실제
  레코드의 토큰을 기준으로 슬롯을 선택한다.

## 게임 메뉴 상태 레코드

| 화면 | 원문 | 원본 바이트 | 표시 칸 | 번역 단계 | 패딩 | 초기 | 선택 | 해제 | 복귀 |
|---|---|---:|---:|---|---:|---|---|---|---|
| 게임 메뉴 | 中止 | 3/4 | 2/3 | 중지(글리프 직역) | 선택판 1칸 | 확인 | 확인 | 조사 필요 | 조사 필요 |
| 게임 메뉴 | ロード | 4/5 | 3/4 | 로-도(음역) | 선택판 1칸 | 확인 | 확인 | 조사 필요 | 조사 필요 |
| 게임 메뉴 | セーブ | 4 | 3 | 세-브(음역) | 없음 | 확인 | 상태 공유 조사 필요 | 조사 필요 | 조사 필요 |
| 게임 메뉴 | 降伏 | 4/5 | 2/3 | 강복(한자음 1차) | 선택판 1칸 | 확인 | 확인 | 조사 필요 | 조사 필요 |

세부 주소와 원시 바이트는 `docs/game-menu-fixed-record-audit.md` 및
`out/inventory/game_menu_*_states.*`를 기준으로 한다.
# 8x8 unit/armament inventory checkpoint

- Japanese source remains the sole translation authority. The English ROM is recorded and hash-checked only as a same-address label locator.
- Unit records: `0x2B368`, 669 records, `0x22` bytes each; the displayed name occupies the first 8 bytes.
- Armament records: `0x33DB6`, 157 records, 8 bytes each.
- No table or 8x8 glyph bytes have been modified at this checkpoint.
- Before any Korean glyph allocation, audit code usage across both complete tables and retain the original eight-byte record length.

## Map C menu — glyph-only fixed-record candidate

- The ordinary and focused `状況表` records at `0xEF3DF` and `0xEF3E6` are a state pair, not separate menu meanings.
- Translation uses a direct one-glyph-to-one-glyph mapping: `全自動/地図/部隊表/状況表/収入表/開発表/部隊順序` → `전자동/지도/부대표/상황표/수입표/개발표/부대순서`.
- No menu record bytes, counters, addresses, or display-cell counts are changed.
