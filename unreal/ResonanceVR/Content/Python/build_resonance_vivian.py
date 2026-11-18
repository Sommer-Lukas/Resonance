"""Give Vivian the existing portrait behavior through a child Blueprint.

Import /Game/MetaHumans/Vivian and its missing Common dependencies first.
The original imported Blueprints and the shared animation authority stay intact.
Run build(), then select_resonance_character.select() in I_Resonance.
"""
import json
import unreal
from build_pitfall import H, checked
import build_resonance_audio2face as ace

SOURCE = '/Game/MetaHumans/Vivian/BP_Vivian'


def components(bp):
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    library = unreal.SubobjectDataBlueprintFunctionLibrary
    result = {}
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp):
        data = subsystem.k2_find_subobject_data_from_handle(handle)
        name = str(library.get_variable_name(data))
        if name != 'None':
            result[name] = library.get_object_for_blueprint(data, bp)
    return result


def copy_properties(source, target, names):
    target.modify()
    for name in names:
        target.set_editor_property(name, source.get_editor_property(name))


def build():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError('Stop Play before building Vivian')
    source = unreal.load_asset(SOURCE)
    parent = unreal.load_asset(ace.RUNTIME_CHARACTER)
    if source is None or parent is None:
        raise RuntimeError('Import Vivian and the existing portrait before building')
    bp = unreal.load_asset(ace.CHARACTER)
    if bp is None:
        factory = unreal.BlueprintFactory()
        factory.set_editor_property('parent_class', parent.generated_class())
        folder, name = ace.CHARACTER.rsplit('/', 1)
        bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, folder, unreal.Blueprint, factory)
    if bp is None:
        raise RuntimeError('Could not create the Vivian portrait Blueprint')
    checked(H.compile_blueprint(bp))
    imported = components(source)
    target = components(bp)
    for name in ('Torso', 'Legs', 'Feet'):
        if name not in target:
            checked(H.add_component_to_blueprint(
                bp, '/Script/Engine.SkeletalMeshComponent', name,
                0, 0, 0, 0, 0, 0, 'Body'))
    target = components(bp)
    transform = ('relative_location', 'relative_rotation', 'relative_scale3d')
    for name in ('Body', 'Face', 'Torso', 'Legs', 'Feet'):
        copy_properties(imported[name], target[name], transform + (
            'skeletal_mesh_asset', 'override_materials', 'visible', 'hidden_in_game'))
        if name != 'Face':
            copy_properties(imported[name], target[name], ('anim_class', 'animation_mode'))
    # Retire the parent's outfit while retaining its component for inherited code.
    target['SkeletalMesh'].set_editor_property('skeletal_mesh_asset', None)
    target['SkeletalMesh'].set_editor_property('override_materials', [])
    for name in ('Hair', 'Eyebrows', 'Fuzz', 'Eyelashes', 'Mustache', 'Beard'):
        copy_properties(imported[name], target[name], transform + (
            'groom_asset', 'binding_asset', 'groom_groups_desc',
            'override_materials', 'visible', 'hidden_in_game'))
    copy_properties(imported['LODSync'], target['LODSync'], (
        'components_to_sync', 'custom_lod_mapping', 'num_lods', 'min_lod'))
    target['LODSync'].set_editor_property('forced_lod', ace.FORCED_LOD)
    target['Face'].set_editor_property('anim_class', unreal.load_asset(ace.FACE).generated_class())
    target['Face'].set_editor_property('visibility_based_anim_tick_option',
                                     unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    checked(H.compile_blueprint(bp))
    if not unreal.EditorAssetLibrary.save_loaded_asset(bp):
        raise RuntimeError('Could not save Vivian portrait')
    print(json.dumps({'character': ace.CHARACTER, 'appearance': SOURCE,
                      'behavior_parent': ace.RUNTIME_CHARACTER, 'forced_lod': ace.FORCED_LOD}))


if __name__ == '__main__':
    build()
