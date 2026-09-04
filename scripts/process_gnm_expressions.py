#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.render_lower_face_sweep import lower_face_indices  # noqa: E402
from voice_face.fitting.expression_processing import (  # noqa: E402
    ExpressionProcessingConfig,
    actor_id_from_sample,
    blink_signals,
    estimate_neutral_expression,
    expression_array,
    load_metadata,
    lower_face_stats,
    process_expression,
)
from voice_face.gnm.load import load_gnm  # noqa: E402

SEQUENCE_ROOT = ROOT / "data" / "processed" / "gnm" / "sequences"
DEFAULT_OUT_ROOT = ROOT / "data" / "processed" / "gnm" / "sequences_processed"
DEFAULT_NEUTRAL_ROOT = ROOT / "data" / "processed" / "gnm" / "neutral_expression"


def _resolve_sample(sample: str) -> Path:
    path = Path(sample)
    if path.exists():
        return path
    candidate = SEQUENCE_ROOT / f"{sample}.npz"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(sample)


def _neutral_paths(actor: str) -> list[Path]:
    return sorted(SEQUENCE_ROOT.glob(f"{actor}__front__neutral__level_1__*.npz"))


def _save_neutral(actor: str, neutral: np.ndarray, metadata: dict[str, object], output_root: Path) -> Path:
    output = output_root / f"{actor}.npz"
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, neutral_expression=neutral, metadata=json.dumps(metadata, sort_keys=True))
    return output


def process_sample(path: Path, neutral_path: Path, output_root: Path, lower_indices: np.ndarray, config: ExpressionProcessingConfig) -> Path:
    with np.load(path, allow_pickle=False) as data, np.load(neutral_path, allow_pickle=False) as neutral_data:
        old_expression = expression_array(data).astype(np.float32, copy=False)
        neutral = neutral_data["neutral_expression"].astype(np.float32)
        valid = np.asarray(data["valid"] if "valid" in data.files else np.ones(len(old_expression), dtype=bool), dtype=bool)
        raw_delta, processed = process_expression(old_expression, valid, neutral, lower_indices, config)
        blink_left, blink_right = blink_signals(data)
        meta = load_metadata(data)
        meta["processing_mode"] = "neutral_relative_v1"
        meta["neutral_expression_path"] = str(neutral_path.resolve())
        meta["expression_semantics"] = {
            "expression_absolute_old": "absolute beta from old fit",
            "expression_neutral_relative": "old absolute beta minus actor neutral beta",
            "expression_processed": "neutral-relative beta after adaptive lower-face filtering and soft safety bound",
            "expression": "same as expression_processed for downstream compatibility",
        }
        meta["lower_face_indices"] = [int(i) for i in lower_indices]
        meta["old_lower_face_stats"] = lower_face_stats(old_expression, lower_indices)
        meta["new_lower_face_stats"] = lower_face_stats(processed, lower_indices)
        output = output_root / path.name
        output.parent.mkdir(parents=True, exist_ok=True)
        keys = {key: data[key] for key in data.files if key != "metadata"}
        keys.update(
            expression_absolute_old=old_expression,
            expression_neutral_relative=raw_delta,
            expression_processed=processed,
            expression_smoothed=processed,
            expression=processed,
            neutral_expression=neutral,
            blink_left=blink_left,
            blink_right=blink_right,
            metadata=json.dumps(meta, sort_keys=True),
        )
        np.savez_compressed(output, **keys)
        return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Create non-overwriting neutral-relative GNM expression fits.")
    parser.add_argument("--sample", action="append", required=True, help="Sample id or old fit path. May be repeated.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--neutral-dir", type=Path, default=DEFAULT_NEUTRAL_ROOT)
    parser.add_argument("--lower-soft-bound", type=float, default=5.0)
    args = parser.parse_args()

    config = ExpressionProcessingConfig(lower_soft_bound=args.lower_soft_bound)
    gnm = load_gnm()
    lower_indices = lower_face_indices(gnm)
    neutral_by_actor: dict[str, Path] = {}
    for sample in args.sample:
        path = _resolve_sample(sample)
        actor = actor_id_from_sample(path.stem)
        if actor not in neutral_by_actor:
            neutral, neutral_meta = estimate_neutral_expression(_neutral_paths(actor), config)
            neutral_meta["actor_id"] = actor
            neutral_by_actor[actor] = _save_neutral(actor, neutral, neutral_meta, args.neutral_dir)
            print(neutral_by_actor[actor])
        print(process_sample(path, neutral_by_actor[actor], args.out_dir, lower_indices, config))


if __name__ == "__main__":
    main()
