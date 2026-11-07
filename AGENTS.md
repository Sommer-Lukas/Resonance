# Resonance agent guide

Read `README.md` before changing the project. Resonance is a minimal,
face-only Unreal Engine architecture reference with a Python contract and
deterministic simulation under `src/resonance_pipeline`.

## Local browser streaming and WebXR

- Read `docs/PIXEL_STREAMING_SETUP.md` before changing streaming or VR behavior.
- The maintained launcher is `scripts/start-pixelstream.ps1`; run it from this
  repository with `-Quality Low` for the 8 GB laptop. The player starts in desktop
  view; Open in VR is optional and requires browser headset support.
- Low means actual Unreal scalability level 0 in desktop and VR, not only a
  streaming-resolution limit. Keep generated GameUserSettings.ini isolated per
  run and preserve startup verification of all graphics groups. Do not raise
  Low's texture quality on VR entry or persist it into normal editor settings.
- Graphics complexity and VR clarity are separate: `-Quality Low -VRClarity Clear`
  is the default. Keep Low graphics while increasing sampling/bitrate for blur;
  `-VRClarity Economy` is the explicit 480p/70%/half-framebuffer fallback. Avoid
  stacking resolution reductions by default or enabling Epic to fix pixelation.
- Browser speech uses Epic's existing audio element. Preserve its playback
  recovery on XR entry/visibility/device changes and explicit output selector;
  do not add a second audible player, unmute Windows, or enable microphone capture.
- `scripts/pixelstream-webxr.js` extends Epic's pinned UE5.6 reference player.
  `unreal/ResonanceVR/Plugins/ResonanceWebXR` contains the native session switch.
  Keep the camera/rendering changes confined to launcher sessions and restore
  desktop settings on VR exit. Preserve the existing face/audio pipeline.
- Sources, tests and documentation belong in this repository. `.pixelstream/`
  contains ignored downloads/builds/logs; `scripts/pixelstream.local.json` contains
  ignored machine paths. No external worktree is required to start streaming.
- Run `node --test scripts/test-pixelstream-webxr.cjs scripts/test-pixelstream-loopback.cjs`
  for browser-session and loopback checks. Passing these or synthetic stereo
  transitions does not establish physical headset performance or tracking.

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
