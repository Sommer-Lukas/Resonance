# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Mouth driver abstraction for speech articulation experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np


@dataclass(frozen=True, slots=True)
class MouthFrame:
    jaw_open: float
    lip_close: float
    mouth_smile: float


@dataclass(frozen=True, slots=True)
class MouthTrajectory:
    features: np.ndarray
    valid: np.ndarray
    fps: float
    feature_names: tuple[str, ...] = ("jaw_open", "lip_close", "mouth_smile")


class MouthDriver(Protocol):
    def predict(self, audio_path: Path, target_fps: float) -> MouthTrajectory:
        ...


def frame_at(trajectory: MouthTrajectory, time_seconds: float) -> MouthFrame:
    if len(trajectory.features) == 0:
        return MouthFrame(0.0, 0.0, 0.0)
    index = max(0, min(int(time_seconds * trajectory.fps), len(trajectory.features) - 1))
    row = trajectory.features[index]
    return MouthFrame(float(row[0]), float(row[1]), float(row[2]))


@dataclass(frozen=True, slots=True)
class ConstantMouthDriver:
    frame: MouthFrame = MouthFrame(0.0, 0.0, 0.0)
    seconds: float = 1.0

    def predict(self, audio_path: Path, target_fps: float) -> MouthTrajectory:
        frames = max(1, int(round(self.seconds * target_fps)))
        row = np.array([self.frame.jaw_open, self.frame.lip_close, self.frame.mouth_smile], dtype=np.float32)
        return MouthTrajectory(np.repeat(row[None, :], frames, axis=0), np.ones(frames, dtype=bool), target_fps)

    def sample(self, time_seconds: float) -> MouthFrame:
        return self.frame


class BlendshapeMouthDriver:
    def __init__(self, tracking_npz: Path, *, jaw_index: int = 25, smile_left_index: int = 44, smile_right_index: int = 45):
        data = np.load(tracking_npz, allow_pickle=False)
        self._timestamps = data["timestamps_ms"].astype(np.float32) / 1000.0
        self._blendshapes = np.nan_to_num(data["blendshapes"].astype(np.float32))
        self._valid = data["valid"].astype(bool)
        self._jaw_index = jaw_index
        self._smile_left_index = smile_left_index
        self._smile_right_index = smile_right_index

    def predict(self, audio_path: Path, target_fps: float) -> MouthTrajectory:
        if len(self._timestamps) == 0:
            return MouthTrajectory(np.zeros((0, 3), dtype=np.float32), np.zeros(0, dtype=bool), target_fps)
        duration = float(self._timestamps[-1]) if len(self._timestamps) else 0.0
        frames = max(1, int(round(duration * target_fps)) + 1)
        features = np.zeros((frames, 3), dtype=np.float32)
        valid = np.zeros(frames, dtype=bool)
        for index in range(frames):
            source = int(np.searchsorted(self._timestamps, index / target_fps, side="right") - 1)
            source = max(0, min(source, len(self._timestamps) - 1))
            row = self._blendshapes[source]
            if row.size > self._jaw_index:
                features[index, 0] = row[self._jaw_index]
            if row.size > max(self._smile_left_index, self._smile_right_index):
                features[index, 2] = 0.5 * (row[self._smile_left_index] + row[self._smile_right_index])
            valid[index] = self._valid[source]
        return MouthTrajectory(features, valid, target_fps)

    def sample(self, time_seconds: float) -> MouthFrame:
        if len(self._timestamps) == 0 or self._blendshapes.shape[1] == 0:
            return MouthFrame(0.0, 0.0, 0.0)
        index = int(np.searchsorted(self._timestamps, time_seconds, side="right") - 1)
        index = max(0, min(index, len(self._timestamps) - 1))
        row = self._blendshapes[index]
        smile = 0.5 * (row[self._smile_left_index] + row[self._smile_right_index]) if row.size > max(self._smile_left_index, self._smile_right_index) else 0.0
        jaw = row[self._jaw_index] if row.size > self._jaw_index else 0.0
        return MouthFrame(float(jaw), 0.0, float(smile))


__all__ = ["MouthFrame", "MouthTrajectory", "MouthDriver", "ConstantMouthDriver", "BlendshapeMouthDriver", "frame_at"]
