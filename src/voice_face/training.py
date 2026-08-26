# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Minimal train/evaluate loops for fitted residual baselines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np

from voice_face.dataset import GnmTrajectoryDataset, discover_fits, write_actor_splits
from voice_face.io import write_json
from voice_face.losses import LossConfig, trajectory_loss
from voice_face.models import build_model, require_torch


@dataclass(frozen=True, slots=True)
class TrainConfig:
    model: str = "b0"
    epochs: int = 1
    lr: float = 1e-3
    hidden_dim: int = 128


def _collate_one(batch):
    return batch[0]


def _target_residual(target_expression):
    baseline = target_expression[:, :1, :].expand_as(target_expression)
    return target_expression - baseline


def train(fits_dir: Path, output_path: Path, config: TrainConfig = TrainConfig(), loss_config: LossConfig = LossConfig()) -> Path:
    torch = require_torch()
    records = discover_fits(fits_dir)
    split_path = output_path.with_suffix(".splits.json")
    write_actor_splits(records, split_path)
    dataset = GnmTrajectoryDataset(records, split="train", split_path=split_path)
    if len(dataset) == 0:
        raise RuntimeError("No training fits found")
    first = dataset[0]
    mouth0 = cast(Any, first["mouth"])
    target0 = cast(Any, first["target_expression"])
    model = build_model(config.model, mouth_dim=mouth0.shape[-1], output_dim=target0.shape[-1], hidden_dim=config.hidden_dim, num_emotions=len(dataset.label_to_index))
    opt = torch.optim.Adam(model.parameters(), lr=config.lr)
    loader = torch.utils.data.DataLoader(cast(Any, dataset), batch_size=1, shuffle=True, collate_fn=_collate_one)
    history = []
    for _ in range(config.epochs):
        losses = []
        for batch in loader:
            mouth = cast(Any, batch["mouth"]).unsqueeze(0).float()
            target = cast(Any, batch["target_expression"]).unsqueeze(0).float()
            valid = cast(Any, batch["valid"]).unsqueeze(0).bool()
            emotion = cast(Any, batch["emotion_index"]).reshape(1).long()
            intensity = cast(Any, batch["intensity"]).reshape(1).float()
            prosody = None if batch["prosody"] is None else cast(Any, batch["prosody"]).unsqueeze(0).float()
            pred = model(mouth, emotion, intensity, prosody)
            loss = trajectory_loss(pred, _target_residual(target), valid, loss_config)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
        history.append(float(np.mean(losses)))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "config": config.__dict__, "mouth_dim": mouth0.shape[-1], "output_dim": target0.shape[-1], "num_emotions": len(dataset.label_to_index), "history": history}, output_path)
    write_json(output_path.with_suffix(".json"), {"history": history, "records": len(dataset), "split_path": str(split_path)})
    return output_path


def evaluate(fits_dir: Path, checkpoint_path: Path, report_path: Path, *, split: str = "test") -> Path:
    torch = require_torch()
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    model = build_model(checkpoint["config"]["model"], mouth_dim=checkpoint["mouth_dim"], output_dim=checkpoint["output_dim"], hidden_dim=checkpoint["config"].get("hidden_dim", 128), num_emotions=checkpoint.get("num_emotions", 1))
    model.load_state_dict(checkpoint["state_dict"])
    dataset = GnmTrajectoryDataset(discover_fits(fits_dir), split=split, split_path=checkpoint_path.with_suffix(".splits.json"))
    losses = []
    with torch.no_grad():
        for item in dataset:
            mouth = cast(Any, item["mouth"]).unsqueeze(0).float()
            target = cast(Any, item["target_expression"]).unsqueeze(0).float()
            valid = cast(Any, item["valid"]).unsqueeze(0).bool()
            emotion = cast(Any, item["emotion_index"]).reshape(1).long()
            intensity = cast(Any, item["intensity"]).reshape(1).float()
            losses.append(float(trajectory_loss(model(mouth, emotion, intensity), _target_residual(target), valid).cpu()))
    write_json(report_path, {"split": split, "records": len(dataset), "mean_loss": float(np.mean(losses)) if losses else None})
    return report_path
