"""Wire number-key playlists and save only the portrait's assets."""
import json
from pathlib import Path
import unreal
from build_pitfall import H, checked
import build_resonance_audio2face as ace
import build_resonance_face_modes as modes


def build():
    manifest_path = Path(unreal.Paths.project_content_dir()) / 'Resonance/Audio/MixedEmotionSets/manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if set(manifest['keys']) != set('12345') or any(len(m) != 3 for m in manifest['keys'].values()):
        raise RuntimeError('Generate all five three-mix sets first')
    modes.build_character()
    viewer = unreal.load_asset(modes.VIEWER)
    modes.clean(viewer, ('ResonanceAudioPlaylistInputNodes',))
    g = modes.OwnedGraph(viewer, 'ResonanceAudioPlaylistInputNodes')
    for index, name in enumerate(('One', 'Two', 'Three', 'Four', 'Five'), 1):
        key = 'audio_key_' + str(index)
        g.node(key, 'InputKey', key_name=name)
        g.call(key + '_play', 'ResonanceAudioPlaylist', 'PlayPortraitSet', Set=index)
        g.wire(key, 'Pressed', key + '_play', 'execute')
    checked(H.compile_blueprint(viewer))
    unreal.EditorAssetLibrary.save_loaded_asset(viewer)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if levels.get_current_level().get_outer().get_name() == 'I_Resonance':
        levels.save_current_level()
    print(json.dumps({'success': True, 'keys': '1-5', 'mixes_per_set': 3, 'base': 'voice_test.wav once'}))


if __name__ == '__main__':
    build()
