from support import roundtrip_fixtures as fx

from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.handoff_model import (
    HandoffClip,
    HandoffDiagnosticCode,
    HandoffGap,
    HandoffTrackKind,
)
from davinci_ai_editor.xmeml_reader import (
    EVIDENCE_CLASS,
    TrackKey,
    UnsupportedConstruct,
    read_xmeml,
)

V1 = TrackKey(HandoffTrackKind.VIDEO, 1)


def _codes(text: str) -> list[HandoffDiagnosticCode]:
    return [d.code for d in read_xmeml(text).diagnostics]


def test_reads_writer_output_back() -> None:
    expected = fx.expected_timeline(marker=True)
    result = read_xmeml(fx.written(expected))
    assert result.evidence_class == EVIDENCE_CLASS == "FILE_ROUNDTRIP"
    assert result.complete and result.timeline is not None
    timeline = result.timeline
    assert timeline.rate == expected.rate and timeline.start_frame == 0
    assert [t.name for t in timeline.tracks] == ["Video 1", "Audio 1"]
    video = timeline.tracks[0]
    assert [type(i) for i in video.items] == [HandoffClip, HandoffClip, HandoffGap, HandoffClip]
    b = video.items[1]
    assert isinstance(b, HandoffClip)
    assert b.media.media_id == "m2" and b.media.target_path == "/media/b.mov"
    assert b.source_range == FrameRange(200, 260)
    assert b.media.available_range == FrameRange(0, 1000) and b.media.media_start_frame == 0
    assert [(m.frame_range, m.name, m.note) for m in b.markers] == [
        (FrameRange(210, 211), "beat", "n")
    ]
    # reused <file id=…/> references resolve to the first definition
    audio_first = timeline.tracks[1].items[0]
    assert isinstance(audio_first, HandoffClip) and audio_first.media.media_id == "m1"


def test_file_reference_before_definition_and_windows_path() -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence>'
        "<name>s</name><rate><timebase>24</timebase><ntsc>TRUE</ntsc></rate>"
        "<timecode><string>00:00:00:00</string><frame>0</frame></timecode>"
        "<media><video><track>"
        + fx.clip_block("c1", "one", 0, 10, 0, 10, '<file id="f1"/>')
        + fx.clip_block(
            "c2",
            "two",
            10,
            20,
            5,
            15,
            '<file id="f1"><name>clip.mov</name><pathurl>file:///C:/media/clip.mov</pathurl>'
            "</file>",
        )
        + "</track></video></media></sequence></xmeml>"
    )
    result = read_xmeml(xml)
    assert result.timeline is not None, result.diagnostics
    first = result.timeline.tracks[0].items[0]
    assert isinstance(first, HandoffClip)
    assert first.media.target_path == "C:/media/clip.mov" and first.media.media_id == "clip.mov"


def test_refuses_entities_external_doctype_and_oversize() -> None:
    body = '<xmeml version="5"><sequence/></xmeml>'
    xxe = '<?xml version="1.0"?><!DOCTYPE xmeml [<!ENTITY x SYSTEM "file:///etc/passwd">]>' + body
    laughs = (
        '<?xml version="1.0"?><!DOCTYPE xmeml [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
        '<xmeml version="5"><sequence><name>&b;</name></sequence></xmeml>'
    )
    external = '<?xml version="1.0"?><!DOCTYPE xmeml SYSTEM "http://x/xmeml.dtd">' + body
    for text in (xxe, laughs, external):
        result = read_xmeml(text)
        assert result.refused
        assert result.diagnostics[-1].code is HandoffDiagnosticCode.UNSUPPORTED_FEATURE
    text = fx.written(fx.expected_timeline())
    oversized = read_xmeml(text, max_chars=100)
    assert oversized.refused and "exceeds" in oversized.diagnostics[-1].message
    assert read_xmeml("<xmeml").refused


def test_refuses_unknown_rate_missing_timecode_and_bad_reference() -> None:
    text = fx.written(fx.expected_timeline())
    no_ntsc = text.replace("<ntsc>FALSE</ntsc>", "", 1)
    assert _codes(no_ntsc)[-1] is HandoffDiagnosticCode.UNKNOWN_RATE
    odd_rate = text.replace("<timebase>25</timebase>", "<timebase>23</timebase>")
    assert _codes(odd_rate)[-1] is HandoffDiagnosticCode.UNKNOWN_RATE
    start = text.index("<timecode>")
    end = text.index("</timecode>") + len("</timecode>")
    no_timecode = text[:start] + text[end:]
    result = read_xmeml(no_timecode)
    assert result.refused and "UNKNOWN" in result.diagnostics[-1].message
    dangling = text.replace('<file id="file-2" />', '<file id="file-9" />')
    assert _codes(dangling)[-1] is HandoffDiagnosticCode.MALFORMED_DOCUMENT
    two_sequences = text.replace("</xmeml>", "<sequence/></xmeml>")
    assert _codes(two_sequences)[-1] is HandoffDiagnosticCode.UNSUPPORTED_FEATURE


def test_unsupported_constructs_become_unknown_regions() -> None:
    text = fx.written(fx.expected_timeline())
    transition = fx.insert_in_track(
        text, 0, "<transitionitem><start>100</start><end>120</end></transitionitem>"
    )
    result = read_xmeml(transition)
    assert result.timeline is not None and not result.complete
    constructs = {r.construct for r in result.unknown_regions}
    assert UnsupportedConstruct.TRANSITION in constructs
    assert UnsupportedConstruct.OVERLAPPING_CLIPS in constructs
    overlap = [r for r in result.unknown_regions if r.construct.value == "OVERLAPPING_CLIPS"]
    assert overlap[0].frame_range == FrameRange(50, 120)
    # B was not placed (its span is UNKNOWN); C is still read
    names = [i.name for i in result.timeline.tracks[0].items if isinstance(i, HandoffClip)]
    assert names == ["A", "C"]

    speed = fx.set_fields(text, "clipitem-3", out=360)
    assert {r.construct for r in read_xmeml(speed).unknown_regions} == {
        UnsupportedConstruct.SPEED_CHANGE
    }
    nested = text.replace(
        '<clipitem id="clipitem-3">', '<clipitem id="clipitem-3"><sequence id="n"/>'
    )
    assert read_xmeml(nested).unknown_regions[0].construct is UnsupportedConstruct.NESTED_SEQUENCE
    filtered = text.replace(
        '<clipitem id="clipitem-3">',
        '<clipitem id="clipitem-3"><filter><effect><effectid>timeremap</effectid></effect>'
        "</filter>",
    )
    assert read_xmeml(filtered).unknown_regions[0].construct is UnsupportedConstruct.SPEED_CHANGE
    generator = fx.insert_in_track(
        text, 0, "<generatoritem><start>170</start><end>190</end></generatoritem>"
    )
    region = read_xmeml(generator).unknown_regions[0]
    assert region.construct is UnsupportedConstruct.GENERATOR
    assert region.frame_range == FrameRange(170, 190) and region.track == V1


def test_transition_adjacent_boundary_makes_whole_track_unknown() -> None:
    text = fx.set_fields(fx.written(fx.expected_timeline()), "clipitem-2", start=-1)
    result = read_xmeml(text)
    assert result.timeline is not None
    region = result.unknown_regions[0]
    assert region.frame_range is None and region.track == V1
    assert result.timeline.tracks[0].items == ()
