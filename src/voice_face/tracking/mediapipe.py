"""Video tracking through the vendored MediaPipe FaceTracker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from voice_face.bootstrap import add_vendor_paths, repo_root
from voice_face.io import should_skip
from voice_face.types import TrackingSequence


def _open_cv2():
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("OpenCV is required for video tracking") from exc
    return cv2


def track_video(video_path: Path, output_path: Path, *, force: bool = False, output_blendshapes: bool = True) -> Path:
    if should_skip(output_path, force):
        return output_path
    add_vendor_paths()
    from webcam_puppet.tracker import FaceTracker

    cv2 = _open_cv2()
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    landmarks: list[np.ndarray] = []
    blendshapes: list[np.ndarray] = []
    pose: list[np.ndarray] = []
    confidence: list[float] = []
    valid: list[bool] = []
    timestamps: list[float] = []
    landmark_dim = 478
    blendshape_dim = 52 if output_blendshapes else 0
    model_path = repo_root() / "outputs" / "voice_face" / "cache" / "face_landmarker.task"
    with FaceTracker(model_path=model_path, video_mode=True, output_blendshapes=output_blendshapes) as tracker:
        frame_index = 0
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            timestamp = frame_index / fps if fps > 0 else float(frame_index)
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            obs = tracker.detect(rgb, timestamp_ms=int(round(timestamp * 1000.0)))
            if obs is None:
                landmarks.append(np.full((landmark_dim, 3), np.nan, dtype=np.float32))
                blendshapes.append(np.full((blendshape_dim,), np.nan, dtype=np.float32))
                pose.append(np.full((4, 4), np.nan, dtype=np.float32))
                confidence.append(np.nan)
                valid.append(False)
            else:
                landmark_dim = int(obs.landmarks.shape[0])
                landmarks.append(np.asarray(obs.landmarks, dtype=np.float32))
                values = obs.blendshapes if output_blendshapes and obs.blendshapes is not None else np.full((blendshape_dim,), np.nan, dtype=np.float32)
                blendshapes.append(np.asarray(values, dtype=np.float32))
                pose.append(np.full((4, 4), np.nan, dtype=np.float32))
                confidence.append(1.0)
                valid.append(True)
            timestamps.append(timestamp)
            frame_index += 1
    cap.release()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"version": 1, "source_video": str(video_path.resolve()), "width": width, "height": height, "fps": fps, "tracker": "webcam_puppet.FaceTracker", "output_blendshapes": output_blendshapes}
    t = np.asarray(timestamps, dtype=np.float32)
    np.savez_compressed(
        output_path,
        timestamps=t,
        timestamps_ms=(t * 1000).astype(np.int64),
        landmarks=np.asarray(landmarks, dtype=np.float32),
        blendshapes=np.asarray(blendshapes, dtype=np.float32) if output_blendshapes else np.empty((len(valid), 0), dtype=np.float32),
        pose=np.asarray(pose, dtype=np.float32),
        tracking_confidence=np.asarray(confidence, dtype=np.float32),
        valid=np.asarray(valid, dtype=bool),
        metadata=json.dumps(metadata, sort_keys=True),
    )
    return output_path


def load_tracking(path: Path) -> dict[str, Any]:
    data = np.load(path, allow_pickle=False)
    metadata = json.loads(str(data["metadata"]))
    timestamps = data["timestamps"] if "timestamps" in data.files else data["timestamps_ms"].astype(np.float32) / 1000.0
    blendshapes = data["blendshapes"] if "blendshapes" in data.files else np.empty((len(timestamps), 0), dtype=np.float32)
    return {"timestamps": timestamps, "timestamps_ms": (timestamps * 1000).astype(np.int64), "landmarks": data["landmarks"], "blendshapes": blendshapes, "pose": data["pose"] if "pose" in data.files else np.empty((len(timestamps), 0), dtype=np.float32), "tracking_confidence": data["tracking_confidence"] if "tracking_confidence" in data.files else np.full(len(timestamps), np.nan), "valid": data["valid"], "metadata": metadata}


def load_tracking_sequence(path: Path) -> TrackingSequence:
    tracking = load_tracking(path)
    return TrackingSequence(tracking["landmarks"], tracking["blendshapes"], tracking["valid"].astype(bool), tracking["timestamps"], tracking["metadata"], tracking["pose"], tracking["tracking_confidence"])
