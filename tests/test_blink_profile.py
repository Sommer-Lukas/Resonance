"""Profile safety invariants for the native blink curve baked by the builder."""
import runpy
from pathlib import Path

PROFILE = runpy.run_path(str(Path(__file__).resolve().parents[1] /
    'unreal/ResonanceVR/Content/Python/resonance_blink.py'))


def test_blink_is_bounded_and_reopens():
    closure = PROFILE['closure']
    assert all(0 <= closure(i / 1000) <= 1 for i in range(-1000, 2001))
    assert closure(-1) == closure(0) == closure(1) == closure(2) == 0
    assert closure(.22) == closure(.32) == 1


def test_blink_has_fast_close_and_longer_reopening_without_overlap():
    closure = PROFILE['closure']
    assert all(closure(i / 1000) <= closure((i + 1) / 1000) for i in range(220))
    assert all(closure(i / 1000) >= closure((i + 1) / 1000) for i in range(320, 1000))
    assert PROFILE['DURATION'][1] < PROFILE['PAUSE'][0]
    assert PROFILE['FIRST_PAUSE'][0] > 0
