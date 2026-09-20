from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_glyph_patch import genesis_checksum, render_glyph


V029_SHA256 = "93AB33A6CA42A52747670B314DCF8A2D3BBB90777D6DD6F3FD32181059471939"
SOURCE_SIZE = 0x100000
TARGET_SIZE = 0x200000
FONT16_SOURCE = 0x03C86A
FONT16_SIZE = 0x4800
FONT16_CLONE = 0x100000
FONT8_SOURCE = 0x03850E
FONT8_SIZE = 0x548
FONT8_CLONE = 0x110000
FONT16_POINTER_OFFSET = 0x0081E2
FONT8_POINTER_OFFSETS = (0x008146, 0x008200, 0x0106AE)
CHECKSUM_OFFSET = 0x18E
ROM_END_OFFSET = 0x1A4
RECORD_BASE = 0x120000
STOCK_CODES = {
    "A": 0x15, "C": 0x17,
    "N": 0x22, "o": 0x3D, ".": 0x9B,
    "0": 0x00, "1": 0x01, "2": 0x02, "3": 0x03, "4": 0x04,
    "5": 0x05, "6": 0x06, "7": 0x07, "8": 0x08, "9": 0x09,
}
# Correct two adjacent source-glyph readings in the cloned 16x16 bank.
# The original audit mislabeled 0x0DE (車) as 重; the actual 重 is 0x0FF.
FIXED_GLYPH_OVERRIDES = {0x0CD: "전", 0x0DE: "차", 0x0FF: "중"}
DEV_TRANSITION_EXIT = 0x1BCC60
DEV_TRANSITION_ENTRY = 0x1BCCB0
DEV_TRANSITION_EXIT_HOOK = 0x00FDB2
DEV_TRANSITION_ENTRY_HOOK = 0x00FDBE
DEV_TRANSITION_FOOTER_SUPPRESS = 0x00FDDA
DEV_TRANSITION_CATEGORY_SUPPRESS = 0x00FDF6
FONT_PATH = Path(
    "R:/advanced-daisenryaku-kr-rebuild/assets/fonts/sources/"
    "Galmuri14Bitmap-Regular-2.40.3.ttf"
)

# Japanese source record, four visible cells, natural Korean four-cell layout,
# and every known direct pointer operand. English records are intentionally absent.
RECORDS = (
    # ロード has separate ordinary/focused draw paths. Keep both Korean so
    # moving the cursor away cannot restore the stock katakana glyphs.
    ("game_load", 0x0EF452, ("읽", "기", " "), (0x011842,)),
    ("load", 0x0EF456, ("시", "나", "리", "오"), (0x006220,)),
    ("situation", 0x0EF3E6, ("상", "황", "표", " "), (0x00622A,)),
    ("sound", 0x0EF428, ("사", "운", "드", " "), (0x006234, 0x010176, 0x011EDA)),
    ("control", 0x0EF42D, (" ", "조", "작", " "), (0x00623E, 0x010180)),
    ("search", 0x0EF433, (" ", "색", "적", " "), (0x006248, 0x01018A)),
    ("weather", 0x0EF43A, (" ", "날", "씨", " "), (0x006252, 0x010194, 0x010F30)),
    ("system", 0x0EF441, ("시", "스", "템", " "), (0x00625C, 0x01019E, 0x0124C0)),
    ("alarm", 0x0EF446, ("알", "람", " ", " "), (0x011EC8,)),
    ("search_level_row", 0x0EF50A, ("색", "적", "레", "벨", " ", " ", " "), (0x01231A,)),
    ("weather_title", 0x0EF525, ("날", "씨", "설", "정"), (0x0123D6,)),
    ("weather_rule_row", 0x0EF52D, ("날", "씨", "규", "칙", " ", " "), (0x012420,)),
    # 都市 収入 is six fixed cells including its trailing blank.
    ("income_title", 0x0EF536, ("도", "시", " ", "수", "입", " "), (0x0103AC,)),
    ("system_battle_speed", 0x0EF4BD, ("전", "투", "화", "면", "속", "도", " ", " ", " "), (0x01250C,)),
    ("system_hex_line", 0x0EF4CB, ("헥", "스", "라", "인", " ", " ", " ", " ", " "), (0x01251A,)),
    ("system_enemy_performance", 0x0EF4D5, ("적", "유", "닛", "성", "능", "표", " ", " ", " "), (0x012528,)),
    ("system_counter_weapon", 0x0EF4E3, ("반", "격", "무", "기", "선", "택", " ", " ", " "), (0x012536,)),
    ("game_save", 0x0EF45B, ("저", "장", " "), (0x011838,)),
    ("game_title", 0x0EF423, ("게", "임"), (0x0117F8,)),
    ("game_surrender", 0x0EF45F, ("항", "복"), (0x01186E,)),
    ("game_surrender_focused", 0x0EF463, ("항", "복", " "), (0x01184C,)),
    ("save_number_title", 0x0EF468, ("저", "장", " ", "N", "o", ".", "선", "택"), (0x011AB0,)),
    ("load_number_title", 0x0EF473, ("읽", "기", " ", "N", "o", ".", "선", "택"), (0x00603E, 0x0118F4)),
    ("scenario_edit", 0x0EF485, ("에", "디", "트", " "), (0x006270,)),
    # The situation screen draws 作戦 and 目標 with two consecutive renderer
    # calls while preserving A0 between them.  Keep these as adjacent two-cell
    # records and redirect only the first pointer operand.
    ("operation", 0x0EF5B9, ("작", "전"), (0x010CDC,)),
    ("objective", 0x0EF5BC, ("목", "표"), ()),
    # 占 領 状 態 is a seven-cell record with the original interstitial spaces.
    ("occupation_state", 0x0EF5C1, ("점", " ", "령", " ", "상", " ", "태"), (0x010CF6,)),
    # タイプ別 機数表: preserve the stock 13-cell spaced title geometry.
    ("type_count_table_title", 0x0EF5EA,
     ("기", " ", "종", " ", "별", " ", "기", " ", "수", " ", "표", " ", " "),
     (0x0110C4,)),
    # Production screen labels.  These are isolated instead of changing the
    # shared glyph slots: 画/面 and the ground/placement glyphs are reused by
    # unrelated screens.  Preserve the stock 4/2/3/2-cell geometry and every
    # direct initial/focus draw reference.
    ("production_screen_title", 0x0EF257, ("생", "산", "화", "면"), (0x00F95A,)),
    ("production_available", 0x0EF25E, ("가", "용", "자", "금"), (0x00F96C,)),
    ("production_placement", 0x0EF266, ("배", "치"), (0x00F76E, 0x00F97E)),
    ("production_remaining", 0x0EF26B, ("잔", "여"), (0x00F990,)),
    ("production_ground_initial", 0x0EF270, ("지", "상", " "), (0x00F9C0,)),
    ("production_ground_focused", 0x0EF274, ("지", "상"), (0x00F9AA,)),
    # B-button help overlay.  The Japanese records are
    # `Aボタン 次部隊  Cボタン 首都` and its A/C-swapped form.  Keep the
    # stock A/C glyphs and the exact 17-cell record length.  Korean `버튼` is
    # one cell shorter than `ボタン`, so retain a harmless trailing blank.
    ("map_help_a_next_unit_c_capital", 0x0EFAFC,
     ("A", "버", "튼", " ", "다", "음", "부", "대", " ", " ",
      "C", "버", "튼", " ", "수", "도", " "),
     (0x00A6A8,)),
    ("map_help_a_capital_c_next_unit", 0x0EFB13,
     ("A", "버", "튼", " ", "수", "도", " ", " ",
      "C", "버", "튼", " ", "다", "음", "부", "대", " "),
     (0x00A6B4,)),
    # Surrender/result screen unit.  These four consecutive Japanese records
    # are selected through the pointer table at 0x00B7A0..0x00B7AC.  Preserve
    # their respective 6/6/7/9-cell geometry so no result branch can shift the
    # following record or reuse a stale focused/unfocused drawing path.
    ("major_victory_result", 0x0EFE49,
     ("대", "승", "리", " ", " ", " "),
     (0x00B7A0,)),
    ("victory_result", 0x0EFE56,
     ("승", "리", " ", " ", " ", " "),
     (0x00B7A4,)),
    ("draw_result", 0x0EFE63,
     ("무", "승", "부", " ", " ", " ", " "),
     (0x00B7A8,)),
    ("defeat_result", 0x0EFE71,
     ("당", "신", "의", " ", "패", "배", "입", "니", "다"),
     (0x00B7AC,)),
    # Situation header fields are independent fixed-width records.
    ("situation_snow_depth", 0x0EF5B2, ("적", "설", "량"), (0x010F58,)),
    ("situation_normal", 0x0EF5CD, ("정", "상"), (0x010F9C,)),
    ("situation_temperate", 0x0EF11B, ("온", "대"), (0x010D02,)),
    # Development footer records keep their original 4/14-cell geometry.
    ("development_footer", 0x0EF619, ("개", "발", "화", "면"), (0x00FDD6,)),
    ("development_type_select", 0x0EF622,
     ("개", "발", "화", "면", " ", "병", "기", "종", "류", "선", "택", " ", " ", " "),
     (0x00FA92,)),
    # Unit-selection status records are consumed consecutively from the first
    # pointer.  Preserve their original 3/3/3/3/2-cell layout and adjacency.
    ("development_production_none", 0x0EF637, ("생", "산", "중"), (0x00FE22,)),
    ("development_evolution_1", 0x0EF63C, ("진", "화", "1"), ()),
    ("development_evolution_2", 0x0EF642, ("진", "화", "2"), ()),
    ("development_evolution_3", 0x0EF648, ("진", "화", "3"), ()),
    ("development_selected_title", 0x0EF64E, ("개", "발"), (0x001957, 0x009624)),
)

# Runtime error messages.  Every replacement is padded to the exact Japanese
# record width; overlong text is rejected at import time.  Six stock records
# have no executable reference in Rev A and intentionally remain untouched.
ERROR_SPECS = (
    ("error_01", 0x0EF653, 13, "오류 1 무기 사용 불가", (0x00F56A,)),
    ("error_02", 0x0EF668, 13, "오류 2 탄약 부족", (0x00F578,)),
    ("error_03", 0x0EF67E, 15, "오류 3 이 무기 공격불가", (0x00F582,)),
    ("error_04", 0x0EF695, 11, "오류 4 빈 슬롯없음", (0x00F590,)),
    ("error_05", 0x0EF6A7, 15, "오류 5 공격용 무기 아님", (0x00F59E,)),
    ("error_06", 0x0EF6BF, 13, "오류 6 이동후 사용불가", (0x00F5AC,)),
    ("error_07", 0x0EF6D4, 15, "오류 7 반격 전용 무기", (0x00F5BA,)),
    ("error_08", 0x0EF6ED, 14, "오류 8 점령 불가", (0x00D0B4,)),
    ("error_09", 0x0EF703, 14, "오류 9 보급원 없음", (0x00F5C8,)),
    ("error_10", 0x0EF718, 12, "오류 10 이미 보급함", (0x00F5D6,)),
    ("error_11", 0x0EF729, 17, "오류 11 여기서 합류 불가", (0x00F5E4,)),
    ("error_13", 0x0EF75F, 17, "오류 13 여기서 보충 불가", (0x00F5F2,)),
    ("error_14", 0x0EF77A, 17, "오류 14 보충전 차량 하차", (0x00F600,)),
    ("error_15", 0x0EF795, 18, "오류 15 핵무기 사용 금지", (0x00F612,)),
    ("error_16", 0x0EF7B1, 18, "오류 16 핵폭탄 투하 대기중", (0x00D0C2,)),
    ("error_17", 0x0EF7CC, 15, "오류 17 탄약없어 폭격불가", (0x00D0D0,)),
    ("error_18", 0x0EF7E1, 14, "오류 18 여기서 폭격불가", (0x00D0DE, 0x00D0EC)),
    ("error_19", 0x0EF7F4, 17, "오류 19 이동 후 폭격 불가", (0x00D0FA,)),
    ("error_20", 0x0EF80E, 16, "오류 20 보급없어 생산불가", (0x00D108,)),
    ("error_22", 0x0EF842, 11, "오류 22 요새화최대", (0x00D116,)),
    ("error_23", 0x0EF853, 16, "오류 23 여기서 생산 불가", (0x00D124,)),
    ("error_24", 0x0EF86B, 11, "오류 24 자금 부족", (0x00D132, 0x00F620)),
    ("error_25", 0x0EF87B, 17, "오류 25 공항없어 하차 불가", (0x00D140,)),
    ("error_26", 0x0EF894, 15, "오류 26 타군 부대입니다", (0x00D14E,)),
    ("error_27", 0x0EF8A9, 16, "오류 27 진입 불가", (0x00D15C,)),
    ("error_29", 0x0EF8DB, 14, "오류 29 적 부대를 선택", (0x00D16A,)),
    ("error_30", 0x0EF8EE, 11, "오류30경험250필요", (0x00F62E,)),
    ("error_31", 0x0EF8FE, 15, "오류31 여기서 레벨업불가", (0x00F63C,)),
    ("error_32", 0x0EF916, 15, "오류 32 여기서 개조불가", (0x00F64A,)),
    ("error_33", 0x0EF92E, 13, "오류 33 유닛 수 최대", (0x0126B6,)),
    ("error_36", 0x0EF96A, 15, "오류36 결빙시 사용 불가", (0x00F658,)),
    ("error_37", 0x0EF981, 15, "오류37 맑을때 지상공격", (0x00F666,)),
    ("error_38", 0x0EF995, 15, "오류38 맑을때 대공공격", (0x00F678,)),
    ("error_39", 0x0EF9A9, 15, "오류39 맑음흐림 폭격", (0x00D186,)),
    ("error_40", 0x0EF9BE, 15, "오류40 맑음흐림 강하", (0x00D194,)),
    ("error_41", 0x0EF9D3, 17, "오류41 폭풍눈 공격 불가", (0x00F686,)),
    ("error_42", 0x0EF9EA, 17, "오류42 폭풍눈 강하 불가", (0x00D1A2,)),
    ("error_43", 0x0EFA01, 17, "오류43 폭풍눈 출격 불가", (0x00D1B0,)),
    ("error_45", 0x0EFA31, 15, "오류 45 최대 레벨", (0x00F694,)),
    ("error_46", 0x0EFA48, 15, "오류 46 진화 병기 없음", (0x00F6A2,)),
    ("error_47", 0x0EFA5F, 15, "오류47 점령중 이동 불가", (0x00D178,)),
    ("error_48", 0x0EFA77, 17, "오류 48 시간 변경 불가", (0x0126C6,)),
    ("error_49", 0x0EFA8D, 15, "오류 49 개조 병기 없음", (0x00F6B0,)),
)

for error_name, error_source, error_width, error_text, error_refs in ERROR_SPECS:
    if len(error_text) > error_width:
        raise ValueError(
            f"{error_name} exceeds fixed width: {len(error_text)} > {error_width}"
        )
    RECORDS += ((
        error_name,
        error_source,
        tuple(error_text.ljust(error_width)),
        error_refs,
    ),)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def glyph_code(index: int) -> bytes:
    if not 0x240 <= index <= 0x2FC:
        raise ValueError(f"expanded glyph index out of range: 0x{index:03X}")
    return bytes((0xFE, index - 0x1FD))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    source = args.source.read_bytes()
    if len(source) != SOURCE_SIZE or sha256(source) != V029_SHA256:
        raise SystemExit("REFUSED: source is not approved v029")

    rom = bytearray(source)
    rom.extend(b"\xFF" * (TARGET_SIZE - SOURCE_SIZE))
    rom[FONT16_CLONE:FONT16_CLONE + FONT16_SIZE] = source[
        FONT16_SOURCE:FONT16_SOURCE + FONT16_SIZE
    ]
    rom[FONT8_CLONE:FONT8_CLONE + FONT8_SIZE] = source[
        FONT8_SOURCE:FONT8_SOURCE + FONT8_SIZE
    ]

    # Keep the immutable source untouched.  Correct only the cloned font bank
    # used by this build so dynamic names such as 軽戦車 render as 경전차.
    for index, character in FIXED_GLYPH_OVERRIDES.items():
        start = FONT16_CLONE + index * 32
        rom[start:start + 32] = render_glyph(character, FONT_PATH)

    allowed_prefix = {CHECKSUM_OFFSET, CHECKSUM_OFFSET + 1, *range(ROM_END_OFFSET, ROM_END_OFFSET + 4)}
    pointer_changes = []

    def redirect(offset: int, before: int, after: int, kind: str) -> None:
        current = int.from_bytes(rom[offset:offset + 4], "big")
        if current != before:
            raise SystemExit(
                f"REFUSED: {kind} pointer at 0x{offset:06X} is 0x{current:06X}, "
                f"expected 0x{before:06X}"
            )
        rom[offset:offset + 4] = after.to_bytes(4, "big")
        allowed_prefix.update(range(offset, offset + 4))
        pointer_changes.append({
            "kind": kind,
            "operand_offset": f"0x{offset:06X}",
            "before": f"0x{before:06X}",
            "after": f"0x{after:06X}",
        })

    redirect(FONT16_POINTER_OFFSET, FONT16_SOURCE, FONT16_CLONE, "16x16 font source")
    for offset in FONT8_POINTER_OFFSETS:
        redirect(offset, FONT8_SOURCE, FONT8_CLONE, "8x8 font source")

    characters = []
    for _, _, cells, _ in RECORDS:
        for character in cells:
            if character not in (" ", "-") and character not in STOCK_CODES and character not in characters:
                characters.append(character)
    glyph_indices = {character: 0x240 + i for i, character in enumerate(characters)}
    expansion_ranges = [
        (FONT16_CLONE, FONT16_SIZE),
        (FONT8_CLONE, FONT8_SIZE),
    ]
    glyph_report = []
    for character, index in glyph_indices.items():
        start = FONT16_CLONE + index * 32
        if start + 32 > FONT8_CLONE:
            raise SystemExit(
                f"REFUSED: 16x16 glyph {character!r} at 0x{start:06X} "
                f"overlaps 8x8 font bank at 0x{FONT8_CLONE:06X}"
            )
        bitmap = render_glyph(character, FONT_PATH)
        rom[start:start + 32] = bitmap
        expansion_ranges.append((start, 32))
        glyph_report.append({
            "character": character,
            "index": f"0x{index:03X}",
            "start": f"0x{start:06X}",
        })

    cursor = RECORD_BASE
    record_report = []
    record_addresses = {}
    for name, original, cells, refs in RECORDS:
        record_addresses[name] = cursor
        payload = bytearray((len(cells) - 1,))
        for cell in cells:
            if cell == " ":
                payload.extend(b"\x14")
            elif cell == "-":
                payload.extend(b"\x8C")
            elif cell in STOCK_CODES:
                payload.append(STOCK_CODES[cell])
            else:
                payload.extend(glyph_code(glyph_indices[cell]))
        target = cursor
        rom[target:target + len(payload)] = payload
        expansion_ranges.append((target, len(payload)))
        for ref in refs:
            redirect(ref, original, target, f"{name} fixed display record")
        record_report.append({
            "name": name,
            "source_record": f"0x{original:06X}",
            "target_record": f"0x{target:06X}",
            "cells": len(cells),
            "text": "".join(cells),
            "bytes": payload.hex(" ").upper(),
            "pointer_operands": [f"0x{x:06X}" for x in refs],
        })
        cursor += len(payload)

    # The stock detail transition draws its footer/category before the new
    # background art has finished replacing the previous screen.  Port the
    # user-accepted VRAM-clean ordering from the 2026-09-01 checkpoint: clear
    # only the two stale footer tile-map rows on entry, suppress both early
    # text draws, then redraw the footer and dynamic category after the art.
    entry_program = bytes.fromhex(
        "2F0723FC6C0C000300C000047E1F33FC002400C0000051CFFFF6"
        "23FC6C8C000300C000047E1F33FC002400C0000051CFFFF62E1F"
        "31FCA152CD044EF90000FDC4"
    )
    footer_address = record_addresses["development_footer"]
    exit_program = (
        bytes.fromhex("2F002F082F092F0E43F900FF8B84")
        + bytes.fromhex("41F9") + footer_address.to_bytes(4, "big")
        + bytes.fromhex(
            "4EB90000816670003038CDC2C0FC000743F900FF8B9841F9000237C6"
            "D1C04EB9000081662C5F225F205F201F11FC0001CDA04E75"
        )
    )
    transition_patches = (
        (DEV_TRANSITION_ENTRY, entry_program, b"\xFF" * len(entry_program)),
        (DEV_TRANSITION_EXIT, exit_program, b"\xFF" * len(exit_program)),
        (DEV_TRANSITION_ENTRY_HOOK, bytes.fromhex("4EF9001BCCB0"), bytes.fromhex("31FCA152CD04")),
        (DEV_TRANSITION_EXIT_HOOK, bytes.fromhex("4EB9001BCC60"), bytes.fromhex("11FC0001CDA0")),
        (DEV_TRANSITION_FOOTER_SUPPRESS, bytes.fromhex("4E714E714E71"), bytes.fromhex("4EB900008166")),
        (DEV_TRANSITION_CATEGORY_SUPPRESS, bytes.fromhex("4E714E714E71"), bytes.fromhex("4EB900008166")),
    )
    for offset, replacement, expected in transition_patches:
        current = bytes(rom[offset:offset + len(replacement)])
        if current != expected:
            raise SystemExit(
                f"REFUSED: development transition bytes at 0x{offset:06X} "
                f"are {current.hex().upper()}, expected {expected.hex().upper()}"
            )
        rom[offset:offset + len(replacement)] = replacement
        if offset < SOURCE_SIZE:
            allowed_prefix.update(range(offset, offset + len(replacement)))
        else:
            expansion_ranges.append((offset, len(replacement)))

    rom[ROM_END_OFFSET:ROM_END_OFFSET + 4] = (TARGET_SIZE - 1).to_bytes(4, "big")
    checksum = genesis_checksum(rom)
    rom[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 2] = checksum.to_bytes(2, "big")

    actual_prefix = {
        i for i, (before, after) in enumerate(zip(source, rom[:SOURCE_SIZE]))
        if before != after
    }
    unexpected_prefix = sorted(actual_prefix - allowed_prefix)
    if unexpected_prefix:
        raise SystemExit(
            "REFUSED: unexpected locked-prefix changes: "
            + ", ".join(f"0x{x:06X}" for x in unexpected_prefix[:16])
        )
    allowed_expansion = set()
    for start, size in expansion_ranges:
        allowed_expansion.update(range(start, start + size))
    unexpected_expansion = [
        i for i in range(SOURCE_SIZE, TARGET_SIZE)
        if i not in allowed_expansion and rom[i] != 0xFF
    ]
    if unexpected_expansion:
        raise SystemExit("REFUSED: undeclared expansion data")
    if rom[FONT8_CLONE:FONT8_CLONE + FONT8_SIZE] != source[FONT8_SOURCE:FONT8_SOURCE + FONT8_SIZE]:
        raise SystemExit("REFUSED: cloned 8x8 font bank was modified")
    if cursor > 0x130000:
        raise SystemExit("REFUSED: expanded records exceeded reserved record bank")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rom)
    report = {
        "purpose": "project-04 16x16 start/pre-game menu records",
        "source_sha256": sha256(source),
        "output_sha256": sha256(rom),
        "size": len(rom),
        "checksum": f"0x{checksum:04X}",
        "original_records_modified": 0,
        "english_records_modified": 0,
        "unexpected_prefix_changes": 0,
        "glyphs": glyph_report,
        "records": record_report,
        "pointer_changes": pointer_changes,
    }
    args.output.with_suffix(args.output.suffix + ".build.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
