#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

from subprocess import run


def main() -> None:
    p = argparse.ArgumentParser(description="Render individual synchronized comparison files for B0/B1/GRU/TCN.")
    p.add_argument("--sample-id", required=True)
    p.add_argument("--b1", type=Path, default=ROOT / "outputs" / "checkpoints" / "b1_static.npz")
    p.add_argument("--gru", type=Path, default=ROOT / "outputs" / "checkpoints" / "gru_best.pt")
    p.add_argument("--tcn", type=Path, default=ROOT / "outputs" / "checkpoints" / "tcn_best.pt")
    p.add_argument("--include-target-gnm", action="store_true")
    args = p.parse_args()
    jobs = [("b0", args.b1), ("b1", args.b1), ("gru", args.gru), ("tcn", args.tcn)]
    for model, ckpt in jobs:
        if model != "b0" and not ckpt.exists():
            continue
        cmd = [sys.executable, "scripts/predict_and_render.py", "--checkpoint", str(ckpt), "--sample-id", args.sample_id, "--model", model]
        if args.include_target_gnm: cmd.append("--include-target-gnm")
        run(cmd, check=True, cwd=ROOT)

if __name__ == "__main__": main()
