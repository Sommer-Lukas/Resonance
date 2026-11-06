"""Author pad-only teleportation using the VR template's runtime arc and ring.

Run through build_pitfall or main() with PitFallUebung open and PIE stopped.
All play behavior is saved Blueprint; editor Python is only a builder.
"""
import json
import unreal
from build_pitfall import Graph, H, ROOT, TAG, LEVEL, checked, blueprint, material

PAD = ROOT + '/Blueprints/BP_PitFallTeleportPad'
PLAYER = ROOT + '/Blueprints/BP_PitFallTrackedPlayer'
PADS = (
    ('Entrance', (0, -820, 2)),
    ('Overlook', (0, -460, 2)),
    ('West', (-800, -400, 2)),
    ('East', (800, -400, 2)),
    ('North', (0, 800, 2)),
)


def info(bp, name):
    return checked(H.get_blueprint_graph_info(bp, name))['nodes']


def function_graph(bp, name):
    """Retain the template's function signature while replacing its body."""
    g = Graph(bp, clear=False, graph_name=name)
    for n in info(bp, name):
        if n['node_class'] == 'K2Node_FunctionEntry':
            g.nodes['entry'] = n['node_name']
        elif n['node_class'] == 'K2Node_FunctionResult':
            g.nodes['result'] = n['node_name']
        else:
            checked(H.remove_blueprint_node(bp, name, n['node_name']))
    return g


def build_pad():
    bp = blueprint('BP_PitFallTeleportPad', unreal.StaticMeshActor)
    cdo = unreal.get_default_object(bp.generated_class())
    mesh = cdo.static_mesh_component
    mesh.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cylinder'))
    mesh.set_material(0, material('M_TeleportPadGlow', (0.015, 0.65, 0.85), 3))
    mesh.set_relative_scale3d(unreal.Vector(1.2, 1.2, 0.04))
    mesh.set_collision_profile_name('BlockAll')
    mesh.set_editor_property('mobility', unreal.ComponentMobility.STATIC)
    checked(H.compile_blueprint(bp))
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    return bp


def build_validation(bp):
    # ObjectIsA safely rejects a null hit actor, unlike calling ActorHasTag on it.
    # All placed pads have solid support and room for the full Character capsule.
    g = function_graph(bp, 'IsValidTeleportLocation')
    g.call('hit', 'GameplayStatics', 'BreakHitResult')
    g.wire('entry', 'Hit', 'hit', 'Hit')
    g.call('pad', 'GameplayStatics', 'ObjectIsA', ObjectClass=PAD + '.BP_PitFallTeleportPad_C')
    g.wire('hit', 'HitActor', 'pad', 'Object')
    g.call('normal', 'KismetMathLibrary', 'BreakVector')
    g.wire('hit', 'ImpactNormal', 'normal', 'InVec')
    g.call('top', 'KismetMathLibrary', 'Greater_DoubleDouble', B='0.9')
    g.wire('normal', 'Z', 'top', 'A')
    g.call('valid', 'KismetMathLibrary', 'BooleanAND')
    g.wire('pad', 'ReturnValue', 'valid', 'A')
    g.wire('top', 'ReturnValue', 'valid', 'B')
    g.wire('valid', 'ReturnValue', 'result', 'ReturnValue')
    g.wire('hit', 'ImpactPoint', 'result', 'ProjectedLocation')
    g.flow('entry', 'result')
    # Pad hits already provide the real surface height; no navmesh cell offset.
    trace = Graph(bp, clear=False, graph_name='TeleportTrace')
    nodes = info(bp, 'TeleportTrace')
    trace.nodes['valid'] = next(n['node_name'] for n in nodes if n['node_title'] == 'Is Valid Teleport Location')
    trace.nodes['store'] = next(n['node_name'] for n in nodes if n['node_title'] == 'Set ProjectedTeleportLocation')
    trace.wire('valid', 'ProjectedLocation', 'store', 'ProjectedTeleportLocation')


def build_commit(bp):
    g = function_graph(bp, 'TryTeleport')
    g.node('valid', 'VariableGet', variable_name='bValidTeleportLocation')
    g.node('branch', 'Branch')
    g.flow('entry', 'branch')
    g.wire('valid', 'bValidTeleportLocation', 'branch', 'Condition')
    g.node('target', 'VariableGet', variable_name='ProjectedTeleportLocation')
    g.node('camera', 'VariableGet', variable_name='Camera')
    g.call('eye', 'SceneComponent', 'K2_GetComponentLocation')
    g.wire('camera', 'Camera', 'eye', 'self')
    g.call('actor', 'Actor', 'K2_GetActorLocation')
    g.call('offset', 'KismetMathLibrary', 'Subtract_VectorVector')
    g.wire('eye', 'ReturnValue', 'offset', 'A')
    g.wire('actor', 'ReturnValue', 'offset', 'B')
    g.call('xy', 'KismetMathLibrary', 'BreakVector')
    g.wire('offset', 'ReturnValue', 'xy', 'InVec')
    g.call('horizontal', 'KismetMathLibrary', 'MakeVector')
    g.wire('xy', 'X', 'horizontal', 'X')
    g.wire('xy', 'Y', 'horizontal', 'Y')
    g.call('aligned', 'KismetMathLibrary', 'Subtract_VectorVector')
    g.wire('target', 'ProjectedTeleportLocation', 'aligned', 'A')
    g.wire('horizontal', 'ReturnValue', 'aligned', 'B')
    g.node('capsule', 'VariableGet', variable_name='CapsuleComponent')
    g.call('height', 'CapsuleComponent', 'GetScaledCapsuleHalfHeight')
    g.wire('capsule', 'CapsuleComponent', 'height', 'self')
    g.call('radius', 'CapsuleComponent', 'GetScaledCapsuleRadius')
    g.wire('capsule', 'CapsuleComponent', 'radius', 'self')
    g.call('clearance', 'KismetMathLibrary', 'Add_DoubleDouble', B='2')
    g.wire('height', 'ReturnValue', 'clearance', 'A')
    g.call('up', 'KismetMathLibrary', 'MakeVector')
    g.wire('clearance', 'ReturnValue', 'up', 'Z')
    g.call('destination', 'KismetMathLibrary', 'Add_VectorVector')
    g.wire('aligned', 'ReturnValue', 'destination', 'A')
    g.wire('up', 'ReturnValue', 'destination', 'B')
    g.call('space', 'KismetSystemLibrary', 'CapsuleTraceSingleByProfile',
           ProfileName='Pawn', bTraceComplex='false', bIgnoreSelf='true', DrawDebugType='None')
    for pin in ['Start', 'End']:
        g.wire('destination', 'ReturnValue', 'space', pin)
    g.wire('height', 'ReturnValue', 'space', 'HalfHeight')
    g.wire('radius', 'ReturnValue', 'space', 'Radius')
    # A large physical tracking offset can put the capsule beside the plank.
    # Require support under its centre as well as free space around the body.
    g.call('support_depth', 'KismetMathLibrary', 'Add_DoubleDouble', B='20')
    g.wire('height', 'ReturnValue', 'support_depth', 'A')
    g.call('support_down', 'KismetMathLibrary', 'MakeVector')
    g.wire('support_depth', 'ReturnValue', 'support_down', 'Z')
    g.call('support_end', 'KismetMathLibrary', 'Subtract_VectorVector')
    g.wire('destination', 'ReturnValue', 'support_end', 'A')
    g.wire('support_down', 'ReturnValue', 'support_end', 'B')
    g.call('support', 'KismetSystemLibrary', 'LineTraceSingleByProfile',
           ProfileName='Pawn', bTraceComplex='false', bIgnoreSelf='true', DrawDebugType='None')
    g.wire('destination', 'ReturnValue', 'support', 'Start')
    g.wire('support_end', 'ReturnValue', 'support', 'End')
    g.wire('branch', 'then', 'support', 'execute')
    g.node('supported', 'Branch')
    g.flow('support', 'supported')
    g.wire('support', 'ReturnValue', 'supported', 'Condition')
    g.wire('supported', 'then', 'space', 'execute')
    g.node('blocked', 'Branch')
    g.flow('space', 'blocked')
    g.wire('space', 'ReturnValue', 'blocked', 'Condition')
    g.call('rotation', 'Actor', 'K2_GetActorRotation')
    g.call('teleport', 'Actor', 'K2_TeleportTo')
    g.wire('destination', 'ReturnValue', 'teleport', 'DestLocation')
    g.wire('rotation', 'ReturnValue', 'teleport', 'DestRotation')
    g.wire('blocked', 'else', 'teleport', 'execute')
    g.node('movement', 'VariableGet', variable_name='CharacterMovement')
    g.call('stop', 'MovementComponent', 'StopMovementImmediately')
    g.wire('movement', 'CharacterMovement', 'stop', 'self')
    g.flow('teleport', 'stop')


def build_events(bp):
    if unreal.EditorAssetLibrary.get_metadata_tag(bp, 'PitFallTeleportEvents') == '1':
        return
    g = Graph(bp, clear=False)
    nodes = info(bp, 'EventGraph')
    event = next(n for n in nodes if n['node_title'] == 'EnhancedInputAction IA_Hand_IndexCurl_Right')
    g.nodes['input'] = event['node_name']

    def splice(event_node, pin, key):
        """Preserve existing hand animation/reset execution alongside teleport."""
        g.node(key, 'Sequence')
        old = next(p for p in event_node['pins'] if p['pin_name'] == pin).get('linked_to', [])
        g.nodes['source'] = event_node['node_name']
        g.wire('source', pin, key, 'execute')
        for index, link in enumerate(old):
            g.nodes['old_' + str(index)] = link['node_name']
            g.wire(key, 'then_0', 'old_' + str(index), link['pin_name'])

    g.call('start', '', 'StartTeleportTrace')
    g.wire('input', 'Started', 'start', 'execute')
    # Use the actual right-controller aim pose. Desktop uses a downward camera
    # ray so T can be exercised without a headset or untracked controllers.
    g.node('aim', 'VariableGet', variable_name='MotionControllerRightAim')
    g.node('camera', 'VariableGet', variable_name='Camera')
    g.call('hmd', 'HeadMountedDisplayFunctionLibrary', 'IsHeadMountedDisplayEnabled')
    for key, component in [('hand', 'aim'), ('view', 'camera')]:
        variable = 'MotionControllerRightAim' if key == 'hand' else 'Camera'
        g.call(key + '_position', 'SceneComponent', 'K2_GetComponentLocation')
        g.call(key + '_direction', 'SceneComponent', 'GetForwardVector')
        g.wire(component, variable, key + '_position', 'self')
        g.wire(component, variable, key + '_direction', 'self')
    g.call('down', 'KismetMathLibrary', 'Add_VectorVector', B='0,0,-0.1')
    g.wire('view_direction', 'ReturnValue', 'down', 'A')
    g.call('unit', 'KismetMathLibrary', 'Normal')
    g.wire('down', 'ReturnValue', 'unit', 'A')
    for key in ['position', 'direction']:
        g.call(key, 'KismetMathLibrary', 'SelectVector')
        g.wire('hmd', 'ReturnValue', key, 'bPickA')
        g.wire('hand_' + key, 'ReturnValue', key, 'A')
        g.wire('view_position' if key == 'position' else 'unit', 'ReturnValue', key, 'B')
    for key in ['update', 'release_update']:
        g.call(key, '', 'TeleportTrace')
        g.wire('position', 'ReturnValue', key, 'StartPos')
        g.wire('direction', 'ReturnValue', key, 'ForwardVector')
    splice(event, 'Triggered', 'hold')
    g.node('active', 'VariableGet', variable_name='bTeleportTraceActive')
    g.node('hold_active', 'Branch')
    g.wire('active', 'bTeleportTraceActive', 'hold_active', 'Condition')
    g.wire('hold', 'then_1', 'hold_active', 'execute')
    g.wire('hold_active', 'then', 'update', 'execute')
    splice(event, 'Completed', 'release')
    g.node('release_active', 'Branch')
    g.wire('active', 'bTeleportTraceActive', 'release_active', 'Condition')
    g.wire('release', 'then_1', 'release_active', 'execute')
    g.wire('release_active', 'then', 'release_update', 'execute')
    g.call('commit', '', 'TryTeleport')
    g.call('end', '', 'EndTeleportTrace')
    g.flow('release_update', 'commit', 'end')
    splice(event, 'Canceled', 'cancel')
    g.wire('cancel', 'then_1', 'end', 'execute')
    # Clear both state and visuals even when reset occurs while holding aim.
    reset = next(n for n in nodes if n['node_title'] == 'EnhancedInputAction IA_Menu_Toggle_Left')
    reset_link = next(p for p in reset['pins'] if p['pin_name'] == 'Triggered')['linked_to'][0]
    g.nodes['reset_position'] = reset_link['node_name']
    incoming = next(n for n in nodes if n['node_name'] == reset_link['node_name'])
    reset_exec = next(p for p in incoming['pins'] if p['pin_name'] == 'execute').get('linked_to', [])
    g.node('reset_sequence', 'Sequence')
    for index, link in enumerate(reset_exec):
        g.nodes['reset_source_' + str(index)] = link['node_name']
        g.wire('reset_source_' + str(index), link['pin_name'], 'reset_sequence', 'execute')
    g.call('reset_end', '', 'EndTeleportTrace')
    g.wire('reset_sequence', 'then_0', 'reset_end', 'execute')
    g.wire('reset_sequence', 'then_1', 'reset_position', 'execute')
    unreal.EditorAssetLibrary.set_metadata_tag(bp, 'PitFallTeleportEvents', '1')


def build_player(bp):
    build_validation(bp)
    build_commit(bp)
    build_events(bp)
    # Do not leave a valid destination after cancel, reset or successful release.
    g = Graph(bp, clear=False, graph_name='EndTeleportTrace')
    nodes = info(bp, 'EndTeleportTrace')
    if not any(n['node_title'] == 'Set bValidTeleportLocation' for n in nodes):
        g.nodes['entry'] = next(n['node_name'] for n in nodes if n['node_class'] == 'K2Node_FunctionEntry')
        entry = next(n for n in nodes if n['node_name'] == g.nodes['entry'])
        link = next(p for p in entry['pins'] if p['pin_name'] == 'then')['linked_to'][0]
        g.nodes['old'] = link['node_name']
        g.node('invalidate', 'VariableSet', variable_name='bValidTeleportLocation', pin_defaults={'bValidTeleportLocation':'false'})
        g.flow('entry', 'invalidate')
        g.wire('invalidate', 'then', 'old', link['pin_name'])
    checked(H.compile_blueprint(bp))
    unreal.EditorAssetLibrary.save_loaded_asset(bp)


def place_pads(pad):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actors.get_all_level_actors():
        if 'PitFallTeleport' in [str(t) for t in actor.tags]:
            actors.destroy_actor(actor)
    dark = material('M_TeleportPadInset', (0.015, 0.045, 0.065))
    for name, xyz in PADS:
        a = actors.spawn_actor_from_class(pad.generated_class(), unreal.Vector(*xyz))
        a.set_actor_label('TeleportPad_' + name)
        a.set_folder_path('PitFall/Teleport')
        a.tags = [TAG, 'PitFallTeleport']
        # A dark inset leaves a bright cyan rim; no extra collision surface.
        inset = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(xyz[0], xyz[1], 4.2))
        inset.set_actor_label('TeleportPad_Inset_' + name)
        inset.tags = [TAG, 'PitFallTeleport']
        inset.set_folder_path('PitFall/Teleport')
        inset.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cylinder'))
        inset.static_mesh_component.set_material(0, dark)
        inset.static_mesh_component.set_collision_profile_name('NoCollision')
        inset.set_actor_scale3d(unreal.Vector(1.02, 1.02, 0.004))
        label = actors.spawn_actor_from_class(unreal.TextRenderActor, unreal.Vector(xyz[0], xyz[1] + 68, 12), unreal.Rotator(yaw=-90))
        label.set_actor_label('TeleportPad_Label_' + name)
        label.tags = [TAG, 'PitFallTeleport']
        label.set_folder_path('PitFall/Teleport')
        label.text_render.set_text(name.upper() + '\nTELEPORT')
        label.text_render.set_world_size(14)
        label.text_render.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
        label.text_render.set_text_render_color(unreal.Color(40, 220, 255))


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split('.')[0] != LEVEL:
        raise RuntimeError('Open PitFallUebung before building teleportation')
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
        raise RuntimeError('Stop Play before building teleportation')
    pad = build_pad()
    build_player(unreal.load_asset(PLAYER))
    place_pads(pad)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    print(json.dumps({'success': True, 'teleport_pads': len(PADS)}))


if __name__ == '__main__':
    main()
