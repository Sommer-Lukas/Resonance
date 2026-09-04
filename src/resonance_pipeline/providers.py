from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from .contracts import AudioChunk, AudioFeatures, AudioEmotionProvider, Emotion


class FileAudioSource:
    def __init__(self, path: str | Path, chunk_size: int, sample_rate: int = 16_000, channels: int = 1) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self._wave = wave.open(str(path), "rb")
        if self._wave.getframerate() != sample_rate or self._wave.getnchannels() != channels:
            self._wave.close()
            raise ValueError("unexpected WAV sample rate or channel count")
        if self._wave.getsampwidth() != 2 or self._wave.getcomptype() != "NONE":
            self._wave.close()
            raise ValueError("WAV must be uncompressed 16-bit PCM")
        self._chunk_size = chunk_size
        self._sample_rate = sample_rate
        self._channels = channels
        self._frames_read = 0
        self._eos = False

    def read(self) -> AudioChunk:
        if self._eos:
            return AudioChunk(self._frames_read / self._sample_rate, (), self._sample_rate, self._channels, end_of_stream=True)
        raw = self._wave.readframes(self._chunk_size)
        frame_bytes = self._channels * 2
        frame_count = len(raw) // frame_bytes
        if frame_count == 0:
            self._eos = True
            self._wave.close()
            return AudioChunk(self._frames_read / self._sample_rate, (), self._sample_rate, self._channels, end_of_stream=True)
        values = struct.unpack("<" + "h" * (frame_count * self._channels), raw)
        samples = tuple(sum(values[i:i + self._channels]) / (32768.0 * self._channels) for i in range(0, len(values), self._channels))
        timestamp = self._frames_read / self._sample_rate
        self._frames_read += frame_count
        return AudioChunk(timestamp, samples, self._sample_rate, self._channels)


class RmsFeatures:
    def compute(self, chunk: AudioChunk) -> AudioFeatures:
        if chunk.end_of_stream:
            return AudioFeatures(chunk.timestamp, 0.0, 0.0, 0.0, 0)
        squared = [sample * sample for sample in chunk.samples]
        crossings = sum(a * b < 0 for a, b in zip(chunk.samples, chunk.samples[1:]))
        return AudioFeatures(chunk.timestamp, len(chunk.samples) / chunk.sample_rate, math.sqrt(sum(squared) / len(squared)), max(map(abs, chunk.samples), default=0.0), crossings)


class LocalAsr:
    def transcribe(self, chunk: AudioChunk) -> str:
        return "utterance" if chunk.samples and max(map(abs, chunk.samples)) > 0.01 else ""


class LocalTextEmotion:
    def infer(self, text: str) -> Emotion:
        lowered = text.lower()
        if any(word in lowered for word in ("great", "glad", "happy")):
            return Emotion(0.85, 0.65, 0.8)
        if any(word in lowered for word in ("sad", "sorry", "difficult")):
            return Emotion(0.2, 0.45, 0.8)
        return Emotion()


class LocalAudioEmotion(AudioEmotionProvider):
    def infer(self, features: AudioFeatures) -> Emotion:
        return Emotion(0.5, features.rms, min(1.0, features.duration * 10.0))
