import xml.etree.ElementTree as ET
from pathlib import Path

from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.handoff_model import (
    ARTIFACT_KIND,
    HandoffClip,
    HandoffDiagnosticCode,
    HandoffGap,
    HandoffMarker,
    HandoffMediaRef,
    HandoffSeverity,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
    MarkerColor,
)
from davinci_ai_editor.temporal_mapping import FrameRate
from davinci_ai_editor.xmeml_writer import write_xmeml

FIXTURES = Path(__file__).parent / "fixtures" / "handoff001"
DF2997 = FrameRate(30000, 1001)


def _timeline() -> HandoffTimeline:
    media = HandoffMediaRef("m1", "/media/a & b.mov", FrameRange(0, 100), 107892)
    video = HandoffTrack(
        "V", HandoffTrackKind.VIDEO, (HandoffGap(2), HandoffClip("c1", media, FrameRange(10, 13)))
    )
    audio = HandoffTrack(
        "A", HandoffTrackKind.AUDIO, (HandoffClip("c1a", media, FrameRange(10, 15), False),)
    )
    return HandoffTimeline("Golden <xml>", DF2997, 107892, (video, audio))


def test_xmeml_matches_golden() -> None:
    result = write_xmeml(_timeline())
    assert result.text == (FIXTURES / "golden.xmeml.xml").read_text(encoding="utf-8")
    assert result.diagnostics == ()
    assert result.artifact_kind == ARTIFACT_KIND
    assert result.authorizes_import is False


def test_xmeml_header_and_parse_back() -> None:
    text = write_xmeml(_timeline()).text
    assert text is not None
    assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n')
    root = ET.fromstring(text.split("\n", 2)[2])
    assert root.tag == "xmeml" and root.get("version") == "5"
    sequence = root.find("sequence")
    assert sequence is not None
    assert sequence.findtext("name") == "Golden <xml>"
    assert sequence.findtext("rate/timebase") == "30"
    assert sequence.findtext("rate/ntsc") == "TRUE"
    assert sequence.findtext("timecode/displayformat") == "DF"
    assert sequence.findtext("timecode/string") == "01:00:00;00"
    video_items = sequence.findall("media/video/track/clipitem")
    assert [
        (c.findtext("start"), c.findtext("end"), c.findtext("in"), c.findtext("out"))
        for c in video_items
    ] == [("2", "5", "10", "13")]
    first_file = video_items[0].find("file")
    assert first_file is not None
    assert first_file.findtext("pathurl") == "file:///media/a%20%26%20b.mov"
    audio_items = sequence.findall("media/audio/track/clipitem")
    assert audio_items[0].findtext("enabled") == "FALSE"
    reused = audio_items[0].find("file")
    assert reused is not None and reused.get("id") == "file-1" and len(reused) == 0


def test_xmeml_ndf_rate_and_deterministic() -> None:
    media = HandoffMediaRef("m1", "/a.mov")
    track = HandoffTrack("V", HandoffTrackKind.VIDEO, (HandoffClip("c", media, FrameRange(0, 24)),))
    timeline = HandoffTimeline("t", FrameRate(24000, 1001), 0, (track,))
    text = write_xmeml(timeline).text
    assert text is not None and text == write_xmeml(timeline).text
    root = ET.fromstring(text.split("\n", 2)[2])
    assert root.findtext("sequence/rate/timebase") == "24"
    assert root.findtext("sequence/rate/ntsc") == "TRUE"
    assert root.findtext("sequence/timecode/displayformat") == "NDF"
    # UNKNOWN media start: no file timecode is invented
    assert root.find("sequence/media/video/track/clipitem/file/timecode") is None


def test_xmeml_refuses_missing_reference_and_unknown_kind() -> None:
    missing = HandoffClip("c", HandoffMediaRef("m", None), FrameRange(0, 1))
    track = HandoffTrack("V", HandoffTrackKind.VIDEO, (missing,))
    result = write_xmeml(HandoffTimeline("t", FrameRate(25, 1), 0, (track,)))
    assert result.refused and result.text is None
    assert result.diagnostics[0].code is HandoffDiagnosticCode.MISSING_MEDIA_PATH
    unknown = HandoffTrack("X", HandoffTrackKind.UNKNOWN, ())
    result = write_xmeml(HandoffTimeline("t", FrameRate(25, 1), 0, (unknown,)))
    assert result.diagnostics[0].code is HandoffDiagnosticCode.UNKNOWN_TRACK_KIND


def test_xmeml_markers_written_with_color_warning() -> None:
    media = HandoffMediaRef("m1", "/a.mov")
    marker = HandoffMarker(FrameRange(1, 2), "beat", MarkerColor.BLUE, "n")
    clip = HandoffClip("c", media, FrameRange(0, 5), markers=(marker,))
    track = HandoffTrack("V", HandoffTrackKind.VIDEO, (clip,))
    result = write_xmeml(HandoffTimeline("t", FrameRate(25, 1), 0, (track,)))
    assert result.text is not None
    assert [(d.code, d.severity) for d in result.diagnostics] == [
        (HandoffDiagnosticCode.MARKER_NOT_REPRESENTED, HandoffSeverity.WARNING)
    ]
    root = ET.fromstring(result.text.split("\n", 2)[2])
    assert root.findtext("sequence/media/video/track/clipitem/marker/name") == "beat"
