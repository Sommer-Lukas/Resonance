"""Small stdlib/numpy prosody extraction aligned to face timestamps."""

from __future__ import annotations

import contextlib
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from voice_face.alignment import resample_to_timestamps


@dataclass(frozen=True, slots=True)
class AudioSignal:
    samples: np.ndarray
    sample_rate: int


PROSODY_FEATURE_NAMES = ("f0_hz", "rms_energy", "voiced")


def read_wav_mono(path: Path) -> AudioSignal:
    with contextlib.closing(wave.open(str(path), "rb")) as handle:
        channels = handle.getnchannels()
        sample_rate = handle.getframerate()
        width = handle.getsampwidth()
        frames = handle.readframes(handle.getnframes())
    if width == 1:
        audio = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 2:
        audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        audio = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {width}")
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return AudioSignal(audio.astype(np.float32), sample_rate)


def read_media_audio_mono(path: Path, *, sample_rate: int = 16000) -> AudioSignal:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError("imageio-ffmpeg is required to decode audio from non-WAV media") from exc
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "pipe:1"]
    proc = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace").strip() or f"ffmpeg failed for {path}")
    return AudioSignal(np.frombuffer(proc.stdout, dtype="<f4").astype(np.float32), sample_rate)


def read_audio_mono(path: Path) -> AudioSignal:
    if path.suffix.lower() == ".wav":
        return read_wav_mono(path)
    return read_media_audio_mono(path)


def _estimate_f0(frame: np.ndarray, sample_rate: int, *, min_hz: float = 60.0, max_hz: float = 400.0) -> tuple[float, bool]:
    frame = frame - float(np.mean(frame))
    rms = float(np.sqrt(np.mean(frame * frame))) if len(frame) else 0.0
    if rms < 1e-4:
        return 0.0, False
    corr = np.correlate(frame, frame, mode="full")[len(frame) - 1 :]
    min_lag = max(1, int(sample_rate / max_hz))
    max_lag = min(len(corr) - 1, int(sample_rate / min_hz))
    if max_lag <= min_lag:
        return 0.0, False
    lag = min_lag + int(np.argmax(corr[min_lag:max_lag]))
    confidence = float(corr[lag] / corr[0]) if corr[0] > 0 else 0.0
    return (float(sample_rate / lag), confidence > 0.25)


def extract_prosody(audio: AudioSignal, target_timestamps: np.ndarray, *, window_seconds: float = 0.04) -> np.ndarray:
    timestamps = np.asarray(target_timestamps, dtype=np.float32)
    out = np.zeros((len(timestamps), len(PROSODY_FEATURE_NAMES)), dtype=np.float32)
    if len(audio.samples) == 0 or audio.sample_rate <= 0 or len(timestamps) == 0:
        return out
    half = max(1, int(round(window_seconds * audio.sample_rate / 2.0)))
    for i, timestamp in enumerate(timestamps):
        center = int(round(float(timestamp) * audio.sample_rate))
        start = max(0, center - half)
        end = min(len(audio.samples), center + half)
        frame = audio.samples[start:end]
        if len(frame) == 0:
            continue
        rms = float(np.sqrt(np.mean(frame * frame)))
        f0, voiced = _estimate_f0(frame, audio.sample_rate)
        out[i] = (f0 if voiced else 0.0, rms, 1.0 if voiced else 0.0)
    return out


def prosody_from_audio(path: Path, target_timestamps: np.ndarray) -> np.ndarray:
    return extract_prosody(read_audio_mono(path), target_timestamps)


def prosody_from_wav(path: Path, target_timestamps: np.ndarray) -> np.ndarray:
    return extract_prosody(read_wav_mono(path), target_timestamps)


def resample_prosody(source_timestamps: np.ndarray, prosody: np.ndarray, target_timestamps: np.ndarray) -> np.ndarray:
    return resample_to_timestamps(source_timestamps, prosody, target_timestamps)
