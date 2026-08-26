"""Typed sequence containers for the face-only research pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True, slots=True)
class SampleMetadata:
    sample_id: str
    actor_id: str
    emotion: str
    intensity: float
    video_path: Path = Path("")
    camera: str = ""
    audio_path: Path | None = None
    utterance_id: str = ""
    fps: float = 0.0
    frame_count: int = 0
    duration: float = 0.0

    @property
    def actor(self) -> str:
        return self.actor_id


@dataclass(frozen=True, slots=True)
class TrackingSequence:
    landmarks: np.ndarray
    blendshapes: np.ndarray
    valid: np.ndarray
    timestamps: np.ndarray
    metadata: SampleMetadata | dict[str, object]
    pose: np.ndarray | None = None
    tracking_confidence: np.ndarray | None = None


@dataclass(frozen=True, slots=True)
class GNMSequence:
    timestamps: np.ndarray
    expression_raw: np.ndarray
    expression_smoothed: np.ndarray
    rotation: np.ndarray
    translation: np.ndarray
    fit_error: np.ndarray
    valid: np.ndarray
    metadata: SampleMetadata | dict[str, object] | None = None

    @property
    def expression(self) -> np.ndarray:
        return self.expression_raw
