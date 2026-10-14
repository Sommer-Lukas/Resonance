"""PitFall player based on Epic's VR template, with Character stair collision.

Keep the template's actual Enhanced Input events and tracked hand components.
Editor helper compilation is not required; all runtime behavior is Blueprint.
"""
import json
import unreal
from build_pitfall import Graph, H, ROOT, DEPTH, START, blueprint, checked

PLAYER = ROOT + '/Blueprints/BP_PitFallTrackedPlayer'


def build_input():
    context = unreal.load_asset(ROOT + '/Input/IMC_PitFall')
    context.unmap_all()
    bindings = {
        'IA_Move': [('OculusTouch_Left_Thumbstick_Y', False), ('W', False), ('S', True)],
        'IA_Turn': [('OculusTouch_Right_Thumbstick_X', False), ('E', False), ('Q', True)],
        'IA_Menu_Toggle_Left': [('OculusTouch_Left_X_Click', False), ('R', False)],
    }
    for name, keys in bindings.items():
        action = unreal.load_asset('/Game/VRTemplate/Input/Actions/' + name)
        for key, negative in keys:
            k = unreal.Key()
            k.set_editor_property('key_name', key)
            mapping = context.map_key(action, k)
            modifiers = []
            if name in ['IA_Move', 'IA_Turn'] and 'Thumbstick' in key:
                deadzone = unreal.new_object(unreal.InputModifierDeadZone, outer=context)
                modifiers.append(deadzone)
            if negative:
                modifiers.append(unreal.new_object(unreal.InputModifierNegate, outer=context))
            mapping.set_editor_property('modifiers', modifiers)
            mappings = list(context.get_editor_property('mappings'))
            mappings[-1].set_editor_property('modifiers', modifiers)
            context.set_editor_property('mappings', mappings)
    context.set_editor_property('context_description', 'PitFall walking, snap turning and reset')
    unreal.EditorAssetLibrary.save_loaded_asset(context)
    # Register this context for OpenXR at startup; activate it only in this pawn.
    settings = unreal.get_default_object(unreal.load_class(None, '/Script/EnhancedInput.EnhancedInputDeveloperSettings'))
    defaults = list(settings.get_editor_property('DefaultMappingContexts'))
    for entry in defaults:
        if entry.get_editor_property('InputMappingContext') == context:
            entry.set_editor_property('bAddImmediately', False)
    settings.set_editor_property('DefaultMappingContexts', defaults)


def build_player():
    bp = unreal.load_asset(PLAYER)
    if bp is None:
        bp = unreal.EditorAssetLibrary.duplicate_asset('/Game/VRTemplate/Blueprints/VRPawn', PLAYER)
    if unreal.EditorAssetLibrary.get_metadata_tag(bp, 'PitFallVRVersion') != '1':
        unreal.BlueprintEditorLibrary.reparent_blueprint(bp, unreal.Character)
        checked(H.compile_blueprint(bp))
        g = Graph(bp, clear=False)
        info = json.loads(H.get_blueprint_graph_info(bp, 'EventGraph'))
        by_title = {n['node_title']: n for n in info['nodes']}

        def existing(key, title):
            g.nodes[key] = by_title[title]['node_name']

        existing('move_event', 'EnhancedInputAction IA_Move')
        existing('reset_event', 'EnhancedInputAction IA_Menu_Toggle_Left')
        existing('begin', 'Event BeginPlay')
        # Remove teleport execution and template menu from this exercise.
        for event in ['move_event', 'reset_event']:
            n = next(n for n in info['nodes'] if n['node_name'] == g.nodes[event])
            for pin in n['pins']:
                if pin['type'] == 'exec':
                    for link in pin.get('linked_to', []):
                        checked(H.remove_blueprint_node(bp, 'EventGraph', link['node_name']))
        # Register our context through the template's correctly typed subsystem.
        mapping = by_title['Add Mapping Context\nTarget is Enhanced Input Subsystem Interface']
        # There are two similarly titled calls; find the one using IMC_Default.
        mapping = next(n for n in info['nodes'] if any(p.get('default_object','').endswith('IMC_Default.IMC_Default') for p in n['pins']))
        g.nodes['mapping'] = mapping['node_name']
        checked(H.set_blueprint_node_pin_default(bp, 'EventGraph', mapping['node_name'], 'MappingContext', ROOT+'/Input/IMC_PitFall.IMC_PitFall'))
        checked(H.set_blueprint_node_pin_default(bp, 'EventGraph', mapping['node_name'], 'Priority', '10'))
        subsystem = next(n for n in info['nodes'] if n['node_class'] == 'K2Node_GetSubsystemFromPC')
        g.nodes['subsystem'] = subsystem['node_name']
        incoming = next(p for p in mapping['pins'] if p['pin_name'] == 'execute')['linked_to'][0]
        g.nodes['before_mapping'] = incoming['node_name']
        g.call('remove_default', 'EnhancedInputSubsystemInterface', 'RemoveMappingContext', MappingContext='/Game/VRTemplate/Input/IMC_Default.IMC_Default')
        g.wire('subsystem', 'ReturnValue', 'remove_default', 'self')
        g.flow('before_mapping', 'remove_default', 'mapping')
        # Movement uses the actual Enhanced Input ActionValue supplied by OpenXR.
        g.node('camera', 'VariableGet', variable_name='Camera')
        g.call('rot', 'SceneComponent', 'K2_GetComponentRotation')
        g.wire('camera', 'Camera', 'rot', 'self')
        g.call('breakrot', 'KismetMathLibrary', 'BreakRotator')
        g.wire('rot', 'ReturnValue', 'breakrot', 'InRot')
        g.call('yaw', 'KismetMathLibrary', 'MakeRotator')
        g.wire('breakrot', 'Yaw', 'yaw', 'Yaw')
        g.call('forward', 'KismetMathLibrary', 'GetForwardVector')
        g.wire('yaw', 'ReturnValue', 'forward', 'InRot')
        g.call('walk', 'Pawn', 'AddMovementInput')
        g.wire('move_event', 'Triggered', 'walk', 'execute')
        g.wire('move_event', 'ActionValue', 'walk', 'ScaleValue')
        g.wire('forward', 'ReturnValue', 'walk', 'WorldDirection')
        # Reset input uses the template's pressed trigger, not polling an XR key.
        g.call('reset_position', 'Actor', 'K2_SetActorLocation', NewLocation=','.join(str(v) for v in START), bSweep='false', bTeleport='true')
        g.call('reset_rotation', 'Actor', 'K2_SetActorRotation', NewRotation='0,90,0', bTeleportPhysics='true')
        g.node('movement', 'VariableGet', variable_name='CharacterMovement')
        g.call('stop', 'MovementComponent', 'StopMovementImmediately')
        g.wire('movement', 'CharacterMovement', 'stop', 'self')
        g.wire('reset_event', 'Triggered', 'reset_position', 'execute')
        g.flow('reset_position', 'reset_rotation', 'stop')
        # A recenter makes the physical tracking origin match the marked start.
        g.call('recenter', 'HeadMountedDisplayFunctionLibrary', 'ResetOrientationAndPosition', Yaw='0', Options='OrientationAndPosition')
        g.flow('stop', 'recenter')
        # Preserve the template BeginPlay, including HideLoadingScreen. A stale
        # loading layer can cover the live world on the headset while PC moves.
        old_begin = next(p for p in by_title['Event BeginPlay']['pins'] if p['pin_name']=='then')['linked_to'][0]
        g.nodes['old_begin'] = old_begin['node_name']
        g.node('setup', 'Sequence')
        g.flow('begin', 'setup')
        g.wire('setup', 'then_0', 'old_begin', old_begin['pin_name'])
        g.call('hide_loading', 'XRLoadingScreenFunctionLibrary', 'HideLoadingScreen')
        g.wire('setup', 'then_1', 'hide_loading', 'execute')
        g.call('hmd', 'HeadMountedDisplayFunctionLibrary', 'IsHeadMountedDisplayEnabled')
        g.node('desktop', 'Branch')
        g.flow('hide_loading', 'desktop')
        g.wire('hmd', 'ReturnValue', 'desktop', 'Condition')
        g.call('desktop_camera', 'SceneComponent', 'K2_SetRelativeLocation', NewLocation='0,0,170', bSweep='false', bTeleport='true')
        g.wire('camera', 'Camera', 'desktop_camera', 'self')
        g.wire('desktop', 'else', 'desktop_camera', 'execute')
        # Desktop Play skips the template's HMD branch. Activate our context too.
        g.wire('desktop_camera', 'then', 'remove_default', 'execute')
        g.node('tick', 'Event', event_name='ReceiveTick')
        g.call('position', 'Actor', 'K2_GetActorLocation')
        g.call('xyz', 'KismetMathLibrary', 'BreakVector')
        g.wire('position', 'ReturnValue', 'xyz', 'InVec')
        g.call('below', 'KismetMathLibrary', 'Less_DoubleDouble', B=str(-DEPTH-300))
        g.wire('xyz', 'Z', 'below', 'A')
        g.node('fall', 'Branch')
        g.flow('tick', 'fall')
        g.wire('below', 'ReturnValue', 'fall', 'Condition')
        g.wire('fall', 'then', 'reset_position', 'execute')
        unreal.EditorAssetLibrary.set_metadata_tag(bp, 'PitFallVRVersion', '1')
    # The existing pawn may have been authored for a shallower shaft. Refresh
    # its fall threshold on every rebuild without replacing template logic.
    info = json.loads(H.get_blueprint_graph_info(bp, 'EventGraph'))
    below = next(n for n in info['nodes'] if any(
        p.get('pin_name') == 'A' and any(
            link.get('pin_name') == 'Z' for link in p.get('linked_to', []))
        for p in n['pins']) and any(
            p.get('pin_name') == 'B' for p in n['pins']))
    checked(H.set_blueprint_node_pin_default(
        bp, 'EventGraph', below['node_name'], 'B', str(-DEPTH-300)))
    if unreal.EditorAssetLibrary.get_metadata_tag(bp, 'PitFallSnapHeight') != '1':
        # The template's floor-root math must preserve the Character capsule's
        # altitude instead of subtracting the VROrigin's -88 cm offset twice.
        snap = Graph(bp, clear=False, graph_name='SnapTurn')
        snap.nodes['computed'] = 'K2Node_CommutativeAssociativeBinaryOperator_1'
        snap.nodes['actor_location'] = 'K2Node_CallFunction_28'
        snap.nodes['set_location'] = 'K2Node_CallFunction_9'
        snap.call('xy', 'KismetMathLibrary', 'BreakVector')
        snap.wire('computed', 'ReturnValue', 'xy', 'InVec')
        snap.call('altitude', 'KismetMathLibrary', 'BreakVector')
        snap.wire('actor_location', 'ReturnValue', 'altitude', 'InVec')
        snap.call('capsule_position', 'KismetMathLibrary', 'MakeVector')
        snap.wire('xy', 'X', 'capsule_position', 'X')
        snap.wire('xy', 'Y', 'capsule_position', 'Y')
        snap.wire('altitude', 'Z', 'capsule_position', 'Z')
        snap.wire('capsule_position', 'ReturnValue', 'set_location', 'NewLocation')
        unreal.EditorAssetLibrary.set_metadata_tag(bp, 'PitFallSnapHeight', '1')
    checked(H.set_component_property(bp, 'VROrigin', 'RelativeLocation', '(X=0,Y=0,Z=-88)'))
    checked(H.set_component_property(bp, 'Camera', 'bLockToHmd', 'true'))
    checked(H.set_component_property(bp, 'HeadMountedDisplayMesh', 'bHiddenInGame', 'true'))
    checked(H.compile_blueprint(bp))
    cdo = unreal.get_default_object(bp.generated_class())
    checked(H.set_blueprint_cdo_property(bp, 'SnapTurnDegrees', '-30'))
    cdo.set_editor_property('use_controller_rotation_yaw', False)
    movement = cdo.get_editor_property('character_movement')
    movement.set_editor_property('max_walk_speed', 100)
    movement.set_editor_property('max_step_height', 30)
    movement.set_editor_property('max_acceleration', 400)
    movement.set_editor_property('walkable_floor_angle', 45)
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    gm = blueprint('BP_PitFallGameMode', unreal.GameModeBase)
    checked(H.set_blueprint_cdo_property(gm, 'DefaultPawnClass', bp.generated_class().get_path_name()))
    checked(H.compile_blueprint(gm))
    unreal.EditorAssetLibrary.save_loaded_asset(gm)
    return gm.generated_class()


def main():
    build_input()
    mode = build_player()
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_name() != 'PitFallUebung':
        raise RuntimeError('Open PitFallUebung before applying the player fix')
    world.get_world_settings().set_editor_property('default_game_mode', mode)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    print(json.dumps({'success':True,'player':PLAYER,'hands':'VR template tracked controller hands','input':'Enhanced Input action events'}))


if __name__ == '__main__':
    main()
