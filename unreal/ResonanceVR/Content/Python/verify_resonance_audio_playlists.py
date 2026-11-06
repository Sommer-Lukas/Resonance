"""PIE test: one-shot base, a complete three-mix set, then actual keys 2–5.

Uses player input delivery, not direct calls to the playlist selector.
Evidence is written under Saved/AudioPlaylists. Run start() just after PIE begins.
"""
import json
import time
from pathlib import Path
import unreal
import build_resonance_audio2face as ace

_handle = None
_playlist = _state = _world = None
_start = 0.0
_stage = 'base'
_set_started = 0.0
_release = None
_samples = []
_checks = {}
_tested_keys = []
_last_sample = 0.0
_starts_before_key = 0


def press(key):
    global _release, _starts_before_key
    _starts_before_key = _playlist.get_editor_property('PlaybackStarts')
    name = ('One', 'Two', 'Three', 'Four', 'Five')[key - 1]
    unreal.ResonanceFaceEditorLibrary.send_pie_key(name, True)
    _release = (name, time.monotonic() + .10)


def finish(reason='complete'):
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    if _release:
        unreal.ResonanceFaceEditorLibrary.send_pie_key(_release[0], False)
    _checks['completed'] = reason == 'complete'
    folder = Path(unreal.Paths.project_saved_dir()) / 'AudioPlaylists'
    folder.mkdir(exist_ok=True)
    (folder / 'validation.json').write_text(json.dumps({
        'passed': all(_checks.values()), 'reason': reason, 'checks': _checks,
        'tested_keys': _tested_keys, 'samples': _samples}, indent=2), encoding='utf-8')
    unreal.log('Audio playlist checks: ' + json.dumps(_checks))


def _tick(_dt):
    global _stage, _set_started, _release, _last_sample
    now = time.monotonic()
    elapsed = now - _start
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None:
        finish('PIE stopped')
        return
    if _release and now >= _release[1]:
        unreal.ResonanceFaceEditorLibrary.send_pie_key(_release[0], False)
        _release = None
    group = _playlist.get_editor_property('ActiveSet')
    index = _playlist.get_editor_property('MixIndex')
    starts = _playlist.get_editor_property('PlaybackStarts')
    completed = _playlist.get_editor_property('CompletedMixes')
    active = _playlist.get_editor_property('bPlaylistActive')
    if now - _last_sample >= .2:
        _last_sample = now
        _samples.append({'elapsed': elapsed, 'stage': _stage, 'set': group, 'mix': index + 1,
                         'starts': starts, 'completed_mixes': completed, 'active': active,
                         'path': _playlist.get_requested_audio_path(),
                         'has_emotion': _state.get_editor_property('bHasAutomaticEmotion')})
    if _stage == 'base' and elapsed >= 43:
        _checks['base_once_no_36_second_replay'] = starts == 1 and completed == 1 and group == 0 and not active
        _checks['base_is_original_clip'] = _playlist.get_requested_audio_path() == 'Resonance/Audio/voice_test.wav'
        _stage = 'set_one'
        _set_started = now
        press(1)
    elif _stage == 'set_one':
        if group == 1 and not active and completed == 3:
            _checks['key_one_plays_three_consecutive_mixes'] = True
            _checks['set_order'] = list(dict.fromkeys(s['mix'] for s in _samples if s['set'] == 1)) == [1, 2, 3]
            _checks['facial_emotion_still_enabled'] = _state.get_editor_property('bHasAutomaticEmotion')
            _tested_keys.append(1)
            _stage = 'other_keys'
            _set_started = now
            press(2)
        elif now - _set_started > 160:
            finish('set one did not finish all three mixes')
    elif _stage == 'other_keys':
        expected = len(_tested_keys) + 1
        if group == expected and now - _set_started >= 3 and starts > _starts_before_key:
            _tested_keys.append(expected)
            _checks['key_' + str(expected) + '_starts_its_set'] = index == 0 and active
            if expected == 5:
                finish()
            else:
                _set_started = now
                press(expected + 1)
        elif now - _set_started > 20:
            finish('number key did not start its set')
    if elapsed > 260:
        finish('timeout')


def start():
    global _handle, _playlist, _state, _world, _start, _stage, _last_sample, _release
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
    _world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    actor = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(_world, unreal.Actor)
                 if a.get_class() == unreal.load_asset(ace.CHARACTER).generated_class())
    _playlist = actor.get_component_by_class(unreal.ResonanceAudioPlaylist)
    _state = actor.get_component_by_class(unreal.ResonanceFaceState)
    _samples.clear()
    _checks.clear()
    _tested_keys.clear()
    _start = time.monotonic()
    _last_sample = 0.0
    _stage = 'base'
    _release = None
    _handle = unreal.register_slate_post_tick_callback(_tick)
