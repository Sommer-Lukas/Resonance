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

from voice_face.gnm.load import load_gnm
from voice_face.visualization.diagnostics import render_fit_video, write_fit_report, write_frame_stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a reconstructed GNM diagnostic video and reports.")
    parser.add_argument("fit", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--size", type=int, default=480)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    out = args.out or args.fit.with_suffix(".diagnostic.mp4")
    gnm = load_gnm()
    render_fit_video(args.fit, out, gnm, force=args.force, size=args.size)
    write_fit_report(args.fit, out.with_suffix(".json"))
    write_frame_stats(args.fit, out.with_suffix(".csv"))
    print(out)


if __name__ == "__main__":
    main()
