"""Separate ten-second PitFall cinematic; never rebuild the playable exercise.

Run copy_level(), load MAP in a separate editor command, then build().
Preview with render(True); render() exports 4K PNG frames.
"""
import json
import math
from pathlib import Path
import unreal

ROOT = '/Game/PitFallTrailer'
MAP = ROOT + '/L_PitFallTrailer'
SEQUENCE = ROOT + '/LS_PitFallTrailer'
SOURCE = '/Game/Resonance/Levels/PitFallUebung'
FPS = 24
DURATION = 10
_queue = None
_executor = None


def saved():
    folder = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'PitFallTrailer'
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def require_map(path):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split('.')[0] != path:
        raise RuntimeError('Open '+path+' first')
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
        raise RuntimeError('Stop PIE first')


def copy_level():
    require_map(SOURCE)
    if unreal.EditorAssetLibrary.does_asset_exist(MAP):
        raise RuntimeError('Trailer map exists; preserve it and open it to continue')
    if unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        raise RuntimeError('Save current map edits before copying the exercise')
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError('Could not save trailer copy')
    print('Copy saved. Load '+MAP+' in a separate command before build().')


def red_material():
    name='M_TrailerWarningRed'
    asset=unreal.load_asset(ROOT+'/'+name)
    if asset:
        return asset
    asset=unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,ROOT,unreal.Material,unreal.MaterialFactoryNew())
    lib=unreal.MaterialEditingLibrary
    color=lib.create_material_expression(asset,unreal.MaterialExpressionConstant3Vector,-250,0)
    color.set_editor_property('constant',unreal.LinearColor(3.,.012,.004))
    lib.connect_material_property(color,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    asset.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    lib.recompile_material(asset)
    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    return asset


def spawn(cls,label,position):
    actor=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(cls,unreal.Vector(*position))
    actor.set_actor_label(label)
    actor.set_folder_path('PitFallTrailer')
    actor.set_editor_property('tags',['PitFallTrailer'])
    return actor


def warning_strip(label,position,size,material):
    actor=spawn(unreal.StaticMeshActor,label,position)
    actor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
    actor.static_mesh_component.set_material(0,material)
    actor.static_mesh_component.set_collision_profile_name('NoCollision')
    actor.set_actor_scale3d(unreal.Vector(*(v/100 for v in size)))


def light_pulse(sequence,actor,base,index):
    owner=sequence.add_possessable(actor)
    binding=sequence.add_possessable(actor.get_component_by_class(unreal.PointLightComponent))
    binding.set_parent(owner)
    track=binding.add_track(unreal.MovieSceneFloatTrack)
    track.set_property_name_and_path('Intensity','Intensity')
    section=track.add_section()
    section.set_range(-FPS,(DURATION+1)*FPS)
    channel=section.get_all_channels()[0]
    # Slow breathing warning illumination; no strobe or live Blueprint timer.
    for frame in range(-FPS,(DURATION+1)*FPS+1,6):
        strength=.80+.20*math.sin(frame/FPS*math.tau/2.8+index*.6)
        channel.add_key(unreal.FrameNumber(frame),base*strength,
            interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)


def camera_shot(sequence,cuts,index,start,end,lens,keys):
    actor=spawn(unreal.CineCameraActor,'PitFallTrailer_Camera_'+str(index),keys[0][1])
    cine=actor.get_cine_camera_component()
    cine.set_editor_property('current_focal_length',lens)
    cine.set_editor_property('current_aperture',8.)
    film=cine.get_editor_property('filmback')
    film.set_editor_property('sensor_width',36.)
    film.set_editor_property('sensor_height',20.25)
    cine.set_editor_property('filmback',film)
    focus=cine.get_editor_property('focus_settings')
    focus.set_editor_property('focus_method',unreal.CameraFocusMethod.DISABLE)
    cine.set_editor_property('focus_settings',focus)
    binding=sequence.add_possessable(actor)
    section=binding.add_track(unreal.MovieScene3DTransformTrack).add_section()
    section.set_range(-FPS,(DURATION+1)*FPS)
    channels=section.get_all_channels()
    for time,position,target in keys:
        rotation=unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*position),unreal.Vector(*target))
        for channel,value in zip(channels,(*position,rotation.roll,rotation.pitch,rotation.yaw,1,1,1)):
            channel.add_key(unreal.FrameNumber(round(time*FPS)),value,
                interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    cut=cuts.add_section()
    cut.set_range(round(start*FPS),round(end*FPS))
    binding_id=unreal.MovieSceneObjectBindingID()
    binding_id.set_editor_property('guid',binding.get_id())
    cut.set_camera_binding_id(binding_id)


def build():
    require_map(MAP)
    if unreal.EditorAssetLibrary.does_asset_exist(SEQUENCE):
        raise RuntimeError('Trailer sequence exists; preserve manual edits')
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    material=red_material()
    room_lights=[]
    for actor in actors.get_all_level_actors():
        label=actor.get_actor_label()
        if label.startswith('TeleportPad') or label in ('Sign_Title','Sign_Controls','Sign_Finish'):
            actor.set_actor_hidden_in_game(True)
            actor.set_is_temporarily_hidden_in_editor(True)
        if label in ('Deck_Overlook','Mark_Overlook'):
            scale=actor.get_actor_scale3d()
            scale.x=1.0  # one-metre cinematic plank, confined to this copy
            actor.set_actor_scale3d(scale)
        if isinstance(actor,unreal.StaticMeshActor):
            comp=actor.static_mesh_component
            for slot in range(comp.get_num_materials()):
                old=comp.get_material(slot)
                if old and old.get_name()=='M_RouteLight':
                    comp.set_material(slot,material)
        if label.startswith('Light_Room_'):
            comp=actor.get_component_by_class(unreal.PointLightComponent)
            comp.set_intensity(950.)
            comp.set_light_color(unreal.LinearColor(1.,.018,.006))
            comp.set_editor_property('source_radius',25.)
            room_lights.append(actor)
        if label.startswith('Light_Shaft_'):
            comp=actor.get_component_by_class(unreal.PointLightComponent)
            comp.set_intensity(comp.get_editor_property('intensity')*.6)
            comp.set_light_color(unreal.LinearColor(1.,.035,.012))
            comp.set_editor_property('attenuation_radius',800.)
        if isinstance(actor,unreal.PostProcessVolume):
            settings=actor.get_editor_property('settings')
            for prop,value in [('auto_exposure_bias',-.55),('bloom_intensity',.65),
                               ('vignette_intensity',.38)]:
                settings.set_editor_property('override_'+prop,True)
                settings.set_editor_property(prop,value)
            actor.set_editor_property('settings',settings)
    fill=spawn(unreal.PointLight,'Trailer_CoolSteelFill',(0,-100,260))
    comp=fill.get_component_by_class(unreal.PointLightComponent)
    comp.set_editor_property('mobility',unreal.ComponentMobility.MOVABLE)
    comp.set_intensity(140.)
    comp.set_light_color(unreal.LinearColor(.13,.25,.5))
    comp.set_editor_property('attenuation_radius',1900.)
    comp.set_editor_property('cast_shadows',False)
    # Small warning strips repeat down the shaft to make its scale readable.
    for depth in (100,900,1800,3000,4500):
        for side in (-1,1):
            warning_strip('Trailer_WarningX_'+str(depth)+'_'+str(side),
                (0,side*581,-depth),(1000,10,6),material)
            warning_strip('Trailer_WarningY_'+str(depth)+'_'+str(side),
                (side*581,0,-depth),(10,1000,6),material)
    sequence=unreal.AssetToolsHelpers.get_asset_tools().create_asset('LS_PitFallTrailer',
        ROOT,unreal.LevelSequence,unreal.LevelSequenceFactoryNew())
    sequence.set_display_rate(unreal.FrameRate(FPS,1))
    sequence.set_playback_start(0)
    sequence.set_playback_end(FPS*DURATION)
    cuts=sequence.add_track(unreal.MovieSceneCameraCutTrack)
    camera_shot(sequence,cuts,1,0,3.25,24.,[
        (0,(-160,-920,140),(0,-360,-40)),
        (3.25,(-45,-625,120),(0,-180,-190))])
    camera_shot(sequence,cuts,2,3.25,6.5,20.,[
        (3.25,(0,-300,190),(10,80,-2200)),
        (6.5,(125,-140,130),(-40,100,-3000))])
    camera_shot(sequence,cuts,3,6.5,10,22.,[
        (6.5,(160,150,-350),(0,-440,40)),
        (10,(260,300,-1800),(0,-300,120))])
    for index,actor in enumerate(sorted(room_lights,key=lambda a:a.get_actor_label())):
        light_pulse(sequence,actor,950.,index)
    unreal.EditorAssetLibrary.save_loaded_asset(sequence)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    print('PitFall cinematic ready: '+SEQUENCE)


def _finished(executor,success):
    (saved()/'render_result.json').write_text(json.dumps({'success':success}),encoding='utf-8')
    unreal.log('PITFALL TRAILER RENDER COMPLETE: '+str(success))


def render(preview=False,output_directory=None):
    global _queue,_executor
    require_map(MAP)
    if not hasattr(unreal,'MoviePipelineQueueSubsystem'):
        raise RuntimeError('Reopen editor with -EnablePlugins=MovieRenderPipeline')
    _queue=unreal.MoviePipelineQueue()
    job=_queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
    job.job_name='PitFallTrailer_Preview' if preview else 'PitFallTrailer_4K'
    job.map=unreal.SoftObjectPath(MAP+'.L_PitFallTrailer')
    job.sequence=unreal.SoftObjectPath(SEQUENCE+'.LS_PitFallTrailer')
    config=job.get_configuration()
    out=config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    out.output_directory=unreal.DirectoryPath(str(output_directory or saved()/('Preview' if preview else 'Frames4K')))
    out.file_name_format='PitFall.{frame_number}'
    out.output_resolution=unreal.IntPoint(1280,720) if preview else unreal.IntPoint(3840,2160)
    out.use_custom_frame_rate=True
    out.output_frame_rate=unreal.FrameRate(FPS,1)
    out.zero_pad_frame_numbers=4
    out.override_existing_output=False
    config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    aa=config.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    aa.override_anti_aliasing=True
    aa.anti_aliasing_method=unreal.AntiAliasingMethod.AAM_NONE
    aa.spatial_sample_count=1
    aa.temporal_sample_count=1 if preview else 4
    aa.engine_warm_up_count=16
    aa.render_warm_up_count=4
    aa.render_warm_up_frames=True
    if not preview:
        tiles=config.find_or_add_setting_by_class(unreal.MoviePipelineHighResSetting)
        tiles.tile_count=2
        tiles.overlap_ratio=.05
        tiles.allocate_history_per_tile=False
    quality=config.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)
    quality.game_mode_override=unreal.GameModeBase
    quality.cinematic_quality_settings=True
    quality.use_lod_zero=True
    quality.disable_hlo_ds=True
    quality.use_high_quality_shadows=True
    quality.texture_streaming=unreal.MoviePipelineTextureStreamingMethod.NONE
    cvars=config.find_or_add_setting_by_class(unreal.MoviePipelineConsoleVariableSetting)
    for name,value in {'r.MotionBlurQuality':4.,'r.ShadowQuality':5.,
        'r.Streaming.PoolSize':1536.,'r.Shadow.Virtual.MaxPhysicalPages':2048.,
        'r.ScreenPercentage':100.}.items():
        cvars.add_or_update_console_variable(name,value)
    _executor=unreal.MoviePipelinePIEExecutor()
    _executor.on_executor_finished_delegate.add_callable_unique(_finished)
    _executor.execute(_queue)
    print('Rendering PitFall trailer to '+out.output_directory.path)
