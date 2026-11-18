# PitFall: ten-second cinematic

The cinematic is a separate darker version of the exercise:

* Map: `/Game/PitFallTrailer/L_PitFallTrailer`
* Sequence: `/Game/PitFallTrailer/LS_PitFallTrailer`
* Movie: `ResonanceVR/Saved/PitFallTrailer/PitFall-Trailer-4K.mp4`

Open the map and then the sequence in Sequencer. The ten seconds contain an
approach to the plank, a moving view down the 60-metre shaft, and a descending
camera looking back toward the rim. The cinematic copy has red room lights
with a slow intensity pulse, darker shaft lighting, red warning strips at
several depths, a one-metre-wide plank, and a subtle cool fill for the steel.
Teleport markers and floating instructions are hidden in this version.

The playable `PitFallUebung` map, its geometry/material assets, player,
teleportation, and project settings are unchanged. Source file SHA-256 hashes
were compared before and after authoring. The cinematic uses private actor
overrides and one private warning material; it does not rebuild the exercise.

## Render again

Movie Render Queue must be enabled for the editor session, as with the
[portrait trailer](TRAILER.md). With the cinematic map open and PIE stopped:

```python
import pitfall_trailer
pitfall_trailer.render(output_directory="C:/renders/PitFallTake2")
# pitfall_trailer.render(preview=True, output_directory="C:/renders/PitFallPreview")
```

The full export is 3840 x 2160, 24 fps, 240 frames, with four temporal samples,
cinematic quality, high quality shadows and two by two tiles with 5% overlap.
It uses its own render queue and a temporary base game mode, so gameplay does
not run during capture. Saved output is ignored by Git. Use a fresh directory
for another take to preserve existing media.

From the repository root, encode an export with:

```powershell
uv run python unreal/encode_pitfall_trailer.py `
  --frames C:/renders/PitFallTake2 --output C:/renders/PitFallTake2.mp4
```

The encoder checks all 240 frame numbers, creates an original deterministic
wind/rumble sound bed with quiet warning tones, and produces H.264 CRF 16 video
with AAC audio. The movie fades in over 0.3 seconds and out over its final
0.7 seconds. Ambient audio is added during encoding, not Sequencer playback.
The portrait speech sample is not used or modified.

## Recreate the cinematic

`Content/Python/pitfall_trailer.py` contains the authoring source. It rejects
overwriting existing cinematic assets. For a fresh build, use fresh `ROOT`,
`MAP` and `SEQUENCE` paths, open the saved original PitFall map, and run
`copy_level()`. Load the new map in a separate editor command, then run
`build()`. Saving a map copy does not switch the active editor world; the
map guards prevent accidentally styling or saving changes into the source.

Native Movie Render Queue completed the export successfully. The existing
13 Python tests and demo passed. Rendering this offline movie does not
establish headset performance or comfort.
