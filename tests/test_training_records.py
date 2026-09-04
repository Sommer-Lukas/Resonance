import csv
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

from voice_face.alignment import nearest_valid, resample_to_timestamps, target_fps
from voice_face.data.mead import MeadSample
from voice_face.prosody import prosody_from_wav
from voice_face.training_records import build_training_sequence, load_training_sequence, save_training_sequence


def _write_wav(path: Path, hz: float = 200.0, seconds: float = 0.2, sample_rate: int = 16000) -> None:
    samples = (0.5 * np.sin(2.0 * math.pi * hz * np.arange(int(seconds * sample_rate)) / sample_rate)).astype(np.float32)
    pcm = np.clip(samples * 32767.0, -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def _write_fit(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamps = np.asarray([0.0, 0.04, 0.08, 0.12], dtype=np.float32)
    blendshapes = np.zeros((4, 52), dtype=np.float32)
    blendshapes[:, 25] = [0.0, 0.4, 0.8, 0.2]
    blendshapes[:, 19] = [0.1, 0.2, 0.3, 0.4]
    blendshapes[:, 44] = 0.2
    blendshapes[:, 45] = 0.4
    np.savez_compressed(
        path,
        identity=np.zeros(2, dtype=np.float32),
        expression_raw=np.ones((4, 3), dtype=np.float32),
        expression_smoothed=np.ones((4, 3), dtype=np.float32) * 2,
        expression=np.ones((4, 3), dtype=np.float32) * 2,
        rotation=np.zeros((4, 1, 3), dtype=np.float32),
        rotations=np.zeros((4, 1, 3), dtype=np.float32),
        translation=np.zeros((4, 3), dtype=np.float32),
        fit_error=np.zeros(4, dtype=np.float32),
        landmark_rmse=np.zeros(4, dtype=np.float32),
        valid=np.array([True, True, False, True]),
        timestamps=timestamps,
        timestamps_ms=(timestamps * 1000).astype(np.int64),
        blendshapes=blendshapes,
        metadata=json.dumps({"source_video": "", "fps": 25.0}),
    )


def test_resampling_and_valid_alignment():
    src_t = np.asarray([0.0, 0.1], dtype=np.float32)
    values = np.asarray([[0.0, 1.0], [10.0, 11.0]], dtype=np.float32)
    dst_t = np.asarray([0.0, 0.05, 0.1], dtype=np.float32)
    assert np.allclose(resample_to_timestamps(src_t, values, dst_t), [[0, 1], [5, 6], [10, 11]])
    assert nearest_valid(src_t, np.asarray([True, False]), dst_t).tolist() == [True, True, False]
    assert round(target_fps(dst_t)) == 20


def test_prosody_from_wav_tracks_voiced_synthetic_audio(tmp_path):
    wav = tmp_path / "tone.wav"
    _write_wav(wav)
    prosody = prosody_from_wav(wav, np.asarray([0.04, 0.08, 0.12], dtype=np.float32))
    assert prosody.shape == (3, 3)
    assert np.all(prosody[:, 1] > 0.1)
    assert np.all(prosody[:, 2] == 1.0)
    assert np.all((prosody[:, 0] > 150.0) & (prosody[:, 0] < 260.0))


def test_training_sequence_serialization_reuses_fit_metadata(tmp_path):
    fit = tmp_path / "fits" / "actor__front__happy__level_2__001.npz"
    wav = tmp_path / "001.wav"
    _write_fit(fit)
    _write_wav(wav)
    sample = MeadSample("actor__front__happy__level_2__001", "actor", "happy", 2, "front", tmp_path / "001.mp4", wav, "001", 25.0, 4, 0.16)
    seq = build_training_sequence(fit, sample, transcript="hello")
    out = save_training_sequence(seq, tmp_path / "training" / "sample.npz")
    loaded = load_training_sequence(out)
    assert loaded.beta_target.shape == (4, 3)
    assert loaded.mouth.features.shape == (4, 3)
    assert loaded.prosody.shape == (4, 3)
    assert loaded.emotion == "happy"
    assert loaded.intensity == 2
    assert loaded.actor_id == "actor"
    assert loaded.sample_id == sample.sample_id
    assert loaded.transcript == "hello"
    assert loaded.valid.tolist() == [True, True, False, True]


def test_generate_training_sequences_cli_reports_missing_fit_and_writes_record(tmp_path):
    fit_dir = tmp_path / "fits"
    out_dir = tmp_path / "records"
    wav = tmp_path / "001.wav"
    _write_wav(wav)
    _write_fit(fit_dir / "actor__front__happy__level_1__001.npz")
    index = tmp_path / "index.csv"
    fields = ["sample_id", "actor_id", "emotion", "intensity", "camera", "video_path", "audio_path", "utterance_id", "fps", "frame_count", "duration"]
    with index.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"sample_id": "actor__front__happy__level_1__001", "actor_id": "actor", "emotion": "happy", "intensity": "1", "camera": "front", "video_path": "missing.mp4", "audio_path": str(wav), "utterance_id": "001", "fps": "25", "frame_count": "4", "duration": "0.16"})
        writer.writerow({"sample_id": "actor__front__sad__level_1__001", "actor_id": "actor", "emotion": "sad", "intensity": "1", "camera": "front", "video_path": "missing.mp4", "audio_path": str(wav), "utterance_id": "001", "fps": "25", "frame_count": "4", "duration": "0.16"})
    report = tmp_path / "failures.json"
    result = subprocess.run([sys.executable, "scripts/generate_training_sequences.py", "--index", str(index), "--fit-dir", str(fit_dir), "--out-dir", str(out_dir), "--failure-report", str(report)], cwd=Path(__file__).resolve().parents[1], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == 0, result.stderr
    assert (out_dir / "actor__front__happy__level_1__001.npz").exists()
    payload = json.loads(report.read_text())
    assert payload["failure_count"] == 1
    assert payload["failures"][0]["stage"] == "fit"
