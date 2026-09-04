#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from voice_face.gnm.load import load_gnm
from voice_face.visualization.training_diagnostics import render_training_diagnostic


def main() -> None:
    parser = argparse.ArgumentParser(description="Render original|GNM target|mouth-only TrainingSequence diagnostics.")
    parser.add_argument("training_sequence", type=Path)
    parser.add_argument("--fit", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    out = args.out or args.training_sequence.with_suffix(".mouth_diagnostic.mp4")
    render_training_diagnostic(args.training_sequence, args.fit, out, load_gnm(), force=args.force, size=args.size)
    print(out)


if __name__ == "__main__":
    main()
