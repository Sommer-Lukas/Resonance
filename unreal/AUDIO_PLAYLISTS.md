# Mixed-emotion audio review

Open `/Game/Resonance/Levels/I_Resonance` and press Play. The original
`voice_test.wav` plays once after the two-second start delay. It then waits for
input, with the emotion-conditioned face layer enabled. There is no timed
replay or automatic progression into test audio.

Click the game viewport to give it keyboard focus. Each number key starts its
entire set of three mixed recordings, consecutively:

| Key | Mix durations | Total speech/test audio |
|---|---|---|
| 1 | 40.62, 42.65, 39.68 seconds | about 2:03 |
| 2 | 41.55, 43.47, 44.22 seconds | about 2:09 |
| 3 | 35.97, 39.80, 37.91 seconds | about 1:54 |
| 4 | 40.46, 44.04, 44.91 seconds | about 2:09 |
| 5 | 38.02, 40.67, 44.23 seconds | about 2:03 |

Pressing another number replaces the active set. Pressing the same number
restarts that set from its first mix. Once all three recordings finish, playback
waits again. The on-screen line identifies the set and mix. X/Y retain their
face-mode controls and replay the current recording through the same serial
playback controller.

Every mix contains all seven EmoDB source categories: neutral, happiness,
sadness, anger, fear, disgust and boredom. A single speaker is used within a
mix, with short blocks of acted utterances and 0.35-second pauses between
utterances. Speaker and category ordering vary across mixes. These are edited
test sequences, not a coherent conversation or a natural continuous emotional
performance. Original recordings are unchanged.

The face still follows **automatically inferred ACE emotion output**; the
source category annotations do not override the face. Boredom and other source
labels need not map one-to-one to the installed classifier's outputs. See
[emotion fusion](EMOTION_IDLE.md).

`Content/Resonance/Audio/MixedEmotionSets/manifest.json` records the source
files, speaker, source category, confidence and exact segment start/end times.
These let you compare visible behavior with the audio sequence. Complete
received emotion data is exported after each played recording to
`Saved/EmotionStreams/emotion_<stream_id>.csv` before the next recording starts.

## Rebuild

Run the generator using the project's editor Python (or normal Python):

```python
from pathlib import Path
import unreal
import resonance_audio_mixes as mixes
content = Path(unreal.Paths.project_content_dir())
mixes.build(content / 'Resonance/Audio/emodb_2.0',
            content / 'Resonance/Audio/MixedEmotionSets', mixes_per_key=3,
            minimum_seconds=30, maximum_seconds=45, pause_seconds=.35)
```

The generator requires only Python's standard library. The generated WAVs are
stored through Git LFS. Install the native plugin with `Build-EmotionFace.ps1`,
then in the editor run:

```python
import build_resonance_audio_playlists
build_resonance_audio_playlists.build()
```

Playback is native C++/Blueprint; editor Python is only used to build assets or
run verification. A set advances on audible playback completion, never on the
inference-send completion callback. Replacing a set stops old playback and
waits for the existing send to end before starting another inference request.

`verify_resonance_audio_playlists.start()` in a fresh PIE session checks that the
base remains one-shot past the old replay interval, plays all three recordings
from key 1, and exercises actual player-input events for keys 2–5. Results are
saved under `Saved/AudioPlaylists/`.

## Local verification — 3 November 2026

The native build passed. The editor checks verified the one-shot base past the
old 36-second replay interval, a complete key-1 sequence in order, automatic
completion after its third mix, the active facial emotion layer, and key events
2–5 starting their respective sets. Base evidence was retained separately after
the first PIE session ended during playback; the complete set and remaining
keys were then tested in a new session. Results are in
`Saved/AudioPlaylists/validation.json` and `base-check.json`.

`unreal/tests/check_audio_mixes.py` independently verified all 15 distinct WAVs
against their source PCM, speaker/category annotations, durations and silence
gaps. Run it with `uv run python unreal/tests/check_audio_mixes.py`.
The reference harness's 13 tests and demo also passed.
