#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import argparse, csv, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from voice_face.audio_mouth import fit_audio_mouth_model


def main() -> None:
    p = argparse.ArgumentParser(description="Train lightweight audio->mouth regression from fitted clips.")
    p.add_argument("--index", type=Path, default=ROOT / "outputs" / "voice_face" / "mead_index.csv")
    p.add_argument("--fit-dir", type=Path, default=ROOT / "data" / "processed" / "gnm" / "sequences")
    p.add_argument("--out", type=Path, default=ROOT / "outputs" / "checkpoints" / "audio_mouth.npz")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--feature-mode", choices=["prosody", "wavlm"], default="wavlm")
    p.add_argument("--cache-dir", type=Path, default=ROOT / "outputs" / "cache" / "wavlm_base_plus")
    p.add_argument("--model-id", default="microsoft/wavlm-base-plus")
    args = p.parse_args()
    pairs = []
    with args.index.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            fit = args.fit_dir / f"{row['sample_id']}.npz"
            audio = Path(row["audio_path"])
            if fit.exists() and audio.exists():
                pairs.append((fit, audio))
            if args.limit and len(pairs) >= args.limit:
                break
    print(fit_audio_mouth_model(pairs, args.out, feature_mode=args.feature_mode, cache_dir=args.cache_dir, model_id=args.model_id))
    print(f"audio_mouth_samples={len(pairs)}")

if __name__ == "__main__":
    main()
