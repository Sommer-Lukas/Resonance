#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
"""Render a controlled lower-face GNM expression ablation sweep.

Lower-face coefficients are resolved at runtime from the installed GNM model via
``gnm.shape.gnm_utils.expression_regions_indices(gnm)[LOWER_FACE_REGION]`` after
``add_vendor_paths()``. The script never refits or writes fitted sequences; it
copies the loaded expression array and changes only those resolved coefficients.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from voice_face.bootstrap import add_vendor_paths
from voice_face.gnm.load import load_gnm
from voice_face.visualization.diagnostics import _panel

LOWER_FACE_REGION = "lower_face_region"
SEQUENCE_ROOT = ROOT / "data" / "processed" / "gnm" / "sequences"
OUTPUT_ROOT = ROOT / "outputs" / "lower_face_sweep"
REPRESENTATIVE_SAMPLES = (
    "video_0__front__neutral__level_1__030",
    "video_1__front__happy__level_3__017",
    "video_0__front__angry__level_3__013",
    "video_2__front__sad__level_3__026",
    "video_0__front__disgusted__level_3__008",
)


@dataclass(frozen=True)
class Variant:
    code: str
    filename: str
    scale: float | None
    soft_clamp: float | None
    pre_scale: float = 1.0

    @property
    def label(self) -> str:
        if self.soft_clamp is None:
            return f"{self.code} scale={self.scale:.2f} soft=none"
        if self.pre_scale == 1.0:
            return f"{self.code} scale=1.00 soft={self.soft_clamp:.1f}"
        return f"{self.code} scale={self.pre_scale:.2f} soft={self.soft_clamp:.1f}"


class _MaterialGnm(Protocol):
    template_vertex_positions: np.ndarray
    triangles: np.ndarray
    vertex_group_names: Sequence[str]

    def vertex_group(self, name: str) -> np.ndarray: ...


class _Renderer(Protocol):
    def render(self, vertices: np.ndarray) -> np.ndarray: ...


VARIANTS = (
    Variant("V0", "V0_original.mp4", 1.0, None),
    Variant("V1", "V1_scale_085.mp4", 0.85, None),
    Variant("V2", "V2_scale_070.mp4", 0.70, None),
    Variant("V3", "V3_scale_055.mp4", 0.55, None),
    Variant("V4", "V4_scale_040.mp4", 0.40, None),
    Variant("V5", "V5_soft_300.mp4", None, 3.0),
    Variant("V6", "V6_soft_400.mp4", None, 4.0),
    Variant("V6A", "V6A_soft_450.mp4", None, 4.5),
    Variant("V6B", "V6B_soft_500.mp4", None, 5.0),
    Variant("V6C", "V6C_soft_600.mp4", None, 6.0),
    Variant("V7", "V7_scale075_soft350.mp4", None, 3.5, pre_scale=0.75),
)

DIAGNOSTIC_BACKGROUND = (0.0, 0.0, 0.0)
DIAGNOSTIC_SKIN_COLOR = (0.86, 0.72, 0.64)
DIAGNOSTIC_MATERIALS: tuple[tuple[str, tuple[str, ...], tuple[float, float, float]], ...] = ()


def lower_face_indices(gnm: Any) -> np.ndarray:
    add_vendor_paths()
    from gnm.shape import gnm_utils

    regions = gnm_utils.expression_regions_indices(gnm)
    if LOWER_FACE_REGION not in regions:
        raise KeyError(f"GNM expression region missing: {LOWER_FACE_REGION}")
    return np.asarray(regions[LOWER_FACE_REGION], dtype=np.int64)


def apply_variant(expression: np.ndarray, indices: np.ndarray, variant: Variant) -> np.ndarray:
    transformed = np.array(expression, copy=True)
    lower = expression[:, indices].astype(np.float32, copy=True)
    if variant.soft_clamp is None:
        if variant.scale is None:
            raise ValueError(f"{variant.code} needs a scale")
        lower *= float(variant.scale)
    else:
        x = lower * float(variant.pre_scale)
        lower = float(variant.soft_clamp) * np.tanh(x / float(variant.soft_clamp))
    transformed[:, indices] = lower
    return transformed


def changed_columns(original: np.ndarray, transformed: np.ndarray) -> np.ndarray:
    return np.flatnonzero(np.any(~np.isclose(original, transformed, equal_nan=True), axis=0))


def _triangle_subset_for_groups(gnm: _MaterialGnm, group_names: Sequence[str]) -> np.ndarray:
    available = set(str(name) for name in getattr(gnm, "vertex_group_names", ()))
    mask = np.zeros(len(gnm.template_vertex_positions), dtype=bool)
    for name in group_names:
        if name in available:
            mask |= np.asarray(gnm.vertex_group(name)) > 0
    return np.asarray(gnm.triangles)[np.all(mask[np.asarray(gnm.triangles)], axis=1)]


def _lower_face_material_renderers(gnm: _MaterialGnm, camera: object) -> tuple[_Renderer, list[_Renderer]]:
    from webcam_puppet.renderer import MeshRenderer

    base = MeshRenderer(gnm.triangles, camera, base_color=DIAGNOSTIC_SKIN_COLOR)
    overlays = []
    for _, group_names, color in DIAGNOSTIC_MATERIALS:
        triangles = _triangle_subset_for_groups(gnm, group_names)
        if len(triangles):
            overlays.append(MeshRenderer(triangles, camera, background=DIAGNOSTIC_BACKGROUND, base_color=color))
    return base, overlays


def _render_lower_face_material(vertices: np.ndarray, base_renderer: _Renderer, overlay_renderers: Sequence[_Renderer]) -> np.ndarray:
    image = base_renderer.render(vertices)
    for renderer in overlay_renderers:
        overlay = renderer.render(vertices)
        pixels = np.any(overlay != 0, axis=-1)
        image[pixels] = overlay[pixels]
    return image


def _stats(values: np.ndarray) -> dict[str, float]:
    abs_values = np.abs(np.nan_to_num(values, nan=0.0))
    return {
        "max_abs": float(np.max(abs_values)),
        "mean_abs": float(np.mean(abs_values)),
        "p95_abs": float(np.percentile(abs_values, 95)),
        "p99_abs": float(np.percentile(abs_values, 99)),
    }


def _sample_path(sample_id: str) -> Path:
    path = Path(sample_id)
    if path.exists():
        return path
    candidate = SEQUENCE_ROOT / f"{sample_id}.npz"
    if candidate.exists():
        return candidate
    matches = sorted(SEQUENCE_ROOT.glob(f"*{sample_id}*.npz"))
    if len(matches) == 1:
        return matches[0]
    raise FileNotFoundError(f"Could not resolve sample: {sample_id}")


def _metadata(data: Any, path: Path) -> dict[str, Any]:
    meta = json.loads(str(data["metadata"])) if "metadata" in data.files else {}
    parts = path.stem.split("__")
    meta.setdefault("sample_id", path.stem)
    if len(parts) > 2:
        meta.setdefault("emotion", parts[2])
    if len(parts) > 3:
        meta.setdefault("intensity", parts[3].replace("level_", ""))
    return meta


def _source_video(meta: dict[str, Any]) -> Path | None:
    source = str(meta.get("source_video", ""))
    if not source:
        return None
    path = Path(source)
    return path if path.is_absolute() else ROOT / path


def _rotation(data: Any) -> np.ndarray:
    return data["rotation"] if "rotation" in data.files else data["rotations"]


def _mux_source_audio(video_path: Path, source_video: Path | None) -> None:
    if source_video is None or not source_video.exists():
        return
    try:
        import imageio_ffmpeg
    except ImportError:
        return
    tmp = video_path.with_suffix(".silent.mp4")
    video_path.rename(tmp)
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-i", str(tmp), "-i", str(source_video), "-map", "0:v:0", "-map", "1:a:0?", "-c:v", "copy", "-c:a", "aac", str(video_path)]
    proc = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        tmp.rename(video_path)
    else:
        tmp.unlink(missing_ok=True)


def _put_label(panel: np.ndarray, lines: Iterable[str]) -> None:
    import cv2

    y = 20
    for line in lines:
        cv2.putText(panel, line, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(panel, line, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (245, 245, 245), 1, cv2.LINE_AA)
        y += 16


def _variant_label(variant: Variant, meta: dict[str, Any], frame: int) -> list[str]:
    return [
        variant.label,
        f"sample={meta['sample_id']}",
        f"emotion={meta.get('emotion', 'unknown')} intensity={meta.get('intensity', 'unknown')}",
        f"frame={frame}",
    ]


def _human_label(meta: dict[str, Any], frame: int) -> list[str]:
    return [
        "ORIGINAL HUMAN",
        f"sample={meta['sample_id']}",
        f"emotion={meta.get('emotion', 'unknown')} intensity={meta.get('intensity', 'unknown')}",
        f"frame={frame}",
    ]


def _render_expression_video(path: Path, expression: np.ndarray, fit: dict[str, np.ndarray], gnm: Any, variant: Variant, meta: dict[str, Any], *, size: int, fps: float, source_video: Path | None) -> None:
    add_vendor_paths()
    import cv2
    from webcam_puppet.renderer import Camera

    path.parent.mkdir(parents=True, exist_ok=True)
    camera = Camera.fit_to_mesh(gnm.template_vertex_positions, (size, size))
    base_renderer, overlay_renderers = _lower_face_material_renderers(gnm, camera)
    writer = cv2.VideoWriter(str(path), getattr(cv2, "VideoWriter_fourcc")(*"mp4v"), fps, (size, size))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {path}")
    for frame in range(len(expression)):
        vertices = gnm(fit["identity"], expression[frame], fit["rotation"][min(frame, len(fit["rotation"]) - 1)], fit["translation"][min(frame, len(fit["translation"]) - 1)])
        image = _render_lower_face_material(vertices, base_renderer, overlay_renderers)
        panel = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        _put_label(panel, _variant_label(variant, meta, frame))
        writer.write(panel)
    writer.release()
    _mux_source_audio(path, source_video)


def _render_grid(path: Path, expressions: dict[str, np.ndarray], fit: dict[str, np.ndarray], gnm: Any, meta: dict[str, Any], *, size: int, fps: float, source_video: Path | None) -> None:
    add_vendor_paths()
    import cv2
    from webcam_puppet.renderer import Camera

    path.parent.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(source_video)) if source_video and source_video.exists() else None
    camera = Camera.fit_to_mesh(gnm.template_vertex_positions, (size, size))
    base_renderer, overlay_renderers = _lower_face_material_renderers(gnm, camera)
    writer = cv2.VideoWriter(str(path), getattr(cv2, "VideoWriter_fourcc")(*"mp4v"), fps, (size * 3, size * 3))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {path}")
    frame_count = len(next(iter(expressions.values())))
    cells_per_row = 3
    for frame in range(frame_count):
        if cap is None:
            original = np.zeros((size, size, 3), dtype=np.uint8)
        else:
            ok, image = cap.read()
            original = _panel(image, size) if ok else np.zeros((size, size, 3), dtype=np.uint8)
        _put_label(original, _human_label(meta, frame))
        panels = [original]
        for variant in VARIANTS:
            expression = expressions[variant.code]
            vertices = gnm(fit["identity"], expression[frame], fit["rotation"][min(frame, len(fit["rotation"]) - 1)], fit["translation"][min(frame, len(fit["translation"]) - 1)])
            image = _render_lower_face_material(vertices, base_renderer, overlay_renderers)
            panel = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            _put_label(panel, _variant_label(variant, meta, frame))
            panels.append(panel)

        rows = []
        for start in range(0, len(panels), cells_per_row):
            row = panels[start : start + cells_per_row]
            if len(row) < cells_per_row:
                row = row + [np.zeros((size, size, 3), dtype=np.uint8) for _ in range(cells_per_row - len(row))]
            rows.append(np.hstack(row))
        writer.write(np.vstack(rows))
    if cap is not None:
        cap.release()
    writer.release()
    _mux_source_audio(path, source_video)


def _write_parameters(path: Path, rows: list[dict[str, Any]], indices: np.ndarray) -> None:
    fieldnames = ["variant", "scale", "soft_clamp", "max_abs", "mean_abs", "p95_abs", "p99_abs"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        handle.write(f"# lower_face_region={LOWER_FACE_REGION}\n")
        handle.write("# lower_face_indices=" + " ".join(str(int(i)) for i in indices) + "\n")
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_selection(path: Path, sample_id: str) -> None:
    def _scale(value: float | None) -> str:
        return "" if value is None else f"{value:.2f}"

    def _soft_clamp(value: float | None) -> str:
        return "" if value is None else f"{value:.1f}"

    rows = "\n".join(
        f"| {variant.code} | {_scale(variant.scale)} | {_soft_clamp(variant.soft_clamp)} |  |  |  |  |"
        for variant in VARIANTS
    )
    path.write_text(
        f"# Lower-Face Sweep Manual Selection: {sample_id}\n\n"
        "No winner is selected here; fill subjective columns during manual review.\n\n"
        "| Variant | Scale | Soft clamp | Visual mouth size | Articulation visibility | Naturalness | Selected |\n"
        "|---|---|---|---|---|---|---|\n"
        f"{rows}\n",
        encoding="utf-8",
    )


def render_sample(sample: str, *, size: int, stats_only: bool) -> Path:
    fit_path = _sample_path(sample)
    out_dir = OUTPUT_ROOT / fit_path.stem
    gnm = load_gnm()
    indices = lower_face_indices(gnm)
    with np.load(fit_path, allow_pickle=False) as data:
        expression = (data["expression_smoothed"] if "expression_smoothed" in data.files else data["expression"]).astype(np.float32, copy=True)
        fit = {"identity": data["identity"].copy(), "rotation": _rotation(data).copy(), "translation": data["translation"].copy()}
        meta = _metadata(data, fit_path)

    meta["sample_id"] = fit_path.stem
    fps = float(meta.get("fps") or 25.0)
    source_video = _source_video(meta)
    transformed: dict[str, np.ndarray] = {}
    rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        variant_expression = apply_variant(expression, indices, variant)
        changed = changed_columns(expression, variant_expression)
        if variant.code != "V0" and not set(changed).issubset(set(int(i) for i in indices)):
            raise RuntimeError(f"{variant.code} changed non-lower-face expression columns")
        transformed[variant.code] = variant_expression
        stats = _stats(variant_expression[:, indices])
        rows.append({"variant": variant.code, "scale": "" if variant.scale is None else f"{variant.scale:.2f}", "soft_clamp": "" if variant.soft_clamp is None else f"{variant.soft_clamp:.1f}", **{k: f"{v:.6f}" for k, v in stats.items()}})

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_parameters(out_dir / "parameters.csv", rows, indices)
    _write_selection(out_dir / "selection.md", fit_path.stem)
    if stats_only:
        return out_dir
    for variant in VARIANTS:
        _render_expression_video(out_dir / variant.filename, transformed[variant.code], fit, gnm, variant, meta, size=size, fps=fps, source_video=source_video)
    _render_grid(out_dir / "comparison_grid.mp4", transformed, fit, gnm, meta, size=size, fps=fps, source_video=source_video)
    return out_dir


def _samples_from_args(args: argparse.Namespace) -> list[str]:
    samples = list(args.sample or [])
    if args.all_representative:
        samples.extend(REPRESENTATIVE_SAMPLES)
    unique = list(dict.fromkeys(samples))
    if not unique:
        raise SystemExit("Pass --sample <sample_id> or --all-representative")
    return unique


def main() -> None:
    parser = argparse.ArgumentParser(description="Render V0..V7 lower-face-only GNM expression ablation videos.")
    parser.add_argument("--sample", action="append", help="Sample id or fit path. May be repeated.")
    parser.add_argument("--all-representative", action="store_true", help="Render the built-in neutral/happy/angry/sad/extreme set.")
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--stats-only", "--dry-run", dest="stats_only", action="store_true", help="Write parameters.csv and selection.md without rendering videos.")
    args = parser.parse_args()
    for sample in _samples_from_args(args):
        out_dir = render_sample(sample, size=args.size, stats_only=args.stats_only)
        print(out_dir)


if __name__ == "__main__":
    main()
