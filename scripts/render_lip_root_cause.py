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
)
from voice_face.bootstrap import add_vendor_paths  # noqa: E402
from voice_face.gnm.load import load_gnm  # noqa: E402

OUTPUT_ROOT = ROOT / "outputs" / "lip_root_cause"
DEFAULT_SAMPLE = "video_0__front__neutral__level_1__030"
DEFAULT_PROCESSED_ROOT = ROOT / "data" / "processed" / "gnm" / "sequences_processed"


def _expression(data: Any) -> np.ndarray:
    return data["expression_smoothed"] if "expression_smoothed" in data.files else data["expression"]


def _processed_expression(sample: str, processed_root: Path) -> np.ndarray | None:
    path = processed_root / f"{Path(sample).stem}.npz"
    if not path.exists():
        return None
    with np.load(path, allow_pickle=False) as data:
        return data["expression_processed"].astype(np.float32, copy=True)


def render_diagnostic(sample: str, *, size: int, processed_root: Path) -> Path:
    add_vendor_paths()
    import cv2
    from webcam_puppet.renderer import Camera

    fit_path = _sample_path(sample)
    with np.load(fit_path, allow_pickle=False) as data:
        identity = data["identity"].astype(np.float32, copy=True)
        expression = _expression(data).astype(np.float32, copy=False)
        rotation = _rotation(data).astype(np.float32, copy=False)
        translation = data["translation"].astype(np.float32, copy=False)
        meta = _metadata(data, fit_path)

    meta["sample_id"] = fit_path.stem
    fps = float(meta.get("fps") or 30.0)
    gnm = load_gnm()
    camera = Camera.fit_to_mesh(gnm.template_vertex_positions, (size, size))
    base_renderer, overlay_renderers = _lower_face_material_renderers(gnm, camera)

    zero_identity = np.zeros_like(identity)
    zero_expression = np.zeros(expression.shape[1], dtype=np.float32)
    new_expression = _processed_expression(fit_path.stem, processed_root)

    source_video = _source_video(meta)
    cap = cv2.VideoCapture(str(source_video)) if source_video and source_video.exists() else None
    out_dir = OUTPUT_ROOT / fit_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    video_path = out_dir / "lip_root_cause.mp4"
    columns = 5 if new_expression is not None else 4
    writer = cv2.VideoWriter(str(video_path), getattr(cv2, "VideoWriter_fourcc")(*"mp4v"), fps, (size * columns, size))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {video_path}")

    for frame in range(len(expression)):
        pose = rotation[min(frame, len(rotation) - 1)]
        offset = translation[min(frame, len(translation) - 1)]
        cases = [
            ("A: alpha=0 beta=0", zero_identity, zero_expression),
            ("B: fitted alpha beta=0", identity, zero_expression),
            ("C_old: fitted alpha old beta", identity, expression[frame]),
        ]
        if new_expression is not None:
            cases.append(("C_new: fitted alpha processed", identity, new_expression[frame]))

        if cap is not None:
            ok, human_frame = cap.read()
            original = _panel(human_frame, size) if ok else np.zeros((size, size, 3), dtype=np.uint8)
        else:
            original = np.zeros((size, size, 3), dtype=np.uint8)
        _put_label(original, ["ORIGINAL HUMAN", f"sample={fit_path.stem}", f"frame={frame}"])

        panels = [original]
        for label, case_identity, case_expression in cases:
            vertices = gnm(case_identity, case_expression, pose, offset)
            image = _render_lower_face_material(vertices, base_renderer, overlay_renderers)
            panel = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            _put_label(panel, [label, f"sample={fit_path.stem}", f"frame={frame}"])
            panels.append(panel)
        writer.write(np.hstack(panels))

    if cap is not None:
        cap.release()
    writer.release()
    _mux_source_audio(video_path, source_video)
    (out_dir / "lip_root_cause.json").write_text(
        json.dumps(
            {
                "sample": fit_path.stem,
                "source_video": str(source_video) if source_video else None,
                "frames": int(len(expression)),
                "fps": fps,
                "cases": ["ORIGINAL HUMAN", "A: alpha=0 beta=0", "B: fitted alpha beta=0", "C_old: fitted alpha old beta", *( ["C_new: fitted alpha processed"] if new_expression is not None else [] )],
                "note": "Render-only diagnostic; fitted sequence is not modified.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return video_path


def render_frame(sample: str, *, frame: int, size: int) -> Path:
    add_vendor_paths()
    import cv2
    from webcam_puppet.renderer import Camera

    fit_path = _sample_path(sample)
    with np.load(fit_path, allow_pickle=False) as data:
        identity = data["identity"].astype(np.float32, copy=True)
        expression = _expression(data).astype(np.float32, copy=False)
        rotation = _rotation(data).astype(np.float32, copy=False)
        translation = data["translation"].astype(np.float32, copy=False)
        meta = _metadata(data, fit_path)

    frame = max(0, min(int(frame), len(expression) - 1))
    meta["sample_id"] = fit_path.stem
    gnm = load_gnm()
    camera = Camera.fit_to_mesh(gnm.template_vertex_positions, (size, size))
    base_renderer, overlay_renderers = _lower_face_material_renderers(gnm, camera)
    zero_identity = np.zeros_like(identity)
    zero_expression = np.zeros(expression.shape[1], dtype=np.float32)
    pose = rotation[min(frame, len(rotation) - 1)]
    offset = translation[min(frame, len(translation) - 1)]
    cases = (
        ("A: alpha=0 beta=0", zero_identity, zero_expression),
        ("B: fitted alpha beta=0", identity, zero_expression),
        ("C: fitted alpha beta=neutral", identity, expression[frame]),
    )

    source_video = _source_video(meta)
    if source_video and source_video.exists():
        cap = cv2.VideoCapture(str(source_video))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ok, human_frame = cap.read()
        cap.release()
        original = _panel(human_frame, size) if ok else np.zeros((size, size, 3), dtype=np.uint8)
    else:
        original = np.zeros((size, size, 3), dtype=np.uint8)
    _put_label(original, ["ORIGINAL HUMAN", f"sample={fit_path.stem}", f"frame={frame}"])

    panels = [original]
    for label, case_identity, case_expression in cases:
        vertices = gnm(case_identity, case_expression, pose, offset)
        image = _render_lower_face_material(vertices, base_renderer, overlay_renderers)
        panel = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        _put_label(panel, [label, f"sample={fit_path.stem}", f"frame={frame}"])
        panels.append(panel)

    out_dir = OUTPUT_ROOT / fit_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    image_path = out_dir / f"lip_root_cause_frame_{frame:04d}.jpg"
    cv2.imwrite(str(image_path), np.hstack(panels))
    (out_dir / f"lip_root_cause_frame_{frame:04d}.json").write_text(
        json.dumps(
            {
                "sample": fit_path.stem,
                "frame": frame,
                "source_video": str(source_video) if source_video else None,
                "cases": ["ORIGINAL HUMAN", *[case[0] for case in cases]],
                "note": "Render-only diagnostic; fitted sequence is not modified.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return image_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render D/A/B/C lip-thickness root-cause diagnostic.")
    parser.add_argument("--sample", default=DEFAULT_SAMPLE, help="Neutral fitted sample id or .npz path.")
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_ROOT)
    parser.add_argument("--frame", type=int, help="Also write a single JPG for this frame.")
    parser.add_argument("--size", type=int, default=360)
    args = parser.parse_args()
    print(render_diagnostic(args.sample, size=args.size, processed_root=args.processed_dir))
    if args.frame is not None:
        print(render_frame(args.sample, frame=args.frame, size=args.size))


if __name__ == "__main__":
    main()
