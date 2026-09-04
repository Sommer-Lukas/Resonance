# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Training and evaluation loops for emotional residual face models."""

from __future__ import annotations

import csv
import json
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np

from voice_face.dataset import TrainingSequenceDataset, discover_training_records, read_actor_splits, write_actor_splits
from voice_face.fusion import FusionConfig, fuse_torch
from voice_face.io import read_config, write_json
from voice_face.losses import LossConfig, combine_losses, loss_components
from voice_face.models import build_model, build_static_table, require_torch


@dataclass(frozen=True, slots=True)
class TrainConfig:
    model: str = "gru"
    epochs: int = 2
    lr: float = 1e-3
    hidden_dim: int = 256
    emotion_dim: int = 16
    layers: int = 2
    dropout: float = 0.1
    batch_size: int = 1
    seed: int = 7
    patience: int = 5
    grad_clip: float = 1.0
    causal: bool = True


def load_train_config(path: Path | None) -> tuple[TrainConfig, LossConfig, dict[str, Any]]:
    payload = read_config(path) if path else {}
    model = payload.get("model", {})
    training = payload.get("training", {})
    losses = payload.get("losses", {})
    return TrainConfig(**{k: v for k, v in {**model, **training}.items() if k in TrainConfig.__dataclass_fields__}), LossConfig(**{k: v for k, v in losses.items() if k in LossConfig.__dataclass_fields__}), payload


def _collate_one(batch):
    return batch[0]


def _seed(seed: int) -> None:
    torch = require_torch()
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    torch.use_deterministic_algorithms(False)


def _batch(item: dict[str, Any], device: str):
    torch = require_torch()
    return {
        "mouth_expression": cast(Any, item["mouth_expression"]).unsqueeze(0).float().to(device),
        "prosody": cast(Any, item["prosody"]).unsqueeze(0).float().to(device),
        "target_expression": cast(Any, item["target_expression"]).unsqueeze(0).float().to(device),
        "valid": cast(Any, item["valid"]).unsqueeze(0).bool().to(device),
        "emotion_index": cast(Any, item["emotion_index"]).reshape(1).long().to(device),
        "intensity": cast(Any, item["intensity"]).reshape(1).float().to(device),
    }


def _metrics(model, dataset, loss_config: LossConfig, fusion_config: FusionConfig, device: str) -> dict[str, float]:
    torch = require_torch()
    totals: dict[str, list[float]] = {"total": [], "geometry": [], "mouth": [], "emotion_region": [], "velocity": [], "acceleration": [], "residual": []}
    model.eval()
    with torch.no_grad():
        for item in dataset:
            b = _batch(item, device)
            residual = model(b["mouth_expression"], emotion_index=b["emotion_index"], intensity=b["intensity"], prosody=b["prosody"])
            pred = fuse_torch(b["mouth_expression"], residual, fusion_config)
            comps = loss_components(pred, b["target_expression"], residual, b["valid"], loss_config)
            total = combine_losses(comps, loss_config)
            totals["total"].append(float(total.cpu()))
            for key, value in comps.items():
                totals[key].append(float(value.cpu()))
    return {k: float(np.mean(v)) if v else float("nan") for k, v in totals.items()}


def train_records(records_dir: Path, output_path: Path, config: TrainConfig = TrainConfig(), loss_config: LossConfig = LossConfig(), *, split_path: Path | None = None, fusion_config: FusionConfig = FusionConfig(), resume: Path | None = None, device: str = "cpu") -> Path:
    torch = require_torch(); _seed(config.seed)
    records = discover_training_records(records_dir)
    if not records:
        raise RuntimeError(f"No TrainingSequence records found in {records_dir}")
    split_path = split_path or output_path.with_suffix(".splits.json")
    if not split_path.exists():
        write_actor_splits(records, split_path)
    train_ds = TrainingSequenceDataset(records, split="train", split_path=split_path)
    val_ds = TrainingSequenceDataset(records, split="val", split_path=split_path, emotion_to_index=train_ds.label_to_index)
    if len(train_ds) == 0:
        train_ds = TrainingSequenceDataset(records, split="val", split_path=split_path)
    first = train_ds[0]
    mouth_dim = int(cast(Any, first["mouth_expression"]).shape[-1]); prosody_dim = int(cast(Any, first["prosody"]).shape[-1]); output_dim = int(cast(Any, first["target_expression"]).shape[-1])
    model = build_model(config.model, mouth_dim=mouth_dim, output_dim=output_dim, hidden_dim=config.hidden_dim, num_emotions=len(train_ds.label_to_index), prosody_dim=prosody_dim, emotion_dim=config.emotion_dim, layers=config.layers, dropout=config.dropout, causal=config.causal).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=config.lr)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=2)
    start_epoch = 0; best = float("inf"); history = []
    if resume and resume.exists():
        ckpt = torch.load(resume, map_location=device)
        model.load_state_dict(ckpt["state_dict"]); opt.load_state_dict(ckpt["optimizer"]); start_epoch = int(ckpt.get("epoch", 0)) + 1; best = float(ckpt.get("best_val", best)); history = list(ckpt.get("history", []))
    loader = torch.utils.data.DataLoader(cast(Any, train_ds), batch_size=1, shuffle=True, collate_fn=_collate_one)
    bad_epochs = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    for epoch in range(start_epoch, config.epochs):
        model.train(); train_losses = []
        for item in loader:
            b = _batch(item, device)
            residual = model(b["mouth_expression"], emotion_index=b["emotion_index"], intensity=b["intensity"], prosody=b["prosody"])
            pred = fuse_torch(b["mouth_expression"], residual, fusion_config)
            comps = loss_components(pred, b["target_expression"], residual, b["valid"], loss_config)
            total = combine_losses(comps, loss_config)
            if not torch.isfinite(total):
                raise RuntimeError("NaN/Inf loss detected")
            opt.zero_grad(); total.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip); opt.step()
            train_losses.append(float(total.detach().cpu()))
        val_metrics = _metrics(model, val_ds if len(val_ds) else train_ds, loss_config, fusion_config, device)
        sched.step(val_metrics["total"])
        row = {"epoch": epoch, "train_total": float(np.mean(train_losses)), **{f"val_{k}": v for k, v in val_metrics.items()}}
        history.append(row); write_json(output_path.with_suffix(".json"), {"history": history, "split_path": str(split_path), "records": len(records)})
        checkpoint = {"state_dict": model.state_dict(), "optimizer": opt.state_dict(), "epoch": epoch, "best_val": best, "config": asdict(config), "loss_config": asdict(loss_config), "fusion_config": asdict(fusion_config), "mouth_dim": mouth_dim, "prosody_dim": prosody_dim, "output_dim": output_dim, "num_emotions": len(train_ds.label_to_index), "label_to_index": train_ds.label_to_index, "history": history}
        torch.save(checkpoint, output_path.with_suffix(".last.pt"))
        if val_metrics["total"] < best:
            best = val_metrics["total"]; checkpoint["best_val"] = best; torch.save(checkpoint, output_path); bad_epochs = 0
        else:
            bad_epochs += 1
        if bad_epochs >= config.patience:
            break
    return output_path


def train_static(records_dir: Path, output_path: Path, *, split_path: Path | None = None) -> Path:
    records = discover_training_records(records_dir)
    split_path = split_path or output_path.with_suffix(".splits.json")
    if not split_path.exists():
        write_actor_splits(records, split_path)
    mapping = read_actor_splits(split_path)
    train_records_local = [r for r in records if mapping.get(r.actor) == "train"] or records
    labels = {label: i for i, label in enumerate(sorted({r.emotion for r in records}))}
    table = build_static_table(train_records_local, labels)
    table.save(output_path, labels)
    write_json(output_path.with_suffix(".json"), {"model": "b1", "records": len(train_records_local), "split_path": str(split_path), "label_to_index": labels})
    return output_path


train = train_records
