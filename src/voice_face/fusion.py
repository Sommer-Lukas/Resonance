"""Fusion from speech-only GNM expression state plus emotional residual."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class FusionConfig:
    residual_scale: float = 1.0
    preserve_mouth: float = 0.0
    clamp: float = 6.0
    mask: tuple[float, ...] = ()


def _mask(dim: int, config: FusionConfig) -> np.ndarray:
    if config.mask:
        values = np.asarray(config.mask, dtype=np.float32)
        if len(values) != dim:
            raise ValueError(f"fusion mask length {len(values)} != expression dim {dim}")
        return values
    values = np.ones(dim, dtype=np.float32)
    if dim:
        values[: min(3, dim)] *= 1.0 - float(config.preserve_mouth)
    return values


def fuse_numpy(mouth_expression: np.ndarray, residual: np.ndarray, config: FusionConfig = FusionConfig()) -> np.ndarray:
    mask = _mask(mouth_expression.shape[-1], config)
    out = mouth_expression + residual * mask * float(config.residual_scale)
    return np.clip(out, -float(config.clamp), float(config.clamp)).astype(np.float32)


def fuse_torch(mouth_expression, residual, config: FusionConfig = FusionConfig()):
    import torch

    values = torch.as_tensor(_mask(mouth_expression.shape[-1], config), dtype=mouth_expression.dtype, device=mouth_expression.device)
    out = mouth_expression + residual * values * float(config.residual_scale)
    return torch.clamp(out, -float(config.clamp), float(config.clamp))
