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

from voice_face.evaluation import evaluate_models


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate B0/B1/GRU/TCN on actor-held-out TrainingSequence records.")
    parser.add_argument("--records-dir", type=Path, default=ROOT / "data" / "processed" / "training_sequences")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "evaluation" / "metrics.json")
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--split", choices=["train", "val", "validation", "test"], default="test")
    parser.add_argument("--split-file", type=Path, default=None)
    parser.add_argument("--b1", type=Path, default=ROOT / "outputs" / "checkpoints" / "b1_static.npz")
    parser.add_argument("--gru", type=Path, default=ROOT / "outputs" / "checkpoints" / "gru_best.pt")
    parser.add_argument("--tcn", type=Path, default=ROOT / "outputs" / "checkpoints" / "tcn_best.pt")
    args = parser.parse_args()
    print(evaluate_models(args.records_dir, args.out, args.csv or args.out.with_suffix(".csv"), split=args.split, split_path=args.split_file, b1=args.b1 if args.b1.exists() else None, gru=args.gru if args.gru.exists() else None, tcn=args.tcn if args.tcn.exists() else None))


if __name__ == "__main__":
    main()
