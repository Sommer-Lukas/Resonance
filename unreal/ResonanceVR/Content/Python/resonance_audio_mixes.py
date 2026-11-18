"""Build reproducible EmoDB test mixes and segment annotations using only stdlib.

These are concatenated acted utterances, not a continuous conversation or new
emotion labels. Source WAVs remain untouched. Runtime playback uses the baked WAVs.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import random
import wave

EMOTIONS = ('neutral', 'happiness', 'sadness', 'anger', 'fear', 'disgust', 'boredom')
FORMAT = (16000, 1, 2, 'NONE')


def read_catalog(root):
    root = Path(root)
    with (root / 'db.files.csv').open(encoding='utf-8', newline='') as source:
        files = {r['file']: r for r in csv.DictReader(source)}
    with (root / 'db.emotion.csv').open(encoding='utf-8', newline='') as source:
        labels = list(csv.DictReader(source))
    speakers = {}
    for row in labels:
        relative = Path(row['file'])
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or relative.parts[0] != 'wav':
            raise ValueError('Expected a microphone WAV within the dataset: ' + str(relative))
        info = files[row['file']]
        with wave.open(str(path), 'rb') as wav:
            fmt = (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getcomptype())
            if fmt != FORMAT:
                raise ValueError(f'Unsupported WAV format for {relative}: {fmt}')
            frames = wav.getnframes()
        item = {'file': relative.as_posix(), 'emotion': row['emotion'],
                'speaker': info['speaker'], 'frames': frames,
                'confidence': float(row['emotion.confidence'])}
        speakers.setdefault(info['speaker'], {}).setdefault(row['emotion'], []).append(item)
    complete = {speaker: groups for speaker, groups in speakers.items()
                if all(emotion in groups for emotion in EMOTIONS)}
    if not complete:
        raise ValueError('No speaker has all required emotions')
    return complete


def plan_mix(groups, seed, minimum_seconds, maximum_seconds, pause_seconds):
    """Use emotional blocks of whole utterances; never cut speech."""
    if not 0 < minimum_seconds <= maximum_seconds or pause_seconds < 0:
        raise ValueError('Invalid duration or pause bounds')
    rng = random.Random(seed)
    order = list(EMOTIONS)
    rng.shuffle(order)
    mean_seconds = sum(sum(item['frames'] / FORMAT[0] for item in groups[emotion])
                       / len(groups[emotion]) for emotion in EMOTIONS) / len(EMOTIONS)
    per_category = max(2, round((minimum_seconds + maximum_seconds) / 2
                               / len(EMOTIONS) / (mean_seconds + pause_seconds)))
    # Find a bounded full-utterance arrangement with every category represented.
    # The seed, catalog order and full segment manifest make the result replayable.
    for _ in range(500):
        blocks = []
        for emotion in order:
            available = groups[emotion]
            blocks.append(rng.sample(available, min(per_category, len(available))))
        segments = [item for block in blocks for item in block]

        def duration(items):
            return sum(r['frames'] for r in items) / FORMAT[0] + pause_seconds * (len(items) - 1)

        while duration(segments) > maximum_seconds:
            removable = [(block, index, item) for block in blocks if len(block) > 1
                         for index, item in enumerate(block)]
            if not removable:
                break
            block, index, _ = max(removable, key=lambda entry: entry[2]['frames'])
            block.pop(index)
            segments = [item for block in blocks for item in block]
        if minimum_seconds <= duration(segments) <= maximum_seconds:
            return segments
    raise ValueError('Could not fit complete mixed-emotion utterances within requested duration bounds')


def bake_mix(root, destination, segments, pause_seconds):
    root, destination = Path(root), Path(destination)
    pause_frames = round(pause_seconds * FORMAT[0])
    cursor = 0
    annotation = []
    digest = hashlib.sha256()
    with wave.open(str(destination), 'wb') as output:
        output.setnchannels(FORMAT[1])
        output.setsampwidth(FORMAT[2])
        output.setframerate(FORMAT[0])
        for index, item in enumerate(segments):
            if index:
                silence = bytes(pause_frames * FORMAT[2])
                output.writeframesraw(silence)
                digest.update(silence)
                cursor += pause_frames
            with wave.open(str(root / item['file']), 'rb') as source:
                pcm = source.readframes(source.getnframes())
            expected = item['frames'] * FORMAT[2]
            if len(pcm) != expected:
                raise ValueError('Source changed while building: ' + item['file'])
            output.writeframesraw(pcm)
            digest.update(pcm)
            annotation.append(dict(item, start_seconds=cursor / FORMAT[0],
                                   end_seconds=(cursor + item['frames']) / FORMAT[0]))
            cursor += item['frames']
    return {'file': destination.name, 'seconds': cursor / FORMAT[0],
            'pcm_sha256': digest.hexdigest(), 'segments': annotation}


def build(root, destination, *, mixes_per_key, minimum_seconds, maximum_seconds, pause_seconds):
    if mixes_per_key < 2:
        raise ValueError('Each key must have multiple mixes')
    root, destination = Path(root), Path(destination)
    catalog = read_catalog(root)
    speakers = sorted(catalog, key=int)
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {'description': 'Concatenated EmoDB acted speech; labels describe source utterances, not A2E predictions.',
                'sample_rate': FORMAT[0], 'pause_seconds': pause_seconds, 'keys': {}}
    identities = set()
    for key in range(1, 6):
        mixes = []
        for index in range(mixes_per_key):
            speaker = speakers[((key - 1) * mixes_per_key + index) % len(speakers)]
            seed = key * 10007 + index * 101
            segments = plan_mix(catalog[speaker], seed, minimum_seconds, maximum_seconds, pause_seconds)
            identity = tuple(item['file'] for item in segments)
            if identity in identities:
                raise ValueError('Duplicate mix plan')
            identities.add(identity)
            name = f'key_{key}_mix_{index + 1:02d}.wav'
            mix = bake_mix(root, destination / name, segments, pause_seconds)
            mixes.append(dict(mix, speaker=speaker, seed=seed))
        manifest['keys'][str(key)] = mixes
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--mixes-per-key', type=int, required=True)
    parser.add_argument('--minimum-seconds', type=float, required=True)
    parser.add_argument('--maximum-seconds', type=float, required=True)
    parser.add_argument('--pause-seconds', type=float, required=True)
    args = parser.parse_args()
    result = build(args.root, args.destination, mixes_per_key=args.mixes_per_key,
                   minimum_seconds=args.minimum_seconds, maximum_seconds=args.maximum_seconds,
                   pause_seconds=args.pause_seconds)
    print(json.dumps({key: [round(m['seconds'], 2) for m in mixes] for key, mixes in result['keys'].items()}))
