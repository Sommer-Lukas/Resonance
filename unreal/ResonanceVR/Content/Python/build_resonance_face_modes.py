"""Two explicit face modes, safe audio replay and scoped Enhanced Input."""
import json
import unreal
from build_pitfall import Graph, H, checked
import build_resonance_audio2face as ace
from resonance_face_demo import DURATION, PHASES

VIEWER = '/Game/Resonance/Blueprints/BP_ResonanceViewer'
INPUT = '/Game/Resonance/Input'
CONTEXT = INPUT + '/IMC_ResonanceFaceModes'
ACTIONS = {'Authored': ('OculusTouch_Left_X_Click', 'X'),
           'Model': ('OculusTouch_Left_Y_Click', 'Y')}
STATE = {'FaceDemoAuthored': 'bool', 'FaceDemoStartedAt': 'real',
         'FaceAudioSending': 'bool', 'FaceAudioReplayQueued': 'bool'}


class OwnedGraph(Graph):
    """Record mutations as they happen so an interrupted build can be rerun."""
    def __init__(self, bp, tag):
        self.tag, self.owned = tag, []
        super().__init__(bp, clear=False)

    def node(self, key, kind='CallFunction', **kwargs):
        result = super().node(key, kind, **kwargs)
        self.owned.append(self.nodes[key])
        unreal.EditorAssetLibrary.set_metadata_tag(self.bp, self.tag, json.dumps(self.owned))
        return result


def prepare_character():
    bp = unreal.load_asset(ace.CHARACTER)
    names = {v['name'] for v in checked(H.list_blueprint_variables(bp))['variables']}
    for name, kind in STATE.items():
        if name not in names:
            if not unreal.BlueprintEditorLibrary.add_member_variable(bp, name,
                    unreal.BlueprintEditorLibrary.get_basic_type_by_name(kind)):
                raise RuntimeError('Cannot add ' + name)
    components = checked(H.list_blueprint_components(bp))['components']
    if not any(c['variable_name'] == 'ResonanceACEAudio' for c in components):
        checked(H.add_component_to_blueprint(bp, '/Script/ACERuntime.ACEAudioCurveSourceComponent',
                                           'ResonanceACEAudio', 0, 0, 0, 0, 0, 0, 'Face'))
    face = unreal.load_asset(ace.FACE)
    checked(H.set_component_property(bp, 'Face', 'AnimClass', face.generated_class().get_path_name()))
    checked(H.set_component_property(bp, 'Face', 'VisibilityBasedAnimTickOption', 'AlwaysTickPoseAndRefreshBones'))
    checked(H.set_component_property(bp, 'LODSync', 'ForcedLOD', str(ace.FORCED_LOD)))
    checked(H.compile_blueprint(bp))
    return bp


def clean(bp, tags, keep=()):
    nodes = ace.info(bp, 'EventGraph')
    old = set()
    for tag in tags:
        old.update(json.loads(unreal.EditorAssetLibrary.get_metadata_tag(bp, tag) or '[]'))
    for n in nodes:
        if n['node_name'] in old and n['node_name'] not in keep:
            checked(H.remove_blueprint_node(bp, 'EventGraph', n['node_name']))


def cast_result(bp, node):
    info = next(n for n in ace.info(bp, 'EventGraph') if n['node_name'] == node)
    return next(p['pin_name'] for p in info['pins'] if p['direction'] == 'Output' and p['type'] == 'object')


def build_character():
    bp = prepare_character()
    clean(bp, ('ResonanceACEDemoNodes', 'ResonanceFaceLabelNodes', 'ResonanceFaceModeNodes'))
    nodes = ace.info(bp, 'EventGraph')
    g = OwnedGraph(bp, 'ResonanceFaceModeNodes')
    g.nodes['begin'] = next(n['node_name'] for n in nodes if n['node_title'] == 'Event BeginPlay')
    g.nodes['tick'] = next(n['node_name'] for n in nodes if n['node_title'] == 'Event Tick')
    g.nodes['speech'] = next(n['node_name'] for n in nodes if n['node_class'] == 'K2Node_AsyncAction')
    for event in ('begin', 'tick'):
        n = next(n for n in nodes if n['node_name'] == g.nodes[event])
        if any(p.get('linked_to') for p in n['pins'] if p['pin_name'] == 'then'):
            raise RuntimeError('Preserve unrelated ' + event + ' behavior before rebuilding face modes')
    for key, event in [('authored', 'ResonanceUseAuthoredFace'), ('model', 'ResonanceUseModelFace'),
                       ('request', 'ResonanceRequestAudio'), ('cycle', 'ResonanceAudioCycle')]:
        g.node(key, 'CustomEvent', event_name=event)
    checked(H.compile_blueprint(bp))
    g.node('audio', 'VariableGet', variable_name='ResonanceACEAudio')
    g.call('owner', 'ActorComponent', 'GetOwner')
    g.wire('audio', 'ResonanceACEAudio', 'owner', 'self')
    g.call('time', 'GameplayStatics', 'GetTimeSeconds')
    g.call('level', 'GameplayStatics', 'GetCurrentLevelName', bRemovePrefixString='true')
    g.call('portrait', 'KismetStringLibrary', 'EqualEqual_StrStr', B='I_Resonance')
    g.node('gate', 'Branch')
    g.flow('begin', 'level', 'gate')
    g.wire('level', 'ReturnValue', 'portrait', 'A')
    g.wire('portrait', 'ReturnValue', 'gate', 'Condition')
    g.call('delay', 'KismetSystemLibrary', 'Delay', Duration=2.0)
    g.flow('gate', 'delay')
    g.call('start_cycle', '', 'ResonanceAudioCycle')
    g.flow('delay', 'start_cycle')
    # Default is model output with the AnimBlueprint blink input. Both selections reset the local
    # showcase clock and request a replay, coalesced while a send is in flight.
    for key, enabled in [('authored', True), ('model', False)]:
        g.node(key + '_set', 'VariableSet', variable_name='FaceDemoAuthored',
               pin_defaults={'FaceDemoAuthored': str(enabled).lower()})
        g.node(key + '_clock', 'VariableSet', variable_name='FaceDemoStartedAt')
        g.wire('time', 'ReturnValue', key + '_clock', 'FaceDemoStartedAt')
        g.call(key + '_log', 'KismetSystemLibrary', 'PrintString',
               InString='Face mode: ' + ('authored showcase' if enabled else 'James diffusion + procedural blinks'),
               bPrintToScreen='false', bPrintToLog='true')
        g.call(key + '_replay', '', 'ResonanceRequestAudio')
        g.flow(key, key + '_set', key + '_clock', key + '_log', key + '_replay')
    g.node('sending', 'VariableGet', variable_name='FaceAudioSending')
    g.node('busy', 'Branch')
    g.flow('request', 'busy')
    g.wire('sending', 'FaceAudioSending', 'busy', 'Condition')
    g.node('queue', 'VariableSet', variable_name='FaceAudioReplayQueued', pin_defaults={'FaceAudioReplayQueued': 'true'})
    g.wire('busy', 'then', 'queue', 'execute')
    g.node('lock', 'VariableSet', variable_name='FaceAudioSending', pin_defaults={'FaceAudioSending': 'true'})
    g.wire('busy', 'else', 'lock', 'execute')
    g.call('stop', 'ACEBlueprintLibrary', 'StopCharacter')
    g.wire('owner', 'ReturnValue', 'stop', 'Character')
    g.call('settle', 'KismetSystemLibrary', 'Delay', Duration=0.1)
    g.flow('lock', 'stop', 'settle')
    g.call('face_parameters', 'ACEBlueprintLibrary', 'CreateAudio2FaceParameters')
    g.flow('settle', 'face_parameters')
    previous_parameter = 'face_parameters'
    for name, value in ace.MODEL_FACE_PARAMETERS.items():
        key = 'parameter_' + name
        g.call(key, 'Audio2FaceParameters', 'SetParameter', ParamName=name, ParamValue=value)
        g.wire('face_parameters', 'ReturnValue', key, 'self')
        g.flow(previous_parameter, key)
        previous_parameter = key
    g.flow(previous_parameter, 'speech')
    g.wire('face_parameters', 'ReturnValue', 'speech', 'Audio2FaceParameters')
    g.call('content', 'KismetSystemLibrary', 'GetProjectContentDirectory')
    g.call('path', 'KismetStringLibrary', 'Concat_StrStr', B=ace.WAV)
    g.wire('content', 'ReturnValue', 'path', 'A')
    g.wire('path', 'ReturnValue', 'speech', 'PathToWav')
    g.wire('owner', 'ReturnValue', 'speech', 'Character')
    ace.configure_speech(bp, g.nodes['speech'])
    g.node('unlock', 'VariableSet', variable_name='FaceAudioSending', pin_defaults={'FaceAudioSending': 'false'})
    g.wire('speech', 'AudioSendCompleted', 'unlock', 'execute')
    g.node('complete', 'Sequence')
    g.flow('unlock', 'complete')
    g.node('success', 'Branch')
    g.wire('complete', 'then_0', 'success', 'execute')
    g.wire('speech', 'bSuccess', 'success', 'Condition')
    g.call('ok', 'KismetSystemLibrary', 'PrintString', InString='ACE audio submission completed', bPrintToScreen='false')
    g.call('failure', 'KismetSystemLibrary', 'PrintString', InString='ACE audio failed: inspect the Unreal output log')
    g.wire('success', 'then', 'ok', 'execute')
    g.wire('success', 'else', 'failure', 'execute')
    g.node('queued', 'VariableGet', variable_name='FaceAudioReplayQueued')
    g.node('pending', 'Branch')
    g.wire('complete', 'then_1', 'pending', 'execute')
    g.wire('queued', 'FaceAudioReplayQueued', 'pending', 'Condition')
    g.node('clear_queue', 'VariableSet', variable_name='FaceAudioReplayQueued', pin_defaults={'FaceAudioReplayQueued': 'false'})
    g.call('replay', '', 'ResonanceRequestAudio')
    g.flow('pending', 'clear_queue', 'replay')
    g.call('periodic_request', '', 'ResonanceRequestAudio')
    g.call('interval', 'KismetSystemLibrary', 'Delay', Duration=DURATION)
    g.call('repeat', '', 'ResonanceAudioCycle')
    g.flow('cycle', 'periodic_request', 'interval', 'repeat')
    # One status line replaces itself; no delayed authored labels can leak into
    # model mode. Its clock is reset by X, independently of speech warm-up.
    g.node('mode', 'VariableGet', variable_name='FaceDemoAuthored')
    g.node('epoch', 'VariableGet', variable_name='FaceDemoStartedAt')
    g.call('elapsed', 'KismetMathLibrary', 'Subtract_DoubleDouble')
    g.wire('time', 'ReturnValue', 'elapsed', 'A')
    g.wire('epoch', 'FaceDemoStartedAt', 'elapsed', 'B')
    g.call('phase_time', 'KismetMathLibrary', 'Percent_FloatFloat', B=DURATION)
    g.wire('elapsed', 'ReturnValue', 'phase_time', 'A')
    previous = None
    for i in reversed(range(len(PHASES) - 1)):
        g.call('before_' + str(i), 'KismetMathLibrary', 'Less_DoubleDouble', B=PHASES[i+1][0])
        g.wire('phase_time', 'ReturnValue', 'before_' + str(i), 'A')
        g.call('phase_' + str(i), 'KismetMathLibrary', 'SelectString', A='Authored: ' + PHASES[i][1],
               B='Authored: ' + PHASES[-1][1])
        if previous:
            g.wire(previous, 'ReturnValue', 'phase_' + str(i), 'B')
        g.wire('before_' + str(i), 'ReturnValue', 'phase_' + str(i), 'bPickA')
        previous = 'phase_' + str(i)
    g.call('status', 'KismetMathLibrary', 'SelectString', B=ace.PROVIDER + ' + procedural blinks')
    g.wire(previous, 'ReturnValue', 'status', 'A')
    g.wire('mode', 'FaceDemoAuthored', 'status', 'bPickA')
    g.call('instructions', 'KismetStringLibrary', 'Concat_StrStr', A='X: authored showcase | Y: model-driven\n')
    g.wire('status', 'ReturnValue', 'instructions', 'B')
    g.call('label', 'KismetSystemLibrary', 'PrintString', Duration=0.2, Key='ResonanceFaceMode',
           TextColor='(R=0.3,G=0.85,B=1.0,A=1.0)', bPrintToScreen='true', bPrintToLog='false')
    g.wire('instructions', 'ReturnValue', 'label', 'InString')
    g.node('tick_portrait', 'Branch')
    g.wire('portrait', 'ReturnValue', 'tick_portrait', 'Condition')
    g.flow('tick', 'tick_portrait', 'label')
    g.node('end', 'Event', event_name='ReceiveEndPlay')
    g.call('end_stop', 'ACEBlueprintLibrary', 'StopCharacter')
    g.wire('owner', 'ReturnValue', 'end_stop', 'Character')
    g.flow('end', 'end_stop')
    unreal.EditorAssetLibrary.set_metadata_tag(bp, 'ResonanceFaceModeNodes', json.dumps(
        [name for key, name in g.nodes.items() if key not in ('begin', 'tick', 'speech')]))
    for tag in ('ResonanceACEDemoNodes', 'ResonanceFaceLabelNodes'):
        unreal.EditorAssetLibrary.set_metadata_tag(bp, tag, '[]')
    checked(H.compile_blueprint(bp))
    unreal.EditorAssetLibrary.save_loaded_asset(bp)


def build_input_assets():
    assets = unreal.AssetToolsHelpers.get_asset_tools()
    context = unreal.load_asset(CONTEXT) or assets.create_asset('IMC_ResonanceFaceModes', INPUT,
        unreal.InputMappingContext, unreal.InputMappingContext_Factory())
    context.unmap_all()
    for mode, keys in ACTIONS.items():
        name = 'IA_Face' + mode
        action = unreal.load_asset(INPUT + '/' + name) or assets.create_asset(name, INPUT,
            unreal.InputAction, unreal.InputAction_Factory())
        action.set_editor_property('value_type', unreal.InputActionValueType.BOOLEAN)
        action.set_editor_property('consume_input', True)
        for key in keys:
            k = unreal.Key()
            k.set_editor_property('key_name', key)
            context.map_key(action, k)
        unreal.EditorAssetLibrary.save_loaded_asset(action)
    context.set_editor_property('context_description', 'Portrait face modes: X showcase, Y full ACE model')
    unreal.EditorAssetLibrary.save_loaded_asset(context)
    # OpenXR reads this list when constructing each session's action bindings.
    settings = unreal.get_default_object(unreal.load_class(None,
        '/Script/EnhancedInput.EnhancedInputDeveloperSettings'))
    defaults = list(settings.get_editor_property('DefaultMappingContexts'))
    if not any(e.get_editor_property('InputMappingContext') == context for e in defaults):
        entry = defaults[0].copy()
        entry.set_editor_property('InputMappingContext', context)
        entry.set_editor_property('Priority', 30)
        entry.set_editor_property('bAddImmediately', False)
        entry.set_editor_property('bRegisterWithUserSettings', False)
        defaults.append(entry)
        settings.set_editor_property('DefaultMappingContexts', defaults)
    return context


def build_viewer_input():
    bp = unreal.load_asset(VIEWER)
    nodes = ace.info(bp, 'EventGraph')
    events = {mode: next((n for n in nodes if n['node_class'] == 'K2Node_EnhancedInputAction'
                          and 'IA_Face' + mode in n['node_title']), None) for mode in ACTIONS}
    if not all(events.values()):
        raise RuntimeError('Paste face_mode_input_nodes.txt into the portrait viewer EventGraph once')
    begin = next(n for n in nodes if n['node_title'] == 'Event BeginPlay')
    continuation = unreal.EditorAssetLibrary.get_metadata_tag(bp, 'ResonanceViewerBeginContinuation')
    if not continuation:
        continuation = next(p['linked_to'][0]['node_name'] for p in begin['pins'] if p['pin_name'] == 'then')
        unreal.EditorAssetLibrary.set_metadata_tag(bp, 'ResonanceViewerBeginContinuation', continuation)
    cast_names = json.loads(unreal.EditorAssetLibrary.get_metadata_tag(bp, 'ResonanceFaceInputCasts') or '{}')
    target_name = unreal.load_asset(ace.CHARACTER).generated_class().get_name()
    for key in ('cast_Authored', 'cast_Model'):
        existing = next((n for n in nodes if n['node_name'] == cast_names.get(key)), None)
        if existing and not any(p.get('sub_type') == target_name and p['direction'] == 'Output'
                                for p in existing['pins']):
            cast_names.pop(key)
    if not cast_names:
        for n in nodes:
            if n['node_class'] != 'K2Node_DynamicCast':
                continue
            incoming = next((p.get('linked_to', []) for p in n['pins'] if p['pin_name'] == 'execute'), [])
            if not incoming:
                continue
            src = next(x for x in nodes if x['node_name'] == incoming[0]['node_name'])
            if src['node_class'] == 'K2Node_Event' and 'End' in src['node_title']:
                cast_names['end_cast'] = n['node_name']
            elif src['node_title'].startswith('Sequence'):
                cast_names['cast_input'] = n['node_name']
            elif src['node_title'].startswith('Get Actor Of Class'):
                trigger = next(p['linked_to'][0] for p in src['pins'] if p['pin_name'] == 'execute')
                action = next(x for x in nodes if x['node_name'] == trigger['node_name'])
                mode = 'Authored' if 'IA_FaceAuthored' in action['node_title'] else 'Model'
                cast_names['cast_' + mode] = n['node_name']
    clean(bp, ('ResonanceFaceInputNodes',), keep=cast_names.values())
    g = OwnedGraph(bp, 'ResonanceFaceInputNodes')
    g.nodes.update({'begin': begin['node_name'], 'tracking': continuation})
    g.node('setup', 'Sequence')
    g.flow('begin', 'setup')
    g.wire('setup', 'then_0', 'tracking', 'execute')
    g.call('controller', 'GameplayStatics', 'GetPlayerController', PlayerIndex=0)
    g.call('subsystem', 'SubsystemBlueprintLibrary', 'GetLocalPlayerSubSystemFromPlayerController',
           Class='/Script/EnhancedInput.EnhancedInputLocalPlayerSubsystem')
    g.wire('controller', 'ReturnValue', 'subsystem', 'PlayerController')
    def cast(key, target):
        if key in cast_names:
            g.nodes[key] = cast_names[key]
        else:
            g.node(key, 'CastTo', cast_class=target)
            cast_names[key] = g.nodes[key]

    cast('cast_input', '/Script/EnhancedInput.EnhancedInputLocalPlayerSubsystem')
    g.wire('subsystem', 'ReturnValue', 'cast_input', 'Object')
    g.wire('setup', 'then_1', 'cast_input', 'execute')
    g.call('mapping', 'EnhancedInputSubsystemInterface', 'AddMappingContext',
           MappingContext=CONTEXT + '.IMC_ResonanceFaceModes', Priority=30)
    g.wire('cast_input', cast_result(bp, g.nodes['cast_input']), 'mapping', 'self')
    g.flow('cast_input', 'mapping')
    for mode, function in [('Authored', 'ResonanceUseAuthoredFace'), ('Model', 'ResonanceUseModelFace')]:
        g.nodes['event_' + mode] = events[mode]['node_name']
        g.call('find_' + mode, 'GameplayStatics', 'GetActorOfClass', ActorClass=unreal.load_asset(ace.CHARACTER).generated_class().get_path_name())
        cast('cast_' + mode, unreal.load_asset(ace.CHARACTER).generated_class().get_path_name())
        g.wire('find_' + mode, 'ReturnValue', 'cast_' + mode, 'Object')
        g.wire('event_' + mode, 'Started', 'find_' + mode, 'execute')
        g.flow('find_' + mode, 'cast_' + mode)
        g.call('mode_' + mode, unreal.load_asset(ace.CHARACTER).generated_class().get_name(), function)
        g.wire('cast_' + mode, cast_result(bp, g.nodes['cast_' + mode]), 'mode_' + mode, 'self')
        g.flow('cast_' + mode, 'mode_' + mode)
    g.node('end', 'Event', event_name='ReceiveEndPlay')
    cast('end_cast', '/Script/EnhancedInput.EnhancedInputLocalPlayerSubsystem')
    g.wire('subsystem', 'ReturnValue', 'end_cast', 'Object')
    g.flow('end', 'end_cast')
    g.call('unmap', 'EnhancedInputSubsystemInterface', 'RemoveMappingContext', MappingContext=CONTEXT + '.IMC_ResonanceFaceModes')
    g.wire('end_cast', cast_result(bp, g.nodes['end_cast']), 'unmap', 'self')
    g.flow('end_cast', 'unmap')
    unreal.EditorAssetLibrary.set_metadata_tag(bp, 'ResonanceFaceInputNodes', json.dumps(
        [name for key, name in g.nodes.items() if key not in ('begin', 'tracking', 'event_Authored', 'event_Model')]))
    unreal.EditorAssetLibrary.set_metadata_tag(bp, 'ResonanceFaceInputCasts', json.dumps(cast_names))
    checked(H.compile_blueprint(bp))
    unreal.EditorAssetLibrary.save_loaded_asset(bp)


def build():
    build_character()
    build_input_assets()
    build_viewer_input()
    print(json.dumps({'success': True, 'default': 'model-driven', 'X': 'authored', 'Y': 'model-driven'}))
