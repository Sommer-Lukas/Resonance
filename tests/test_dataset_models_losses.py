# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
import json

import numpy as np
import pytest

from voice_face.dataset import FitRecord, GnmTrajectoryDataset, actor_split, assert_actor_independent, discover_fits, write_actor_splits
from voice_face.mouth import MouthTrajectory
from voice_face.types import GNMSequence, SampleMetadata, TrackingSequence


def _write_fit(path, emotion, *, actor=None, intensity=0.7):
    path.parent.mkdir(parents=True, exist_ok=True)
    blendshapes = np.zeros((3, 52), dtype=np.float32)
    blendshapes[:, 25] = [0.0, 0.5, 1.0]
    blendshapes[:, 44] = 0.2
    blendshapes[:, 45] = 0.4
    np.savez_compressed(
        path,
        expression=np.ones((3, 2), dtype=np.float32),
        rotations=np.zeros((3, 1, 3), dtype=np.float32),
        translation=np.zeros((3, 3), dtype=np.float32),
        valid=np.array([True, False, True]),
        landmark_rmse=np.zeros(3, dtype=np.float32),
        timestamps_ms=np.array([0, 40, 80]),
        blendshapes=blendshapes,
        identity=np.zeros(1, dtype=np.float32),
        metadata=json.dumps({"emotion": emotion, "actor": actor or "video_0", "intensity": intensity}),
    )


def test_required_dataclasses_exist():
    sample = SampleMetadata("s", "a", "happy", 0.5)
    tracking = TrackingSequence(np.zeros((1, 1, 3)), np.zeros((1, 0)), np.array([True]), np.array([0]), sample)
    gnm = GNMSequence(np.zeros(1), np.zeros((1, 2)), np.zeros((1, 1, 3)), np.zeros((1, 3)), np.array([True]), np.array([0]), sample)
    mouth = MouthTrajectory(np.zeros((1, 3), dtype=np.float32), np.array([True]), 25.0)
    assert tracking.metadata.actor == "a"
    assert gnm.expression.shape == (1, 2)
    assert mouth.feature_names == ("jaw_open", "lip_close", "mouth_smile")


def test_actor_split_is_persisted_and_actor_independent(tmp_path):
    assert actor_split("video_0") == actor_split("video_0")
    _write_fit(tmp_path / "video_0__front__happy__level_1__001.npz", "happy")
    _write_fit(tmp_path / "video_1__front__angry__level_2__001.npz", "angry")
    records = discover_fits(tmp_path)
    assert records[0] == FitRecord(tmp_path / "video_0__front__happy__level_1__001.npz", "video_0", "happy", 0.7)
    split_path = tmp_path / "splits.json"
    splits = write_actor_splits(records, split_path)
    payload = json.loads(split_path.read_text())
    assert splits == payload["by_actor"]
    assert set(payload) == {"by_actor", "train_actors", "validation_actors", "test_actors"}
    assert_actor_independent(splits)


def test_dataset_example_contains_required_fields(tmp_path):
    torch = pytest.importorskip("torch")
    _write_fit(tmp_path / "video_0__front__happy__level_1__001.npz", "happy")
    records = discover_fits(tmp_path)
    split_path = tmp_path / "splits.json"
    splits = write_actor_splits(records, split_path)
    dataset = GnmTrajectoryDataset(records, split=splits["video_0"], split_path=split_path)
    item = dataset[0]
    assert set(["mouth", "emotion_label", "emotion_index", "intensity", "prosody", "target_expression", "valid"]).issubset(item)
    assert item["mouth"].shape == (3, 3)
    assert torch.equal(item["target_expression"], torch.ones(3, 2))
    assert item["emotion_label"] == "happy"
    assert item["prosody"] is None


def test_models_have_required_baseline_semantics():
    torch = pytest.importorskip("torch")
    from voice_face.models import build_model

    mouth = torch.randn(2, 4, 3)
    emotion = torch.tensor([0, 1])
    intensity = torch.tensor([0.2, 0.8])
    b0 = build_model("b0", mouth_dim=3, output_dim=5, num_emotions=2)
    assert torch.equal(b0(mouth, emotion, intensity), torch.zeros(2, 4, 5))
    b1 = build_model("b1", mouth_dim=3, output_dim=5, num_emotions=2, hidden_dim=6)
    y1 = b1(mouth, emotion, intensity)
    assert y1.shape == (2, 4, 5)
    assert torch.allclose(y1[:, 0], y1[:, -1])
    b2 = build_model("b2", mouth_dim=3, output_dim=5, num_emotions=2, hidden_dim=6, prosody_dim=2)
    assert b2(mouth, emotion, intensity, torch.zeros(2, 4, 2)).shape == (2, 4, 5)


def test_loss_config_geometry_regions_and_regularization():
    torch = pytest.importorskip("torch")
    from voice_face.losses import LossConfig, trajectory_loss

    pred = torch.ones(1, 3, 2)
    target = torch.zeros(1, 3, 2)
    valid = torch.tensor([[True, True, False]])
    pred_vertices = torch.ones(1, 3, 4, 3)
    target_vertices = torch.zeros(1, 3, 4, 3)
    loss = trajectory_loss(
        pred,
        target,
        valid,
        LossConfig(geometry=1.0, mouth_region_geometry=1.0, upper_face_geometry=1.0, velocity=1.0, acceleration=1.0, residual_regularization=0.1),
        pred_vertices=pred_vertices,
        target_vertices=target_vertices,
        mouth_region_indices=torch.tensor([0, 1]),
        upper_face_region_indices=torch.tensor([2, 3]),
    )
    assert torch.isfinite(loss)
    assert loss > 0
