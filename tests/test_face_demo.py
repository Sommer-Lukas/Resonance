"""Guard the baked showcase's ownership, eyelid safety and loop continuity."""
from pathlib import Path
import runpy


DEMO = runpy.run_path(str(Path(__file__).resolve().parents[1] /
    'unreal/ResonanceVR/Content/Python/resonance_face_demo.py'))
values = DEMO['values']


def test_demo_exercises_all_owned_regions_without_taking_speech_channels():
    samples = [values(i / 120) for i in range(int(DEMO['DURATION'] * 120))]
    for name in DEMO['CHANNELS']:
        assert not name.lower().startswith(('mouth', 'jaw', 'eyelook', 'head'))
        assert max(frame[name] for frame in samples) >= 0.5, name
        assert all(0 <= frame[name] <= 1 for frame in samples)


def test_blinks_close_both_eyes_and_suppress_competing_eyelid_shapes():
    for start in DEMO['BLINKS']:
        closed = values(start + 0.14)
        assert closed['EyeBlinkLeft'] == closed['EyeBlinkRight'] == 1
        for side in ('Left', 'Right'):
            assert closed['EyeWide' + side] == 0
            assert closed['EyeSquint' + side] == 0
        assert values(start + 0.3)['EyeBlinkLeft'] == 0


def test_loop_returns_to_neutral_and_remains_continuous():
    assert all(v == 0 for v in values(35.5).values())
    for t in (0, 1.64, 14, 19, 24, 28, 32, 35.5):
        a, b = values(t), values(t + DEMO['DURATION'])
        assert all(abs(a[name] - b[name]) < 1e-10 for name in a)
    previous = values(0)
    for i in range(1, int(DEMO['DURATION'] * 240) + 1):
        current = values(i / 240)
        assert max(abs(current[n] - previous[n]) for n in current) < 0.06
        previous = current
