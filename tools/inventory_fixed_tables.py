from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONFIG = ROOT / "config" / "source.json"
TABLE_CONFIG = ROOT / "config" / "table-inventory.json"
LOCATOR_CONFIG = ROOT / "config" / "locator-reference.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def number(value: int | str) -> int:
    return value if isinstance(value, int) else int(value, 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only fixed-table inventory")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--group", required=True)
    parser.add_argument("--locator", type=Path)
    return parser.parse_args()


def decode_latin_name(data: bytes) -> str:
    punctuation = {0x9B: ".", 0x9C: ":", 0x9D: "-", 0x9F: ",", 0xA5: "mm", 0xA6: "kg"}
    output: list[str] = []
    for code in data:
        if code <= 9:
            output.append(str(code))
        elif code == 0x14:
            output.append(" ")
        elif 0x15 <= code <= 0x2E:
            output.append(chr(ord("A") + code - 0x15))
        elif 0x2F <= code <= 0x48:
            output.append(chr(ord("a") + code - 0x2F))
        else:
            output.append(punctuation.get(code, f"<{code:02X}>"))
    return "".join(output).rstrip()


def main() -> None:
    args = parse_args()
    source = args.source.read_bytes()
    expected = json.loads(SOURCE_CONFIG.read_text(encoding="utf-8"))
    actual_hash = sha256(source)
    if len(source) != expected["size"] or actual_hash != expected["sha256"]:
        raise SystemExit("immutable Japanese source verification failed")

    config = json.loads(TABLE_CONFIG.read_text(encoding="utf-8"))["groups"]
    if args.group not in config:
        raise SystemExit(f"unknown group: {args.group}")
    group = config[args.group]
    base = number(group["base"])
    count = number(group["count"])
    record_size = number(group["record_size"])
    name_offset = number(group["name_offset"])
    name_size = number(group["name_size"])
    first_index = number(group.get("first_index", 0))

    locator = None
    if args.locator:
        locator = args.locator.read_bytes()
        locator_config = json.loads(LOCATOR_CONFIG.read_text(encoding="utf-8"))
        if len(locator) != locator_config["size"] or sha256(locator) != locator_config["sha256"]:
            raise SystemExit("English locator reference verification failed")

    rows: list[dict[str, object]] = []
    usage: collections.Counter[int] = collections.Counter()
    for relative_index in range(count):
        index = first_index + relative_index
        address = base + relative_index * record_size
        record = source[address : address + record_size]
        name = record[name_offset : name_offset + name_size]
        usage.update(name)
        rows.append({
            "index": index,
            "address": f"0x{address:06X}",
            "record_size": len(record),
            "name_size": len(name),
            "name_hex": name.hex(" ").upper(),
            "record_hex": record.hex(" ").upper(),
            "locator_differs": locator is not None and locator[address + name_offset : address + name_offset + name_size] != name,
            "locator_label": decode_latin_name(locator[address + name_offset : address + name_offset + name_size]) if locator is not None else "",
        })

    out = ROOT / "out" / "inventory"
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{args.group}.json"
    csv_path = out / f"{args.group}.csv"
    usage_path = out / f"{args.group}-code-usage.json"
    json_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    usage_path.write_text(json.dumps(
        [{"code": f"0x{code:02X}", "uses": uses} for code, uses in sorted(usage.items())],
        indent=2,
    ) + "\n", encoding="utf-8")
    print(json.dumps({
        "group": args.group,
        "records": len(rows),
        "source_sha256": actual_hash,
        "table_start": f"0x{base:06X}",
        "table_end": f"0x{base + count * record_size:06X}",
        "distinct_name_codes": len(usage),
    }))


if __name__ == "__main__":
    main()
