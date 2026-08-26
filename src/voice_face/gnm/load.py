# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Lazy GNM model and correspondence loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from voice_face.bootstrap import add_vendor_paths, repo_root


def load_gnm() -> Any:
    add_vendor_paths()
    from gnm.shape import gnm_numpy

    return gnm_numpy.GNM.from_local(version=gnm_numpy.GNMMajorVersion.V3, variant=gnm_numpy.GNMVariant.HEAD)


def load_correspondence(gnm: Any, cache_path: Path, *, force: bool = False) -> Any:
    add_vendor_paths()
    from webcam_puppet.correspondence import load_or_build_correspondence
    from webcam_puppet.tracker import FaceTracker

    model_path = repo_root() / "outputs" / "voice_face" / "cache" / "face_landmarker.task"
    with FaceTracker(model_path=model_path, video_mode=False) as tracker:
        return load_or_build_correspondence(gnm, tracker.landmarks_only, cache_path, rebuild=force)
