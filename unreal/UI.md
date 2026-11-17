# VR menu

The trainee-facing menu runs inside the Unreal app as a curved panel in front of
the portrait viewer. It follows the clickable web prototype: brushed-silver
stage, translucent "frosted" glass panels and the Resonance logo blues.

Phase 1 (this build) provides the framework: a top bar with Home, People and
Sessions tabs, a landing screen, simple Home, People and Sessions screens, and a
laser pointer on each controller. Person pages, briefings, starting a session
and session history follow in later phases.

## Build

Requires the UE 5.6 editor with the `UnrealMCPython` plugin compiled, the same
as the other build scripts in `ResonanceVR/Content/Python`.

1. Open `/Game/Resonance/Levels/I_Resonance`.
2. In the Python console run:

   ```python
   import build_resonance_ui; build_resonance_ui.build()
   ```

   The first run imports the images, builds the menu and input assets, then
   stops with `Paste menu_input_nodes.txt into the BP_ResonanceViewer EventGraph`.
3. Open `BP_ResonanceViewer`, open its EventGraph, and paste the contents of
   `Content/Python/menu_input_nodes.txt` (two trigger input nodes). Save.
4. Run the build again. It rebuilds the menu from scratch and wires the
   triggers to the pointers.
5. Check the result:

   ```python
   import verify_resonance_ui; verify_resonance_ui.verify()
   ```

Rerunning the build replaces `WBP_ResonanceMenu`, `BP_ResonanceMenu` and the
`Resonance_Menu` actor. Do not edit those by hand; change the script or the
content file instead.

## What it creates

| Asset | Purpose |
|---|---|
| `/Game/Resonance/UI/Textures/T_ResonanceStage`, `T_ResonanceLogo`, `T_ResonanceLogoMark` | Imported from `ResonanceVR/UISource`. The logo has its background removed. |
| `/Game/Resonance/UI/WBP_ResonanceMenu` | 1440×900 menu widget. `ShowLanding`, `ShowHome`, `ShowPeople` and `ShowSessions` switch screens. |
| `/Game/Resonance/Blueprints/BP_ResonanceMenu` | Widget component on a 40° cylinder, 1.08 m wide, placed 0.9 m in front of the PlayerStart. |
| `/Game/Resonance/Input/IMC_ResonanceMenu`, `IA_ResonanceSelectLeft/Right` | Left and right trigger click what that hand points at. |
| `BP_ResonanceViewer` components `LeftHand`, `RightHand`, `LeftPointer`, `RightPointer` | Aim-pose motion controllers with widget interaction rays. |

## Content

Menu text, clients and colours live in
`Content/Python/resonance_ui_content.json`. Edit it and rerun the build. Keeping
the text in a JSON file avoids binary merge conflicts on the widget asset.

Current client-to-MetaHuman mapping is an assumption until the team confirms it:
Anna uses `New_realistic_character`, Jonas `I0_Metahuman_test`, Peter
`4k_MetaHuman_Asian_Old`. Only Anna is marked available.

## Limits

- The glass is translucent tinting over the stage image, not real background
  blur. Unreal's background blur does not work on world-space widgets and would
  be costly in VR.
- Fonts are the engine's Roboto and Roboto Mono, not the prototype's Montserrat
  and Geist.
- Pointer rays use the widget interaction debug line. A proper laser mesh and
  hand-tracking pinch are later work.
- Not yet run in the editor or on a headset. Text size, panel distance, pointer
  feel and frame time need a VR Preview pass.
