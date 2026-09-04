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

from voice_face.data.mead import read_index
from voice_face.fitting.pipeline import FitConfig, fit_sample
from voice_face.gnm.load import load_correspondence, load_gnm


def _parse_floats(value: str | None) -> tuple[float, ...] | None:
    if value is None or value == "":
        return None
    return tuple(float(part) for part in value.split(",") if part)


def _parse_ints(value: str) -> tuple[int, ...]:
    if value == "":
        return ()
    return tuple(int(part) for part in value.split(",") if part)


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-solve expression processing for GNM fits with cached actor identity.")
    parser.add_argument("--index", type=Path, default=ROOT / "outputs" / "voice_face" / "mead_index.csv")
    parser.add_argument("--tracking-dir", type=Path, default=ROOT / "outputs" / "voice_face" / "tracking")
    parser.add_argument("--identity-dir", type=Path, default=ROOT / "outputs" / "voice_face" / "identity")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs" / "voice_face" / "fits")
    parser.add_argument("--correspondence", type=Path, default=ROOT / "outputs" / "voice_face" / "correspondence.npz")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--smoothing", type=float, default=0.0)
    parser.add_argument("--expression-gain", type=float, default=1.0)
    parser.add_argument("--processing-mode", choices=("legacy", "regional"), default="legacy", help="Post-solve expression processing mode: legacy smoothing or regional channel smoothing/blink restoration.")
    parser.add_argument("--region-smoothing", type=_parse_floats, default=None, help="Comma-separated per-expression smoothing alphas for post-solve regional processing.")
    parser.add_argument("--blink-blendshape-indices", type=_parse_ints, default=(), help="Comma-separated source blendshape indices for blink preservation.")
    parser.add_argument("--blink-expression-indices", type=_parse_ints, default=(), help="Comma-separated expression channels restored toward raw on blink frames.")
    parser.add_argument("--blink-gain", type=float, default=1.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    gnm = load_gnm()
    correspondence = load_correspondence(gnm, args.correspondence)
    for sample in read_index(args.index)[: args.limit]:
        tracking = args.tracking_dir / f"{sample.sample_id}.npz"
        identity = args.identity_dir / f"{sample.actor_id}.npz"
        if not tracking.exists() or not identity.exists():
            continue
        out = args.out_dir / f"{sample.sample_id}.npz"
        fit_sample(tracking, identity, out, gnm, correspondence, force=args.force, config=FitConfig(args.smoothing, args.expression_gain, args.processing_mode, args.region_smoothing, args.blink_blendshape_indices, args.blink_expression_indices, args.blink_gain))
        print(out)


if __name__ == "__main__":
    main()
