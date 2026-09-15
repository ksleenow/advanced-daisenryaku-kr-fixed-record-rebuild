from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def render_glyph(character: str, font_path: Path) -> bytes:
    # This is the previously accepted 16x16 UI rendering recipe. It keeps the
    # visible bitmap inside the stock four-tile cell without changing geometry.
    canvas = Image.new("L", (16, 16), 0)
    font = ImageFont.truetype(str(font_path), 21)
    draw = ImageDraw.Draw(canvas)
    box = draw.textbbox((0, 0), character, font=font)
    draw.text(
        ((16 - (box[2] - box[0])) // 2 - box[0],
         (16 - (box[3] - box[1])) // 2 - box[1]),
        character, fill=255, font=font,
    )

    result = bytearray()
    pixels = canvas.load()
    for tile in range(4):
        tile_x = (tile % 2) * 8
        tile_y = (tile // 2) * 8
        for row in range(8):
            value = 0
            for column in range(8):
                if pixels[tile_x + column, tile_y + row] >= 96:
                    value |= 0x80 >> column
            result.append(value)
    return bytes(result)


def render_small_glyph(character: str, font_path: Path) -> bytes:
    """Render the user-approved M8x8 bitmap without resampling."""
    canvas = Image.new("L", (16, 16), 0)
    font = ImageFont.truetype(str(font_path), 16)
    draw = ImageDraw.Draw(canvas)
    box = draw.textbbox((0, 0), character, font=font)
    draw.text((-box[0], -box[1]), character, fill=255, font=font)
    pixels = canvas.crop((0, 0, 8, 8)).load()
    return bytes(
        sum((0x80 >> column) for column in range(8) if pixels[column, row])
        for row in range(8)
    )


def genesis_checksum(rom: bytes) -> int:
    total = 0
    for offset in range(0x200, len(rom), 2):
        word = rom[offset] << 8
        if offset + 1 < len(rom):
            word |= rom[offset + 1]
        total = (total + word) & 0xFFFF
    return total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--group", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--small-font-index",
        action="append",
        default=[],
        help="explicit record-safe 8x8 glyph index (repeatable; 0x00-0xA6 only)",
    )
    args = parser.parse_args()

    source_config = json.loads((ROOT / "config/source.json").read_text(encoding="utf-8"))
    font_config = json.loads((ROOT / "config/font-source.json").read_text(encoding="utf-8"))
    small_font_config = json.loads(
        (ROOT / "config/small-font-source.json").read_text(encoding="utf-8")
    )
    patch_config = json.loads((ROOT / "config/glyph-patches.json").read_text(encoding="utf-8"))
    source = args.source.read_bytes()
    if sha256(source) != source_config["sha256"]:
        raise SystemExit("Japanese source hash mismatch")

    font_path = Path(font_config["path"])
    font_data = font_path.read_bytes()
    if sha256(font_data) != font_config["sha256"]:
        raise SystemExit("font source hash mismatch")
    small_font_path = Path(small_font_config["path"])
    small_font_data = small_font_path.read_bytes()
    if sha256(small_font_data) != small_font_config["sha256"]:
        raise SystemExit("small font source hash mismatch")

    patches = []
    for group in args.group:
        try:
            patches.extend(patch_config["groups"][group])
        except KeyError as error:
            raise SystemExit(f"unknown glyph group: {group}") from error

    small_font_indices = {int(value, 0) for value in args.small_font_index}
    unsafe_small = sorted(index for index in small_font_indices if not 0 <= index < 0xA7)
    if unsafe_small:
        raise SystemExit(
            "unsafe 8x8 record code(s): "
            + ", ".join(f"0x{index:02X}" for index in unsafe_small)
        )

    font_base = int(patch_config["font_base"], 0)
    glyph_bytes = int(patch_config["glyph_bytes"])
    rom = bytearray(source)
    changed_ranges = []
    seen: dict[int, str] = {}
    for patch in patches:
        index = int(patch["index"], 0)
        prior = seen.get(index)
        if prior is not None:
            if prior != patch["target"]:
                raise SystemExit(
                    f"conflicting targets for glyph 0x{index:03X}: "
                    f"{prior!r} and {patch['target']!r}"
                )
            continue
        seen[index] = patch["target"]
        start = font_base + index * glyph_bytes
        end = start + glyph_bytes
        replacement = render_glyph(patch["target"], font_path)
        if len(replacement) != glyph_bytes:
            raise SystemExit("rendered glyph has unexpected size")
        rom[start:end] = replacement
        changed_ranges.append({
            "font": "16x16",
            "source": patch["source"], "target": patch["target"],
            "index": f"0x{index:03X}", "start": f"0x{start:06X}",
            "end_exclusive": f"0x{end:06X}"
        })
        # The original 68K loaders upload exactly 0x548 bytes: 169 compact
        # glyphs (codes 00-A8).  Codes A7 and above remain prohibited in text
        # records because runtime tests proved control/multibyte collisions.
        # Never mirror 16x16 patches into this bank implicitly.
        if index in small_font_indices:
            small_start = 0x3850E + index * 8
            small_end = small_start + 8
            rom[small_start:small_end] = render_small_glyph(
                patch["target"], small_font_path
            )
            changed_ranges.append({
                "font": "8x8",
                "source": patch["source"], "target": patch["target"],
                "index": f"0x{index:03X}", "start": f"0x{small_start:06X}",
                "end_exclusive": f"0x{small_end:06X}"
            })

    missing_small = sorted(small_font_indices - set(seen))
    if missing_small:
        raise SystemExit(
            "requested 8x8 index has no selected glyph patch: "
            + ", ".join(f"0x{index:02X}" for index in missing_small)
        )

    checksum = genesis_checksum(rom)
    rom[0x18E:0x190] = checksum.to_bytes(2, "big")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rom)

    allowed = {0x18E, 0x18F}
    for item in changed_ranges:
        allowed.update(range(int(item["start"], 0), int(item["end_exclusive"], 0)))
    actual_changed = {index for index, (before, after) in enumerate(zip(source, rom)) if before != after}
    unexpected = sorted(actual_changed - allowed)
    if unexpected:
        args.output.unlink(missing_ok=True)
        raise SystemExit(f"unexpected changed bytes: {unexpected[:16]}")

    report = {
        "source_sha256": sha256(source), "output_sha256": sha256(rom),
        "size": len(rom), "checksum": f"0x{checksum:04X}",
        "changed_byte_count": len(actual_changed), "unexpected_changes": 0,
        "records_modified": 0, "glyph_patches": changed_ranges,
    }
    report_path = args.output.with_suffix(args.output.suffix + ".build.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Keep console output compatible with the Korean Windows code page; the
    # UTF-8 report file above retains the actual Japanese/Korean characters.
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
