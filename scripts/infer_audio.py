#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

DEFAULT_MOUTH_MODEL = ROOT / "outputs" / "checkpoints" / "audio_mouth_wavlm_240_fixed.npz"

import numpy as np
from voice_face.gnm.load import load_gnm
from voice_face.prediction import free_audio_features, predict_checkpoint, save_prediction
from voice_face.rendering import render_prediction_video


def main() -> None:
    p = argparse.ArgumentParser(description="Free audio emotional GNM inference: audio + emotion + intensity + identity -> rendered video.")
    p.add_argument("--audio", type=Path, required=True)
    p.add_argument("--emotion", required=True)
    p.add_argument("--intensity", type=float, required=True)
    p.add_argument("--identity", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--mouth-model", type=Path, default=DEFAULT_MOUTH_MODEL)
    p.add_argument("--mouth-cache-dir", type=Path, default=ROOT / "outputs" / "cache" / "wavlm_base_plus")
    p.add_argument("--out", type=Path, default=ROOT / "outputs" / "predictions" / "predicted_animation.mp4")
    p.add_argument("--npz", type=Path, default=None)
    p.add_argument("--fps", type=float, default=30.0)
    p.add_argument("--size", type=int, default=320)
    args = p.parse_args()
    gnm = load_gnm(); identity = np.load(args.identity, allow_pickle=False)["identity"].astype(np.float32)
    timestamps, mouth_expression, prosody = free_audio_features(args.audio, int(gnm.expression_dim), fps=args.fps, mouth_model=args.mouth_model if args.mouth_model.exists() else None, mouth_cache_dir=args.mouth_cache_dir)
    expression = predict_checkpoint(args.checkpoint, mouth_expression, prosody, args.emotion, args.intensity)
    rotation = np.zeros((len(timestamps), int(gnm.num_joints), 3), dtype=np.float32); translation = np.zeros((len(timestamps), 3), dtype=np.float32)
    save_prediction(args.npz or args.out.with_suffix(".npz"), timestamps, expression, identity, rotation, translation, {"audio": str(args.audio), "emotion": args.emotion, "intensity": args.intensity})
    render_prediction_video(expression, identity, rotation, translation, args.out, gnm, fps=args.fps, size=args.size, source_audio=args.audio)
    print(args.out)

if __name__ == "__main__": main()
