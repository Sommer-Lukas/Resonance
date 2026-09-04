"""Adapters from mouth-driver features to GNM-compatible expression states."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class MouthExpressionAdapter:
    expression_dim: int
    jaw_index: int = 0
    lip_close_index: int = 1
    smile_index: int = 2
    gain: float = 1.0

    def transform(self, mouth_features: np.ndarray) -> np.ndarray:
        features = np.asarray(mouth_features, dtype=np.float32)
        out = np.zeros((features.shape[0], int(self.expression_dim)), dtype=np.float32)
        if self.expression_dim > self.jaw_index and features.shape[1] > 0:
            out[:, self.jaw_index] = features[:, 0] * self.gain
        if self.expression_dim > self.lip_close_index and features.shape[1] > 1:
            out[:, self.lip_close_index] = features[:, 1] * self.gain
        if self.expression_dim > self.smile_index and features.shape[1] > 2:
            out[:, self.smile_index] = features[:, 2] * self.gain
        return out
