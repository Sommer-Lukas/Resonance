#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from voice_face.data.mead import index_mead, load_index_config, write_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Index MEAD mp4 files into a CSV manifest.")
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "raw" / "mead")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "voice_face" / "mead_index.csv")
    args = parser.parse_args()
    samples = index_mead(args.root, load_index_config(args.config))
    write_index(samples, args.out)
    print(f"indexed {len(samples)} videos -> {args.out}")


if __name__ == "__main__":
    main()
