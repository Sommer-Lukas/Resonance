# Resonance agent guide

Read `README.md` before changing the project. Resonance is a minimal,
face-only Unreal Engine architecture reference with a Python contract and
deterministic simulation under `src/resonance_pipeline`.

## Boundaries

- Keep audio chunks, features/prosody, ASR, text emotion, audio emotion,
  client-state fusion, listening, Audio2Face, head movement, and animation
  fusion replaceable through small typed protocols.
- Keep all final facial values under the single `AnimationFusion` authority.
- Audio2Face is an external Unreal adapter boundary. Local output is a demo
  placeholder, not NVIDIA integration or validation.
- Face-only means facial expression, speech articulation, and minimal head
  motion required by the face experiment. Do not add body, hands, posture,
  locomotion, gaze/social-attention, multiple avatars, trainee diagnosis,
  therapy, or clinical claims.

## Implementation rules

- Use Python standard library plus pytest only; prefer frozen dataclasses and
  `Protocol` contracts.
- Preserve deterministic timestamps, fixed WAV chunking, explicit EOS, repeated
  post-EOS reads, and validation of sample rate, channels, and `s16le` format.
- Keep providers narrow and local demos deterministic. Do not add registries,
  dependency-injection frameworks, ML training, network calls, or generated
  artifacts.
- Keep `ResonanceOrchestrator` as the small explicit application layer for
  advancing client/trainee sources, history, state, and final signal creation.
- Paired non-EOS client/trainee chunks must have aligned timestamps; reject
  misalignment rather than adding buffering or resampling. Trainee-only frames
  advance the client state's timestamp.
- Do not touch `third_party`, `.git`, or `.omo`.
- Do not claim real-time performance, perceptual validity, or Audio2Face
  validation without the future Unreal/device/human-evaluation evidence.

## Validation

Run:

```sh
PYTHONPATH=src:. pytest -q tests
PYTHONPATH=src:. python demo.py
```

Tests should target silent failures in chunk sequencing/EOS, partial chunks,
WAV validation, clamping/sampling, deterministic fusion, and final-output
authority. The migration from the old first-party prototype is history only;
do not restore that implementation.
