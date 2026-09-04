# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Audio-to-mouth regression for CPU-only lip-sync baselines."""

from __future__ import annotations

import json
import hashlib
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from voice_face.alignment import resample_to_timestamps, target_fps
from voice_face.mouth import MouthTrajectory
from voice_face.prosody import AudioSignal, extract_prosody, read_audio_mono


FeatureMode = Literal["prosody", "wavlm"]
DEFAULT_WAVLM_MODEL_ID = "microsoft/wavlm-base-plus"


def audio_mouth_features(audio_path: Path, timestamps: np.ndarray, *, feature_mode: FeatureMode = "prosody", cache_dir: Path | None = None, model_id: str = DEFAULT_WAVLM_MODEL_ID) -> np.ndarray:
    if feature_mode == "wavlm":
        return WavLMFeatureCache(model_id=model_id, cache_dir=cache_dir).features(audio_path, timestamps)
    prosody = extract_prosody(read_audio_mono(audio_path), timestamps)
    f0 = prosody[:, 0]
    energy = prosody[:, 1]
    voiced = prosody[:, 2]
    log_energy = np.log1p(energy * 100.0)
    f0_norm = np.where(f0 > 0.0, f0 / 300.0, 0.0)
    d_energy = np.gradient(log_energy) if len(log_energy) > 1 else np.zeros_like(log_energy)
    d_f0 = np.gradient(f0_norm) if len(f0_norm) > 1 else np.zeros_like(f0_norm)
    return np.stack([log_energy, f0_norm, voiced, d_energy, d_f0, log_energy * voiced, np.ones_like(log_energy)], axis=-1).astype(np.float32)


def _resample_audio(audio: AudioSignal, sample_rate: int) -> AudioSignal:
    if audio.sample_rate == sample_rate:
        return audio
    duration = len(audio.samples) / float(audio.sample_rate) if audio.sample_rate else 0.0
    size = max(1, int(round(duration * sample_rate)))
    source_t = np.arange(len(audio.samples), dtype=np.float32) / float(audio.sample_rate)
    target_t = np.arange(size, dtype=np.float32) / float(sample_rate)
    samples = np.interp(target_t, source_t, audio.samples).astype(np.float32) if len(source_t) else np.zeros(size, dtype=np.float32)
    return AudioSignal(samples, sample_rate)


@lru_cache(maxsize=2)
def _load_wavlm(model_id: str, model_cache: str | None):
    from transformers import AutoFeatureExtractor, AutoModel, AutoProcessor

    try:
        processor = AutoProcessor.from_pretrained(model_id, cache_dir=model_cache)
    except (OSError, ValueError, TypeError):
        processor = AutoFeatureExtractor.from_pretrained(model_id, cache_dir=model_cache)
    model = AutoModel.from_pretrained(model_id, device_map="auto", cache_dir=model_cache)
    model.eval()
    return processor, model


@dataclass(frozen=True, slots=True)
class WavLMFeatureCache:
    model_id: str = DEFAULT_WAVLM_MODEL_ID
    cache_dir: Path | None = None

    def features(self, audio_path: Path, timestamps: np.ndarray) -> np.ndarray:
        hidden_timestamps, hidden = self._hidden_states(audio_path)
        aligned = resample_to_timestamps(hidden_timestamps, hidden, np.asarray(timestamps, dtype=np.float32))
        return np.concatenate([aligned.astype(np.float32), np.ones((len(aligned), 1), dtype=np.float32)], axis=1)

    def _hidden_states(self, audio_path: Path) -> tuple[np.ndarray, np.ndarray]:
        cache_path = self._cache_path(audio_path)
        if cache_path is not None and cache_path.exists():
            data = np.load(cache_path, allow_pickle=False)
            return data["timestamps"].astype(np.float32), data["features"].astype(np.float32)
        timestamps, hidden = self._extract_hidden_states(audio_path)
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(cache_path, timestamps=timestamps, features=hidden, model_id=self.model_id)
        return timestamps, hidden

    def _cache_path(self, audio_path: Path) -> Path | None:
        if self.cache_dir is None:
            return None
        audio = read_audio_mono(audio_path)
        digest = hashlib.sha256()
        digest.update(self.model_id.encode("utf-8"))
        digest.update(b"wavlm-v1")
        digest.update(str(audio.sample_rate).encode("ascii"))
        digest.update(np.asarray(audio.samples, dtype=np.float32).tobytes())
        return self.cache_dir / "features" / f"{digest.hexdigest()}.npz"

    def _extract_hidden_states(self, audio_path: Path) -> tuple[np.ndarray, np.ndarray]:
        import torch

        model_cache = str(self.cache_dir / "model") if self.cache_dir else None
        processor, model = _load_wavlm(self.model_id, model_cache)
        sample_rate = int(getattr(getattr(processor, "feature_extractor", processor), "sampling_rate", 16000))
        audio = _resample_audio(read_audio_mono(audio_path), sample_rate)
        inputs = processor(audio.samples, sampling_rate=sample_rate, return_tensors="pt")
        device = getattr(model, "device", torch.device("cpu"))
        inputs = inputs.to(device)
        with torch.no_grad():
            hidden = model(**inputs).last_hidden_state.squeeze(0).detach().cpu().numpy().astype(np.float32)
        duration = len(audio.samples) / float(sample_rate) if sample_rate else 0.0
        timestamps = np.linspace(0.0, duration, num=len(hidden), endpoint=False, dtype=np.float32)
        return timestamps, hidden


def mouth_targets_from_fit(fit_path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.load(fit_path, allow_pickle=False)
    timestamps = data["timestamps"] if "timestamps" in data.files else data["timestamps_ms"].astype(np.float32) / 1000.0
    blend = np.nan_to_num(data["blendshapes"].astype(np.float32))
    target = np.zeros((len(timestamps), 3), dtype=np.float32)
    if blend.shape[1] > 25:
        target[:, 0] = blend[:, 25]
    if blend.shape[1] > 27:
        target[:, 1] = blend[:, 27]
    if blend.shape[1] > 45:
        target[:, 2] = 0.5 * (blend[:, 44] + blend[:, 45])
    return timestamps.astype(np.float32), target


def fit_audio_mouth_model(samples: list[tuple[Path, Path]], output_path: Path, *, ridge: float = 1e-3, feature_mode: FeatureMode = "prosody", cache_dir: Path | None = None, model_id: str = DEFAULT_WAVLM_MODEL_ID) -> Path:
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    failures: list[dict[str, str]] = []
    for fit_path, audio_path in samples:
        try:
            timestamps, target = mouth_targets_from_fit(fit_path)
            xs.append(audio_mouth_features(audio_path, timestamps, feature_mode=feature_mode, cache_dir=cache_dir, model_id=model_id))
            ys.append(target)
        except Exception as exc:
            failures.append({"fit": str(fit_path), "audio": str(audio_path), "error": str(exc)})
    if not xs:
        raise RuntimeError("No audio-mouth training samples available")
    x = np.concatenate(xs, axis=0).astype(np.float32)
    y = np.concatenate(ys, axis=0).astype(np.float32)
    reg = np.eye(x.shape[1], dtype=np.float32) * float(ridge)
    weights = np.linalg.solve(x.T @ x + reg, x.T @ y).astype(np.float32)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    feature_names = ["log_energy", "f0_norm", "voiced", "d_energy", "d_f0", "voiced_energy", "bias"] if feature_mode == "prosody" else [f"wavlm_{i}" for i in range(x.shape[1] - 1)] + ["bias"]
    np.savez_compressed(output_path, weights=weights, feature_mode=feature_mode, model_id=model_id, feature_names=json.dumps(feature_names), target_names=json.dumps(["jaw_open", "lip_close", "mouth_smile"]), failures=json.dumps(failures, sort_keys=True))
    return output_path


@dataclass(frozen=True, slots=True)
class AudioRegressionMouthDriver:
    model_path: Path
    cache_dir: Path | None = None

    def predict(self, audio_path: Path, target_timestamps: np.ndarray) -> MouthTrajectory:
        data = np.load(self.model_path, allow_pickle=False)
        feature_mode_raw = str(data["feature_mode"]) if "feature_mode" in data.files else "prosody"
        if feature_mode_raw not in ("prosody", "wavlm"):
            raise ValueError(f"Unsupported audio mouth feature mode: {feature_mode_raw}")
        feature_mode: FeatureMode = "wavlm" if feature_mode_raw == "wavlm" else "prosody"
        model_id = str(data["model_id"]) if "model_id" in data.files else DEFAULT_WAVLM_MODEL_ID
        features = audio_mouth_features(audio_path, np.asarray(target_timestamps, dtype=np.float32), feature_mode=feature_mode, cache_dir=self.cache_dir, model_id=model_id) @ data["weights"].astype(np.float32)
        features = np.clip(features, 0.0, 1.0).astype(np.float32)
        valid = np.isfinite(features).all(axis=1)
        return MouthTrajectory(features, valid, target_fps(target_timestamps), timestamps=np.asarray(target_timestamps, dtype=np.float32))
