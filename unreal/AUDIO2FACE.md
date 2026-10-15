# Selectable face modes (UE 5.6 / Windows)

Open `ResonanceVR/ResonanceVR.uproject`, load
`/Game/Resonance/Levels/I_Resonance`, and press **Play** or **VR Preview**.
The default is **James diffusion + procedural blinks**. The portrait submits speech after two seconds;
first use also initializes the GPU model, which can take several more seconds.
Keep the editor in the foreground while inspecting desktop playback.

The portrait now uses `BP_New_realistic_character` from
`/Game/MetaHumans/New_realistic_character/`. Its LODSync **Forced LOD is 2**,
saved in both the Blueprint defaults and the level instance so close-up viewing
does not select the problematic higher-detail material setup. The skeletal
mesh API reports forced value 3 because that API uses 1-based LOD indices;
LODSync uses 0-based indices, so both refer to LOD 2.
The replacement retains the previous eye line and camera/viewer placement.
The old character asset is preserved, but its level actor was replaced.
The new character's own face, body, hair, materials and initialization are
retained; the shared face skeleton supports the existing ACE and blink graph.
The replacement passed all eight Enhanced Input mode checks and ten blink
checks at Forced LOD 2. A 16-second final-output capture is saved locally as
`Saved/Audio2Face-new-realistic-character.json`. Verification scripts resolve
the configured character class rather than matching the previous actor name.

The selected provider is now **`LocalA2F-James`**, James v3.0 diffusion
(60 FPS model output), from the supplied UE 5.6 package. This replaces
`LocalA2F-Mark-AR`. Both modes still use `voice_test.wav`.

| Left Quest/Touch controller | Desktop keyboard | Mode |
|---|---|---|
| **X** | **X** | Preserved authored full face showcase |
| **Y** | **Y** | James diffusion expressions + varied procedural blinks |

Each selection switches the facial mode and requests a replay of the same WAV.
If an inference send is already in progress, the mode switches immediately and
one replay is queued until that send completes. Rapid presses coalesce into
one pending replay; inference jobs are not started concurrently. The fade
between facial modes takes a fraction of a second. Periodic speech continues
every 36 seconds in either mode. Stop and Play again to reset everything.

**Y/default** sets the authored showcase fusion weight to zero. James diffusion
controls articulation and expression, with a separately identified procedural
blink input. This mode is no longer a pure model-only baseline. Mouth, jaw,
brows, cheeks and nose retain model output; eyelids blend toward closure and
eye widening/squinting blend toward zero during a procedural blink.

### Varied blinking in Y/default

The native face AnimBlueprint schedules its first blink after 1.5–4 seconds,
then samples a fresh pause of 2.8–6.5 seconds between blink starts. Duration
varies from 0.24–0.34 seconds and closure strength from 0.96–1.0. Both eyes
close together with a fast close, brief hold and slower reopening. This is
an aesthetic demo setting, not an empirically validated human blink model.

The scheduler samples random values only on initialization or a new blink;
they remain fixed through that blink. It uses game time, continues through
speech and silence, and is independent of audio replay and the 36-second
showcase clock. Each run gets different timings. No periodic baked sequence,
Python runtime callback, gaze behavior or body animation is involved.

The blink input uses `lerp(modelBlink, 1, proceduralClosure)`, preserving
existing model closure and staying bounded for model values in [0,1]. It
attenuates eye widening/squinting during closure, then returns control to the
model. The final `ResonanceAnimationFusion` still owns the output before
retargeting: X replaces these regions with its original authored values,
while Y passes the composed model/blink input through. Transitions retain
the existing fade. `verify_resonance_blink.py` checks the actual final curves,
random timing bounds, reopening, replay independence and preservation of X.
The 42-second editor verification passed all ten checks and captured ten
blink events with varied pauses (roughly 3.05–6.46 seconds in that run).
Evidence is in `Saved/Natural-blink-validation.json`; this verifies behavior
and curve composition, not perceived naturalness in a headset.

**Authored** mode preserves the previous 36-second showcase. X restarts its
expression clock, and the status line identifies the current stage:

| Seconds in cycle | Visible behavior |
|---|---|
| 0–12 | Subtle brow changes and natural blinks, with ACE speech articulation |
| 12–17 | Raised brows and widened eyes; forehead skin detail |
| 17–22 | Puzzled/furrowed brows |
| 22–27 | Eyelid squint and cheek raise |
| 27–31 | Nose wrinkle/sneer |
| 31–35 | Asymmetric questioning brow |
| 35–36 | Smooth return to neutral |

Blinks continue through the cycle with varied deterministic intervals. Each
blink lasts 0.28 seconds, reaches full closure and suppresses competing eye-wide
and eye-squint weights. There is no gaze/attention controller or body animation.
Speech loading/sending is independent of the authored clock and may overlap
the next expression stage.

Both modes now use `Content/Resonance/Audio/voice_test.wav`, the supplied
German recording: 9 seconds, mono, 48 kHz, 16-bit PCM. The original file is
used directly by the local ACE provider. The previous database clip,
`Content/Resonance/Audio/emodb_2.0/wav/08b03Tc.wav` (8.97825 seconds, mono,
16 kHz, 16-bit PCM), remains available; its path is retained as `EMODB_WAV`
in the builder. Earlier baseline measurements below used that previous clip.

Editor smoke testing of `voice_test.wav` completed successfully through the
local provider, returning 269 animation samples. A model-only replay showed
brow, eye, cheek and nose activity alongside articulation (peak inner brow
0.119, brow down 0.054, jaw open 0.622). Blinking remained negligible; this
recording does not guarantee expressive blinks. The existing vendor polling
timeout warning still appeared before successful completion.

### Previous Claire audit and emotion correction

The speech node now explicitly sets `bEnableEmotionOverride=False` and
`EmotionOverrideStrength=0`. The vendor struct defaults enabled application
blending at 0.5 despite this demo supplying no individual overrides. Local
plugin source forwards that flag to Audio2Emotion independently of whether
any override is active. This caused weaker audio-driven expression in the
observed comparison. Overall emotion strength remains the vendor default 0.6;
no scripted emotion or additional curve amplification was added to Y.

With the same `voice_test.wav`, sampled inner-brow peaks increased from
0.119 to 0.240 and brow-down from 0.054 to 0.115; jaw-open stayed near 0.62.
These are editor final-pose samples, not perceptual validation or a matched
capture of every model frame. The capture averaged roughly three samples per
second and cannot rule out missed short blinks. The verifier now records
sampling gaps and fusion alpha so this limitation is explicit.

A repeat with background throttling temporarily disabled captured 498 samples
over 16 seconds (mean gap 0.032 s, maximum 0.047 s). Both blink curves stayed
exactly zero, inner brow peaked at 0.242 and brow down at 0.116. This confirms
no visible blink in that tested playback, rather than relying on the sparse
capture. The editor throttle setting was restored afterwards. Evidence:
`Saved/Audio2Face-voice-model-audit-unthrottled.json`.

The audited model path is ACE -> fusion with alpha exactly 0 -> NVIDIA ARKit
pose mapping -> MetaHuman face post-process. No mouth-only mask is present.
Native blink strength and upper-face strength are both 1 in the installed
model config. Almost no blink activity was captured in either run; reliable
natural blinking remains unresolved in the pure model mode. X still provides
authored blinks. A different vocal performance does not guarantee them in Y.
NVIDIA describes Claire as less expressive than Mark/James; the supplied
archive is the v2.3 regressive model, not v3 diffusion. See
[NVIDIA provider and parameter documentation](https://docs.nvidia.com/ace/latest/workflows/kairos/ace-unreal-plugin-audio2face.html).

## Diffusion model selection

Before the procedural blink layer was added, Mark and James v3.0 diffusion were tested with the same German recording,
overall emotion strength 1.0, application emotion blending disabled, and
normal `upperFaceStrength=1.0`, `blinkStrength=1.0`. The former regressive
profile's 2x face/blink amplification is no longer used.

| Peak final curve | Mark diffusion | James diffusion |
|---|---:|---:|
| Inner-brow raise | 0.844 | 1.000 |
| Brow lowering, strongest side | 0.484 | 0.959 |
| Outer-brow raise, strongest side | 0.809 | 0.714 |
| Eyelid squint, strongest side | 0.161 | 0.492 |
| Blink, strongest side | 0.023 | 0.141 |
| Eye widening, strongest side | 0.959 | 0.377 |
| Cheek squint, strongest side | 0.311 | 0.347 |

James was selected for stronger brow/squint activity, more eyelid closure and
less extreme eye widening in this clip. This is a clip-specific selection,
not a universal model ranking or human evaluation. Those measurements used
model-only Y. Model-generated blink activity was partial, not a full closure.
James's measured forehead-joint position range reached 0.357 cm on one
component axis, confirming upper-face motion reaches the MetaHuman rig.

Both providers returned complete 539-frame submissions for the 9-second clip.
Local evidence: `Saved/Audio2Face-voice-Mark-diffusion.json` (1501 samples,
mean interval 32 ms) and `Saved/Audio2Face-voice-James-diffusion.json` (2177
samples, mean interval 17 ms). These are final-pose samples, not raw model
frames. The verifier now samples at up to each editor frame to cover diffusion.

Loading James while Mark remained allocated exhausted GPU memory and crashed
the editor during comparison. The editor recovered; James was then tested
successfully in isolation. Normal playback requests only James. Do not allocate
multiple diffusion providers concurrently on this machine; use a fresh editor
session or release the previous provider before comparing. The original
background-throttle setting was restored after testing.

## Previous regressive model comparison

### Mark versus James on voice_test.wav

Both supplied UE 5.6 models were tested through the saved face graph with
authored fusion alpha 0. Final comparison used identical supported settings:
overall emotion strength 1.0, upper-face strength 2.0, blink strength 2.0,
application emotion overrides disabled. Parameters are created and passed to
the async speech node on every replay. Other face parameters retain defaults.
This is a deliberately stronger model profile, not the vendor default or an
added expression timeline. Raising blink strength does not schedule blinks.

| Peak final curve | Mark | James |
|---|---:|---:|
| Brow lowering, strongest side | 0.291 | 0.004 |
| Outer-brow raise, strongest side | 0.186 | 0.113 |
| Inner-brow raise | 0.036 | 0.226 |
| Blink, strongest side | 0.088 | 0.002 |
| Cheek squint, strongest side | 0.028 | 0.073 |
| Nose sneer, strongest side | 0.083 | 0.037 |

Mark was previously selected for this clip's brow/eye emphasis, not as a universally
better model. Neither produced a full natural blink. Mark's measured
forehead-joint position range included 0.092 cm on one component axis,
confirming upper-face motion reaches the MetaHuman rig. Peak curve magnitude
does not establish perceptual quality. X still supplies the authored showcase;
Y remains model output without scripted blink or expression additions.

Warm-run captures contain 554 Mark and 560 James final-pose samples over
18 seconds, around 31 samples/second. Both providers completed 269-frame
speech submissions. Evidence is in ignored local Saved files:
`Audio2Face-voice-Mark-AR-expressive.json` and
`Audio2Face-voice-James-AR-expressive.json`. The earlier partial Mark warm-up
capture was discarded and repeated. Background throttling was temporarily
disabled for measurements; the original setting was restored afterward.

## Installed versions

- Base plugin: `NV_ACE_Reference`, **2.5.0-20250614-2282**, UE 5.6.
- Selected model plugin: `NvAudio2FaceJames`,
  **2.4.0-20250610-2270**, UE 5.6; James **v3.0 diffusion**, 60 FPS model.
- Mark diffusion and the earlier regressive plugins remain installed for comparison.
- Explicit provider: `LocalA2F-James`. No server or API key is used.

The newest matching packages supplied locally were the `UE5.6-v2.4.0.zip`
archives. The `UE5.5-v2.4.0rc7.zip` files are not used. Claire, James, and
Mark have matching package versions; James diffusion is now selected.
Package version 2.4.0 does **not** mean model version 2.4. The user supplied
the v3.0 diffusion packages after the initial regressive-model setup.
See NVIDIA's [support matrix](https://docs.nvidia.com/ace/ace-unreal-plugin/2.5/ace-unreal-plugin-support-matrix.html).

For another machine, install the base plugin into `ResonanceVR/Plugins/`
and extract `NvAudio2FaceJames-UE5.6-v2.4.0.zip` and
`NvAudio2FaceMark-UE5.6-v2.4.0.zip` from `ResonanceVR/Models/ACE_3.0_A2F_Models/`
into the same `Plugins/` directory. The earlier regressive comparison packages
come from `ACE_2.3_A2F_Models/`. Restart Unreal. ACE plugins are explicitly enabled for Win64 in the project
descriptor. Vendor binaries, archives, and model weights are locally installed
and ignored by Git; retain NVIDIA's supplied licenses.

## Connection

`BP_New_realistic_character` owns `ResonanceACEAudio`, an ACE Audio Curve Source
component attached to Face. It plays the returned audio and supplies synchronized
curves. The face uses `/Game/Resonance/Animation/ABP_ResonanceFace`:

`Copy Body Pose -> Apply ACE Face Animations -> Blink Input -> AnimationFusion (Modify Curve) -> mh_arkit_mapping_pose_A2F -> Output Pose`

`ResonanceAnimationFusion` is the final curve authority before retargeting.
In authored mode ACE supplies mouth/jaw articulation. Fifteen bounded authored curves supply
bilateral blinks, eye widening/squinting, inner/outer brow raises, brow lowering,
cheek squint/raise and nose sneers. These regions are explicitly replaced in
the fusion node; they do not compete with ACE's weak upper-face predictions.
Curve values are clamped to [0,1] when authored. The graph reads native
CurveFloat assets with linear interpolation and a shared game-time clock.
The owning character stores the selected mode and the authored start time;
the face AnimBlueprint blends `DemoAlpha` toward 1 for authored or 0 for
model-driven. In Y, the final fusion node passes the composed model/blink input
unchanged. The portrait viewer owns the input mapping context, and other maps
do not automatically start speech or enable the showcase. All runtime behavior
is compiled Blueprint.

The showcase is **authored expression behavior**, not evidence that Audio2Face
inferred puzzlement or other emotions from speech. The initial ACE-only test
of this clip measured peak blinking around 0.006, eye widening around 0.023,
and several squint, outer-brow, cheek and nose channels at or near zero.

The existing MetaHuman face post-process remains responsible for its rig.
The NVIDIA pose mapping avoids the additional legacy MouthClose processing.
ACE curve interpolation and decay to zero after speech are enabled.
See NVIDIA's [character setup](https://docs.nvidia.com/ace/ace-unreal-plugin/latest/ace-unreal-plugin-animation.html).

BeginPlay checks the map name, waits two seconds in `I_Resonance`, then calls
`AnimateCharacterFromWavFileAsync` with the explicit local provider. The WAV
path is built from the project Content directory. Submission failure prints
an error; submission completion is logged separately from playback completion.
The clip is resubmitted every 36 seconds and can be replayed by selecting a
mode. Other maps do not automatically submit it. EndPlay stops the character's
audio, and the viewer removes its input mapping context. A single status line
shows the active mode; delayed authored labels cannot remain in model mode.

## VR input

`/Game/Resonance/Input/IMC_ResonanceFaceModes` maps `IA_FaceAuthored` to
`OculusTouch_Left_X_Click`/keyboard X and `IA_FaceModel` to
`OculusTouch_Left_Y_Click`/keyboard Y. The portrait viewer responds to **Started**,
so holding a button does not repeatedly request playback. It adds this context
at priority 30 on BeginPlay and removes it on EndPlay, preserving its existing
headset calibration and stationary camera behavior.

The context is listed in `DefaultInput.ini` with `bAddImmediately=False` so
OpenXR can discover its actions when creating a session, while activation
remains scoped to this viewer. Start a new VR Preview session after changing
bindings. Quest controller hardware operation still needs headset verification;
the editor test exercises the actual Enhanced Input action events by injection.

This is an isolated fixed-audio Unreal adapter demonstration. The deterministic
Python harness still uses its placeholder adapter. Live listening/turn events
and the Python orchestrator are not connected to this authored showcase.
PCVR performance,
lip-sync quality, and human perceptual validity are not established by the
smoke test. This configuration uses a loose local WAV and has not been staged
or validated as a packaged game or standalone Quest application.

## Rebuild and inspect

The assets are already saved. To rebuild existing assets, run in Unreal's Python console:

```python
import build_resonance_full_face as demo
demo.build()
```

The builder preserves existing MetaHuman initialization nodes and records its
own generated EventGraph nodes in asset metadata so subsequent runs replace
only those nodes. It refuses to replace unrelated BeginPlay behavior. Its
face AnimBlueprint is owned by this demo and its EventGraph is rebuilt.
`build_resonance_face_modes.py` builds the mode state, serialized replay queue,
and viewer bindings. It retains the editor-resolved cast nodes across rebuilds
because the installed MCP helper does not resolve new wildcard pins itself.
Edit `Content/Python/resonance_face_demo.py` to tune the authored sequence, blink timing,
and expression strengths. The builder rebakes 15 CurveFloat assets under
`/Game/Resonance/Animation/FaceCurves`; intermediate CSV files stay in ignored
`Saved/FaceDemoCurves`.

If creating the graph assets from scratch, import
`build_resonance_audio2face as a`, run `a.prepare_face()`, then paste
the text from `Content/Python/ace_face_nodes.txt` into the AnimGraph once.
Paste `ace_async_node.txt` into the MetaHuman EventGraph once. Create the input
assets with `build_resonance_face_modes.build_input_assets()`, then paste
`face_mode_input_nodes.txt` once into `BP_ResonanceViewer`'s EventGraph.
Run `demo.build()`. The complete face snippet already includes AnimationFusion.
On first creation, new casts may need **File → Refresh All Nodes** in the face
and viewer Blueprints, followed by Compile. Rerunning the relevant build step
then retains those resolved nodes; ordinary saved-asset rebuilds need no GUI.
Paste into a fresh pose graph; inserting it alongside an old graph can leave
duplicate pose links because the installed MCP helper does not handle Unreal's
"break both existing pose links" response. Existing saved assets can simply be
rebuilt with `demo.build()` without any clipboard operation.
These are Unreal's native Blueprint clipboard formats; the installed
MCP helper cannot create these node types directly. No C++ toolchain is needed
with the supplied compatible binary plugins.

For full authored-region evidence, select X and run
`import verify_resonance_audio2face as v; v.start()` during Play. It samples final facial curves, five facial joint
positions and six actual animated skin-material parameters for 40 seconds,
writing `Saved/Audio2Face-full-face.json`. A complete cycle must be sampled
before assessing every region. The previous ACE-only baseline is stored in
`Saved/Audio2Face-ace-baseline.json` locally.
Inspect `Saved/Logs/ResonanceVR.log` for `LogACERuntime`, `LogACEAIMSDK`, and
`ACE audio submission completed`, and `Face mode:`. The earlier authored cycle verification
on 15 October 2026 measured all 15 owned channels changing, including blink
1.0, outer-brow raise 0.8, brow lowering 0.75, eyelid squint 0.65, cheek raise
0.75 and nose sneer 0.8. Jaw articulation remained active (peak about 0.55).
The actual skin material's blink, inner/outer brow raise, brow-lowering,
nose-wrinkler and cheek-raise parameters all changed too. Thus forehead/eye,
cheek and nose wrinkle maps are driven through the existing MetaHuman rig,
not new textures. These are editor output checks, not a perceptual or
performance evaluation. The viewport was also inspected during playback.

To verify mode switching, start Play and run
`import verify_resonance_face_modes as modes; modes.start()`. The 24-second
test injects actual Enhanced Input actions, checks the authored clock reset,
rapid-switch replay queue, strong authored brow movement, and a fully zero
authored fusion weight in model mode. It writes
`Saved/Face-mode-validation.json`. This does not test physical button hardware.
The editor test passed all seven switching/queue checks with 745 samples.
Normal keyboard X and Y presses were also exercised through the mapped keys,
and the context was confirmed removed after EndPlay. All three affected
Blueprints compile cleanly; the Python regression suite has 11 passing tests.

The ACE runs also logged an NVIDIA worker polling timeout warning despite
returning the clip and reporting successful submission. This remains a vendor
runtime warning to investigate if playback pauses; smooth or real-time
playback is not claimed.
