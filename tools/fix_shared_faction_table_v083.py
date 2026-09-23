from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "out/project-05-campaign-briefings-v076.md"
OUTPUT = ROOT / "out/project-06-faction-display-split-v083.md"
REPORT = OUTPUT.with_suffix(OUTPUT.suffix + ".build.json")

EXPECTED_SOURCE_SHA256 = "AADA45EA1708A80C8E7F504DADFA5D15CC82B51CE9743E8B70187DD013F17917"
FACTION_POINTER_OPERAND = 0x0065C9
ORIGINAL_FACTION_TABLE = 0x0233F1
HELPER = 0x149400
CHECKSUM = 0x18E


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def genesis_checksum(data: bytes) -> int:
    return sum(
        int.from_bytes(data[pos:pos + 2], "big")
        for pos in range(0x200, len(data) - 1, 2)
    ) & 0xFFFF


def build_helper() -> bytes:
    """Decode the pre-game country buffer without changing the shared table.

    The stock renderer enters with A0 pointing at the current byte and expects
    D4 plus the condition codes from CMPI.B #$FD,D4.  After MOVE.B (A0)+,D4,
    A0 identifies one of the eight fixed display cells at $FFC810..$FFC817.
    Only when the buffer still begins with the stock German record ($75) do we
    substitute four Korean glyph indices and four stock blank cells.
    """
    code = bytearray()
    labels: dict[str, int] = {}
    branches: list[tuple[int, str]] = []

    def label(name: str) -> None:
        labels[name] = len(code)

    def branch(opcode: int, target: str) -> None:
        code.extend((opcode, 0))
        branches.append((len(code) - 1, target))

    code.extend(bytes.fromhex("7800 1818"))          # MOVEQ #0,D4 / MOVE.B (A0)+,D4
    code.extend(bytes.fromhex("0C38 0075 C810"))     # stock German buffer guard
    branch(0x66, "normal")                           # BNE.S

    # A0 points one byte beyond the cell just consumed.
    targets = (
        (0x00FFC811, "dok"), (0x00FFC812, "blank"),
        (0x00FFC813, "il"),  (0x00FFC814, "blank"),
        (0x00FFC815, "je"),  (0x00FFC816, "blank"),
        (0x00FFC817, "guk"), (0x00FFC818, "blank"),
    )
    for address, target in targets:
        code.extend(bytes.fromhex("B1FC") + address.to_bytes(4, "big"))
        branch(0x67, target)                          # BEQ.S

    label("normal")
    code.extend(bytes.fromhex("0C04 00FD 4E75"))     # stock CMPI.B / RTS

    for name, index in (
        ("dok", 0x1D4), ("il", 0x1D6), ("je", 0x06F),
        ("guk", 0x2E5), ("blank", 0x014),
    ):
        label(name)
        code.extend(bytes.fromhex("383C") + index.to_bytes(2, "big"))
        branch(0x60, "normal")

    for pos, target in branches:
        displacement = labels[target] - (pos + 1)
        if not -128 <= displacement <= 127:
            raise SystemExit(f"branch to {target} exceeds byte range")
        code[pos] = displacement & 0xFF
    return bytes(code)


def main() -> None:
    source = SOURCE.read_bytes()
    if sha256(source) != EXPECTED_SOURCE_SHA256:
        raise SystemExit("REFUSED: v076 source hash mismatch")
    rom = bytearray(source)

    if bytes(rom[FACTION_POINTER_OPERAND:FACTION_POINTER_OPERAND + 3]) != bytes.fromhex("14 90 00"):
        raise SystemExit("REFUSED: shared faction pointer is not the v076 clone")
    rom[FACTION_POINTER_OPERAND:FACTION_POINTER_OPERAND + 3] = ORIGINAL_FACTION_TABLE.to_bytes(3, "big")

    helper = build_helper()
    rom[HELPER:HELPER + len(helper)] = helper
    rom[CHECKSUM:CHECKSUM + 2] = b"\0\0"
    checksum = genesis_checksum(rom)
    rom[CHECKSUM:CHECKSUM + 2] = checksum.to_bytes(2, "big")

    OUTPUT.write_bytes(rom)
    changed = [i for i, (a, b) in enumerate(zip(source, rom)) if a != b]
    allowed = set(range(CHECKSUM, CHECKSUM + 2))
    allowed.update(range(FACTION_POINTER_OPERAND, FACTION_POINTER_OPERAND + 3))
    allowed.update(range(HELPER, HELPER + len(helper)))
    unexpected = sorted(set(changed) - allowed)
    if unexpected:
        raise SystemExit(f"REFUSED: unexpected change at 0x{unexpected[0]:06X}")

    report = {
        "source": str(SOURCE),
        "source_sha256": sha256(source),
        "output": str(OUTPUT),
        "output_sha256": sha256(rom),
        "size": len(rom),
        "checksum": f"0x{checksum:04X}",
        "changed_byte_count": len(changed),
        "shared_faction_table": f"0x{ORIGINAL_FACTION_TABLE:06X}",
        "pregame_buffer": "0xFFC810..0xFFC817",
        "pregame_text": "독 일 제 국",
        "helper": f"0x{HELPER:06X}",
        "helper_size": len(helper),
        "unexpected_changes": 0,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
