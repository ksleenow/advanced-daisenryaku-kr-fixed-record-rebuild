from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = ROOT / "assets" / "unit-names-ko.json"
INVENTORY = ROOT / "out" / "inventory" / "all_unit_names.csv"
GLYPH_PATCHES = ROOT / "config" / "glyph-patches.json"
REPORT_JSON = ROOT / "out" / "unit-name-fixed8-audit.json"
REPORT_CSV = ROOT / "out" / "unit-name-fixed8-audit.csv"
OVERFLOW_CSV = ROOT / "out" / "unit-name-over-8-review.csv"


def encoded_cells(text: str) -> int:
    """The isolated gameplay codebook uses one byte per visible glyph."""
    return len(text)


def main() -> None:
    translations = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    glyph_config = json.loads(GLYPH_PATCHES.read_text(encoding="utf-8"))
    shared_targets = {
        patch["target"]
        for group in glyph_config["groups"].values()
        for patch in group
    }
    with INVENTORY.open(encoding="utf-8-sig", newline="") as handle:
        inventory = {row["index"]: row for row in csv.DictReader(handle)}

    rows = []
    for index_text, target in sorted(translations.items(), key=lambda item: int(item[0])):
        source = inventory[index_text]
        used = encoded_cells(target)
        missing = sorted({
            character for character in target
            if "\uac00" <= character <= "\ud7a3" and character not in shared_targets
        })
        rows.append({
            "index": int(index_text),
            "address": source["address"],
            "record_bytes": 8,
            "source_hex": source["name_hex"],
            "locator_label": source["locator_label"],
            "target": target,
            "encoded_bytes": used,
            "padding_bytes": max(0, 8 - used),
            "missing_shared_glyphs": "".join(missing),
            "status": (
                "review_required" if used > 8
                else "font_isolation_required" if missing
                else "ready"
            ),
        })

    REPORT_JSON.write_text(
        json.dumps({
            "rule": "one visible glyph = one isolated gameplay code byte; record remains exactly 8 bytes",
            "translated_records": len(rows),
            "ready_records": sum(row["status"] == "ready" for row in rows),
            "review_required_records": sum(row["status"] == "review_required" for row in rows),
            "font_isolation_required_records": sum(
                row["status"] == "font_isolation_required" for row in rows
            ),
            "missing_shared_glyphs": sorted({
                character
                for row in rows
                for character in row["missing_shared_glyphs"]
            }),
            "rows": rows,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    fields = list(rows[0])
    with REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with OVERFLOW_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(row for row in rows if row["status"] == "review_required")
    print(json.dumps({
        "translated": len(rows),
        "ready": sum(row["status"] == "ready" for row in rows),
        "review_required": sum(row["status"] == "review_required" for row in rows),
        "font_isolation_required": sum(
            row["status"] == "font_isolation_required" for row in rows
        ),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
