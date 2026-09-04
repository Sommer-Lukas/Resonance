#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.render_lower_face_sweep import _metadata, _rotation, _sample_path, lower_face_indices  # noqa: E402
from scripts.render_mouth_aperture_sweep import (  # noqa: E402
    CANDIDATES,
    CORRESPONDENCE,
    _available_pairs,
    _candidate_expression,
    _gnm_aperture,
    _learn_aperture_direction,
    _mapped_vertices,
    _mp_aperture,
)
from voice_face.bootstrap import add_vendor_paths  # noqa: E402
from voice_face.fitting.expression_processing import blendshape, lower_face_stats  # noqa: E402
from voice_face.gnm.load import load_gnm  # noqa: E402

PROCESSED_ROOT = ROOT / "data" / "processed" / "gnm" / "sequences_processed"
OUTPUT_ROOT = ROOT / "data" / "processed" / "gnm" / "sequences_m2"
SELECTION_PATH = ROOT / "data" / "processed" / "gnm" / "selected_expression_model.json"
_context_cache: tuple[Any, np.ndarray, dict[int, int]] | None = None
_direction_cache: dict[str, np.ndarray] = {}


def _context() -> tuple[Any, np.ndarray, dict[int, int]]:
    global _context_cache
    if _context_cache is None:
        add_vendor_paths()
        from webcam_puppet.correspondence import Correspondence

        gnm = load_gnm()
        _context_cache = (gnm, lower_face_indices(gnm), _mapped_vertices(Correspondence.load(CORRESPONDENCE)))
    return _context_cache


def _samples_from_args(samples: list[str] | None, all_processed: bool, processed_root: Path) -> list[str]:
    selected = list(samples or [])
    if all_processed:
        selected.extend(str(path) for path in sorted(processed_root.glob("*.npz")))
    if not selected:
        raise SystemExit("Pass --sample or --all-processed")
    return list(dict.fromkeys(selected))


def _processed_path(sample: str, processed_root: Path) -> Path:
    path = Path(sample)
    if path.exists():
        return path
    candidate = processed_root / f"{Path(sample).stem}.npz"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(candidate)


def _landmarks(old_data, old_path: Path) -> np.ndarray:
    if "landmarks" in old_data.files:
        return old_data["landmarks"].astype(np.float32, copy=True)
    tracking_path = _metadata(old_data, old_path).get("source_tracking")
    with np.load(str(tracking_path), allow_pickle=False) as tracking:
        return tracking["landmarks"].astype(np.float32, copy=True)


def lock_sample(sample: str, processed_root: Path, output_root: Path) -> Path:
    processed_path = _processed_path(sample, processed_root)
    output = output_root / processed_path.name
    if output.exists():
        return output
    old_path = _sample_path(processed_path.stem)
    actor = processed_path.stem.split("__", 1)[0]
    candidate = next(item for item in CANDIDATES if item.code == "M2")
    gnm, lower_indices, mapped = _context()
    pairs = _available_pairs(mapped)
    with np.load(old_path, allow_pickle=False) as old_data, np.load(processed_path, allow_pickle=False) as processed_data:
        current = processed_data["expression_processed"].astype(np.float32, copy=True)
        identity = old_data["identity"].astype(np.float32, copy=True)
        rotation = _rotation(old_data).astype(np.float32, copy=True)
        translation = old_data["translation"].astype(np.float32, copy=True)
        landmarks = _landmarks(old_data, old_path)
        jaw_open = blendshape(old_data, "jawOpen")
        meta = json.loads(str(processed_data["metadata"])) if "metadata" in processed_data.files else {}
        keys = {key: processed_data[key] for key in processed_data.files if key != "metadata"}
    source_aperture, _, _, _ = _mp_aperture(landmarks, pairs)
    frames = min(len(current), len(rotation), len(translation), len(source_aperture), len(jaw_open))
    current_aperture = np.zeros(frames, dtype=np.float32)
    for frame in range(frames):
        current_aperture[frame] = _gnm_aperture(gnm(identity, current[frame], rotation[frame], translation[frame]), mapped)[0]
    if actor not in _direction_cache:
        neutral_expression = np.median(current[:frames], axis=0).astype(np.float32)
        _direction_cache[actor] = _learn_aperture_direction(gnm, identity, neutral_expression, rotation[0], translation[0], lower_indices, mapped)
    direction = _direction_cache[actor]
    selected = _candidate_expression(current[:frames], source_aperture[:frames], current_aperture, jaw_open[:frames], direction, candidate)
    if len(selected) < len(current):
        selected = np.vstack([selected, current[len(selected) :]]).astype(np.float32)
    meta["selected_expression_model"] = "M2"
    meta["selected_expression_source"] = str(processed_path.resolve())
    meta["selected_expression_parameters"] = {
        "candidate": candidate.code,
        "aperture_weight": candidate.aperture_weight,
        "jaw_weight": candidate.jaw_weight,
        "lower_regularization": candidate.lower_regularization,
        "smoothing": candidate.smoothing,
        "method": "neutral_relative_processed_plus_geometry_derived_aperture_direction",
    }
    meta["m2_lower_face_stats"] = lower_face_stats(selected, lower_indices)
    keys.update(expression_m2=selected, expression_processed=selected, expression_smoothed=selected, expression=selected, metadata=json.dumps(meta, sort_keys=True))
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, **keys)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Lock selected M2 mouth-aperture expression targets into a non-overwriting output set.")
    parser.add_argument("--sample", action="append")
    parser.add_argument("--all-processed", action="store_true")
    parser.add_argument("--processed-dir", type=Path, default=PROCESSED_ROOT)
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    outputs = [lock_sample(sample, args.processed_dir, args.out_dir) for sample in _samples_from_args(args.sample, args.all_processed, args.processed_dir)]
    SELECTION_PATH.write_text(json.dumps({"selected_expression_model": "M2", "output_dir": str(args.out_dir.resolve()), "files": [str(path.resolve()) for path in outputs]}, indent=2), encoding="utf-8")
    for output in outputs:
        print(output)
    print(SELECTION_PATH)


if __name__ == "__main__":
    main()
