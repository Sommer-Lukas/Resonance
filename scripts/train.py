#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from dataclasses import asdict

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from voice_face.training import TrainConfig, load_train_config, train_records, train_static


def main() -> None:
    parser = argparse.ArgumentParser(description="Train B1 static, M1 GRU, or M2 TCN residual face models from TrainingSequence records.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--records-dir", type=Path, default=ROOT / "data" / "processed" / "training_sequences")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--model", choices=["b1", "gru", "tcn"], default=None)
    parser.add_argument("--split", type=Path, default=None)
    parser.add_argument("--resume", type=Path, default=None)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    config, loss_config, _ = load_train_config(args.config)
    model_name = args.model or config.model
    out = args.out or ROOT / "outputs" / "checkpoints" / ("b1_static.npz" if model_name == "b1" else f"{model_name}_best.pt")
    if model_name == "b1":
        print(train_static(args.records_dir, out, split_path=args.split))
    else:
        print(train_records(args.records_dir, out, TrainConfig(**{**asdict(config), "model": model_name}), loss_config, split_path=args.split, resume=args.resume, device=args.device))


if __name__ == "__main__":
    main()
