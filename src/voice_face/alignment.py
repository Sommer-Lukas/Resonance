"""Timestamp alignment helpers for synchronized face training records."""

from __future__ import annotations

import numpy as np


def target_fps(timestamps: np.ndarray, default: float = 25.0) -> float:
    ts = np.asarray(timestamps, dtype=np.float32)
    if len(ts) < 2:
        return default
    diffs = np.diff(ts)
    valid = diffs[diffs > 0]
    if len(valid) == 0:
        return default
    return float(1.0 / np.median(valid))


def resample_to_timestamps(source_timestamps: np.ndarray, values: np.ndarray, target_timestamps: np.ndarray) -> np.ndarray:
    src_t = np.asarray(source_timestamps, dtype=np.float32)
    dst_t = np.asarray(target_timestamps, dtype=np.float32)
    src_v = np.asarray(values, dtype=np.float32)
    if len(dst_t) == 0:
        return np.zeros((0,) + src_v.shape[1:], dtype=np.float32)
    if len(src_t) == 0 or len(src_v) == 0:
        return np.zeros((len(dst_t),) + src_v.shape[1:], dtype=np.float32)
    if len(src_t) != len(src_v):
        raise ValueError(f"source_timestamps length {len(src_t)} != values length {len(src_v)}")
    flat = src_v.reshape(len(src_v), -1)
    out = np.empty((len(dst_t), flat.shape[1]), dtype=np.float32)
    for column in range(flat.shape[1]):
        out[:, column] = np.interp(dst_t, src_t, flat[:, column], left=flat[0, column], right=flat[-1, column])
    return out.reshape((len(dst_t),) + src_v.shape[1:]).astype(np.float32)


def nearest_valid(source_timestamps: np.ndarray, valid: np.ndarray, target_timestamps: np.ndarray) -> np.ndarray:
    src_t = np.asarray(source_timestamps, dtype=np.float32)
    src_valid = np.asarray(valid, dtype=bool)
    dst_t = np.asarray(target_timestamps, dtype=np.float32)
    if len(dst_t) == 0:
        return np.zeros(0, dtype=bool)
    if len(src_t) == 0 or len(src_valid) == 0:
        return np.zeros(len(dst_t), dtype=bool)
    indexes = np.searchsorted(src_t, dst_t, side="left")
    indexes = np.clip(indexes, 0, len(src_t) - 1)
    previous = np.clip(indexes - 1, 0, len(src_t) - 1)
    use_previous = np.abs(dst_t - src_t[previous]) <= np.abs(dst_t - src_t[indexes])
    indexes = np.where(use_previous, previous, indexes)
    return src_valid[indexes]
