from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_glyph_patch import genesis_checksum
from build_project04_start16 import (
    BASELINE_KOREAN_GLYPHS,
    BRIEFING_POINTER_OFFSET,
    BRIEFING_RELOCATED_BASE,
    STOCK_CODES,
    baseline_glyph_code,
    compress_lzss_literals,
    decompress_lzss,
    glyph_code,
)


CHECKSUM_OFFSET = 0x18E
RESERVED_END = 0x148000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--translations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = args.source.read_bytes()
    if len(source) != 0x200000:
        raise SystemExit("REFUSED: review source must be a 2 MiB official build")
    pointer = int.from_bytes(
        source[BRIEFING_POINTER_OFFSET:BRIEFING_POINTER_OFFSET + 4], "big"
    )
    if pointer != BRIEFING_RELOCATED_BASE:
        raise SystemExit(f"REFUSED: briefing pointer is 0x{pointer:06X}")

    build_report_path = args.source.with_suffix(args.source.suffix + ".build.json")
    build_report = json.loads(build_report_path.read_text(encoding="utf-8"))
    if build_report["output_sha256"] != sha256(source):
        raise SystemExit("REFUSED: source ROM does not match its build report")
    glyph_indices = {
        item["character"]: int(item["index"], 16) for item in build_report["glyphs"]
    }
    translations = json.loads(args.translations.read_text(encoding="utf-8"))
    if len(translations) != 44:
        raise SystemExit(f"REFUSED: expected 44 scenarios, got {len(translations)}")

    def encode_text(text: str) -> bytes:
        result = bytearray()
        for cell in text:
            if cell == " ":
                result.append(0x14)
            elif cell == "-":
                result.append(0x8C)
            elif cell == "－":
                result.append(0x9D)
            elif cell == "/":
                result.append(0x9E)
            elif cell in STOCK_CODES:
                result.append(STOCK_CODES[cell])
            elif "A" <= cell <= "Z":
                result.append(0x15 + ord(cell) - ord("A"))
            elif "a" <= cell <= "z":
                result.append(0x2F + ord(cell) - ord("a"))
            elif cell in glyph_indices:
                result.extend(glyph_code(glyph_indices[cell]))
            elif cell in BASELINE_KOREAN_GLYPHS:
                result.extend(baseline_glyph_code(BASELINE_KOREAN_GLYPHS[cell]))
            else:
                raise SystemExit(f"REFUSED: no glyph for {cell!r}")
        return bytes(result)

    official_records = build_report["campaign_briefings"]["records"]
    if len(official_records) != 44:
        raise SystemExit("REFUSED: official build report does not contain 44 records")

    # Scenario zero is redirected to one QA-only record.  The scenario marker
    # gets its own page, after which every original text slot and page-break
    # control is reproduced.  This avoids increasing any stock screen's row
    # topology (the first review build added a heading to the record itself and
    # overflowed scenario 4's six-row screen).
    review = bytearray()
    row_count = 0
    for scenario, entry in enumerate(translations):
        if int(entry["scenario"]) != scenario:
            raise SystemExit(f"REFUSED: translation index mismatch at {scenario}")
        heading = f"시나리오 {scenario:02d}"
        heading_payload = encode_text(heading)
        review.append(len(heading) - 1)
        review.extend(heading_payload)
        review.append(0x80)
        row_count += 1

        record = official_records[scenario]
        if "shared_with" in record:
            record = official_records[int(record["shared_with"])]
        controls = [int(value, 16) for value in record["original_controls"]]
        translated_index = 0
        text_control_indices = [
            index for index, control in enumerate(controls) if not control & 0x80
        ]
        for control_index, control in enumerate(controls):
            if control & 0x80:
                review.append(control)
                continue
            text = (
                entry["rows"][translated_index]
                if translated_index < len(entry["rows"])
                else " "
            )
            translated_index += 1
            if not 1 <= len(text) <= 20:
                raise SystemExit(
                    f"REFUSED: scenario {scenario} row width {len(text)}: {text!r}"
                )
            payload = encode_text(text)
            rebuilt_control = len(text) - 1
            if (
                scenario == 43
                and control_index == text_control_indices[-1]
            ):
                rebuilt_control |= 0x40
            review.append(rebuilt_control)
            review.extend(payload)
            row_count += 1
        if scenario != 43:
            review.append(0x80)

    packed = compress_lzss_literals(bytes(review))
    if BRIEFING_RELOCATED_BASE + len(packed) > RESERVED_END:
        raise SystemExit("REFUSED: review stream exceeds reserved briefing bank")
    rom = bytearray(source)
    rom[BRIEFING_RELOCATED_BASE:RESERVED_END] = b"\xFF" * (
        RESERVED_END - BRIEFING_RELOCATED_BASE
    )
    rom[BRIEFING_RELOCATED_BASE:BRIEFING_RELOCATED_BASE + len(packed)] = packed
    verified, verified_end = decompress_lzss(rom, BRIEFING_RELOCATED_BASE)
    if verified != bytes(review):
        raise SystemExit("REFUSED: review stream decompression mismatch")
    if verified_end != BRIEFING_RELOCATED_BASE + len(packed):
        raise SystemExit("REFUSED: review packed-size mismatch")

    rom[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 2] = b"\x00\x00"
    checksum = genesis_checksum(rom)
    rom[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 2] = checksum.to_bytes(2, "big")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rom)
    report = {
        "purpose": "QA-only sequential campaign briefing review ROM",
        "official_source": str(args.source),
        "source_sha256": sha256(source),
        "output_sha256": sha256(rom),
        "size": len(rom),
        "checksum": f"0x{checksum:04X}",
        "scenario_count": len(translations),
        "text_rows": row_count,
        "unpacked_size": len(review),
        "packed_size": len(packed),
        "entry": "CAMPAIGN -> STANDARD -> scenario 0; press A to advance",
        "distribution": "QA only; do not distribute as the normal game ROM",
    }
    args.output.with_suffix(args.output.suffix + ".build.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
