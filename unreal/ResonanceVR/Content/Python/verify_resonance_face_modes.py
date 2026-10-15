"""Exercise the actual Enhanced Input events in PIE, including rapid switches."""
import json
import time
from pathlib import Path
import unreal
import build_resonance_face_modes as modes
import build_resonance_audio2face as ace

_handle = None
_samples = []
_events = []
_started = 0
_last = -1
_actor = None
_face = None
_input = None


def _inject(mode):
    action = unreal.load_asset(modes.INPUT + '/IA_Face' + mode)
    _input.inject_input_vector_for_action(action, unreal.Vector(1, 0, 0), [], [])


def _finish():
    global _handle
    unreal.unregister_slate_post_tick_callback(_handle)
    _handle = None
    def window(a, b):
        return [s for s in _samples if a <= s['seconds'] <= b]
    checks = {
        'complete_run': bool(_samples) and _samples[-1]['seconds'] >= 23.8,
        'authored_action_received': any(s['authored'] for s in window(1.05, 1.3)),
        'model_action_received': any(not s['authored'] for s in window(1.4, 2.3)),
        'authored_fusion_enabled': bool(window(4, 18)) and all(s['alpha'] > 0.999 for s in window(4, 18)),
        'model_fusion_fully_bypassed': bool(window(21, 23.8)) and all(s['alpha'] == 0 for s in window(21, 23.8)),
        'replay_coalesced_while_sending': any(s['queued'] and s['sending'] for s in _samples),
        'timeline_restarted_on_selection': any(0 <= s['demo_time'] < 0.3 for s in window(2.55, 2.8)),
        'authored_brows_animate': max((s['brow'] for s in _samples), default=0) >= 0.79,
    }
    result = {'passed': all(checks.values()), 'checks': checks, 'samples': _samples,
              'character': ace.CHARACTER, 'forced_lod': ace.FORCED_LOD,
              'note': 'Enhanced Input injection; physical headset/controller not tested'}
    path = Path(unreal.Paths.project_saved_dir()) / 'Face-mode-validation.json'
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    unreal.log('Face mode verification: ' + json.dumps(checks))


def _tick(_delta):
    global _last
    elapsed = time.monotonic() - _started
    if not unreal.SystemLibrary.is_valid(_actor):
        _finish()
        return
    while _events and elapsed >= _events[0][0]:
        _, mode = _events.pop(0)
        _inject(mode)
    if elapsed - _last >= 0.025:
        _last = elapsed
        anim = _face.get_anim_instance()
        _samples.append({'seconds': round(elapsed, 3),
                         'authored': _actor.get_editor_property('FaceDemoAuthored'),
                         'alpha': anim.get_editor_property('DemoAlpha'),
                         'demo_time': anim.get_editor_property('DemoTime'),
                         'sending': _actor.get_editor_property('FaceAudioSending'),
                         'queued': _actor.get_editor_property('FaceAudioReplayQueued'),
                         'brow': anim.get_curve_value('BrowOuterUpLeft'),
                         'blink': anim.get_curve_value('EyeBlinkLeft')})
    if elapsed >= 24:
        _finish()


def start():
    global _handle, _started, _last, _actor, _face, _input
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError('Start Play before this verification')
    _actor = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                  if a.get_class() == unreal.load_asset(ace.CHARACTER).generated_class())
    _face = next(c for c in _actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Face')
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    api = unreal.get_default_object(unreal.load_class(None, '/Script/Engine.SubsystemBlueprintLibrary'))
    _input = api.call_method('GetLocalPlayerSubSystemFromPlayerController', (
        pc, unreal.load_class(None, '/Script/EnhancedInput.EnhancedInputLocalPlayerSubsystem')))
    if _input.has_mapping_context(unreal.load_asset(modes.CONTEXT)) is None:
        raise RuntimeError('Portrait input context is not active')
    _actor.call_method('ResonanceUseModelFace')
    _samples.clear()
    _events[:] = [(1.0, 'Authored'), (1.35, 'Model'), (2.5, 'Authored'), (20.0, 'Model')]
    _started, _last = time.monotonic(), -1
    _handle = unreal.register_slate_post_tick_callback(_tick)
