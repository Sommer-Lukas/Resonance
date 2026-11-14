"""Capture final head pose and curves for 33 forced profiles in PIE.

start(seconds_per_variant=3.0) advances on game time, not wall time. Results
are written to Saved/EmotionBehavior/validation.json. This tests animation
integration, not automatic emotion inference or perceptual realism.
"""
import json
from pathlib import Path
import unreal
import preview_resonance_behavior as behavior

NAMES = ('amazement', 'anger', 'cheekiness', 'disgust', 'fear', 'grief',
         'joy', 'outofbreath', 'pain', 'sadness', 'neutral')
_handle = None
_samples = []
_state = _face = _world = None
_start = 0.0
_seconds = 3.0
_index = -1
_actor_label = None


def finish(reason='complete'):
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    if _state:
        _state.set_editor_property('preview_variant', -1)
        _state.resume_automatic_emotion()
    groups = {i: [s for s in _samples if s['index'] == i] for i in range(33)}
    quats = [s['head_quaternion'] for s in _samples]
    checks = {
        'complete': reason == 'complete',
        'all_33_profiles_sampled': all(groups.values()),
        'final_head_moves': bool(quats) and any(
            max(q[a] for q in quats) - min(q[a] for q in quats) > .001 for a in range(4)),
        'head_is_bounded': bool(_samples) and all(
            abs(v) <= limit + .001 for s in _samples
            for v, limit in zip(s['head_degrees'], (5, 5, 3))),
        'final_expression_active': bool(_samples) and any(
            s['brow_down'] > .1 or s['cheek'] > .1 for s in _samples),
        'blink_reaches_closure': any(s['blink'] > .9 and min(s['eye_blinks']) > .9 for s in _samples),
    }
    folder = Path(unreal.Paths.project_saved_dir()) / 'EmotionBehavior'
    folder.mkdir(exist_ok=True)
    result = {'passed': all(checks.values()), 'reason': reason, 'checks': checks, 'samples': _samples}
    (folder / 'validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    unreal.log('Emotion behaviour verification: ' + json.dumps(checks))
    return checks


def _tick(_dt):
    global _index, _state, _face
    if not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
        finish('PIE stopped')
        return
    elapsed = unreal.GameplayStatics.get_time_seconds(_world) - _start
    index = int(elapsed / _seconds)
    if index >= 33:
        finish()
        return
    # PIE startup can reconstruct character components after the callback was
    # registered. Resolve the live component rather than sampling a stale one.
    live_state = behavior._state(_actor_label)
    if live_state != _state:
        _state = live_state
        _index = -1
    candidates = [c for c in _state.get_owner().get_components_by_class(unreal.SkeletalMeshComponent)
                  if c.get_anim_instance() and 'ResonanceFace' in c.get_anim_instance().get_class().get_name()]
    if len(candidates) != 1:
        return
    _face = candidates[0]
    if index != _index:
        _index = index
        _state.preview_emotion(NAMES[index // 3], .85)
        _state.set_editor_property('preview_variant', index % 3)
    head = _state.get_editor_property('head_degrees')
    q = _face.get_socket_transform('head', unreal.RelativeTransformSpace.RTS_COMPONENT).rotation
    anim = _face.get_anim_instance()
    _samples.append({'time': elapsed, 'index': index, 'emotion': NAMES[index // 3],
        'variant': index % 3, 'head_degrees': [head.x, head.y, head.z],
        'head_quaternion': [q.x, q.y, q.z, q.w],
        'blink': _state.get_editor_property('emotion_blink'),
        'eye_blinks': [anim.get_curve_value(n) for n in ('EyeBlinkLeft', 'EyeBlinkRight')],
        'brow_down': anim.get_curve_value('BrowDownLeft'),
        'cheek': anim.get_curve_value('CheekSquintLeft')})


def start(seconds_per_variant=3.0, actor_label=None):
    global _handle, _state, _face, _world, _start, _seconds, _index, _actor_label
    if seconds_per_variant < 2.0:
        raise ValueError('Allow at least two game seconds per variant')
    if _handle is not None:
        finish('restarted')
    _state = behavior._state(actor_label)
    _actor_label = actor_label
    _world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    candidates = [c for c in _state.get_owner().get_components_by_class(unreal.SkeletalMeshComponent)
                  if c.get_anim_instance() and 'ResonanceFace' in c.get_anim_instance().get_class().get_name()]
    if len(candidates) != 1:
        raise RuntimeError('Expected one Resonance face animation component')
    _face = candidates[0]
    _samples.clear()
    _seconds = seconds_per_variant
    _index = -1
    _start = unreal.GameplayStatics.get_time_seconds(_world)
    _handle = unreal.register_slate_post_tick_callback(_tick)
