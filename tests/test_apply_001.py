"""APPLY-001: marker approval inside the NLE -> approved cuts on a new Expected timeline.

Editor actions are simulated as text edits of our own writer output (marker
renames, a marker drag, a human trim). No media, no Resolve, no rendering.
"""

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import replace

import pytest
from support import roundtrip_fixtures as fx

from davinci_ai_editor.apply_cuts import (
    ApplyConfirmation,
    ApplyRefused,
    SkipReason,
    apply_approved_cuts,
    build_apply_confirmation,
    next_version_name,
)
from davinci_ai_editor.candidate_markers import (
    CandidateDecision,
    CandidateHandoff,
    CutCandidate,
    MarkerSelectionSet,
    SelectionIssue,
    attach_candidate_markers,
    parse_candidate_marker_name,
    read_marker_selections,
)
from davinci_ai_editor.domain import FrameRange, RippleDisplacement, TrackId
from davinci_ai_editor.handoff_model import (
    HandoffClip,
    HandoffMarker,
    HandoffMediaRef,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
    MarkerColor,
    ReimportedTimeline,
)
from davinci_ai_editor.otio_json import read_otio, write_otio
from davinci_ai_editor.roundtrip_diff import (
    RoundTripDiff,
    RoundTripFormat,
    diff_otio_roundtrip,
    roundtrip_artifact_ref,
)
from davinci_ai_editor.roundtrip_verification import (
    ActualProvenance,
    VerificationStatus,
    verify_roundtrip,
)
from davinci_ai_editor.xmeml_reader import read_xmeml

INTERVIEW = HandoffMediaRef("int", "/media/interview.mov", FrameRange(0, 1000), 0)
BROLL = HandoffMediaRef("broll", "/media/broll.mov", FrameRange(0, 1000), 0)

CANDIDATES = (
    CutCandidate("AIE-0001", FrameRange(20, 40), "filler um"),
    CutCandidate("AIE-0002", FrameRange(100, 130), "long pause"),
    CutCandidate("AIE-0003", FrameRange(200, 210), "repeat"),
    CutCandidate("AIE-0004", FrameRange(350, 360), "cough"),
    CutCandidate("AIE-0005", FrameRange(400, 410), "breath"),
    CutCandidate("AIE-0006", FrameRange(450, 460), "stumble"),
    CutCandidate("AIE-0007", FrameRange(540, 560), "false start"),
)


def _base() -> HandoffTimeline:
    """V1: A[0,300) int 0-300 | B[300,600) broll 0-300; A1 mirrors V1 (linked A/V)."""
    video = HandoffTrack(
        "V1",
        HandoffTrackKind.VIDEO,
        (
            HandoffClip("A", INTERVIEW, FrameRange(0, 300)),
            HandoffClip("B", BROLL, FrameRange(0, 300)),
        ),
    )
    audio = HandoffTrack(
        "A1",
        HandoffTrackKind.AUDIO,
        (
            HandoffClip("Aa", INTERVIEW, FrameRange(0, 300)),
            HandoffClip("Ba", BROLL, FrameRange(0, 300)),
        ),
    )
    return HandoffTimeline("Interview", fx.RATE, 0, (video, audio))


def _handoff() -> CandidateHandoff:
    return attach_candidate_markers(_base(), CANDIDATES)


def _rename(text: str, old: str, new: str) -> str:
    needle = f"<name>{old}</name>"
    assert text.count(needle) == 1, old
    return text.replace(needle, f"<name>{new}</name>")


def _editor_export(expected_text: str) -> str:
    """Approve 2, reject 1, leave 1 pending, malformed 1, moved 1, approve 1 in a trim."""
    text = _rename(expected_text, "AIE-0001 ?", "AIE-0001 OK")
    text = _rename(text, "AIE-0002 ?", "aie-0002 승인")
    text = _rename(text, "AIE-0003 ?", "AIE-0003 x")
    text = _rename(text, "AIE-0005 ?", "AIE-0005 maybe")
    text = _rename(text, "AIE-0007 ?", "AIE-0007 OK")
    moved = re.compile(
        r"(<name>AIE-0006 \?</name>\s*<comment>[^<]*</comment>\s*<in>)150(</in>\s*<out>)160(</out>)"
    )
    text, count = moved.subn(r"\g<1>155\g<2>165\g<3>", text)
    assert count == 1
    # human tail trim of B on V1 and A1 (linked), leaving a gap
    text = fx.set_fields(text, "clipitem-2", end=580, out=280, duration=280)
    return fx.set_fields(text, "clipitem-4", end=580, out=280, duration=280)


def _pipeline() -> tuple[CandidateHandoff, MarkerSelectionSet, RoundTripDiff, ApplyConfirmation]:
    handoff = _handoff()
    exported = _editor_export(fx.written(handoff.timeline))
    result = read_xmeml(exported)
    assert result.timeline is not None and result.complete, result.diagnostics
    diff = fx.diff_text(handoff.timeline, exported)
    selection = read_marker_selections(result.timeline, handoff.candidates)
    confirmation = build_apply_confirmation(selection, handoff.timeline, diff)
    return handoff, selection, diff, confirmation


def _clipitems(text: str, kind: str) -> list[ET.Element]:
    root = ET.fromstring(text)
    return root.findall(f"sequence/media/{kind}/track/clipitem")


def test_candidate_markers_are_written_with_tokens_and_notes() -> None:
    text = fx.written(_handoff().timeline)
    assert "<name>AIE-0001 ?</name>" in text
    assert "<comment>candidate=AIE-0001; reason=filler um</comment>" in text
    markers = _clipitems(text, "video")[0].findall("marker")
    assert [m.findtext("name") for m in markers] == ["AIE-0001 ?", "AIE-0002 ?", "AIE-0003 ?"]


def test_end_to_end_marker_approval_to_applied_timeline() -> None:
    handoff, selection, diff, confirmation = _pipeline()
    # --- selection (not approval) ---
    decisions = {s.candidate_id: (s.decision, s.issue) for s in selection.selections}
    assert decisions == {
        "AIE-0001": (CandidateDecision.APPROVED, SelectionIssue.NONE),
        "AIE-0002": (CandidateDecision.APPROVED, SelectionIssue.NONE),
        "AIE-0003": (CandidateDecision.REJECTED, SelectionIssue.NONE),
        "AIE-0004": (CandidateDecision.PENDING, SelectionIssue.NONE),
        "AIE-0005": (CandidateDecision.UNKNOWN, SelectionIssue.MALFORMED),
        "AIE-0006": (CandidateDecision.UNKNOWN, SelectionIssue.MOVED),
        "AIE-0007": (CandidateDecision.APPROVED, SelectionIssue.NONE),
    }
    assert selection.authorizes_apply is False and selection.axis == "SELECTION"
    # --- confirmation ---
    assert [c.candidate_id for c in confirmation.approved_cuts] == ["AIE-0001", "AIE-0002"]
    assert [c.timeline_range for c in confirmation.approved_cuts] == [
        FrameRange(20, 40),
        FrameRange(100, 130),
    ]
    assert confirmation.removed_frames == 50
    skipped = {s.candidate_id: s.reason for s in confirmation.skipped}
    assert skipped == {
        "AIE-0003": SkipReason.REJECTED,
        "AIE-0004": SkipReason.PENDING,
        "AIE-0005": SkipReason.UNKNOWN,
        "AIE-0006": SkipReason.UNKNOWN,
        "AIE-0007": SkipReason.HUMAN_EDIT_LOCKED,
    }
    summary = confirmation.summary
    assert "승인된 컷 2개" in summary and "총 제거 50프레임 (2.000초)" in summary
    assert "AIE-0007 HUMAN_EDIT_LOCKED (사람이 수정한 구간 - 보호)" in summary
    assert "AIE-0006 UNKNOWN (판단 불가 - 적용하지 않음) - MOVED" in summary
    assert "AIE-0005 UNKNOWN (판단 불가 - 적용하지 않음) - MALFORMED" in summary
    assert confirmation.confirmation_digest in summary
    assert {(s.lock.frame_range, s.delta_frames) for s in confirmation.shifted_locks} == {
        (FrameRange(300, 600), -50)
    }
    assert confirmation.authorizes_apply is False
    # --- approval: wrong digest refused ---
    with pytest.raises(ApplyRefused):
        apply_approved_cuts(confirmation, confirmed_digest="0" * 64)
    with pytest.raises(ApplyRefused):
        apply_approved_cuts(confirmation, confirmed_digest=diff.digest)
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    assert applied.timeline.name == "Interview AIE v2"
    assert applied.artifact_kind == "EXPECTED_TIMELINE_ARTIFACT"
    assert applied.authorizes_import is False and applied.verified is False
    assert applied.remaining_candidate_ids == (
        "AIE-0003",
        "AIE-0004",
        "AIE-0005",
        "AIE-0006",
        "AIE-0007",
    )
    expected_displacements = {
        (FrameRange(40, 100), -20),
        (FrameRange(130, 300), -50),
        (FrameRange(300, 580), -50),
    }
    for track in ("Video 1", "Audio 1"):
        assert {
            (d.original_range, d.delta_frames)
            for d in applied.ripple_displacements
            if d.track_id == TrackId(track)
        } == expected_displacements
    assert RippleDisplacement(TrackId("Video 1"), FrameRange(300, 580), -50) in (
        applied.ripple_displacements
    )
    # --- write the new timeline and parse it back ---
    text = fx.written(applied.timeline)
    video, audio = _clipitems(text, "video"), _clipitems(text, "audio")
    spans = [
        (c.findtext("start"), c.findtext("end"), c.findtext("in"), c.findtext("out")) for c in video
    ]
    assert spans == [
        ("0", "20", "0", "20"),
        ("20", "80", "40", "100"),
        ("80", "250", "130", "300"),
        ("250", "530", "0", "280"),
    ]
    assert [
        (c.findtext("start"), c.findtext("end"), c.findtext("in"), c.findtext("out")) for c in audio
    ] == spans
    for index, (v, a) in enumerate(zip(video, audio, strict=True), start=1):
        refs = {
            (link.findtext("linkclipref"), link.findtext("mediatype"), link.findtext("clipindex"))
            for link in v.findall("link")
        }
        assert refs == {(v.get("id"), "video", str(index)), (a.get("id"), "audio", str(index))}
        assert len(a.findall("link")) == 2
    names = [m.findtext("name") for c in video for m in c.findall("marker")]
    assert names == [
        "AIE-0003 x",
        "AIE-0004 ?",
        "AIE-0005 maybe",
        "AIE-0006 ?",
        "AIE-0007 OK",
    ]
    # --- VER-001 on a simulated immediate re-export of the applied file ---
    reexport = text.replace("clipitem-", "item-")
    verify_diff = fx.diff_text(applied.timeline, reexport, ref="reexport.xml")
    report = verify_roundtrip(
        applied.revision,
        applied.timeline,
        verify_diff,
        provenance=ActualProvenance.IMMEDIATE_REEXPORT,
    )
    assert report.status is VerificationStatus.MATCH, report.reasons
    assert handoff.timeline.name == "Interview"


def test_pipeline_is_deterministic() -> None:
    first = _pipeline()[3]
    second = _pipeline()[3]
    assert first == second and first.summary == second.summary
    a = apply_approved_cuts(first, confirmed_digest=first.confirmation_digest)
    b = apply_approved_cuts(second, confirmed_digest=second.confirmation_digest)
    assert a == b and fx.written(a.timeline) == fx.written(b.timeline)


def test_confirmation_refuses_stale_bindings() -> None:
    handoff, selection, diff, _ = _pipeline()
    other = attach_candidate_markers(_base(), CANDIDATES[:2]).timeline
    with pytest.raises(ValueError):
        build_apply_confirmation(selection, other, diff)
    untouched = fx.written(handoff.timeline)
    stale_diff = fx.diff_text(handoff.timeline, untouched)
    with pytest.raises(ValueError):
        build_apply_confirmation(selection, handoff.timeline, stale_diff)


def test_confirmation_digest_binds_the_cut_set() -> None:
    _, _, _, confirmation = _pipeline()
    with pytest.raises(ValueError):
        replace(confirmation, approved_cuts=confirmation.approved_cuts[:1])


@pytest.mark.parametrize(
    ("name", "token", "decision"),
    [
        ("AIE-0012 ?", "AIE-0012", CandidateDecision.PENDING),
        ("AIE-0012 OK", "AIE-0012", CandidateDecision.APPROVED),
        ("aie-0012 ok", "AIE-0012", CandidateDecision.APPROVED),
        ("AIE-0012 승인", "AIE-0012", CandidateDecision.APPROVED),
        ("AIE-0012 X", "AIE-0012", CandidateDecision.REJECTED),
        ("AIE-0012 x", "AIE-0012", CandidateDecision.REJECTED),
        ("AIE-0012 제외", "AIE-0012", CandidateDecision.REJECTED),
        ("AIE-0012 yes", "AIE-0012", CandidateDecision.UNKNOWN),
        ("AIE-0012", "AIE-0012", CandidateDecision.UNKNOWN),
        ("AIE-0012 OK extra", "AIE-0012", CandidateDecision.UNKNOWN),
        ("AIE-12 OK", None, CandidateDecision.UNKNOWN),
        ("beat", None, CandidateDecision.UNKNOWN),
    ],
)
def test_marker_name_vocabulary(name: str, token: str | None, decision: CandidateDecision) -> None:
    assert parse_candidate_marker_name(name) == (token, decision)


def _otio_selection(name: str, color: str) -> CandidateDecision:
    handoff = attach_candidate_markers(_base(), CANDIDATES[:1])
    text = write_otio(handoff.timeline).text
    assert text is not None
    document = json.loads(text)
    marker = document["tracks"]["children"][0]["children"][0]["markers"][0]
    assert marker["color"] == "YELLOW"
    marker["name"], marker["color"] = name, color
    read = read_otio(json.dumps(document))
    assert read.timeline is not None
    return read_marker_selections(read.timeline, handoff.candidates).selections[0].decision


def test_marker_colour_is_a_secondary_signal_only() -> None:
    assert _otio_selection("AIE-0001 OK", "GREEN") is CandidateDecision.APPROVED
    assert _otio_selection("AIE-0001 X", "RED") is CandidateDecision.REJECTED
    assert _otio_selection("AIE-0001 OK", "BLUE") is CandidateDecision.APPROVED
    assert _otio_selection("AIE-0001 OK", "RED") is CandidateDecision.UNKNOWN
    assert _otio_selection("AIE-0001 ?", "GREEN") is CandidateDecision.UNKNOWN


def _actual_with_markers(markers: tuple[HandoffMarker, ...]) -> ReimportedTimeline:
    base = _base()
    video = base.tracks[0]
    first = video.items[0]
    assert isinstance(first, HandoffClip)
    items = (replace(first, markers=markers), *video.items[1:])
    tracks = (replace(video, items=items), *base.tracks[1:])
    return ReimportedTimeline("Interview", fx.RATE, 0, tracks)


def test_duplicated_and_missing_tokens_are_unknown() -> None:
    handoff = attach_candidate_markers(_base(), CANDIDATES[:2])
    marker = HandoffMarker(FrameRange(20, 40), "AIE-0001 OK")
    actual = _actual_with_markers((marker, replace(marker, name="AIE-0001 X")))
    selection = read_marker_selections(actual, handoff.candidates)
    assert selection.selection("AIE-0001").issue is SelectionIssue.DUPLICATED
    assert selection.selection("AIE-0002").issue is SelectionIssue.MISSING
    stray = _actual_with_markers((HandoffMarker(FrameRange(5, 6), "AIE-0099 OK"),))
    assert read_marker_selections(stray, handoff.candidates).unexpected_tokens == ("AIE-0099",)


def _confirm(handoff: CandidateHandoff, text: str) -> ApplyConfirmation:
    result = read_xmeml(text)
    assert result.timeline is not None
    diff = fx.diff_text(handoff.timeline, text)
    selection = read_marker_selections(result.timeline, handoff.candidates)
    return build_apply_confirmation(selection, handoff.timeline, diff)


def test_marker_added_by_the_editor_is_a_human_edit_lock() -> None:
    handoff = attach_candidate_markers(_base(), CANDIDATES[:1])
    text = _rename(fx.written(handoff.timeline), "AIE-0001 ?", "AIE-0001 OK")
    human = "<marker><name>keep this laugh</name><comment /><in>30</in><out>31</out></marker>"
    text = text.replace("</clipitem>", human + "</clipitem>", 1)
    confirmation = _confirm(handoff, text)
    assert confirmation.approved_cuts == ()
    assert confirmation.skipped[0].reason is SkipReason.HUMAN_EDIT_LOCKED


def test_existing_marker_overlapping_an_approved_cut_blocks_it() -> None:
    base = _base()
    video = base.tracks[0]
    first = video.items[0]
    assert isinstance(first, HandoffClip)
    laugh = HandoffMarker(FrameRange(30, 31), "keep this laugh", MarkerColor.BLUE)
    items = (replace(first, markers=(laugh,)), *video.items[1:])
    with_marker = replace(base, tracks=(replace(video, items=items), *base.tracks[1:]))
    overlapping = (*CANDIDATES[:1], CutCandidate("AIE-0008", FrameRange(35, 50), "overlap"))
    handoff = attach_candidate_markers(with_marker, overlapping)
    text = _rename(fx.written(handoff.timeline), "AIE-0001 ?", "AIE-0001 OK")
    text = _rename(text, "AIE-0008 ?", "AIE-0008 OK")
    confirmation = _confirm(handoff, text)
    assert confirmation.approved_cuts == ()
    details = {s.candidate_id: (s.reason, s.detail) for s in confirmation.skipped}
    assert details["AIE-0001"] == (
        SkipReason.MARKER_CONFLICT,
        "overlaps AIE-0008 OK, keep this laugh",
    )
    assert details["AIE-0008"] == (SkipReason.MARKER_CONFLICT, "overlaps AIE-0001 OK")


def test_whole_unknown_diff_locks_every_cut() -> None:
    handoff = attach_candidate_markers(_base(), CANDIDATES[:1])
    text = _rename(fx.written(handoff.timeline), "AIE-0001 ?", "AIE-0001 OK")
    text = re.sub(r"<frame>0</frame>", "<frame>10</frame>", text, count=1)
    text = text.replace("<string>00:00:00:00</string>", "<string>00:00:00:10</string>", 1)
    result = read_xmeml(text)
    assert result.timeline is not None, result.diagnostics
    diff = fx.diff_text(handoff.timeline, text)
    selection = read_marker_selections(result.timeline, handoff.candidates)
    confirmation = build_apply_confirmation(selection, handoff.timeline, diff)
    assert confirmation.approved_cuts == ()
    assert confirmation.skipped[0].reason is SkipReason.HUMAN_EDIT_LOCKED


def test_otio_round_trip_selection_and_apply_strong_identity() -> None:
    handoff = attach_candidate_markers(_base(), CANDIDATES[:2])
    text = write_otio(handoff.timeline).text
    assert text is not None
    document = json.loads(text)
    for marker in document["tracks"]["children"][0]["children"][0]["markers"]:
        marker["name"] = marker["name"].replace("?", "OK")
    mutated = json.dumps(document)
    read = read_otio(mutated)
    assert read.timeline is not None
    artifact = roundtrip_artifact_ref("export.otio", mutated, RoundTripFormat.OTIO_JSON)
    diff = diff_otio_roundtrip(handoff.timeline, read, artifact_ref=artifact)
    selection = read_marker_selections(read.timeline, handoff.candidates)
    confirmation = build_apply_confirmation(selection, handoff.timeline, diff)
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    assert applied.timeline.duration == 600 - 50
    assert applied.remaining_candidate_ids == ()


def test_attach_refuses_candidates_outside_one_clip() -> None:
    with pytest.raises(ValueError):
        attach_candidate_markers(_base(), (CutCandidate("AIE-0001", FrameRange(290, 310), "x"),))
    with pytest.raises(ValueError):
        CutCandidate("AIE-1", FrameRange(0, 1), "x")
    with pytest.raises(ValueError):
        CutCandidate("AIE-0001", FrameRange(0, 1), "line\nbreak")


def test_next_version_name() -> None:
    assert next_version_name("Interview") == "Interview AIE v2"
    assert next_version_name("Interview AIE v2") == "Interview AIE v3"


def test_writer_links_linked_av_clips_only() -> None:
    text = fx.written(fx.expected_timeline())
    video, audio = _clipitems(text, "video"), _clipitems(text, "audio")
    assert [len(c.findall("link")) for c in video] == [2, 2, 0]
    assert [len(c.findall("link")) for c in audio] == [2, 2]
    link = audio[0].findall("link")[1]
    assert (link.findtext("mediatype"), link.findtext("groupindex")) == ("audio", "1")
    reread = read_xmeml(text)
    assert reread.complete
