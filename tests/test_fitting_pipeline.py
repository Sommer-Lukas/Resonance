# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
import json
from types import SimpleNamespace

import numpy as np

from voice_face.fitting.pipeline import FitConfig, cache_actor_identity, fit_sample
from voice_face.tracking.mediapipe import load_tracking


class FakeParams:
    def __init__(self, identity, expression, rotations, translation):
        self.identity = identity
        self.expression = expression
        self.rotations = rotations
        self.translation = translation
        self.landmark_rmse = 0.25


class FakeSolver:
    def __init__(self):
        self._identity = None
    def solve_identity(self, landmarks, width, height):
        self._identity = np.array([width, height], dtype=np.float32)
        return self._identity
    def solve(self, landmarks, width, height):
        value = float(landmarks[0, 0])
        return FakeParams(self._identity, np.array([value, value * 10.0], dtype=np.float32), np.full((1, 3), value, dtype=np.float32), np.array([value, value + 1.0, value + 2.0], dtype=np.float32))


def _tracking(path):
    np.savez_compressed(
        path,
        landmarks=np.array([[[1.0, 0.0, 0.0]], [[np.nan, np.nan, np.nan]], [[3.0, 0.0, 0.0]]], dtype=np.float32),
        blendshapes=np.array([[0.0], [0.0], [1.0]], dtype=np.float32),
        valid=np.array([True, False, True]),
        timestamps_ms=np.array([0, 40, 80]),
        metadata=json.dumps({"width": 640, "height": 480, "fps": 25.0, "source_video": "synthetic.mp4"}),
    )


def test_identity_cache_reused_for_fit(monkeypatch, tmp_path):
    monkeypatch.setattr("voice_face.fitting.pipeline._solver", lambda gnm, correspondence, config: FakeSolver())
    tracking = tmp_path / "track.npz"
    identity = tmp_path / "video_0.npz"
    fit = tmp_path / "fit.npz"
    _tracking(tracking)
    gnm = SimpleNamespace(expression_dim=2, num_joints=1)

    cache_actor_identity("video_0", [tracking], identity, gnm, object(), config=FitConfig())
    fit_sample(tracking, identity, fit, gnm, object(), config=FitConfig())

    identity_data = np.load(identity)
    fit_data = np.load(fit)
    assert identity_data["source_frame"] == 0
    assert np.allclose(fit_data["identity"], [640, 480])
    assert fit_data["valid"].tolist() == [True, False, True]
    assert np.isnan(fit_data["expression"][1]).all()


def test_regional_mode_smooths_expressions_only_and_preserves_blinks(monkeypatch, tmp_path):
    monkeypatch.setattr("voice_face.fitting.pipeline._solver", lambda gnm, correspondence, config: FakeSolver())
    tracking = tmp_path / "track.npz"
    identity = tmp_path / "video_0.npz"
    fit = tmp_path / "fit.npz"
    _tracking(tracking)
    gnm = SimpleNamespace(expression_dim=2, num_joints=1)

    cache_actor_identity("video_0", [tracking], identity, gnm, object(), config=FitConfig())
    fit_sample(tracking, identity, fit, gnm, object(), config=FitConfig(0.5, 1.0, "regional", (0.5, 0.0), (0,), (0,), 1.0))

    data = np.load(fit)
    metadata = json.loads(str(data["metadata"]))
    assert np.allclose(data["expression_raw"][[0, 2]], [[1.0, 10.0], [3.0, 30.0]])
    assert np.allclose(data["expression_smoothed"][0], [1.0, 10.0])
    assert np.isnan(data["expression_smoothed"][1]).all()
    assert np.allclose(data["expression_smoothed"][2], [3.0, 30.0])
    assert np.allclose(data["rotation"][[0, 2], 0, 0], [1.0, 3.0])
    assert np.allclose(data["translation"][[0, 2]], [[1.0, 2.0, 3.0], [3.0, 4.0, 5.0]])
    assert metadata["processing_mode"] == "regional"
    assert metadata["regional_processing"]["blink"]["frames"] == 1


def test_regional_mode_tolerates_missing_blendshapes(tmp_path, monkeypatch):
    monkeypatch.setattr("voice_face.fitting.pipeline._solver", lambda gnm, correspondence, config: FakeSolver())
    tracking = tmp_path / "track.npz"
    identity = tmp_path / "video_0.npz"
    fit = tmp_path / "fit.npz"
    np.savez_compressed(
        tracking,
        landmarks=np.array([[[1.0, 0.0, 0.0]], [[np.nan, np.nan, np.nan]], [[3.0, 0.0, 0.0]]], dtype=np.float32),
        valid=np.array([True, False, True]),
        timestamps_ms=np.array([0, 40, 80]),
        metadata=json.dumps({"width": 640, "height": 480, "fps": 25.0, "source_video": "synthetic.mp4"}),
    )
    gnm = SimpleNamespace(expression_dim=2, num_joints=1)

    loaded = load_tracking(tracking)
    assert loaded["blendshapes"].shape == (3, 0)
    assert loaded["blendshapes"].dtype == np.float32

    cache_actor_identity("video_0", [tracking], identity, gnm, object(), config=FitConfig())
    fit_sample(tracking, identity, fit, gnm, object(), config=FitConfig(0.5, 1.0, "regional", None, (0,), (0,), 1.0))

    data = np.load(fit)
    metadata = json.loads(str(data["metadata"]))
    assert data["blendshapes"].shape == (3, 0)
    assert metadata["regional_processing"]["blink"]["frames"] == 0
    assert metadata["processing_stage"] == "post_solve_expression"
    assert np.allclose(data["rotation"][[0, 2], 0, 0], [1.0, 3.0])
    assert np.allclose(data["translation"][[0, 2]], [[1.0, 2.0, 3.0], [3.0, 4.0, 5.0]])


def test_fit_config_rejects_unknown_processing_mode():
    try:
        FitConfig(processing_mode="other")
    except ValueError as exc:
        assert "processing_mode" in str(exc)
    else:
        raise AssertionError("expected invalid processing mode to fail")
