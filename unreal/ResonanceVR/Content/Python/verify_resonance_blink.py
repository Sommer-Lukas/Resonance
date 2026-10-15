"""Editor verification of actual native scheduler and final MetaHuman curves."""
import json
import time
from pathlib import Path
import unreal
from resonance_face_demo import values
import build_resonance_audio2face as ace

_handle = None
_samples = []
_events = []
_start = 0
_actor = None
_face = None
_replay_kept_clock = False


def finish():
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    native = [s for s in _samples if s['alpha'] == 0]
    closed = [s for s in native if s['natural'] > 0.90]
    starts = {}
    for s in _samples:
        if s['started'] > 0:
            starts[s['started']] = (s['duration'], s['strength'], s['next'] - s['started'])
    pauses = [v[2] for v in starts.values()]
    authored = [s for s in _samples if s['alpha'] == 1]
    checks = {
        'complete_run': bool(_samples and _samples[-1]['elapsed'] >= 41.5),
        'multiple_blinks': len(starts) >= 5,
        'bounded_random_pauses': bool(pauses) and all(2.8 <= p <= 6.5 for p in pauses),
        'varied_pauses': len(pauses) >= 3 and max(pauses) - min(pauses) > 0.15,
        'bounded_random_duration': bool(starts) and all(.24 <= v[0] <= .34 for v in starts.values()),
        'near_full_bilateral_closure': bool(closed) and all(min(s['left'], s['right']) >= .89 for s in closed),
        'eye_widening_suppressed': bool(closed) and all(max(s['wide_left'], s['wide_right']) <= 1 - s['natural'] + .01 for s in closed),
        'reopens_between_blinks': any(s['natural'] == 0 and min(s['left'], s['right']) < .3 for s in native),
        'authored_showcase_preserved': bool(authored) and max(s['authored_error'] for s in authored) < .025,
        'audio_replay_keeps_blink_clock': _replay_kept_clock,
    }
    result = {'passed': all(checks.values()), 'checks': checks,
              'character': ace.CHARACTER, 'forced_lod': ace.FORCED_LOD,
              'blink_events': [{'started': k, 'duration': v[0], 'strength': v[1], 'next_pause': v[2]}
                               for k, v in starts.items()], 'samples': _samples}
    path = Path(unreal.Paths.project_saved_dir()) / 'Natural-blink-validation.json'
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    unreal.log('Natural blink verification: ' + json.dumps(checks))


def _tick(_delta):
    global _replay_kept_clock
    elapsed = time.monotonic() - _start
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None:
        finish()
        return
    anim = _face.get_anim_instance()
    while _events and elapsed >= _events[0][0]:
        _, mode = _events.pop(0)
        before = anim.get_editor_property('BlinkNextTime')
        _actor.call_method('ResonanceUse' + mode + 'Face')
        if mode == 'Model':
            _replay_kept_clock = before == anim.get_editor_property('BlinkNextTime')
    expected = values(anim.get_editor_property('DemoTime'))
    _samples.append({
        'elapsed': elapsed, 'alpha': anim.get_editor_property('DemoAlpha'),
        'natural': anim.get_editor_property('NaturalBlink'),
        'started': anim.get_editor_property('BlinkStartedAt'),
        'next': anim.get_editor_property('BlinkNextTime'),
        'duration': anim.get_editor_property('BlinkDuration'),
        'strength': anim.get_editor_property('BlinkStrength'),
        'left': anim.get_curve_value('EyeBlinkLeft'), 'right': anim.get_curve_value('EyeBlinkRight'),
        'wide_left': anim.get_curve_value('EyeWideLeft'), 'wide_right': anim.get_curve_value('EyeWideRight'),
        'authored_error': max(abs(anim.get_curve_value(n) - v) for n, v in expected.items()),
    })
    if elapsed >= 42:
        finish()


def start():
    global _handle, _start, _actor, _face, _replay_kept_clock
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError('Start Play before verifying blinks')
    _actor = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                  if a.get_class() == unreal.load_asset(ace.CHARACTER).generated_class())
    _face = next(c for c in _actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Face')
    _actor.call_method('ResonanceUseModelFace')
    _replay_kept_clock = False
    _samples.clear()
    _events[:] = [(18, 'Authored'), (22, 'Model'), (30, 'Model')]
    _start = time.monotonic()
    _handle = unreal.register_slate_post_tick_callback(_tick)
