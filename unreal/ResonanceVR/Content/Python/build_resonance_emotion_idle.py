"""Install native emotion fusion without replacing speech or input EventGraphs.

Run in the editor after applying patch_ace_emotion_transport.py and compiling.
"""
import json
import unreal
from build_pitfall import H, checked
import build_resonance_audio2face as ace


def build(face_path=ace.FACE, character_path=ace.CHARACTER, calibration_path=None,
          source_postprocess='/Game/MetaHumans/Common/Face/ABP_Face_PostProcess',
          postprocess_path='/Game/Resonance/Animation/ABP_ResonanceFacePostProcess'):
    """Install the same fusion on a replacement face/character Blueprint pair."""
    face = unreal.load_asset(face_path)
    result = unreal.ResonanceFaceEditorLibrary.install_fusion(face)
    if result:
        raise RuntimeError(result)
    checked(H.compile_blueprint(face))
    postprocess = unreal.load_asset(postprocess_path)
    if postprocess is None:
        postprocess = unreal.EditorAssetLibrary.duplicate_asset(source_postprocess, postprocess_path)
    result = unreal.ResonanceFaceEditorLibrary.install_head_fusion(postprocess)
    if result:
        raise RuntimeError(result)
    checked(H.compile_blueprint(postprocess))
    character = unreal.load_asset(character_path)
    if character is None:
        raise RuntimeError(f'Missing character Blueprint: {character_path}')
    components = checked(H.list_blueprint_components(character))['components']
    if not any(c['variable_name'] == 'ResonanceEmotionState' for c in components):
        checked(H.add_component_to_blueprint(character, '/Script/ResonanceFace.ResonanceFaceState',
                                           'ResonanceEmotionState', 0, 0, 0, 0, 0, 0, ''))
    if calibration_path:
        from preview_resonance_behavior import create_calibration
        calibration = create_calibration(calibration_path)
        checked(H.set_component_property(character, 'ResonanceEmotionState', 'Calibration',
                                         "ResonanceFaceCalibration'" + calibration.get_path_name() + "'"))
    checked(H.set_component_property(character, 'ResonanceEmotionState', 'HeadPostProcessClass',
                                     postprocess.generated_class().get_path_name()))
    checked(H.compile_blueprint(character))
    # Existing placed instances can retain old component overrides after a
    # Blueprint recompile. Install explicitly on those instances as well.
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for actor in actors:
        if actor.get_class() == character.generated_class():
            state = actor.get_component_by_class(unreal.ResonanceFaceState)
            if state:
                state.modify()
                state.set_editor_property('head_post_process_class', postprocess.generated_class())
                if calibration_path:
                    state.set_editor_property('calibration', calibration)
    # Save the owned assets and the reconstructed portrait instance if open.
    unreal.EditorAssetLibrary.save_loaded_asset(face)
    unreal.EditorAssetLibrary.save_loaded_asset(character)
    unreal.EditorAssetLibrary.save_loaded_asset(postprocess)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if levels.get_current_level().get_outer().get_name() == 'I_Resonance':
        levels.save_current_level()
    print(json.dumps({'success': True, 'profiles': 11, 'emotion_source': 'local ACE output',
                      'retain_last_emotion': True}))


if __name__ == '__main__':
    build()
