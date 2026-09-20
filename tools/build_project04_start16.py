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
RESOURCE_LOGO_HELPER = 0x1EF000
RESOURCE_LOGO_ASSET = 0x1F0000
RESOURCE_LOGO_POINTER = 0x000640
RESOURCE_LOGO_HOOK = 0x0006FE
RESOURCE_LOGO_TOP_MAP = 0x0D5426
RESOURCE_LOGO_DIR = Path("assets/resource-logo")
CREDIT_HELPER = 0x1E8000
CREDIT_RECORD_BASE = 0x1E8100
TIMELINE_BASE = 0x1EA000
BRIEFING_TRANSLATIONS = Path("assets/campaign-briefings-ko.json")
BRIEFING_ORIGINAL_BASE = 0x023EB6
BRIEFING_RELOCATED_BASE = 0x140000
BRIEFING_POINTER_OFFSET = 0x00230E
BRIEFING_OFFSET_TABLE = 0x023E5E
BRIEFING_SCENARIO_COUNT = 44
STOCK_CODES = {
    "A": 0x15, "C": 0x17,
    "N": 0x22, "o": 0x3D, ".": 0x9B,
    "0": 0x00, "1": 0x01, "2": 0x02, "3": 0x03, "4": 0x04,
    "5": 0x05, "6": 0x06, "7": 0x07, "8": 0x08, "9": 0x09,
}


def decompress_lzss(data: bytes, address: int) -> tuple[bytes, int]:
    pos = address
    token_count = int.from_bytes(data[pos:pos + 2], "big") + 1
    pos += 2
    window = bytearray(0x1000)
    write_pos = 0xFEE
    output = bytearray()
    flags = 0
    bits_left = 0
    for _ in range(token_count):
        if bits_left == 0:
            flags = data[pos]
            pos += 1
            bits_left = 8
        literal = bool(flags & 0x80)
        flags = (flags << 1) & 0xFF
        bits_left -= 1
        if literal:
            value = data[pos]
            pos += 1
            output.append(value)
            window[write_pos] = value
            write_pos = (write_pos + 1) & 0xFFF
        else:
            pair = int.from_bytes(data[pos:pos + 2], "big")
            pos += 2
            read_pos = pair >> 4
            length = (pair & 0xF) + 3
            for _ in range(length):
                value = window[read_pos]
                read_pos = (read_pos + 1) & 0xFFF
                output.append(value)
                window[write_pos] = value
                write_pos = (write_pos + 1) & 0xFFF
    return bytes(output), pos


def compress_lzss_literals(data: bytes) -> bytes:
    if not data or len(data) > 0x10000:
        raise ValueError(f"briefing stream cannot be encoded: {len(data)} bytes")
    output = bytearray((len(data) - 1).to_bytes(2, "big"))
    for start in range(0, len(data), 8):
        chunk = data[start:start + 8]
        output.append((0xFF << (8 - len(chunk))) & 0xFF)
        output.extend(chunk)
    return bytes(output)


def skip_glyph(data: bytes, pos: int) -> int:
    return pos + (1 if data[pos] < 0xFD else 2)


def record_controls(data: bytes, start: int) -> tuple[list[int], int]:
    controls = []
    pos = start
    for _ in range(256):
        control = data[pos]
        pos += 1
        controls.append(control)
        if not control & 0x80:
            for _ in range((control & 0x3F) + 1):
                pos = skip_glyph(data, pos)
        if control & 0x40:
            return controls, pos
    raise ValueError(f"unterminated briefing record at 0x{start:04X}")
# Korean glyphs already present in the approved v029 16x16 bank.  Reusing
# these audited slots keeps the expanded-code namespace small and leaves the
# immutable source bank untouched.
BASELINE_KOREAN_GLYPHS = {
    "가": 0x067, "각": 0x11D, "공": 0x0D5, "군": 0x0FF,
    "기": 0x068, "내": 0x13A, "년": 0x1C9, "담": 0x0C2,
    "데": 0x074, "독": 0x1D4, "동": 0x108, "라": 0x083,
    "리": 0x084, "립": 0x1D0, "방": 0x126, "베": 0x090,
    "병": 0x0B9, "부": 0x14A, "불": 0x0B3, "사": 0x053,
    "성": 0x111, "소": 0x057, "스": 0x055, "아": 0x049,
    "약": 0x0AF, "양": 0x1DE, "오": 0x04D, "유": 0x081,
    "인": 0x0B5, "일": 0x1D6, "임": 0x1D3, "작": 0x0EF,
    "장": 0x0AA, "정": 0x0C0, "제": 0x06F, "조": 0x070,
    "주": 0x0E4, "진": 0x114, "체": 0x1E0, "총": 0x184,
    "취": 0x0C5, "코": 0x052, "통": 0x16B, "폭": 0x0D0,
    "한": 0x0CC, "할": 0x1DD, "합": 0x10B, "해": 0x1DF,
    "협": 0x1D8, "화": 0x118, "회": 0x16E, "히": 0x077,
}

CREDIT_LINES = (
    "한글화 v0.95",
    "한글화 기술·제작 Codex",
    "기획·제작 쏘갈장군",
)

# The playable attract-mode chronology ends at the non-aggression pact.  The
# later Potsdam record remains unused, exactly as in the Japanese program.
TIMELINE_SPECS = (
    ("timeline_1919", 0x0EFB7D, 0x000EF4, "1919년 베르사유 조약 체결", None),
    ("timeline_1923", 0x0EFB92, 0x000FC0, "1923년 뮌헨 폭동", None),
    ("timeline_1933", 0x0EFBA3, 0x000FE2, "1933년 히틀러 내각 성립", None),
    ("timeline_1934", 0x0EFBB7, 0x00109C, "1934년 힌덴부르크 사망", "      히틀러 총통 취임"),
    ("timeline_1936", 0x0EFBDD, 0x001172, "1936년 독일 라인란트 진주", "      일독 방공협정 조인"),
    ("timeline_1938_a", 0x0EFC09, 0x00128E, "1938년 독일 오스트리아 병합", "      뮌헨 회담"),
    ("timeline_1938_b", 0x0EFC2F, 0x0013AE, "1938년 주데텐란트 독일에 할양", None),
    ("timeline_1939", 0x0EFC46, 0x0014BA, "1939년 독일, 체코 해체", "      독소 불가침조약 체결"),
)
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
    # Campaign/end-of-war notice.  The Japanese source is
    # `ヨーロッパにおける戦いは終わった`, not the old rebuild's inferred
    # "Germany conquered" label.  Keep all 16 visible cells; TURN immediately
    # before it is Japanese-original English and remains untouched.
    ("european_war_ended", 0x0EFE89,
     ("유", "럽", "에", "서", "의", " ", "전", "쟁",
      "은", " ", "끝", "났", "다", " ", " ", " "),
     (0x00187E,)),
    # Opening-demo message.  The Japanese record is 18 fixed cells and the
    # approved Korean wording also occupies exactly 18 cells, so the stock
    # screen position and timing path remain unchanged.
    ("opening_tragedy_message", 0x0EFB58,
     ("이", " ", "비", "극", "이", " ", "반", "복", "되", "지", " ",
      "않", "기", "를", " ", "바", "라", "며"),
     (0x000746,)),
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
    if not 0x240 <= index <= 0x3FC:
        raise ValueError(f"expanded glyph index out of range: 0x{index:03X}")
    if index <= 0x2FC:
        return bytes((0xFE, index - 0x1FD))
    return bytes((0xFF, index - 0x2FD))


def baseline_glyph_code(index: int) -> bytes:
    """Encode a glyph index from the original Japanese two-tier code table."""
    if index < 0xFD:
        return bytes((index,))
    if index <= 0x1FC:
        return bytes((0xFD, index - 0xFD))
    raise ValueError(f"baseline glyph index out of range: 0x{index:03X}")


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
    briefings = json.loads(BRIEFING_TRANSLATIONS.read_text(encoding="utf-8"))
    if len(briefings) != BRIEFING_SCENARIO_COUNT:
        raise SystemExit(f"REFUSED: expected 44 briefing translations, got {len(briefings)}")

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
    supplemental_text = "".join(CREDIT_LINES)
    for _, _, _, first, second in TIMELINE_SPECS:
        supplemental_text += first + (second or "")
    supplemental_text += "".join(row for entry in briefings for row in entry["rows"])
    for character in supplemental_text:
        if (
            character not in (" ", "-")
            and character not in STOCK_CODES
            and character not in BASELINE_KOREAN_GLYPHS
            and character not in characters
        ):
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

    def encode_cells(cells: str | tuple[str, ...]) -> bytes:
        payload = bytearray((len(cells) - 1,))
        for cell in cells:
            if cell == " ":
                payload.append(0x14)
            elif cell == "-":
                payload.append(0x8C)
            elif cell == "－":
                payload.append(0x9D)
            elif cell == "/":
                payload.append(0x9E)
            elif cell == "·":
                payload.extend(glyph_code(glyph_indices[cell]))
            elif cell in STOCK_CODES:
                payload.append(STOCK_CODES[cell])
            elif "A" <= cell <= "Z":
                payload.append(0x15 + ord(cell) - ord("A"))
            elif "a" <= cell <= "z":
                payload.append(0x2F + ord(cell) - ord("a"))
            elif cell in glyph_indices:
                payload.extend(glyph_code(glyph_indices[cell]))
            elif cell in BASELINE_KOREAN_GLYPHS:
                payload.extend(baseline_glyph_code(BASELINE_KOREAN_GLYPHS[cell]))
            else:
                raise ValueError(f"no glyph encoding for {cell!r}")
        return bytes(payload)

    for name, original, cells, refs in RECORDS:
        record_addresses[name] = cursor
        payload = bytearray(encode_cells(cells))
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

    # Opening localization credits.  The stock message remains on its original
    # renderer path; this helper adds three lower rows, restores the original
    # VDP register write, and extends the stock 60-frame delay to 180 frames.
    credit_cursor = CREDIT_RECORD_BASE
    credit_addresses = []
    for line in CREDIT_LINES:
        encoded = encode_cells(line)
        credit_addresses.append(credit_cursor)
        rom[credit_cursor:credit_cursor + len(encoded)] = encoded
        expansion_ranges.append((credit_cursor, len(encoded)))
        credit_cursor += len(encoded)
        if credit_cursor & 1:
            credit_cursor += 1
    credit_program = bytearray()
    credit_destinations = []
    for line, address, row in zip(
        CREDIT_LINES, credit_addresses, (0xFF8900, 0xFF8A80, 0xFF8C00)
    ):
        destination = row + ((40 - len(line) * 2) // 2) * 2
        credit_destinations.append(destination)
        credit_program += bytes.fromhex("41F9") + address.to_bytes(4, "big")
        credit_program += bytes.fromhex("43F9") + destination.to_bytes(4, "big")
        credit_program += bytes.fromhex("72007400")
        credit_program += bytes.fromhex("4EB900008166")
    credit_program += bytes.fromhex("33FC0EEE00FF03824E75")
    rom[CREDIT_HELPER:CREDIT_HELPER + len(credit_program)] = credit_program
    expansion_ranges.append((CREDIT_HELPER, len(credit_program)))
    expected_credit_hook = bytes.fromhex("33FC0EEE00FF0382")
    if bytes(rom[0x000766:0x00076E]) != expected_credit_hook:
        raise SystemExit("REFUSED: opening credit hook bytes differ from approved v029")
    rom[0x000766:0x00076E] = bytes.fromhex("4EB9001E80004E71")
    allowed_prefix.update(range(0x000766, 0x00076E))
    if bytes(rom[0x00077C:0x00077E]) != bytes.fromhex("003C"):
        raise SystemExit("REFUSED: opening duration is not stock 60 frames")
    rom[0x00077C:0x00077E] = bytes.fromhex("00B4")
    allowed_prefix.update(range(0x00077C, 0x00077E))

    # Full playable chronology.  Continuation records are deliberately stored
    # immediately after their primary record because the stock routine advances
    # A0 rather than loading another pointer for the second line.
    timeline_cursor = TIMELINE_BASE
    timeline_report = []
    for name, original, ref, first, second in TIMELINE_SPECS:
        target = timeline_cursor
        first_encoded = encode_cells(first)
        rom[timeline_cursor:timeline_cursor + len(first_encoded)] = first_encoded
        expansion_ranges.append((timeline_cursor, len(first_encoded)))
        timeline_cursor += len(first_encoded)
        second_target = None
        if second:
            second_target = timeline_cursor
            second_encoded = encode_cells(second)
            rom[timeline_cursor:timeline_cursor + len(second_encoded)] = second_encoded
            expansion_ranges.append((timeline_cursor, len(second_encoded)))
            timeline_cursor += len(second_encoded)
        redirect(ref, original, target, f"{name} chronology record")
        timeline_report.append({
            "name": name,
            "target_record": f"0x{target:06X}",
            "first": first,
            "second": second,
            "second_record": f"0x{second_target:06X}" if second_target else None,
        })

    # Campaign briefings are a compressed stream with a fixed 44-entry offset
    # table.  Rebuild each record inside its original span, preserving the
    # Japanese row/page topology and the deliberate scenario-13/43 sharing.
    original_briefing, original_briefing_end = decompress_lzss(
        source, BRIEFING_ORIGINAL_BASE
    )
    briefing_unpacked = bytearray(original_briefing)
    briefing_offsets = [
        int.from_bytes(
            source[
                BRIEFING_OFFSET_TABLE + scenario * 2:
                BRIEFING_OFFSET_TABLE + scenario * 2 + 2
            ],
            "big",
        )
        for scenario in range(BRIEFING_SCENARIO_COUNT)
    ]
    unique_offsets = sorted(set(briefing_offsets))
    rebuilt_by_offset = {}
    briefing_report = []
    for scenario, entry in enumerate(briefings):
        if int(entry["scenario"]) != scenario:
            raise SystemExit(f"REFUSED: briefing entry {scenario} has wrong scenario id")
        offset = briefing_offsets[scenario]
        shared_scenarios = [
            index for index, value in enumerate(briefing_offsets) if value == offset
        ]
        if offset in rebuilt_by_offset:
            first_scenario = rebuilt_by_offset[offset]["scenario"]
            if entry["rows"] != briefings[first_scenario]["rows"]:
                raise SystemExit(
                    f"REFUSED: shared briefing {first_scenario}/{scenario} differs"
                )
            briefing_report.append({
                "scenario": scenario,
                "offset": f"0x{offset:04X}",
                "shared_with": first_scenario,
                "rows": entry["rows"],
            })
            continue

        controls, _ = record_controls(original_briefing, offset)
        text_slots = sum(1 for control in controls if not control & 0x80)
        if len(entry["rows"]) > text_slots:
            raise SystemExit(
                f"REFUSED: briefing {scenario} needs {len(entry['rows'])} rows, "
                f"original has {text_slots}"
            )
        rebuilt = bytearray()
        translated_index = 0
        for control in controls:
            if control & 0x80:
                rebuilt.append(control)
                continue
            text = (
                entry["rows"][translated_index]
                if translated_index < len(entry["rows"])
                else " "
            )
            translated_index += 1
            if not 1 <= len(text) <= 20:
                raise SystemExit(
                    f"REFUSED: briefing {scenario} row width {len(text)}: {text!r}"
                )
            encoded = bytearray(encode_cells(text))
            encoded[0] = (encoded[0] & 0x3F) | (control & 0x40)
            rebuilt.extend(encoded)
        next_offsets = [value for value in unique_offsets if value > offset]
        capacity_end = next_offsets[0] if next_offsets else len(briefing_unpacked)
        capacity = capacity_end - offset
        if len(rebuilt) > capacity:
            raise SystemExit(
                f"REFUSED: briefing {scenario} uses {len(rebuilt)} > {capacity} bytes"
            )
        briefing_unpacked[offset:offset + len(rebuilt)] = rebuilt
        rebuilt_by_offset[offset] = {"scenario": scenario, "bytes": bytes(rebuilt)}
        briefing_report.append({
            "scenario": scenario,
            "offset": f"0x{offset:04X}",
            "shared_scenarios": shared_scenarios,
            "original_controls": [f"0x{control:02X}" for control in controls],
            "text_slots": text_slots,
            "translated_rows": len(entry["rows"]),
            "encoded_size": len(rebuilt),
            "capacity": capacity,
            "rows": entry["rows"],
        })

    briefing_packed = compress_lzss_literals(bytes(briefing_unpacked))
    if BRIEFING_RELOCATED_BASE + len(briefing_packed) > 0x148000:
        raise SystemExit("REFUSED: relocated briefing stream exceeds reserved bank")
    rom[
        BRIEFING_RELOCATED_BASE:
        BRIEFING_RELOCATED_BASE + len(briefing_packed)
    ] = briefing_packed
    expansion_ranges.append((BRIEFING_RELOCATED_BASE, len(briefing_packed)))
    redirect(
        BRIEFING_POINTER_OFFSET,
        BRIEFING_ORIGINAL_BASE,
        BRIEFING_RELOCATED_BASE,
        "campaign briefing compressed stream",
    )
    verified_briefing, verified_end = decompress_lzss(rom, BRIEFING_RELOCATED_BASE)
    if verified_briefing != bytes(briefing_unpacked):
        raise SystemExit("REFUSED: relocated briefing decompression mismatch")
    if verified_end != BRIEFING_RELOCATED_BASE + len(briefing_packed):
        raise SystemExit("REFUSED: relocated briefing packed-size mismatch")
    for offset, rebuilt_entry in rebuilt_by_offset.items():
        expected = rebuilt_entry["bytes"]
        if verified_briefing[offset:offset + len(expected)] != expected:
            raise SystemExit(
                f"REFUSED: briefing {rebuilt_entry['scenario']} decode mismatch"
            )

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

    # Opening resource-credit screen.  Keep all Japanese magazine-logo art,
    # replace only the private caption tiles, and draw the two Korean magazine
    # labels after the stock screen setup.  The helper is assembled here from
    # reviewed 68000 opcodes; no executable patch is imported from the former
    # rebuild.
    logo_asset = (RESOURCE_LOGO_DIR / "logo.nem").read_bytes()
    top_map = (RESOURCE_LOGO_DIR / "top-caption-map.bin").read_bytes()
    middle_row = (RESOURCE_LOGO_DIR / "middle-caption-row.bin").read_bytes()
    bottom_row = (RESOURCE_LOGO_DIR / "bottom-caption-row.bin").read_bytes()
    if len(top_map) != 72 or len(middle_row) != 44 or len(bottom_row) != 32:
        raise SystemExit("REFUSED: resource-credit asset geometry changed")

    def words(data: bytes) -> list[int]:
        return [int.from_bytes(data[i:i + 2], "big") for i in range(0, len(data), 2)]

    middle_words = words(middle_row)
    bottom_words = words(bottom_row)
    blank_tile = 0x0101
    middle_line = [word for word in middle_words if word != blank_tile]
    bottom_line = [word for word in bottom_words if word != blank_tile]
    if middle_line != [0x126, 0x127, 0x128, 0x129, 0x12A, 0x12B, 0x12C]:
        # The two intentional inter-word blanks are restored below.
        if middle_words[6:15] != [0x126, 0x127, 0x101, 0x128, 0x129, 0x101, 0x12A, 0x12B, 0x12C]:
            raise SystemExit("REFUSED: middle resource caption mapping changed")
    if bottom_words[4:11] != [0x12D, 0x12E, 0x101, 0x12F, 0x130, 0x131, 0x132]:
        raise SystemExit("REFUSED: bottom resource caption mapping changed")
    caption_lines = (middle_words[6:15], bottom_words[4:11])
    caption_destinations = (0x00FF981E, 0x00FF9B20)
    helper = bytearray()
    helper_data_patches = []
    for line, destination in zip(caption_lines, caption_destinations):
        helper.extend(b"\x41\xF9")
        helper_data_patches.append(len(helper))
        helper.extend(b"\x00\x00\x00\x00")
        helper.extend(b"\x43\xF9" + destination.to_bytes(4, "big"))
        helper.extend(bytes((0x70, len(line) - 1)))
        helper.extend(b"\x32\xD8\x51\xC8\xFF\xFC")
    # Restore the stock A1 source pointer consumed immediately after the hook.
    helper.extend(b"\x43\xF9\x00\x0D\x55\xBE\x4E\x75")
    if len(helper) & 1:
        helper.append(0)
    for line, patch_offset in zip(caption_lines, helper_data_patches):
        data_address = RESOURCE_LOGO_HELPER + len(helper)
        helper[patch_offset:patch_offset + 4] = data_address.to_bytes(4, "big")
        for word in line:
            helper.extend(word.to_bytes(2, "big"))

    resource_patches = (
        (RESOURCE_LOGO_POINTER, bytes.fromhex("41F9001F0000"), bytes.fromhex("41F9000D49C8")),
        (RESOURCE_LOGO_HOOK, bytes.fromhex("4EB9001EF000"), bytes.fromhex("43F9000D55BE")),
        (RESOURCE_LOGO_TOP_MAP, top_map, source[RESOURCE_LOGO_TOP_MAP:RESOURCE_LOGO_TOP_MAP + len(top_map)]),
        (RESOURCE_LOGO_HELPER, bytes(helper), b"\xFF" * len(helper)),
        (RESOURCE_LOGO_ASSET, logo_asset, b"\xFF" * len(logo_asset)),
    )
    for offset, replacement, expected in resource_patches:
        current = bytes(rom[offset:offset + len(replacement)])
        if current != expected:
            raise SystemExit(
                f"REFUSED: resource-credit bytes at 0x{offset:06X} are "
                f"{current[:16].hex().upper()}, expected {expected[:16].hex().upper()}"
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
        "purpose": "project-05 fixed-layout campaign briefing records",
        "source_sha256": sha256(source),
        "output_sha256": sha256(rom),
        "size": len(rom),
        "checksum": f"0x{checksum:04X}",
        "original_records_modified": 0,
        "english_records_modified": 0,
        "unexpected_prefix_changes": 0,
        "glyphs": glyph_report,
        "records": record_report,
        "opening_credits": {
            "lines": list(CREDIT_LINES),
            "display_frames": 180,
            "destinations": [f"0x{x:08X}" for x in credit_destinations],
            "helper": f"0x{CREDIT_HELPER:06X}",
        },
        "timeline": timeline_report,
        "campaign_briefings": {
            "source_base": f"0x{BRIEFING_ORIGINAL_BASE:06X}",
            "source_packed_size": original_briefing_end - BRIEFING_ORIGINAL_BASE,
            "relocated_base": f"0x{BRIEFING_RELOCATED_BASE:06X}",
            "packed_size": len(briefing_packed),
            "unpacked_size": len(briefing_unpacked),
            "records": briefing_report,
        },
        "pointer_changes": pointer_changes,
    }
    args.output.with_suffix(args.output.suffix + ".build.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
