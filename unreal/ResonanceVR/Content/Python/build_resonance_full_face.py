"""Build selectable authored/model-driven face modes with native Blueprints.

Paste ace_face_nodes.txt once into a fresh ABP_ResonanceFace AnimGraph first.
Python is an editor builder only; runtime needs no Python callbacks.
"""
import json
from pathlib import Path
import unreal
from build_pitfall import Graph, H, checked
import build_resonance_audio2face as ace
from resonance_face_demo import CHANNELS, DURATION, values

CURVES = '/Game/Resonance/Animation/FaceCurves'


def bake_curves():
    folder = Path(unreal.Paths.project_saved_dir()) / 'FaceDemoCurves'
    folder.mkdir(exist_ok=True)
    tasks = []
    samples = [(i / 60.0, values(i / 60.0)) for i in range(int(DURATION * 60) + 1)]
    for channel in CHANNELS:
        source = folder / ('CF_' + channel + '.csv')
        source.write_text(''.join(f'{t:.6f},{v[channel]:.6f}\n' for t, v in samples), encoding='utf-8')
        settings = unreal.CSVImportSettings()
        settings.set_editor_property('import_type', unreal.CSVImportType.ECSV_CURVE_FLOAT)
        settings.set_editor_property('import_curve_interp_mode', unreal.RichCurveInterpMode.RCIM_LINEAR)
        factory = unreal.CSVImportFactory()
        factory.set_editor_property('automated_import_settings', settings)
        task = unreal.AssetImportTask()
        task.set_editor_properties({'filename': str(source.resolve()), 'destination_path': CURVES,
                                   'destination_name': 'CF_' + channel, 'automated': True,
                                   'replace_existing': True, 'factory': factory, 'save': True})
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    for channel in CHANNELS:
        if unreal.load_asset(CURVES + '/CF_' + channel) is None:
            raise RuntimeError('Curve import failed: ' + channel)


def build_animation():
    import build_resonance_blink as blink
    bp = unreal.load_asset(ace.FACE)
    fusion = next((n for n in ace.info(bp, 'AnimGraph') if n['node_name'].startswith('ResonanceAnimationFusion')), None)
    if fusion is None:
        raise RuntimeError('The face AnimGraph must include the AnimationFusion Modify Curve node')
    old = unreal.EditorAssetLibrary.get_metadata_tag(bp, 'ResonanceFaceCurveNodes')
    nodes = ace.info(bp, 'AnimGraph')
    for n in nodes:
        if n['node_name'] in json.loads(old or '[]') or n['node_class'] in ('K2Node_CallFunction', 'K2Node_VariableGet'):
            checked(H.remove_blueprint_node(bp, 'AnimGraph', n['node_name']))
    event_nodes = ace.info(bp, 'EventGraph')
    target_name = unreal.load_asset(ace.CHARACTER).generated_class().get_name()
    actor_cast = next((n for n in event_nodes if n['node_class'] == 'K2Node_DynamicCast'
                       and any(p.get('sub_type') == target_name and p['direction'] == 'Output'
                               for p in n['pins'])), None)
    # Retain the native editor's resolved cast pin type. The installed helper
    # does not notify wildcard pins when creating links programmatically.
    for n in event_nodes:
        if actor_cast is None or n['node_name'] != actor_cast['node_name']:
            checked(H.remove_blueprint_node(bp, 'EventGraph', n['node_name']))
    g = Graph(bp, clear=False)
    unreal.BlueprintEditorLibrary.remove_unused_variables(bp)
    variables = checked(H.list_blueprint_variables(bp))['variables']
    for name in ('DemoTime', 'DemoAlpha') + blink.VARIABLES:
        if not any(v['name'] == name for v in variables):
            if not unreal.BlueprintEditorLibrary.add_member_variable(bp, name,
                    unreal.BlueprintEditorLibrary.get_basic_type_by_name('real')):
                raise RuntimeError('Could not add ' + name)
    checked(H.compile_blueprint(bp))
    g.node('update', 'Event', event_name='BlueprintUpdateAnimation')
    g.call('owner', 'AnimInstance', 'GetOwningActor')
    actor_class = unreal.load_asset(ace.CHARACTER).generated_class().get_path_name()
    if actor_cast:
        g.nodes['portrait_actor'] = actor_cast['node_name']
    else:
        g.node('portrait_actor', 'CastTo', cast_class=actor_class)
    g.wire('owner', 'ReturnValue', 'portrait_actor', 'Object')
    g.flow('update', 'portrait_actor')
    from build_resonance_face_modes import cast_result
    actor_pin = cast_result(bp, g.nodes['portrait_actor'])
    g.node('mode', 'VariableGet', variable_name='FaceDemoAuthored', variable_class=actor_class)
    g.node('epoch', 'VariableGet', variable_name='FaceDemoStartedAt', variable_class=actor_class)
    g.wire('portrait_actor', actor_pin, 'mode', 'self')
    g.wire('portrait_actor', actor_pin, 'epoch', 'self')
    g.call('time', 'GameplayStatics', 'GetTimeSeconds')
    g.call('elapsed', 'KismetMathLibrary', 'Subtract_DoubleDouble')
    g.wire('time', 'ReturnValue', 'elapsed', 'A')
    g.wire('epoch', 'FaceDemoStartedAt', 'elapsed', 'B')
    g.node('cache', 'VariableSet', variable_name='DemoTime')
    g.wire('elapsed', 'ReturnValue', 'cache', 'DemoTime')
    g.flow('portrait_actor', 'cache')
    g.call('alpha', 'KismetMathLibrary', 'SelectFloat', A=1.0, B=0.0)
    g.wire('mode', 'FaceDemoAuthored', 'alpha', 'bPickA')
    g.node('current_alpha', 'VariableGet', variable_name='DemoAlpha')
    g.call('blend', 'KismetMathLibrary', 'FInterpTo', InterpSpeed=12.0)
    g.wire('current_alpha', 'DemoAlpha', 'blend', 'Current')
    g.wire('alpha', 'ReturnValue', 'blend', 'Target')
    g.wire('update', 'DeltaTimeX', 'blend', 'DeltaTime')
    g.node('enable', 'VariableSet', variable_name='DemoAlpha')
    g.wire('blend', 'ReturnValue', 'enable', 'DemoAlpha')
    g.flow('cache', 'enable')
    blink.add_scheduler(g, 'enable')
    # Replace only nodes generated by this builder in the pose graph.
    g = Graph(bp, clear=False, graph_name='AnimGraph')
    g.nodes['fusion'] = fusion['node_name']
    g.node('enabled', 'VariableGet', variable_name='DemoAlpha')
    g.wire('enabled', 'DemoAlpha', 'fusion', 'Alpha')
    blink.connect_pose(g)
    g.node('clock', 'VariableGet', variable_name='DemoTime')
    g.call('cycle', 'KismetMathLibrary', 'Percent_FloatFloat', B=DURATION)
    g.wire('clock', 'DemoTime', 'cycle', 'A')
    # Evaluate bounded authored curves, then replace only our owned regions in
    # one AnimationFusion node before ARKit retargeting. Mouth/jaw pass through.
    for channel in CHANNELS:
        key = 'curve_' + channel
        g.node(key, target='CurveFloat', function_name='GetFloatValue', pin_defaults={
            'self': CURVES + '/CF_' + channel + '.CF_' + channel})
        g.wire('cycle', 'ReturnValue', key, 'InTime')
        pin = next(p['pin_name'] for p in fusion['pins'] if p.get('friendly_name') == channel)
        g.wire(key, 'ReturnValue', 'fusion', pin)
    unreal.EditorAssetLibrary.set_metadata_tag(bp, 'ResonanceFaceCurveNodes', json.dumps(
        [name for key, name in g.nodes.items() if key not in ('fusion', 'blink_input')]))
    checked(H.compile_blueprint(bp))
    unreal.EditorAssetLibrary.save_loaded_asset(bp)


def build():
    import build_resonance_face_modes as modes
    modes.prepare_character()
    import build_resonance_blink as blink
    blink.bake()
    bake_curves()
    build_animation()
    ace.build_face()
    modes.build()
    print(json.dumps({'success': True, 'default_mode': 'model-driven',
                      'cycle_seconds': DURATION, 'authored_channels': list(CHANNELS)}))


if __name__ == '__main__':
    build()
