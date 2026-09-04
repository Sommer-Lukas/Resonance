# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Quantitative evaluation for speech-only, static, GRU and TCN models."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from voice_face.dataset import TrainingSequenceDataset, discover_training_records, read_actor_splits, write_actor_splits
from voice_face.fusion import FusionConfig, fuse_numpy, fuse_torch
from voice_face.io import write_json
from voice_face.losses import LossConfig, loss_components
from voice_face.models import StaticEmotionTable, build_model, require_torch
from voice_face.training_records import load_training_sequence


def _numpy_metrics(pred: np.ndarray, target: np.ndarray, valid: np.ndarray) -> dict[str, float]:
    mask = valid.astype(bool)
    if not mask.any():
        return {"geometry_error": float("nan"), "mouth_error": float("nan"), "emotion_region_error": float("nan"), "velocity_error": float("nan"), "acceleration_error": float("nan")}
    split = max(1, pred.shape[-1] // 5)
    geom = float(np.mean((pred[mask] - target[mask]) ** 2))
    mouth = float(np.mean((pred[mask, :split] - target[mask, :split]) ** 2))
    upper = float(np.mean((pred[mask, split:] - target[mask, split:]) ** 2)) if pred.shape[-1] > split else 0.0
    vmask = mask[1:] & mask[:-1]
    vel = float(np.mean(((pred[1:] - pred[:-1]) - (target[1:] - target[:-1]))[vmask] ** 2)) if vmask.any() else float("nan")
    amask = mask[2:] & mask[1:-1] & mask[:-2]
    pa = pred[2:] - 2 * pred[1:-1] + pred[:-2]
    ta = target[2:] - 2 * target[1:-1] + target[:-2]
    acc = float(np.mean((pa - ta)[amask] ** 2)) if amask.any() else float("nan")
    return {"geometry_error": geom, "mouth_error": mouth, "emotion_region_error": upper, "velocity_error": vel, "acceleration_error": acc}


def _load_torch_checkpoint(path: Path):
    torch = require_torch()
    ckpt = torch.load(path, map_location="cpu")
    cfg = ckpt["config"]
    model = build_model(cfg["model"], mouth_dim=ckpt["mouth_dim"], output_dim=ckpt["output_dim"], hidden_dim=cfg.get("hidden_dim", 256), num_emotions=ckpt["num_emotions"], prosody_dim=ckpt.get("prosody_dim", 3), emotion_dim=cfg.get("emotion_dim", 16), layers=cfg.get("layers", 2), dropout=cfg.get("dropout", 0.0), causal=cfg.get("causal", True))
    model.load_state_dict(ckpt["state_dict"]); model.eval()
    return model, ckpt


def _smooth_expression(expression: np.ndarray, alpha: float) -> np.ndarray:
    if len(expression) < 2 or alpha <= 0.0:
        return expression.astype(np.float32)
    out = expression.astype(np.float32).copy()
    for i in range(1, len(out)):
        out[i] = alpha * out[i] + (1.0 - alpha) * out[i - 1]
    return out


def predict_record(model_name: str, checkpoint: Path | None, sequence_path: Path, label_to_index: dict[str, int] | None = None, *, preserve_mouth: float = 0.0, smooth_alpha: float = 0.0) -> np.ndarray:
    seq = load_training_sequence(sequence_path)
    key = model_name.lower()
    if key == "b0":
        return seq.mouth_expression
    if key == "b1":
        if checkpoint is None:
            raise ValueError("B1 requires a static table checkpoint")
        table, labels = StaticEmotionTable.load(checkpoint)
        index = labels.get(seq.emotion, 0)
        residual = table.predict_numpy(seq.mouth_expression, index, float(seq.intensity))
        return _smooth_expression(fuse_numpy(seq.mouth_expression, residual, FusionConfig(preserve_mouth=preserve_mouth)), smooth_alpha)
    if checkpoint is None:
        raise ValueError(f"{model_name} requires a checkpoint")
    torch = require_torch(); model, ckpt = _load_torch_checkpoint(checkpoint)
    labels = label_to_index or ckpt.get("label_to_index", {})
    emotion_index = torch.tensor([int(labels.get(seq.emotion, 0))])
    intensity = torch.tensor([float(seq.intensity) / 3.0])
    mouth = torch.from_numpy(seq.mouth_expression).unsqueeze(0).float()
    prosody = torch.from_numpy(seq.prosody).unsqueeze(0).float()
    start = time.perf_counter()
    with torch.no_grad():
        residual = model(mouth, emotion_index=emotion_index, intensity=intensity, prosody=prosody)
        pred = fuse_torch(mouth, residual, FusionConfig(preserve_mouth=preserve_mouth)).squeeze(0).cpu().numpy().astype(np.float32)
    _ = time.perf_counter() - start
    return _smooth_expression(pred, smooth_alpha)


def evaluate_models(records_dir: Path, output_json: Path, output_csv: Path, *, split: str = "test", split_path: Path | None = None, b1: Path | None = None, gru: Path | None = None, tcn: Path | None = None) -> Path:
    records = discover_training_records(records_dir)
    if not records:
        raise RuntimeError(f"No TrainingSequence records found in {records_dir}")
    split_path = split_path or output_json.with_suffix(".splits.json")
    if not split_path.exists():
        write_actor_splits(records, split_path)
    mapping = read_actor_splits(split_path)
    selected = [r for r in records if mapping.get(r.actor) == ("val" if split == "validation" else split)] or records
    checkpoints = {"b0": None, "b1": b1, "gru": gru, "tcn": tcn}
    rows: list[dict[str, Any]] = []
    for model_name, ckpt in checkpoints.items():
        if model_name != "b0" and ckpt is None:
            continue
        for record in selected:
            seq = load_training_sequence(record.path)
            start = time.perf_counter()
            pred = predict_record(model_name, ckpt, record.path)
            elapsed = max(time.perf_counter() - start, 1e-9)
            metrics = _numpy_metrics(pred, seq.beta_target, seq.valid)
            rows.append({"model": model_name, "sample_id": seq.sample_id, "actor": seq.actor_id, "emotion": seq.emotion, "intensity": seq.intensity, "frames": len(seq.timestamps), "inference_seconds": elapsed, "fps": len(seq.timestamps) / elapsed, **metrics})
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["model"])
        writer.writeheader(); writer.writerows(rows)
    summary = {"split": split, "records": len(selected), "rows": rows}
    write_json(output_json, summary)
    return output_json


evaluate = evaluate_models
