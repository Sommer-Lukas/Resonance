# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Prediction helpers for fitted samples and free audio."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from voice_face.fusion import FusionConfig, fuse_torch
from voice_face.mouth_adapter import MouthExpressionAdapter
from voice_face.prosody import extract_prosody, read_audio_mono


def free_audio_features(audio_path: Path, expression_dim: int, *, fps: float = 30.0, mouth_model: Path | None = None, mouth_cache_dir: Path | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    audio = read_audio_mono(audio_path)
    duration = len(audio.samples) / float(audio.sample_rate) if audio.sample_rate else 0.0
    frames = max(1, int(round(duration * fps)))
    timestamps = np.arange(frames, dtype=np.float32) / float(fps)
    prosody = extract_prosody(audio, timestamps)
    energy = prosody[:, 1]
    norm = energy / max(float(np.percentile(energy, 95)), 1e-6)
    if mouth_model is not None:
        from voice_face.audio_mouth import AudioRegressionMouthDriver
        features = AudioRegressionMouthDriver(mouth_model, cache_dir=mouth_cache_dir).predict(audio_path, timestamps).features
    else:
        features = np.stack([np.clip(norm, 0.0, 1.0), 1.0 - prosody[:, 2], np.zeros_like(norm)], axis=-1).astype(np.float32)
    mouth_expression = MouthExpressionAdapter(expression_dim).transform(features)
    return timestamps, mouth_expression, prosody


def smooth_expression(expression: np.ndarray, alpha: float = 0.35) -> np.ndarray:
    if len(expression) < 2 or alpha <= 0.0:
        return expression.astype(np.float32)
    out = expression.astype(np.float32).copy()
    for i in range(1, len(out)):
        out[i] = alpha * out[i] + (1.0 - alpha) * out[i - 1]
    return out


def predict_checkpoint(checkpoint: Path, mouth_expression: np.ndarray, prosody: np.ndarray, emotion: str, intensity: float, *, preserve_mouth: float = 0.0, smooth_alpha: float = 0.0) -> np.ndarray:
    import torch
    from voice_face.models import build_model

    ckpt = torch.load(checkpoint, map_location="cpu")
    cfg = ckpt["config"]
    model = build_model(cfg["model"], mouth_dim=ckpt["mouth_dim"], output_dim=ckpt["output_dim"], hidden_dim=cfg.get("hidden_dim", 256), num_emotions=ckpt["num_emotions"], prosody_dim=ckpt.get("prosody_dim", 3), emotion_dim=cfg.get("emotion_dim", 16), layers=cfg.get("layers", 2), dropout=cfg.get("dropout", 0.0), causal=cfg.get("causal", True))
    model.load_state_dict(ckpt["state_dict"]); model.eval()
    label_to_index = ckpt.get("label_to_index", {})
    normalized_intensity = float(intensity) / 3.0 if intensity > 1.0 else float(intensity)
    with torch.no_grad():
        residual = model(torch.from_numpy(mouth_expression).unsqueeze(0).float(), emotion_index=torch.tensor([int(label_to_index.get(emotion, 0))]), intensity=torch.tensor([normalized_intensity]), prosody=torch.from_numpy(prosody).unsqueeze(0).float())
        fused = fuse_torch(torch.from_numpy(mouth_expression).unsqueeze(0).float(), residual, FusionConfig(preserve_mouth=preserve_mouth, clamp=5.0)).squeeze(0).cpu().numpy().astype(np.float32)
        return smooth_expression(fused, smooth_alpha)


def save_prediction(path: Path, timestamps: np.ndarray, expression: np.ndarray, identity: np.ndarray, rotation: np.ndarray, translation: np.ndarray, metadata: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, timestamps=timestamps.astype(np.float32), expression=expression.astype(np.float32), identity=identity.astype(np.float32), rotation=rotation.astype(np.float32), rotations=rotation.astype(np.float32), translation=translation.astype(np.float32), metadata=json.dumps(metadata, sort_keys=True))
    return path
