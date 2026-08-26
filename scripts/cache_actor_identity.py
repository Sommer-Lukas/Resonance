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
from collections import defaultdict

from voice_face.data.mead import read_index
from voice_face.fitting.pipeline import FitConfig, cache_actor_identity
from voice_face.gnm.load import load_correspondence, load_gnm


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache one fixed GNM identity per MEAD actor.")
    parser.add_argument("--index", type=Path, default=ROOT / "outputs" / "voice_face" / "mead_index.csv")
    parser.add_argument("--tracking-dir", type=Path, default=ROOT / "outputs" / "voice_face" / "tracking")
    parser.add_argument("--identity-dir", type=Path, default=ROOT / "outputs" / "voice_face" / "identity")
    parser.add_argument("--correspondence", type=Path, default=ROOT / "outputs" / "voice_face" / "correspondence.npz")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    by_actor = defaultdict(list)
    for sample in read_index(args.index):
        path = args.tracking_dir / f"{sample.sample_id}.npz"
        if path.exists():
            by_actor[sample.actor_id].append(path)
    gnm = load_gnm()
    correspondence = load_correspondence(gnm, args.correspondence)
    for actor, paths in sorted(by_actor.items()):
        out = args.identity_dir / f"{actor}.npz"
        cache_actor_identity(actor, paths, out, gnm, correspondence, force=args.force, config=FitConfig())
        print(out)


if __name__ == "__main__":
    main()
