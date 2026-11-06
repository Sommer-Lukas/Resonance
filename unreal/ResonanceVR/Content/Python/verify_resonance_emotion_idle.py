"""Capture automatic emotion, held idle and final MetaHuman curves in PIE.

start() runs asynchronously. Evidence is saved under Saved/EmotionIdle.
Manual profile checks are separate from evidence of automatic inference.
"""
import json
import time
from pathlib import Path
import unreal
import build_resonance_audio2face as ace

NAMES = ('amazement', 'anger', 'cheekiness', 'disgust', 'fear', 'grief',
         'joy', 'outofbreath', 'pain', 'sadness', 'neutral')
CURVES = ('BrowInnerUp', 'BrowOuterUpLeft', 'BrowOuterUpRight', 'BrowDownLeft',
          'BrowDownRight', 'EyeBlinkLeft', 'EyeBlinkRight', 'EyeWideLeft',
          'EyeWideRight', 'EyeLookDownLeft', 'EyeLookDownRight', 'EyeLookUpLeft',
          'EyeLookUpRight', 'EyeLookInLeft', 'EyeLookOutRight', 'EyeLookOutLeft',
          'EyeLookInRight', 'CheekSquintLeft', 'NoseSneerLeft', 'JawOpen', 'MouthClose')
_handle = None
_samples = []
_actor = _state = _source = _anim = None
_start = _hold_start = _manual_start = None
_game_start = 0.0
_last_profile = -1
_manual_results = []
_emotion_csv = ''


def finish(reason='complete'):
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    _state.resume_automatic_emotion()
    automatic = [s for s in _samples if s['stage'] == 'automatic' and s['has_emotion']]
    held = [s for s in automatic if not s['speaking']]
    closed = [s for s in automatic if s['natural_blink'] > .9]
    settled = {name: next((s for s in reversed(_samples) if s.get('manual_profile') == name), None)
               for name in NAMES}
    checks = {
        'completed': reason == 'complete',
        'actual_sdk_emotions': bool(automatic) and max(s['received'] for s in automatic) > 10,
        'ten_finite_scores': bool(automatic) and all(len(s['raw']) == 10 and
            all(0 <= x <= 1 for x in s['raw']) for s in automatic),
        'last_emotion_retained': len(held) > 20 and all(s['raw'] == held[0]['raw'] for s in held),
        'idle_eyes_move': len(held) > 20 and any(
            max(s['curves'][c] for s in held) - min(s['curves'][c] for s in held) > .002
            for c in CURVES if c.startswith('EyeLook')),
        'final_upper_face_active': bool(automatic) and max(
            s['curves']['BrowInnerUp'] + s['curves']['BrowDownLeft'] for s in automatic) > .01,
        'speech_articulation_active': bool(automatic) and max(s['curves']['JawOpen'] for s in automatic) > .02,
        'all_manual_profiles_accepted': len(_manual_results) == 11 and all(r['accepted'] for r in _manual_results),
        'manual_profiles_reach_target': all(s and s['dominant'] == name for name, s in settled.items()),
        'blink_closure': bool(closed) and all(min(s['curves']['EyeBlinkLeft'], s['curves']['EyeBlinkRight'])
            >= s['natural_blink'] - .001 for s in closed),
        'widening_suppressed_during_blink': bool(closed) and all(max(s['curves']['EyeWideLeft'], s['curves']['EyeWideRight'])
            <= 1 - s['natural_blink'] + .001 for s in closed),
        'conjugate_eyes': all(abs(s['curves']['EyeLookInLeft'] - s['curves']['EyeLookOutRight']) < .0001
            and abs(s['curves']['EyeLookOutLeft'] - s['curves']['EyeLookInRight']) < .0001 for s in _samples),
    }
    folder = Path(unreal.Paths.project_saved_dir()) / 'EmotionIdle'
    folder.mkdir(exist_ok=True)
    result = {'passed': all(checks.values()), 'reason': reason, 'checks': checks,
              'manual_profiles': _manual_results, 'samples': _samples,
              'emotion_csv': _emotion_csv or _source.export_emotion_stream()}
    (folder / 'validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    unreal.log('Emotion idle validation: ' + json.dumps(checks))


def _tick(_dt):
    global _hold_start, _manual_start, _last_profile, _emotion_csv
    elapsed = time.monotonic() - _start
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        finish('PIE stopped')
        return
    # Use the animation's game clock for settling times. Editor screenshots or
    # RPC stalls can advance wall time while the actual animation is paused.
    game_elapsed = unreal.GameplayStatics.get_time_seconds(world) - _game_start
    speaking = _source.is_emotion_playback_active()
    received = _source.get_editor_property('emotion_samples_received')
    has = _state.get_editor_property('has_automatic_emotion')
    if has and received > 10 and not speaking and _manual_start is None:
        if _hold_start is None:
            _hold_start = game_elapsed
        elif game_elapsed - _hold_start >= 6.5:
            # Preserve this complete clip before periodic autoplay starts another stream.
            _emotion_csv = _source.export_emotion_stream()
            _manual_start = game_elapsed
    elif speaking and _manual_start is None:
        _hold_start = None
    if _manual_start is not None:
        index = int((game_elapsed - _manual_start) / 2.0)
        if index >= len(NAMES):
            finish()
            return
        if index != _last_profile:
            _last_profile = index
            _manual_results.append({'name': NAMES[index], 'accepted': _state.preview_emotion(NAMES[index], .8)})
    _samples.append({
        'elapsed': elapsed, 'game_elapsed': game_elapsed,
        'stage': 'manual' if _manual_start is not None else 'automatic',
        'manual_profile': NAMES[_last_profile] if _manual_start is not None else None,
        'speaking': speaking, 'has_emotion': has, 'received': received,
        'emotion_time': _state.get_editor_property('emotion_audio_time'),
        'raw': list(_state.get_editor_property('emotion_scores')),
        'smoothed': list(_state.get_editor_property('smoothed_emotion_scores')),
        'dominant': str(_state.get_editor_property('dominant_emotion')),
        'blend': _state.get_editor_property('current_blend'),
        'natural_blink': _anim.get_editor_property('NaturalBlink'),
        'curves': {c: _anim.get_curve_value(c) for c in CURVES},
    })
    if elapsed > 100:
        finish('timeout waiting for automatic emotion/playback')


def start():
    global _handle, _start, _game_start, _hold_start, _manual_start, _last_profile, _actor, _state, _source, _anim, _emotion_csv
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError('Start PIE first')
    _actor = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                  if a.get_class() == unreal.load_asset(ace.CHARACTER).generated_class())
    _state = _actor.get_component_by_class(unreal.ResonanceFaceState)
    _source = _actor.get_component_by_class(unreal.ACEAudioCurveSourceComponent)
    if _state is None:
        raise RuntimeError('Run build_resonance_emotion_idle.build() first')
    face = next(c for c in _actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Face')
    _anim = face.get_anim_instance()
    _state.resume_automatic_emotion()
    _samples.clear()
    _manual_results.clear()
    _hold_start = _manual_start = None
    _last_profile = -1
    _emotion_csv = ''
    _start = time.monotonic()
    _game_start = unreal.GameplayStatics.get_time_seconds(world)
    _handle = unreal.register_slate_post_tick_callback(_tick)
