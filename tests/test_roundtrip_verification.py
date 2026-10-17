import re

import pytest
from support import roundtrip_fixtures as fx

from davinci_ai_editor.handoff_model import HandoffTimeline
from davinci_ai_editor.roundtrip_diff import RoundTripDiff
from davinci_ai_editor.roundtrip_verification import (
    ActualProvenance,
    Attribution,
    AttributionBasis,
    ItemStatus,
    VerificationReport,
    VerificationStatus,
    intended_cut_list,
    render_report,
    verify_roundtrip,
)
from davinci_ai_editor.trust_evidence import artifact_revision

IMMEDIATE = ActualProvenance.IMMEDIATE_REEXPORT
EDITED = ActualProvenance.AFTER_HUMAN_EDIT


def _verify(
    expected: HandoffTimeline,
    diff: RoundTripDiff,
    provenance: ActualProvenance = IMMEDIATE,
    baseline: RoundTripDiff | None = None,
    acknowledged: tuple[str, ...] = (),
) -> VerificationReport:
    approved = artifact_revision("ver001", "plan-1", expected)
    return verify_roundtrip(
        approved,
        expected,
        diff,
        provenance=provenance,
        baseline=baseline,
        acknowledged_change_ids=acknowledged,
    )


def _statuses(report: VerificationReport) -> dict[str, ItemStatus]:
    return {i.item_id: i.status for i in report.items}


def _strip_markers(text: str) -> str:
    return re.sub(r"\s*<marker>.*?</marker>", "", text, flags=re.DOTALL)


def test_intended_cut_list_has_clips_and_gaps() -> None:
    ids = [i.item_id for i in intended_cut_list(fx.expected_timeline())]
    assert ids == [
        "E:VIDEO:1:0",
        "E:VIDEO:1:1",
        "G:VIDEO:1:2",
        "E:VIDEO:1:3",
        "E:AUDIO:1:0",
        "E:AUDIO:1:1",
    ]


def test_exact_match() -> None:
    expected = fx.expected_timeline(marker=True)
    report = _verify(expected, fx.diff_text(expected, fx.written(expected)))
    assert report.status is VerificationStatus.MATCH
    assert set(_statuses(report).values()) == {ItemStatus.MATCH}
    assert report.evidence_class == "FILE_ROUNDTRIP"
    assert report.native_evidence is False and report.verified_live is False


def test_one_frame_drift_is_mismatch() -> None:
    expected = fx.expected_timeline()
    text = fx.set_fields(fx.written(expected), "clipitem-3", start=131, end=171)
    report = _verify(expected, fx.diff_text(expected, text))
    item = report.item("E:VIDEO:1:3")
    assert item.status is ItemStatus.FRAME_DRIFT and item.drift is not None
    assert item.drift.delta == 1
    assert item.attribution is Attribution.HANDOFF_LOSS
    assert item.basis is AttributionBasis.USER_DECLARED_NO_EDITS
    assert report.status is VerificationStatus.MISMATCH


def test_lost_marker() -> None:
    expected = fx.expected_timeline(marker=True)
    text = _strip_markers(fx.written(expected))
    report = _verify(expected, fx.diff_text(expected, text))
    assert report.item("E:VIDEO:1:1").status is ItemStatus.MARKER_LOST
    assert report.status is VerificationStatus.MISMATCH


def test_lost_cut() -> None:
    expected = fx.cut_timeline()
    text = fx.delete_clip(fx.written(expected), "clipitem-2")
    text = fx.set_fields(text, "clipitem-1", end=80, out=80, duration=80)
    report = _verify(expected, fx.diff_text(expected, text))
    assert _statuses(report) == {
        "E:VIDEO:1:0": ItemStatus.MISSING_CUT,
        "E:VIDEO:1:1": ItemStatus.MISSING_CUT,
    }
    assert report.status is VerificationStatus.MISMATCH


def test_extra_cut() -> None:
    expected = fx.expected_timeline()
    text = fx.set_fields(fx.written(expected), "clipitem-2", end=80, out=230, duration=30)
    text = fx.insert_in_track(
        text, 0, fx.clip_block("s", "B", 80, 110, 230, 260, '<file id="file-2"/>')
    )
    report = _verify(expected, fx.diff_text(expected, text))
    assert report.item("E:VIDEO:1:1").status is ItemStatus.EXTRA_CUT
    added = fx.insert_in_track(
        fx.written(expected), 0, fx.clip_block("n", "N", 110, 130, 0, 20, fx.NEW_FILE)
    )
    report = _verify(expected, fx.diff_text(expected, added))
    assert report.item("A:VIDEO:1:2").status is ItemStatus.EXTRA_CUT
    assert report.item("G:VIDEO:1:2").status is ItemStatus.EXTRA_CUT
    assert report.status is VerificationStatus.MISMATCH


def test_track_flattening() -> None:
    expected = fx.two_video_tracks()
    text = fx.written(expected)
    start = text.index('<clipitem id="clipitem-2">')
    end = text.index("</clipitem>", start) + len("</clipitem>")
    block = text[start:end]
    tracks = [m.start() for m in re.finditer(r"<track>", text)]
    track_end = text.index("</track>", tracks[1]) + len("</track>")
    flattened = fx.insert_in_track(text[: tracks[1]] + text[track_end:], 0, block)
    report = _verify(expected, fx.diff_text(expected, flattened))
    assert report.item("E:VIDEO:2:1").status is ItemStatus.TRACK_FLATTENED
    assert report.item("G:VIDEO:2:0").status is ItemStatus.TRACK_FLATTENED
    assert report.item("E:VIDEO:1:0").status is ItemStatus.MATCH
    assert report.status is VerificationStatus.MISMATCH


def test_unsupported_construct_is_unverified() -> None:
    expected = fx.expected_timeline()
    text = fx.insert_in_track(
        fx.written(expected),
        0,
        "<transitionitem><start>100</start><end>120</end></transitionitem>",
    )
    report = _verify(expected, fx.diff_text(expected, text))
    assert report.status is VerificationStatus.UNVERIFIED
    assert report.item("E:VIDEO:1:1").status is ItemStatus.UNKNOWN
    assert "UNSUPPORTED_REGION" in report.reasons


def test_rate_change_and_unreadable_are_unverified() -> None:
    expected = fx.expected_timeline()
    text = fx.written(expected).replace("<timebase>25</timebase>", "<timebase>24</timebase>")
    report = _verify(expected, fx.diff_text(expected, text))
    assert report.status is VerificationStatus.UNVERIFIED
    assert set(_statuses(report).values()) == {ItemStatus.UNKNOWN}
    unreadable = _verify(expected, fx.diff_text(expected, "<xmeml"))
    assert unreadable.status is VerificationStatus.UNVERIFIED
    assert unreadable.actual_digest is None


def test_human_change_vs_handoff_loss_with_baseline() -> None:
    expected = fx.expected_timeline(marker=True)
    clean = fx.written(expected)
    baseline = fx.diff_text(expected, clean, "baseline.xml")
    edited = fx.delete_clip(clean, "clipitem-3")
    report = _verify(expected, fx.diff_text(expected, edited), EDITED, baseline)
    item = report.item("E:VIDEO:1:3")
    assert item.status is ItemStatus.HUMAN_CHANGED and item.observed is ItemStatus.MISSING_CUT
    assert item.basis is AttributionBasis.BASELINE_REEXPORT
    assert report.status is VerificationStatus.MATCH and report.human_changed_count == 1

    lossy = _strip_markers(clean)
    lossy_baseline = fx.diff_text(expected, lossy, "baseline.xml")
    final = fx.delete_clip(lossy, "clipitem-3")
    report = _verify(expected, fx.diff_text(expected, final), EDITED, lossy_baseline)
    assert report.item("E:VIDEO:1:1").status is ItemStatus.MARKER_LOST
    assert report.item("E:VIDEO:1:1").attribution is Attribution.HANDOFF_LOSS
    assert report.item("E:VIDEO:1:3").status is ItemStatus.HUMAN_CHANGED
    assert report.status is VerificationStatus.MISMATCH

    added = fx.insert_in_track(clean, 0, fx.clip_block("n", "N", 170, 190, 0, 20, fx.NEW_FILE))
    report = _verify(expected, fx.diff_text(expected, added), EDITED, baseline)
    assert report.item("A:VIDEO:1:4").status is ItemStatus.HUMAN_CHANGED


def test_without_evidence_attribution_is_unknown_unless_acknowledged() -> None:
    expected = fx.expected_timeline()
    edited = fx.delete_clip(fx.written(expected), "clipitem-3")
    diff = fx.diff_text(expected, edited)
    report = _verify(expected, diff, EDITED)
    item = report.item("E:VIDEO:1:3")
    assert item.status is ItemStatus.UNKNOWN and item.observed is ItemStatus.MISSING_CUT
    assert report.status is VerificationStatus.UNVERIFIED
    unknown_provenance = _verify(expected, diff, ActualProvenance.UNKNOWN)
    assert unknown_provenance.status is VerificationStatus.UNVERIFIED
    acknowledged = _verify(expected, diff, EDITED, acknowledged=("E:VIDEO:1:3",))
    assert acknowledged.item("E:VIDEO:1:3").status is ItemStatus.HUMAN_CHANGED
    assert acknowledged.item("E:VIDEO:1:3").basis is AttributionBasis.USER_ACKNOWLEDGED
    assert acknowledged.status is VerificationStatus.MATCH


def test_stale_or_mismatched_approval_is_refused() -> None:
    expected = fx.expected_timeline()
    diff = fx.diff_text(expected, fx.written(expected))
    other = artifact_revision("ver001", "plan-1", fx.cut_timeline())
    with pytest.raises(ValueError):
        verify_roundtrip(other, expected, diff, provenance=IMMEDIATE)
    with pytest.raises(ValueError):
        _verify(fx.cut_timeline(), diff)
    cut = fx.cut_timeline()
    with pytest.raises(ValueError):
        _verify(expected, diff, EDITED, fx.diff_text(cut, fx.written(cut)))


def test_render_is_deterministic_and_keeps_codes() -> None:
    expected = fx.expected_timeline()
    text = fx.set_fields(fx.written(expected), "clipitem-3", start=131, end=171)
    report = _verify(expected, fx.diff_text(expected, text))
    rendered = render_report(report)
    assert rendered == render_report(report)
    assert "Overall: MISMATCH" in rendered
    assert "FRAME_DRIFT delta=+1" in rendered
    assert "FILE_ROUNDTRIP (file round-trip; not native, not live)" in rendered
    korean = render_report(report, korean=True)
    assert "MISMATCH (불일치)" in korean and "FRAME_DRIFT (프레임 어긋남)" in korean
    assert report.digest == _verify(expected, fx.diff_text(expected, text)).digest
