"""Independently validate baked PCM against original EmoDB utterances and metadata."""
import csv
import hashlib
import json
from pathlib import Path
import wave

CONTENT = Path(__file__).resolve().parents[1] / 'ResonanceVR/Content'
ROOT = CONTENT / 'Resonance/Audio/emodb_2.0'
MIXES = CONTENT / 'Resonance/Audio/MixedEmotionSets'


def check():
    manifest = json.loads((MIXES / 'manifest.json').read_text(encoding='utf-8'))
    with (ROOT / 'db.emotion.csv').open(encoding='utf-8', newline='') as source:
        labels = {r['file']: r['emotion'] for r in csv.DictReader(source)}
    with (ROOT / 'db.files.csv').open(encoding='utf-8', newline='') as source:
        speakers = {r['file']: r['speaker'] for r in csv.DictReader(source)}
    hashes = set()
    durations = {}
    assert set(manifest['keys']) == set('12345')
    for key, mixes in manifest['keys'].items():
        assert len(mixes) == 3
        durations[key] = []
        for mix in mixes:
            with wave.open(str(MIXES / mix['file']), 'rb') as wav:
                assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getcomptype()) == (16000, 1, 2, 'NONE')
                seconds = wav.getnframes() / 16000
                pcm = wav.readframes(wav.getnframes())
            assert 30 <= seconds <= 45
            assert abs(seconds - mix['seconds']) < 1 / 16000
            digest = hashlib.sha256(pcm).hexdigest()
            assert digest == mix['pcm_sha256'] and digest not in hashes
            hashes.add(digest)
            cursor = 0
            emotions = set()
            for index, segment in enumerate(mix['segments']):
                start = round(segment['start_seconds'] * 16000)
                end = round(segment['end_seconds'] * 16000)
                gap = start - cursor
                assert gap == (round(manifest['pause_seconds'] * 16000) if index else 0)
                assert pcm[cursor * 2:start * 2] == bytes(gap * 2)
                with wave.open(str(ROOT / segment['file']), 'rb') as original:
                    original_pcm = original.readframes(original.getnframes())
                assert pcm[start * 2:end * 2] == original_pcm
                assert segment['emotion'] == labels[segment['file']]
                assert speakers[segment['file']] == mix['speaker'] == segment['speaker']
                emotions.add(segment['emotion'])
                cursor = end
            assert cursor * 2 == len(pcm)
            assert emotions == {'neutral', 'happiness', 'sadness', 'anger', 'fear', 'disgust', 'boredom'}
            durations[key].append(round(seconds, 2))
    return {'passed': True, 'distinct_mixes': len(hashes), 'durations': durations}


if __name__ == '__main__':
    result = check()
    folder = CONTENT.parent / 'Saved/AudioPlaylists'
    folder.mkdir(exist_ok=True)
    (folder / 'assets.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
