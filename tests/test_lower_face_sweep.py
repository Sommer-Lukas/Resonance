# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("render_lower_face_sweep", ROOT / "scripts" / "render_lower_face_sweep.py")
assert SPEC and SPEC.loader
sweep = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sweep
SPEC.loader.exec_module(sweep)


def test_apply_variant_changes_only_lower_face_indices():
    expression = np.arange(12, dtype=np.float32).reshape(2, 6)
    indices = np.array([2, 4])

    transformed = sweep.apply_variant(expression, indices, sweep.VARIANTS[2])

    assert np.allclose(transformed[:, indices], expression[:, indices] * 0.70)
    assert set(sweep.changed_columns(expression, transformed)) == {2, 4}


def test_soft_variant_matches_requested_formula():
    expression = np.array([[0.0, 2.0, -4.0]], dtype=np.float32)
    indices = np.array([1, 2])

    variant = next(variant for variant in sweep.VARIANTS if variant.code == "V7")

    transformed = sweep.apply_variant(expression, indices, variant)

    expected = 3.5 * np.tanh((0.75 * expression[:, indices]) / 3.5)
    assert np.allclose(transformed[:, indices], expected)
    assert np.allclose(transformed[:, [0]], expression[:, [0]])


def test_write_selection_uses_requested_table_schema(tmp_path: Path):
    output: Path = tmp_path / "selection.md"

    sweep._write_selection(output, "sample_123")

    text = output.read_text(encoding="utf-8")
    assert "| Variant | Scale | Soft clamp | Visual mouth size | Articulation visibility | Naturalness | Selected |" in text
    assert "| V0 | 1.00 |  |  |  |  |  |" in text
    assert "| V1 | 0.85 |  |  |  |  |  |" in text
    assert "| V5 |  | 3.0 |  |  |  |  |" in text
    assert "| V7 |  | 3.5 |  |  |  |  |" in text
    assert "File" not in text
    assert "No winner is selected here" in text


def test_triangle_subset_uses_available_material_groups():
    class FakeGnm:
        template_vertex_positions: np.ndarray = np.zeros((5, 3), dtype=np.float32)
        triangles: np.ndarray = np.array([[0, 1, 2], [2, 3, 4], [0, 3, 4]], dtype=np.int32)
        vertex_group_names: list[str] = ["skin", "upper_teeth_and_gums"]

        def vertex_group(self, name: str) -> np.ndarray:
            groups = {
                "upper_teeth_and_gums": np.array([0, 0, 1, 1, 1], dtype=np.float32),
            }
            return groups[name]

    triangles = sweep._triangle_subset_for_groups(FakeGnm(), ("teeth", "upper_teeth_and_gums", "lower_teeth_and_gums"))

    assert triangles.tolist() == [[2, 3, 4]]


def test_render_lower_face_material_composites_non_background_pixels():
    class FakeRenderer:
        image: np.ndarray

        def __init__(self, image: np.ndarray):
            self.image = image

        def render(self, _vertices: np.ndarray) -> np.ndarray:
            return self.image.copy()

    base = np.full((2, 2, 3), 10, dtype=np.uint8)
    overlay = np.zeros((2, 2, 3), dtype=np.uint8)
    overlay[0, 1] = [200, 20, 30]

    image = sweep._render_lower_face_material(np.zeros((1, 3)), FakeRenderer(base), [FakeRenderer(overlay)])

    assert image.tolist() == [[[10, 10, 10], [200, 20, 30]], [[10, 10, 10], [10, 10, 10]]]
