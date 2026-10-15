"""Replace the portrait's previous client, retaining its authored eye line."""
import json
from pathlib import Path
import unreal
import build_resonance_audio2face as ace

PREVIOUS = '/Game/MetaHumans/4k_MetaHuman_Asian_Old/BP_4k_MetaHuman_Asian_Old'


def face_of(actor):
    return next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent)
                if c.get_name() == 'Face')


def eye_center(actor):
    face = face_of(actor)
    return (face.get_socket_location('FACIAL_L_Eye') +
            face.get_socket_location('FACIAL_R_Eye')) * 0.5


def select():
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_name() != 'I_Resonance':
        raise RuntimeError('Open I_Resonance before replacing the portrait character')
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        raise RuntimeError('Stop Play before changing the portrait character')
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    target_class = unreal.load_asset(ace.CHARACTER).generated_class()
    previous_class = unreal.load_asset(PREVIOUS).generated_class()
    existing = actors.get_all_level_actors()
    old = next((a for a in existing if a.get_class() == previous_class), None)
    new = next((a for a in existing if a.get_class() == target_class), None)
    if new is None and old is None:
        raise RuntimeError('No portrait character found to replace')
    with unreal.ScopedEditorTransaction('Select New_realistic_character for Resonance portrait'):
        if new is None:
            target_eye = eye_center(old)
            new = actors.spawn_actor_from_class(target_class, old.get_actor_location(), old.get_actor_rotation())
            new.set_actor_scale3d(old.get_actor_scale3d())
            new.set_actor_location(new.get_actor_location() + target_eye - eye_center(new), False, True)
        lod = new.get_component_by_class(unreal.LODSyncComponent)
        if lod is None:
            raise RuntimeError('The selected character must have LODSync')
        lod.set_editor_property('ForcedLOD', ace.FORCED_LOD)
        new.set_actor_label('Resonance_New_realistic_character')
        # The Blueprint owns the ACE component, face AnimClass and X/Y events.
        if face_of(new).get_editor_property('anim_class') != unreal.load_asset(ace.FACE).generated_class():
            raise RuntimeError('New character does not have the Resonance face animation')
        if old is not None:
            actors.destroy_actor(old)
        actors.set_selected_level_actors([new])
    result = {'character': ace.CHARACTER, 'forced_lod': lod.get_editor_property('ForcedLOD'),
              'location': str(new.get_actor_location()), 'eye_center': str(eye_center(new)),
              'previous_asset_preserved': PREVIOUS, 'saved_level': level.save_current_level()}
    (Path(unreal.Paths.project_saved_dir()) / 'Character-selection.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    select()
