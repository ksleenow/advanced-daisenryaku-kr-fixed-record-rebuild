from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def glyph(data: bytes, base: int, index: int) -> Image.Image:
    raw = data[base + index * 32 : base + (index + 1) * 32]
    image = Image.new("1", (16, 16))
    pixels = image.load()
    for tile in range(4):
        tx, ty = (tile % 2) * 8, (tile // 2) * 8
        for row in range(8):
            value = raw[tile * 8 + row]
            for column in range(8):
                pixels[tx + column, ty + row] = bool(value & (0x80 >> column))
    return image.convert("RGB")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", type=lambda value: int(value, 0), default=0x3C86A)
    parser.add_argument("--start", type=lambda value: int(value, 0), default=0xA0)
    parser.add_argument("--end", type=lambda value: int(value, 0), default=0x140)
    args = parser.parse_args()
    data = args.source.read_bytes()
    scale, cell_w, cell_h, columns = 3, 70, 70, 8
    count = args.end - args.start
    rows = (count + columns - 1) // columns
    sheet = Image.new("RGB", (cell_w * columns, cell_h * rows), "#dddddd")
    draw = ImageDraw.Draw(sheet)
    for offset, index in enumerate(range(args.start, args.end)):
        x = (offset % columns) * cell_w
        y = (offset // columns) * cell_h
        tile = glyph(data, args.base, index).resize((16 * scale, 16 * scale), Image.Resampling.NEAREST)
        sheet.paste(tile, (x, y))
        draw.text((x, y + 50), f"{index:03X}", fill="black")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)


if __name__ == "__main__":
    main()
