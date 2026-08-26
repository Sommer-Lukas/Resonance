# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
import json

import numpy as np

from voice_face.fitting.smoothing import exponential_smooth, trajectory_stats
from voice_face.visualization.diagnostics import write_fit_report, write_frame_stats


def test_smoothing_preserves_invalid_frames():
    values = np.array([[0.0], [10.0], [20.0], [40.0]], dtype=np.float32)
    valid = np.array([True, False, True, True])

    out = exponential_smooth(values, valid, 0.5)

    assert out[1, 0] == 10.0
    assert out[2, 0] == 10.0
    assert out[3, 0] == 25.0
    stats = trajectory_stats(out, valid)
    assert stats.valid_frames == 3
    assert stats.invalid_frames == 1


def test_fit_report_and_frame_csv_keep_invalid_mask(tmp_path):
    fit = tmp_path / "fit.npz"
    np.savez_compressed(
        fit,
        identity=np.zeros(2, dtype=np.float32),
        expression=np.zeros((2, 3), dtype=np.float32),
        rotations=np.zeros((2, 1, 3), dtype=np.float32),
        translation=np.zeros((2, 3), dtype=np.float32),
        landmark_rmse=np.array([0.1, np.nan], dtype=np.float32),
        valid=np.array([True, False]),
        timestamps_ms=np.array([0, 40]),
        blendshapes=np.zeros((2, 0), dtype=np.float32),
        metadata=json.dumps({"fps": 25.0}),
    )

    report = write_fit_report(fit, tmp_path / "report.json")
    csv_path = write_frame_stats(fit, tmp_path / "frames.csv")

    payload = json.loads(report.read_text())
    assert payload["valid_frames"] == 1
    assert payload["invalid_frames"] == 1
    assert "False" in csv_path.read_text()
