# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Datasets and actor-level splits for face trajectory training."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence, cast

import numpy as np

from voice_face.training_records import TrainingSequence, load_training_sequence


@dataclass(frozen=True, slots=True)
class FitRecord:
    path: Path
    actor: str
    emotion: str
    intensity: float = 1.0


@dataclass(frozen=True, slots=True)
class TrainingRecord:
    path: Path
    actor: str
    emotion: str
    intensity: float
    sample_id: str


def actor_split(actor: str, *, val_fraction: float = 0.15, test_fraction: float = 0.15) -> str:
    bucket = int(hashlib.sha1(actor.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    if bucket < test_fraction:
        return "test"
    if bucket < test_fraction + val_fraction:
        return "val"
    return "train"


def _balanced_actor_mapping(actors: Sequence[str]) -> dict[str, str]:
    unique = sorted(set(actors))
    if not unique:
        return {}
    if len(unique) == 1:
        return {unique[0]: "train"}
    test_count = max(1, round(len(unique) * 0.15))
    val_count = max(1, round(len(unique) * 0.15)) if len(unique) >= 3 else 0
    train_count = max(1, len(unique) - test_count - val_count)
    val_start = train_count
    test_start = min(len(unique), train_count + val_count)
    mapping = {actor: "train" for actor in unique[:train_count]}
    mapping.update({actor: "val" for actor in unique[val_start:test_start]})
    mapping.update({actor: "test" for actor in unique[test_start:]})
    return mapping


def actor_splits(actors: Sequence[str]) -> dict[str, list[str]]:
    mapping = _balanced_actor_mapping(actors)
    return {"train_actors": [a for a, split in mapping.items() if split == "train"], "validation_actors": [a for a, split in mapping.items() if split == "val"], "test_actors": [a for a, split in mapping.items() if split == "test"]}


def write_actor_splits(records: Sequence[FitRecord | TrainingRecord], path: Path) -> dict[str, str]:
    mapping = _balanced_actor_mapping([record.actor for record in records])
    grouped = actor_splits(list(mapping))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"by_actor": mapping, **grouped}, indent=2, sort_keys=True), encoding="utf-8")
    return mapping


def read_actor_splits(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "by_actor" in payload:
        return {str(k): str(v) for k, v in payload["by_actor"].items()}
    return {str(k): str(v) for k, v in payload.items()}


def assert_actor_independent(split_by_actor: dict[str, str]) -> None:
    if len(split_by_actor) != len(set(split_by_actor)):
        raise ValueError("Duplicate actor split entries")


def discover_fits(root: Path) -> list[FitRecord]:
    records: list[FitRecord] = []
    for path in sorted(root.rglob("*.npz")):
        data = np.load(path, allow_pickle=False)
        if "expression" not in data.files and "expression_smoothed" not in data.files:
            continue
        meta = json.loads(str(data["metadata"])) if "metadata" in data.files else {}
        stem = path.stem.split("__")
        records.append(FitRecord(path, stem[0] if stem else str(meta.get("actor_id", meta.get("actor", "unknown"))), stem[2] if len(stem) > 2 else str(meta.get("emotion", "unknown")), float(meta.get("intensity", 1.0))))
    return records


def discover_training_records(root: Path) -> list[TrainingRecord]:
    records: list[TrainingRecord] = []
    for path in sorted(root.rglob("*.npz")):
        data = np.load(path, allow_pickle=False)
        if "beta_target" not in data.files or "mouth_expression" not in data.files:
            continue
        records.append(TrainingRecord(path, str(data["actor_id"]), str(data["emotion"]), float(data["intensity"]), str(data["sample_id"])))
    return records


def load_gnm_sequence(path: Path):
    from voice_face.types import GNMSequence, SampleMetadata

    data = np.load(path, allow_pickle=False)
    meta = json.loads(str(data["metadata"])) if "metadata" in data.files else {}
    stem = path.stem.split("__")
    sample = SampleMetadata(path.stem, stem[0] if stem else str(meta.get("actor_id", "unknown")), stem[2] if len(stem) > 2 else str(meta.get("emotion", "unknown")), int(float(meta.get("intensity", 1))), Path(str(meta.get("source_video", path))), stem[1] if len(stem) > 1 else "")
    return GNMSequence(data["timestamps"] if "timestamps" in data.files else data["timestamps_ms"].astype(np.float32) / 1000.0, data["expression_raw"] if "expression_raw" in data.files else data["expression"], data["expression_smoothed"] if "expression_smoothed" in data.files else data["expression"], data["rotation"] if "rotation" in data.files else data["rotations"], data["translation"], data["fit_error"] if "fit_error" in data.files else data["landmark_rmse"], data["valid"].astype(bool), sample)


def mouth_from_fit(path: Path):
    from voice_face.mouth import BlendshapeMouthDriver

    data = np.load(path, allow_pickle=False)
    timestamps = data["timestamps"] if "timestamps" in data.files else data["timestamps_ms"].astype(np.float32) / 1000.0
    return BlendshapeMouthDriver.from_fit(path).predict(Path(""), timestamps)


class TrainingSequenceDataset:
    def __init__(self, records: Sequence[TrainingRecord], *, split: str = "train", split_path: Path | None = None, emotion_to_index: dict[str, int] | None = None):
        import torch

        self._torch = torch
        split_by_actor = read_actor_splits(split_path) if split_path else {record.actor: actor_split(record.actor) for record in records}
        assert_actor_independent(split_by_actor)
        wanted = "val" if split == "validation" else split
        self.records = [record for record in records if split_by_actor.get(record.actor) == wanted]
        labels = sorted({record.emotion for record in records})
        self.label_to_index = emotion_to_index or {label: i for i, label in enumerate(labels)}

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]
        seq = load_training_sequence(record.path)
        return {
            "mouth": self._torch.from_numpy(seq.mouth.features.astype(np.float32)),
            "mouth_expression": self._torch.from_numpy(seq.mouth_expression.astype(np.float32)),
            "prosody": self._torch.from_numpy(seq.prosody.astype(np.float32)),
            "target_expression": self._torch.from_numpy(seq.beta_target.astype(np.float32)),
            "valid": self._torch.from_numpy(seq.valid.astype(bool)),
            "emotion_label": seq.emotion,
            "emotion_index": self._torch.tensor(self.label_to_index[seq.emotion]),
            "intensity": self._torch.tensor(float(seq.intensity) / 3.0, dtype=self._torch.float32),
            "metadata": seq.metadata,
            "actor_id": seq.actor_id,
            "sample_id": seq.sample_id,
            "path": str(record.path),
        }


GnmTrajectoryDataset = TrainingSequenceDataset

class FitTrajectoryDataset:
    def __init__(self, records: Sequence[FitRecord], *, split: str = "train", split_path: Path | None = None):
        import torch

        self._torch = torch
        split_by_actor = read_actor_splits(split_path) if split_path else {record.actor: actor_split(record.actor) for record in records}
        wanted = "val" if split == "validation" else split
        self.records = [record for record in records if split_by_actor.get(record.actor) == wanted]
        self.label_to_index = {label: i for i, label in enumerate(sorted({record.emotion for record in records}))}

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]
        seq = load_gnm_sequence(record.path)
        mouth = mouth_from_fit(record.path)
        data = np.load(record.path, allow_pickle=False)
        prosody = data["prosody"].astype(np.float32) if "prosody" in data.files else None
        return {
            "mouth": self._torch.from_numpy(mouth.features.astype(np.float32)),
            "emotion_label": record.emotion,
            "emotion_index": self._torch.tensor(self.label_to_index[record.emotion]),
            "intensity": self._torch.tensor(record.intensity, dtype=self._torch.float32),
            "prosody": None if prosody is None else self._torch.from_numpy(prosody),
            "target_expression": self._torch.from_numpy(np.nan_to_num(seq.expression_smoothed.astype(np.float32))),
            "valid": self._torch.from_numpy(seq.valid),
            "metadata": seq.metadata,
            "path": str(record.path),
        }

GnmTrajectoryDataset = FitTrajectoryDataset
