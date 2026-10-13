"""Run in UE 5.6's editor Python console to build the PitFall exercise.

Only actors tagged PitFallExercise and assets under /Game/PitFall are authored.
Runtime behavior is compiled Blueprint; Python is not needed by the headset.
"""
import json
import math
import unreal

LEVEL = '/Game/Resonance/Levels/PitFallUebung'
ROOT = '/Game/PitFall'
TAG = 'PitFallExercise'
START = (0, -820, 90)
DEPTH = 2400
FLIGHT_DROP = 300
STEPS_PER_FLIGHT = 20
H = unreal.MCPythonHelper


def checked(result):
    data = json.loads(result)
    if not data.get('success'):
        raise RuntimeError(data)
    return data


def blueprint(name, parent):
    path = ROOT + '/Blueprints/' + name
    bp = unreal.load_asset(path)
    if bp is None:
        factory = unreal.BlueprintFactory()
        factory.set_editor_property('parent_class', parent)
        bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, ROOT + '/Blueprints', unreal.Blueprint, factory)
    return bp


class Graph:
    def __init__(self, bp, clear=True, graph_name='EventGraph'):
        self.bp = bp
        self.graph_name = graph_name
        self.nodes = {}
        info = json.loads(H.get_blueprint_graph_info(bp, graph_name))
        if clear:
            for n in info['nodes']:
                checked(H.remove_blueprint_node(bp, graph_name, n['node_name']))

    def node(self, key, kind='CallFunction', **kwargs):
        kwargs.setdefault('pos_x', (len(self.nodes) % 8) * 380)
        kwargs.setdefault('pos_y', (len(self.nodes) // 8) * 260)
        result = checked(H.add_blueprint_node(self.bp, self.graph_name, json.dumps(dict(type=kind, **kwargs))))
        self.nodes[key] = result['node_name']
        for pin, value in kwargs.get('pin_defaults', {}).items():
            checked(H.set_blueprint_node_pin_default(self.bp, self.graph_name, result['node_name'], pin, value))
        return key

    def call(self, key, target, function, **defaults):
        return self.node(key, target=target, function_name=function, pin_defaults={k: str(v) for k, v in defaults.items()})

    def wire(self, src, pin, dst, dest):
        checked(H.connect_blueprint_pins(self.bp, self.graph_name, self.nodes[src], pin, self.nodes[dst], dest))

    def flow(self, *keys):
        for a, b in zip(keys, keys[1:]):
            self.wire(a, 'then', b, 'execute')


def build_player():
    from build_pitfall_vr import build_player as build_tracked_player
    return build_tracked_player()


def build_input():
    from build_pitfall_vr import build_input as build_tracked_input
    return build_tracked_input()

def material(name, rgb, glow=0):
    path = ROOT+'/Materials/'+name
    m = unreal.load_asset(path)
    if m:
        return m
    m = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, ROOT+'/Materials', unreal.Material, unreal.MaterialFactoryNew())
    lib = unreal.MaterialEditingLibrary
    color = lib.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -350, 0)
    color.set_editor_property('constant', unreal.LinearColor(*rgb))
    lib.connect_material_property(color, '', unreal.MaterialProperty.MP_BASE_COLOR)
    rough = lib.create_material_expression(m, unreal.MaterialExpressionConstant, -350, 160)
    rough.set_editor_property('r', 0.85)
    lib.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
    if glow:
        emissive = lib.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -350, 300)
        emissive.set_editor_property('constant', unreal.LinearColor(*(c*glow for c in rgb)))
        lib.connect_material_property(emissive, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(m)
    unreal.EditorAssetLibrary.save_loaded_asset(m)
    return m


def build_level(game_mode):
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if levels.get_current_level().get_path_name().split('.')[0] != LEVEL:
        levels.load_level(LEVEL)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actors.get_all_level_actors():
        if TAG in [str(t) for t in actor.tags]:
            actors.destroy_actor(actor)
    cube = unreal.load_asset('/Engine/BasicShapes/Cube')
    mats = {
        'wall': material('M_ShaftConcrete', (0.095,0.12,0.15)),
        'floor': material('M_Deck', (0.24,0.29,0.32)),
        'ramp': material('M_Walkway', (0.35,0.40,0.42)),
        'rail': material('M_Rail', (0.045,0.06,0.07)),
        'yellow': material('M_HazardYellow', (0.95,0.54,0.025)),
        'cyan': material('M_RouteLight', (0.02,0.55,0.8), 2),
    }
    count = 0

    def spawn(cls, label, xyz, rotation=(0,0,0)):
        a = actors.spawn_actor_from_class(cls, unreal.Vector(*xyz), unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
        a.set_actor_label(label)
        a.set_editor_property('tags', [TAG])
        a.set_folder_path('PitFall/'+label.split('_')[0])
        return a

    def box(label, xyz, size, mat='wall', rotation=(0,0,0), collision=True):
        nonlocal count
        a = spawn(unreal.StaticMeshActor, label, xyz, rotation)
        comp = a.static_mesh_component
        comp.set_static_mesh(cube)
        comp.set_material(0, mats[mat])
        comp.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
        a.set_actor_scale3d(unreal.Vector(*(s/100 for s in size)))
        count += 1
        return a

    def sign(label, text, xyz, size=24, yaw=-90, color=(220,235,245)):
        a = spawn(unreal.TextRenderActor, label, xyz, (0,yaw,0))
        c = a.text_render
        c.set_text(text)
        c.set_world_size(size)
        c.set_text_render_color(unreal.Color(*color))
        c.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
        return a

    # Enclosed upper room and a shaft twice as deep as the original exercise.
    box('Deck_South', (0,-800,-20), (2000,400,40), 'floor')
    box('Deck_North', (0,800,-20), (2000,400,40), 'floor')
    box('Deck_West', (-800,0,-20), (400,1200,40), 'floor')
    box('Deck_East', (800,0,-20), (400,1200,40), 'floor')
    for x in [-55,55]:
        box('Mark_Start_Side_'+str(x), (START[0]+x,START[1],1), (4,110,2), 'cyan', collision=False)
    for y in [-55,55]:
        box('Mark_Start_End_'+str(y), (START[0],START[1]+y,1), (110,4,2), 'cyan', collision=False)
    box('Shaft_Bottom', (0,0,-DEPTH-20), (1200,1200,40), 'floor')
    for name, xyz, dims in [('West',(-650,0,-DEPTH/2),(100,1400,DEPTH)),('East',(650,0,-DEPTH/2),(100,1400,DEPTH)),('North',(0,650,-DEPTH/2),(1200,100,DEPTH)),('South',(0,-650,-DEPTH/2),(1200,100,DEPTH))]:
        box('Shaft_'+name, xyz, dims)
    for name, xyz, dims in [('West',(-1050,0,175),(100,2200,350)),('East',(1050,0,175),(100,2200,350)),('North',(0,1050,175),(2000,100,350)),('South',(0,-1050,175),(2000,100,350))]:
        box('Room_'+name, xyz, dims)
    box('Room_Ceiling', (0,0,375), (2200,2200,50))
    for x in [-750,750]:
        for y in [-750,750]:
            box('Room_Lamp_'+str(x)+'_'+str(y), (x,y,344), (180,35,8), 'cyan', collision=False)
    box('Deck_Entry', (-470,-620,-20), (200,160,40), 'ramp')
    box('Deck_Overlook', (0,-440,-15), (140,320,30), 'ramp')
    box('Mark_Overlook', (0,-285,1), (140,10,2), 'yellow', collision=False)
    # Eight flights wrap around the shaft, with 15 cm risers and broad treads.
    # Descend along the west wall first, so the south flight clears the plank.
    plan = [(-470,-470),(-470,470),(470,470),(470,-470)]
    corners = [(*plan[i % 4], -i*FLIGHT_DROP) for i in range(DEPTH//FLIGHT_DROP+1)]
    for i, (x,y,z) in enumerate(corners):
        box('Stair_Landing_'+str(i), (x,y,z-20), (200,200,40), 'ramp')
    for i, (a,b) in enumerate(zip(corners,corners[1:])):
        dx,dy = b[0]-a[0], b[1]-a[1]
        distance = math.hypot(dx,dy)
        ux,uy = dx/distance,dy/distance
        # Every tread has collision; risers remain below the 30 cm step limit.
        p = (a[0]+100*ux,a[1]+100*uy,a[2])
        q = (b[0]-100*ux,b[1]-100*uy,b[2])
        length = math.dist(p,q)
        pitch = math.degrees(math.atan2(q[2]-p[2],distance-200))
        yaw = math.degrees(math.atan2(dy,dx))
        center = tuple((p[j]+q[j])/2 for j in range(3))
        tread = (distance-200)/STEPS_PER_FLIGHT
        riser = FLIGHT_DROP/STEPS_PER_FLIGHT
        for step in range(STEPS_PER_FLIGHT):
            top = a[2]-(step+1)*riser
            xyz = (p[0]+ux*(step+0.5)*tread,p[1]+uy*(step+0.5)*tread,top-20)
            box('Stair_Flight_'+str(i)+'_Step_'+str(step), xyz, (tread+0.5,200,40), 'ramp', (0,yaw,0))
            box('Mark_Tread_'+str(i)+'_'+str(step), (xyz[0]-ux*(tread/2-2),xyz[1]-uy*(tread/2-2),top+1), (4,190,2), 'yellow', (0,yaw,0), False)
        # The inside rail keeps stick movement on the descent; overlook stays open.
        nx,ny = uy,-ux
        railcenter = (center[0]+nx*96,center[1]+ny*96,center[2]+95)
        box('Rail_Descent_'+str(i), railcenter, (length,7,7), 'rail', (pitch,yaw,0))
        lightcenter = (center[0]+nx*80,center[1]+ny*80,center[2]+2)
        box('Mark_Route_'+str(i), lightcenter, (length,5,3), 'cyan', (pitch,yaw,0), False)
        for t in [0,0.25,0.5,0.75,1]:
            xyz = tuple(p[j]+(q[j]-p[j])*t for j in range(3))
            box('Rail_Post_'+str(i)+'_'+str(t), (xyz[0]+nx*96,xyz[1]+ny*96,xyz[2]+47), (7,7,94), 'rail')
    for y in [-597,597]:
        for x in range(-550,600,100):
            if y < 0 and (-580 < x < -360 or -100 < x < 100):
                continue
            box('Mark_Rim_'+str(x)+'_'+str(y), (x,y,1), (65,12,2), 'yellow', collision=False)
    # Depth markers and architectural ribs make the height legible.
    for depth in range(0,DEPTH+1,FLIGHT_DROP):
        box('Shaft_Rib_'+str(depth), (595,0,-depth), (8,1200,12), 'rail')
        sign('Sign_Depth_'+str(depth), str(depth//100)+' m', (590,0,-depth+110), 34, 180)
    sign('Sign_Title', 'PITFALL / VR EXERCISE', (-160,-590,210), 30)
    sign('Sign_Controls', 'LEFT STICK: WALK   |   RIGHT STICK: SNAP TURN\nX: RESET   |   FOLLOW BLUE ROUTE DOWN', (-160,-589,155), 14)
    sign('Sign_Entry', 'STAIRS\n24 m DESCENT', (-470,-550,90), 18)
    sign('Sign_Finish', 'BOTTOM REACHED\nX TO RETURN TO START', (0,580,-DEPTH+150), 28)
    start = spawn(unreal.PlayerStart, 'Player_Start', START, (0,90,0))
    for x in [-750,750]:
        for y in [-750,750]:
            light = spawn(unreal.PointLight, 'Light_Room_'+str(x)+'_'+str(y), (x,y,300))
            c = light.get_component_by_class(unreal.PointLightComponent)
            c.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
            c.set_editor_property('intensity', 500)
            c.set_editor_property('attenuation_radius', 1300)
            c.set_editor_property('cast_shadows', True)
            c.set_light_color(unreal.LinearColor(0.9,0.95,1))
    for i,z in enumerate(range(-150,-DEPTH,-450)):
        light = spawn(unreal.PointLight, 'Light_Shaft_'+str(i), (0,0,z))
        c = light.get_component_by_class(unreal.PointLightComponent)
        c.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
        c.set_editor_property('intensity', 650)
        c.set_editor_property('attenuation_radius', 1200)
        c.set_editor_property('cast_shadows', False)
        c.set_light_color(unreal.LinearColor(0.5,0.75,1))
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    world.get_world_settings().set_editor_property('default_game_mode', game_mode)
    world.get_world_settings().set_editor_property('kill_z', -DEPTH-1500)
    levels.save_current_level()
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(unreal.Vector(-250,-800,200), unreal.Rotator(pitch=-20,yaw=75,roll=0))
    print(json.dumps({'success':True, 'level':LEVEL, 'mesh_count':count, 'actors':len(actors.get_all_level_actors())}))


def main():
    build_input()
    game_mode = build_player()
    build_level(game_mode)


if __name__ == '__main__':
    main()
