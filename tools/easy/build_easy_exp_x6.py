#!/usr/bin/env python3
"""Apply the verified USER-only x6 combat-experience patch.

The input must already contain the verified V1 unit-cap, starting-funds and
EASY VER logo changes. ROMs are local inputs/outputs and must not be committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_SOURCE_SHA256 = "BB42981C0187D09B6EC3BD0BECF4A616D598A1046D7EA40CDC0BEE7BA8346925"
PATCH_OFFSET = 0x00DFEE
EXPECTED_PATCH_SITE = bytes.fromhex("DD2A000E61000004")
HOOK_OFFSET = 0x001E0000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def fix_checksum(data: bytearray) -> int:
    data[0x18E:0x190] = b"\0\0"
    value = sum(
        int.from_bytes(data[i:i + 2], "big")
        for i in range(0x200, len(data), 2)
    ) & 0xFFFF
    data[0x18E:0x190] = value.to_bytes(2, "big")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="verified EASY VER logo ROM")
    parser.add_argument("output", type=Path, help="final EASY VER ROM")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--expected-source-sha256",
        default=EXPECTED_SOURCE_SHA256,
        help="change only after a new base-version audit",
    )
    args = parser.parse_args()

    source = args.source.read_bytes()
    source_hash = sha256(source)
    if source_hash != args.expected_source_sha256.upper():
        raise SystemExit(
            "source SHA-256 mismatch; do not reuse V1 offsets without re-audit: "
            + source_hash
        )

    rom = bytearray(source)
    actual = bytes(rom[PATCH_OFFSET:PATCH_OFFSET + len(EXPECTED_PATCH_SITE)])
    if actual != EXPECTED_PATCH_SITE:
        raise SystemExit(
            f"experience site mismatch at 0x{PATCH_OFFSET:X}: {actual.hex().upper()}"
        )

    # A2 is the receiving unit. A2+0x0F is its faction index. Resolve the
    # runtime faction table and multiply only controller USER(1).
    hook = bytes.fromhex(
        "2F002F08"          # save d0/a0
        "7000"              # d0 = 0
        "102A000F"          # d0.b = receiving unit faction
        "C0FC0020"          # faction record size = 0x20
        "41F8C800"          # a0 = runtime faction table
        "0C3000010009"      # controller byte +9 == USER(1)?
        "660A"              # no: retain original award
        "70001006C0FC0006"  # yes: unsigned original D6 * 6
        "6004"
        "70001006"          # COM/neutral: original D6
        "205F"              # restore a0
        "D12A000E"          # add award to unit experience
        "4CDF0001"          # restore d0 without altering carry
        "4EB90000DFF8"      # original cap-to-250 helper
        "4E75"
    )
    if any(value != 0xFF for value in rom[HOOK_OFFSET:HOOK_OFFSET + len(hook)]):
        raise SystemExit("reserved hook area is not empty")

    rom[HOOK_OFFSET:HOOK_OFFSET + len(hook)] = hook
    replacement = (
        bytes.fromhex("4EB9")
        + HOOK_OFFSET.to_bytes(4, "big")
        + bytes.fromhex("4E71")
    )
    rom[PATCH_OFFSET:PATCH_OFFSET + len(EXPECTED_PATCH_SITE)] = replacement
    checksum = fix_checksum(rom)

    allowed = set(range(0x18E, 0x190))
    allowed.update(range(PATCH_OFFSET, PATCH_OFFSET + len(EXPECTED_PATCH_SITE)))
    allowed.update(range(HOOK_OFFSET, HOOK_OFFSET + len(hook)))
    changed = {i for i, (old, new) in enumerate(zip(source, rom)) if old != new}
    unexpected = sorted(changed - allowed)
    if unexpected:
        raise SystemExit(f"unexpected changed byte at 0x{unexpected[0]:X}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rom)
    report = {
        "source_sha256": source_hash,
        "output_sha256": sha256(rom),
        "size": len(rom),
        "checksum": f"0x{checksum:04X}",
        "feature": "USER combat experience x6",
        "com_behavior": "unchanged",
        "experience_cap": 250,
        "patch_offset": f"0x{PATCH_OFFSET:X}",
        "hook_offset": f"0x{HOOK_OFFSET:X}",
        "hook_length": len(hook),
    }
    manifest = args.manifest or args.output.with_suffix(".manifest.json")
    manifest.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

