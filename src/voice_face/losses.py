# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Configurable residual, coefficient-proxy and geometry losses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LossConfig:
    geometry: float = 1.0
    mouth_region_geometry: float = 0.0
    upper_face_geometry: float = 0.0
    velocity: float = 0.1
    acceleration: float = 0.01
    residual_regularization: float = 0.001


def _masked_mse(value, target, valid):
    mask = valid.to(dtype=value.dtype).reshape(*valid.shape, *([1] * (value.ndim - valid.ndim)))
    return (((value - target) ** 2) * mask).sum() / mask.sum().clamp_min(1.0)


def loss_components(pred_expression, target_expression, pred_residual, valid, config: LossConfig = LossConfig(), *, pred_vertices=None, target_vertices=None, mouth_region_indices=None, upper_face_region_indices=None):
    import torch

    zero = pred_expression.sum() * 0.0
    components = {"geometry": zero, "mouth": zero, "emotion_region": zero, "velocity": zero, "acceleration": zero, "residual": zero}
    if pred_vertices is not None and target_vertices is not None:
        if config.geometry:
            components["geometry"] = _masked_mse(pred_vertices, target_vertices, valid)
        if config.mouth_region_geometry and mouth_region_indices is not None:
            components["mouth"] = _masked_mse(pred_vertices[:, :, mouth_region_indices], target_vertices[:, :, mouth_region_indices], valid)
        if config.upper_face_geometry and upper_face_region_indices is not None:
            components["emotion_region"] = _masked_mse(pred_vertices[:, :, upper_face_region_indices], target_vertices[:, :, upper_face_region_indices], valid)
    else:
        components["geometry"] = _masked_mse(pred_expression, target_expression, valid)
        split = max(1, pred_expression.shape[-1] // 5)
        components["mouth"] = _masked_mse(pred_expression[..., :split], target_expression[..., :split], valid)
        components["emotion_region"] = _masked_mse(pred_expression[..., split:], target_expression[..., split:], valid) if pred_expression.shape[-1] > split else zero
    if pred_expression.shape[1] > 1:
        vmask = valid[:, 1:] & valid[:, :-1]
        components["velocity"] = _masked_mse(pred_expression[:, 1:] - pred_expression[:, :-1], target_expression[:, 1:] - target_expression[:, :-1], vmask)
    if pred_expression.shape[1] > 2:
        amask = valid[:, 2:] & valid[:, 1:-1] & valid[:, :-2]
        pred_acc = pred_expression[:, 2:] - 2 * pred_expression[:, 1:-1] + pred_expression[:, :-2]
        target_acc = target_expression[:, 2:] - 2 * target_expression[:, 1:-1] + target_expression[:, :-2]
        components["acceleration"] = _masked_mse(pred_acc, target_acc, amask)
    components["residual"] = torch.mean(pred_residual ** 2)
    return components


def combine_losses(components: dict[str, Any], config: LossConfig):
    return config.geometry * components["geometry"] + config.mouth_region_geometry * components["mouth"] + config.upper_face_geometry * components["emotion_region"] + config.velocity * components["velocity"] + config.acceleration * components["acceleration"] + config.residual_regularization * components["residual"]


def trajectory_loss(pred_residual, target_residual, valid, config: LossConfig = LossConfig(), *, pred_vertices=None, target_vertices=None, mouth_region_indices=None, upper_face_region_indices=None):
    components = loss_components(pred_residual, target_residual, pred_residual, valid, config, pred_vertices=pred_vertices, target_vertices=target_vertices, mouth_region_indices=mouth_region_indices, upper_face_region_indices=upper_face_region_indices)
    return combine_losses(components, config)
