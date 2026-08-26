#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import argparse

from voice_face.training import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trajectory baseline checkpoint.")
    parser.add_argument("--fits-dir", type=Path, default=ROOT / "outputs" / "voice_face" / "fits")
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "outputs" / "voice_face" / "model.pt")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "voice_face" / "eval.json")
    parser.add_argument("--split", choices=["train", "val", "test"], default="test")
    args = parser.parse_args()
    print(evaluate(args.fits_dir, args.checkpoint, args.out, split=args.split))


if __name__ == "__main__":
    main()
