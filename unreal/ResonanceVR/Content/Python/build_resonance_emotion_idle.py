"""Install native emotion fusion without replacing speech or input EventGraphs.

Run in the editor after applying patch_ace_emotion_transport.py and compiling.
"""
import json
import unreal
from build_pitfall import H, checked
import build_resonance_audio2face as ace


def build():
    face = unreal.load_asset(ace.FACE)
    result = unreal.ResonanceFaceEditorLibrary.install_fusion(face)
    if result:
        raise RuntimeError(result)
    checked(H.compile_blueprint(face))
    character = unreal.load_asset(ace.CHARACTER)
    components = checked(H.list_blueprint_components(character))['components']
    if not any(c['variable_name'] == 'ResonanceEmotionState' for c in components):
        checked(H.add_component_to_blueprint(character, '/Script/ResonanceFace.ResonanceFaceState',
                                           'ResonanceEmotionState', 0, 0, 0, 0, 0, 0, ''))
    checked(H.compile_blueprint(character))
    # Save the owned assets and the reconstructed portrait instance if open.
    unreal.EditorAssetLibrary.save_loaded_asset(face)
    unreal.EditorAssetLibrary.save_loaded_asset(character)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if levels.get_current_level().get_outer().get_name() == 'I_Resonance':
        levels.save_current_level()
    print(json.dumps({'success': True, 'profiles': 11, 'emotion_source': 'local ACE output',
                      'retain_last_emotion': True}))


if __name__ == '__main__':
    build()
