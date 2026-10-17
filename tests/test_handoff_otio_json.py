import json
from pathlib import Path

import pytest

from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.handoff_model import (
    ARTIFACT_KIND,
    HandoffClip,
    HandoffDiagnosticCode,
    HandoffGap,
    HandoffMarker,
    HandoffMediaRef,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
    MarkerColor,
    ReimportedTimeline,
)
from davinci_ai_editor.otio_json import OtioProfile, read_otio, write_otio
from davinci_ai_editor.temporal_mapping import FrameRate

FIXTURES = Path(__file__).parent / "fixtures" / "handoff001"
DF2997 = FrameRate(30000, 1001)


def _golden_timeline() -> HandoffTimeline:
    media = HandoffMediaRef("m1", "/media/a.mov")
    marker = HandoffMarker(FrameRange(11, 12), "beat", MarkerColor.GREEN, "note")
    clip = HandoffClip("c1", media, FrameRange(10, 13), markers=(marker,))
    track = HandoffTrack("V", HandoffTrackKind.VIDEO, (HandoffGap(2), clip))
    return HandoffTimeline("Golden", DF2997, 0, (track,))


def _rich_timeline(media_start: int | None = 86400) -> HandoffTimeline:
    known = HandoffMediaRef("m1", "/media/a b.mov", FrameRange(0, 1000), media_start)
    missing = HandoffMediaRef("m2", None, FrameRange(0, 50), media_start)
    video = HandoffTrack(
        "Picture",
        HandoffTrackKind.VIDEO,
        (
            HandoffGap(10),
            HandoffClip(
                "c1",
                known,
                FrameRange(5, 29),
                markers=(HandoffMarker(FrameRange(6, 7), "mk", MarkerColor.RED, "n"),),
            ),
            HandoffClip("c2", missing, FrameRange(0, 5)),
        ),
    )
    audio = HandoffTrack(
        "Dialogue", HandoffTrackKind.AUDIO, (HandoffClip("a1", known, FrameRange(5, 29), False),)
    )
    return HandoffTimeline("Rich", FrameRate(24, 1), 86400, (video, audio))


def test_default_profile_matches_golden_json() -> None:
    result = write_otio(_golden_timeline())
    golden = (FIXTURES / "golden_default.otio").read_text(encoding="utf-8")
    assert result.text == golden
    assert result.artifact_kind == ARTIFACT_KIND
    assert result.authorizes_import is False
    assert result.diagnostics == ()
    document = json.loads(golden)
    assert document["OTIO_SCHEMA"] == "Timeline.1"
    assert document["tracks"]["OTIO_SCHEMA"] == "Stack.1"
    clip = document["tracks"]["children"][0]["children"][1]
    assert clip["OTIO_SCHEMA"] == "Clip.2"
    assert clip["active_media_reference_key"] == "DEFAULT_MEDIA"
    assert set(clip["media_references"]) == {"DEFAULT_MEDIA"}
    assert clip["markers"][0]["color"] == "GREEN"
    assert clip["source_range"]["start_time"]["rate"] == 30000 / 1001


def test_writer_is_deterministic() -> None:
    first = write_otio(_rich_timeline())
    second = write_otio(_rich_timeline())
    assert first.text is not None and first.text == second.text
    assert first.text.endswith("}\n") and "\r" not in first.text


@pytest.mark.parametrize("timeline", [_golden_timeline(), _rich_timeline(), _rich_timeline(None)])
def test_default_round_trip_is_exact(timeline: HandoffTimeline) -> None:
    written = write_otio(timeline)
    assert written.text is not None
    read = read_otio(written.text)
    assert read.diagnostics == ()
    assert read.timeline == ReimportedTimeline(
        timeline.name, timeline.rate, timeline.start_frame, timeline.tracks
    )
    assert read.evidence_class == "FILE_ROUNDTRIP" and read.native_evidence is False


def test_missing_reference_and_file_url() -> None:
    text = write_otio(_rich_timeline()).text
    assert text is not None
    document = json.loads(text)
    children = document["tracks"]["children"][0]["children"]
    assert children[1]["media_references"]["DEFAULT_MEDIA"]["target_url"] == (
        "file:///media/a%20b.mov"
    )
    missing = children[2]["media_references"]["DEFAULT_MEDIA"]
    assert missing["OTIO_SCHEMA"] == "MissingReference.1"
    assert "target_url" not in missing


def test_resolve_profile_shapes_paths_ranges_and_track_names() -> None:
    result = write_otio(_rich_timeline(), OtioProfile.RESOLVE_SHAPED)
    assert result.text is not None and result.profile is OtioProfile.RESOLVE_SHAPED
    document = json.loads(result.text)
    video, audio = document["tracks"]["children"]
    assert (video["name"], audio["name"]) == ("Video 1", "Audio 1")
    clip = video["children"][1]
    ref = clip["media_references"]["DEFAULT_MEDIA"]
    assert ref["target_url"] == "/media/a b.mov"
    assert clip["source_range"]["start_time"]["value"] == 86405.0
    assert ref["available_range"]["start_time"]["value"] == 86400.0
    assert clip["markers"][0]["marked_range"]["start_time"]["value"] == 86406.0
    read = read_otio(result.text)
    assert read.diagnostics == ()
    assert read.timeline is not None
    assert read.timeline.tracks[0].items == _rich_timeline().tracks[0].items
    assert [t.name for t in read.timeline.tracks] == ["Video 1", "Audio 1"]


def test_resolve_profile_refuses_unknown_media_start() -> None:
    result = write_otio(_rich_timeline(None), OtioProfile.RESOLVE_SHAPED)
    assert result.refused and result.text is None
    assert result.diagnostics[0].code is HandoffDiagnosticCode.MEDIA_START_UNKNOWN
    assert result.authorizes_import is False


def test_resolve_profile_refuses_url_target() -> None:
    media = HandoffMediaRef("m1", "file:///media/a.mov", None, 0)
    track = HandoffTrack("V", HandoffTrackKind.VIDEO, (HandoffClip("c", media, FrameRange(0, 1)),))
    timeline = HandoffTimeline("t", FrameRate(25, 1), 0, (track,))
    result = write_otio(timeline, OtioProfile.RESOLVE_SHAPED)
    assert result.diagnostics[0].code is HandoffDiagnosticCode.UNSUPPORTED_PATH
    assert write_otio(timeline).text is not None


def test_writer_refuses_unknown_kind_color_and_relative_path() -> None:
    media = HandoffMediaRef("m1", "/a.mov")
    unknown_track = HandoffTrack("X", HandoffTrackKind.UNKNOWN, ())
    result = write_otio(HandoffTimeline("t", FrameRate(25, 1), 0, (unknown_track,)))
    assert result.diagnostics[0].code is HandoffDiagnosticCode.UNKNOWN_TRACK_KIND
    marker = HandoffMarker(FrameRange(0, 1), "m")
    clip = HandoffClip("c", media, FrameRange(0, 1), markers=(marker,))
    track = HandoffTrack("V", HandoffTrackKind.VIDEO, (clip,))
    result = write_otio(HandoffTimeline("t", FrameRate(25, 1), 0, (track,)))
    assert result.diagnostics[0].code is HandoffDiagnosticCode.UNKNOWN_MARKER_COLOR
    relative = HandoffClip("c", HandoffMediaRef("m1", "a.mov"), FrameRange(0, 1))
    track = HandoffTrack("V", HandoffTrackKind.VIDEO, (relative,))
    result = write_otio(HandoffTimeline("t", FrameRate(25, 1), 0, (track,)))
    assert result.diagnostics[0].code is HandoffDiagnosticCode.UNSUPPORTED_PATH


def _mutated(path: list[object], value: object) -> str:
    text = write_otio(_golden_timeline()).text
    assert text is not None
    document = json.loads(text)
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return json.dumps(document)


CLIP = ["tracks", "children", 0, "children", 1]


@pytest.mark.parametrize(
    ("path", "value", "code"),
    [
        (["OTIO_SCHEMA"], "Timeline.2", HandoffDiagnosticCode.UNKNOWN_SCHEMA),
        ([*CLIP, "OTIO_SCHEMA"], "Clip.3", HandoffDiagnosticCode.UNKNOWN_SCHEMA),
        ([*CLIP, "OTIO_SCHEMA"], "Transition.1", HandoffDiagnosticCode.UNKNOWN_SCHEMA),
        ([*CLIP, "markers", 0, "OTIO_SCHEMA"], "Marker.3", HandoffDiagnosticCode.UNKNOWN_SCHEMA),
        (
            [*CLIP, "media_references", "DEFAULT_MEDIA", "OTIO_SCHEMA"],
            "ImageSequenceReference.1",
            HandoffDiagnosticCode.UNKNOWN_SCHEMA,
        ),
        (["global_start_time", "rate"], 23.98, HandoffDiagnosticCode.UNKNOWN_RATE),
        (["global_start_time", "rate"], 24.0, HandoffDiagnosticCode.RATE_MISMATCH),
        (
            [*CLIP, "source_range", "start_time", "value"],
            10.5,
            HandoffDiagnosticCode.NON_INTEGRAL_TIME,
        ),
        (
            [*CLIP, "effects"],
            [{"OTIO_SCHEMA": "Effect.1"}],
            HandoffDiagnosticCode.UNSUPPORTED_FEATURE,
        ),
        (
            ["metadata", "davinci_ai_editor", "profile"],
            "SOMETHING",
            HandoffDiagnosticCode.UNKNOWN_SCHEMA,
        ),
    ],
)
def test_reader_reports_unknown_and_unsupported(
    path: list[object], value: object, code: HandoffDiagnosticCode
) -> None:
    result = read_otio(_mutated(path, value))
    assert result.timeline is None
    assert result.diagnostics[-1].code is code
    assert result.evidence_class == "FILE_ROUNDTRIP"


def test_reader_falls_back_to_path_when_nle_dropped_media_id() -> None:
    result = read_otio(_mutated([*CLIP, "media_references", "DEFAULT_MEDIA", "metadata"], {}))
    assert result.timeline is not None
    clip = result.timeline.tracks[0].items[1]
    assert isinstance(clip, HandoffClip)
    assert clip.media.media_id == clip.media.target_path
    assert clip.media.media_start_frame is None
    assert result.timeline.path_identified_media_ids == (clip.media.media_id,)
    assert [d.code for d in result.diagnostics] == [HandoffDiagnosticCode.MISSING_MEDIA_ID]
    assert result.diagnostics[0].severity.value == "WARNING"


def test_reader_refuses_missing_reference_without_media_id() -> None:
    text = write_otio(_rich_timeline()).text
    assert text is not None
    document = json.loads(text)
    document["tracks"]["children"][0]["children"][2]["media_references"]["DEFAULT_MEDIA"][
        "metadata"
    ] = {}
    result = read_otio(json.dumps(document))
    assert result.timeline is None
    assert result.diagnostics[-1].code is HandoffDiagnosticCode.MISSING_MEDIA_ID


def test_reader_keeps_unknown_track_kind_and_color_as_unknown() -> None:
    track_kind = _mutated(["tracks", "children", 0, "kind"], "Data")
    result = read_otio(track_kind)
    assert result.timeline is not None
    assert result.timeline.tracks[0].kind is HandoffTrackKind.UNKNOWN
    assert result.diagnostics[0].code is HandoffDiagnosticCode.UNKNOWN_TRACK_KIND
    color = read_otio(_mutated([*CLIP, "markers", 0, "color"], "TEAL"))
    assert color.timeline is not None
    clip = color.timeline.tracks[0].items[1]
    assert isinstance(clip, HandoffClip)
    assert clip.markers[0].color is MarkerColor.UNKNOWN


def test_reader_rejects_malformed_json() -> None:
    result = read_otio("{not json")
    assert result.timeline is None
    assert result.diagnostics[0].code is HandoffDiagnosticCode.MALFORMED_DOCUMENT
