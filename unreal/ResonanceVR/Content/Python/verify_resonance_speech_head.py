"""Record automatic speech/head behaviour, without cycling expression previews.

start() replays the current playlist clip through the existing ACE player.
Use the nine-second reference clip for the default 45-second recording. Evidence
is written under Saved/SpeechHead. No new audio player or microphone is used.
"""
import json
from pathlib import Path
import unreal
import preview_resonance_behavior as behavior

_handle = None
_samples = []
_world = None
_start = 0.0
_duration = 45.0
_actor_label = None
_base_cues = _base_quiet = 0


def finish(reason='complete'):
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    playing = [s for s in _samples if s['playing']]
    end = max((s['time'] for s in playing), default=0.0)
    tail = [s for s in _samples if s['time'] > end + 1.0]
    quats = [s['head_quaternion'] for s in _samples]
    screens = [s['nose_screen'] for s in _samples if s.get('nose_screen')]
    checks = {
        'complete': reason == 'complete',
        'audible_playback_observed': bool(playing),
        'speech_envelope_available': bool(_samples) and max(s['envelope'] for s in _samples) > .003,
        'voiced_and_quiet_observed': any(s['voiced'] for s in _samples) and any(not s['voiced'] for s in _samples),
        'speech_cues_observed': bool(_samples) and max(s['cues'] for s in _samples) > 0,
        'no_cue_loop_in_silent_tail': len(tail) > 10 and len({s['cues'] for s in tail}) == 1,
        'quiet_adjustments_observed': bool(tail) and
            max(s['quiet_adjustments'] for s in tail) > min(s['quiet_adjustments'] for s in tail),
        'quiet_head_is_visible': bool(tail) and any(
            max(s['head_degrees'][a] for s in tail) - min(s['head_degrees'][a] for s in tail) > .35
            for a in range(3)),
        'head_stays_within_face_limits': bool(_samples) and all(
            abs(v) <= limit + .001 for s in _samples for v, limit in zip(s['head_degrees'], s['limits'])),
        'final_head_moves': bool(quats) and any(
            max(q[a] for q in quats) - min(q[a] for q in quats) > .001 for a in range(4)),
        'visible_nose_displacement': bool(screens) and any(
            max(p[a] for p in screens) - min(p[a] for p in screens) >= 6.0 for a in range(2)),
    }
    folder = Path(unreal.Paths.project_saved_dir()) / 'SpeechHead'
    folder.mkdir(exist_ok=True)
    result = {'passed': all(checks.values()), 'reason': reason, 'checks': checks, 'samples': _samples}
    (folder / 'validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    unreal.log('Speech/head verification: ' + json.dumps(checks))
    return checks


def _tick(_dt):
    if not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
        finish('PIE stopped')
        return
    elapsed = unreal.GameplayStatics.get_time_seconds(_world) - _start
    if elapsed >= _duration:
        finish()
        return
    state = behavior._state(_actor_label)
    owner = state.get_owner()
    source = owner.get_component_by_class(unreal.ACEAudioCurveSourceComponent)
    faces = [c for c in owner.get_components_by_class(unreal.SkeletalMeshComponent)
             if c.get_name() == str(state.get_editor_property('face_component_name')) and c.get_anim_instance()]
    if len(faces) != 1:
        return
    calibration = state.get_editor_property('calibration')
    bone = calibration.get_editor_property('head_bone') if calibration else 'head'
    q = faces[0].get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_COMPONENT).rotation
    pc = unreal.GameplayStatics.get_player_controller(_world, 0)
    screen = unreal.GameplayStatics.project_world_to_screen(
        pc, faces[0].get_socket_location('FACIAL_C_NoseBridge'), False) if pc else None
    head = state.get_editor_property('head_degrees')
    limits = calibration.get_editor_property('head_limits') if calibration else unreal.Vector(5, 5, 3)
    _samples.append({'time': elapsed, 'playing': bool(source and source.is_emotion_playback_active()),
        'envelope': state.get_editor_property('speech_envelope'),
        'envelope_samples': state.get_editor_property('speech_envelope_samples'),
        'file_envelope': state.get_editor_property('speech_envelope_from_file'),
        'voiced': state.get_editor_property('speech_voiced'),
        'cues': max(0, state.get_editor_property('head_speech_cues') - _base_cues),
        'quiet_adjustments': max(0, state.get_editor_property('quiet_head_adjustments') - _base_quiet),
        'limits': [max(0, min(8, v)) for v in (limits.x, limits.y, limits.z)],
        'head_degrees': [head.x, head.y, head.z], 'head_quaternion': [q.x, q.y, q.z, q.w],
        'nose_screen': [screen.x, screen.y] if screen else None})


def start(seconds=45.0, actor_label=None, replay=True):
    global _handle, _world, _start, _duration, _actor_label, _base_cues, _base_quiet
    if seconds < 15:
        raise ValueError('Record at least fifteen game seconds')
    if _handle is not None:
        finish('restarted')
    state = behavior._state(actor_label)
    behavior.resume(actor_label)
    _base_cues = state.get_editor_property('head_speech_cues')
    _base_quiet = state.get_editor_property('quiet_head_adjustments')
    _actor_label = actor_label
    _world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    _start = unreal.GameplayStatics.get_time_seconds(_world)
    _duration = seconds
    _samples.clear()
    _handle = unreal.register_slate_post_tick_callback(_tick)
    if replay:
        playlist = state.get_owner().get_component_by_class(unreal.ResonanceAudioPlaylist)
        if playlist is None:
            finish('missing playlist')
            raise RuntimeError('This recording needs the existing speech playlist component')
        playlist.replay_current()
