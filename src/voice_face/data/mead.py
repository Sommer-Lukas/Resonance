"""MEAD indexing with restartable, configurable filtering."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


@dataclass(frozen=True, slots=True)
class MeadIndexConfig:
    actors: tuple[str, ...] = ()
    emotions: tuple[str, ...] = ()
    intensities: tuple[int, ...] = ()
    frontal_only: bool = False
    clips_per_condition: int | None = None
    max_clips: int | None = None


@dataclass(frozen=True, slots=True)
class MeadSample:
    sample_id: str
    actor_id: str
    emotion: str
    intensity: int
    camera: str
    video_path: Path
    audio_path: Path | None
    utterance_id: str
    fps: float
    frame_count: int
    duration: float

    @property
    def actor(self) -> str:
        return self.actor_id

    @property
    def level(self) -> str:
        return f"level_{self.intensity}"

    @property
    def clip(self) -> str:
        return self.utterance_id


def _video_meta(path: Path) -> tuple[float, int, float]:
    try:
        import cv2
    except ImportError:  # pragma: no cover
        return 0.0, 0, 0.0
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return 0.0, 0, 0.0
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    return fps, frames, frames / fps if fps > 0 else 0.0


def _audio_actor(actor: str) -> str:
    return f"audio_{actor.removeprefix('video_')}" if actor.startswith("video_") else actor


def _maybe_audio(video_path: Path, root: Path, actor: str, emotion: str, level: str, clip: str) -> Path | None:
    audio_actor = _audio_actor(actor)
    stems = (
        video_path.with_suffix(""),
        root / audio_actor / emotion / level / clip,
        root / actor / "audio" / emotion / level / clip,
        root / actor / "audio" / "front" / emotion / level / clip,
    )
    for stem in stems:
        for suffix in (".wav", ".m4a", ".mp3", ".aac"):
            candidate = stem.with_suffix(suffix)
            if candidate.exists():
                return candidate.resolve()
    return None


def parse_mead_path(path: Path, root: Path) -> MeadSample:
    rel = path.resolve().relative_to(root.resolve())
    parts = rel.parts
    if len(parts) < 5:
        raise ValueError(f"Unsupported MEAD layout: {rel}")
    actor = parts[0]
    offset = 2 if len(parts) >= 6 and parts[1] == "video" else 1
    if len(parts) < offset + 4:
        raise ValueError(f"Unsupported MEAD layout: {rel}")
    camera, emotion, level, clip_file = parts[offset : offset + 4]
    clip = Path(clip_file).stem
    intensity = int(level.removeprefix("level_"))
    fps, frame_count, duration = _video_meta(path)
    sample_id = "__".join([actor, camera, emotion, level, clip])
    return MeadSample(sample_id, actor, emotion, intensity, camera, path.resolve(), _maybe_audio(path, root, actor, emotion, level, clip), clip, fps, frame_count, duration)


def load_index_config(path: Path | None) -> MeadIndexConfig:
    if path is None:
        return MeadIndexConfig()
    if yaml is None:  # pragma: no cover
        raise RuntimeError("PyYAML is required for YAML configuration")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return MeadIndexConfig(
        actors=tuple(map(str, payload.get("actors") or ())),
        emotions=tuple(map(str, payload.get("emotions") or ())),
        intensities=tuple(int(v) for v in (payload.get("intensities") or ())),
        frontal_only=bool(payload.get("frontal_only", False)),
        clips_per_condition=payload.get("clips_per_condition"),
        max_clips=payload.get("max_clips"),
    )


def _keep(sample: MeadSample, config: MeadIndexConfig) -> bool:
    return not (
        (config.actors and sample.actor_id not in config.actors)
        or (config.emotions and sample.emotion not in config.emotions)
        or (config.intensities and sample.intensity not in config.intensities)
        or (config.frontal_only and sample.camera != "front")
    )


def index_mead(root: Path, config: MeadIndexConfig | None = None) -> list[MeadSample]:
    root = root.resolve()
    config = config or MeadIndexConfig()
    samples: list[MeadSample] = []
    per_condition: dict[tuple[str, str, int, str], int] = defaultdict(int)
    for path in sorted(root.rglob("*.mp4")):
        try:
            sample = parse_mead_path(path, root)
        except (ValueError, OSError):
            continue
        if not _keep(sample, config):
            continue
        key = (sample.actor_id, sample.emotion, sample.intensity, sample.camera)
        if config.clips_per_condition is not None and per_condition[key] >= config.clips_per_condition:
            continue
        samples.append(sample)
        per_condition[key] += 1
        if config.max_clips is not None and len(samples) >= config.max_clips:
            break
    return samples


def write_index(samples: list[MeadSample], path: Path) -> None:
    fields = ["sample_id", "actor_id", "emotion", "intensity", "camera", "video_path", "audio_path", "utterance_id", "fps", "frame_count", "duration"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for sample in samples:
            row: dict[str, Any] = asdict(sample)
            row["video_path"] = str(sample.video_path)
            row["audio_path"] = "" if sample.audio_path is None else str(sample.audio_path)
            writer.writerow(row)


def read_index(path: Path) -> list[MeadSample]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = []
        for row in csv.DictReader(handle):
            rows.append(MeadSample(row["sample_id"], row["actor_id"], row["emotion"], int(row["intensity"]), row["camera"], Path(row["video_path"]), Path(row["audio_path"]) if row["audio_path"] else None, row["utterance_id"], float(row["fps"] or 0), int(row["frame_count"] or 0), float(row["duration"] or 0)))
        return rows
