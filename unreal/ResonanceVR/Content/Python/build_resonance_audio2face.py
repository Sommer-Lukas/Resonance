"""Rebuild the fixed-audio ACE portrait demo in UE 5.6.

First paste ace_face_nodes.txt into ABP_ResonanceFace's AnimGraph and
ace_async_node.txt into the portrait MetaHuman's EventGraph. These two node
types are not supported by the installed MCP graph creation helper.
All playback then runs as compiled Blueprint, without editor Python.
"""
import json
import unreal
from build_pitfall import Graph, H, checked

FACE = '/Game/Resonance/Animation/ABP_ResonanceFace'
CHARACTER = '/Game/MetaHumans/New_realistic_character/BP_New_realistic_character'
FORCED_LOD = 2
PROVIDER = 'LocalA2F-James'
EMODB_WAV = 'Resonance/Audio/emodb_2.0/wav/08b03Tc.wav'
WAV = 'Resonance/Audio/voice_test.wav'
# Local ACE forwards this enable flag even when no individual override is
# active. Explicitly disable application blending for audio-only inference.
MODEL_EMOTION = ('(OverallEmotionStrength=1.0,DetectedEmotionContrast=1.0,'
                 'MaxDetectedEmotions=3,DetectedEmotionSmoothing=0.7,'
                 'bEnableEmotionOverride=False,EmotionOverrideStrength=0.0)')
# Diffusion supplies expressive motion at normal face/blink strength.
MODEL_FACE_PARAMETERS = {'upperFaceStrength': 1.0, 'blinkStrength': 1.0}


def configure_speech(bp, node):
    checked(H.set_blueprint_node_pin_default(bp, 'EventGraph', node, 'A2FProviderName', PROVIDER))
    checked(H.set_blueprint_node_pin_default(bp, 'EventGraph', node, 'ACEEmotionParameters', MODEL_EMOTION))


def prepare_face():
    """Create/open the face AnimBlueprint before pasting ace_face_nodes.txt."""
    bp = unreal.load_asset(FACE)
    if bp is None:
        factory = unreal.AnimBlueprintFactory()
        factory.set_editor_property('target_skeleton', unreal.load_asset(
            '/Game/MetaHumans/Common/Face/Face_Archetype_Skeleton'))
        bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            'ABP_ResonanceFace', '/Game/Resonance/Animation', unreal.AnimBlueprint, factory)
    unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([bp])
    return bp


def info(bp, graph):
    return checked(H.get_blueprint_graph_info(bp, graph))['nodes']


def build_face():
    bp = unreal.load_asset(FACE)
    nodes = info(bp, 'AnimGraph')
    by_class = {n['node_class']: n['node_name'] for n in nodes}
    fusion = next((n for n in nodes if n['node_name'].startswith('ResonanceAnimationFusion')), None)
    if fusion:
        by_class['AnimGraphNode_ModifyCurve'] = fusion['node_name']
    chain = [('AnimGraphNode_CopyPoseFromMesh', 'Pose', 'AnimGraphNode_ApplyACEAnimation', 'Source'),
             ('AnimGraphNode_ApplyACEAnimation', 'Pose', 'AnimGraphNode_PoseBlendNode', 'SourcePose'),
             ('AnimGraphNode_PoseBlendNode', 'Pose', 'AnimGraphNode_Root', 'Result')]
    if 'AnimGraphNode_ModifyCurve' in by_class:
        chain[1:2] = [
            ('AnimGraphNode_ApplyACEAnimation', 'Pose', 'AnimGraphNode_ModifyCurve', 'SourcePose'),
            ('AnimGraphNode_ModifyCurve', 'Pose', 'AnimGraphNode_PoseBlendNode', 'SourcePose')]
        blink = next((n for n in nodes if n['node_name'].startswith('ResonanceBlinkInput')), None)
        if blink:
            by_class['BlinkInput'] = blink['node_name']
            chain[1:2] = [
                ('AnimGraphNode_ApplyACEAnimation', 'Pose', 'BlinkInput', 'SourcePose'),
                ('BlinkInput', 'Pose', 'AnimGraphNode_ModifyCurve', 'SourcePose')]
    for source, output, dest, pin in chain:
        checked(H.connect_blueprint_pins(bp, 'AnimGraph', by_class[source], output, by_class[dest], pin))
    checked(H.compile_blueprint(bp))
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    return bp


def build():
    face = build_face()
    bp = unreal.load_asset(CHARACTER)
    components = checked(H.list_blueprint_components(bp))['components']
    if not any(c['variable_name'] == 'ResonanceACEAudio' for c in components):
        checked(H.add_component_to_blueprint(bp, '/Script/ACERuntime.ACEAudioCurveSourceComponent',
                                           'ResonanceACEAudio', 0, 0, 0, 0, 0, 0, 'Face'))
    checked(H.set_component_property(bp, 'Face', 'AnimClass', face.generated_class().get_path_name()))
    checked(H.set_component_property(bp, 'Face', 'VisibilityBasedAnimTickOption', 'AlwaysTickPoseAndRefreshBones'))
    checked(H.compile_blueprint(bp))
    nodes = info(bp, 'EventGraph')
    async_nodes = [n for n in nodes if n['node_class'] == 'K2Node_AsyncAction'
                   and 'AnimateCharacterFromWavFileAsync' in n['node_title'].replace(' ', '')]
    if len(async_nodes) != 1:
        raise RuntimeError('Paste ace_async_node.txt into the MetaHuman EventGraph exactly once')
    # Preserve the imported MetaHuman's existing initialization logic.
    previous = unreal.EditorAssetLibrary.get_metadata_tag(bp, 'ResonanceACEDemoNodes')
    for name in json.loads(previous or '[]'):
        if any(n['node_name'] == name for n in nodes):
            checked(H.remove_blueprint_node(bp, 'EventGraph', name))
    g = Graph(bp, clear=False)
    g.nodes['speech'] = async_nodes[0]['node_name']
    begin = next(n for n in nodes if n['node_title'] == 'Event BeginPlay')
    g.nodes['begin'] = begin['node_name']
    if any(p.get('linked_to') for p in begin['pins'] if p['pin_name'] == 'then'):
        # On rebuild the old demo nodes above have already been removed.
        refreshed = next(n for n in info(bp, 'EventGraph') if n['node_name'] == begin['node_name'])
        if any(p.get('linked_to') for p in refreshed['pins'] if p['pin_name'] == 'then'):
            raise RuntimeError('BeginPlay already has unrelated behavior; preserve it before wiring the demo')
    g.call('delay', 'KismetSystemLibrary', 'Delay', Duration=2.0)
    g.call('level', 'GameplayStatics', 'GetCurrentLevelName', bRemovePrefixString='true')
    g.call('portrait', 'KismetStringLibrary', 'EqualEqual_StrStr', B='I_Resonance')
    g.node('only_portrait', 'Branch')
    g.wire('level', 'ReturnValue', 'portrait', 'A')
    g.wire('portrait', 'ReturnValue', 'only_portrait', 'Condition')
    g.call('content', 'KismetSystemLibrary', 'GetProjectContentDirectory')
    g.call('path', 'KismetStringLibrary', 'Concat_StrStr', B=WAV)
    g.node('audio', 'VariableGet', variable_name='ResonanceACEAudio')
    g.call('owner', 'ActorComponent', 'GetOwner')
    g.wire('audio', 'ResonanceACEAudio', 'owner', 'self')
    g.wire('owner', 'ReturnValue', 'speech', 'Character')
    g.wire('content', 'ReturnValue', 'path', 'A')
    g.wire('path', 'ReturnValue', 'speech', 'PathToWav')
    configure_speech(bp, g.nodes['speech'])
    g.flow('begin', 'level', 'only_portrait', 'delay')
    g.wire('delay', 'then', 'speech', 'execute')
    # Sending completion is distinct from audible playback ending.
    g.node('sent', 'Branch')
    g.wire('speech', 'AudioSendCompleted', 'sent', 'execute')
    g.wire('speech', 'bSuccess', 'sent', 'Condition')
    g.call('success', 'KismetSystemLibrary', 'PrintString', InString='ACE audio submission completed', bPrintToScreen='false')
    g.call('failure', 'KismetSystemLibrary', 'PrintString', InString='ACE FAILED: check LogACECore and LogA2FLocal; local Claire provider required')
    g.wire('sent', 'then', 'success', 'execute')
    g.wire('sent', 'else', 'failure', 'execute')
    # Mark only the demo's own nodes so the builder is safe to run again.
    unreal.EditorAssetLibrary.set_metadata_tag(bp, 'ResonanceACEDemoNodes', json.dumps(
        [name for key, name in g.nodes.items() if key not in ('begin', 'speech')]))
    unreal.EditorAssetLibrary.set_metadata_tag(bp, 'ResonanceACEPortraitGate', g.nodes['only_portrait'])
    unreal.EditorAssetLibrary.set_metadata_tag(bp, 'ResonanceACESpeechDelay', g.nodes['delay'])
    checked(H.compile_blueprint(bp))
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    # Apply to the placed portrait too; construction may have instance overrides.
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actors.get_all_level_actors():
        if actor.get_class() == bp.generated_class():
            mesh = next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Face')
            mesh.set_anim_instance_class(face.generated_class())
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    print(json.dumps({'success': True, 'face': FACE, 'provider': PROVIDER, 'wav': WAV}))


if __name__ == '__main__':
    build()
