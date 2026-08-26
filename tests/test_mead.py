# pyright: reportMissingImports=false, reportImplicitRelativeImport=false
from pathlib import Path

from voice_face.data.mead import index_mead, parse_mead_path


def test_parse_observed_mead_layouts(tmp_path):
    root = tmp_path / "mead"
    a = root / "video_0" / "front" / "angry" / "level_1" / "001.mp4"
    b = root / "video_1" / "video" / "front" / "happy" / "level_2" / "002.mp4"
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    a.touch()
    b.touch()

    first = parse_mead_path(a, root)
    second = parse_mead_path(b, root)

    assert first.actor == "video_0"
    assert first.camera == "front"
    assert first.emotion == "angry"
    assert first.sample_id == "video_0__front__angry__level_1__001"
    assert second.actor == "video_1"
    assert second.camera == "front"
    assert second.emotion == "happy"
    assert len(index_mead(root)) == 2
