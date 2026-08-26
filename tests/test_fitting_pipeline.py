# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
import json
from types import SimpleNamespace

import numpy as np

from voice_face.fitting.pipeline import FitConfig, cache_actor_identity, fit_sample


class FakeParams:
    def __init__(self, identity, expression, rotations):
        self.identity = identity
        self.expression = expression
        self.rotations = rotations
        self.translation = np.zeros(3, dtype=np.float32)
        self.landmark_rmse = 0.25


class FakeSolver:
    def __init__(self):
        self._identity = None
    def solve_identity(self, landmarks, width, height):
        self._identity = np.array([width, height], dtype=np.float32)
        return self._identity
    def solve(self, landmarks, width, height):
        return FakeParams(self._identity, np.array([landmarks[0, 0], 2.0], dtype=np.float32), np.ones((1, 3), dtype=np.float32))


def _tracking(path):
    np.savez_compressed(
        path,
        landmarks=np.array([[[1.0, 0.0, 0.0]], [[np.nan, np.nan, np.nan]], [[3.0, 0.0, 0.0]]], dtype=np.float32),
        blendshapes=np.zeros((3, 0), dtype=np.float32),
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
