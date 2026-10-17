"""Synthetic RT-001 / VER-001 fixtures: Expected timelines and text-level edits.

Editor actions are simulated by mutating the *written* xmeml text (string
edits on the deterministic writer output), never by touching media or Resolve.
"""

import re

from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.handoff_model import (
    HandoffClip,
    HandoffGap,
    HandoffMarker,
    HandoffMediaRef,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
    ReimportedTimeline,
)
from davinci_ai_editor.roundtrip_diff import (
    RoundTripDiff,
    RoundTripFormat,
    diff_xmeml_roundtrip,
    roundtrip_artifact_ref,
)
from davinci_ai_editor.temporal_mapping import FrameRate
from davinci_ai_editor.xmeml_reader import read_xmeml
from davinci_ai_editor.xmeml_writer import write_xmeml

RATE = FrameRate(25, 1)
M1 = HandoffMediaRef("m1", "/media/a.mov", FrameRange(0, 1000), 0)
M2 = HandoffMediaRef("m2", "/media/b.mov", FrameRange(0, 1000), 0)
M3 = HandoffMediaRef("m3", "/media/c.mov", FrameRange(0, 1000), 0)


def expected_timeline(*, marker: bool = False) -> HandoffTimeline:
    """V1: A[0,50) m1 100-150 | B[50,110) m2 200-260 | gap 20 | C[130,170) m1 300-340.

    A1: Aa[0,50) m1 100-150 | Ba[50,110) m2 200-260.
    """
    markers = (HandoffMarker(FrameRange(210, 211), "beat", note="n"),) if marker else ()
    video = HandoffTrack(
        "V1",
        HandoffTrackKind.VIDEO,
        (
            HandoffClip("A", M1, FrameRange(100, 150)),
            HandoffClip("B", M2, FrameRange(200, 260), markers=markers),
            HandoffGap(20),
            HandoffClip("C", M1, FrameRange(300, 340)),
        ),
    )
    audio = HandoffTrack(
        "A1",
        HandoffTrackKind.AUDIO,
        (
            HandoffClip("Aa", M1, FrameRange(100, 150)),
            HandoffClip("Ba", M2, FrameRange(200, 260)),
        ),
    )
    return HandoffTimeline("RT", RATE, 0, (video, audio))


def two_video_tracks() -> HandoffTimeline:
    """V1: A[0,50) | gap 60 ; V2: gap 50 | B[50,110)."""
    v1 = HandoffTrack("V1", HandoffTrackKind.VIDEO, (HandoffClip("A", M1, FrameRange(100, 150)),))
    v2 = HandoffTrack(
        "V2",
        HandoffTrackKind.VIDEO,
        (HandoffGap(50), HandoffClip("B", M2, FrameRange(200, 260))),
    )
    return HandoffTimeline("RT2", RATE, 0, (v1, v2))


def cut_timeline() -> HandoffTimeline:
    """An intended cut inside one source: X1[0,40) m1 0-40 | X2[40,80) m1 40-80."""
    video = HandoffTrack(
        "V1",
        HandoffTrackKind.VIDEO,
        (
            HandoffClip("X1", M1, FrameRange(0, 40)),
            HandoffClip("X2", M1, FrameRange(40, 80)),
        ),
    )
    return HandoffTimeline("CUT", RATE, 0, (video,))


def written(timeline: HandoffTimeline) -> str:
    text = write_xmeml(timeline).text
    assert text is not None
    return text


_BLOCK = r'(<clipitem id="{cid}">)(.*?)(</clipitem>)'


def set_fields(text: str, clip_id: str, **values: int | str) -> str:
    """Replace ``<tag>…</tag>`` values inside one clipitem block (text edit)."""
    pattern = re.compile(_BLOCK.format(cid=re.escape(clip_id)), re.DOTALL)
    match = pattern.search(text)
    assert match is not None, clip_id
    body = match.group(2)
    for tag, value in values.items():
        body, count = re.subn(
            rf"(\n\s*<{tag}>)[^<]*(</{tag}>)", rf"\g<1>{value}\g<2>", body, count=1
        )
        assert count == 1, tag
    return text[: match.start(2)] + body + text[match.end(2) :]


def delete_clip(text: str, clip_id: str) -> str:
    pattern = re.compile(r"\n\s*" + _BLOCK.format(cid=re.escape(clip_id)), re.DOTALL)
    result, count = pattern.subn("", text, count=1)
    assert count == 1
    return result


def clip_block(
    clip_id: str,
    name: str,
    start: int,
    end: int,
    source_in: int,
    source_out: int,
    file_xml: str,
) -> str:
    return (
        f'<clipitem id="{clip_id}"><name>{name}</name><enabled>TRUE</enabled>'
        f"<duration>{end - start}</duration><start>{start}</start><end>{end}</end>"
        f"<in>{source_in}</in><out>{source_out}</out>{file_xml}</clipitem>"
    )


NEW_FILE = (
    '<file id="file-new"><name>m3</name><pathurl>file:///media/c.mov</pathurl>'
    "<rate><timebase>25</timebase><ntsc>FALSE</ntsc></rate><duration>1000</duration></file>"
)


M2_FILE = (
    '<file id="file-2"><name>m2</name><pathurl>file:///media/b.mov</pathurl>'
    "<rate><timebase>25</timebase><ntsc>FALSE</ntsc></rate><duration>1000</duration></file>"
)


def insert_in_track(text: str, track_index: int, xml: str) -> str:
    """Insert raw xml at the end of the n-th ``<track>`` (document order)."""
    positions = [m.start() for m in re.finditer(r"</track>", text)]
    position = positions[track_index]
    return text[:position] + xml + text[position:]


def diff_text(expected: HandoffTimeline, text: str, ref: str = "export.xml") -> RoundTripDiff:
    artifact = roundtrip_artifact_ref(ref, text, RoundTripFormat.XMEML)
    return diff_xmeml_roundtrip(expected, read_xmeml(text), artifact_ref=artifact)


def reimported(timeline: HandoffTimeline) -> ReimportedTimeline:
    """Test-only: the same structure as an Actual-side container (simulated re-read)."""
    return ReimportedTimeline(timeline.name, timeline.rate, timeline.start_frame, timeline.tracks)
