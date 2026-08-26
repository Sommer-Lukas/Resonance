"""GNM identity caching and per-frame expression fitting."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from voice_face.bootstrap import add_vendor_paths
from voice_face.fitting.smoothing import exponential_smooth, trajectory_stats
from voice_face.io import should_skip
from voice_face.tracking.mediapipe import load_tracking


@dataclass(frozen=True, slots=True)
class FitConfig:
    smoothing: float = 0.0
    expression_gain: float = 1.0


def _solver(gnm: Any, correspondence: Any, config: FitConfig) -> Any:
    add_vendor_paths()
    from webcam_puppet.solver import LandmarkSolver
    return LandmarkSolver(gnm, correspondence, smoothing=0.0, expression_gain=config.expression_gain)


def cache_actor_identity(actor: str, tracking_paths: list[Path], output_path: Path, gnm: Any, correspondence: Any, *, force: bool = False, config: FitConfig = FitConfig()) -> Path:
    if should_skip(output_path, force):
        return output_path
    solver = _solver(gnm, correspondence, config)
    source_frames: list[dict[str, object]] = []
    first_source_frame = 0
    identities: list[np.ndarray] = []
    errors: list[float] = []
    for path in tracking_paths:
        tracking = load_tracking(path)
        valid = np.asarray(tracking["valid"], dtype=bool)
        meta = tracking["metadata"]
        for index in np.flatnonzero(valid)[:3]:
            identity = solver.solve_identity(tracking["landmarks"][index], int(meta["width"]), int(meta["height"]))
            identities.append(np.asarray(identity, dtype=np.float32))
            errors.append(0.0)
            frame_number = int(index)
            if not source_frames:
                first_source_frame = frame_number
            source_frames.append({"tracking": str(path.resolve()), "frame": frame_number})
        if identities:
            break
    if not identities:
        raise RuntimeError(f"No valid tracking frames found for actor {actor}")
    identity = np.mean(np.stack(identities), axis=0).astype(np.float32)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, identity=identity, identity_coefficients=identity, actor_id=actor, source_frames=json.dumps(source_frames, sort_keys=True), fitting_errors=np.asarray(errors, dtype=np.float32), source_frame=first_source_frame, metadata=json.dumps({"version": 1, "solver": "webcam_puppet.LandmarkSolver", "config": asdict(config)}, sort_keys=True))
    return output_path


def fit_sample(tracking_path: Path, identity_path: Path, output_path: Path, gnm: Any, correspondence: Any, *, force: bool = False, config: FitConfig = FitConfig()) -> Path:
    if should_skip(output_path, force):
        return output_path
    tracking = load_tracking(tracking_path)
    meta = tracking["metadata"]
    identity = np.load(identity_path, allow_pickle=False)["identity"].astype(np.float32)
    solver = _solver(gnm, correspondence, config)
    solver._identity = identity
    valid = np.asarray(tracking["valid"], dtype=bool)
    expression_raw = np.full((len(valid), int(gnm.expression_dim)), np.nan, dtype=np.float32)
    rotation = np.full((len(valid), int(gnm.num_joints), 3), np.nan, dtype=np.float32)
    translation = np.full((len(valid), 3), np.nan, dtype=np.float32)
    fit_error = np.full((len(valid),), np.nan, dtype=np.float32)
    for index in np.flatnonzero(valid):
        params = solver.solve(tracking["landmarks"][index], int(meta["width"]), int(meta["height"]))
        expression_raw[index] = params.expression
        rotation[index] = params.rotations
        translation[index] = params.translation
        fit_error[index] = params.landmark_rmse
    expression_smoothed = exponential_smooth(expression_raw, valid, config.smoothing) if config.smoothing else expression_raw.copy()
    stats = trajectory_stats(np.nan_to_num(expression_smoothed), valid)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"version": 1, "source_tracking": str(tracking_path.resolve()), "identity_path": str(identity_path.resolve()), "source_video": meta.get("source_video"), "width": meta.get("width"), "height": meta.get("height"), "fps": meta.get("fps"), "config": asdict(config), "stats": asdict(stats)}
    np.savez_compressed(output_path, identity=identity, expression_raw=expression_raw, expression_smoothed=expression_smoothed, expression=expression_smoothed, rotation=rotation, rotations=rotation, translation=translation, fit_error=fit_error, landmark_rmse=fit_error, valid=valid, timestamps=tracking["timestamps"], timestamps_ms=tracking["timestamps_ms"], blendshapes=tracking["blendshapes"], metadata=json.dumps(metadata, sort_keys=True))
    return output_path


def smooth_fit(input_path: Path, output_path: Path, *, alpha: float, force: bool = False) -> Path:
    if should_skip(output_path, force):
        return output_path
    data = np.load(input_path, allow_pickle=False)
    valid = data["valid"].astype(bool)
    raw = data["expression_raw"] if "expression_raw" in data.files else data["expression"]
    smoothed = exponential_smooth(raw, valid, alpha)
    meta = json.loads(str(data["metadata"])); meta["post_smoothing_alpha"] = alpha
    np.savez_compressed(output_path, identity=data["identity"], expression_raw=raw, expression_smoothed=smoothed, expression=smoothed, rotation=data["rotation"] if "rotation" in data.files else data["rotations"], rotations=data["rotations"] if "rotations" in data.files else data["rotation"], translation=data["translation"], fit_error=data["fit_error"] if "fit_error" in data.files else data["landmark_rmse"], landmark_rmse=data["landmark_rmse"] if "landmark_rmse" in data.files else data["fit_error"], valid=valid, timestamps=data["timestamps"] if "timestamps" in data.files else data["timestamps_ms"].astype(np.float32) / 1000.0, timestamps_ms=data["timestamps_ms"] if "timestamps_ms" in data.files else (data["timestamps"] * 1000).astype(np.int64), blendshapes=data["blendshapes"], metadata=json.dumps(meta, sort_keys=True))
    return output_path
