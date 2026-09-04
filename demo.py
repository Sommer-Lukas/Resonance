from __future__ import annotations

import math
import struct
import tempfile
import wave
from pathlib import Path

from src.resonance_pipeline.pipeline import ResonanceOrchestrator
from src.resonance_pipeline.providers import FileAudioSource


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        client_path = Path(directory) / "client.wav"
        trainee_path = Path(directory) / "trainee.wav"
        with wave.open(str(client_path), "wb") as output:
            output.setparams((1, 2, 16_000, 1600, "NONE", "not compressed"))
            output.writeframes(b"".join(struct.pack("<h", int(12_000 * math.sin(i / 8))) for i in range(1600)))
        with wave.open(str(trainee_path), "wb") as output:
            output.setparams((1, 2, 16_000, 1600, "NONE", "not compressed"))
            output.writeframes(b"".join(struct.pack("<h", int(8_000 * math.sin(i / 5))) for i in range(1600)))
        orchestrator = ResonanceOrchestrator()
        frames = orchestrator.run(FileAudioSource(client_path, 400), FileAudioSource(trainee_path, 400))
        for frame in frames:
            print(f"timestamp={frame.timestamp:.3f} state={frame.state.emotion} response={frame.response!r} facial={frame.final.as_mapping()}")


if __name__ == "__main__":
    main()
