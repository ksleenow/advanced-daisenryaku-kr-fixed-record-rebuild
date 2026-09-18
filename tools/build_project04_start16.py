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
FONT8_CLONE = 0x105000
FONT16_POINTER_OFFSET = 0x0081E2
FONT8_POINTER_OFFSETS = (0x008146, 0x008200, 0x0106AE)
CHECKSUM_OFFSET = 0x18E
ROM_END_OFFSET = 0x1A4
RECORD_BASE = 0x106100
FONT_PATH = Path(
    "R:/advanced-daisenryaku-kr-rebuild/assets/fonts/sources/"
    "Galmuri14Bitmap-Regular-2.40.3.ttf"
)

# Japanese source record, four visible cells, natural Korean four-cell layout,
# and every known direct pointer operand. English records are intentionally absent.
RECORDS = (
    # ロード has separate ordinary/focused draw paths. Keep both Korean so
    # moving the cursor away cannot restore the stock katakana glyphs.
    ("load_ordinary", 0x0EF452, ("시", "나", "리", "오"), (0x011842,)),
    ("load", 0x0EF456, ("시", "나", "리", "오"), (0x006220,)),
    ("sound", 0x0EF428, ("사", "운", "드", " "), (0x006234, 0x010176, 0x011EDA)),
    ("control", 0x0EF42D, (" ", "조", "작", " "), (0x00623E, 0x010180)),
    ("search", 0x0EF433, (" ", "색", "적", " "), (0x006248, 0x01018A)),
    ("weather", 0x0EF43A, (" ", "날", "씨", " "), (0x006252, 0x010194, 0x010F30)),
    ("system", 0x0EF441, ("시", "스", "템", " "), (0x00625C, 0x01019E, 0x0124C0)),
    ("alarm", 0x0EF446, ("알", "람", " ", " "), (0x011EC8,)),
    ("search_level_row", 0x0EF50A, ("색", "적", "레", "벨", " ", " ", " "), (0x01231A,)),
    ("weather_title", 0x0EF525, ("날", "씨", "설", "정"), (0x0123D6,)),
    ("weather_rule_row", 0x0EF52D, ("날", "씨", "규", "칙", " ", " "), (0x012420,)),
    ("system_hex_line", 0x0EF4CB, ("헥", "스", "라", "인", " ", " ", " ", " ", " "), (0x01251A,)),
)


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
            if character not in (" ", "-") and character not in characters:
                characters.append(character)
    glyph_indices = {character: 0x240 + i for i, character in enumerate(characters)}
    expansion_ranges = [
        (FONT16_CLONE, FONT16_SIZE),
        (FONT8_CLONE, FONT8_SIZE),
    ]
    glyph_report = []
    for character, index in glyph_indices.items():
        start = FONT16_CLONE + index * 32
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
    for name, original, cells, refs in RECORDS:
        payload = bytearray((len(cells) - 1,))
        for cell in cells:
            if cell == " ":
                payload.extend(b"\x14")
            elif cell == "-":
                payload.extend(b"\x8C")
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
