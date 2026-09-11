from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONFIG = ROOT / "config" / "source.json"
SEEDS = ROOT / "config" / "inventory-seeds.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory fixed ROM record spans without modifying the source."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument(
        "--final-boundary",
        type=lambda value: int(value, 0),
        required=True,
        help="exclusive boundary after the final seeded record",
    )
    return parser.parse_args()


def tokenize_payload(payload: bytes) -> list[str]:
    """Split one-byte and FD/FE-prefixed two-byte glyph tokens."""
    tokens: list[str] = []
    index = 0
    while index < len(payload):
        if payload[index] in (0xFD, 0xFE):
            if index + 1 >= len(payload):
                tokens.append(f"{payload[index]:02X}!")
                break
            tokens.append(f"{payload[index]:02X} {payload[index + 1]:02X}")
            index += 2
        else:
            tokens.append(f"{payload[index]:02X}")
            index += 1
    return tokens


def glyph_indices(payload: bytes) -> list[str]:
    """Resolve record bytes to the physical glyph indices used by 0x81C8."""
    indices: list[str] = []
    index = 0
    while index < len(payload):
        code = payload[index]
        if code in (0xFD, 0xFE):
            if index + 1 >= len(payload):
                indices.append(f"0x{code:03X}!")
                break
            glyph_index = code + ((code - 0xFD) << 8) + payload[index + 1]
            indices.append(f"0x{glyph_index:03X}")
            index += 2
        else:
            indices.append(f"0x{code:03X}")
            index += 1
    return indices


def main() -> None:
    args = parse_args()
    source_config = json.loads(SOURCE_CONFIG.read_text(encoding="utf-8"))
    source = args.source.read_bytes()
    actual_hash = sha256(source)
    expected_hash = source_config["sha256"].upper()
    if actual_hash != expected_hash:
        raise SystemExit(f"source hash mismatch: {actual_hash} != {expected_hash}")

    seed_config = json.loads(SEEDS.read_text(encoding="utf-8"))
    try:
        entries = seed_config["groups"][args.group]
    except KeyError as error:
        raise SystemExit(f"unknown inventory group: {args.group}") from error

    addresses = [int(entry["address"], 0) for entry in entries]
    boundaries = addresses[1:] + [args.final_boundary]
    if any(start >= end for start, end in zip(addresses, boundaries)):
        raise SystemExit("seed addresses and final boundary must be strictly increasing")

    rows = []
    for entry, start, end in zip(entries, addresses, boundaries):
        record = source[start:end]
        declared_counter = record[0] if record else None
        payload = record[1:] if record else b""
        glyph_tokens = tokenize_payload(payload)
        rows.append(
            {
                "group": args.group,
                "label": entry["label"],
                "address": f"0x{start:06X}",
                "end_exclusive": f"0x{end:06X}",
                "byte_length": len(record),
                "declared_counter": declared_counter,
                "payload_cells_if_dbf": declared_counter + 1 if declared_counter is not None else None,
                "payload_byte_length": len(payload),
                "glyph_cells": len(glyph_tokens),
                "counter_matches_cells": declared_counter + 1 == len(glyph_tokens) if declared_counter is not None else False,
                "glyph_tokens": " | ".join(glyph_tokens),
                "glyph_indices": " | ".join(glyph_indices(payload)),
                "hex": record.hex(" ").upper(),
            }
        )

    output_dir = ROOT / "out" / "inventory"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{args.group}.json"
    csv_path = output_dir / f"{args.group}.csv"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps({
        "source_sha256": actual_hash,
        "group": args.group,
        "records": len(rows),
        "json": str(json_path),
        "csv": str(csv_path),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
