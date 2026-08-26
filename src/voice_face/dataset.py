# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""PyTorch dataset over fitted GNM trajectories with actor-independent splits."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from voice_face.mouth import MouthTrajectory
from voice_face.types import GNMSequence, SampleMetadata


@dataclass(frozen=True, slots=True)
class FitRecord:
    path: Path
    actor: str
    emotion: str
    intensity: float = 1.0


def actor_split(actor: str, *, val_fraction: float = 0.15, test_fraction: float = 0.15) -> str:
    bucket = int(hashlib.sha1(actor.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    if bucket < test_fraction:
        return "test"
    if bucket < test_fraction + val_fraction:
        return "val"
    return "train"


def write_actor_splits(records: Sequence[FitRecord], path: Path) -> dict[str, str]:
    split_by_actor = {actor: actor_split(actor) for actor in sorted({record.actor for record in records})}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(split_by_actor, indent=2, sort_keys=True), encoding="utf-8")
    return split_by_actor


def read_actor_splits(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_actor_independent(split_by_actor: dict[str, str]) -> None:
    actors_by_split: dict[str, set[str]] = {}
    for actor, split in split_by_actor.items():
        actors_by_split.setdefault(split, set()).add(actor)
    seen: set[str] = set()
    for actors in actors_by_split.values():
        overlap = seen & actors
        if overlap:
            raise ValueError(f"Actors appear in multiple splits: {sorted(overlap)}")
        seen |= actors


def discover_fits(root: Path) -> list[FitRecord]:
    records: list[FitRecord] = []
    for path in sorted(root.rglob("*.npz")):
        data = np.load(path, allow_pickle=False)
        if "expression" not in data.files and "expression_smoothed" not in data.files:
            continue
        meta = json.loads(str(data["metadata"]))
        stem = path.stem.split("__")
        actor = stem[0] if stem else str(meta.get("actor_id", meta.get("actor", "unknown")))
        emotion = stem[2] if len(stem) > 2 else str(meta.get("emotion", "unknown"))
        intensity = float(meta.get("intensity", 1.0))
        records.append(FitRecord(path, actor, emotion, intensity))
    return records


def load_gnm_sequence(path: Path) -> GNMSequence:
    data = np.load(path, allow_pickle=False)
    meta = json.loads(str(data["metadata"]))
    stem = path.stem.split("__")
    sample = SampleMetadata(
        sample_id=path.stem,
        actor_id=stem[0] if stem else str(meta.get("actor_id", meta.get("actor", "unknown"))),
        emotion=stem[2] if len(stem) > 2 else str(meta.get("emotion", "unknown")),
        intensity=int(float(meta.get("intensity", 1))),
        video_path=Path(meta["source_video"]) if meta.get("source_video") else path,
        camera=stem[1] if len(stem) > 1 else "",
    )
    return GNMSequence(timestamps=data["timestamps"] if "timestamps" in data.files else data["timestamps_ms"].astype(np.float32) / 1000.0, expression_raw=data["expression_raw"] if "expression_raw" in data.files else data["expression"], expression_smoothed=data["expression_smoothed"] if "expression_smoothed" in data.files else data["expression"], rotation=data["rotation"] if "rotation" in data.files else data["rotations"], translation=data["translation"], fit_error=data["fit_error"] if "fit_error" in data.files else data["landmark_rmse"], valid=data["valid"].astype(bool), metadata=sample)


def mouth_from_fit(path: Path) -> MouthTrajectory:
    data = np.load(path, allow_pickle=False)
    blendshapes = np.nan_to_num(data["blendshapes"].astype(np.float32)) if "blendshapes" in data.files else np.zeros((len(data["valid"]), 0), dtype=np.float32)
    features = np.zeros((len(data["valid"]), 3), dtype=np.float32)
    if blendshapes.shape[1] > 25:
        features[:, 0] = blendshapes[:, 25]
    if blendshapes.shape[1] > 45:
        features[:, 2] = 0.5 * (blendshapes[:, 44] + blendshapes[:, 45])
    timestamps = data["timestamps_ms"].astype(np.float32)
    fps = 1000.0 / float(np.median(np.diff(timestamps))) if len(timestamps) > 1 else 25.0
    return MouthTrajectory(features, data["valid"].astype(bool), fps)


class GnmTrajectoryDataset:
    def __init__(self, records: Sequence[FitRecord], *, split: str = "train", split_path: Path | None = None):
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("PyTorch is required for GnmTrajectoryDataset") from exc
        self._torch = torch
        split_by_actor = read_actor_splits(split_path) if split_path else {record.actor: actor_split(record.actor) for record in records}
        assert_actor_independent(split_by_actor)
        self.records = [record for record in records if split_by_actor[record.actor] == split]
        emotions = sorted({record.emotion for record in records})
        self.label_to_index = {label: i for i, label in enumerate(emotions)}

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
