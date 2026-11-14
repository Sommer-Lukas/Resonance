"""PIE controls for any actor with ResonanceEmotionState; no runtime Python needed.

    import preview_resonance_behavior as behavior
    behavior.preview('angry', variant=1)  # or happy/sad/the ten dimension names
    behavior.preview('neutral', variant=-1)  # automatically vary all three
    behavior.resume()

Pass actor_label when the world contains multiple compatible actors. This does
not infer emotions or change the audio model. Calibration assets are persistent;
preview selections affect only the PIE instance.
"""
import unreal


def _state(actor_label=None):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError('Start PIE first')
    matches = []
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        state = actor.get_component_by_class(unreal.ResonanceFaceState)
        if state and (actor_label is None or actor.get_actor_label() == actor_label):
            matches.append(state)
    if len(matches) != 1:
        raise RuntimeError(f'Expected one compatible actor, found {len(matches)}; specify actor_label')
    return matches[0]


def preview(emotion='neutral', strength=.85, variant=-1, actor_label=None):
    if variant not in (-1, 0, 1, 2):
        raise ValueError('variant must be -1 (automatic) or 0, 1, 2')
    state = _state(actor_label)
    if not state.preview_emotion(emotion, strength):
        raise ValueError(f'Unsupported emotion: {emotion}')
    state.set_editor_property('preview_variant', variant)
    return snapshot(actor_label)


def resume(actor_label=None):
    state = _state(actor_label)
    state.set_editor_property('preview_variant', -1)
    state.resume_automatic_emotion()


def snapshot(actor_label=None):
    state = _state(actor_label)
    return {name: state.get_editor_property(name) for name in (
        'dominant_emotion', 'active_variant', 'head_degrees', 'emotion_blink',
        'current_blend', 'idle_curves')}


def create_calibration(asset_path='/Game/Resonance/Animation/DA_DefaultFaceCalibration'):
    """Create an editable per-face Data Asset; never overwrite an existing asset."""
    existing = unreal.load_asset(asset_path)
    if existing:
        if not isinstance(existing, unreal.ResonanceFaceCalibration):
            raise TypeError(f'{asset_path} is not a face calibration')
        return existing
    folder, name = asset_path.rsplit('/', 1)
    factory = unreal.DataAssetFactory()
    factory.set_editor_property('data_asset_class', unreal.ResonanceFaceCalibration)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, folder, unreal.ResonanceFaceCalibration, factory)
    if asset is None:
        raise RuntimeError(f'Could not create {asset_path}')
    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    return asset
