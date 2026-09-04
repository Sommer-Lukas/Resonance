#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import argparse, csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

import numpy as np
from voice_face.evaluation import predict_record
from voice_face.gnm.load import load_gnm
from voice_face.rendering import render_side_by_side
from voice_face.training_records import load_training_sequence


def _find_sample(index: Path, sample_id: str) -> dict[str, str]:
    with index.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["sample_id"] == sample_id:
                return row
    raise SystemExit(f"sample not found: {sample_id}")


def main() -> None:
    p = argparse.ArgumentParser(description="Predict and render a held-out MEAD comparison without using target video for prediction.")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--sample-id", required=True)
    p.add_argument("--model", choices=["gru", "tcn", "b1", "b0"], default=None)
    p.add_argument("--records-dir", type=Path, default=ROOT / "data" / "processed" / "training_sequences")
    p.add_argument("--fits-dir", type=Path, default=ROOT / "data" / "processed" / "gnm" / "sequences")
    p.add_argument("--index", type=Path, default=ROOT / "outputs" / "voice_face" / "mead_index.csv")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--include-target-gnm", action="store_true")
    p.add_argument("--size", type=int, default=320)
    p.add_argument("--preserve-mouth", type=float, default=0.0)
    p.add_argument("--smooth-alpha", type=float, default=0.0)
    args = p.parse_args()
    model = args.model or ("tcn" if "tcn" in args.checkpoint.name else "gru" if "gru" in args.checkpoint.name else "b1")
    seq_path = args.records_dir / f"{args.sample_id}.npz"; fit_path = args.fits_dir / f"{args.sample_id}.npz"
    seq = load_training_sequence(seq_path); fit = np.load(fit_path, allow_pickle=False); meta = json.loads(str(fit["metadata"]))
    pred = predict_record(model, None if model == "b0" else args.checkpoint, seq_path, preserve_mouth=args.preserve_mouth, smooth_alpha=args.smooth_alpha)
    out = args.out or ROOT / "outputs" / "comparisons" / f"{args.sample_id}_{model}.mp4"
    target = fit["expression_smoothed"] if args.include_target_gnm else None
    render_side_by_side(Path(meta["source_video"]), pred, fit["identity"], fit["rotation"], fit["translation"], out, load_gnm(), target_expression=target, fps=float(meta.get("fps", 30.0)), size=args.size, label=f"Emotion: {seq.emotion} Intensity: {seq.intensity} Model: {model.upper()}")
    print(out)

if __name__ == "__main__": main()
