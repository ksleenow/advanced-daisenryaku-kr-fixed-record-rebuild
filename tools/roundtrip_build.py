from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "out" / "original-roundtrip.md")
    args = parser.parse_args()

    cfg = json.loads((ROOT / "config" / "source.json").read_text(encoding="utf-8"))
    source = args.source.read_bytes()
    if len(source) != cfg["size"]:
        raise SystemExit(f"REFUSED: source size {len(source)} != {cfg['size']}")
    digest = sha256(source)
    if digest != cfg["sha256"]:
        raise SystemExit(f"REFUSED: unsupported source SHA-256 {digest}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    partial.write_bytes(source)
    if partial.read_bytes() != source:
        partial.unlink(missing_ok=True)
        raise SystemExit("REFUSED: output readback mismatch")
    os.replace(partial, args.output)

    report = {
        "source_sha256": digest,
        "output_sha256": sha256(args.output.read_bytes()),
        "size": len(source),
        "byte_identical": args.output.read_bytes() == source,
    }
    args.output.with_suffix(args.output.suffix + ".build.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

