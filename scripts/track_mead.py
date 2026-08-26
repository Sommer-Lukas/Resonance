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
from voice_face.tracking.mediapipe import track_video


def main() -> None:
    parser = argparse.ArgumentParser(description="Track MEAD videos with MediaPipe FaceTracker.")
    parser.add_argument("--index", type=Path, default=ROOT / "outputs" / "voice_face" / "mead_index.csv")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "outputs" / "voice_face" / "tracking")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    samples = read_index(args.index)[: args.limit]
    for sample in samples:
        out = args.out_dir / f"{sample.sample_id}.npz"
        track_video(sample.video_path, out, force=args.force)
        print(out)


if __name__ == "__main__":
    main()
