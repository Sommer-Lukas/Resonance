"""Build the stationary portrait viewer; runtime behavior is compiled Blueprint.

The initial headset pose is removed once from the tracking origin, so the
headset starts at the authored eye position without adding physical eye height.
Subsequent headset translation and rotation remain tracked normally.
"""
import json
import unreal
from build_pitfall import Graph, H, checked

ROOT = '/Game/Resonance/Blueprints'
PATH = ROOT + '/BP_ResonanceViewer'


def build():
    bp = unreal.load_asset(PATH)
    if bp is None:
        factory = unreal.BlueprintFactory()
        factory.set_editor_property('parent_class', unreal.Pawn)
        bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            'BP_ResonanceViewer', ROOT, unreal.Blueprint, factory)
        checked(H.add_component_to_blueprint(
            bp, '/Script/Engine.SceneComponent', 'TrackingOrigin',
            0, 0, 0, 0, 0, 0, ''))
        checked(H.add_component_to_blueprint(
            bp, '/Script/Engine.CameraComponent', 'Camera',
            0, 0, 0, 0, 0, 0, 'TrackingOrigin'))
    checked(H.set_component_property(bp, 'Camera', 'bLockToHmd', 'true'))
    checked(H.set_component_property(bp, 'Camera', 'bUsePawnControlRotation', 'false'))
    checked(H.set_component_property(bp, 'Camera', 'FieldOfView', '45'))
    checked(H.compile_blueprint(bp))

    g = Graph(bp)
    g.node('begin', 'Event', event_name='ReceiveBeginPlay')
    g.call('enabled', 'HeadMountedDisplayFunctionLibrary', 'IsHeadMountedDisplayEnabled')
    g.node('vr', 'Branch')
    g.wire('begin', 'then', 'vr', 'execute')
    g.wire('enabled', 'ReturnValue', 'vr', 'Condition')
    g.call('wait', 'KismetSystemLibrary', 'Delay', Duration=0.2)
    g.wire('vr', 'then', 'wait', 'execute')
    g.call('valid', 'HeadMountedDisplayFunctionLibrary', 'HasValidTrackingPosition')
    g.node('tracked', 'Branch')
    g.wire('wait', 'then', 'tracked', 'execute')
    g.wire('valid', 'ReturnValue', 'tracked', 'Condition')
    g.wire('tracked', 'else', 'wait', 'execute')
    g.call('pose', 'HeadMountedDisplayFunctionLibrary', 'GetOrientationAndPosition')
    g.call('break', 'KismetMathLibrary', 'BreakRotator')
    g.wire('pose', 'DeviceRotation', 'break', 'InRot')
    g.call('yaw', 'KismetMathLibrary', 'Multiply_DoubleDouble', B=-1)
    g.wire('break', 'Yaw', 'yaw', 'A')
    g.call('rotation', 'KismetMathLibrary', 'MakeRotator', Roll=0, Pitch=0)
    g.wire('yaw', 'ReturnValue', 'rotation', 'Yaw')
    g.call('negative', 'KismetMathLibrary', 'NegateVector')
    g.wire('pose', 'DevicePosition', 'negative', 'A')
    g.call('offset', 'KismetMathLibrary', 'RotateAngleAxis', Axis='0,0,1')
    g.wire('negative', 'ReturnValue', 'offset', 'InVect')
    g.wire('yaw', 'ReturnValue', 'offset', 'AngleDeg')
    g.node('origin', 'VariableGet', variable_name='TrackingOrigin')
    g.call('set_rotation', 'SceneComponent', 'K2_SetRelativeRotation')
    g.call('set_location', 'SceneComponent', 'K2_SetRelativeLocation')
    for key in ['set_rotation', 'set_location']:
        g.wire('origin', 'TrackingOrigin', key, 'self')
    g.wire('rotation', 'ReturnValue', 'set_rotation', 'NewRotation')
    g.wire('offset', 'ReturnValue', 'set_location', 'NewLocation')
    g.wire('tracked', 'then', 'set_rotation', 'execute')
    g.flow('set_rotation', 'set_location')
    checked(H.compile_blueprint(bp))
    unreal.EditorAssetLibrary.save_loaded_asset(bp)

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    camera = next(a for a in actors.get_all_level_actors()
                  if a.get_actor_label() == 'Resonance_FaceCamera')
    camera.set_editor_property('auto_activate_for_player', unreal.AutoReceiveInput.DISABLED)
    camera.get_component_by_class(unreal.CameraComponent).set_editor_property('lock_to_hmd', False)
    start = next(a for a in actors.get_all_level_actors() if isinstance(a, unreal.PlayerStart))
    start.set_actor_location(camera.get_actor_location(), False, False)
    start.set_actor_rotation(camera.get_actor_rotation(), False)
    gm = unreal.load_asset(ROOT + '/BP_ResonancePortraitGameMode')
    unreal.get_default_object(gm.generated_class()).set_editor_property('default_pawn_class', bp.generated_class())
    unreal.EditorAssetLibrary.save_loaded_asset(gm)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    print(json.dumps({'success': True, 'viewer': PATH}))


if __name__ == '__main__':
    build()
