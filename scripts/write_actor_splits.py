#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from voice_face.dataset import assert_actor_independent, discover_fits, write_actor_splits


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist actor-independent train/val/test splits for fitted trajectories.")
    parser.add_argument("--fits-dir", type=Path, default=ROOT / "outputs" / "voice_face" / "fits")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "voice_face" / "actor_splits.json")
    args = parser.parse_args()
    splits = write_actor_splits(discover_fits(args.fits_dir), args.out)
    assert_actor_independent(splits)
    print(args.out)


if __name__ == "__main__":
    main()
