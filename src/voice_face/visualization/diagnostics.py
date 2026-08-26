"""Render GNM fit diagnostics and write extraction reports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from voice_face.bootstrap import add_vendor_paths
from voice_face.fitting.smoothing import trajectory_stats
from voice_face.io import should_skip, write_json


def _fit_error(data):
    return data["fit_error"] if "fit_error" in data.files else data["landmark_rmse"]


def _timestamps(data):
    return data["timestamps"] if "timestamps" in data.files else data["timestamps_ms"].astype(np.float32) / 1000.0


def write_fit_report(fit_path: Path, report_path: Path) -> Path:
    data = np.load(fit_path, allow_pickle=False)
    valid = data["valid"].astype(bool)
    errors = _fit_error(data).astype(np.float32)
    expr = data["expression_smoothed"] if "expression_smoothed" in data.files else data["expression"]
    stats = trajectory_stats(np.nan_to_num(expr.astype(np.float32)), valid)
    valid_errors = errors[valid]
    payload = {
        "fit_path": str(fit_path),
        "frames": int(len(valid)),
        "valid_frames": int(valid.sum()),
        "invalid_frames": int((~valid).sum()),
        "tracked_frame_percentage": float(valid.mean() * 100.0) if len(valid) else 0.0,
        "mean_fitting_error": float(np.nanmean(valid_errors)) if valid_errors.size else None,
        "mean_landmark_rmse": float(np.nanmean(valid_errors)) if valid_errors.size else None,
        "median_fitting_error": float(np.nanmedian(valid_errors)) if valid_errors.size else None,
        "p95_fitting_error": float(np.nanpercentile(valid_errors, 95)) if valid_errors.size else None,
        "failed_frames": [int(i) for i in np.flatnonzero(~valid)],
        "velocity_statistics": {"mean": stats.mean_abs_velocity, "p95": stats.p95_abs_velocity},
        "acceleration_jitter_statistics": {"mean": stats.mean_abs_acceleration, "p95": stats.p95_abs_acceleration},
        "metadata": json.loads(str(data["metadata"])),
    }
    write_json(report_path, payload)
    return report_path


def write_frame_stats(fit_path: Path, csv_path: Path) -> Path:
    data = np.load(fit_path, allow_pickle=False)
    timestamps = _timestamps(data)
    errors = _fit_error(data)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["frame", "timestamp", "valid", "fit_error"])
        writer.writeheader()
        for i, ok in enumerate(data["valid"].astype(bool)):
            writer.writerow({"frame": i, "timestamp": float(timestamps[i]), "valid": bool(ok), "fit_error": float(errors[i]) if ok else ""})
    return csv_path


def _panel(frame_bgr: np.ndarray, size: int) -> np.ndarray:
    import cv2

    if frame_bgr.size == 0:
        return np.zeros((size, size, 3), dtype=np.uint8)
    h, w = frame_bgr.shape[:2]
    scale = min(size / w, size / h)
    resized = cv2.resize(frame_bgr, (max(1, int(round(w * scale))), max(1, int(round(h * scale)))), interpolation=cv2.INTER_AREA)
    out = np.zeros((size, size, 3), dtype=np.uint8)
    top = (size - resized.shape[0]) // 2
    left = (size - resized.shape[1]) // 2
    out[top:top + resized.shape[0], left:left + resized.shape[1]] = resized
    return out


def _draw_landmarks(panel: np.ndarray, landmarks: np.ndarray, source_shape: tuple[int, int], size: int) -> None:
    import cv2

    h, w = source_shape
    scale = min(size / w, size / h)
    left = (size - int(round(w * scale))) // 2
    top = (size - int(round(h * scale))) // 2
    for point in landmarks:
        if np.isfinite(point[:2]).all():
            x = int(round(left + point[0] * w * scale))
            y = int(round(top + point[1] * h * scale))
            cv2.circle(panel, (x, y), 1, (0, 255, 80), -1, cv2.LINE_AA)


def render_fit_video(fit_path: Path, output_path: Path, gnm: Any, *, force: bool = False, size: int = 480) -> Path:
    if should_skip(output_path, force):
        return output_path
    add_vendor_paths()
    import cv2
    from webcam_puppet.renderer import Camera, MeshRenderer

    data = np.load(fit_path, allow_pickle=False)
    meta = json.loads(str(data["metadata"]))
    expression = data["expression_smoothed"] if "expression_smoothed" in data.files else data["expression"]
    rotation = data["rotation"] if "rotation" in data.files else data["rotations"]
    errors = _fit_error(data)
    tracking = None
    tracking_path = Path(str(meta.get("source_tracking", "")))
    if tracking_path.exists():
        tracking = np.load(tracking_path, allow_pickle=False)
    video = cv2.VideoCapture(str(meta.get("source_video", ""))) if meta.get("source_video") else None

    camera = Camera.fit_to_mesh(gnm.template_vertex_positions, (size, size))
    renderer = MeshRenderer(gnm.triangles, camera)
    fps = float(meta.get("fps") or 25.0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_path), getattr(cv2, "VideoWriter_fourcc")(*"mp4v"), fps, (size * 3, size))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {output_path}")

    valid = data["valid"].astype(bool)
    for index, ok in enumerate(valid):
        source_bgr = np.zeros((size, size, 3), dtype=np.uint8)
        if video is not None:
            read_ok, frame_bgr = video.read()
            if read_ok:
                source_bgr = _panel(frame_bgr, size)
                landmark_bgr = source_bgr.copy()
            else:
                landmark_bgr = source_bgr.copy()
        else:
            landmark_bgr = source_bgr.copy()
        if tracking is not None and index < len(tracking["landmarks"]):
            width = int(meta.get("width") or source_bgr.shape[1])
            height = int(meta.get("height") or source_bgr.shape[0])
            _draw_landmarks(landmark_bgr, tracking["landmarks"][index], (height, width), size)
        if ok:
            rendered = renderer.render(gnm(data["identity"], expression[index], rotation[index], data["translation"][index]))
            render_bgr = cv2.cvtColor(rendered, cv2.COLOR_RGB2BGR)
        else:
            render_bgr = np.zeros((size, size, 3), dtype=np.uint8)
        text = f"{fit_path.stem} frame {index} valid={bool(ok)} err={float(errors[index]) if ok else float('nan'):.4f}"
        for panel in (source_bgr, landmark_bgr, render_bgr):
            cv2.putText(panel, text, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (245, 245, 245), 1, cv2.LINE_AA)
        writer.write(np.hstack([source_bgr, landmark_bgr, render_bgr]))
    if video is not None:
        video.release()
    writer.release()
    return output_path
