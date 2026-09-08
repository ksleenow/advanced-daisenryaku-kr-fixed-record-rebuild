from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def genesis_checksum(rom: bytes) -> int:
    return sum((rom[i] << 8) | rom[i + 1] for i in range(0x200, len(rom), 2)) & 0xFFFF


def render_8x8(character: str, font_path: Path) -> bytes:
    canvas = Image.new("L", (16, 16), 0)
    font = ImageFont.truetype(str(font_path), 16)
    draw = ImageDraw.Draw(canvas)
    box = draw.textbbox((0, 0), character, font=font)
    draw.text((-box[0], -box[1]), character, fill=255, font=font)
    pixels = canvas.load()
    return bytes(sum(0x80 >> x for x in range(8) if pixels[x, y]) for y in range(8))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an audited fixed 8-byte name patch")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--group", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    source_config = json.loads((ROOT / "config/source.json").read_text(encoding="utf-8"))
    table_config = json.loads((ROOT / "config/table-inventory.json").read_text(encoding="utf-8"))["groups"]
    font_config = json.loads((ROOT / "config/small-font-source.json").read_text(encoding="utf-8"))
    patch_config = json.loads((ROOT / "config/fixed-name-patches.json").read_text(encoding="utf-8"))
    source = args.source.read_bytes()
    parent_hash = sha256(source)
    if len(source) != source_config["size"] or parent_hash not in patch_config["allowed_parent_sha256"]:
        raise SystemExit("parent ROM verification failed")
    font_path = Path(font_config["path"])
    if sha256(font_path.read_bytes()) != font_config["sha256"]:
        raise SystemExit("8x8 font verification failed")
    group = patch_config["groups"][args.group]
    rom = bytearray(source)
    allowed: set[int] = {0x18E, 0x18F}
    report: list[dict[str, object]] = []

    font_base = int(patch_config["small_font_base"], 0)
    glyph_bytes = int(patch_config["glyph_bytes"])
    for glyph in group["glyphs"]:
        code = int(glyph["code"], 0)
        start = font_base + code * glyph_bytes
        replacement = render_8x8(glyph["target"], font_path)
        rom[start:start + glyph_bytes] = replacement
        allowed.update(range(start, start + glyph_bytes))
        report.append({"kind": "glyph", "code": f"0x{code:02X}", "target": glyph["target"], "address": f"0x{start:06X}"})

    for record_patch in group["records"]:
        table = table_config[record_patch["table"]]
        record_size = int(table["record_size"])
        if record_size != 8:
            raise SystemExit("this builder permits only exact eight-byte records")
        address = int(table["base"], 0) + int(record_patch["index"]) * record_size
        expected = bytes.fromhex(record_patch["expected_hex"])
        replacement = bytes.fromhex(record_patch["replacement_hex"])
        if len(expected) != record_size or len(replacement) != record_size:
            raise SystemExit("record length changed")
        if source[address:address + record_size] != expected:
            raise SystemExit(f"record preimage mismatch at 0x{address:06X}")
        rom[address:address + record_size] = replacement
        allowed.update(range(address, address + record_size))
        report.append({"kind": "record", "index": record_patch["index"], "display": record_patch["display"], "address": f"0x{address:06X}"})

    checksum = genesis_checksum(rom)
    rom[0x18E:0x190] = checksum.to_bytes(2, "big")
    changed = {i for i, pair in enumerate(zip(source, rom)) if pair[0] != pair[1]}
    unexpected = changed - allowed
    if unexpected:
        raise SystemExit(f"unexpected writes: {sorted(unexpected)[:16]}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rom)
    build_report = {
        "source_sha256": sha256(source), "output_sha256": sha256(rom), "size": len(rom),
        "checksum": f"0x{checksum:04X}", "changed_bytes": len(changed), "unexpected_changes": 0,
        "patches": report,
    }
    args.output.with_suffix(args.output.suffix + ".build.json").write_text(
        json.dumps(build_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(build_report, ensure_ascii=True))


if __name__ == "__main__":
    main()
