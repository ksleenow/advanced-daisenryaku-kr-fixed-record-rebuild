from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_glyph_patch import genesis_checksum, render_glyph, render_small_glyph


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "AADA45EA1708A80C8E7F504DADFA5D15CC82B51CE9743E8B70187DD013F17917"
UNIT_BASE = 0x02B368
UNIT_STRIDE = 0x22
NAME_SIZE = 8
BLANK_CODE = 0

# Expansion-only assets.  The copied renderer keeps all original relative
# branches intact; its final BSR lands on the appended jump back to $00820C.
RENDERER_BASE = 0x1D0000
RENDERER_SOURCE_START = 0x008124
RENDERER_SOURCE_END = 0x00820C
RENDERER_8_ENTRY = RENDERER_BASE + (0x008162 - RENDERER_SOURCE_START)
RENDERER_16_ENTRY = RENDERER_BASE + (0x00816A - RENDERER_SOURCE_START)
WRAPPER_8 = 0x1D0100
WRAPPER_16 = 0x1D0120
WRAPPER_8_HUD = 0x1D0140
WRAPPER_8_LIST = 0x1D0160
DISPATCHER_8 = 0x1D0200
FONT8_BASE = 0x1D1000
FONT16_BASE = 0x1D2000

HOOK_8 = 0x00FBC8
HOOK_8_HUD = 0x00C8B0
HOOK_8_LIST = 0x00C870
HOOK_16 = 0x00CD04
HOOK_8_EXPECTED = bytes.fromhex("6100 855A D2FC")
HOOK_8_HUD_EXPECTED = bytes.fromhex("6100 B872 5489")
HOOK_8_LIST_EXPECTED = bytes.fromhex("6100 B8B2 205F")
HOOK_16_EXPECTED = bytes.fromhex("6100 B464 43F9")

FONT16_PATH = Path(json.loads((ROOT / "config/font-source.json").read_text(encoding="utf-8"))["path"])
FONT8_PATH = Path(json.loads((ROOT / "config/small-font-source.json").read_text(encoding="utf-8"))["path"])


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def jmp(address: int) -> bytes:
    return bytes.fromhex("4EF9") + address.to_bytes(4, "big")


def jsr(address: int) -> bytes:
    return bytes.fromhex("4EB9") + address.to_bytes(4, "big")


def build_private_8_dispatcher() -> bytes:
    """Route translated fixed records to the private font, all others stock.

    The audited translation set currently consists of two address ranges.
    This guard is essential: a private one-byte code has a different meaning
    from the original Japanese code, so globally redirecting untouched records
    makes every non-translated unit name render as garbage.
    """
    range1_start = UNIT_BASE + 560 * UNIT_STRIDE
    range1_end = UNIT_BASE + 564 * UNIT_STRIDE
    range2_start = UNIT_BASE + 608 * UNIT_STRIDE
    range2_end = UNIT_BASE + 669 * UNIT_STRIDE

    code = bytearray()
    fixups: list[tuple[int, str]] = []
    labels: dict[str, int] = {}

    def cmpa(address: int) -> None:
        code.extend(bytes.fromhex("B1FC") + address.to_bytes(4, "big"))

    def bcs(label: str) -> None:
        code.extend(bytes.fromhex("6500"))
        fixups.append((len(code), label))
        code.extend(b"\x00\x00")

    cmpa(range1_start)
    bcs("check_second")
    cmpa(range1_end)
    bcs("private")
    labels["check_second"] = len(code)
    cmpa(range2_start)
    bcs("stock")
    cmpa(range2_end)
    bcs("private")
    labels["stock"] = len(code)
    code.extend(jsr(0x008162))
    code.extend(bytes.fromhex("4E75"))
    labels["private"] = len(code)
    code.extend(jsr(RENDERER_8_ENTRY))
    code.extend(bytes.fromhex("4E75"))

    for displacement_at, label in fixups:
        # 68000 word branches are relative to the extension-word address
        # (instruction address + 2), not to the end of that word.
        displacement = labels[label] - displacement_at
        code[displacement_at:displacement_at + 2] = displacement.to_bytes(2, "big", signed=True)
    return bytes(code)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--all", action="store_true", help="patch every audited unit name; default is index 623 only")
    args = parser.parse_args()

    source = args.source.read_bytes()
    if sha256(source) != SOURCE_SHA256:
        raise SystemExit("source must be the approved v076 checkpoint")
    rom = bytearray(source)
    translations = json.loads((ROOT / "assets/unit-names-ko.json").read_text(encoding="utf-8"))
    selected = translations if args.all else {"623": translations["623"]}

    characters = sorted({character for text in selected.values() for character in text})
    if len(characters) > 0xFE:
        raise SystemExit("private one-byte codebook is exhausted")
    code_for = {character: index + 1 for index, character in enumerate(characters)}

    # Build isolated font banks. Code 0 is deliberately blank padding.
    rom[FONT8_BASE:FONT8_BASE + 0x800] = bytes(0x800)
    rom[FONT16_BASE:FONT16_BASE + 0x2000] = bytes(0x2000)
    for character, code in code_for.items():
        rom[FONT8_BASE + code * 8:FONT8_BASE + (code + 1) * 8] = render_small_glyph(character, FONT8_PATH)
        rom[FONT16_BASE + code * 32:FONT16_BASE + (code + 1) * 32] = render_glyph(character, FONT16_PATH)

    patched_records = []
    for index_text, text in sorted(selected.items(), key=lambda item: int(item[0])):
        encoded = bytes(code_for[character] for character in text)
        if len(encoded) > NAME_SIZE:
            raise SystemExit(f"unit {index_text} exceeds the fixed 8-byte record: {text}")
        address = UNIT_BASE + int(index_text) * UNIT_STRIDE
        rom[address:address + NAME_SIZE] = encoded + bytes([BLANK_CODE]) * (NAME_SIZE - len(encoded))
        patched_records.append({"index": int(index_text), "address": f"0x{address:06X}", "text": text, "bytes": encoded.hex(" ").upper()})

    renderer = bytearray(source[RENDERER_SOURCE_START:RENDERER_SOURCE_END])
    # The LEA absolute-long operands begin at $8146/$81E2. Keep the opcodes
    # and the following MULU instructions byte-identical to the approved ROM.
    renderer[0x008146 - RENDERER_SOURCE_START:0x00814A - RENDERER_SOURCE_START] = FONT8_BASE.to_bytes(4, "big")
    renderer[0x0081E2 - RENDERER_SOURCE_START:0x0081E6 - RENDERER_SOURCE_START] = FONT16_BASE.to_bytes(4, "big")
    rom[RENDERER_BASE:RENDERER_BASE + len(renderer)] = renderer
    rom[RENDERER_BASE + len(renderer):RENDERER_BASE + len(renderer) + 6] = jmp(0x00820C)
    dispatcher8 = build_private_8_dispatcher()
    rom[DISPATCHER_8:DISPATCHER_8 + len(dispatcher8)] = dispatcher8

    if bytes(rom[HOOK_8:HOOK_8 + 6]) != HOOK_8_EXPECTED:
        raise SystemExit("8x8 unit-name hook bytes differ from approved v076")
    if bytes(rom[HOOK_8_HUD:HOOK_8_HUD + 6]) != HOOK_8_HUD_EXPECTED:
        raise SystemExit("8x8 HUD unit-name hook bytes differ from approved v076")
    if bytes(rom[HOOK_8_LIST:HOOK_8_LIST + 6]) != HOOK_8_LIST_EXPECTED:
        raise SystemExit("8x8 list unit-name hook bytes differ from approved v076")
    if bytes(rom[HOOK_16:HOOK_16 + 6]) != HOOK_16_EXPECTED:
        raise SystemExit("16x16 unit-name hook bytes differ from approved v076")

    # The six-byte JMP replaces the original BSR plus the first word of the
    # following instruction. Each wrapper reproduces that instruction before
    # returning to the first untouched address.
    rom[HOOK_8:HOOK_8 + 6] = jmp(WRAPPER_8)
    wrapper8 = jsr(DISPATCHER_8) + bytes.fromhex("D2FC 0072") + jmp(0x00FBD0)
    rom[WRAPPER_8:WRAPPER_8 + len(wrapper8)] = wrapper8

    # Main-map HUD and the unit-list screen use two additional direct calls
    # to the same stock renderer. Keep their displaced instruction exactly,
    # while routing only the unit-name draw through the isolated 8x8 bank.
    rom[HOOK_8_HUD:HOOK_8_HUD + 6] = jmp(WRAPPER_8_HUD)
    wrapper8_hud = jsr(DISPATCHER_8) + bytes.fromhex("5489") + jmp(0x00C8B6)
    rom[WRAPPER_8_HUD:WRAPPER_8_HUD + len(wrapper8_hud)] = wrapper8_hud

    rom[HOOK_8_LIST:HOOK_8_LIST + 6] = jmp(WRAPPER_8_LIST)
    wrapper8_list = jsr(DISPATCHER_8) + bytes.fromhex("205F") + jmp(0x00C876)
    rom[WRAPPER_8_LIST:WRAPPER_8_LIST + len(wrapper8_list)] = wrapper8_list

    rom[HOOK_16:HOOK_16 + 6] = jmp(WRAPPER_16)
    wrapper16 = jsr(RENDERER_16_ENTRY) + bytes.fromhex("43F9 00FF82A8") + jmp(0x00CD0E)
    rom[WRAPPER_16:WRAPPER_16 + len(wrapper16)] = wrapper16

    rom[0x18E:0x190] = b"\x00\x00"
    rom[0x18E:0x190] = genesis_checksum(rom).to_bytes(2, "big")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rom)

    manifest = {
        "source": str(args.source),
        "source_sha256": SOURCE_SHA256,
        "output": str(args.output),
        "output_sha256": sha256(rom),
        "mode": "all" if args.all else "proof-index-623",
        "fixed_record_bytes": NAME_SIZE,
        "private_codebook": {character: f"0x{code:02X}" for character, code in code_for.items()},
        "patched_records": patched_records,
        "hooks": {
            "8x8-production": f"0x{HOOK_8:06X}",
            "8x8-hud": f"0x{HOOK_8_HUD:06X}",
            "8x8-list": f"0x{HOOK_8_LIST:06X}",
            "16x16": f"0x{HOOK_16:06X}",
        },
    }
    args.output.with_suffix(args.output.suffix + ".json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
