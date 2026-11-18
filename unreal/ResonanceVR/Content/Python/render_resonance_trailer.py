"""Movie Render Queue setup for the isolated trailer; no global config edits.

Enable MovieRenderPipeline for the editor session with
-EnablePlugins=MovieRenderPipeline, then run render(preview=True) or render().
"""
import json
import unreal
import resonance_trailer as trailer

_executor = None
_queue = None


def _finished(executor, success):
    (trailer.saved()/'render_result.json').write_text(json.dumps({'success':success}),encoding='utf-8')
    unreal.log('TRAILER RENDER FINISHED: '+str(success))


def render(preview=False, output_directory=None):
    global _executor, _queue
    if not hasattr(unreal,'MoviePipelineQueueSubsystem'):
        raise RuntimeError('Reopen editor with -EnablePlugins=MovieRenderPipeline; project settings need no changes')
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
        raise RuntimeError('Stop PIE before rendering')
    # Own a separate queue, leaving the user queue untouched.
    _queue=unreal.MoviePipelineQueue()
    job=_queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
    job.job_name='ResonanceTrailer_Preview' if preview else 'ResonanceTrailer_4K'
    job.map=unreal.SoftObjectPath(trailer.MAP+'.L_Trailer')
    job.sequence=unreal.SoftObjectPath(trailer.SEQUENCE+'.LS_ResonanceTrailer')
    config=job.get_configuration()
    out=config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    out.output_directory=unreal.DirectoryPath(str(output_directory or
        trailer.saved()/('Preview' if preview else 'Frames4K')))
    out.file_name_format='Resonance.{frame_number}'
    out.output_resolution=unreal.IntPoint(1280,720) if preview else unreal.IntPoint(3840,2160)
    out.use_custom_frame_rate=True
    out.output_frame_rate=unreal.FrameRate(trailer.FPS,1)
    out.zero_pad_frame_numbers=4
    out.override_existing_output=False
    config.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    if not preview:
        tiles=config.find_or_add_setting_by_class(unreal.MoviePipelineHighResSetting)
        tiles.tile_count=2
        tiles.overlap_ratio=.15
        tiles.allocate_history_per_tile=False
        tiles.override_sub_surface_scattering=True
        tiles.burley_sample_count=64
    aa=config.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    aa.spatial_sample_count=1
    aa.temporal_sample_count=2 if preview else 8
    aa.override_anti_aliasing=True
    aa.anti_aliasing_method=unreal.AntiAliasingMethod.AAM_NONE
    aa.engine_warm_up_count=32
    aa.render_warm_up_count=8
    aa.render_warm_up_frames=True
    quality=config.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)
    quality.game_mode_override=unreal.GameModeBase
    quality.cinematic_quality_settings=True
    quality.use_lod_zero=True
    quality.disable_hlo_ds=True
    quality.use_high_quality_shadows=True
    quality.texture_streaming=unreal.MoviePipelineTextureStreamingMethod.NONE
    cvars=config.find_or_add_setting_by_class(unreal.MoviePipelineConsoleVariableSetting)
    for name,value in {'r.MotionBlurQuality':4.,'r.DepthOfFieldQuality':4.,
        'r.ShadowQuality':5.,'r.ViewDistanceScale':2.,'r.ScreenPercentage':100.,
        'r.Streaming.PoolSize':1536.,'r.Shadow.Virtual.MaxPhysicalPages':4096.}.items():
        cvars.add_or_update_console_variable(name,value)
    _executor=unreal.MoviePipelinePIEExecutor()
    _executor.on_executor_finished_delegate.add_callable_unique(_finished)
    _executor.execute(_queue)
    unreal.log('Started isolated trailer render: '+out.output_directory.path)
