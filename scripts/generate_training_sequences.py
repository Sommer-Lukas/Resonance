#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from voice_face.data.mead import MeadSample, read_index
from voice_face.training_records import build_training_sequence, save_training_sequence, write_failure_report
from voice_face.audio_mouth import AudioRegressionMouthDriver


def _transcript(sample: MeadSample, transcript_dir: Path | None) -> str:
    if transcript_dir is None:
        return ""
    for name in (f"{sample.sample_id}.txt", f"{sample.utterance_id}.txt"):
        path = transcript_dir / name
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synchronized ML TrainingSequence records from fitted MEAD GNM sequences.")
    parser.add_argument("--index", type=Path, default=ROOT / "outputs" / "voice_face" / "mead_index.csv")
    parser.add_argument("--fit-dir", type=Path, default=ROOT / "data" / "processed" / "gnm" / "sequences")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data" / "processed" / "training_sequences")
    parser.add_argument("--failure-report", type=Path, default=ROOT / "outputs" / "voice_face" / "training_sequence_failures.json")
    parser.add_argument("--transcript-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--mouth-model", type=Path, default=None)
    parser.add_argument("--mouth-cache-dir", type=Path, default=ROOT / "outputs" / "cache" / "wavlm_base_plus")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    failures: list[dict[str, str]] = []
    written = 0
    for sample in read_index(args.index)[: args.limit]:
        fit_path = args.fit_dir / f"{sample.sample_id}.npz"
        out_path = args.out_dir / f"{sample.sample_id}.npz"
        if not fit_path.exists():
            failures.append({"sample_id": sample.sample_id, "stage": "fit", "error": f"missing {fit_path}"})
            continue
        if out_path.exists() and not args.force:
            print(out_path)
            written += 1
            continue
        try:
            driver = AudioRegressionMouthDriver(args.mouth_model, cache_dir=args.mouth_cache_dir) if args.mouth_model else None
            sequence = build_training_sequence(fit_path, sample, mouth_driver=driver, transcript=_transcript(sample, args.transcript_dir))
            save_training_sequence(sequence, out_path, force=args.force)
            dims = {"beta_target": list(sequence.beta_target.shape), "mouth": list(sequence.mouth.features.shape), "prosody": list(sequence.prosody.shape), "valid_frames": int(sequence.valid.sum())}
            print(f"{out_path} {json.dumps(dims, sort_keys=True)}")
            written += 1
        except Exception as exc:
            failures.append({"sample_id": sample.sample_id, "stage": "training_sequence", "error": str(exc)})
    write_failure_report(args.failure_report, failures)
    print(f"training_sequences={written} failures={len(failures)} report={args.failure_report}")


if __name__ == "__main__":
    main()
