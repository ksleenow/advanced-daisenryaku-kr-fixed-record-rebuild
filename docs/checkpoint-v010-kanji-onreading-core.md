# v010 한자음 핵심 치환 체크포인트

## 목적

- 기준 ROM: 일본판 Rev. A 원본
- 기준 작업본: v009 가타카나 음역판
- 판독이 확실한 16x16 한자 글리프만 한국 한자음 한 글자로 치환한다.
- 문맥에 따른 의역은 하지 않으며, 원본의 글자 수·주소·레코드·셀 수를 바꾸지 않는다.

## 빌드

```powershell
python tools\build_glyph_patch.py `
  --source R:\work\original_rev_a_probe.md `
  --group unit_action_menu `
  --group unit_secondary_menu `
  --group map_c_menu `
  --group unit_order_menu `
  --group katakana_phonetic `
  --group kanji_onreading_core `
  --output out\fixed-record-kanji-onreading-v010.md
```

## 결과

- 출력: `out/fixed-record-kanji-onreading-v010.md`
- 크기: 1,048,576 bytes
- SHA-256: `9BE76AF3F28D646F6775AEA62F4D7DAFEB0792762A5E2DD59C982CDA4D1A36A8`
- 메가드라이브 체크섬: `0x5083`
- 변경된 레코드: 0
- 허용 범위 밖 변경: 0
- UI 레코드 영역 `0xEF000..0xEFFFF`: 원본과 완전 동일

## 적용 원칙

- 한 글리프를 한 글리프로만 치환한다.
- 같은 한자가 서로 다른 슬롯에 중복되어 있으면 각 슬롯을 별도로 치환한다.
- 판독이 불확실하거나 한자가 아닌 슬롯은 추측하여 바꾸지 않는다.
- v009는 보존하며, v010은 사용자 실행 검증 전까지 안전 태그로 승격하지 않는다.

## 실행 검증 항목

- 최초 표시
- 포커스 진입
- 포커스 이탈
- 메뉴 재진입
- 지도 복귀
- 표준 시나리오 진입 및 정지 여부

