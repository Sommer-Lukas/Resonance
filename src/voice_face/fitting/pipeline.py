"""GNM identity caching and per-frame expression fitting."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from voice_face.bootstrap import add_vendor_paths
from voice_face.fitting.smoothing import channel_exponential_smooth, exponential_smooth, trajectory_stats
from voice_face.io import should_skip
from voice_face.tracking.mediapipe import load_tracking


@dataclass(frozen=True, slots=True)
class FitConfig:
    smoothing: float = 0.0
    expression_gain: float = 1.0
    processing_mode: str = "legacy"
    region_smoothing: tuple[float, ...] | None = None
    blink_blendshape_indices: tuple[int, ...] = ()
    blink_expression_indices: tuple[int, ...] = ()
    blink_gain: float = 1.0

    def __post_init__(self) -> None:
        if self.processing_mode not in {"legacy", "regional"}:
            raise ValueError("processing_mode must be 'legacy' or 'regional'")


def _solver(gnm: Any, correspondence: Any, config: FitConfig) -> Any:
    add_vendor_paths()
    from webcam_puppet.solver import LandmarkSolver
    return LandmarkSolver(gnm, correspondence, smoothing=0.0, expression_gain=config.expression_gain)


def _valid_indices(indices: tuple[int, ...], size: int) -> list[int]:
    return [index for index in indices if 0 <= index < size]


def _regional_expression(expression_raw: np.ndarray, valid: np.ndarray, blendshapes: np.ndarray, config: FitConfig) -> tuple[np.ndarray, dict[str, object]]:
    channel_count = expression_raw.shape[1]
    if config.region_smoothing is None:
        alphas = np.full(channel_count, config.smoothing, dtype=np.float32)
    else:
        alphas = np.asarray(config.region_smoothing, dtype=np.float32)
    processed = channel_exponential_smooth(expression_raw, valid, alphas)

    blink_blendshape_indices = _valid_indices(config.blink_blendshape_indices, blendshapes.shape[1] if blendshapes.ndim == 2 else 0)
    blink_expression_indices = _valid_indices(config.blink_expression_indices, channel_count)
    blink_frames = np.zeros(len(valid), dtype=bool)
    if blink_blendshape_indices and blink_expression_indices:
        blink_frames = valid & np.any(np.nan_to_num(blendshapes[:, blink_blendshape_indices], nan=0.0) > 0.0, axis=1)
        blink_gain = float(np.clip(config.blink_gain, 0.0, 1.0))
        processed[np.ix_(blink_frames, blink_expression_indices)] = (
            (1.0 - blink_gain) * processed[np.ix_(blink_frames, blink_expression_indices)]
            + blink_gain * expression_raw[np.ix_(blink_frames, blink_expression_indices)]
        )

    metadata: dict[str, object] = {
        "processing_mode": "regional",
        "processing_stage": "post_solve_expression",
        "expression_processing": "channel_smoothing_and_blink_restoration",
        "region_smoothing": alphas.astype(float).tolist(),
        "blink": {
            "blendshape_indices": blink_blendshape_indices,
            "expression_indices": blink_expression_indices,
            "gain": float(np.clip(config.blink_gain, 0.0, 1.0)),
            "frames": int(blink_frames.sum()),
        },
    }
    return processed, metadata


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
    blendshapes = np.asarray(tracking.get("blendshapes", np.empty((len(valid), 0), dtype=np.float32)), dtype=np.float32)
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
    regional_metadata: dict[str, object] | None = None
    if config.processing_mode == "legacy":
        expression_smoothed = exponential_smooth(expression_raw, valid, config.smoothing) if config.smoothing else expression_raw.copy()
    else:
        expression_smoothed, regional_metadata = _regional_expression(expression_raw, valid, blendshapes, config)
    stats = trajectory_stats(np.nan_to_num(expression_smoothed), valid)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"version": 1, "source_tracking": str(tracking_path.resolve()), "identity_path": str(identity_path.resolve()), "source_video": meta.get("source_video"), "width": meta.get("width"), "height": meta.get("height"), "fps": meta.get("fps"), "config": asdict(config), "processing_mode": config.processing_mode, "processing_stage": "post_solve_expression", "stats": asdict(stats)}
    if regional_metadata is not None:
        metadata["regional_processing"] = regional_metadata
    np.savez_compressed(output_path, identity=identity, expression_raw=expression_raw, expression_smoothed=expression_smoothed, expression=expression_smoothed, rotation=rotation, rotations=rotation, translation=translation, fit_error=fit_error, landmark_rmse=fit_error, valid=valid, timestamps=tracking["timestamps"], timestamps_ms=tracking["timestamps_ms"], blendshapes=blendshapes, metadata=json.dumps(metadata, sort_keys=True))
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
