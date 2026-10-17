import pytest

from davinci_ai_editor.domain import (
    Clip,
    ClipId,
    FrameRange,
    MediaId,
    TimelineId,
    TimelineSnapshot,
    TimelineVersion,
    Track,
    TrackId,
    TrackType,
)
from davinci_ai_editor.handoff_model import (
    ARTIFACT_KIND,
    HandoffClip,
    HandoffGap,
    HandoffMarker,
    HandoffMediaRef,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
    MarkerColor,
    file_url_to_path,
    handoff_from_snapshot,
    has_url_scheme,
    path_to_file_url,
)
from davinci_ai_editor.temporal_mapping import FrameRate

R24 = FrameRate(24, 1)
M1 = HandoffMediaRef("m1", "/media/a.mov", FrameRange(0, 500), 86400)
M2 = HandoffMediaRef("m2", None)


def _clip(clip_id: str, media: str, timeline: tuple[int, int], source: tuple[int, int]) -> Clip:
    return Clip(ClipId(clip_id), MediaId(media), FrameRange(*timeline), FrameRange(*source))


def _snapshot() -> TimelineSnapshot:
    return TimelineSnapshot(
        TimelineId("tl"),
        TimelineVersion(3),
        (
            Track(
                TrackId("V1"),
                (
                    _clip("c1", "m1", (10, 20), (100, 110)),
                    _clip("c2", "m1", (20, 30), (200, 210)),
                    _clip("c3", "m2", (45, 50), (0, 5)),
                ),
                TrackType.VIDEO,
            ),
            Track(TrackId("A1"), (_clip("a1", "m1", (0, 30), (300, 330)),), TrackType.AUDIO),
            Track(TrackId("X"), (), TrackType.UNKNOWN),
        ),
    )


def test_builder_derives_ordered_gaps_from_snapshot() -> None:
    timeline = handoff_from_snapshot(_snapshot(), {"m1": M1, "m2": M2}, R24, "Expected cut")
    assert timeline.artifact_kind == ARTIFACT_KIND == "EXPECTED_TIMELINE_ARTIFACT"
    assert timeline.authorizes_import is False
    assert timeline.start_frame == 0
    video, audio, unknown = timeline.tracks
    assert video == HandoffTrack(
        "V1",
        HandoffTrackKind.VIDEO,
        (
            HandoffGap(10),
            HandoffClip("c1", M1, FrameRange(100, 110)),
            HandoffClip("c2", M1, FrameRange(200, 210)),
            HandoffGap(15),
            HandoffClip("c3", M2, FrameRange(0, 5)),
        ),
    )
    assert [start for start, _ in video.placements()] == [10, 20, 45]
    assert audio.items == (HandoffClip("a1", M1, FrameRange(300, 330)),)
    assert unknown.kind is HandoffTrackKind.UNKNOWN and unknown.items == ()
    assert timeline.duration == 50
    assert timeline == handoff_from_snapshot(_snapshot(), {"m1": M1, "m2": M2}, R24, "Expected cut")


def test_builder_rejects_missing_media_and_unsupported_tracks() -> None:
    with pytest.raises(ValueError, match="No media reference"):
        handoff_from_snapshot(_snapshot(), {"m1": M1}, R24, "cut")
    with pytest.raises(ValueError, match="does not match"):
        handoff_from_snapshot(_snapshot(), {"m1": M1, "m2": M1}, R24, "cut")
    subtitle = TimelineSnapshot(
        TimelineId("tl"), TimelineVersion(1), (Track(TrackId("S1"), (), TrackType.SUBTITLE),)
    )
    with pytest.raises(ValueError, match="unsupported"):
        handoff_from_snapshot(subtitle, {}, R24, "cut")


def test_artifact_never_authorizes_import() -> None:
    with pytest.raises(ValueError):
        HandoffTimeline("t", R24, 0, (), authorizes_import=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        HandoffTimeline("t", R24, 0, (), artifact_kind="ACTUAL")  # type: ignore[arg-type]


def test_model_validation() -> None:
    with pytest.raises(ValueError):
        HandoffTimeline("t", FrameRate(12, 1), 0, ())
    with pytest.raises(ValueError):
        HandoffTimeline("t", R24, -1, ())
    with pytest.raises(ValueError):
        HandoffMediaRef("", "/a")
    with pytest.raises(ValueError):
        HandoffMediaRef("m", "/a", None, -1)
    with pytest.raises(ValueError):
        HandoffMediaRef("m", "/a", None, True)
    with pytest.raises(ValueError):
        HandoffClip("c", M1, FrameRange(400, 600))
    with pytest.raises(ValueError):
        HandoffClip("c", M1, FrameRange(0, 10), markers=(HandoffMarker(FrameRange(9, 11), "m"),))
    with pytest.raises(TypeError):
        HandoffClip("c", M1, FrameRange(0, 10), enabled=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        HandoffGap(0)
    assert HandoffMediaRef("m", None).media_start_frame is None
    assert HandoffMediaRef("m", None).is_missing
    assert HandoffMarker(FrameRange(0, 1), "m").color is MarkerColor.UNKNOWN


def test_path_helpers() -> None:
    assert path_to_file_url("/media/a b.mov") == "file:///media/a%20b.mov"
    assert path_to_file_url("C:/media/a b.mov") == "file:///C:/media/a%20b.mov"
    assert path_to_file_url("relative/a.mov") is None
    assert path_to_file_url("https://x/a.mov") == "https://x/a.mov"
    assert not has_url_scheme("C:/media/a.mov")
    assert has_url_scheme("file:///a")
    assert file_url_to_path("file:///media/a%20b.mov") == "/media/a b.mov"
    assert file_url_to_path("file:///C:/media/a%20b.mov") == "C:/media/a b.mov"
    assert file_url_to_path("/plain") == "/plain"
