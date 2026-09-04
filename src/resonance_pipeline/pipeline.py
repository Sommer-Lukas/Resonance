from __future__ import annotations

from dataclasses import dataclass, field, replace

from .contracts import Audio2FaceProvider, AudioChunk, AudioFeatures, AudioSource, AsrProvider, AudioEmotionProvider, ClientState, ConversationTurn, Emotion, FacialOutput, FacialSignal, FeatureProvider, HeadMovementProvider, ListeningProvider, OrchestrationFrame, TextEmotionProvider, clamp
from .providers import LocalAsr, LocalAudioEmotion, LocalTextEmotion, RmsFeatures


def fuse_emotion(timestamp: float, text: Emotion, audio: Emotion, text_weight: float = 0.7) -> ClientState:
    weight = clamp(text_weight)
    return ClientState(timestamp, Emotion(
        text.valence * weight + audio.valence * (1 - weight),
        text.arousal * weight + audio.arousal * (1 - weight),
        text.confidence * weight + audio.confidence * (1 - weight),
    ))


class LocalListening:
    def respond(self, state: ClientState, trainee_utterance: str, trainee_emotion: Emotion) -> str:
        return f"Client state {state.emotion.valence:.2f}/{state.emotion.arousal:.2f}; heard: {trainee_utterance or 'silence'}"


class PlaceholderAudio2Face(Audio2FaceProvider):
    def articulate(self, features: AudioFeatures) -> FacialSignal:
        return FacialSignal.from_mapping(features.timestamp, {"jaw_open": features.rms, "mouth_energy": features.peak})


class PlaceholderHeadMovement(HeadMovementProvider):
    def signal(self, state: ClientState) -> FacialSignal:
        return FacialSignal.from_mapping(state.timestamp, {"head_nod": state.emotion.arousal * 0.1})


@dataclass
class AnimationFusion(FacialOutput):
    applied: list[FacialSignal] = field(default_factory=list)

    def combine(self, articulation: FacialSignal, emotion: FacialSignal, head: FacialSignal) -> FacialSignal:
        values: dict[str, float] = {}
        for signal in (articulation, emotion, head):
            for channel, value in signal.channels:
                values[channel] = clamp(values.get(channel, 0.0) + value)
        return FacialSignal.from_mapping(max(articulation.timestamp, emotion.timestamp, head.timestamp), values)

    def apply(self, signal: FacialSignal) -> None:
        self.applied.append(signal)


@dataclass
class ResonanceOrchestrator:
    feature_provider: FeatureProvider = field(default_factory=RmsFeatures)
    asr_provider: AsrProvider = field(default_factory=LocalAsr)
    text_emotion: TextEmotionProvider = field(default_factory=LocalTextEmotion)
    audio_emotion: AudioEmotionProvider = field(default_factory=LocalAudioEmotion)
    listening: ListeningProvider = field(default_factory=LocalListening)
    audio2face: Audio2FaceProvider = field(default_factory=PlaceholderAudio2Face)
    head_movement: HeadMovementProvider = field(default_factory=PlaceholderHeadMovement)
    animation: AnimationFusion = field(default_factory=AnimationFusion)
    state: ClientState = field(default_factory=lambda: ClientState(0.0, Emotion()))

    def run(self, client_audio: AudioSource, trainee_audio: AudioSource) -> tuple[OrchestrationFrame, ...]:
        frames: list[OrchestrationFrame] = []
        client_eos = trainee_eos = False
        while not (client_eos and trainee_eos):
            client_chunk = client_audio.read() if not client_eos else None
            trainee_chunk = trainee_audio.read() if not trainee_eos else None
            client_eos = client_eos or client_chunk is None or client_chunk.end_of_stream
            trainee_eos = trainee_eos or trainee_chunk is None or trainee_chunk.end_of_stream
            if client_eos and trainee_eos:
                break
            frame = self.process(client_chunk, trainee_chunk)
            frames.append(frame)
        return tuple(frames)

    def process(self, client_chunk: AudioChunk | None, trainee_chunk: AudioChunk | None) -> OrchestrationFrame:
        frame_timestamp = max((chunk.timestamp for chunk in (client_chunk, trainee_chunk) if chunk is not None), default=self.state.timestamp)
        if (client_chunk is not None and trainee_chunk is not None and
                not client_chunk.end_of_stream and not trainee_chunk.end_of_stream and
                client_chunk.timestamp != trainee_chunk.timestamp):
            raise ValueError("paired audio sources must provide aligned timestamps")
        client_features = self.feature_provider.compute(client_chunk) if client_chunk and not client_chunk.end_of_stream else None
        trainee_features = self.feature_provider.compute(trainee_chunk) if trainee_chunk and not trainee_chunk.end_of_stream else None
        trainee_utterance = self.asr_provider.transcribe(trainee_chunk) if trainee_chunk and not trainee_chunk.end_of_stream else ""
        trainee_emotion = self._emotion(trainee_utterance, trainee_features)
        if client_features is not None and client_chunk is not None:
            client_utterance = self.asr_provider.transcribe(client_chunk)
            next_state = fuse_emotion(client_chunk.timestamp, self.text_emotion.infer(client_utterance), self.audio_emotion.infer(client_features))
            self.state = replace(next_state, history=self.state.history)
        if self.state.timestamp < frame_timestamp:
            self.state = replace(self.state, timestamp=frame_timestamp)
        history = self.state.history + (ConversationTurn(self.state.timestamp, "trainee", trainee_utterance, trainee_emotion),)
        response = self.listening.respond(self.state, trainee_utterance, trainee_emotion)
        history += (ConversationTurn(self.state.timestamp, "client", response, self.state.emotion),)
        self.state = replace(self.state, history=history)
        speaking = self.audio2face.articulate(client_features) if client_features is not None else FacialSignal.from_mapping(frame_timestamp, {})
        head = self.head_movement.signal(self.state)
        emotion_signal = FacialSignal.from_mapping(frame_timestamp, {"smile": self.state.emotion.valence})
        final = self.animation.combine(speaking, emotion_signal, head)
        self.animation.apply(final)
        return OrchestrationFrame(frame_timestamp, self.state, trainee_utterance, trainee_emotion, response, speaking, head, final)

    def _emotion(self, text: str, features: AudioFeatures | None) -> Emotion:
        audio = self.audio_emotion.infer(features) if features is not None else Emotion()
        return fuse_emotion(features.timestamp if features is not None else self.state.timestamp, self.text_emotion.infer(text), audio).emotion
