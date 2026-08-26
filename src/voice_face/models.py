# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""B0/B1/B2 residual baselines for emotion-conditioned face motion."""

from __future__ import annotations


def require_torch():
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("PyTorch is required for models") from exc
    return torch


def build_model(name: str, *, mouth_dim: int | None = None, output_dim: int, hidden_dim: int = 128, num_emotions: int = 1, prosody_dim: int = 0, input_dim: int | None = None):
    torch = require_torch()
    nn = torch.nn
    mouth_dim = mouth_dim if mouth_dim is not None else (input_dim or 3)

    class B0(nn.Module):
        def forward(self, mouth, emotion_index=None, intensity=None, prosody=None):
            return torch.zeros((*mouth.shape[:-1], output_dim), dtype=mouth.dtype, device=mouth.device)

    class B1(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(max(1, num_emotions), hidden_dim)
            self.out = nn.Linear(hidden_dim + 1, output_dim)
        def forward(self, mouth, emotion_index, intensity, prosody=None):
            if intensity.ndim == 0:
                intensity_local = intensity.expand(mouth.shape[0])
            else:
                intensity_local = intensity.reshape(-1)
            correction = self.out(torch.cat([self.embedding(emotion_index.reshape(-1)), intensity_local[:, None].to(mouth.dtype)], dim=-1))
            return correction[:, None, :].expand(mouth.shape[0], mouth.shape[1], output_dim)

    class B2(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(max(1, num_emotions), hidden_dim)
            self.rnn = nn.GRU(mouth_dim + hidden_dim + 1 + prosody_dim, hidden_dim, num_layers=2, batch_first=True)
            self.out = nn.Linear(hidden_dim, output_dim)
        def forward(self, mouth, emotion_index, intensity, prosody=None):
            batch, frames, _ = mouth.shape
            emb = self.embedding(emotion_index.reshape(-1))[:, None, :].expand(batch, frames, hidden_dim)
            inten = intensity.reshape(-1, 1, 1).to(mouth.dtype).expand(batch, frames, 1)
            parts = [mouth, emb.to(mouth.dtype), inten]
            if prosody_dim:
                if prosody is None:
                    prosody_local = torch.zeros((batch, frames, prosody_dim), dtype=mouth.dtype, device=mouth.device)
                else:
                    prosody_local = prosody.to(mouth.dtype)
                parts.append(prosody_local)
            y, _ = self.rnn(torch.cat(parts, dim=-1))
            return self.out(y)

    models = {"b0": B0, "b1": B1, "b2": B2}
    key = name.lower()
    if key not in models:
        raise ValueError(f"Unknown model {name!r}; expected one of {sorted(models)}")
    return models[key]()
