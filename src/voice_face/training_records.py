"""Synchronized training-record serialization for fitted MEAD face sequences."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from voice_face.alignment import nearest_valid, resample_to_timestamps, target_fps
from voice_face.data.mead import MeadSample
from voice_face.io import should_skip, write_json
from voice_face.mouth import AudioEnergyMouthDriver, MouthDriver, MouthTrajectory
from voice_face.mouth_adapter import MouthExpressionAdapter
from voice_face.prosody import PROSODY_FEATURE_NAMES, prosody_from_audio


@dataclass(frozen=True, slots=True)
class TrainingSequence:
    timestamps: np.ndarray
    beta_target: np.ndarray
    mouth: MouthTrajectory
    mouth_expression: np.ndarray
    prosody: np.ndarray
    valid: np.ndarray
    emotion: str
    intensity: int
    actor_id: str
    sample_id: str
    transcript: str = ""
    metadata: dict[str, object] | None = None

    @property
    def target_expression(self) -> np.ndarray:
        return self.beta_target



def _metadata_from_fit(data: np.lib.npyio.NpzFile) -> dict[str, object]:
    return json.loads(str(data["metadata"])) if "metadata" in data.files else {}


def _fit_timestamps(data: np.lib.npyio.NpzFile) -> np.ndarray:
    return data["timestamps"].astype(np.float32) if "timestamps" in data.files else data["timestamps_ms"].astype(np.float32) / 1000.0


def _audio_path(sample: MeadSample | None, meta: dict[str, object]) -> Path | None:
    if sample is not None and sample.audio_path is not None and sample.audio_path.exists():
        return sample.audio_path
    for key in ("source_audio", "source_video"):
        if meta.get(key):
            candidate = Path(str(meta[key]))
            if candidate.exists():
                return candidate
    return None


def build_training_sequence(fit_path: Path, sample: MeadSample | None = None, *, mouth_driver: MouthDriver | None = None, transcript: str = "") -> TrainingSequence:
    data = np.load(fit_path, allow_pickle=False)
    meta = _metadata_from_fit(data)
    timestamps = _fit_timestamps(data)
    beta_target = data["expression_smoothed"] if "expression_smoothed" in data.files else data["expression"]
    fit_valid = data["valid"].astype(bool)
    audio = _audio_path(sample, meta)
    if audio is None:
        raise FileNotFoundError(f"No audio available for {fit_path.name}")
    driver = mouth_driver or AudioEnergyMouthDriver()
    mouth_raw = driver.predict(audio, timestamps)
    mouth_timestamps = np.asarray(mouth_raw.timestamps, dtype=np.float32)
    mouth_features = resample_to_timestamps(mouth_timestamps, mouth_raw.features, timestamps)
    mouth_valid = nearest_valid(mouth_timestamps, mouth_raw.valid, timestamps)
    mouth = MouthTrajectory(mouth_features, mouth_valid, target_fps(timestamps), mouth_raw.feature_names, timestamps)
    mouth_expression = MouthExpressionAdapter(int(beta_target.shape[1])).transform(mouth.features)
    prosody = prosody_from_audio(audio, timestamps)
    stem = fit_path.stem.split("__")
    actor_id = sample.actor_id if sample else (stem[0] if stem else str(meta.get("actor_id", meta.get("actor", "unknown"))))
    emotion = sample.emotion if sample else (stem[2] if len(stem) > 2 else str(meta.get("emotion", "unknown")))
    intensity = sample.intensity if sample else int(float(str(meta.get("intensity", 1))))
    sample_id = sample.sample_id if sample else fit_path.stem
    valid = fit_valid & mouth.valid & (prosody[:, 1] > 0.0)
    record_meta = dict(meta)
    record_meta.update({"version": 1, "fit_path": str(fit_path.resolve()), "audio_path": str(audio.resolve()), "prosody_feature_names": PROSODY_FEATURE_NAMES})
    return TrainingSequence(timestamps.astype(np.float32), np.nan_to_num(beta_target.astype(np.float32)), mouth, mouth_expression, prosody.astype(np.float32), valid, emotion, intensity, actor_id, sample_id, transcript, record_meta)


def save_training_sequence(sequence: TrainingSequence, path: Path, *, force: bool = False) -> Path:
    if should_skip(path, force):
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        timestamps=sequence.timestamps.astype(np.float32),
        beta_target=sequence.beta_target.astype(np.float32),
        mouth=sequence.mouth.features.astype(np.float32),
        mouth_expression=sequence.mouth_expression.astype(np.float32),
        mouth_valid=sequence.mouth.valid.astype(bool),
        mouth_timestamps=np.asarray(sequence.mouth.timestamps, dtype=np.float32),
        prosody=sequence.prosody.astype(np.float32),
        valid=sequence.valid.astype(bool),
        emotion=sequence.emotion,
        intensity=int(sequence.intensity),
        actor_id=sequence.actor_id,
        sample_id=sequence.sample_id,
        transcript=sequence.transcript,
        mouth_feature_names=json.dumps(sequence.mouth.feature_names),
        prosody_feature_names=json.dumps(PROSODY_FEATURE_NAMES),
        metadata=json.dumps(sequence.metadata or {}, sort_keys=True),
    )
    return path


def load_training_sequence(path: Path) -> TrainingSequence:
    data = np.load(path, allow_pickle=False)
    mouth = MouthTrajectory(data["mouth"].astype(np.float32), data["mouth_valid"].astype(bool), target_fps(data["timestamps"]), tuple(json.loads(str(data["mouth_feature_names"]))), data["mouth_timestamps"].astype(np.float32))
    return TrainingSequence(
        data["timestamps"].astype(np.float32),
        data["beta_target"].astype(np.float32),
        mouth,
        data["mouth_expression"].astype(np.float32),
        data["prosody"].astype(np.float32),
        data["valid"].astype(bool),
        str(data["emotion"]),
        int(data["intensity"]),
        str(data["actor_id"]),
        str(data["sample_id"]),
        str(data["transcript"]),
        json.loads(str(data["metadata"])),
    )


def write_failure_report(path: Path, failures: list[dict[str, str]]) -> Path:
    write_json(path, {"failures": failures, "failure_count": len(failures)})
    return path
