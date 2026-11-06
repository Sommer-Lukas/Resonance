"""Isolated, authored trailer. Run setup(), capture(), then build_sequence().

All authored assets live under /Game/ResonanceTrailer. Original assets are
read-only inputs. Capture runs in PIE; it never edits the source character.
"""
import json
import math
from pathlib import Path
import unreal
from build_pitfall import H, checked
import build_resonance_audio2face as ace
from resonance_face_demo import CHANNELS, envelope

ROOT = '/Game/ResonanceTrailer'
MAP = ROOT + '/L_Trailer'
SEQUENCE = ROOT + '/LS_ResonanceTrailer'
FPS = 24
DURATION = 14
_handle = None
_samples = []
_face = None
_audio_start = None
_audio_end = None
_last = -1
_throttle_previous = None


def _require_trailer_map():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split('.')[0] != MAP:
        raise RuntimeError('Open '+MAP+' first; source levels must stay unchanged')


def prepare_capture():
    """Call after loading the trailer map, before starting PIE."""
    _require_trailer_map()
    character().get_component_by_class(unreal.LODSyncComponent).set_editor_property('forced_lod',0)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()


def _restore_throttle():
    global _throttle_previous
    if _throttle_previous is not None:
        settings = unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
        settings.set_editor_property('bThrottleCPUWhenNotForeground',_throttle_previous)
        _throttle_previous = None


def saved():
    p = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / 'ResonanceTrailer'
    p.mkdir(parents=True, exist_ok=True)
    return p


def fear(t):
    """Authored anxiety, preserving ACE mouth/jaw articulation."""
    pulse = .5 + .5 * math.sin(t * 1.7)
    intensity = .65 + .25 * envelope(t, 2, 11, 1.5)
    blink = max((envelope(t, b, b + .24, .10) for b in (1.1, 4.4, 8.2, 8.65, 12.5)), default=0)
    v = dict.fromkeys(CHANNELS, 0.)
    v.update(EyeBlinkLeft=blink, EyeBlinkRight=blink,
             EyeWideLeft=(.40 + .12*pulse)*intensity*(1-blink),
             EyeWideRight=(.43 + .12*pulse)*intensity*(1-blink),
             BrowInnerUp=.85*intensity, BrowOuterUpLeft=.40*intensity,
             BrowOuterUpRight=.35*intensity, BrowDownLeft=.22*intensity,
             BrowDownRight=.27*intensity, CheekSquintLeft=.08, CheekSquintRight=.08)
    return v


def setup():
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
        raise RuntimeError('Stop PIE before setup')
    # Duplicate only; never save the source map or shared animation Blueprint.
    if unreal.EditorAssetLibrary.does_asset_exist(MAP):
        raise RuntimeError('Trailer map already exists; open it to continue. Rebuild into a new folder to preserve edits.')
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split('.')[0] != '/Game/Resonance/Levels/I_Resonance':
        raise RuntimeError('Open the source portrait map first')
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError('Could not save trailer map')
    bp = unreal.load_asset(ROOT + '/ABP_TrailerCapture') or unreal.EditorAssetLibrary.duplicate_asset(ace.FACE, ROOT + '/ABP_TrailerCapture')
    curve_dir = ROOT + '/FearCurves'
    tasks = []
    for channel in CHANNELS:
        source = saved() / ('CF_' + channel + '.csv')
        source.write_text(''.join(f'{i/60:.6f},{fear(i/60)[channel]:.6f}\n' for i in range(2161)), encoding='utf-8')
        settings = unreal.CSVImportSettings()
        settings.set_editor_property('import_type', unreal.CSVImportType.ECSV_CURVE_FLOAT)
        settings.set_editor_property('import_curve_interp_mode', unreal.RichCurveInterpMode.RCIM_LINEAR)
        factory = unreal.CSVImportFactory()
        factory.set_editor_property('automated_import_settings', settings)
        task = unreal.AssetImportTask()
        task.set_editor_properties(dict(filename=str(source), destination_path=curve_dir,
            destination_name='CF_'+channel, automated=True, factory=factory, save=True))
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    nodes = ace.info(bp, 'AnimGraph')
    # Redirect only the copied Blueprint's curve getters.
    for n in nodes:
        if n['node_class'] == 'K2Node_CallFunction':
            for pin in n['pins']:
                if pin['pin_name'] == 'self':
                    for channel in CHANNELS:
                        if 'CF_'+channel in str(pin.get('default_object', '')):
                            checked(H.set_blueprint_node_pin_default(bp, 'AnimGraph', n['node_name'], 'self',
                                curve_dir+'/CF_'+channel+'.CF_'+channel))
    checked(H.compile_blueprint(bp))
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    # save_map writes a copy without changing the active editor world. Load
    # MAP in a separate command after this function has released its world.
    print('Saved trailer map. Open '+MAP+' in a separate command, then capture() and start PIE.')


def character(world=None):
    actors = (unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if world else
              unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    return next(a for a in actors if a.get_class() == unreal.load_asset(ace.CHARACTER).generated_class())


def face(a):
    return next(c for c in a.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Face')


def _started():
    global _audio_start
    if _face is not None and _audio_start is None:
        _audio_start = unreal.GameplayStatics.get_time_seconds(_face.get_world())


def _ended():
    global _audio_end
    if _face is not None and _audio_start is not None:
        _audio_end = unreal.GameplayStatics.get_time_seconds(_face.get_world())


def capture():
    global _handle, _face, _audio_start, _audio_end, _last, _throttle_previous
    _require_trailer_map()
    if _handle is not None:
        raise RuntimeError('Capture already running')
    if character().get_component_by_class(unreal.LODSyncComponent).get_editor_property('forced_lod') != 0:
        raise RuntimeError('Run prepare_capture() before capture() to capture the full face rig')
    settings = unreal.get_default_object(unreal.load_class(None,'/Script/UnrealEd.EditorPerformanceSettings'))
    _throttle_previous = settings.get_editor_property('bThrottleCPUWhenNotForeground')
    settings.set_editor_property('bThrottleCPUWhenNotForeground',False)
    _samples.clear()
    _face, _audio_start, _audio_end, _last = None, None, None, -1
    _handle = unreal.register_slate_post_tick_callback(_tick)


def _tick(delta):
    global _face, _last, _handle
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if not world:
        if _face is not None:
            unreal.unregister_slate_post_tick_callback(_handle)
            _handle = None
            _restore_throttle()
        return
    t = unreal.GameplayStatics.get_time_seconds(world)
    if _face is None:
        a = character(world)
        _face = face(a)
        if _face.get_editor_property('disable_post_process_blueprint'):
            _face.toggle_disable_post_process_blueprint()
        _face.set_animation_mode(unreal.AnimationMode.ANIMATION_BLUEPRINT)
        _face.set_anim_instance_class(unreal.load_asset(ROOT+'/ABP_TrailerCapture').generated_class())
        audio = a.get_component_by_class(unreal.ACEAudioCurveSourceComponent)
        audio.on_animation_started.add_callable(_started)
        audio.on_animation_ended.add_callable(_ended)
        # The source character's BeginPlay is gated to I_Resonance. Explicitly
        # request one speech submission on this PIE copy only.
        a.call_method('ResonanceUseAuthoredFace')
    if t - _last < 1/30:
        return
    _last = t
    anim = _face.get_anim_instance()
    curves = {str(n): anim.get_curve_value(n) for n in anim.get_all_curve_names()}
    bones = []
    for i in range(_face.get_num_bones()):
        name = _face.get_bone_name(i)
        tr = _face.get_bone_transform(name, unreal.RelativeTransformSpace.RTS_PARENT_BONE_SPACE)
        p, q, s = tr.translation, tr.rotation, tr.scale3d
        bones.append([str(name), [p.x,p.y,p.z], [q.x,q.y,q.z,q.w], [s.x,s.y,s.z]])
    _samples.append(dict(time=t, curves=curves, bones=bones))
    if _audio_start is not None and t > _audio_start + 11:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
        _restore_throttle()
        (saved()/'performance.json').write_text(json.dumps(dict(audio_start=_audio_start,
            audio_end=_audio_end, samples=_samples)), encoding='utf-8')
        _face = None
        unreal.log('TRAILER CAPTURE COMPLETE: '+str(len(_samples))+' samples')


def bake_performance():
    """Resample final local bone transforms and wrinkle curves to fixed 24fps."""
    from bisect import bisect_right
    data = json.loads((saved()/'performance.json').read_text(encoding='utf-8'))
    samples = data['samples']
    if not data['audio_start'] or len(samples) < 100:
        raise RuntimeError('Incomplete speech capture')
    times = [s['time'] for s in samples]
    gaps = [b-a for a,b in zip(times,times[1:])]
    speech_gaps = [b-a for a,b in zip(times,times[1:]) if a >= data['audio_start']]
    if max(speech_gaps, default=0) > .15:
        raise RuntimeError('Capture gap exceeds 150ms; repeat capture with foreground editor')
    frames = []
    # Speech starts at trailer second 2, independent of model startup latency.
    for i in range(DURATION*FPS+1):
        t = i/FPS - 2 + data['audio_start']
        j = max(0, min(len(samples)-2, bisect_right(times,t)-1))
        a,b = samples[j:j+2]
        alpha = max(0.,min(1.,(t-a['time'])/(b['time']-a['time'])))
        frames.append((a,b,alpha))
    factory = unreal.AnimSequenceFactory()
    factory.set_editor_property('target_skeleton', unreal.load_asset('/Game/MetaHumans/Common/Face/Face_Archetype_Skeleton'))
    anim = unreal.load_asset(ROOT+'/AS_TrailerFace') or unreal.AssetToolsHelpers.get_asset_tools().create_asset('AS_TrailerFace', ROOT, unreal.AnimSequence, factory)
    if unreal.EditorAssetLibrary.get_metadata_tag(anim,'TrailerBakeComplete') == 'true':
        return anim
    ctrl = anim.controller
    ctrl.open_bracket('Bake trailer final facial output', False)
    ctrl.remove_all_bone_tracks(False)
    unreal.AnimationLibrary.remove_all_curve_data(anim)
    ctrl.set_frame_rate(unreal.FrameRate(120,1), False)
    ctrl.set_frame_rate(unreal.FrameRate(FPS,1), False)
    ctrl.set_number_of_frames(unreal.FrameNumber(DURATION*FPS), False)
    for bone_index, bone in enumerate(samples[0]['bones']):
        name = bone[0]
        positions, rotations, scales = [],[],[]
        for a,b,k in frames:
            ba,bb = a['bones'][bone_index],b['bones'][bone_index]
            positions.append(unreal.Vector(*[x+(y-x)*k for x,y in zip(ba[1],bb[1])]))
            qa,qb=unreal.Quat(*ba[2]),unreal.Quat(*bb[2])
            rotations.append(unreal.MathLibrary.quat_slerp(qa,qb,k))
            scales.append(unreal.Vector(*ba[3]))
        ctrl.add_bone_curve(name, False)
        if not ctrl.set_bone_track_keys(name,positions,rotations,scales,False):
            raise RuntimeError('Failed bone '+name)
    # Attribute/material curves keep the animated MetaHuman skin detail.
    names = sorted(set().union(*(s['curves'] for s in samples)))
    for name in names:
        values = [a['curves'].get(name,0)+(b['curves'].get(name,0)-a['curves'].get(name,0))*k for a,b,k in frames]
        if max(abs(v) for v in values) < .00001:
            continue
        cid=unreal.AnimationCurveIdentifierExtensions.set_curve_identifier(
            unreal.AnimationCurveIdentifier(),name,unreal.RawCurveTrackTypes.RCT_FLOAT)
        ctrl.add_curve(cid,6 if name.startswith('head_wm') else 4,False)
        ctrl.set_curve_keys(cid,[unreal.RichCurveKey(time=i/FPS,value=v,
            interp_mode=unreal.RichCurveInterpMode.RCIM_LINEAR) for i,v in enumerate(values)],False)
    ctrl.close_bracket(False)
    unreal.EditorAssetLibrary.set_metadata_tag(anim,'TrailerBakeComplete','true')
    unreal.EditorAssetLibrary.save_loaded_asset(anim)
    (saved()/'capture_report.json').write_text(json.dumps(dict(samples=len(samples),
        maximum_gap=max(gaps),maximum_speech_gap=max(speech_gaps,default=0),
        audio_start=data['audio_start'],audio_end=data['audio_end'],
        baked_frames=len(frames),duration=DURATION,frame_rate=FPS),indent=2),encoding='utf-8')
    return anim


def build_sequence():
    _require_trailer_map()
    anim = unreal.load_asset(ROOT+'/AS_TrailerFace') or bake_performance()
    a=character()
    f=face(a)
    # The final bake already includes RigLogic bone motion and skin curves.
    f.set_editor_property('disable_post_process_blueprint',True)
    f.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    f.set_animation(anim)
    f.set_position(0.,False)
    assets=unreal.AssetToolsHelpers.get_asset_tools()
    seq=unreal.load_asset(SEQUENCE) or assets.create_asset('LS_ResonanceTrailer',ROOT,unreal.LevelSequence,unreal.LevelSequenceFactoryNew())
    if unreal.EditorAssetLibrary.get_metadata_tag(seq,'TrailerBuildComplete') == 'true':
        raise RuntimeError('Sequence already complete; preserve manual edits')
    for tr in seq.get_tracks():
        seq.remove_track(tr)
    for b in seq.get_bindings():
        b.remove()
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for cam in actors.get_all_level_actors():
        if cam.get_actor_label().startswith('Trailer_Camera_'):
            actors.destroy_actor(cam)
    seq.set_display_rate(unreal.FrameRate(FPS,1))
    seq.set_playback_start(0)
    seq.set_playback_end(DURATION*FPS)
    binding=seq.add_possessable(a)
    fb=seq.add_possessable(f)
    fb.set_parent(binding)
    track=fb.add_track(unreal.MovieSceneSkeletalAnimationTrack)
    section=track.add_section()
    section.set_range(0,DURATION*FPS)
    params=section.get_editor_property('params')
    params.set_editor_property('animation',anim)
    params.set_editor_property('force_custom_mode',True)
    section.set_editor_property('params',params)
    # Three gently moving cinema lenses, all directed at the face.
    cuts=seq.add_track(unreal.MovieSceneCameraCutTrack)
    target=unreal.Vector(161.85,10.03,140.)
    shots=[(0,4,[(0,(48.,-18.,134.)),(4,(65.,-10.,132.))],50.),
           (4,10,[(4,(64.,39.,145.)),(7,(68.,24.,144.)),(10,(70.,13.,143.))],65.),
           (10,14,[(10,(55.,-13.,143.)),(14,(40.,-20.,145.))],55.)]
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for index,(start,end,keys,lens) in enumerate(shots):
        cam=actors.spawn_actor_from_class(unreal.CineCameraActor,unreal.Vector(*keys[0][1]))
        cam.set_actor_label('Trailer_Camera_'+str(index+1))
        cam.set_folder_path('ResonanceTrailer/Cameras')
        cine=cam.get_cine_camera_component()
        cine.set_editor_property('current_focal_length',lens)
        cine.set_editor_property('current_aperture',4.)
        film=cine.get_editor_property('filmback')
        film.set_editor_property('sensor_width',36.)
        film.set_editor_property('sensor_height',20.25)
        cine.set_editor_property('filmback',film)
        focus=cine.get_editor_property('focus_settings')
        focus.set_editor_property('focus_method',unreal.CameraFocusMethod.TRACKING)
        tracking=focus.get_editor_property('tracking_focus_settings')
        tracking.set_editor_property('actor_to_track',a)
        tracking.set_editor_property('relative_offset',unreal.Vector(0,9.4,166.77))
        focus.set_editor_property('tracking_focus_settings',tracking)
        cine.set_editor_property('focus_settings',focus)
        cb=seq.add_possessable(cam)
        tr=cb.add_track(unreal.MovieScene3DTransformTrack)
        sec=tr.add_section()
        sec.set_range(start*FPS,end*FPS)
        channels=sec.get_all_channels()
        for t,position in keys:
            pos=unreal.Vector(*position)
            rot=unreal.MathLibrary.find_look_at_rotation(pos,target)
            vals=(*position,rot.roll,rot.pitch,rot.yaw,1,1,1)
            for ch,v in zip(channels,vals):
                ch.add_key(unreal.FrameNumber(round(t*FPS)),v,
                    interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        cut=cuts.add_section()
        cut.set_range(start*FPS,end*FPS)
        bid=unreal.MovieSceneObjectBindingID()
        bid.set_editor_property('guid',cb.get_id())
        cut.set_camera_binding_id(bid)
    # Native audio track lets Sequencer preview use the same untouched WAV.
    task=unreal.AssetImportTask()
    task.set_editor_properties(dict(filename=str(Path(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_content_dir()))/ace.WAV),destination_path=ROOT,
        destination_name='SW_TrailerVoice',automated=True,save=True))
    assets.import_asset_tasks([task])
    sound=unreal.load_asset(ROOT+'/SW_TrailerVoice')
    audio=seq.add_track(unreal.MovieSceneAudioTrack).add_section()
    audio.set_sound(sound)
    audio.set_range(2*FPS,11*FPS)
    unreal.EditorAssetLibrary.set_metadata_tag(seq,'TrailerBuildComplete','true')
    unreal.EditorAssetLibrary.save_loaded_asset(seq)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    print('TRAILER SEQUENCE READY: '+SEQUENCE)
