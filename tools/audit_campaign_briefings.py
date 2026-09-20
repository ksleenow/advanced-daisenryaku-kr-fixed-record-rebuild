from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


LEGACY_DIR = Path(r"R:/advanced-daisenryaku-kr-rebuild/research/legacy-sources")
TRANSLATION_PATH = Path("assets/campaign-briefings-ko.json")
ORIGINAL_ROM = Path(r"R:/work/original_rev_a_probe.md")

sys.path.insert(0, str(LEGACY_DIR))
from extract_campaign_briefings import (  # noqa: E402
    COMPRESSED_BASE,
    OFFSET_TABLE,
    SCENARIO_COUNT,
    decompress_lzss,
    parse_record,
)


def encoded_row_size(text: str) -> int:
    """Return the conservative byte size of one relocated Korean row."""
    size = 1  # row control byte
    for character in text:
        if character == " " or character.isascii():
            size += 1
        else:
            size += 2
    return size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rom = ORIGINAL_ROM.read_bytes()
    unpacked, compressed_end = decompress_lzss(rom, COMPRESSED_BASE)
    offsets = [
        int.from_bytes(rom[OFFSET_TABLE + i * 2 : OFFSET_TABLE + i * 2 + 2], "big")
        for i in range(SCENARIO_COUNT)
    ]
    translations = json.loads(TRANSLATION_PATH.read_text(encoding="utf-8"))
    if len(translations) != SCENARIO_COUNT:
        raise SystemExit(f"expected 44 translations, got {len(translations)}")

    records = []
    total_rows = 0
    total_text_rows = 0
    total_page_breaks = 0
    for scenario, offset in enumerate(offsets):
        rows, parsed_end = parse_record(unpacked, offset)
        page_break_positions = [
            index for index, row in enumerate(rows) if row["page_break"]
        ]
        text_row_count = len(rows) - len(page_break_positions)
        translated_rows = translations[scenario]["rows"]
        row_count_ok = len(translated_rows) <= text_row_count
        distinct_later = sorted({value for value in offsets if value > offset})
        capacity_end = distinct_later[0] if distinct_later else len(unpacked)
        conservative_size = sum(encoded_row_size(row) for row in translated_rows)
        # Every unused original text row is retained as one blank glyph row;
        # page-break controls remain one byte each.
        conservative_size += text_row_count - len(translated_rows)
        conservative_size += len(page_break_positions)
        records.append(
            {
                "scenario": scenario,
                "offset": f"0x{offset:04X}",
                "shared_with": [i for i, value in enumerate(offsets) if value == offset and i != scenario],
                "original_rows": len(rows),
                "original_text_rows": text_row_count,
                "page_break_positions": page_break_positions,
                "translated_rows": len(translated_rows),
                "row_count_ok": row_count_ok,
                "translated_max_glyphs": max(map(len, translated_rows)),
                "conservative_encoded_size": conservative_size,
                "original_record_capacity": capacity_end - offset,
                "parsed_end": f"0x{parsed_end:04X}",
            }
        )
        total_rows += len(rows)
        total_text_rows += text_row_count
        total_page_breaks += len(page_break_positions)

    report = {
        "original_rom": str(ORIGINAL_ROM),
        "compressed_base": f"0x{COMPRESSED_BASE:06X}",
        "compressed_end": f"0x{compressed_end:06X}",
        "unpacked_size": len(unpacked),
        "scenario_count": SCENARIO_COUNT,
        "total_rows": total_rows,
        "total_text_rows": total_text_rows,
        "total_page_breaks": total_page_breaks,
        "translated_total_rows": sum(len(item["rows"]) for item in translations),
        "row_count_violations": [
            record["scenario"] for record in records if not record["row_count_ok"]
        ],
        "shared_record_groups": [
            [i for i, value in enumerate(offsets) if value == offset]
            for offset in sorted(set(offsets))
            if offsets.count(offset) > 1
        ],
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
