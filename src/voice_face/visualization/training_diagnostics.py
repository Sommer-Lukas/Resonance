"""Diagnostics for synchronized TrainingSequence records."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from voice_face.bootstrap import add_vendor_paths
from voice_face.io import should_skip
from voice_face.training_records import load_training_sequence
from voice_face.visualization.diagnostics import _panel


def _mux_audio(video_path: Path, source_video: Path | None) -> None:
    if source_video is None or not source_video.exists():
        return
    try:
        import imageio_ffmpeg
    except ImportError:
        return
    tmp = video_path.with_suffix(".silent.mp4")
    video_path.rename(tmp)
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-i", str(tmp), "-i", str(source_video), "-map", "0:v:0", "-map", "1:a:0?", "-shortest", "-c:v", "copy", "-c:a", "aac", str(video_path)]
    proc = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        tmp.rename(video_path)
    else:
        tmp.unlink(missing_ok=True)


def _mouth_expression(gnm: Any, jaw: float, lip_close: float, smile: float) -> np.ndarray:
    expression = np.zeros(int(gnm.expression_dim), dtype=np.float32)
    if expression.size:
        expression[0] = jaw * 2.0
    if expression.size > 1:
        expression[1] = lip_close
    if expression.size > 2:
        expression[2] = smile
    return expression


def render_training_diagnostic(training_path: Path, fit_path: Path, output_path: Path, gnm: Any, *, force: bool = False, size: int = 320) -> Path:
    if should_skip(output_path, force):
        return output_path
    add_vendor_paths()
    import cv2
    from webcam_puppet.renderer import Camera, MeshRenderer

    sequence = load_training_sequence(training_path)
    fit = np.load(fit_path, allow_pickle=False)
    meta = json.loads(str(fit["metadata"])) if "metadata" in fit.files else {}
    source_video = Path(str(meta.get("source_video", ""))) if meta.get("source_video") else None
    video = cv2.VideoCapture(str(source_video)) if source_video else None
    target_expression = fit["expression_smoothed"] if "expression_smoothed" in fit.files else fit["expression"]
    rotation = fit["rotation"] if "rotation" in fit.files else fit["rotations"]
    camera = Camera.fit_to_mesh(gnm.template_vertex_positions, (size, size))
    renderer = MeshRenderer(gnm.triangles, camera)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fps = float(meta.get("fps") or 25.0)
    writer = cv2.VideoWriter(str(output_path), getattr(cv2, "VideoWriter_fourcc")(*"mp4v"), fps, (size * 3, size))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {output_path}")
    identity = fit["identity"]
    translation = fit["translation"]
    for index, timestamp in enumerate(sequence.timestamps):
        original = np.zeros((size, size, 3), dtype=np.uint8)
        if video is not None:
            ok, frame_bgr = video.read()
            if ok:
                original = _panel(frame_bgr, size)
        target = cv2.cvtColor(renderer.render(gnm(identity, target_expression[index], rotation[index], translation[index])), cv2.COLOR_RGB2BGR)
        mouth_row = sequence.mouth.features[index]
        mouth_expression = _mouth_expression(gnm, float(mouth_row[0]), float(mouth_row[1]), float(mouth_row[2]))
        mouth = cv2.cvtColor(renderer.render(gnm(identity, mouth_expression, rotation[index], translation[index])), cv2.COLOR_RGB2BGR)
        label = f"{sequence.sample_id} t={float(timestamp):.3f}s jaw={mouth_row[0]:.2f} rms={sequence.prosody[index,1]:.3f} f0={sequence.prosody[index,0]:.0f}"
        for panel in (original, target, mouth):
            cv2.putText(panel, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (245, 245, 245), 1, cv2.LINE_AA)
        writer.write(np.hstack([original, target, mouth]))
    if video is not None:
        video.release()
    writer.release()
    _mux_audio(output_path, source_video)
    return output_path
