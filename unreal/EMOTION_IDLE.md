# Emotion-conditioned upper face

The native `ResonanceFace` plugin combines Audio2Face articulation with eleven
authored upper-face profiles (the ten ACE emotion controls plus neutral).
Each profile has three restrained local variations, smooth transitions,
emotion-dependent conjugate eye movements with stationary pauses, and the
existing procedural blinks. The last received emotion is retained after speech.
The existing X showcase and Y model mode remain selectable.

## Build and install

The local NVIDIA plugin is ignored by Git. Its SDK already returns an emotion
slot, but ACE 2.5 discards it. Apply the small, checked-in adapter patch before
building; it changes only vendor adapter source, never `ThirdParty` code:

```powershell
powershell -ExecutionPolicy Bypass -File unreal/Build-EmotionFace.ps1
```

Close the editor for the native build: the transport changes the C++ ABI and
reflected component interface. Install MSVC 14.38, Windows SDK 22621 and the
.NET Framework SDK 4.8 if unavailable. The script builds only affected modules
and emits the local plugin module manifest. Reopen, then run in its Python console:

```python
import build_resonance_emotion_idle
build_resonance_emotion_idle.build()
```

The migration saves the face and character Blueprints, plus the reconstructed
portrait level instance when that level is open. It preserves speech/input graphs and replaces the old blink/showcase
curve writers with one final `ResonanceAnimationFusionNative` node. Its output
feeds the existing NVIDIA pose mapping and MetaHuman post-process. Mouth, jaw
and head curves pass through untouched.

## Emotion data and timing

The output is the local SDK's ten-element processed/remapped emotion vector,
not raw classifier probabilities. The installed classifier has five non-neutral
classes plus neutral; ten available authored profiles do not imply ten learned
classes. Missing categories remain usable through manual preview or a later
explicit client-state adapter. Neutral is the remaining weight below a total
of one; overlapping totals above one are normalized for expression blending.

Inference callbacks copy their transient emotion data into a queue. Samples
carry a stream ID and the local audio-derived timestamp with the same underflow
compensation as facial animation. The game thread consumes only samples whose
time has reached the playback clock. Future inference results cannot directly
change the currently playing face. Stream replacement clears pending samples
and history, while preserving the last displayed emotion. A clip without emotion
data therefore retains the previous state; the initial state is neutral.

`ResonanceEmotionState` exposes received and smoothed scores, dominant emotion,
idle curves and emotion audio time for inspection. Its settings are:

| Setting | Initial value | Purpose |
|---|---:|---|
| SpeakingBlend | 0.65 | Upper-face interpolation toward authored idle during speech |
| IdleBlend | 0.90 | Upper-face interpolation during silence |
| TransitionSeconds | 0.8 | Emotion smoothing time constant |

These are tunable animation parameters, not perceptually validated values.
The eye layer owns only eight directional eye curves, with small offsets; it
does not implement social attention, tracking or head motion. Blinks preserve
model closure and close the remaining opening; widening and squint relax during
closure. X showcase takes precedence smoothly through the existing mode alpha.

For previewing any of the ten authored profiles or neutral, call
`ResonanceEmotionState.PreviewEmotion(name, strength)` and later
`ResumeAutomaticEmotion()`. Preview affects the authored upper face only.

`ResonanceACEAudio.ExportEmotionStream()` writes the current stream's received
emotion history to `Saved/EmotionStreams/emotion_<stream_id>.csv`. History is
bounded to 18,000 samples per stream. Export before requesting another clip.
The number-key playlist controller exports completed clips automatically before
advancing to the next mix; see [audio review controls](AUDIO_PLAYLISTS.md).
The CSV retains time and stream ID for later processing. No file IO runs in
inference callbacks.

## Verification

```powershell
unreal/tests/run_emotion_idle_tests.cmd
$env:PYTHONPATH='src;.'
uv run --with pytest python -m pytest -q tests
uv run python demo.py
```

`verify_resonance_emotion_idle.py` captures actual inferred scores and final face
curves in PIE, checks retained emotion and eye variation after speech, exports
the received stream and exercises the manual profiles separately. Local output
checks do not establish headset performance or perceived naturalness.

## Local editor verification — 3 November 2026

The native build and standalone C++ checks passed. A fresh PIE capture passed
all 12 checks for actual SDK scores, bounded values, retained emotion, moving
eyes, upper-face output, speech articulation, all eleven manual profiles,
blink closure, suppression of widening during blinks and conjugate eye motion.
The 9-second clip produced 18 emotion samples (derived timestamps 0–8.5 s)
alongside 539 facial frames. The final retained vector was predominantly fear;
this is a model output observation, not a labelled accuracy result.

The original X showcase was also checked against its authored values with
fusion alpha 1.0; maximum curve error in the final sampled comparison was below
0.0001. A separate capture confirmed that both eye joints rotate (approximately
0.79 degrees and 1.57 degrees of variation on the two active axes), rather than
only changing curve values. Local evidence is in `Saved/EmotionIdle/validation.json`,
`showcase.json`, `eye-bones.json`, `native-animgraph.json` and `Saved/EmotionStreams/`.
The reference harness's 13 tests and demo passed. The installed local toolchain
is MSVC 14.38, Windows SDK 22621 and .NET Framework SDK 4.8.
