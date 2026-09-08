#!/usr/bin/env python3
"""Read-only audit of the original compact 8x8 font and known text tables."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


FONT_BASE = 0x3850E
FONT_SIZE = 0xA90
GLYPH_SIZE = 8
SAFE_CODE_END = 0xA7  # A7-FF are unsafe control/multibyte values.


def load_usage(path: Path) -> dict[int, int]:
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {int(row["code"], 16): int(row["uses"]) for row in rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    font = rom[FONT_BASE : FONT_BASE + FONT_SIZE]
    if len(font) != FONT_SIZE:
        raise SystemExit("ROM is too short for the original compact font")

    unit = load_usage(args.inventory / "all_unit_names-code-usage.json")
    armament = load_usage(args.inventory / "armament_names-code-usage.json")
    visible = load_usage(args.inventory / "unit_names_visible_range-code-usage.json")

    glyphs = [font[i : i + GLYPH_SIZE] for i in range(0, FONT_SIZE, GLYPH_SIZE)]
    duplicates: dict[bytes, list[int]] = defaultdict(list)
    for code in range(SAFE_CODE_END):
        duplicates[glyphs[code]].append(code)

    rows = []
    for code in range(SAFE_CODE_END):
        glyph = glyphs[code]
        known_uses = unit.get(code, 0) + armament.get(code, 0)
        rows.append(
            {
                "code": f"0x{code:02X}",
                "blank": not any(glyph),
                "glyph_sha256": hashlib.sha256(glyph).hexdigest().upper(),
                "duplicate_codes": [
                    f"0x{x:02X}" for x in duplicates[glyph] if x != code
                ],
                "unit_uses": unit.get(code, 0),
                "visible_unit_uses": visible.get(code, 0),
                "armament_uses": armament.get(code, 0),
                "known_table_uses": known_uses,
                "candidate_only": known_uses == 0,
            }
        )

    pointer = FONT_BASE.to_bytes(4, "big")
    pointer_refs = []
    start = 0
    while True:
        pos = rom.find(pointer, start)
        if pos < 0:
            break
        pointer_refs.append(f"0x{pos:06X}")
        start = pos + 1

    report = {
        "rom": str(args.rom),
        "rom_sha256": hashlib.sha256(rom).hexdigest().upper(),
        "font_base": f"0x{FONT_BASE:06X}",
        "font_size": FONT_SIZE,
        "glyph_size": GLYPH_SIZE,
        "glyph_count": len(glyphs),
        "audited_safe_range": "0x00-0xA6",
        "excluded_range": "0xA7-0xFF",
        "font_pointer_refs": pointer_refs,
        "rows": rows,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    candidates = [r for r in rows if r["candidate_only"]]
    blank = [r for r in candidates if r["blank"]]
    lines = [
        "# Original 8x8 font safety audit",
        "",
        f"- ROM SHA-256: `{report['rom_sha256']}`",
        f"- Font: `{report['font_base']}` / `{FONT_SIZE:#x}` bytes / {len(glyphs)} glyphs",
        "- Renderer-safe audit range: `0x00-0xA6`",
        "- Hard exclusion: `0xA7-0xFF` (control/multibyte regression proven)",
        f"- Direct ROM pointer references: {', '.join(pointer_refs) or 'none'}",
        f"- Codes unused by the known unit+armament tables: {len(candidates)}",
        f"- Blank codes among those candidates: {len(blank)}",
        "",
        "## Important limitation",
        "",
        "An unused code in the known unit and armament tables is only a candidate. "
        "It is not globally safe until every renderer path and dynamic/focus state using "
        "the shared font bank is traced.",
        "",
        "## Candidate codes",
        "",
        "`" + " ".join(r["code"] for r in candidates) + "`",
        "",
        "## Blank candidate codes",
        "",
        "`" + (" ".join(r["code"] for r in blank) or "none") + "`",
        "",
    ]
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
