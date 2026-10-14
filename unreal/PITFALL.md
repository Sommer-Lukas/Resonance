# PitFallUebung VR exercise

Open `/Game/Resonance/Levels/PitFallUebung` in Unreal Engine 5.6.
The saved level uses its own `BP_PitFallGameMode` and `BP_PitFallTrackedPlayer`.
The player preserves the VR template's camera, controller tracking, hand meshes,
hand animation events, and loading-screen cleanup, with Character collision for the deck and plank.
The exercise is separate from Resonance's facial animation experiment.

## Play on Quest through PCVR

1. Connect the headset through Quest Link or Air Link and enter the PCVR session.
   Make the headset's PC runtime the active OpenXR runtime before launching Unreal.
2. In Unreal's Play dropdown, select **VR Preview**. If it is unavailable, connect
   the headset first and restart the editor.
3. Spawn on the solid upper deck, centred 2.2 metres before the shaft edge and
   facing the plank. Reset returns to the same position. The upper room has
   four walls and a ceiling with interior lighting.
4. Approach the overlook plank to view the open shaft, 60 metres deep.
   There are no stairs, landings, descent handrails, or route strips inside it.

| Control | Action |
| --- | --- |
| Left stick forward/back | Headset-facing walking at up to 1 m/s |
| Right stick left/right | Turn 30 degrees; centre the stick before turning again |
| Left controller X | Return to the entrance and stop movement |
| W and S / Q and E / R | Desktop movement / turning / reset |

Stay inside your physical headset boundary; use the stick to approach the virtual
overlook. The floor in the real room remains flat. Desktop Play mode provides a
fixed-height camera for checking geometry and movement.

The pit has solid walls, depth markers, fading lighting, and a dark bottom
platform. X returns the player to the entrance; falling below the level also
resets the player. Four-sided wall ribs and continuous corner edges emphasize
the shaft's depth. Ribs stop short of the corner edges, and shaft walls meet
the deck underside, avoiding overlapping visible faces at their joins.
Cool shaft lights fade toward the dark bottom; fixed exposure keeps the view
into the pit from automatically brightening.
No editor Python is required during play. This is a playable exercise scene,
not a study protocol or a validated measure of a participant's response.

## Rebuild and validation

Assets belong to `/Game/PitFall`. The level-building source is
`ResonanceVR/Content/Python/build_pitfall.py`. To rebuild in the editor Python
console with Play mode stopped:

```python
import build_pitfall
build_pitfall.main()
```

Rebuilding replaces only actors tagged `PitFallExercise` in this level and
keeps the authored tracked player. User actors with other tags are preserved.
`build_pitfall_vr.py` authors the player and input context. Walking uses the
template's `IA_Move` Enhanced Input event, turning uses `IA_Turn`, and reset
uses its pressed `IA_Menu_Toggle_Left` event remapped to X. The original
teleport execution is disconnected. Grip and hand animation events are retained.
The default input context in `Config/DefaultInput.ini` registers OpenXR bindings
without activating PitFall controls in other maps. The player activates its
context at BeginPlay and removes the conflicting template locomotion context.
The level override leaves the main project's default map and game mode intact.

Earlier UE 5.6.1 checks verified Blueprint compilation, Play mode spawning
before the plank, gravity, and automatic reset below the deeper shaft. Stair
collision and descent were checked before the stairs were removed.
For the repaired player, input injected through the current player's Enhanced
Input subsystem moves the capsule, turns it by 30 degrees while preserving its
height, and resets it to `(0, -820, 90)`. Both hand skeletal meshes exist and are
visible in the runtime pawn. These checks do not establish headset display or
physical controller tracking on the device.
The existing Python contract checks and demo pass (8 tests). Headset execution,
controller bindings on physical hardware, comfort, frame times, and standalone
Quest packaging still require device checks. Use PCVR VR Preview for the first run.

## If the PC mirror moves but the headset image is frozen

The PC mirror alone is insufficient evidence of headset rendering. Stop Play,
return to the Link session in the headset, and start **VR Preview** again. The
player now explicitly calls `HideLoadingScreen` at startup so an XR loading
layer cannot remain over the live scene. If the headset still shows a frozen
image, reconnect Link and restart Unreal before retrying. A loss of the OpenXR
session or an unfocused Link session must be checked on the headset; changing
movement logic cannot repair a disconnected display session.

Controller-driven virtual hands are provided. This does not implement optical
bare-hand tracking. The Live Coding Win64 SDK error is a separate C++ build
environment issue; the saved Blueprint exercise runs without Live Coding.
