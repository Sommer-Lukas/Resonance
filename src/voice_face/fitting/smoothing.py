"""Temporal smoothing and trajectory statistics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class TrajectoryStats:
    valid_frames: int
    invalid_frames: int
    mean_abs_velocity: float
    p95_abs_velocity: float
    mean_abs_acceleration: float
    p95_abs_acceleration: float
    max_abs_value: float


def exponential_smooth(values: np.ndarray, valid: np.ndarray, alpha: float) -> np.ndarray:
    if not 0.0 <= alpha < 1.0:
        raise ValueError("alpha must be in [0, 1)")
    out = np.asarray(values, dtype=np.float32).copy()
    valid = np.asarray(valid, dtype=bool)
    previous = None
    for index, ok in enumerate(valid):
        if not ok:
            continue
        if previous is None or alpha == 0.0:
            previous = out[index].copy()
        else:
            previous = alpha * previous + (1.0 - alpha) * out[index]
            out[index] = previous
    return out


def channel_exponential_smooth(values: np.ndarray, valid: np.ndarray, alphas: np.ndarray) -> np.ndarray:
    alphas = np.asarray(alphas, dtype=np.float32)
    if not np.isfinite(alphas).all() or np.any((alphas < 0.0) | (alphas >= 1.0)):
        raise ValueError("alphas must be in [0, 1)")
    out = np.asarray(values, dtype=np.float32).copy()
    if out.ndim != 2 or alphas.shape != (out.shape[1],):
        raise ValueError("alphas must match expression channel count")
    valid = np.asarray(valid, dtype=bool)
    previous = None
    for index, ok in enumerate(valid):
        if not ok:
            continue
        if previous is None:
            previous = out[index].copy()
        else:
            previous = alphas * previous + (1.0 - alphas) * out[index]
            out[index] = previous
    return out


def trajectory_stats(values: np.ndarray, valid: np.ndarray) -> TrajectoryStats:
    valid = np.asarray(valid, dtype=bool)
    present = np.asarray(values)[valid]
    if len(present) == 0:
        return TrajectoryStats(0, int((~valid).sum()), 0.0, 0.0, 0.0, 0.0, 0.0)
    velocity = np.abs(np.diff(present, axis=0))
    acceleration = np.abs(np.diff(present, n=2, axis=0))
    return TrajectoryStats(
        valid_frames=int(valid.sum()),
        invalid_frames=int((~valid).sum()),
        mean_abs_velocity=float(np.mean(velocity)) if velocity.size else 0.0,
        p95_abs_velocity=float(np.percentile(velocity, 95)) if velocity.size else 0.0,
        mean_abs_acceleration=float(np.mean(acceleration)) if acceleration.size else 0.0,
        p95_abs_acceleration=float(np.percentile(acceleration, 95)) if acceleration.size else 0.0,
        max_abs_value=float(np.max(np.abs(present))),
    )
