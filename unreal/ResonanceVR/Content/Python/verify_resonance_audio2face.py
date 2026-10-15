"""Sample final PIE curves, joint motion and actual animated skin parameters."""
import json
import time
from pathlib import Path
import unreal
import build_resonance_audio2face as ace
from resonance_face_demo import CHANNELS

_handle = None
_samples = []
_start = 0
_duration = 40
_mode = 'full-face'
_last = -1
_face = None
_provider = None
MATERIAL_PARAMETERS = (
    'head_wm1_normal_head_wm1_blink_L',
    'head_wm1_normal_head_wm1_browsRaiseInner_L',
    'head_wm1_normal_head_wm1_browsRaiseOuter_L',
    'head_wm2_normal_head_wm2_browsDown_L',
    'head_wm2_normal_head_wm2_noseWrinkler_L',
    'head_wm3_normal_head_wm3_cheekRaiseUpper_L',
)
BONES = ('FACIAL_C_Jaw', 'FACIAL_L_EyelidUpperA', 'FACIAL_L_ForeheadInSkin',
         'FACIAL_L_CheekOuter', 'FACIAL_L_NoseUpper')


def _tick(_delta):
    global _handle, _last, _face
    elapsed = time.monotonic() - _start
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None and _samples:
        finish()
        return
    if world and elapsed - _last >= 0.010:
        _last = elapsed
        if _face is None:
            for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
                if actor.get_class() == unreal.load_asset(ace.CHARACTER).generated_class():
                    _face = next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Face')
                    break
        if _face:
            anim = _face.get_anim_instance()
            material = next((m for i in range(_face.get_num_materials())
                             if (m := _face.get_material(i)) is not None
                             and f'Skin_Baked_LOD{ace.FORCED_LOD}' in m.get_name()), _face.get_material(0))
            positions = {}
            for bone in BONES:
                p = _face.get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_COMPONENT).translation
                positions[bone] = [p.x, p.y, p.z]
            _samples.append({
                'wall_seconds': round(elapsed, 3),
                'game_seconds': unreal.GameplayStatics.get_time_seconds(world),
                'authored': _face.get_owner().get_editor_property('FaceDemoAuthored'),
                'fusion_alpha': anim.get_editor_property('DemoAlpha'),
                'procedural_blink': anim.get_editor_property('NaturalBlink'),
                'curves': {n: anim.get_curve_value(n) for n in CHANNELS + ('JawOpen', 'MouthClose')},
                'joints': positions,
                'skin': {n: material.get_scalar_parameter_value(n) for n in MATERIAL_PARAMETERS},
            })
    if elapsed >= _duration:
        finish()


def finish():
    global _handle, _face
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    result = {'provider': _provider, 'wav': ace.WAV, 'mode': _mode,
              'character': ace.CHARACTER, 'forced_lod': ace.FORCED_LOD,
              'note': 'Final output includes the procedural blink input in Y; not raw model predictions.',
              'face_parameters': dict(ace.MODEL_FACE_PARAMETERS),
              'emotion_parameters': ace.MODEL_EMOTION, 'samples': _samples}
    gaps = [b['wall_seconds'] - a['wall_seconds'] for a, b in zip(_samples, _samples[1:])]
    result['sampling'] = {
        'maximum_gap_seconds': max(gaps, default=0),
        'mean_gap_seconds': sum(gaps) / len(gaps) if gaps else None,
        'note': 'Final-pose samples, not every model frame. Sparse sampling can miss short blinks.',
    }
    for category in ('curves', 'skin'):
        result[category + '_range'] = {
            n: [min(s[category][n] for s in _samples), max(s[category][n] for s in _samples)]
            for n in (_samples[0][category] if _samples else {})}
    dest = Path(unreal.Paths.project_saved_dir()) / ('Audio2Face-' + _mode + '.json')
    dest.write_text(json.dumps(result, indent=2), encoding='utf-8')
    _face = None
    unreal.log('ACE face verification written to ' + str(dest))


def start(mode='full-face', duration=40):
    global _handle, _start, _duration, _mode, _last, _face, _provider
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
    _samples.clear()
    _face = None
    _last = -1
    _mode, _duration = mode, duration
    _provider = ace.PROVIDER
    _start = time.monotonic()
    _handle = unreal.register_slate_post_tick_callback(_tick)
