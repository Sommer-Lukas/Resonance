# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Mouth driver abstraction for speech articulation experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from voice_face.alignment import resample_to_timestamps, target_fps


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
    timestamps: np.ndarray | None = None

    def __post_init__(self) -> None:
        if self.timestamps is None:
            object.__setattr__(self, "timestamps", np.arange(len(self.features), dtype=np.float32) / float(self.fps or 1.0))


class MouthDriver(Protocol):
    def predict(self, audio_path: Path, target_timestamps: np.ndarray) -> MouthTrajectory:
        ...


def frame_at(trajectory: MouthTrajectory, time_seconds: float) -> MouthFrame:
    if len(trajectory.features) == 0:
        return MouthFrame(0.0, 0.0, 0.0)
    timestamps = np.asarray(trajectory.timestamps, dtype=np.float32)
    index = int(np.searchsorted(timestamps, time_seconds, side="right") - 1)
    index = max(0, min(index, len(trajectory.features) - 1))
    row = trajectory.features[index]
    return MouthFrame(float(row[0]), float(row[1]), float(row[2]))


@dataclass(frozen=True, slots=True)
class ConstantMouthDriver:
    frame: MouthFrame = MouthFrame(0.0, 0.0, 0.0)

    def predict(self, audio_path: Path, target_timestamps: np.ndarray) -> MouthTrajectory:
        timestamps = np.asarray(target_timestamps, dtype=np.float32)
        row = np.array([self.frame.jaw_open, self.frame.lip_close, self.frame.mouth_smile], dtype=np.float32)
        return MouthTrajectory(np.repeat(row[None, :], len(timestamps), axis=0), np.ones(len(timestamps), dtype=bool), target_fps(timestamps), timestamps=timestamps)

    def sample(self, time_seconds: float) -> MouthFrame:
        return self.frame


@dataclass(frozen=True, slots=True)
class AudioEnergyMouthDriver:
    fps: float = 30.0

    def predict(self, audio_path: Path, target_timestamps: np.ndarray) -> MouthTrajectory:
        from voice_face.prosody import extract_prosody, read_audio_mono

        timestamps = np.asarray(target_timestamps, dtype=np.float32)
        if not audio_path.exists():
            return MouthTrajectory(np.zeros((len(timestamps), 3), dtype=np.float32), np.zeros(len(timestamps), dtype=bool), target_fps(timestamps), timestamps=timestamps)
        prosody = extract_prosody(read_audio_mono(audio_path), timestamps)
        energy = prosody[:, 1]
        scale = max(float(np.percentile(energy, 95)), 1e-6)
        jaw = np.clip(energy / scale, 0.0, 1.0)
        voiced = prosody[:, 2]
        features = np.stack([jaw, 1.0 - voiced, np.zeros_like(jaw)], axis=-1).astype(np.float32)
        return MouthTrajectory(features, energy > 1e-5, target_fps(timestamps), timestamps=timestamps)


class BlendshapeMouthDriver:
    def __init__(self, tracking_npz: Path | None = None, *, timestamps: np.ndarray | None = None, blendshapes: np.ndarray | None = None, valid: np.ndarray | None = None, jaw_index: int = 25, lip_close_index: int = 27, smile_left_index: int = 44, smile_right_index: int = 45):
        if tracking_npz is not None:
            data = np.load(tracking_npz, allow_pickle=False)
            timestamps = data["timestamps"] if "timestamps" in data.files else data["timestamps_ms"].astype(np.float32) / 1000.0
            blendshapes = data["blendshapes"]
            valid = data["valid"]
        self._timestamps = np.asarray(timestamps if timestamps is not None else np.zeros(0), dtype=np.float32)
        self._blendshapes = np.nan_to_num(np.asarray(blendshapes if blendshapes is not None else np.zeros((len(self._timestamps), 0)), dtype=np.float32))
        self._valid = np.asarray(valid if valid is not None else np.zeros(len(self._timestamps), dtype=bool), dtype=bool)
        self._jaw_index = jaw_index
        self._lip_close_index = lip_close_index
        self._smile_left_index = smile_left_index
        self._smile_right_index = smile_right_index

    @classmethod
    def from_fit(cls, fit_npz: Path) -> "BlendshapeMouthDriver":
        data = np.load(fit_npz, allow_pickle=False)
        timestamps = data["timestamps"] if "timestamps" in data.files else data["timestamps_ms"].astype(np.float32) / 1000.0
        return cls(timestamps=timestamps, blendshapes=data["blendshapes"], valid=data["valid"])

    def predict(self, audio_path: Path, target_timestamps: np.ndarray) -> MouthTrajectory:
        timestamps = np.asarray(target_timestamps, dtype=np.float32)
        if len(self._timestamps) == 0:
            return MouthTrajectory(np.zeros((len(timestamps), 3), dtype=np.float32), np.zeros(len(timestamps), dtype=bool), target_fps(timestamps), timestamps=timestamps)
        source = np.zeros((len(self._timestamps), 3), dtype=np.float32)
        if self._blendshapes.shape[1] > self._jaw_index:
            source[:, 0] = self._blendshapes[:, self._jaw_index]
        if self._blendshapes.shape[1] > self._lip_close_index:
            source[:, 1] = self._blendshapes[:, self._lip_close_index]
        if self._blendshapes.shape[1] > max(self._smile_left_index, self._smile_right_index):
            source[:, 2] = 0.5 * (self._blendshapes[:, self._smile_left_index] + self._blendshapes[:, self._smile_right_index])
        features = resample_to_timestamps(self._timestamps, source, timestamps)
        valid = np.interp(timestamps, self._timestamps, self._valid.astype(np.float32), left=0.0, right=0.0) > 0.5
        return MouthTrajectory(features, valid, target_fps(timestamps), timestamps=timestamps)

    def sample(self, time_seconds: float) -> MouthFrame:
        return frame_at(self.predict(Path(""), np.asarray([time_seconds], dtype=np.float32)), time_seconds)


__all__ = ["MouthFrame", "MouthTrajectory", "MouthDriver", "ConstantMouthDriver", "AudioEnergyMouthDriver", "BlendshapeMouthDriver", "frame_at"]
