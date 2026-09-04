#!/usr/bin/env python3
"""Tiny dependency-light smoke test for the face pipeline wiring."""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np

from voice_face.data.mead import MeadIndexConfig, index_mead, read_index, write_index
from voice_face.dataset import FitRecord, assert_actor_independent, write_actor_splits
from voice_face.fitting.smoothing import exponential_smooth, trajectory_stats
from voice_face.mouth import ConstantMouthDriver, MouthFrame
from voice_face.visualization.diagnostics import write_fit_report


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        video = root / "mead" / "actor_0" / "front" / "happy" / "level_2" / "001.mp4"
        video.parent.mkdir(parents=True)
        video.write_bytes(b"not a real video")
        manifest = root / "manifest.csv"
        samples = index_mead(root / "mead", MeadIndexConfig(frontal_only=True, max_clips=1))
        assert len(samples) == 1 and samples[0].actor_id == "actor_0"
        write_index(samples, manifest)
        assert read_index(manifest)[0].sample_id == samples[0].sample_id

        values = np.array([[0.0], [1.0], [3.0]], dtype=np.float32)
        valid = np.array([True, False, True])
        assert exponential_smooth(values, valid, 0.5).shape == values.shape
        assert trajectory_stats(values, valid).valid_frames == 2

        mouth = ConstantMouthDriver(MouthFrame(0.1, 0.0, 0.2)).predict(Path("dummy.wav"), np.asarray([0.0, 0.1], dtype=np.float32))
        assert mouth.features.shape == (2, 3)

        fit = root / "fits" / "actor_0__front__happy__2__001.npz"
        fit.parent.mkdir(parents=True)
        np.savez_compressed(
            fit,
            identity=np.zeros(2, dtype=np.float32),
            expression_raw=np.zeros((3, 2), dtype=np.float32),
            expression_smoothed=np.ones((3, 2), dtype=np.float32),
            expression=np.ones((3, 2), dtype=np.float32),
            rotation=np.zeros((3, 1, 3), dtype=np.float32),
            rotations=np.zeros((3, 1, 3), dtype=np.float32),
            translation=np.zeros((3, 3), dtype=np.float32),
            fit_error=np.array([0.1, np.nan, 0.3], dtype=np.float32),
            landmark_rmse=np.array([0.1, np.nan, 0.3], dtype=np.float32),
            valid=np.array([True, False, True]),
            timestamps=np.array([0.0, 0.04, 0.08], dtype=np.float32),
            timestamps_ms=np.array([0, 40, 80]),
            blendshapes=np.zeros((3, 52), dtype=np.float32),
            metadata='{"source_video":"dummy.mp4","fps":25}',
        )
        write_fit_report(fit, root / "report.json")
        splits = write_actor_splits([FitRecord(fit, "actor_0", "happy", 2)], root / "splits.json")
        assert_actor_independent(splits)
    print("smoke pipeline ok")


if __name__ == "__main__":
    main()
