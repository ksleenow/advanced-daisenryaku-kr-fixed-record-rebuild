from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_glyph_patch import render_glyph


V029_SHA256 = "93AB33A6CA42A52747670B314DCF8A2D3BBB90777D6DD6F3FD32181059471939"
SOURCE_SIZE = 0x100000
TARGET_SIZE = 0x200000
CHECKSUM_OFFSET = 0x18E
ROM_END_OFFSET = 0x1A4
TARGET_ROM_END = TARGET_SIZE - 1
FONT16_SOURCE = 0x03C86A
FONT16_SIZE = 0x4800  # 0x240 glyphs * 32 bytes
FONT16_CLONE = 0x100000
FONT8_SOURCE = 0x03850E
FONT8_SIZE = 0x548  # 169 glyphs * 8 bytes
FONT8_CLONE = 0x105000
FONT16_POINTER_OFFSET = 0x0081E2
FONT8_POINTER_OFFSETS = (0x008146, 0x008200, 0x0106AE)
DIAGNOSTIC_GLYPH_BASE = FONT16_CLONE + FONT16_SIZE
DIAGNOSTIC_RECORD = 0x106000
DIAGNOSTIC_RECORD_POINTER_OFFSET = 0x0117F8
DIAGNOSTIC_ORIGINAL_RECORD = bytes.fromhex("01 FD 5A FD 5B")
DIAGNOSTIC_RECORD_BYTES = bytes.fromhex("01 FE 42 FE 43")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def genesis_checksum(rom: bytes) -> int:
    total = 0
    for offset in range(0x200, len(rom), 2):
        word = rom[offset] << 8
        if offset + 1 < len(rom):
            word |= rom[offset + 1]
        total = (total + word) & 0xFFFF
    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a data-free 1 MiB to 2 MiB expansion PoC from v029."
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--fill",
        default="0xFF",
        type=lambda value: int(value, 0),
        help="single byte used only for the appended expansion area",
    )
    parser.add_argument(
        "--clone-fonts",
        action="store_true",
        help="copy the locked original font banks into the expansion area",
    )
    parser.add_argument(
        "--redirect-font16",
        action="store_true",
        help="redirect only the 16x16 LEA source pointer to its identical clone",
    )
    parser.add_argument(
        "--redirect-font8",
        action="store_true",
        help="redirect all three known 8x8 font source pointers to its identical clone",
    )
    parser.add_argument(
        "--diagnostic-title",
        action="store_true",
        help="add two new 16x16 glyphs and redirect one fixed 2-cell title record",
    )
    args = parser.parse_args()

    source = args.source.read_bytes()
    if len(source) != SOURCE_SIZE:
        raise SystemExit(f"REFUSED: source size {len(source)} != {SOURCE_SIZE}")
    digest = sha256(source)
    if digest != V029_SHA256:
        raise SystemExit(f"REFUSED: source is not approved v029: {digest}")
    if not 0 <= args.fill <= 0xFF:
        raise SystemExit("REFUSED: --fill must be one byte")
    if int.from_bytes(source[ROM_END_OFFSET:ROM_END_OFFSET + 4], "big") != SOURCE_SIZE - 1:
        raise SystemExit("REFUSED: source ROM end header is unexpected")

    rom = bytearray(source)
    rom.extend(bytes([args.fill]) * (TARGET_SIZE - SOURCE_SIZE))
    cloned_ranges: list[dict[str, object]] = []
    pointer_changes: list[dict[str, object]] = []
    if args.redirect_font16 and not args.clone_fonts:
        raise SystemExit("REFUSED: --redirect-font16 requires --clone-fonts")
    if args.redirect_font8 and not args.clone_fonts:
        raise SystemExit("REFUSED: --redirect-font8 requires --clone-fonts")
    if args.diagnostic_title and not args.redirect_font16:
        raise SystemExit("REFUSED: --diagnostic-title requires --redirect-font16")
    if args.clone_fonts:
        for name, source_start, size, target_start in (
            ("16x16", FONT16_SOURCE, FONT16_SIZE, FONT16_CLONE),
            ("8x8", FONT8_SOURCE, FONT8_SIZE, FONT8_CLONE),
        ):
            source_end = source_start + size
            target_end = target_start + size
            if not SOURCE_SIZE <= target_start < target_end <= TARGET_SIZE:
                raise SystemExit(f"REFUSED: {name} clone is outside expansion area")
            block = source[source_start:source_end]
            if len(block) != size:
                raise SystemExit(f"REFUSED: {name} source font block is truncated")
            rom[target_start:target_end] = block
            if rom[target_start:target_end] != block:
                raise SystemExit(f"REFUSED: {name} font clone readback mismatch")
            cloned_ranges.append({
                "font": name,
                "source_start": f"0x{source_start:06X}",
                "target_start": f"0x{target_start:06X}",
                "size": size,
                "sha256": sha256(block),
            })
    if args.redirect_font16:
        current = int.from_bytes(
            rom[FONT16_POINTER_OFFSET:FONT16_POINTER_OFFSET + 4], "big"
        )
        if current != FONT16_SOURCE:
            raise SystemExit(
                f"REFUSED: 16x16 pointer is 0x{current:06X}, expected 0x{FONT16_SOURCE:06X}"
            )
        rom[FONT16_POINTER_OFFSET:FONT16_POINTER_OFFSET + 4] = FONT16_CLONE.to_bytes(4, "big")
        pointer_changes.append({
            "kind": "16x16 LEA source",
            "operand_offset": f"0x{FONT16_POINTER_OFFSET:06X}",
            "before": f"0x{FONT16_SOURCE:06X}",
            "after": f"0x{FONT16_CLONE:06X}",
        })
    if args.redirect_font8:
        for pointer_offset in FONT8_POINTER_OFFSETS:
            current = int.from_bytes(rom[pointer_offset:pointer_offset + 4], "big")
            if current != FONT8_SOURCE:
                raise SystemExit(
                    f"REFUSED: 8x8 pointer at 0x{pointer_offset:06X} is "
                    f"0x{current:06X}, expected 0x{FONT8_SOURCE:06X}"
                )
            rom[pointer_offset:pointer_offset + 4] = FONT8_CLONE.to_bytes(4, "big")
            pointer_changes.append({
                "kind": "8x8 font source",
                "operand_offset": f"0x{pointer_offset:06X}",
                "before": f"0x{FONT8_SOURCE:06X}",
                "after": f"0x{FONT8_CLONE:06X}",
            })
    diagnostic_ranges: list[dict[str, object]] = []
    if args.diagnostic_title:
        font_path = Path(
            "R:/advanced-daisenryaku-kr-rebuild/assets/fonts/sources/"
            "Galmuri14Bitmap-Regular-2.40.3.ttf"
        )
        for ordinal, character in enumerate(("시", "험")):
            start = DIAGNOSTIC_GLYPH_BASE + ordinal * 32
            glyph = render_glyph(character, font_path)
            if len(glyph) != 32:
                raise SystemExit("REFUSED: diagnostic glyph size mismatch")
            rom[start:start + 32] = glyph
            diagnostic_ranges.append({
                "kind": "16x16 diagnostic glyph",
                "character": character,
                "glyph_index": f"0x{0x240 + ordinal:03X}",
                "start": f"0x{start:06X}",
                "size": 32,
            })
        rom[DIAGNOSTIC_RECORD:DIAGNOSTIC_RECORD + 5] = DIAGNOSTIC_RECORD_BYTES
        diagnostic_ranges.append({
            "kind": "fixed diagnostic title record",
            "text": "시험",
            "start": f"0x{DIAGNOSTIC_RECORD:06X}",
            "size": 5,
            "cell_count": 2,
        })
        current = int.from_bytes(
            rom[DIAGNOSTIC_RECORD_POINTER_OFFSET:DIAGNOSTIC_RECORD_POINTER_OFFSET + 4],
            "big",
        )
        if current != 0x0EF423:
            raise SystemExit("REFUSED: diagnostic title pointer source is unexpected")
        if source[0x0EF423:0x0EF428] != DIAGNOSTIC_ORIGINAL_RECORD:
            raise SystemExit("REFUSED: original fixed title record is unexpected")
        rom[
            DIAGNOSTIC_RECORD_POINTER_OFFSET:DIAGNOSTIC_RECORD_POINTER_OFFSET + 4
        ] = DIAGNOSTIC_RECORD.to_bytes(4, "big")
        pointer_changes.append({
            "kind": "diagnostic fixed title record",
            "operand_offset": f"0x{DIAGNOSTIC_RECORD_POINTER_OFFSET:06X}",
            "before": "0x0EF423",
            "after": f"0x{DIAGNOSTIC_RECORD:06X}",
        })
    rom[ROM_END_OFFSET:ROM_END_OFFSET + 4] = TARGET_ROM_END.to_bytes(4, "big")
    checksum = genesis_checksum(rom)
    rom[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 2] = checksum.to_bytes(2, "big")

    allowed_prefix_changes = {
        CHECKSUM_OFFSET,
        CHECKSUM_OFFSET + 1,
        *range(ROM_END_OFFSET, ROM_END_OFFSET + 4),
    }
    if args.redirect_font16:
        allowed_prefix_changes.update(
            range(FONT16_POINTER_OFFSET, FONT16_POINTER_OFFSET + 4)
        )
    if args.redirect_font8:
        for pointer_offset in FONT8_POINTER_OFFSETS:
            allowed_prefix_changes.update(range(pointer_offset, pointer_offset + 4))
    if args.diagnostic_title:
        allowed_prefix_changes.update(
            range(DIAGNOSTIC_RECORD_POINTER_OFFSET, DIAGNOSTIC_RECORD_POINTER_OFFSET + 4)
        )
    actual_prefix_changes = {
        index
        for index, (before, after) in enumerate(zip(source, rom[:SOURCE_SIZE]))
        if before != after
    }
    unexpected = sorted(actual_prefix_changes - allowed_prefix_changes)
    if unexpected:
        raise SystemExit(
            "REFUSED: unexpected changes in locked v029 prefix: "
            + ", ".join(f"0x{offset:06X}" for offset in unexpected[:16])
        )
    if len(rom) != TARGET_SIZE:
        raise SystemExit("REFUSED: target size mismatch")
    allowed_expansion = set()
    for item in cloned_ranges:
        start = int(item["target_start"], 0)
        allowed_expansion.update(range(start, start + int(item["size"])))
    for item in diagnostic_ranges:
        start = int(item["start"], 0)
        allowed_expansion.update(range(start, start + int(item["size"])))
    unexpected_expansion = [
        offset
        for offset in range(SOURCE_SIZE, TARGET_SIZE)
        if offset not in allowed_expansion and rom[offset] != args.fill
    ]
    if unexpected_expansion:
        raise SystemExit("REFUSED: data exists outside declared expansion ranges")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rom)
    report = {
        "purpose": (
            "project-03 isolated new-glyph fixed-record display proof"
            if diagnostic_ranges
            else
            "project-03 cloned font addressability proof; no text or VRAM changes"
            if pointer_changes
            else "project-03 locked font clone; no reference or text changes"
            if args.clone_fonts
            else "project-03 ROM expansion only; no font or text changes"
        ),
        "source_sha256": digest,
        "output_sha256": sha256(rom),
        "source_size": SOURCE_SIZE,
        "output_size": TARGET_SIZE,
        "fill_byte": f"0x{args.fill:02X}",
        "rom_end_before": f"0x{SOURCE_SIZE - 1:08X}",
        "rom_end_after": f"0x{TARGET_ROM_END:08X}",
        "checksum": f"0x{checksum:04X}",
        "changed_prefix_offsets": [
            f"0x{offset:06X}" for offset in sorted(actual_prefix_changes)
        ],
        "unexpected_prefix_changes": 0,
        "font_changes": 0,
        "font_clones": cloned_ranges,
        "diagnostic_ranges": diagnostic_ranges,
        "record_changes": 1 if diagnostic_ranges else 0,
        "pointer_changes": pointer_changes,
        "code_changes": 0,
    }
    args.output.with_suffix(args.output.suffix + ".build.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
