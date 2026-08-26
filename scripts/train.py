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

from voice_face.losses import LossConfig
from voice_face.training import TrainConfig, train


def main() -> None:
    parser = argparse.ArgumentParser(description="Train B0/B1/B2 trajectory baselines.")
    parser.add_argument("--fits-dir", type=Path, default=ROOT / "outputs" / "voice_face" / "fits")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "voice_face" / "model.pt")
    parser.add_argument("--model", choices=["b0", "b1", "b2"], default="b0")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--loss-velocity", type=float, default=0.0)
    parser.add_argument("--loss-acceleration", type=float, default=0.0)
    parser.add_argument("--loss-residual-regularization", type=float, default=0.0)
    args = parser.parse_args()
    print(train(args.fits_dir, args.out, TrainConfig(args.model, args.epochs, args.lr), LossConfig(velocity=args.loss_velocity, acceleration=args.loss_acceleration, residual_regularization=args.loss_residual_regularization)))


if __name__ == "__main__":
    main()
