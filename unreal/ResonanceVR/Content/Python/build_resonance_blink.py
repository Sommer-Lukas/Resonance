"""Native blink scheduler input to the final AnimationFusion authority."""
from pathlib import Path
import unreal
from build_pitfall import H, checked
from resonance_blink import FIRST_PAUSE, PAUSE, DURATION, STRENGTH, closure

CURVE = '/Game/Resonance/Animation/FaceCurves/CF_NaturalBlink'
VARIABLES = ('BlinkNextTime', 'BlinkStartedAt', 'BlinkDuration',
             'BlinkStrength', 'NaturalBlink')


def bake():
    source = Path(unreal.Paths.project_saved_dir()) / 'NaturalBlink.csv'
    source.write_text(''.join(f'{i/200:.6f},{closure(i/200):.6f}\n' for i in range(201)), encoding='utf-8')
    settings = unreal.CSVImportSettings()
    settings.set_editor_property('import_type', unreal.CSVImportType.ECSV_CURVE_FLOAT)
    settings.set_editor_property('import_curve_interp_mode', unreal.RichCurveInterpMode.RCIM_LINEAR)
    factory = unreal.CSVImportFactory()
    factory.set_editor_property('automated_import_settings', settings)
    task = unreal.AssetImportTask()
    folder, name = CURVE.rsplit('/', 1)
    task.set_editor_properties({'filename': str(source.resolve()), 'destination_path': folder,
                               'destination_name': name, 'automated': True,
                               'replace_existing': True, 'factory': factory, 'save': True})
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    if unreal.load_asset(CURVE) is None:
        raise RuntimeError('Could not import natural blink profile')


def add_scheduler(g, after):
    """Sample random values only on initialization or a new blink, never per frame."""
    g.call('blink_now', 'GameplayStatics', 'GetTimeSeconds')
    g.node('blink_next', 'VariableGet', variable_name='BlinkNextTime')
    g.call('blink_initialized', 'KismetMathLibrary', 'Greater_DoubleDouble', B=0.0)
    g.wire('blink_next', 'BlinkNextTime', 'blink_initialized', 'A')
    g.node('blink_init_gate', 'Branch')
    g.flow(after, 'blink_init_gate')
    g.wire('blink_initialized', 'ReturnValue', 'blink_init_gate', 'Condition')

    def schedule(key, bounds):
        g.call(key + '_random', 'KismetMathLibrary', 'RandomFloatInRange', Min=bounds[0], Max=bounds[1])
        g.call(key + '_time', 'KismetMathLibrary', 'Add_DoubleDouble')
        g.wire('blink_now', 'ReturnValue', key + '_time', 'A')
        g.wire(key + '_random', 'ReturnValue', key + '_time', 'B')
        g.node(key, 'VariableSet', variable_name='BlinkNextTime')
        g.wire(key + '_time', 'ReturnValue', key, 'BlinkNextTime')

    schedule('blink_first', FIRST_PAUSE)
    g.wire('blink_init_gate', 'else', 'blink_first', 'execute')
    g.node('blink_inactive', 'VariableSet', variable_name='BlinkStartedAt',
           pin_defaults={'BlinkStartedAt': '-1000.0'})
    g.node('blink_zero', 'VariableSet', variable_name='NaturalBlink', pin_defaults={'NaturalBlink': '0.0'})
    g.node('blink_default_duration', 'VariableSet', variable_name='BlinkDuration',
           pin_defaults={'BlinkDuration': '0.28'})
    g.flow('blink_first', 'blink_inactive', 'blink_default_duration', 'blink_zero')

    g.call('blink_due', 'KismetMathLibrary', 'GreaterEqual_DoubleDouble')
    g.wire('blink_now', 'ReturnValue', 'blink_due', 'A')
    g.wire('blink_next', 'BlinkNextTime', 'blink_due', 'B')
    g.node('blink_due_gate', 'Branch')
    g.wire('blink_init_gate', 'then', 'blink_due_gate', 'execute')
    g.wire('blink_due', 'ReturnValue', 'blink_due_gate', 'Condition')
    g.node('blink_start', 'VariableSet', variable_name='BlinkStartedAt')
    g.wire('blink_now', 'ReturnValue', 'blink_start', 'BlinkStartedAt')
    g.wire('blink_due_gate', 'then', 'blink_start', 'execute')
    previous = 'blink_start'
    for name, bounds in (('BlinkDuration', DURATION), ('BlinkStrength', STRENGTH)):
        key = 'blink_set_' + name
        g.call(key + '_random', 'KismetMathLibrary', 'RandomFloatInRange', Min=bounds[0], Max=bounds[1])
        g.node(key, 'VariableSet', variable_name=name)
        g.wire(key + '_random', 'ReturnValue', key, name)
        g.flow(previous, key)
        previous = key
    schedule('blink_schedule', PAUSE)
    g.flow(previous, 'blink_schedule')

    g.node('blink_start_value', 'VariableGet', variable_name='BlinkStartedAt')
    g.node('blink_duration_value', 'VariableGet', variable_name='BlinkDuration')
    g.node('blink_strength_value', 'VariableGet', variable_name='BlinkStrength')
    g.call('blink_age', 'KismetMathLibrary', 'Subtract_DoubleDouble')
    g.wire('blink_now', 'ReturnValue', 'blink_age', 'A')
    g.wire('blink_start_value', 'BlinkStartedAt', 'blink_age', 'B')
    g.call('blink_phase', 'KismetMathLibrary', 'Divide_DoubleDouble')
    g.wire('blink_age', 'ReturnValue', 'blink_phase', 'A')
    g.wire('blink_duration_value', 'BlinkDuration', 'blink_phase', 'B')
    g.node('blink_profile', target='CurveFloat', function_name='GetFloatValue',
           pin_defaults={'self': CURVE + '.CF_NaturalBlink'})
    g.wire('blink_phase', 'ReturnValue', 'blink_profile', 'InTime')
    g.call('blink_amplitude', 'KismetMathLibrary', 'Multiply_DoubleDouble')
    g.wire('blink_profile', 'ReturnValue', 'blink_amplitude', 'A')
    g.wire('blink_strength_value', 'BlinkStrength', 'blink_amplitude', 'B')
    g.node('blink_cache', 'VariableSet', variable_name='NaturalBlink')
    g.wire('blink_amplitude', 'ReturnValue', 'blink_cache', 'NaturalBlink')
    g.wire('blink_due_gate', 'else', 'blink_cache', 'execute')
    g.flow('blink_schedule', 'blink_cache')


def connect_pose(g):
    nodes = checked(H.get_blueprint_graph_info(g.bp, 'AnimGraph'))['nodes']
    blink = next((n for n in nodes if n['node_name'].startswith('ResonanceBlinkInput')), None)
    if blink is None:
        raise RuntimeError('Paste the updated ace_face_nodes.txt pose nodes before rebuilding')
    g.nodes['blink_input'] = blink['node_name']
    g.node('blink_value', 'VariableGet', variable_name='NaturalBlink')
    g.wire('blink_value', 'NaturalBlink', 'blink_input', 'Alpha')
