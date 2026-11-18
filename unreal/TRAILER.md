# Isolated Resonance trailer

The trailer is an authored 14-second portrait of `New_realistic_character`,
using the existing nine-second `Content/Resonance/Audio/voice_test.wav`.
Three moving cinema cameras approach the face, move across a close-up during
speech, and pull back for a final hold. The exported movie fades in and out.

Open `/Game/ResonanceTrailer/L_Trailer`, then
`/Game/ResonanceTrailer/LS_ResonanceTrailer` in Sequencer. Speech starts at
second 2 and ends at second 11. Play the sequence in Sequencer to preview;
ordinary Play does not automatically start the trailer.

The original startup map, face Blueprint, animation Blueprint, VR inputs,
ACE configuration and Python pipeline remain the existing implementation.
Trailer assets are confined to `/Game/ResonanceTrailer`. Shared MetaHuman
meshes, materials and the original WAV are read-only dependencies.

## Performance

`ABP_TrailerCapture` is a private copy of the face animation Blueprint.
Its fifteen upper-face curve getters point at private authored fear curves:
raised inner brows, wider eyes, mild brow tension and irregular blinks.
ACE supplies the speech articulation. This is an authored performance,
not emotion recognition or validation of perceived fear.

The final pose was captured from a PIE copy at **face LOD 0**, including all
875 local bone transforms and active skin-detail curves. `AS_TrailerFace`
resamples that capture to 24 fps. Sequencer forces custom animation mode so
the original face Blueprint cannot replace the bake. The trailer disables
the face post-process Blueprint because the bake already contains the final
RigLogic bone output; running it again would overwrite the baked pose.
No live inference or editor Python tick callback is needed for rendering.

The verified capture contains 293 samples. Its largest gap during speech is
approximately 93 ms. The larger startup gap occurs before audible speech.
The bake is deterministic, but it remains a sampled performance rather than
an export of every inference frame. Check lip sync by watching the movie.

## Render and encode

Open the existing project with Movie Render Queue enabled for that session:

```powershell
& 'C:/Program Files/Epic Games/UE_5.6/Engine/Binaries/Win64/UnrealEditor.exe' `
  "$PWD/unreal/ResonanceVR/ResonanceVR.uproject" `
  /Game/ResonanceTrailer/L_Trailer -EnablePlugins=MovieRenderPipeline
```

This does not edit the project descriptor or shared renderer configuration.
In the Unreal Python console:

```python
import render_resonance_trailer as trailer_render
trailer_render.render()  # 3840 x 2160, 24fps, eight temporal samples
# trailer_render.render(preview=True)  # 1280 x 720, two temporal samples
```

The renderer uses a separate queue, cinematic scalability, LOD 0, high quality
shadows, depth of field, and warm-up frames. The 4K output uses two by two tiles
with 15% overlap, 64 subsurface samples, a 1536 MB texture-streaming pool and
4096 virtual shadow pages to fit the laptop GPU. Console overrides apply only
to the render. PNG output is lossless. This uses deferred rendering, not path
tracing; the baked performance does not establish real-time VR performance.

Output is local and ignored by Git:

* `ResonanceVR/Saved/ResonanceTrailer/Frames4K/`: 336 numbered PNGs.
* `ResonanceVR/Saved/ResonanceTrailer/Resonance-Trailer-4K.mp4`: final movie.
* `ResonanceVR/Saved/ResonanceTrailer/capture_report.json`: sampling evidence.
* `ResonanceVR/Saved/ResonanceTrailer/render_result.json`: last render status.

After rendering, from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File unreal/Encode-Trailer.ps1
```

The encoder verifies all 336 frame numbers, uses H.264 CRF 16 and AAC 256 kbps,
and adds exactly two seconds of leading silence to match the animation.
It leaves the source WAV unchanged. Existing exports are not overwritten;
use a fresh output directory/name for another render.
For example, call `trailer_render.render(output_directory="C:/renders/Take2")`,
then pass `-Frames C:/renders/Take2 -Output C:/renders/Take2.mp4` to the encoder.

## Rebuild into a fresh trailer folder

The existing baked sequence is the normal starting point. To recreate from
the source scene, use a fresh `ROOT`, `MAP` and `SEQUENCE` in
`Content/Python/resonance_trailer.py`; completed assets reject rebuilding
so manual edits are preserved.

1. Open the original `I_Resonance` map and run `resonance_trailer.setup()`.
   It saves a copy and creates private fear curves and animation Blueprint.
2. Open the new trailer map in a separate editor command. `save_map` writes
   a copy without changing the current world; never continue on the source.
3. Run `prepare_capture()`, then `capture()`, then start PIE. Capture requests
   one authored speech performance on the PIE actor only. Wait for
   `TRAILER CAPTURE COMPLETE`, then stop PIE and allow shutdown to finish.
4. Run `bake_performance()`, then `build_sequence()`.
5. Preview before rendering. In particular, check that LOD 0 was captured,
   the mouth moves, camera cuts are correct, and face animation uses custom
   mode. Capturing lower LOD bones and rendering LOD 0 loses facial motion.

Editor background throttling is temporarily disabled by `capture()` and
restored when capture finishes. No runtime settings are saved by that change.

API references: [Epic Movie Render Queue scripting](https://dev.epicgames.com/documentation/unreal-engine/programming-a-render-in-mrg-in-unreal-engine),
[FFmpeg encoding and filters](https://ffmpeg.org/ffmpeg-all.html).
