"""Observe final Vivian eye/lid rig motion and coupled head travel in PIE.

Run start() after Play. Uses authored previews, not emotion inference evidence.
Results are local under Saved/EyeHeadVariation/validation.json.
"""
import json
from pathlib import Path
import unreal
import preview_resonance_behavior as behavior

EMOTIONS = ('neutral', 'fear', 'joy', 'sadness', 'anger', 'amazement')
CURVES = ('EyeLookDownLeft', 'EyeLookUpLeft', 'EyeLookInLeft', 'EyeLookOutLeft',
          'EyeBlinkLeft', 'EyeBlinkRight', 'EyeWideLeft', 'EyeSquintLeft',
          'BrowOuterUpLeft', 'CheekSquintLeft', 'JawOpen')
BONES = ('FACIAL_L_Eye', 'FACIAL_L_EyelidUpperA', 'FACIAL_L_EyelidLowerA')
_handle = None
_samples = []
_world = None
_start = 0.
_phase = -1
_seconds = 12.


def finish(reason='complete'):
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
        behavior.resume()
    summary = {}
    for emotion in EMOTIONS:
        rows = [s for s in _samples if s['emotion'] == emotion and s['age'] > 1.]
        # Inspect eyelids between full blinks so closure alone cannot pass.
        open_rows = [s for s in rows if s['blink'] < .05 and s['curves']['EyeBlinkLeft'] < .45]
        ranges = {name: max((r['curves'][name] for r in rows), default=0) -
                  min((r['curves'][name] for r in rows), default=0) for name in CURVES}
        bone_ranges = {name: [max((r['bones'][name][a] for r in open_rows), default=0) -
                             min((r['bones'][name][a] for r in open_rows), default=0)
                             for a in range(3)] for name in BONES}
        rotation_ranges = {name: [max((r['bone_rotations'][name][a] for r in open_rows), default=0) -
                                 min((r['bone_rotations'][name][a] for r in open_rows), default=0)
                                 for a in range(4)] for name in BONES}
        summary[emotion] = {'samples': len(rows), 'curve_ranges': ranges,
                            'open_eye_bone_ranges_cm': bone_ranges,
                            'open_eye_rotation_ranges': rotation_ranges,
                            'head_ranges_degrees': [max((r['head'][a] for r in rows), default=0) -
                                                   min((r['head'][a] for r in rows), default=0)
                                                   for a in range(3)]}
    checks = {
        'complete': reason == 'complete',
        'all_profiles_sampled': all(s['samples'] > 20 for s in summary.values()),
        'neutral_eyes_explore': max(summary['neutral']['curve_ranges'][n] for n in CURVES[:4]) > .025,
        # These eyelid joints rotate around an eye-centered pivot. Position
        # alone would falsely report a frozen lid when the joint rotates.
        'eyelids_move_between_blinks': all(max(s['open_eye_rotation_ranges']['FACIAL_L_EyelidUpperA']) > .001
                                          for s in summary.values()),
        'head_uses_all_axes': all(min(s['head_ranges_degrees']) > .05 for s in summary.values()),
        'head_within_limits': bool(_samples) and all(abs(v) <= limit + .001 for s in _samples
                                                    for v, limit in zip(s['head'], s['limits'])),
        'speech_articulation_present': any(s['curves']['JawOpen'] > .02 for s in _samples),
    }
    folder = Path(unreal.Paths.project_saved_dir()) / 'EyeHeadVariation'
    folder.mkdir(exist_ok=True)
    result = {'passed': all(checks.values()), 'reason': reason, 'checks': checks,
              'summary': summary, 'samples': _samples,
              'note': 'Authored previews and local audio; no human or headset evaluation.'}
    (folder / 'validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    unreal.log('Eye/head variation: ' + json.dumps(checks))
    return checks


def _tick(dt):
    global _phase
    if not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
        finish('PIE stopped')
        return
    elapsed = unreal.GameplayStatics.get_time_seconds(_world) - _start
    index = int(elapsed / _seconds)
    if index >= len(EMOTIONS):
        finish()
        return
    state = behavior._state()
    if index != _phase:
        _phase = index
        state.preview_emotion(EMOTIONS[index], 1., -1)
        state.get_owner().get_component_by_class(unreal.ResonanceAudioPlaylist).replay_current()
    face = next(c for c in state.get_owner().get_components_by_class(unreal.SkeletalMeshComponent)
                if c.get_name() == 'Face')
    anim = face.get_anim_instance()
    head_transform = face.get_socket_transform('head', unreal.RelativeTransformSpace.RTS_COMPONENT)
    bones = {}
    rotations = {}
    for name in BONES:
        if face.get_bone_index(name) < 0:
            raise RuntimeError('Missing required verification bone: ' + name)
        transform = face.get_socket_transform(name, unreal.RelativeTransformSpace.RTS_COMPONENT)
        local = head_transform.inverse_transform_location(transform.translation)
        bones[name] = [local.x, local.y, local.z]
        rotation = head_transform.rotation.inversed() * transform.rotation
        rotations[name] = [rotation.x, rotation.y, rotation.z, rotation.w]
    head = state.get_editor_property('head_degrees')
    calibration = state.get_editor_property('calibration')
    limits = calibration.get_editor_property('head_limits') if calibration else unreal.Vector(5, 5, 3)
    _samples.append({'emotion': EMOTIONS[index], 'age': elapsed-index*_seconds,
                     'head': [head.x, head.y, head.z], 'limits': [limits.x, limits.y, limits.z],
                     'blink': state.get_editor_property('emotion_blink'), 'bones': bones,
                     'bone_rotations': rotations,
                     'curves': {name: anim.get_curve_value(name) for name in CURVES}})


def start(seconds_per_emotion=12.):
    global _handle, _world, _start, _phase, _seconds
    if seconds_per_emotion < 10:
        raise ValueError('Allow at least ten seconds for varied eye holds')
    if _handle is not None:
        finish('restarted')
    behavior._state()
    _world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    _seconds = seconds_per_emotion
    _start = unreal.GameplayStatics.get_time_seconds(_world)
    _phase = -1
    _samples.clear()
    _handle = unreal.register_slate_post_tick_callback(_tick)
