# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Residual models for emotion-conditioned GNM expression prediction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def require_torch():
    try:
        import torch
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyTorch is required for models") from exc
    return torch


class StaticEmotionTable:
    def __init__(self, table: dict[tuple[int, int], np.ndarray], fallback: np.ndarray):
        self.table = table
        self.fallback = fallback.astype(np.float32)

    def predict_numpy(self, mouth_expression: np.ndarray, emotion_index: int, intensity: float) -> np.ndarray:
        level = int(round(float(intensity) * 3.0 if intensity <= 1.0 else float(intensity)))
        keys = [(emotion_index, level)]
        if not keys[0] in self.table:
            levels = sorted(k[1] for k in self.table if k[0] == emotion_index)
            if levels:
                low = max([v for v in levels if v <= level] or [levels[0]])
                high = min([v for v in levels if v >= level] or [levels[-1]])
                if low != high:
                    a = (level - low) / float(high - low)
                    residual = (1.0 - a) * self.table[(emotion_index, low)] + a * self.table[(emotion_index, high)]
                    return np.repeat(residual[None, :], len(mouth_expression), axis=0)
                keys = [(emotion_index, low)]
        residual = self.table.get(keys[0], self.fallback)
        return np.repeat(residual[None, :], len(mouth_expression), axis=0)

    def save(self, path: Path, label_to_index: dict[str, int]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, fallback=self.fallback, keys=json.dumps([[e, i] for e, i in self.table], sort_keys=True), values=np.stack(list(self.table.values())) if self.table else np.zeros((0, len(self.fallback)), dtype=np.float32), label_to_index=json.dumps(label_to_index, sort_keys=True))
        return path

    @classmethod
    def load(cls, path: Path) -> tuple["StaticEmotionTable", dict[str, int]]:
        data = np.load(path, allow_pickle=False)
        keys = json.loads(str(data["keys"]))
        values = data["values"].astype(np.float32)
        table = {(int(k[0]), int(k[1])): values[i] for i, k in enumerate(keys)}
        return cls(table, data["fallback"].astype(np.float32)), json.loads(str(data["label_to_index"]))


def build_static_table(records: list[Any], label_to_index: dict[str, int]) -> StaticEmotionTable:
    sums: dict[tuple[int, int], list[np.ndarray]] = {}
    all_residuals: list[np.ndarray] = []
    from voice_face.training_records import load_training_sequence

    for record in records:
        seq = load_training_sequence(record.path)
        residual = seq.beta_target - seq.mouth_expression
        valid = seq.valid
        if valid.any():
            mean = residual[valid].mean(axis=0).astype(np.float32)
            key = (label_to_index[seq.emotion], int(seq.intensity))
            sums.setdefault(key, []).append(mean)
            all_residuals.append(mean)
    fallback = np.mean(np.stack(all_residuals), axis=0).astype(np.float32) if all_residuals else np.zeros(1, dtype=np.float32)
    return StaticEmotionTable({k: np.mean(np.stack(v), axis=0).astype(np.float32) for k, v in sums.items()}, fallback)


def build_model(name: str, *, mouth_dim: int | None = None, output_dim: int, hidden_dim: int = 256, num_emotions: int = 1, prosody_dim: int = 3, emotion_dim: int = 16, layers: int = 2, dropout: float = 0.1, causal: bool = True, input_dim: int | None = None):
    torch = require_torch()
    nn = torch.nn
    mouth_dim = mouth_dim if mouth_dim is not None else (input_dim or output_dim)
    key = name.lower()

    class B0(nn.Module):
        def forward(self, mouth_expression, emotion_index=None, intensity=None, prosody=None):
            return torch.zeros((*mouth_expression.shape[:-1], output_dim), dtype=mouth_expression.dtype, device=mouth_expression.device)

    class B1(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(max(1, num_emotions), hidden_dim)
            self.out = nn.Linear(hidden_dim + 1, output_dim)
        def forward(self, mouth_expression, emotion_index=None, intensity=None, prosody=None):
            batch, frames, _ = mouth_expression.shape
            emotion_index = torch.zeros(batch, dtype=torch.long, device=mouth_expression.device) if emotion_index is None else emotion_index.reshape(-1).long()
            intensity = torch.ones(batch, dtype=mouth_expression.dtype, device=mouth_expression.device) if intensity is None else intensity.reshape(-1).to(mouth_expression.dtype)
            residual = self.out(torch.cat([self.embedding(emotion_index).to(mouth_expression.dtype), intensity[:, None]], dim=-1))
            return residual[:, None, :].expand(batch, frames, output_dim)

    class ResidualGRU(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(max(1, num_emotions), emotion_dim)
            self.proj = nn.Linear(mouth_dim + prosody_dim + emotion_dim + 1, hidden_dim)
            self.rnn = nn.GRU(hidden_dim, hidden_dim, num_layers=layers, batch_first=True, dropout=dropout if layers > 1 else 0.0, bidirectional=not causal)
            self.out = nn.Linear(hidden_dim * (1 if causal else 2), output_dim)
        def forward(self, mouth_expression, emotion_index=None, intensity=None, prosody=None):
            batch, frames, _ = mouth_expression.shape
            if prosody is None:
                prosody = torch.zeros((batch, frames, prosody_dim), dtype=mouth_expression.dtype, device=mouth_expression.device)
            emotion_index = torch.zeros(batch, dtype=torch.long, device=mouth_expression.device) if emotion_index is None else emotion_index.reshape(-1).long()
            intensity = torch.ones(batch, dtype=mouth_expression.dtype, device=mouth_expression.device) if intensity is None else intensity.reshape(-1).to(mouth_expression.dtype)
            emb = self.embedding(emotion_index)[:, None, :].expand(batch, frames, emotion_dim).to(mouth_expression.dtype)
            inten = intensity[:, None, None].expand(batch, frames, 1)
            x = torch.cat([mouth_expression, prosody.to(mouth_expression.dtype), emb, inten], dim=-1)
            y, _ = self.rnn(torch.relu(self.proj(x)))
            return self.out(y)

    class TcnBlock(nn.Module):
        def __init__(self, dilation: int):
            super().__init__()
            pad = dilation
            self.net = nn.Sequential(nn.Conv1d(hidden_dim, hidden_dim, 3, padding=pad, dilation=dilation), nn.GroupNorm(8 if hidden_dim % 8 == 0 else 1, hidden_dim), nn.ReLU(), nn.Dropout(dropout), nn.Conv1d(hidden_dim, hidden_dim, 1))
        def forward(self, x):
            y = self.net(x)
            if y.shape[-1] != x.shape[-1]:
                y = y[..., : x.shape[-1]]
            return torch.relu(x + y)

    class ResidualTCN(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(max(1, num_emotions), emotion_dim)
            self.inp = nn.Conv1d(mouth_dim + prosody_dim + emotion_dim + 1, hidden_dim, 1)
            self.blocks = nn.Sequential(*[TcnBlock(2 ** i) for i in range(max(1, layers))])
            self.out = nn.Conv1d(hidden_dim, output_dim, 1)
        def forward(self, mouth_expression, emotion_index=None, intensity=None, prosody=None):
            batch, frames, _ = mouth_expression.shape
            if prosody is None:
                prosody = torch.zeros((batch, frames, prosody_dim), dtype=mouth_expression.dtype, device=mouth_expression.device)
            emotion_index = torch.zeros(batch, dtype=torch.long, device=mouth_expression.device) if emotion_index is None else emotion_index.reshape(-1).long()
            intensity = torch.ones(batch, dtype=mouth_expression.dtype, device=mouth_expression.device) if intensity is None else intensity.reshape(-1).to(mouth_expression.dtype)
            emb = self.embedding(emotion_index)[:, None, :].expand(batch, frames, emotion_dim).to(mouth_expression.dtype)
            x = torch.cat([mouth_expression, prosody.to(mouth_expression.dtype), emb, intensity[:, None, None].expand(batch, frames, 1)], dim=-1).transpose(1, 2)
            return self.out(self.blocks(torch.relu(self.inp(x)))).transpose(1, 2)

    models = {"b0": B0, "b1": B1, "gru": ResidualGRU, "m1": ResidualGRU, "tcn": ResidualTCN, "m2": ResidualTCN, "b2": ResidualGRU}
    if key not in models:
        raise ValueError(f"Unknown model {name!r}; expected one of {sorted(models)}")
    return models[key]()
