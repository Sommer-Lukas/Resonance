"""Check the VR menu build without entering VR. Prints one JSON line.

    import verify_resonance_ui; verify_resonance_ui.verify()
Headset checks (pointer feel, text size, frame time) still need VR Preview.
"""
import json
import unreal
from build_pitfall import H
import build_resonance_ui as ui
import build_resonance_audio2face as ace


def verify():
    problems = []
    for file in ui.TEXTURES:
        name = file.rsplit('.', 1)[0]
        if not unreal.EditorAssetLibrary.does_asset_exist(ui.TEX + '/' + name):
            problems.append('missing texture ' + name)
    widget = unreal.load_asset(ui.MENU_WIDGET)
    names = set()
    if widget is None:
        problems.append('missing ' + ui.MENU_WIDGET)
    else:
        names = {w['name'] for w in json.loads(H.umg_get_widget_info(widget))['widgets']}
        required = ['Stage', 'TopBar', 'StartButton'] + ['Screen' + s for s in ui.SCREENS] + \
                   ['Tab' + t for t in ui.TABS] + ['Tab%sLabel' % t for t in ui.TABS]
        problems += ['missing widget ' + n for n in required if n not in names]
        titles = {n['node_title'] for n in ace.info(widget, 'EventGraph')}
        problems += ['missing event Show' + s for s in ui.SCREENS
                     if not any(('Show' + s) in t for t in titles)]
    viewer = unreal.load_asset(ui.VIEWER)
    components = {c['variable_name'] for c in json.loads(H.list_blueprint_components(viewer))['components']}
    for hand in ui.SELECT:
        for part in ('Hand', 'Pointer'):
            if hand + part not in components:
                problems.append('viewer missing ' + hand + part)
    owned = unreal.EditorAssetLibrary.get_metadata_tag(viewer, 'ResonanceMenuInputNodes')
    if not owned:
        problems.append('viewer trigger input not wired (paste menu_input_nodes.txt, rerun build)')
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    menus = [a for a in actors if ui.TAG in [str(t) for t in a.tags]]
    if len(menus) != 1:
        problems.append('expected one Resonance_Menu actor in the level, found %d' % len(menus))
    print(json.dumps({'success': not problems, 'widgets': len(names), 'problems': problems}))
    return not problems


if __name__ == '__main__':
    verify()
