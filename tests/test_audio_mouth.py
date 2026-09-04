import json
import math
import importlib.util
import wave
from pathlib import Path

import numpy as np

from voice_face.audio_mouth import AudioRegressionMouthDriver, WavLMFeatureCache, fit_audio_mouth_model, mouth_targets_from_fit


def _write_wav(path: Path, seconds: float = 0.16, sample_rate: int = 16000) -> None:
    samples = (0.4 * np.sin(2.0 * math.pi * 180.0 * np.arange(int(seconds * sample_rate)) / sample_rate)).astype(np.float32)
    pcm = np.clip(samples * 32767.0, -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def _write_fit(path: Path) -> None:
    timestamps = np.asarray([0.0, 0.04, 0.08, 0.12], dtype=np.float32)
    blendshapes = np.zeros((4, 52), dtype=np.float32)
    blendshapes[:, 25] = [0.0, 0.3, 0.8, 0.2]
    blendshapes[:, 19] = [0.9, 0.9, 0.9, 0.9]
    blendshapes[:, 27] = [0.2, 0.3, 0.1, 0.4]
    blendshapes[:, 44] = [0.1, 0.2, 0.3, 0.2]
    blendshapes[:, 45] = [0.2, 0.4, 0.2, 0.1]
    np.savez_compressed(path, timestamps=timestamps, blendshapes=blendshapes, metadata=json.dumps({}))


def test_mouth_targets_use_mediapipe_mouth_close_not_eye_squint(tmp_path):
    fit = tmp_path / "fit.npz"
    _write_fit(fit)
    _, target = mouth_targets_from_fit(fit)
    assert np.allclose(target[:, 1], [0.2, 0.3, 0.1, 0.4])


def test_infer_audio_defaults_to_fixed_wavlm_mouth_model():
    script = Path(__file__).resolve().parents[1] / "scripts" / "infer_audio.py"
    spec = importlib.util.spec_from_file_location("infer_audio", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DEFAULT_MOUTH_MODEL.name == "audio_mouth_wavlm_240_fixed.npz"


def test_wavlm_feature_cache_reuses_saved_hidden_states(tmp_path, monkeypatch):
    audio = tmp_path / "clip.wav"
    _write_wav(audio)
    cache = WavLMFeatureCache(cache_dir=tmp_path / "cache")
    calls = {"count": 0}

    def fake_extract(_audio_path):
        calls["count"] += 1
        return np.asarray([0.0, 0.08], dtype=np.float32), np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    monkeypatch.setattr(WavLMFeatureCache, "_extract_hidden_states", lambda self, audio_path: fake_extract(audio_path))
    timestamps = np.asarray([0.0, 0.04, 0.08], dtype=np.float32)
    first = cache.features(audio, timestamps)
    second = cache.features(audio, timestamps)
    assert calls["count"] == 1
    assert first.shape == (3, 3)
    assert np.allclose(first, second)
    assert np.all(first[:, -1] == 1.0)


def test_wavlm_audio_mouth_model_trains_and_predicts_from_cache(tmp_path):
    audio = tmp_path / "clip.wav"
    fit = tmp_path / "fit.npz"
    model = tmp_path / "mouth.npz"
    cache = WavLMFeatureCache(cache_dir=tmp_path / "cache")
    _write_wav(audio)
    _write_fit(fit)
    cache_path = cache._cache_path(audio)
    assert cache_path is not None
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache_path, timestamps=np.asarray([0.0, 0.04, 0.08, 0.12], dtype=np.float32), features=np.eye(4, dtype=np.float32), model_id=cache.model_id)
    fit_audio_mouth_model([(fit, audio)], model, feature_mode="wavlm", cache_dir=tmp_path / "cache")
    data = np.load(model, allow_pickle=False)
    assert str(data["feature_mode"]) == "wavlm"
    assert data["weights"].shape == (5, 3)
    mouth = AudioRegressionMouthDriver(model, cache_dir=tmp_path / "cache").predict(audio, np.asarray([0.0, 0.04, 0.08], dtype=np.float32))
    assert mouth.features.shape == (3, 3)
    assert np.isfinite(mouth.features).all()
    assert np.all((mouth.features >= 0.0) & (mouth.features <= 1.0))
