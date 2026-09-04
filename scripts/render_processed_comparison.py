#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import argparse
import json
import sys
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
from voice_face.fitting.expression_processing import blink_signals, blendshape  # noqa: E402
from voice_face.gnm.load import load_gnm  # noqa: E402

DEFAULT_PROCESSED_ROOT = ROOT / "data" / "processed" / "gnm" / "sequences_processed"
DEFAULT_OUTPUT_ROOT = ROOT / "outputs" / "processed_comparisons"


def _processed_path(sample: str, root: Path) -> Path:
    path = root / f"{Path(sample).stem}.npz"
    if path.exists():
        return path
    raise FileNotFoundError(path)


def _expr(data: Any, key: str) -> np.ndarray:
    if key in data.files:
        return data[key].astype(np.float32, copy=False)
    return data["expression"].astype(np.float32, copy=False)


def _crop_mouth(panel: np.ndarray) -> np.ndarray:
    h, w = panel.shape[:2]
    y0, y1 = int(h * 0.42), int(h * 0.82)
    x0, x1 = int(w * 0.20), int(w * 0.80)
    return panel[y0:y1, x0:x1]


def _render_panel(gnm: Any, renderers: tuple[Any, list[Any]], identity: np.ndarray, expression: np.ndarray, rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    vertices = gnm(identity, expression, rotation, translation)
    image = _render_lower_face_material(vertices, renderers[0], renderers[1])
    import cv2

    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


def render_comparison(sample: str, processed_root: Path, output_root: Path, *, size: int) -> tuple[Path, Path]:
    add_vendor_paths()
    import cv2
    from webcam_puppet.renderer import Camera

    old_path = _sample_path(sample)
    new_path = _processed_path(old_path.stem, processed_root)
    with np.load(old_path, allow_pickle=False) as old_data, np.load(new_path, allow_pickle=False) as new_data:
        old_expression = _expr(old_data, "expression")
        new_raw = _expr(new_data, "expression_neutral_relative")
        new_processed = _expr(new_data, "expression_processed")
        identity = old_data["identity"].astype(np.float32, copy=False)
        rotation = _rotation(old_data).astype(np.float32, copy=False)
        translation = old_data["translation"].astype(np.float32, copy=False)
        meta = _metadata(old_data, old_path)
        source_video = _source_video(meta)
        fps = float(meta.get("fps") or 30.0)
        jaw_open = blendshape(old_data, "jawOpen")
        mouth_close = blendshape(old_data, "mouthClose")
        blink_left, blink_right = blink_signals(old_data)

    gnm = load_gnm()
    lower_indices = lower_face_indices(gnm)
    camera = Camera.fit_to_mesh(gnm.template_vertex_positions, (size, size))
    renderers = _lower_face_material_renderers(gnm, camera)
    cap = cv2.VideoCapture(str(source_video)) if source_video and source_video.exists() else None
    out_dir = output_root / old_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    full_path = out_dir / "old_new_comparison.mp4"
    mouth_path = out_dir / "mouth_closeup_comparison.mp4"
    full_writer = cv2.VideoWriter(str(full_path), getattr(cv2, "VideoWriter_fourcc")(*"mp4v"), fps, (size * 4, size))
    mouth_writer = cv2.VideoWriter(str(mouth_path), getattr(cv2, "VideoWriter_fourcc")(*"mp4v"), fps, (size * 3, size // 2))
    if not full_writer.isOpened() or not mouth_writer.isOpened():
        raise RuntimeError("Could not open comparison video writer")
    frames = min(len(old_expression), len(new_raw), len(new_processed), len(rotation), len(translation))
    for frame in range(frames):
        if cap is not None:
            ok, human = cap.read()
            original = _panel(human, size) if ok else np.zeros((size, size, 3), dtype=np.uint8)
        else:
            original = np.zeros((size, size, 3), dtype=np.uint8)
        pose = rotation[min(frame, len(rotation) - 1)]
        offset = translation[min(frame, len(translation) - 1)]
        old_panel = _render_panel(gnm, renderers, identity, old_expression[frame], pose, offset)
        raw_panel = _render_panel(gnm, renderers, identity, new_raw[frame], pose, offset)
        processed_panel = _render_panel(gnm, renderers, identity, new_processed[frame], pose, offset)
        lower_max = float(np.max(np.abs(np.nan_to_num(new_processed[frame, lower_indices], nan=0.0))))
        common = [
            f"emotion={meta.get('emotion', 'unknown')} intensity={meta.get('intensity', 'unknown')}",
            f"frame={frame} jawOpen={jaw_open[min(frame, len(jaw_open)-1)]:.2f} mouthClose={mouth_close[min(frame, len(mouth_close)-1)]:.2f}",
            f"blinkL={blink_left[min(frame, len(blink_left)-1)]:.2f} blinkR={blink_right[min(frame, len(blink_right)-1)]:.2f} maxLower={lower_max:.2f}",
        ]
        for panel, title in ((original, "ORIGINAL HUMAN"), (old_panel, "OLD FIT"), (raw_panel, "NEW RAW FIT"), (processed_panel, "NEW PROCESSED FIT")):
            _put_label(panel, [title, *common])
        full_writer.write(np.hstack([original, old_panel, raw_panel, processed_panel]))

        crops = [_crop_mouth(original), _crop_mouth(old_panel), _crop_mouth(processed_panel)]
        crops = [cv2.resize(crop, (size, size // 2), interpolation=cv2.INTER_LINEAR) for crop in crops]
        for panel, title in zip(crops, ("Original mouth", "Old GNM", "New GNM"), strict=True):
            _put_label(panel, [title, f"frame={frame}"])
        mouth_writer.write(np.hstack(crops))
    if cap is not None:
        cap.release()
    full_writer.release()
    mouth_writer.release()
    _mux_source_audio(full_path, source_video)
    _mux_source_audio(mouth_path, source_video)
    return full_path, mouth_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render OLD/NEW processed GNM comparison videos.")
    parser.add_argument("--sample", action="append", required=True)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--size", type=int, default=360)
    args = parser.parse_args()
    for sample in args.sample:
        print(*render_comparison(sample, args.processed_dir, args.out_dir, size=args.size), sep="\n")


if __name__ == "__main__":
    main()
