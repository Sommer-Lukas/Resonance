#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.render_lower_face_sweep import (  # noqa: E402
    _lower_face_material_renderers,
    _metadata,
    _mux_source_audio,
    _panel,
    _put_label,
    _render_lower_face_material,
    _rotation,
    _sample_path,
    _source_video,
    lower_face_indices,
)
from voice_face.bootstrap import add_vendor_paths  # noqa: E402
from voice_face.fitting.expression_processing import blendshape  # noqa: E402
from voice_face.gnm.load import load_gnm  # noqa: E402

PROCESSED_ROOT = ROOT / "data" / "processed" / "gnm" / "sequences_processed"
OUTPUT_ROOT = ROOT / "outputs" / "mouth_aperture_sweep"
CORRESPONDENCE = ROOT / "third_party" / "gnm-webcam-puppet" / "webcam_puppet" / "assets" / "correspondence.npz"
INNER_UPPER = 13
INNER_LOWER = 14
OUTER_UPPER = 0
OUTER_LOWER = 17
LEFT_CORNER = 61
RIGHT_CORNER = 291
INNER_PAIRS = ((13, 14), (82, 87), (312, 317), (81, 178), (311, 402))
UPPER_INNER = (13, 82, 312, 81, 311)
LOWER_INNER = (14, 87, 317, 178, 402)


@dataclass(frozen=True)
class Candidate:
    code: str
    aperture_weight: float
    jaw_weight: float
    lower_regularization: str
    smoothing: str


CANDIDATES = (
    Candidate("M0", 0.0, 0.0, "current", "current"),
    Candidate("M1", 0.75, 1.0, "current", "current"),
    Candidate("M2", 1.25, 1.5, "current", "current"),
    Candidate("M3", 1.75, 2.0, "current", "current"),
)


def _processed_path(sample: str) -> Path:
    path = PROCESSED_ROOT / f"{Path(sample).stem}.npz"
    if path.exists():
        return path
    raise FileNotFoundError(path)


def _available_pairs(mapped: dict[int, int] | None = None) -> tuple[tuple[int, int], ...]:
    if mapped is None:
        return INNER_PAIRS
    return tuple(pair for pair in INNER_PAIRS if pair[0] in mapped and pair[1] in mapped)


def _available_indices(indices: tuple[int, ...], mapped: dict[int, int]) -> list[int]:
    return [index for index in indices if index in mapped]


def _mp_aperture(landmarks: np.ndarray, pairs: tuple[tuple[int, int], ...]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    width = np.abs(landmarks[:, RIGHT_CORNER, 0] - landmarks[:, LEFT_CORNER, 0])
    width = np.maximum(width, 1e-6)
    inner_values = [np.abs(landmarks[:, lower, 1] - landmarks[:, upper, 1]) for upper, lower in pairs]
    inner = np.mean(np.stack(inner_values, axis=1), axis=1) if inner_values else np.zeros(len(landmarks), dtype=np.float32)
    outer = np.abs(landmarks[:, OUTER_LOWER, 1] - landmarks[:, OUTER_UPPER, 1])
    return inner / width, inner, outer, width


def _mapped_vertices(correspondence: Any) -> dict[int, int]:
    return {int(landmark): int(vertex) for landmark, vertex in zip(correspondence.landmark_indices, correspondence.vertex_indices, strict=True)}


def _gnm_aperture(vertices: np.ndarray, mapped: dict[int, int]) -> tuple[float, float, float, float, float, float]:
    pairs = _available_pairs(mapped)
    upper_outer = vertices[mapped[OUTER_UPPER]]
    lower_outer = vertices[mapped[OUTER_LOWER]]
    left = vertices[mapped[LEFT_CORNER]]
    right = vertices[mapped[RIGHT_CORNER]]
    width = max(float(np.linalg.norm(right[:2] - left[:2])), 1e-6)
    inner = float(np.mean([abs(float(vertices[mapped[lower], 1] - vertices[mapped[upper], 1])) for upper, lower in pairs])) if pairs else 0.0
    outer = abs(float(lower_outer[1] - upper_outer[1]))
    upper_points = _available_indices(UPPER_INNER, mapped)
    lower_points = _available_indices(LOWER_INNER, mapped)
    upper_inner = np.mean([vertices[mapped[index], :2] for index in upper_points], axis=0) if upper_points else upper_outer[:2]
    lower_inner = np.mean([vertices[mapped[index], :2] for index in lower_points], axis=0) if lower_points else lower_outer[:2]
    upper_thickness = float(np.linalg.norm(upper_outer[:2] - upper_inner)) / width
    lower_thickness = float(np.linalg.norm(lower_outer[:2] - lower_inner)) / width
    return inner / width, inner, outer, width, upper_thickness, lower_thickness


def _expressions(data: Any) -> tuple[np.ndarray, np.ndarray]:
    current = data["expression_processed"].astype(np.float32, copy=False)
    raw = data["expression_neutral_relative"].astype(np.float32, copy=False)
    return current, raw


def _learn_aperture_direction(gnm: Any, identity: np.ndarray, expression: np.ndarray, rotation: np.ndarray, translation: np.ndarray, lower_indices: np.ndarray, mapped: dict[int, int]) -> np.ndarray:
    direction = np.zeros(expression.shape[0], dtype=np.float32)
    base = expression.copy()
    step = 1.0
    scores = []
    for index in lower_indices:
        plus = base.copy()
        minus = base.copy()
        plus[index] += step
        minus[index] -= step
        plus_values = _gnm_aperture(gnm(identity, plus, rotation, translation), mapped)
        minus_values = _gnm_aperture(gnm(identity, minus, rotation, translation), mapped)
        aperture_response = (plus_values[0] - minus_values[0]) / (2.0 * step)
        thickness_response = abs(plus_values[4] - minus_values[4]) + abs(plus_values[5] - minus_values[5])
        if aperture_response > 0.0:
            scores.append((aperture_response / (0.03 + thickness_response), int(index)))
    if not scores:
        return direction
    scores.sort(reverse=True)
    for score, index in scores[:12]:
        direction[index] = score
    norm = float(np.max(np.abs(direction)))
    if norm > 1e-6:
        direction /= norm
    return direction.astype(np.float32)


def _candidate_expression(current: np.ndarray, source_aperture: np.ndarray, current_aperture: np.ndarray, jaw_open: np.ndarray, direction: np.ndarray, candidate: Candidate) -> np.ndarray:
    if candidate.code == "M0":
        return current.copy()
    deficit = np.maximum(source_aperture[: len(current)] - current_aperture[: len(current)], 0.0)
    drive = deficit * float(candidate.aperture_weight) * (1.0 + float(candidate.jaw_weight) * jaw_open[: len(current)])
    return (current + drive[:, None].astype(np.float32) * direction[None, :]).astype(np.float32)


def _render(gnm: Any, renderers: tuple[Any, list[Any]], identity: np.ndarray, expression: np.ndarray, rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    import cv2

    image = _render_lower_face_material(gnm(identity, expression, rotation, translation), renderers[0], renderers[1])
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


def _crop_mouth(panel: np.ndarray) -> np.ndarray:
    h, w = panel.shape[:2]
    return panel[int(h * 0.42) : int(h * 0.84), int(w * 0.18) : int(w * 0.82)]


def render_sample(sample: str, *, size: int) -> Path:
    add_vendor_paths()
    import cv2
    from webcam_puppet.correspondence import Correspondence
    from webcam_puppet.renderer import Camera

    old_path = _sample_path(sample)
    processed_path = _processed_path(old_path.stem)
    gnm = load_gnm()
    lower_indices = lower_face_indices(gnm)
    correspondence = Correspondence.load(CORRESPONDENCE)
    mapped = _mapped_vertices(correspondence)
    pairs = _available_pairs(mapped)
    if not pairs:
        raise RuntimeError("No mapped inner-lip landmark pairs found in correspondence")
    out_dir = OUTPUT_ROOT / old_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    with np.load(old_path, allow_pickle=False) as old_data, np.load(processed_path, allow_pickle=False) as new_data:
        old_expression = old_data["expression"].astype(np.float32, copy=False)
        current, raw = _expressions(new_data)
        identity = old_data["identity"].astype(np.float32, copy=False)
        rotation = _rotation(old_data).astype(np.float32, copy=False)
        translation = old_data["translation"].astype(np.float32, copy=False)
        landmarks = old_data["landmarks"] if "landmarks" in old_data.files else None
        if landmarks is None:
            tracking_path = _metadata(old_data, old_path).get("source_tracking")
            with np.load(str(tracking_path), allow_pickle=False) as tracking:
                landmarks = tracking["landmarks"].astype(np.float32, copy=False)
        meta = _metadata(old_data, old_path)
        source_video = _source_video(meta)
        fps = float(meta.get("fps") or 30.0)
        jaw_open = blendshape(old_data, "jawOpen")
        mouth_close = blendshape(old_data, "mouthClose")
    source_aperture, source_inner, source_outer, source_width = _mp_aperture(landmarks, pairs)
    camera = Camera.fit_to_mesh(gnm.template_vertex_positions, (size, size))
    renderers = _lower_face_material_renderers(gnm, camera)
    frames = min(len(old_expression), len(current), len(raw), len(rotation), len(translation), len(source_aperture))
    old_aperture = np.zeros(frames, dtype=np.float32)
    current_aperture = np.zeros(frames, dtype=np.float32)
    old_lip = np.zeros((frames, 2), dtype=np.float32)
    current_lip = np.zeros((frames, 2), dtype=np.float32)
    for frame in range(frames):
        pose = rotation[min(frame, len(rotation) - 1)]
        offset = translation[min(frame, len(translation) - 1)]
        old_values = _gnm_aperture(gnm(identity, old_expression[frame], pose, offset), mapped)
        current_values = _gnm_aperture(gnm(identity, current[frame], pose, offset), mapped)
        old_aperture[frame] = old_values[0]
        current_aperture[frame] = current_values[0]
        old_lip[frame] = old_values[4], old_values[5]
        current_lip[frame] = current_values[4], current_values[5]
    neutral_expression = np.median(current[:frames], axis=0).astype(np.float32)
    direction = _learn_aperture_direction(gnm, identity, neutral_expression, rotation[0], translation[0], lower_indices, mapped)
    candidate_expressions = {candidate.code: _candidate_expression(current[:frames], source_aperture[:frames], current_aperture, jaw_open[:frames], direction, candidate) for candidate in CANDIDATES}
    candidate_aperture: dict[str, np.ndarray] = {}
    candidate_lip: dict[str, np.ndarray] = {}
    for candidate in CANDIDATES:
        apertures = np.zeros(frames, dtype=np.float32)
        lips = np.zeros((frames, 2), dtype=np.float32)
        expr = candidate_expressions[candidate.code]
        for frame in range(frames):
            values = _gnm_aperture(gnm(identity, expr[frame], rotation[min(frame, len(rotation) - 1)], translation[min(frame, len(translation) - 1)]), mapped)
            apertures[frame] = values[0]
            lips[frame] = values[4], values[5]
        candidate_aperture[candidate.code] = apertures
        candidate_lip[candidate.code] = lips
    _write_parameters(out_dir / "parameters.csv")
    _write_metrics(out_dir / "aperture_metrics.csv", frames, source_aperture, source_inner, source_outer, source_width, jaw_open, mouth_close, old_aperture, current_aperture, candidate_aperture, old_lip, current_lip, candidate_lip)
    _write_videos(out_dir, old_path.stem, gnm, renderers, identity, rotation, translation, meta, source_video, fps, size, frames, source_aperture, jaw_open, current_aperture, candidate_aperture, current, candidate_expressions)
    return out_dir


def _write_parameters(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["candidate", "aperture_weight", "jaw_weight", "lower_regularization", "smoothing"])
        writer.writeheader()
        for candidate in CANDIDATES:
            writer.writerow({"candidate": candidate.code, "aperture_weight": candidate.aperture_weight, "jaw_weight": candidate.jaw_weight, "lower_regularization": candidate.lower_regularization, "smoothing": candidate.smoothing})


def _write_metrics(path: Path, frames: int, source_aperture: np.ndarray, source_inner: np.ndarray, source_outer: np.ndarray, source_width: np.ndarray, jaw_open: np.ndarray, mouth_close: np.ndarray, old_aperture: np.ndarray, current_aperture: np.ndarray, candidate_aperture: dict[str, np.ndarray], old_lip: np.ndarray, current_lip: np.ndarray, candidate_lip: dict[str, np.ndarray]) -> None:
    fields = ["frame", "mediapipe_jawOpen", "mediapipe_mouthClose", "source_inner_lip_distance", "source_outer_lip_distance", "source_mouth_width", "source_aperture", "old_gnm_aperture", "new_gnm_aperture"]
    for candidate in CANDIDATES:
        fields += [f"{candidate.code}_aperture", f"{candidate.code}_aperture_error", f"{candidate.code}_upper_lip_ratio", f"{candidate.code}_lower_lip_ratio"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for frame in range(frames):
            row = {"frame": frame, "mediapipe_jawOpen": f"{jaw_open[frame]:.6f}", "mediapipe_mouthClose": f"{mouth_close[frame]:.6f}", "source_inner_lip_distance": f"{source_inner[frame]:.6f}", "source_outer_lip_distance": f"{source_outer[frame]:.6f}", "source_mouth_width": f"{source_width[frame]:.6f}", "source_aperture": f"{source_aperture[frame]:.6f}", "old_gnm_aperture": f"{old_aperture[frame]:.6f}", "new_gnm_aperture": f"{current_aperture[frame]:.6f}"}
            for candidate in CANDIDATES:
                code = candidate.code
                row[f"{code}_aperture"] = f"{candidate_aperture[code][frame]:.6f}"
                row[f"{code}_aperture_error"] = f"{candidate_aperture[code][frame] - source_aperture[frame]:.6f}"
                row[f"{code}_upper_lip_ratio"] = f"{candidate_lip[code][frame, 0]:.6f}"
                row[f"{code}_lower_lip_ratio"] = f"{candidate_lip[code][frame, 1]:.6f}"
            writer.writerow(row)


def _write_videos(out_dir: Path, sample_id: str, gnm: Any, renderers: tuple[Any, list[Any]], identity: np.ndarray, rotation: np.ndarray, translation: np.ndarray, meta: dict[str, Any], source_video: Path | None, fps: float, size: int, frames: int, source_aperture: np.ndarray, jaw_open: np.ndarray, current_aperture: np.ndarray, candidate_aperture: dict[str, np.ndarray], current: np.ndarray, candidate_expressions: dict[str, np.ndarray]) -> None:
    import cv2

    full_path = out_dir / "aperture_sweep_comparison.mp4"
    mouth_path = out_dir / "aperture_sweep_mouth_closeup.mp4"
    full_writer = cv2.VideoWriter(str(full_path), getattr(cv2, "VideoWriter_fourcc")(*"mp4v"), fps, (size * 5, size))
    mouth_writer = cv2.VideoWriter(str(mouth_path), getattr(cv2, "VideoWriter_fourcc")(*"mp4v"), fps, (size * 5, size // 2))
    cap = cv2.VideoCapture(str(source_video)) if source_video and source_video.exists() else None
    if not full_writer.isOpened() or not mouth_writer.isOpened():
        raise RuntimeError("Could not open mouth aperture sweep video writer")
    visible = CANDIDATES[:4]
    for frame in range(frames):
        if cap is not None:
            ok, human = cap.read()
            original = _panel(human, size) if ok else np.zeros((size, size, 3), dtype=np.uint8)
        else:
            original = np.zeros((size, size, 3), dtype=np.uint8)
        pose = rotation[min(frame, len(rotation) - 1)]
        offset = translation[min(frame, len(translation) - 1)]
        panels = [original]
        titles = ["ORIGINAL HUMAN"]
        for candidate in visible:
            expr = current[frame] if candidate.code == "M0" else candidate_expressions[candidate.code][frame]
            panels.append(_render(gnm, renderers, identity, expr, pose, offset))
            titles.append(f"{candidate.code} aw={candidate.aperture_weight} jw={candidate.jaw_weight} reg={candidate.lower_regularization}")
        for panel, title, candidate in zip(panels, titles, (None, *visible), strict=True):
            pred = current_aperture[frame] if candidate is None or candidate.code == "M0" else candidate_aperture[candidate.code][frame]
            _put_label(panel, [title, f"frame={frame} jawOpen={jaw_open[frame]:.2f}", f"srcA={source_aperture[frame]:.3f} predA={pred:.3f} err={pred-source_aperture[frame]:+.3f}"])
        full_writer.write(np.hstack(panels))
        crops = [cv2.resize(_crop_mouth(panel), (size, size // 2), interpolation=cv2.INTER_LINEAR) for panel in panels]
        for crop, title in zip(crops, titles, strict=True):
            _put_label(crop, [title, f"frame={frame}"])
        mouth_writer.write(np.hstack(crops))
    if cap is not None:
        cap.release()
    full_writer.release()
    mouth_writer.release()
    _mux_source_audio(full_path, source_video)
    _mux_source_audio(mouth_path, source_video)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render mouth-aperture recovery sweep videos and metrics.")
    parser.add_argument("--sample", action="append", required=True)
    parser.add_argument("--size", type=int, default=360)
    args = parser.parse_args()
    for sample in args.sample:
        print(render_sample(sample, size=args.size))


if __name__ == "__main__":
    main()
