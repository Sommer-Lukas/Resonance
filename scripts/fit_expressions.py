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


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit GNM expression trajectories with cached actor identity.")
    parser.add_argument("--index", type=Path, default=ROOT / "outputs" / "voice_face" / "mead_index.csv")
    parser.add_argument("--tracking-dir", type=Path, default=ROOT / "outputs" / "voice_face" / "tracking")
    parser.add_argument("--identity-dir", type=Path, default=ROOT / "outputs" / "voice_face" / "identity")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs" / "voice_face" / "fits")
    parser.add_argument("--correspondence", type=Path, default=ROOT / "outputs" / "voice_face" / "correspondence.npz")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--smoothing", type=float, default=0.0)
    parser.add_argument("--expression-gain", type=float, default=1.0)
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
        fit_sample(tracking, identity, out, gnm, correspondence, force=args.force, config=FitConfig(args.smoothing, args.expression_gain))
        print(out)


if __name__ == "__main__":
    main()
