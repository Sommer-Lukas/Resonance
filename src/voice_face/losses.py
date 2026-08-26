# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Configurable residual and geometry losses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LossConfig:
    geometry: float = 0.0
    mouth_region_geometry: float = 0.0
    upper_face_geometry: float = 0.0
    velocity: float = 0.0
    acceleration: float = 0.0
    residual_regularization: float = 0.0


def _masked_mse(value, target, valid):
    mask = valid.to(dtype=value.dtype).reshape(*valid.shape, *([1] * (value.ndim - valid.ndim)))
    return (((value - target) ** 2) * mask).sum() / mask.sum().clamp_min(1.0)


def trajectory_loss(pred_residual, target_residual, valid, config: LossConfig = LossConfig(), *, pred_vertices=None, target_vertices=None, mouth_region_indices=None, upper_face_region_indices=None):
    loss = _masked_mse(pred_residual, target_residual, valid)
    if config.velocity and pred_residual.shape[1] > 1:
        vmask = valid[:, 1:] & valid[:, :-1]
        loss = loss + config.velocity * _masked_mse(pred_residual[:, 1:] - pred_residual[:, :-1], target_residual[:, 1:] - target_residual[:, :-1], vmask)
    if config.acceleration and pred_residual.shape[1] > 2:
        amask = valid[:, 2:] & valid[:, 1:-1] & valid[:, :-2]
        pred_accel = pred_residual[:, 2:] - 2 * pred_residual[:, 1:-1] + pred_residual[:, :-2]
        target_accel = target_residual[:, 2:] - 2 * target_residual[:, 1:-1] + target_residual[:, :-2]
        loss = loss + config.acceleration * _masked_mse(pred_accel, target_accel, amask)
    if config.residual_regularization:
        loss = loss + config.residual_regularization * _masked_mse(pred_residual, pred_residual.detach() * 0.0, valid)
    if pred_vertices is not None and target_vertices is not None:
        if config.geometry:
            loss = loss + config.geometry * _masked_mse(pred_vertices, target_vertices, valid)
        if config.mouth_region_geometry and mouth_region_indices is not None:
            loss = loss + config.mouth_region_geometry * _masked_mse(pred_vertices[:, :, mouth_region_indices], target_vertices[:, :, mouth_region_indices], valid)
        if config.upper_face_geometry and upper_face_region_indices is not None:
            loss = loss + config.upper_face_geometry * _masked_mse(pred_vertices[:, :, upper_face_region_indices], target_vertices[:, :, upper_face_region_indices], valid)
    return loss
