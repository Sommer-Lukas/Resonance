# Emotion idle and head behaviour

`feature/head-emotion` starts from `main`. Streaming/WebXR stays on its own branch.

The native scheduler provides three authored upper-face/eye/head variants per
Audio2Face dimension plus neutral (33 variants). It changes variants after
3.5–7.5 seconds without immediate repeats, blending the expressions smoothly.
Head targets hold and settle smoothly: anger has stronger movement, sadness,
grief and neutral have quieter movement. Motion is independent of speech.
The last automatic emotion continues into idle, as before.

Automatic changes wait 120 ms after playback-aligned scores before entering a
faster 0.3-second emotion filter and 0.18-second expression/variant filter.
This separates slightly later onset from quicker blending. The character's
`ResonanceEmotionState` exposes `EmotionDelaySeconds`, `TransitionSeconds`, and
`VariantTransitionSeconds` for tuning. Delay 0 restores direct onset. These
filter values are time constants, not fixed transition durations. Manual
preview bypasses the onset delay; audio and articulation are not delayed.
Queued targets are cleared on detected stream replacement and manual preview.

These are artistic character performances, not validated human emotion rules.
No new classifier is installed. ACE still supplies ten control dimensions.
Six-class preview aliases map as follows; they do not imply that a six-class
classifier detects the other dimensions:

| Input | Control |
| --- | --- |
| neutral | neutral (all ten scores zero) |
| angry | anger |
| disgust | disgust |
| fear | fear |
| happy | joy |
| sad | sadness |

All ten controls are previewable: amazement, anger, cheekiness, disgust, fear,
grief, joy, outofbreath, pain, sadness. Shyness/embarrassment are not inferred
classes or aliases; this implementation covers the requested eleven profiles.

## Switching faces

Assign a reusable `ResonanceFaceCalibration` Data Asset to the character's
`ResonanceEmotionState` component. Duplicate it when a face needs separate tuning.
Defaults work without an asset on the current MetaHuman:

- Expression strength 1.3, optional individual curve gains.
- Eye strength 1, eye curve limit .18 with a calibration assigned.
- Head strength 1, pitch/yaw limits 5 degrees and roll limit 3 degrees.
- Head bone `head`, configurable local pitch/yaw/roll axes.
- Canonical ARKit channels, optional curve-name mapping. Mapping to `None`
  disables a channel. Mapped target names must be unique.

Runtime rotation limits cannot exceed 8 degrees. Jaw and mouth remain supplied
by speech. A pose-only pass of the fusion node after MetaHuman's post-process
RigLogic adds local head rotation
and fades it out in authored showcase mode; it never rotates an actor/camera.
A missing head bone skips rotation. Another skeleton requires a compatible
animation graph and deliberate axis/curve calibration; a map is not retargeting.

After the native build and editor restart:

```python
import build_resonance_emotion_idle as setup
setup.build(calibration_path='/Game/Resonance/Animation/DA_DefaultFaceCalibration')
```

Supply `face_path` and `character_path` for a replacement Blueprint pair. The
face graph must already contain the ACE source and the original Resonance
fusion wiring or the native fusion node. The installer also adds the final
pose-only pass, idempotently, in an owned copy of the post-process Blueprint.
The face state installs that copy on the named face component at BeginPlay.
Original MetaHuman post-process assets remain untouched. For a different rig,
also supply its `source_postprocess` and a unique `postprocess_path`; its final
post-process graph must preserve that rig's existing deformation pipeline.
This does not build arbitrary rigs.
Save the calibration after editing its strengths/limits in the editor.

## Preview in PIE

```python
import preview_resonance_behavior as behavior
behavior.preview('angry', strength=.85, variant=0)
behavior.preview('angry', strength=.85, variant=1)
behavior.preview('angry', strength=.85, variant=2)
behavior.preview('happy', variant=-1)  # automatically vary
behavior.snapshot()
behavior.resume()  # automatic emotion and automatic variants
```

`import verify_resonance_behavior as verify; verify.start()` records all 33
profile/variant combinations on game time under `Saved/EmotionBehavior`.

Pass `actor_label='...'` when multiple compatible actors exist. Preview affects
the PIE instance, not the classifier, speech audio or persistent defaults.

When a face state is present, its emotion blink scheduler replaces the old
Blueprint procedural input. Model blinks remain intact. Full closure suppresses
competing eyelid widening/squint. Only one procedural schedule reaches fusion.

## Checks and future work

Run `unreal/tests/run_emotion_idle_tests.cmd`, the AGENTS.md Python suite/demo,
and build `ResonanceFace`/`ResonanceFaceEditor` with UE 5.6 (close the editor for
DLL linking). Tests cover 33 distinct variants, smooth bounded head motion,
blink events, aliases, deterministic replay, invalid inputs and final fusion.

Compare each variant/intensity with the same audio and camera. Check eye
direction, neck seams, skin deformation and head axes on each replacement face.
Automated checks do not establish naturalness, headset performance or tracking.

Local validation on 14 November 2026: UE 5.6 native modules built successfully;
all native scheduler checks and 13 Python tests passed; the demo completed.
The PIE capture passed all six integration checks across 5,826 samples and all
33 variants, including changing final head-bone transforms and blink closure.
The default calibration and owned post-process assignment survived a new PIE
session. One startup Niagara/HairStrands crash occurred while rebuilding assets
before editor startup completed; it did not recur in subsequent PIE runs.
That observation does not establish a root cause or a general crash fix.

Future option: speech/prosody gestures, separately switchable from emotion idle.
No speech accent detector or speech gesture scheduler is implemented here.
