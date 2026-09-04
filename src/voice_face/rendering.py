# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""GNM prediction rendering and comparison videos."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from voice_face.bootstrap import add_vendor_paths
from voice_face.visualization.diagnostics import _panel
from voice_face.visualization.training_diagnostics import _mux_audio


def render_prediction_video(expression: np.ndarray, identity: np.ndarray, rotation: np.ndarray, translation: np.ndarray, output_path: Path, gnm: Any, *, fps: float = 30.0, size: int = 320, source_audio: Path | None = None) -> Path:
    add_vendor_paths(); import cv2
    from webcam_puppet.renderer import Camera, MeshRenderer
    output_path.parent.mkdir(parents=True, exist_ok=True)
    camera = Camera.fit_to_mesh(gnm.template_vertex_positions, (size, size)); renderer = MeshRenderer(gnm.triangles, camera)
    writer = cv2.VideoWriter(str(output_path), getattr(cv2, "VideoWriter_fourcc")(*"mp4v"), fps, (size, size))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {output_path}")
    for i in range(len(expression)):
        frame = renderer.render(gnm(identity, expression[i], rotation[min(i, len(rotation)-1)], translation[min(i, len(translation)-1)]))
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    writer.release(); _mux_audio(output_path, source_audio)
    return output_path


def render_side_by_side(source_video: Path, prediction_expression: np.ndarray, identity: np.ndarray, rotation: np.ndarray, translation: np.ndarray, output_path: Path, gnm: Any, *, target_expression: np.ndarray | None = None, fps: float = 30.0, size: int = 320, label: str = "") -> Path:
    add_vendor_paths(); import cv2
    from webcam_puppet.renderer import Camera, MeshRenderer
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(source_video)); camera = Camera.fit_to_mesh(gnm.template_vertex_positions, (size, size)); renderer = MeshRenderer(gnm.triangles, camera)
    cols = 3 if target_expression is not None else 2
    writer = cv2.VideoWriter(str(output_path), getattr(cv2, "VideoWriter_fourcc")(*"mp4v"), fps, (size * cols, size))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {output_path}")
    for i in range(len(prediction_expression)):
        ok, frame = cap.read(); original = _panel(frame, size) if ok else np.zeros((size, size, 3), dtype=np.uint8)
        panels = [original]
        if target_expression is not None:
            target = renderer.render(gnm(identity, target_expression[i], rotation[min(i, len(rotation)-1)], translation[min(i, len(translation)-1)]))
            panels.append(cv2.cvtColor(target, cv2.COLOR_RGB2BGR))
        pred = renderer.render(gnm(identity, prediction_expression[i], rotation[min(i, len(rotation)-1)], translation[min(i, len(translation)-1)]))
        panels.append(cv2.cvtColor(pred, cv2.COLOR_RGB2BGR))
        text = label or "ORIGINAL HUMAN | PREDICTED GNM"
        for panel in panels:
            cv2.putText(panel, text, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (245,245,245), 1, cv2.LINE_AA)
        writer.write(np.hstack(panels))
    cap.release(); writer.release(); _mux_audio(output_path, source_video)
    return output_path
