from __future__ import annotations

import struct
import wave
from pathlib import Path
from typing import Iterator

import pytest

from src.resonance_pipeline.contracts import AudioChunk, Emotion, FacialSignal
from src.resonance_pipeline.pipeline import AnimationFusion, PlaceholderAudio2Face, PlaceholderHeadMovement, ResonanceOrchestrator, fuse_emotion
from src.resonance_pipeline.providers import FileAudioSource, LocalAudioEmotion, RmsFeatures


def write_wav(path: Path, frames: list[int], rate: int = 8000, channels: int = 1, width: int = 2) -> None:
    with wave.open(str(path), "wb") as output:
        output.setparams((channels, width, rate, len(frames), "NONE", "not compressed"))
        output.writeframes(b"".join(struct.pack("<h", value) for value in frames))


def test_wav_chunks_are_sequenced_partial_and_repeatable_eos(tmp_path: Path) -> None:
    path = tmp_path / "voice.wav"
    write_wav(path, [100, -100, 200, -200, 300], rate=8000)
    source = FileAudioSource(path, chunk_size=2, sample_rate=8000)

    first, second, third, eos, again = (source.read() for _ in range(5))

    assert [first.timestamp, second.timestamp, third.timestamp] == [0.0, 0.00025, 0.0005]
    assert [len(first.samples), len(second.samples), len(third.samples)] == [2, 2, 1]
    assert eos.end_of_stream and eos.samples == ()
    assert again == eos


@pytest.mark.parametrize("rate,channels,width", [(16000, 2, 2), (8000, 1, 1)])
def test_wav_metadata_is_validated(tmp_path: Path, rate: int, channels: int, width: int) -> None:
    path = tmp_path / "bad.wav"
    write_wav(path, [1, 2], rate=rate, channels=channels, width=width)
    with pytest.raises(ValueError):
        FileAudioSource(path, 4, sample_rate=16000, channels=1)


def test_audio_contract_rejects_invalid_format_and_eos_samples():
    with pytest.raises(ValueError):
        AudioChunk(0, (1.0,), 16000, 1, sample_format="float32")
    with pytest.raises(ValueError):
        AudioChunk(0, (1.0,), 16000, 1, end_of_stream=True)
    with pytest.raises(ValueError):
        AudioChunk(0, (), 16000, 1)


def test_features_emotion_sampling_and_clamping_are_deterministic() -> None:
    chunk = AudioChunk(1.5, (0.5, -0.5, 0.0), 3, 1)
    features = RmsFeatures().compute(chunk)
    assert features.rms == pytest.approx((1 / 6) ** 0.5)
    assert features.zero_crossings == 1
    state = fuse_emotion(2.0, Emotion(2, -1, 3), Emotion(0, 1, 0), text_weight=0.5)
    assert state.emotion == Emotion(0.5, 0.5, 0.5)
    assert LocalAudioEmotion().infer(features).arousal == pytest.approx(features.rms)


def test_final_animation_fusion_is_the_authority_and_repeatable() -> None:
    articulation = FacialSignal.from_mapping(1.0, {"jaw_open": 0.8, "smile": 0.2})
    emotion = FacialSignal.from_mapping(1.0, {"smile": 0.9})
    head = PlaceholderHeadMovement().signal(fuse_emotion(1.0, Emotion(arousal=1), Emotion()))
    fusion = AnimationFusion()

    final = fusion.combine(articulation, emotion, head)
    fusion.apply(final)

    assert final == fusion.combine(articulation, emotion, head)
    assert final.as_mapping()["smile"] == 1.0
    assert fusion.applied == [final]
    assert PlaceholderAudio2Face().articulate(RmsFeatures().compute(AudioChunk(0, (0.5,), 1, 1))).timestamp == 0


def test_orchestrator_processes_separate_audio_and_retains_conversation_state(tmp_path: Path) -> None:
    client_path = tmp_path / "client.wav"
    trainee_path = tmp_path / "trainee.wav"
    write_wav(client_path, [12000, -12000, 12000, -12000], rate=8000)
    write_wav(trainee_path, [8000, -8000, 8000, -8000], rate=8000)

    orchestrator = ResonanceOrchestrator()
    frames = orchestrator.run(FileAudioSource(client_path, 2, 8000), FileAudioSource(trainee_path, 2, 8000))

    assert len(frames) == 2
    assert all(frame.trainee_utterance == "utterance" for frame in frames)
    assert len(frames[-1].state.history) == 4
    assert len(orchestrator.animation.applied) == len(frames)
    assert frames[-1].final == orchestrator.animation.applied[-1]
    assert frames[-1].speaking.as_mapping()["jaw_open"] > 0


class ChunkSource:
    def __init__(self, *chunks: AudioChunk) -> None:
        self.chunks: Iterator[AudioChunk] = iter(chunks)

    def read(self) -> AudioChunk:
        return next(self.chunks)


def test_trainee_only_frame_advances_state_timestamp() -> None:
    client_eos = AudioChunk(0.0, (), 8000, 1, end_of_stream=True)
    trainee_chunk = AudioChunk(1.25, (0.5,), 8000, 1)
    trainee_eos = AudioChunk(1.375, (), 8000, 1, end_of_stream=True)

    frames = ResonanceOrchestrator().run(
        ChunkSource(client_eos), ChunkSource(trainee_chunk, trainee_eos)
    )

    assert len(frames) == 1
    assert frames[0].timestamp == 1.25
    assert frames[0].state.timestamp == 1.25
    assert frames[0].head.timestamp == 1.25
