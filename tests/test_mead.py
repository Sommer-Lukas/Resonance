# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from voice_face.data.mead import index_mead, parse_mead_path


def test_parse_observed_mead_layouts(tmp_path):
    root = tmp_path / "mead"
    a = root / "video_0" / "front" / "angry" / "level_1" / "001.mp4"
    b = root / "video_1" / "video" / "front" / "happy" / "level_2" / "002.mp4"
    c = root / "audio_0" / "angry" / "level_1" / "001.m4a"
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    c.parent.mkdir(parents=True)
    a.touch()
    b.touch()
    c.touch()

    first = parse_mead_path(a, root)
    second = parse_mead_path(b, root)

    assert first.actor == "video_0"
    assert first.camera == "front"
    assert first.emotion == "angry"
    assert first.audio_path == c.resolve()
    assert first.sample_id == "video_0__front__angry__level_1__001"
    assert second.actor == "video_1"
    assert second.camera == "front"
    assert second.emotion == "happy"
    assert len(index_mead(root)) == 2


def test_parse_current_sibling_video_audio_layout(tmp_path):
    root = tmp_path / "mead"
    video = root / "video_2" / "right_60" / "sad" / "level_2" / "020.mp4"
    audio = root / "audio_2" / "sad" / "level_2" / "020.m4a"
    video.parent.mkdir(parents=True)
    audio.parent.mkdir(parents=True)
    video.touch()
    audio.touch()

    sample = parse_mead_path(video, root)

    assert sample.actor_id == "video_2"
    assert sample.camera == "right_60"
    assert sample.emotion == "sad"
    assert sample.intensity == 2
    assert sample.audio_path == audio.resolve()
    assert sample.sample_id == "video_2__right_60__sad__level_2__020"
