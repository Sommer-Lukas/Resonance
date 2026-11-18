"""Same-audio, explicitly authored emotion comparison in PIE (not inference validation)."""
import json
from pathlib import Path
import unreal
import preview_resonance_behavior as behavior

NAMES = ('neutral', 'fear', 'grief', 'sadness', 'disgust', 'pain')
_handle = None
_rows = []
_world = None
_start = 0.
_phase = -1
_names = NAMES
_phase_seconds = 15.


def finish(reason='complete'):
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
        behavior.resume()
    summary = {}
    for name in _names:
        rows = [r for r in _rows if r['emotion'] == name and r['age'] > 2]
        summary[name] = {
            'samples': len(rows),
            'range_degrees': [max(r['head'][a] for r in rows)-min(r['head'][a] for r in rows)
                              for a in range(3)] if rows else [],
            'range_pixels': [max(r['screen'][a] for r in rows)-min(r['screen'][a] for r in rows)
                             for a in range(2)] if rows else [],
            'looking_away_fraction': sum(r['away'] for r in rows)/len(rows) if rows else 0,
            'mean_pitch': sum(r['head'][0] for r in rows)/len(rows) if rows else 0,
            'seed': rows[0]['seed'] if rows else None,
        }
    passed = reason == 'complete' and all(s['samples'] > 20 and
        max(s['range_degrees'], default=0) > 1.5 for s in summary.values())
    folder = Path(unreal.Paths.project_saved_dir()) / 'EmotionMotionAudit'
    folder.mkdir(exist_ok=True)
    (folder / 'validation.json').write_text(json.dumps(
        {'passed': passed, 'reason': reason, 'summary': summary, 'samples': _rows}, indent=2), encoding='utf-8')
    unreal.log('Same-audio emotion motion: ' + json.dumps(summary))


def _tick(dt):
    global _phase
    if not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
        finish('PIE stopped')
        return
    elapsed = unreal.GameplayStatics.get_time_seconds(_world)-_start
    phase = int(elapsed/_phase_seconds)
    if phase >= len(_names):
        finish()
        return
    state = behavior._state()
    if phase != _phase:
        _phase = phase
        state.preview_emotion(_names[phase], 1.)
        state.get_owner().get_component_by_class(unreal.ResonanceAudioPlaylist).replay_current()
    face = next(c for c in state.get_owner().get_components_by_class(unreal.SkeletalMeshComponent)
                if c.get_name() == str(state.get_editor_property('face_component_name')))
    head = state.get_editor_property('head_degrees')
    pc = unreal.GameplayStatics.get_player_controller(_world, 0)
    screen = unreal.GameplayStatics.project_world_to_screen(pc, face.get_socket_location('FACIAL_C_NoseBridge'), False)
    if screen:
        _rows.append({'emotion': _names[phase], 'age': elapsed-phase*_phase_seconds,
                      'away': state.get_editor_property('looking_away'),
                      'seed': state.get_editor_property('active_behaviour_seed'),
                      'head': [head.x, head.y, head.z], 'screen': [screen.x, screen.y]})


def start(emotions=NAMES, seconds_per_emotion=15.):
    global _handle, _world, _start, _phase, _names, _phase_seconds
    if not emotions or seconds_per_emotion < 5:
        raise ValueError('Provide emotions and at least five seconds per emotion')
    if _handle is not None:
        finish('restarted')
    behavior._state()
    _world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    _start = unreal.GameplayStatics.get_time_seconds(_world)
    _phase = -1
    _names = tuple(emotions)
    _phase_seconds = seconds_per_emotion
    _rows.clear()
    _handle = unreal.register_slate_post_tick_callback(_tick)
