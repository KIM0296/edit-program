import pytest

from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.handoff_model import (
    ARTIFACT_KIND,
    HandoffDiagnosticCode,
    HandoffSeverity,
    HandoffSubtitleCue,
)
from davinci_ai_editor.subtitle_io import (
    BOM,
    SrtCue,
    escape_vtt_text,
    legalize_text,
    ms_to_srt_timestamp,
    read_srt,
    write_srt,
    write_vtt,
)
from davinci_ai_editor.temporal_mapping import FrameRate

R24 = FrameRate(24, 1)
CUES = (
    HandoffSubtitleCue(FrameRange(24, 48), "Hello\n\n\nworld & <b>"),
    HandoffSubtitleCue(FrameRange(0, 12), "   "),
    HandoffSubtitleCue(FrameRange(0, 1), "\nFirst\n"),
    HandoffSubtitleCue(FrameRange(48, 72), "a --> b"),
)

GOLDEN_SRT = (
    "1\n00:00:00,000 --> 00:00:00,042\nFirst\n\n"
    "2\n00:00:01,000 --> 00:00:02,000\nHello\nworld & <b>\n\n"
)
GOLDEN_VTT = (
    "WEBVTT\n\n"
    "00:00:00.000 --> 00:00:00.042\nFirst\n\n"
    "00:00:01.000 --> 00:00:02.000\nHello\nworld &amp; &lt;b&gt;\n\n"
)


def test_srt_golden_renumbers_and_refuses_explicitly() -> None:
    result = write_srt(CUES, R24)
    assert result.text == GOLDEN_SRT
    assert result.written_count == 2
    assert not result.complete
    assert [(d.code, d.location) for d in result.diagnostics] == [
        (HandoffDiagnosticCode.EMPTY_TEXT, "cue[1]"),
        (HandoffDiagnosticCode.ARROW_IN_TEXT, "cue[3]"),
    ]
    assert all(d.severity is HandoffSeverity.REFUSAL for d in result.diagnostics)
    assert result.artifact_kind == ARTIFACT_KIND
    assert result.authorizes_import is False


def test_vtt_golden_header_and_escaping() -> None:
    result = write_vtt(CUES, R24)
    assert result.text == GOLDEN_VTT
    assert [d.code for d in result.diagnostics] == [
        HandoffDiagnosticCode.EMPTY_TEXT,
        HandoffDiagnosticCode.ARROW_IN_TEXT,
    ]
    assert escape_vtt_text("a & b < c > d") == "a &amp; b &lt; c &gt; d"


def test_empty_input_and_complete_flag() -> None:
    assert write_srt((), R24).text == ""
    assert write_vtt((), R24).text == "WEBVTT\n\n"
    ok = write_srt((HandoffSubtitleCue(FrameRange(0, 24), "x"),), R24)
    assert ok.complete and ok.diagnostics == ()


def test_writer_is_deterministic_and_order_independent() -> None:
    forward = write_srt(CUES, R24).text
    assert forward == write_srt(CUES, R24).text
    assert forward == write_srt(tuple(reversed(CUES)), R24).text


def test_ntsc_ms_rounding_covers_range() -> None:
    cue = HandoffSubtitleCue(FrameRange(1, 2), "x")
    assert write_srt((cue,), FrameRate(30000, 1001)).text == (
        "1\n00:00:00,033 --> 00:00:00,067\nx\n\n"
    )


def test_legalize_and_timestamp_helpers() -> None:
    assert legalize_text("\r\nfoo\r\n\r\nbar\n") == "foo\nbar"
    assert ms_to_srt_timestamp(3_723_004) == "01:02:03,004"
    assert ms_to_srt_timestamp(360_000_000) == "100:00:00,000"
    with pytest.raises(ValueError):
        ms_to_srt_timestamp(-1)


def test_reader_parses_golden_round_trip() -> None:
    result = read_srt(GOLDEN_SRT)
    assert result.ok
    assert result.cues == (
        SrtCue(1, 0, 42, "First"),
        SrtCue(2, 1000, 2000, "Hello\nworld & <b>"),
    )


def test_reader_tolerates_bom_crlf_and_missing_final_blank() -> None:
    text = (
        BOM + "1\r\n00:00:01,000 --> 00:00:02,500\r\nLine one\r\nLine two\r\n\r\n"
        "2\r\n00:00:03,000 --> 00:00:04,000\r\nNext"
    )
    result = read_srt(text)
    assert result.ok
    assert result.cues == (
        SrtCue(1, 1000, 2500, "Line one\nLine two"),
        SrtCue(2, 3000, 4000, "Next"),
    )


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("1\n00:00:01,000 --> 00:00:02,000\n", HandoffDiagnosticCode.MALFORMED_BLOCK),
        ("x\n00:00:01,000 --> 00:00:02,000\nhi\n", HandoffDiagnosticCode.BAD_INDEX),
        ("2\n00:00:01,000 --> 00:00:02,000\nhi\n", HandoffDiagnosticCode.BAD_INDEX),
        ("1\n00:00:01.000 --> 00:00:02,000\nhi\n", HandoffDiagnosticCode.BAD_TIMESTAMP),
        ("1\n00:00:01,000->00:00:02,000\nhi\n", HandoffDiagnosticCode.BAD_TIMESTAMP),
        ("1\n00:61:01,000 --> 00:62:02,000\nhi\n", HandoffDiagnosticCode.BAD_TIMESTAMP),
        ("1\n00:00:02,000 --> 00:00:02,000\nhi\n", HandoffDiagnosticCode.NONPOSITIVE_DURATION),
        ("1\n00:00:01,000 --> 00:00:02,000\n  \n", HandoffDiagnosticCode.EMPTY_TEXT),
        ("1\r00:00:01,000 --> 00:00:02,000\rhi\r", HandoffDiagnosticCode.MALFORMED_DOCUMENT),
    ],
)
def test_reader_is_strict(text: str, code: HandoffDiagnosticCode) -> None:
    result = read_srt(text)
    assert not result.ok
    assert result.diagnostics[0].code is code


def test_reader_empty_document() -> None:
    result = read_srt(BOM + "\r\n")
    assert result.ok and result.cues == ()
