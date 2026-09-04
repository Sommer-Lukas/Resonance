from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

BLENDSHAPE_NAMES = (
    "_neutral",
    "browDownLeft",
    "browDownRight",
    "browInnerUp",
    "browOuterUpLeft",
    "browOuterUpRight",
    "cheekPuff",
    "cheekSquintLeft",
    "cheekSquintRight",
    "eyeBlinkLeft",
    "eyeBlinkRight",
    "eyeLookDownLeft",
    "eyeLookDownRight",
    "eyeLookInLeft",
    "eyeLookInRight",
    "eyeLookOutLeft",
    "eyeLookOutRight",
    "eyeLookUpLeft",
    "eyeLookUpRight",
    "eyeSquintLeft",
    "eyeSquintRight",
    "eyeWideLeft",
    "eyeWideRight",
    "jawForward",
    "jawLeft",
    "jawOpen",
    "jawRight",
    "mouthClose",
    "mouthDimpleLeft",
    "mouthDimpleRight",
    "mouthFrownLeft",
    "mouthFrownRight",
    "mouthFunnel",
    "mouthLeft",
    "mouthLowerDownLeft",
    "mouthLowerDownRight",
    "mouthPressLeft",
    "mouthPressRight",
    "mouthPucker",
    "mouthRight",
    "mouthRollLower",
    "mouthRollUpper",
    "mouthShrugLower",
    "mouthShrugUpper",
    "mouthSmileLeft",
    "mouthSmileRight",
    "mouthStretchLeft",
    "mouthStretchRight",
    "mouthUpperUpLeft",
    "mouthUpperUpRight",
    "noseSneerLeft",
    "noseSneerRight",
)
BLENDSHAPE_INDEX = {name: index for index, name in enumerate(BLENDSHAPE_NAMES)}
MOUTH_NEUTRAL_BLENDSHAPES = ("jawOpen", "mouthClose", "mouthSmileLeft", "mouthSmileRight", "mouthFrownLeft", "mouthFrownRight", "mouthStretchLeft", "mouthStretchRight")
BLINK_LEFT = "eyeBlinkLeft"
BLINK_RIGHT = "eyeBlinkRight"


@dataclass(frozen=True, slots=True)
class ExpressionProcessingConfig:
    neutral_max_frames_per_clip: int = 20
    neutral_score_percentile: float = 35.0
    lower_soft_bound: float = 5.0
    lower_small_motion_alpha: float = 0.75
    lower_large_motion_alpha: float = 0.15
    lower_motion_threshold: float = 0.18


def actor_id_from_sample(sample_id: str) -> str:
    parts = sample_id.split("__", 1)
    return parts[0]


def load_metadata(data: Any) -> dict[str, Any]:
    return json.loads(str(data["metadata"])) if "metadata" in data.files else {}


def expression_array(data: Any) -> np.ndarray:
    if "expression_smoothed" in data.files:
        return data["expression_smoothed"]
    return data["expression"]


def blendshape(data: Any, name: str) -> np.ndarray:
    blendshapes = np.asarray(data["blendshapes"] if "blendshapes" in data.files else np.empty((len(expression_array(data)), 0)), dtype=np.float32)
    index = BLENDSHAPE_INDEX[name]
    if blendshapes.ndim != 2 or blendshapes.shape[1] <= index:
        return np.zeros((len(expression_array(data)),), dtype=np.float32)
    return np.nan_to_num(blendshapes[:, index], nan=0.0).astype(np.float32)


def blink_signals(data: Any) -> tuple[np.ndarray, np.ndarray]:
    return blendshape(data, BLINK_LEFT), blendshape(data, BLINK_RIGHT)


def neutral_frame_indices(data: Any, config: ExpressionProcessingConfig) -> np.ndarray:
    valid = np.asarray(data["valid"] if "valid" in data.files else np.ones(len(expression_array(data)), dtype=bool), dtype=bool)
    expression = np.nan_to_num(expression_array(data).astype(np.float32), nan=0.0)
    motion = np.zeros(len(expression), dtype=np.float32)
    if len(expression) > 1:
        velocity = np.linalg.norm(np.diff(expression, axis=0), axis=1)
        motion[1:] = velocity
    score = motion.copy()
    for name in MOUTH_NEUTRAL_BLENDSHAPES:
        score += blendshape(data, name)
    candidates = np.flatnonzero(valid & np.isfinite(score))
    if candidates.size == 0:
        return candidates
    cutoff = np.percentile(score[candidates], float(config.neutral_score_percentile))
    selected = candidates[score[candidates] <= cutoff]
    if selected.size == 0:
        selected = candidates[np.argsort(score[candidates])[:1]]
    return selected[: int(config.neutral_max_frames_per_clip)]


def estimate_neutral_expression(paths: list[Path], config: ExpressionProcessingConfig) -> tuple[np.ndarray, dict[str, Any]]:
    frames = []
    sources = []
    for path in paths:
        with np.load(path, allow_pickle=False) as data:
            expression = np.nan_to_num(expression_array(data).astype(np.float32), nan=0.0)
            indices = neutral_frame_indices(data, config)
            if indices.size:
                frames.append(expression[indices])
                sources.extend({"fit": str(path), "frame": int(index)} for index in indices)
    if not frames:
        raise RuntimeError("No neutral frames available for neutral-expression calibration")
    stacked = np.vstack(frames)
    neutral = np.median(stacked, axis=0).astype(np.float32)
    return neutral, {"source_frames": sources, "frame_count": int(len(stacked)), "config": asdict(config)}


def lower_face_stats(expression: np.ndarray, lower_indices: np.ndarray) -> dict[str, float]:
    lower = np.abs(np.nan_to_num(expression[:, lower_indices], nan=0.0))
    return {
        "mean_abs_lower_face": float(np.mean(lower)),
        "p95_abs_lower_face": float(np.percentile(lower, 95)),
        "max_abs_lower_face": float(np.max(lower)),
    }


def adaptive_lower_filter(expression: np.ndarray, valid: np.ndarray, lower_indices: np.ndarray, config: ExpressionProcessingConfig) -> np.ndarray:
    out = np.asarray(expression, dtype=np.float32).copy()
    valid = np.asarray(valid, dtype=bool)
    previous = None
    for frame, ok in enumerate(valid):
        if not ok:
            continue
        current = out[frame, lower_indices]
        if previous is None:
            previous = current.copy()
            continue
        motion = float(np.mean(np.abs(current - previous)))
        t = np.clip(motion / max(float(config.lower_motion_threshold), 1e-6), 0.0, 1.0)
        alpha = (1.0 - t) * float(config.lower_small_motion_alpha) + t * float(config.lower_large_motion_alpha)
        previous = alpha * previous + (1.0 - alpha) * current
        out[frame, lower_indices] = previous
    return out


def process_expression(old_expression: np.ndarray, valid: np.ndarray, neutral_expression: np.ndarray, lower_indices: np.ndarray, config: ExpressionProcessingConfig) -> tuple[np.ndarray, np.ndarray]:
    raw_delta = np.nan_to_num(old_expression.astype(np.float32), nan=0.0) - neutral_expression.astype(np.float32)
    filtered = adaptive_lower_filter(raw_delta, valid, lower_indices, config)
    lower = filtered[:, lower_indices]
    bound = float(config.lower_soft_bound)
    filtered[:, lower_indices] = bound * np.tanh(lower / bound)
    return raw_delta.astype(np.float32), filtered.astype(np.float32)
