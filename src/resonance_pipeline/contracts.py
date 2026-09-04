from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


def clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class AudioChunk:
    timestamp: float
    samples: tuple[float, ...]
    sample_rate: int
    channels: int
    sample_format: str = "s16le"
    end_of_stream: bool = False

    def __post_init__(self) -> None:
        if self.timestamp < 0 or self.sample_rate <= 0 or self.channels <= 0:
            raise ValueError("invalid audio metadata")
        if self.sample_format != "s16le":
            raise ValueError("only s16le audio is supported")
        if self.end_of_stream and self.samples:
            raise ValueError("EOS chunks cannot contain samples")
        if not self.end_of_stream and not self.samples:
            raise ValueError("non-EOS chunks must contain samples")


@dataclass(frozen=True)
class AudioFeatures:
    timestamp: float
    duration: float
    rms: float
    peak: float
    zero_crossings: int


@dataclass(frozen=True)
class Emotion:
    valence: float = 0.5
    arousal: float = 0.0
    confidence: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "valence", clamp(self.valence))
        object.__setattr__(self, "arousal", clamp(self.arousal))
        object.__setattr__(self, "confidence", clamp(self.confidence))


@dataclass(frozen=True)
class ClientState:
    timestamp: float
    emotion: Emotion
    history: tuple["ConversationTurn", ...] = ()


@dataclass(frozen=True)
class ConversationTurn:
    timestamp: float
    speaker: str
    text: str
    emotion: Emotion


@dataclass(frozen=True)
class FacialSignal:
    timestamp: float
    channels: tuple[tuple[str, float], ...]

    @staticmethod
    def from_mapping(timestamp: float, values: dict[str, float]) -> "FacialSignal":
        return FacialSignal(timestamp, tuple(sorted((key, clamp(value)) for key, value in values.items())))

    def as_mapping(self) -> dict[str, float]:
        return dict(self.channels)


@dataclass(frozen=True)
class OrchestrationFrame:
    timestamp: float
    state: ClientState
    trainee_utterance: str
    trainee_emotion: Emotion
    response: str
    speaking: FacialSignal
    head: FacialSignal
    final: FacialSignal


class AudioSource(Protocol):
    def read(self) -> AudioChunk: ...


class FeatureProvider(Protocol):
    def compute(self, chunk: AudioChunk) -> AudioFeatures: ...


class AsrProvider(Protocol):
    def transcribe(self, chunk: AudioChunk) -> str: ...


class TextEmotionProvider(Protocol):
    def infer(self, text: str) -> Emotion: ...


class AudioEmotionProvider(Protocol):
    def infer(self, features: AudioFeatures) -> Emotion: ...


class ListeningProvider(Protocol):
    def respond(self, state: ClientState, trainee_utterance: str, trainee_emotion: Emotion) -> str: ...


class Audio2FaceProvider(Protocol):
    def articulate(self, features: AudioFeatures) -> FacialSignal: ...


class HeadMovementProvider(Protocol):
    def signal(self, state: ClientState) -> FacialSignal: ...


class FacialOutput(Protocol):
    def apply(self, signal: FacialSignal) -> None: ...
