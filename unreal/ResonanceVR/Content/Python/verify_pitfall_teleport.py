"""Run start() in desktop PIE; exercise the real Enhanced Input events.

Results go to Saved/PitFall-teleport-validation.json. This does not test
physical OpenXR controller bindings or headset comfort.
"""
import json
import time
from pathlib import Path
import unreal

_handle = None


def start():
    global _handle
    if _handle is not None:
        raise RuntimeError('Verification is already running')
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        raise RuntimeError('Start desktop Play in PitFallUebung first')
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    if pawn.get_class().get_name() != 'BP_PitFallTrackedPlayer_C':
        raise RuntimeError('Expected the PitFall tracked player')
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    api = unreal.get_default_object(unreal.load_class(None, '/Script/Engine.SubsystemBlueprintLibrary'))
    inputs = api.call_method('GetLocalPlayerSubSystemFromPlayerController', (
        pc, unreal.load_class(None, '/Script/EnhancedInput.EnhancedInputLocalPlayerSubsystem')))
    action = unreal.load_asset('/Game/VRTemplate/Input/Actions/Hands/IA_Hand_IndexCurl_Right')
    reset_action = unreal.load_asset('/Game/VRTemplate/Input/Actions/IA_Menu_Toggle_Left')
    camera = pawn.get_component_by_class(unreal.CameraComponent)
    original_camera = camera.get_editor_property('relative_location')
    checks = {}

    def reset():
        pawn.call_method('EndTeleportTrace')
        pawn.set_actor_location(unreal.Vector(0, -820, 94.15), False, True)
        pawn.set_actor_rotation(unreal.Rotator(yaw=90), True)
        pawn.get_component_by_class(unreal.CharacterMovementComponent).stop_movement_immediately()

    def trace(direction):
        pawn.call_method('StartTeleportTrace')
        pawn.call_method('TeleportTrace', (unreal.Vector(0, -820, 176.15), direction.normal()))

    reset()
    trace(unreal.Vector(0, 1, -0.65))
    checks['ordinary_deck_rejected'] = not pawn.get_editor_property('bValidTeleportLocation')
    before = pawn.get_actor_location()
    pawn.call_method('TryTeleport')
    checks['invalid_release_does_not_move'] = (pawn.get_actor_location() - before).length() < 0.1
    pawn.call_method('EndTeleportTrace')
    trace(unreal.Vector(0, 1, -0.1))
    checks['pad_surface_accepted'] = pawn.get_editor_property('bValidTeleportLocation')
    target = pawn.get_editor_property('ProjectedTeleportLocation')
    # Emulate a physical headset offset without changing the tracking origin.
    camera.set_relative_location(unreal.Vector(25, -12, original_camera.z), False, True)
    pawn.call_method('TryTeleport')
    eye = camera.get_world_location()
    checks['room_scale_offset_preserved'] = abs(eye.x - target.x) < 0.2 and abs(eye.y - target.y) < 0.2
    checks['capsule_height_preserved'] = abs(pawn.get_actor_location().z - 94) < 0.2
    checks['velocity_cleared'] = pawn.get_velocity().length() < 0.1
    camera.set_relative_location(original_camera, False, True)
    pawn.call_method('EndTeleportTrace')
    checks['end_clears_state'] = not pawn.get_editor_property('bTeleportTraceActive') and not pawn.get_editor_property('bValidTeleportLocation')
    # Move a runtime wall over the pad after tracing to check release clearance.
    reset()
    trace(unreal.Vector(0, 1, -0.1))
    wall = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                if a.get_actor_label() == 'Room_South')
    wall_position = wall.get_actor_location()
    wall_mobility = wall.static_mesh_component.get_editor_property('mobility')
    wall.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    target = pawn.get_editor_property('ProjectedTeleportLocation')
    wall.set_actor_location(unreal.Vector(target.x, target.y, 175), False, True)
    before = pawn.get_actor_location()
    pawn.call_method('TryTeleport')
    checks['blocked_destination_rejected'] = (pawn.get_actor_location() - before).length() < 0.1
    wall.set_actor_location(wall_position, False, True)
    wall.static_mesh_component.set_mobility(wall_mobility)
    reset()
    started = time.monotonic()
    stages = set()

    def tick(_delta):
        global _handle
        elapsed = time.monotonic() - started
        try:
            if not unreal.SystemLibrary.is_valid(pawn):
                raise RuntimeError('PIE ended during verification')
            if elapsed < 0.8 or 1.5 <= elapsed < 2.3:
                inputs.inject_input_vector_for_action(action, unreal.Vector(1, 0, 0), [], [])
            if elapsed >= 0.5 and 'aim' not in stages:
                stages.add('aim')
                checks['input_hold_shows_arc'] = pawn.get_editor_property('bTeleportTraceActive')
                checks['input_hold_finds_pad'] = pawn.get_editor_property('bValidTeleportLocation')
            if elapsed >= 1.2 and 'release' not in stages:
                stages.add('release')
                checks['input_release_teleports'] = pawn.get_actor_location().y > -600
                checks['input_release_hides_arc'] = not pawn.get_editor_property('bTeleportTraceActive')
                reset()
            if elapsed >= 1.9 and 'reset' not in stages:
                stages.add('reset')
                inputs.inject_input_vector_for_action(reset_action, unreal.Vector(1, 0, 0), [], [])
            if elapsed >= 2.7:
                checks['reset_during_aim_cancels'] = not pawn.get_editor_property('bTeleportTraceActive') and abs(pawn.get_actor_location().y + 820) < 1
                rings = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                         if a.get_class().get_name() == 'VRTeleportVisualizer_C']
                checks['no_orphan_destination_rings'] = not rings
                finish()
        except Exception as error:
            checks['runtime_error'] = str(error)
            finish()

    def finish():
        global _handle
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
        result = {'passed': all(v is True for v in checks.values()), 'checks': checks,
                  'note': 'Desktop PIE and Enhanced Input injection; headset not tested'}
        path = Path(unreal.Paths.project_saved_dir()) / 'PitFall-teleport-validation.json'
        path.write_text(json.dumps(result, indent=2), encoding='utf-8')
        unreal.log('PitFall teleport verification: ' + json.dumps(result))

    _handle = unreal.register_slate_post_tick_callback(tick)
