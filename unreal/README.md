# Unreal collaboration

The current editor project is `ResonanceVR/ResonanceVR.uproject`, associated
with **Unreal Engine 5.6**. It contains VR template and MetaHuman assets.
It includes a local Audio2Face portrait demo with a repeating full face
showcase (blinks, brows, eyelids, cheeks, nose and animated skin detail).
Select left-controller **X** for that showcase or **Y** for model-driven facial
output with varied procedural blinks; keyboard X/Y also work. James v3.0 diffusion is the default
model, using the supplied `voice_test.wav`. The portrait character is
**Vivian** (`BP_ResonanceVivian`), with LODSync Forced LOD 2. See
[setup, playback, and verification](AUDIO2FACE.md). Headset performance and
perceptual facial behavior have not been validated.

The Y/default face also uses automatic local ACE emotion output to drive
eleven upper-face profiles, three variants per emotion, emotion-dependent head
movement, eye offsets and blink timing. See [behaviour and face calibration](EMOTION_BEHAVIOR.md).
The last emotion persists after speech. See [emotion fusion, native build and
capture](EMOTION_IDLE.md); source builds require the small local ACE adapter patch.
The original speech plays once on startup. Keyboard **1–5** starts five different
three-mix EmoDB playlists for reviewing longer emotion changes; see
[audio playlist controls](AUDIO_PLAYLISTS.md).

## Open a clone

Install Git, Git LFS and Unreal Engine 5.6. Set up LFS before cloning:

```sh
git lfs install
git clone git@github.com:Sommer-Lukas/Resonance.git
cd Resonance
git lfs pull
```

For an existing clone, run `git lfs install`, `git pull` and `git lfs pull`.
Open `unreal/ResonanceVR/ResonanceVR.uproject` in Unreal Engine 5.6.
The enabled OpenXR and MetaHuman plugins are listed in the project descriptor.
The source-based `Plugins/UnrealMCPython` editor plugin is included under its
own Apache-2.0 license. A fresh clone may require compiling it with a supported
Unreal Engine 5.6 C++ toolchain. The separate local `unreal/unreal-mcp` upstream
checkout is not required to open the project and is not committed.
The separate [PitFallUebung exercise](PITFALL.md) has a deep open shaft and
instructions for playing through PCVR VR Preview.
Allow the first launch to regenerate caches and compile shaders.
Opening the project requires actual LFS assets, not a ZIP containing pointer files.

## Head portrait scene

`/Game/Resonance/Levels/I_Resonance` is the editor and game startup map.
It presents `BP_ResonanceVivian` against a black void, with a frontal
`Resonance_FaceCamera`, a focused overhead key light and a weaker fill light.
Both shoulders and the upper chest are visible, fading into darkness below.
Exposure is fixed in `Resonance_FixedExposure` so the dark scene does not brighten itself.
Adjust these actors in the `Resonance/Portrait` Outliner folder.

Vivian's imported assets live in `/Game/MetaHumans/Vivian`. The portrait
Blueprint `/Game/Resonance/Blueprints/BP_ResonanceVivian` inherits the existing
`BP_New_realistic_character` speech, emotion, blink and playlist behavior,
with Vivian's own meshes, materials, groom bindings and clothing. Rebuild
those appearance overrides with `Content/Python/build_resonance_vivian.py`,
then place her using `Content/Python/select_resonance_character.py`.
The previous character asset remains the behavior parent; it is no longer
the actor placed in the main portrait scene.

The original sky, sunlight, fog and floor are retained with visibility disabled
in `Resonance/DisabledEnvironment`.
`BP_ResonancePortraitGameMode` spawns the stationary `BP_ResonanceViewer` at
the PlayerStart, aligned with the portrait camera, about 1.1 metres in front
of the character (previously 1.5 metres). In VR Preview, the viewer
waits for a valid headset pose and removes its initial position and yaw from
the tracking origin once. Physical eye height is therefore not added on top
of the authored eye height, while later head movements remain tracked. Wear
the headset and face forward when starting VR Preview. Normal Play uses the
same viewpoint without calibration. `Resonance_FaceCamera` remains an editor
framing reference; it does not activate as the player's camera. Rebuild this
setup with `Content/Python/build_resonance_viewer.py` in the editor. Headset
alignment still needs verification on the device; other maps retain their
game modes.

## VR menu

A curved trainee menu (landing, Home, People, Sessions) with controller laser
pointers is built by `Content/Python/build_resonance_ui.py`. See
[VR menu](UI.md) for the build steps and what it creates. It has not yet been
run on a headset.

## Share changes

Use an issue branch and pull request. Pull the latest changes before opening
the editor, and save assets before committing. Coordinate ownership of maps
and assets: `.uasset` and `.umap` files cannot be merged as text. Git LFS stores
these files and imported `.fbx` meshes; it does not automatically prevent
simultaneous edits. GitHub LFS storage and download usage apply.

Commit the `.uproject`, project `Config`, shared `Content`, and any future
`Source`, source plugins and required `Build` resources. The repository ignores
`Binaries`, `DerivedDataCache`, `Intermediate`, `Saved`, generated IDE files,
local developer content and per-user editor settings. These files are generated
locally; they are not needed in a clone of this project. Binary-only third-party
plugins would need a separately documented installation path.

Keep machine credentials local. The Android file-server `SecurityToken` is
empty in shared configuration; configure a private token locally before using
authenticated file-server access.

Epic/MetaHuman and other vendor assets retain their own license terms; the
repository MIT license does not relicense them. Project scope remains the
face experiment described in the root README.
