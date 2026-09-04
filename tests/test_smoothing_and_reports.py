# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
import json

import numpy as np

from voice_face.fitting.smoothing import channel_exponential_smooth, exponential_smooth, trajectory_stats
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


def test_channel_smoothing_uses_per_channel_alpha_and_preserves_invalid_frames():
    values = np.array([[0.0, 0.0], [10.0, 10.0], [20.0, 20.0]], dtype=np.float32)
    valid = np.array([True, False, True])

    out = channel_exponential_smooth(values, valid, np.array([0.5, 0.0], dtype=np.float32))

    assert np.allclose(out[1], [10.0, 10.0])
    assert np.allclose(out[2], [10.0, 20.0])


def test_channel_smoothing_rejects_non_finite_alphas():
    values = np.array([[0.0, 0.0], [10.0, 10.0]], dtype=np.float32)
    valid = np.array([True, True])

    for alphas in (np.array([np.nan, 0.0], dtype=np.float32), np.array([0.5, np.inf], dtype=np.float32)):
        try:
            channel_exponential_smooth(values, valid, alphas)
        except ValueError as exc:
            assert "alphas" in str(exc)
        else:
            raise AssertionError("expected non-finite alphas to fail")


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
    assert payload["processing_mode"] == "legacy"
    assert "False" in csv_path.read_text()


def test_fit_report_adds_raw_vs_processed_stats_when_available(tmp_path):
    fit = tmp_path / "fit.npz"
    np.savez_compressed(
        fit,
        identity=np.zeros(2, dtype=np.float32),
        expression_raw=np.array([[0.0, 1.0], [np.nan, np.nan]], dtype=np.float32),
        expression_smoothed=np.array([[1.0, 1.0], [np.nan, np.nan]], dtype=np.float32),
        expression=np.array([[1.0, 1.0], [np.nan, np.nan]], dtype=np.float32),
        rotation=np.zeros((2, 1, 3), dtype=np.float32),
        rotations=np.zeros((2, 1, 3), dtype=np.float32),
        translation=np.zeros((2, 3), dtype=np.float32),
        fit_error=np.array([0.1, np.nan], dtype=np.float32),
        landmark_rmse=np.array([0.1, np.nan], dtype=np.float32),
        valid=np.array([True, False]),
        timestamps=np.array([0.0, 0.04], dtype=np.float32),
        timestamps_ms=np.array([0, 40]),
        blendshapes=np.zeros((2, 0), dtype=np.float32),
        metadata=json.dumps({"processing_mode": "regional"}),
    )

    report = write_fit_report(fit, tmp_path / "report.json")

    payload = json.loads(report.read_text())
    assert payload["processing_mode"] == "regional"
    assert payload["raw_vs_processed_statistics"]["mean_abs_delta"] == 0.5
