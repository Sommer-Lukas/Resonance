"""Build the VR menu framework (UI phase 1) in UE 5.6's editor Python console.

Creates:
  /Game/Resonance/UI/Textures/   stage background and transparent logo
  /Game/Resonance/UI/WBP_ResonanceMenu   1440x900 menu: glass top bar, four screens
  /Game/Resonance/Blueprints/BP_ResonanceMenu   curved widget panel in front of the viewer
  /Game/Resonance/Input/IMC_ResonanceMenu   trigger -> pointer click
and adds a laser pointer to each hand of BP_ResonanceViewer.

Text comes from resonance_ui_content.json and is baked into the widget, so the
menu needs no runtime file access. Rerun after editing that file.

Usage, with /Game/Resonance/Levels/I_Resonance open:
    import build_resonance_ui; build_resonance_ui.build()
Once per viewer Blueprint, before the first build, paste menu_input_nodes.txt
into BP_ResonanceViewer's EventGraph (same procedure as face_mode_input_nodes.txt).
"""
import json
import os
import unreal
from build_pitfall import Graph, H, checked
from build_resonance_face_modes import OwnedGraph, cast_result, clean
import build_resonance_audio2face as ace

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.normpath(os.path.join(HERE, '..', '..', 'UISource'))
CONTENT = os.path.join(HERE, 'resonance_ui_content.json')

LEVEL = '/Game/Resonance/Levels/I_Resonance'
UI = '/Game/Resonance/UI'
TEX = UI + '/Textures'
MENU_WIDGET = UI + '/WBP_ResonanceMenu'
BLUEPRINTS = '/Game/Resonance/Blueprints'
MENU_ACTOR = BLUEPRINTS + '/BP_ResonanceMenu'
VIEWER = BLUEPRINTS + '/BP_ResonanceViewer'
INPUT = '/Game/Resonance/Input'
CONTEXT = INPUT + '/IMC_ResonanceMenu'
SELECT = {'Left': 'OculusTouch_Left_Trigger_Click', 'Right': 'OculusTouch_Right_Trigger_Click'}
TAG = 'ResonanceMenu'

TEXTURES = ['T_ResonanceStage.jpg', 'T_ResonanceLogo.png', 'T_ResonanceLogoMark.png']
SCREENS = ['Landing', 'Home', 'People', 'Sessions']
TABS = ['Home', 'People', 'Sessions']

# The panel is drawn at 1 px = 0.75 mm: 1440 px -> 1.08 m wide, 0.9 m from the eyes.
DRAW_SIZE = (1440, 900)
PANEL_SCALE = 0.075
PANEL_DISTANCE = 90.0
PANEL_ARC = 40.0

FONT = "/Script/Engine.Font'/Engine/EngineFonts/Roboto.Roboto'"
MONO = "/Script/Engine.Font'/Engine/EngineFonts/RobotoMono.RobotoMono'"


# ─── Styling helpers (Unreal text-import format) ────────────────────────────

def load_content():
    with open(CONTENT, encoding='utf-8') as f:
        return json.load(f)


def linear(rgba):
    """Palette values are sRGB like the web prototype; Slate colours are linear."""
    def channel(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b, a = rgba
    return '(R=%.4f,G=%.4f,B=%.4f,A=%.3f)' % (channel(r), channel(g), channel(b), a)


def slate(rgba):
    return '(SpecifiedColor=%s,ColorUseRule=UseColor_Specified)' % linear(rgba)


def rounded(fill, radius, edge=None, width=1.0):
    edge = edge or [fill[0], fill[1], fill[2], 0.0]
    r = radius
    return ('(DrawAs=RoundedBox,TintColor=%s,OutlineSettings=(CornerRadii=(X=%d,Y=%d,Z=%d,W=%d),'
            'Color=%s,Width=%.1f,RoundingType=FixedRadius,bUseBrushTransparency=True))'
            % (slate(fill), r, r, r, r, slate(edge), width))


def font(size, face='Regular', mono=False):
    return '(FontObject=%s,TypefaceFontName="%s",Size=%d)' % (MONO if mono else FONT, face, size)


def image(texture, w, h):
    path = "/Script/Engine.Texture2D'%s/%s.%s'" % (TEX, texture, texture)
    return '(ResourceObject=%s,ImageSize=(X=%d,Y=%d),DrawAs=Image)' % (path, w, h)


def margin(l, t, r, b):
    return '(Left=%d,Top=%d,Right=%d,Bottom=%d)' % (l, t, r, b)


def button_style(fill, hover, press, radius, edge=None, pad=(26, 14)):
    x, y = pad
    return ('(Normal=%s,Hovered=%s,Pressed=%s,Disabled=%s,NormalPadding=%s,PressedPadding=%s)'
            % (rounded(fill, radius, edge), rounded(hover, radius, edge), rounded(press, radius, edge),
               rounded(fill, radius, edge), margin(x, y, x, y), margin(x, y + 1, x, y - 1)))


class Tree:
    """Thin wrapper over the MCPython UMG helpers."""

    def __init__(self, bp, palette):
        self.bp, self.p = bp, palette

    def add(self, kind, name, parent='', **props):
        checked(H.umg_add_widget(self.bp, kind, name, parent))
        for key, value in props.items():
            self.prop(name, key, value)
        return name

    def prop(self, name, key, value):
        checked(H.umg_set_widget_property(self.bp, name, key, str(value)))

    def widget(self, name):
        return H.umg_find_widget(self.bp, name)

    def place(self, name, x, y, w, h):
        checked(H.umg_set_slot_layout(self.bp, name, 0, 0, 0, 0, x, y, w, h))

    def slot(self, name, pad=None, fill=False, h=None, v=None):
        s = self.widget(name).get_editor_property('slot')
        if pad is not None:
            s.set_padding(unreal.Margin(*pad))
        if fill:
            size = unreal.SlateChildSize()
            size.set_editor_property('value', 1.0)
            size.set_editor_property('size_rule', unreal.SlateSizeRule.FILL)
            s.set_size(size)
        if h:
            s.set_horizontal_alignment(getattr(unreal.HorizontalAlignment, 'H_ALIGN_' + h))
        if v:
            s.set_vertical_alignment(getattr(unreal.VerticalAlignment, 'V_ALIGN_' + v))

    def text(self, name, parent, value, size, face='Regular', color='ink', mono=False, wrap=0):
        self.add('TextBlock', name, parent)
        self.widget(name).set_editor_property('text', unreal.Text(value))
        self.prop(name, 'Font', font(size, face, mono))
        self.prop(name, 'ColorAndOpacity', slate(self.p[color]))
        if wrap:
            self.prop(name, 'WrapTextAt', wrap)
        return name

    def glass(self, name, parent, radius=22, pad=(28, 24, 28, 24), dark=False):
        fill = self.p['glass_navy'] if dark else self.p['glass']
        edge = [1, 1, 1, 0.22] if dark else self.p['glass_edge']
        self.add('Border', name, parent, Background=rounded(fill, radius, edge), Padding=margin(*pad))
        return name

    def button(self, name, parent, label, kind='primary', size=22):
        p = self.p
        if kind == 'primary':
            style = button_style(p['navy'], p['blue'], [0.04, 0.16, 0.26, 1], 14)
            color = 'on_navy'
        elif kind == 'tab':
            style = button_style([1, 1, 1, 0], [1, 1, 1, 0.45], [1, 1, 1, 0.8], 11, pad=(20, 10))
            color = 'ink_muted'
        else:
            style = button_style([1, 1, 1, 0.5], [1, 1, 1, 0.78], [1, 1, 1, 0.9], 14, [1, 1, 1, 0.85])
            color = 'ink'
        self.add('Button', name, parent, WidgetStyle=style)
        self.text(name + 'Label', name, label, size, 'Bold' if kind != 'tab' else 'Regular', color)
        return name

    def label(self, name, parent, value, color='ink_faint'):
        return self.text(name, parent, value.upper(), 15, 'Regular', color, mono=True)


# ─── Assets ─────────────────────────────────────────────────────────────────

def import_textures():
    tasks = []
    for file in TEXTURES:
        task = unreal.AssetImportTask()
        task.set_editor_property('filename', os.path.join(SOURCE, file))
        task.set_editor_property('destination_path', TEX)
        task.set_editor_property('destination_name', os.path.splitext(file)[0])
        task.set_editor_property('automated', True)
        task.set_editor_property('replace_existing', True)
        task.set_editor_property('save', False)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    for file in TEXTURES:
        name = os.path.splitext(file)[0]
        tex = unreal.load_asset(TEX + '/' + name)
        if tex is None:
            raise RuntimeError('Texture import failed: ' + file)
        tex.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_EDITOR_ICON)
        tex.set_editor_property('lod_group', unreal.TextureGroup.TEXTUREGROUP_UI)
        tex.set_editor_property('mip_gen_settings', unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        tex.set_editor_property('never_stream', True)
        unreal.EditorAssetLibrary.save_loaded_asset(tex)


def remove_previous_build():
    """Rebuild from scratch: widget names cannot be reused inside an existing tree."""
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actors.get_all_level_actors():
        if TAG in [str(t) for t in actor.tags]:
            actors.destroy_actor(actor)
    for path in (MENU_ACTOR, MENU_WIDGET):
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            if not unreal.EditorAssetLibrary.delete_asset(path):
                raise RuntimeError('Close editors for %s and rerun' % path)


def create_widget_blueprint():
    factory = unreal.WidgetBlueprintFactory()
    factory.set_editor_property('parent_class', unreal.UserWidget)
    return unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        'WBP_ResonanceMenu', UI, unreal.WidgetBlueprint, factory)


# ─── Menu widget ────────────────────────────────────────────────────────────

def build_top_bar(t):
    t.glass('TopBar', 'Root', radius=20, pad=(18, 10, 12, 10))
    t.place('TopBar', 28, 20, DRAW_SIZE[0] - 56, 78)
    t.add('HorizontalBox', 'TopRow', 'TopBar')
    t.add('Image', 'LogoMark', 'TopRow', Brush=image('T_ResonanceLogoMark', 62, 50))
    t.slot('LogoMark', pad=(0, 0, 12, 0), v='CENTER')
    t.text('Brand', 'TopRow', 'Resonance', 28, 'Bold', 'navy')
    t.slot('Brand', v='CENTER')
    t.add('SizeBox', 'TopSpacer', 'TopRow')
    t.slot('TopSpacer', fill=True)
    t.add('Border', 'Tabs', 'TopRow', Background=rounded([1, 1, 1, 0.28], 13, [1, 1, 1, 0.5]),
          Padding=margin(4, 4, 4, 4))
    t.slot('Tabs', v='CENTER')
    t.add('HorizontalBox', 'TabRow', 'Tabs')
    for tab in TABS:
        t.button('Tab' + tab, 'TabRow', tab, 'tab', 19)
        t.slot('Tab' + tab, pad=(2, 0, 2, 0))


def build_landing(t, c):
    t.add('HorizontalBox', 'ScreenLanding', 'Root')
    t.place('ScreenLanding', 64, 128, 1312, 720)
    t.add('VerticalBox', 'LandingText', 'ScreenLanding')
    t.slot('LandingText', fill=True, v='CENTER', pad=(0, 0, 56, 0))
    t.text('Headline', 'LandingText', c['headline'], 62, 'Bold', 'ink', wrap=680)
    t.text('Lead', 'LandingText', c['body'], 24, 'Regular', 'ink_muted', wrap=600)
    t.slot('Lead', pad=(0, 22, 0, 30))
    t.button('StartButton', 'LandingText', c['start'], 'primary')
    t.slot('StartButton', h='LEFT')
    t.glass('Steps', 'LandingText', radius=20, pad=(26, 22, 26, 22))
    t.slot('Steps', pad=(0, 40, 0, 0))
    t.add('HorizontalBox', 'StepRow', 'Steps')
    for i, (title, body) in enumerate(c['steps'], 1):
        name = 'Step%d' % i
        t.add('VerticalBox', name, 'StepRow')
        t.slot(name, fill=True, pad=(0 if i == 1 else 22, 0, 0, 0))
        t.label(name + 'Number', name, 'Step %d' % i)
        t.text(name + 'Title', name, title, 21, 'Bold')
        t.slot(name + 'Title', pad=(0, 6, 0, 2))
        t.text(name + 'Body', name, body, 17, 'Regular', 'ink_muted', wrap=180)
    t.glass('Hero', 'ScreenLanding', radius=26, pad=(64, 64, 64, 64))
    t.slot('Hero', v='CENTER')
    t.add('Image', 'HeroLogo', 'Hero', Brush=image('T_ResonanceLogo', 430, 358))


def build_home(t, content):
    anna = content['clients'][0]
    scenario = content['scenarios'][0]
    t.add('VerticalBox', 'ScreenHome', 'Root')
    t.place('ScreenHome', 64, 136, 1312, 700)
    t.text('HomeTitle', 'ScreenHome', 'Welcome back.', 46, 'Bold')
    t.glass('Continue', 'ScreenHome', radius=22, pad=(32, 26, 32, 26), dark=True)
    t.slot('Continue', pad=(0, 28, 0, 0))
    t.add('HorizontalBox', 'ContinueRow', 'Continue')
    t.add('VerticalBox', 'ContinueText', 'ContinueRow')
    t.slot('ContinueText', fill=True, v='CENTER')
    t.label('ContinueLabel', 'ContinueText', 'Next practice', 'glow')
    t.text('ContinueTitle', 'ContinueText', '%s · %s' % (anna['name'], scenario['title']), 30, 'Bold', 'on_navy')
    t.slot('ContinueTitle', pad=(0, 8, 0, 6))
    t.text('ContinueSummary', 'ContinueText', scenario['summary'], 19, 'Regular', 'on_navy')
    t.button('ContinueButton', 'ContinueRow', 'Prepare session', 'secondary', 20)
    t.slot('ContinueButton', v='CENTER')


def build_people(t, content):
    t.add('VerticalBox', 'ScreenPeople', 'Root')
    t.place('ScreenPeople', 64, 136, 1312, 700)
    t.text('PeopleTitle', 'ScreenPeople', 'People', 46, 'Bold')
    for i, client in enumerate(content['clients']):
        name = 'Client%d' % i
        t.glass(name, 'ScreenPeople', radius=18, pad=(28, 20, 28, 20))
        t.slot(name, pad=(0, 24 if i == 0 else 12, 0, 0))
        t.add('HorizontalBox', name + 'Row', name)
        t.add('VerticalBox', name + 'Text', name + 'Row')
        t.slot(name + 'Text', fill=True)
        t.text(name + 'Name', name + 'Text', '%s, %d' % (client['name'], client['age']), 26, 'Bold')
        t.text(name + 'Situation', name + 'Text', client['situation'], 18, 'Regular', 'ink_muted')
        status = client['difficulty'] if client['available'] else 'Coming later'
        t.label(name + 'Status', name + 'Row', status, 'blue' if client['available'] else 'ink_faint')
        t.slot(name + 'Status', v='CENTER')
        if not client['available']:
            t.prop(name, 'RenderOpacity', 0.55)


def build_sessions(t):
    t.add('VerticalBox', 'ScreenSessions', 'Root')
    t.place('ScreenSessions', 64, 136, 1312, 700)
    t.text('SessionsTitle', 'ScreenSessions', 'Sessions', 46, 'Bold')
    t.glass('SessionsEmpty', 'ScreenSessions', radius=18, pad=(28, 26, 28, 26))
    t.slot('SessionsEmpty', pad=(0, 24, 0, 0))
    t.text('SessionsEmptyText', 'SessionsEmpty',
           'No sessions yet. Finished practice sessions will appear here.', 20, 'Regular', 'ink_muted')


def build_navigation(bp, palette):
    """ShowLanding/ShowHome/... events toggle screen visibility and the active tab label."""
    g = Graph(bp)  # drop the template's ghost Construct/Tick nodes before adding our own
    for screen in SCREENS:
        g.node('show_' + screen, 'CustomEvent', event_name='Show' + screen)
    checked(H.compile_blueprint(bp))
    for screen in SCREENS:
        steps = ['show_' + screen]
        for other in SCREENS:
            key = '%s_%s' % (screen, other)
            g.node(key + '_get', 'VariableGet', variable_name='Screen' + other)
            g.call(key, 'Widget', 'SetVisibility',
                   InVisibility='SelfHitTestInvisible' if other == screen else 'Collapsed')
            g.wire(key + '_get', 'Screen' + other, key, 'self')
            steps.append(key)
        for tab in TABS:
            key = '%s_tab_%s' % (screen, tab)
            g.node(key + '_get', 'VariableGet', variable_name='Tab%sLabel' % tab)
            g.call(key, 'TextBlock', 'SetColorAndOpacity',
                   InColorAndOpacity=slate(palette['ink'] if tab == screen else palette['ink_muted']))
            g.wire(key + '_get', 'Tab%sLabel' % tab, key, 'self')
            steps.append(key)
        g.flow(*steps)
    for widget, screen in [('TabHome', 'Home'), ('TabPeople', 'People'), ('TabSessions', 'Sessions'),
                           ('StartButton', 'Home'), ('ContinueButton', 'People')]:
        bound = checked(H.umg_bind_widget_event(bp, widget, 'OnClicked'))
        g.nodes['click_' + widget] = bound['node']
        g.call('go_' + widget, '', 'Show' + screen)
        g.flow('click_' + widget, 'go_' + widget)
    g.node('construct', 'Event', event_name='Construct')
    g.call('first', '', 'ShowLanding')
    g.flow('construct', 'first')


def build_menu_widget(content):
    bp = create_widget_blueprint()
    t = Tree(bp, content['palette'])
    t.add('CanvasPanel', 'Root')
    t.add('Image', 'Stage', 'Root', Brush=image('T_ResonanceStage', *DRAW_SIZE))
    t.place('Stage', 0, 0, *DRAW_SIZE)
    build_top_bar(t)
    build_landing(t, content['landing'])
    build_home(t, content)
    build_people(t, content)
    build_sessions(t)
    for screen in SCREENS[1:]:
        t.prop('Screen' + screen, 'Visibility', 'Collapsed')
    checked(H.compile_blueprint(bp))
    build_navigation(bp, content['palette'])
    checked(H.compile_blueprint(bp))
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    return bp


# ─── Input, menu actor and pointers ─────────────────────────────────────────

def build_input_assets():
    assets = unreal.AssetToolsHelpers.get_asset_tools()
    context = unreal.load_asset(CONTEXT) or assets.create_asset(
        'IMC_ResonanceMenu', INPUT, unreal.InputMappingContext, unreal.InputMappingContext_Factory())
    context.unmap_all()
    for hand, key_name in SELECT.items():
        name = 'IA_ResonanceSelect' + hand
        action = unreal.load_asset(INPUT + '/' + name) or assets.create_asset(
            name, INPUT, unreal.InputAction, unreal.InputAction_Factory())
        action.set_editor_property('value_type', unreal.InputActionValueType.BOOLEAN)
        key = unreal.Key()
        key.set_editor_property('key_name', key_name)
        context.map_key(action, key)
        unreal.EditorAssetLibrary.save_loaded_asset(action)
    context.set_editor_property('context_description', 'VR menu: either trigger clicks what that hand points at')
    unreal.EditorAssetLibrary.save_loaded_asset(context)
    # Listed like IMC_ResonanceFaceModes so OpenXR builds bindings for these keys.
    settings = unreal.get_default_object(unreal.load_class(None, '/Script/EnhancedInput.EnhancedInputDeveloperSettings'))
    defaults = list(settings.get_editor_property('DefaultMappingContexts'))
    if defaults and not any(e.get_editor_property('InputMappingContext') == context for e in defaults):
        entry = defaults[0].copy()
        entry.set_editor_property('InputMappingContext', context)
        entry.set_editor_property('Priority', 40)
        entry.set_editor_property('bAddImmediately', False)
        entry.set_editor_property('bRegisterWithUserSettings', False)
        defaults.append(entry)
        settings.set_editor_property('DefaultMappingContexts', defaults)


def build_menu_actor(widget):
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('parent_class', unreal.Actor)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        'BP_ResonanceMenu', BLUEPRINTS, unreal.Blueprint, factory)
    checked(H.add_component_to_blueprint(bp, '/Script/UMG.WidgetComponent', 'Panel', 0, 0, 0, 0, 0, 0, ''))
    for prop, value in [('WidgetClass', widget.generated_class().get_path_name()),
                        ('DrawSize', '(X=%d,Y=%d)' % DRAW_SIZE),
                        ('GeometryMode', 'Cylinder'),
                        ('CylinderArcAngle', str(PANEL_ARC)),
                        ('BlendMode', 'Transparent'),
                        ('RelativeScale3D', '(X=%s,Y=%s,Z=%s)' % ((PANEL_SCALE,) * 3))]:
        checked(H.set_component_property(bp, 'Panel', prop, value))
    checked(H.compile_blueprint(bp))
    # Register the menu input context for the local player (same nodes as the face-mode input).
    g = Graph(bp)
    g.node('begin', 'Event', event_name='ReceiveBeginPlay')
    g.call('controller', 'GameplayStatics', 'GetPlayerController', PlayerIndex=0)
    g.call('subsystem', 'SubsystemBlueprintLibrary', 'GetLocalPlayerSubSystemFromPlayerController',
           Class='/Script/EnhancedInput.EnhancedInputLocalPlayerSubsystem')
    g.wire('controller', 'ReturnValue', 'subsystem', 'PlayerController')
    g.node('cast', 'CastTo', cast_class='/Script/EnhancedInput.EnhancedInputLocalPlayerSubsystem')
    g.wire('subsystem', 'ReturnValue', 'cast', 'Object')
    g.flow('begin', 'cast')
    g.call('mapping', 'EnhancedInputSubsystemInterface', 'AddMappingContext',
           MappingContext=CONTEXT + '.IMC_ResonanceMenu', Priority=40)
    g.wire('cast', cast_result(bp, g.nodes['cast']), 'mapping', 'self')
    g.flow('cast', 'mapping')
    checked(H.compile_blueprint(bp))
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    return bp


def ensure_component(bp, existing, path, name, parent, **props):
    if name not in existing:
        checked(H.add_component_to_blueprint(bp, path, name, 0, 0, 0, 0, 0, 0, parent))
    for prop, value in props.items():
        checked(H.set_component_property(bp, name, prop, str(value)))


def build_viewer_pointers():
    bp = unreal.load_asset(VIEWER)
    nodes = ace.info(bp, 'EventGraph')
    events = {hand: next((n for n in nodes if n['node_class'] == 'K2Node_EnhancedInputAction'
                          and 'IA_ResonanceSelect' + hand in n['node_title']), None) for hand in SELECT}
    if not all(events.values()):
        raise RuntimeError('Paste menu_input_nodes.txt into the BP_ResonanceViewer EventGraph once, then rerun')
    existing = {c['variable_name'] for c in checked(H.list_blueprint_components(bp))['components']}
    for index, hand in enumerate(SELECT):
        # The OpenXR aim pose points along the controller's ray, unlike the grip pose.
        ensure_component(bp, existing, '/Script/HeadMountedDisplay.MotionControllerComponent',
                         hand + 'Hand', 'TrackingOrigin', MotionSource=hand + 'Aim')
        ensure_component(bp, existing, '/Script/UMG.WidgetInteractionComponent',
                         hand + 'Pointer', hand + 'Hand', PointerIndex=index, VirtualUserIndex=0,
                         InteractionDistance=400, bShowDebug='true',
                         DebugColor='(R=0.07,G=0.42,B=0.66,A=1)')
    checked(H.compile_blueprint(bp))
    clean(bp, ('ResonanceMenuInputNodes',))
    g = OwnedGraph(bp, 'ResonanceMenuInputNodes')
    for hand in SELECT:
        g.nodes['event_' + hand] = events[hand]['node_name']
        for phase, function in [('Started', 'PressPointerKey'), ('Completed', 'ReleasePointerKey')]:
            key = '%s_%s' % (hand, function)
            g.node(key + '_get', 'VariableGet', variable_name=hand + 'Pointer')
            g.call(key, 'WidgetInteractionComponent', function, Key='LeftMouseButton')
            g.wire(key + '_get', hand + 'Pointer', key, 'self')
            g.wire('event_' + hand, phase, key, 'execute')
    checked(H.compile_blueprint(bp))
    unreal.EditorAssetLibrary.save_loaded_asset(bp)


def open_level():
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if levels.get_current_level().get_path_name().split('.')[0] != LEVEL:
        levels.load_level(LEVEL)
    return levels


def place_menu(actor_bp):
    levels = open_level()
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    start = next(a for a in actors.get_all_level_actors() if isinstance(a, unreal.PlayerStart))
    forward = start.get_actor_forward_vector()
    # PlayerStart sits at the authored eye position; centre the panel slightly below eye level.
    location = start.get_actor_location() + forward * PANEL_DISTANCE + unreal.Vector(0, 0, -8)
    rotation = start.get_actor_rotation()
    # A widget component's readable face looks along its +X axis, so turn it toward the viewer.
    menu = actors.spawn_actor_from_class(actor_bp.generated_class(), location,
                                         unreal.Rotator(roll=0, pitch=0, yaw=rotation.yaw + 180))
    menu.set_actor_label('Resonance_Menu')
    menu.set_editor_property('tags', [TAG])
    menu.set_folder_path('Resonance/Menu')
    levels.save_current_level()
    return menu


def build():
    content = load_content()
    open_level()  # so the old menu actor is found and removed with its Blueprint
    remove_previous_build()
    import_textures()
    widget = build_menu_widget(content)
    build_input_assets()
    actor_bp = build_menu_actor(widget)
    build_viewer_pointers()
    menu = place_menu(actor_bp)
    print(json.dumps({'success': True, 'widget': MENU_WIDGET, 'actor': MENU_ACTOR,
                      'menu_location': str(menu.get_actor_location())}))


if __name__ == '__main__':
    build()
