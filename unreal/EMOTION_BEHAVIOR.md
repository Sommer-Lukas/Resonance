# Emotion idle and head behaviour

`feature/head-emotion` starts from `main`. Streaming/WebXR stays on its own branch.

The native scheduler provides three authored upper-face/eye variants per
Audio2Face dimension plus neutral (33 variants). It changes variants after
3.5–7.5 seconds without immediate repeats, blending the expressions smoothly.
Head motion uses small turns, dips/lifts, tilts and returns, with curved travel
and uneven pauses. Each shift eases in and out with zero target velocity and
acceleration at its endpoints. A damped velocity state softens interruptions
when an emotion changes; internal speed is limited to 6 degrees/second
per axis and acceleration to 18 degrees/second squared (before per-face gains).
A much slower, tiny drift avoids a completely frozen hold. No periodic sway,
tremor, or semantic gesture inference is used.

Anger uses firmer, more frequent changes with more returns toward the partner;
sadness/grief use smaller movements and longer pauses. Neutral has visible
small orientation changes. Head scheduling uses a separate seeded generator
from face/eye/blink scheduling. Facial variants no longer move the head through
three poses: a stable weighted emotion anchor defines its resting orientation.
The last automatic emotion continues into idle, as before.

## Emotion-conditioned behaviour episodes

Emotion weights also choose ongoing head/eye tendencies. Fear favors a lowered
head and longer downward/sideways looks, with brief forward checks. Sadness and
grief favor similar aversion with different underlying expressions/timing;
anger favors forward attention; joy and neutral use more forward-facing time.
Disgust and pain have intermediate aversion tendencies. These are authored
character performances, not general claims about people with those emotions.

Episodes coordinate a shared sideways/downward bias across eyes and head.
Eyes settle faster than the head. Holds vary and can repeat a behaviour rather
than obligatorily alternate forward/away. Emotion weights blend the tendencies
smoothly. Facial variants remain three per profile; the episode scheduler does
not force the head through those three facial poses.

Normal PIE runs now derive a fresh behaviour seed from a new GUID. Enable the face component's
`UseFixedBehaviourSeed` and set `BehaviourSeed` for controlled comparisons.
`ActiveBehaviourSeed` records the effective seed and `LookingAway` exposes the
current episode. The standalone scheduler remains deterministic for a given
seed, so changing the normal runtime default does not remove replay tests.
Per-face eye strength/limits and head/neck calibration still apply.

The native five-minute fixed-seed test measured approximately 85% look-away
episodes for fear and 11% for anger, with lowered fear head pitch. Equal seeds
replayed exactly; a different seed changed the trajectory. These percentages
are test observations of the authored policy, not validated human norms.
Substantial changes in blended aversion tendency also reconsider the current
episode after a short minimum dwell, so a long fearful hold is not inherited
unchanged by anger. The latest fresh-seed fear-to-anger runtime audit passed
with 2,399 samples: approximately 71% fear look-away time and 15% anger look-away
time, with forward-facing early settled anger. Actual final eye curves and
eye-bone rotation relative to the head were also observed changing. These are
single-run observations; different seeds should produce different results.

## Speech timing instead of a repeating idle performance

`ResonanceEmotionState.UseSpeechTiming` is enabled by default. It observes the
amplitude envelope of the existing ACE audio component attached to the source.
This uses Unreal's audio mixer envelope delegate; it does not play audio, record
microphones, change volume, or infer meaning/emotion from amplitude.

An onset must persist for 100 ms; a pause must last 350 ms. Adaptive amplitude
thresholds and hysteresis suppress syllable-scale triggers. Selected onsets and
pauses and broader energy rises can request a movement, with a 1.4–2.8 second cooldown after travel. Not
every event moves the head. A pause usually permits a small return/settling.
Quiet periods combine a slightly more visible slow drift with sparse,
independent orientation adjustments. Opportunities use exponential intervals,
some are skipped, and their timing/size is not a small/big/return sequence.
Most adjustments are small; approximately one fifth use a larger amplitude.
They wait for at least 800 ms of quiet and a settled preceding movement. They
do not increment the speech cue count or turn syllable gaps into gestures.
Selected speech onsets that would otherwise return to an already centered
pose instead select a visible change.

Per-face calibration exposes `SpeechMotionScale` (1.5 by default),
`QuietMotionScale` (1.0), and `QuietIntervalSeconds` (8.0). The interval is a
distribution scale, not a fixed period, and also depends on emotion. Set quiet
scale to zero to disable adjustments while keeping the low-level drift.
The existing overall strength, head/neck mapping and rotation limits still apply.
The first detected phrase of a new playback now selects a visible pitch/yaw
movement rather than potentially skipping the whole short clip or selecting a
sub-degree roll. Later phrases remain selectively scheduled. Small quiet
adjustments also have a higher amplitude floor; intervals are unchanged.
Speech excursions now recover after a brief variable hold rather than retaining
the side-facing target until another cue. A slower recovery follows the initial
movement. Broader energy rises (250 ms versus 950 ms amplitude smoothing) can
select further excursions during a continuous phrase, with a shorter refractory
interval; ordinary syllable gaps still do not generate repeated cues. This is
amplitude timing, not semantic or linguistic stress recognition.
Grief, sadness, fear, disgust, pain and out-of-breath profiles have larger
movement amplitudes while keeping their different timing. Pitch choice is
biased down for grief/sadness/pain and up for amazement; these are authored
character choices, not universal psychological rules.
The current portrait's `DA_DefaultFaceCalibration` is tuned more visibly than
the conservative class defaults: speech scale 2.0 and quiet scale 1.5. Duplicate
and tune that asset for a replacement face rather than changing all faces.

For local playlist clips, if the mixer envelope has not supplied energy (for
example during suppressed background playback), a cached RMS envelope of the
original PCM16 WAV is sampled using ACE's playback-selected emotion timestamp.
This fallback requires a known local file and timestamp; it is not an adapter
for arbitrary streamed audio. `SpeechEnvelopeFromFile` distinguishes it from
the mixer. Audio playback/volume remains unchanged. Without either envelope,
playback start/stop supplies coarse timing only.
`SpeechEnvelopeSamples`, `SpeechVoiced`, `HeadSpeechCues`, and
`QuietHeadAdjustments` make analysis
observable. Stale mixer envelope samples count as silence after
300 ms once an envelope has been received. A new audio component replaces the
old delegate subscription; subscriptions are removed at EndPlay.

Disable `UseSpeechTiming` explicitly for sparse independent idle shifts. That
fallback uses unbounded exponential pauses; it never inserts a forced dip just
because the next target happens to match the current one.

For a runtime recording of actual speech rather than forced emotion previews:

```python
import verify_resonance_speech_head as verify
verify.start()  # replays the current reference clip on the existing player
```

The default records 45 game seconds for the nine-second reference clip under
`Saved/SpeechHead`; increase `seconds` for longer clips. It checks real envelope
delivery, voice/quiet detection, final bone movement, bounded rotation, and
visible quiet adjustments without continued speech cues in the silent tail.
This does not establish perceived naturalness.

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
- Optional upper-neck bone `neck_02` receives 25% of the existing rotation;
  the head receives the rest. This does not increase the total rotation.
  Neck share can be tuned from 0 to .4. Set the bone to `None` to disable it.
  Missing/non-ancestor neck bones fall back to head-only rotation. Local axes
  are mapped through the bone chain, rather than assuming identical neck axes.
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

The subsequent head-motion refinement passed the native kinematic/replay tests
and another complete PIE capture: 5,807 samples across 33 variants, including
movement of both final head and upper-neck bones. A 120-second isolated replay
produced 40 angry shifts versus 24 sad shifts, with more angular travel for
anger; speed/acceleration stayed bounded during abrupt target changes.
These measurements verify the authored behaviour, not perceived naturalness.

The earlier timer-only head refinement above is historical: visual feedback
identified its recurring pose changes despite its non-periodic scheduling.
The current speech timing removes that coupling and permits genuine stillness.
The reference-clip check recorded 1,780 samples over 30 game seconds, with two
selected head cues and no further cues in the silent tail. The local WAV
envelope fallback was active for 539 samples because the background mixer
reported zeros. All seven integration checks passed. This verifies timing and
data flow; the earlier visual naturalness judgment was not supported by those
technical checks and should be assessed against the actual speaking character.
Future option: semantically/prosodically selected emphasis gestures. The current
controller detects coarse speaking and pauses, not word meaning or pitch accents.

Quiet-motion balance refinement: the neutral 120-second controller replay now
contains 13 irregular adjustments, with 5,029 frames below 0.1 degrees/second
summed axis speed and 763 above 0.3 degrees/second. This verifies a mixture of
calm holds and visible movement, rather than either total stillness or constant
sway. The current portrait calibration passed a 45-second PIE recording with
2,699 samples, five quiet adjustments, approximately 1.7 degrees of horizontal
range in the silent tail, and all ten integration checks passing. Those checks
include continued quiet movement, no repeated speech cues after playback, and
rotation limits. They are not a perceptual naturalness score.

A visibility investigation found two limitations in those earlier checks.
Normal motion could span only a few screen pixels, despite passing a quaternion
change check. A temporary 6.8-degree pitch comparison moved the rendered nose
landmark about 14 pixels, confirming the head pass reaches the visible mesh.
The speech verifier now also checks at least six pixels of projected nose
displacement in the current portrait viewport; that threshold depends on view
size and is not a naturalness metric.

The Python preview helper also used editor property notification to change a
live component's variant. That could reconstruct the component and discard the
just-issued preview. `PreviewEmotion` now applies emotion and variant together
in native code, and `ResumeAutomaticEmotion` resets the variant natively. The
helpers no longer issue editor property changes for these runtime controls.
The regression check confirmed that the same live component remained in manual
anger/variant 1 after three seconds. A fresh ordinary Play session, with no
preceding manual preview or forced rotation, then passed all eleven checks:
2,699 samples, one speech cue, six quiet adjustments, and projected nose ranges
of 6.81 horizontal and 7.74 vertical pixels in the current viewport. This
replaces the earlier weak assumption that any quaternion change was sufficient.

To compare the quieter emotions against the same audio, run
`import audit_resonance_emotion_motion as audit; audit.start()` in PIE. This
records neutral, fear, grief, sadness, disgust and pain for 15 seconds each,
replaying the current local speech clip. It uses explicit emotion previews,
not claimed automatic inference, and writes per-profile angle/pixel ranges to
`Saved/EmotionMotionAudit/validation.json`. The head controller's 60-second
synthetic speech-energy tests also require repeated excursions and a readable
range in all eleven profiles; a steady tone must recover from its initial cue.
The revised controller passed those tests in all eleven profiles. A subsequent
90-second same-audio PIE audit passed for neutral, fear, grief, sadness, disgust
and pain (5,379 samples). Grief/sadness showed approximately 2.76 degrees of
pitch range; fear showed 4.12 degrees of yaw range. These are observed motion
ranges under explicit emotion control, not evidence of perceived naturalness.
