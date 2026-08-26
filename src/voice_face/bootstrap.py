# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Import path helpers for vendored GNM packages."""

from __future__ import annotations

import sys
from pathlib import Path


def repo_root(start: Path | None = None) -> Path:
    path = (start or Path(__file__)).resolve()
    for candidate in (path, *path.parents):
        if (candidate / "third_party").exists() and (candidate / "README.md").exists():
            return candidate
    raise RuntimeError("Could not find Resonance repository root")


def add_vendor_paths(root: Path | None = None) -> Path:
    root = root or repo_root()
    paths = [
        root / "third_party" / "GNM" / "gnm" / "shape",
        root / "third_party" / "gnm-webcam-puppet",
    ]
    for path in paths:
        text = str(path)
        if path.exists() and text not in sys.path:
            sys.path.insert(0, text)
    return root
