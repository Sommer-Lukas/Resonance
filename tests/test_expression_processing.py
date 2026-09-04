# pyright: reportMissingImports=false
from __future__ import annotations

import numpy as np

from voice_face.fitting.expression_processing import ExpressionProcessingConfig, neutral_frame_indices, process_expression


def test_neutral_frame_indices_prefer_low_motion_low_mouth_frames():
    class Data:
        files = ("expression", "blendshapes", "valid")

        def __getitem__(self, key: str):
            return {"expression": expression, "blendshapes": blendshapes, "valid": np.ones(4, dtype=bool)}[key]

    expression = np.array([[0.0, 0.0], [0.01, 0.0], [5.0, 0.0], [5.5, 0.0]], dtype=np.float32)
    blendshapes = np.zeros((4, 52), dtype=np.float32)
    blendshapes[:, 25] = [0.0, 0.02, 0.8, 0.9]

    selected = neutral_frame_indices(Data(), ExpressionProcessingConfig(neutral_score_percentile=50.0))

    assert set(selected.tolist()) <= {0, 1}


def test_process_expression_subtracts_neutral_and_only_filters_lower_face():
    expression = np.array([[10.0, 2.0, 5.0], [12.0, 4.0, 7.0]], dtype=np.float32)
    neutral = np.array([10.0, 1.0, 5.0], dtype=np.float32)
    valid = np.array([True, True])

    raw_delta, processed = process_expression(expression, valid, neutral, np.array([1]), ExpressionProcessingConfig(lower_soft_bound=5.0, lower_motion_threshold=99.0))

    assert np.allclose(raw_delta, [[0.0, 1.0, 0.0], [2.0, 3.0, 2.0]])
    assert np.allclose(processed[:, [0, 2]], raw_delta[:, [0, 2]])
    assert processed[1, 1] < raw_delta[1, 1]
