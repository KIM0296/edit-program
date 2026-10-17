"""LLM-001 advisory cut boundary check tests (synthetic word timings, no media)."""

import pytest

from davinci_ai_editor.cut_boundary_check import (
    BoundaryFinding,
    BoundaryFindingCode,
    BoundaryPolicy,
    CutEdge,
    FindingSeverity,
    SnapSuggestion,
    check_removal_boundaries,
)
from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.temporal_mapping import SourceFrameRange
from davinci_ai_editor.transcript import (
    TranscriptSnapshot,
    TranscriptTokenKind,
    TranscriptWord,
    WordTimingStatus,
)

C = BoundaryFindingCode
POLICY = BoundaryPolicy(min_padding_frames=2, unsafe_gap_frames=4, review_gap_frames=10)


def word(
    ref: str,
    start: int | None,
    end: int | None = None,
    speaker: str | None = "A",
    kind: TranscriptTokenKind = TranscriptTokenKind.WORD,
) -> TranscriptWord:
    if start is None:
        return TranscriptWord(ref, ref, None, WordTimingStatus.MISSING, kind, speaker)
    assert end is not None
    rng = SourceFrameRange(FrameRange(start, end))
    return TranscriptWord(ref, ref, rng, WordTimingStatus.ALIGNED, kind, speaker)


def snap(*words: TranscriptWord, tolerance: int = 0) -> TranscriptSnapshot:
    return TranscriptSnapshot("tx", "src", "prod", tolerance, words)


# Retained "keep1" [0,10) | removable "drop" [30,40) | retained "keep2" [60,70).
WIDE = (word("keep1", 0, 10), word("drop", 30, 40), word("keep2", 60, 70))


def codes(findings: tuple[BoundaryFinding, ...], edge: CutEdge | None = None) -> set[C]:
    return {f.code for f in findings if edge is None or f.edge is edge}


def test_clean_removal_in_wide_silences_has_no_findings() -> None:
    assert check_removal_boundaries(FrameRange(20, 50), snap(*WIDE), POLICY) == ()


@pytest.mark.parametrize(
    ("start", "inside"),
    [(29, False), (30, False), (31, True), (39, True), (40, False), (41, False)],
)
def test_start_edge_at_plus_minus_one_of_word_edges(start: int, inside: bool) -> None:
    findings = check_removal_boundaries(FrameRange(start, 50), snap(*WIDE), POLICY)
    assert (C.CUTS_INSIDE_WORD in codes(findings, CutEdge.START)) is inside


@pytest.mark.parametrize(
    ("end", "inside"),
    [(59, False), (60, False), (61, True), (69, True), (70, False)],
)
def test_end_edge_at_plus_minus_one_of_word_edges(end: int, inside: bool) -> None:
    findings = check_removal_boundaries(FrameRange(20, end), snap(*WIDE), POLICY)
    assert (C.CUTS_INSIDE_WORD in codes(findings, CutEdge.END)) is inside


def test_inside_word_reports_retaining_snap_but_never_applies_it() -> None:
    removal = FrameRange(33, 50)
    findings = check_removal_boundaries(removal, snap(*WIDE, tolerance=3), POLICY)
    inside = next(f for f in findings if f.code is C.CUTS_INSIDE_WORD)
    assert inside.severity is FindingSeverity.UNSAFE
    assert inside.word_ref == "drop" and inside.distance_frames == 3
    assert inside.suggestion == SnapSuggestion(33, 40, 7, False)
    assert removal == FrameRange(33, 50)  # untouched

    end_inside = check_removal_boundaries(FrameRange(20, 62), snap(*WIDE, tolerance=3), POLICY)
    sug = next(f for f in end_inside if f.code is C.CUTS_INSIDE_WORD).suggestion
    assert sug == SnapSuggestion(62, 60, -2, True)


@pytest.mark.parametrize(
    ("start", "padding_finding"),
    [(11, True), (12, False), (13, False)],
)
def test_padding_threshold_exact(start: int, padding_finding: bool) -> None:
    findings = check_removal_boundaries(FrameRange(start, 50), snap(*WIDE), POLICY)
    assert (C.PADDING_BELOW_MIN in codes(findings, CutEdge.START)) is padding_finding
    if padding_finding:
        pad = next(f for f in findings if f.code is C.PADDING_BELOW_MIN)
        assert pad.distance_frames == 1 and pad.word_ref == "keep1"
        assert pad.suggestion == SnapSuggestion(11, 12, 1, False)


def test_end_edge_padding_measures_to_next_retained_word() -> None:
    findings = check_removal_boundaries(FrameRange(20, 59), snap(*WIDE), POLICY)
    pad = next(f for f in findings if f.code is C.PADDING_BELOW_MIN)
    assert pad.edge is CutEdge.END and pad.word_ref == "keep2" and pad.distance_frames == 1
    assert pad.suggestion is not None and pad.suggestion.to_frame == 58


@pytest.mark.parametrize(
    ("gap", "expected"),
    [(3, C.GAP_UNSAFE), (4, C.GAP_REVIEW), (9, C.GAP_REVIEW), (10, None)],
)
def test_gap_classification_thresholds(gap: int, expected: C | None) -> None:
    words = (word("a", 0, 10), word("b", 10 + gap, 20 + gap), word("c", 100, 110))
    policy = BoundaryPolicy(0, 4, 10)
    findings = check_removal_boundaries(FrameRange(10, 50), snap(*words), policy)
    gap_codes = codes(findings, CutEdge.START) & {C.GAP_UNSAFE, C.GAP_REVIEW}
    assert gap_codes == (set() if expected is None else {expected})


@pytest.mark.parametrize(
    ("start", "tolerance", "near"),
    [
        (13, 2, False),  # 3 frames from keep1 end
        (12, 2, True),  # exactly at tolerance
        (11, 1, True),  # +1 frame, tolerance 1
        (11, 0, False),  # tolerance 0: exact transcript claim
        (28, 2, True),  # 2 frames before removed word onset
        (27, 2, False),
    ],
)
def test_edge_within_tolerance_of_word_edge_is_review_not_clean(
    start: int, tolerance: int, near: bool
) -> None:
    policy = BoundaryPolicy(0, 0, 0)
    findings = check_removal_boundaries(
        FrameRange(start, 50), snap(*WIDE, tolerance=tolerance), policy
    )
    near_findings = [f for f in findings if f.code is C.NEAR_WORD_EDGE_WITHIN_TOLERANCE]
    assert bool(near_findings) is near
    assert all(f.severity is FindingSeverity.REVIEW for f in near_findings)


def test_edge_exactly_on_word_edge_with_tolerance_is_review() -> None:
    policy = BoundaryPolicy(0, 0, 0)
    exact = check_removal_boundaries(FrameRange(30, 50), snap(*WIDE, tolerance=1), policy)
    assert C.NEAR_WORD_EDGE_WITHIN_TOLERANCE in codes(exact, CutEdge.START)
    clean = check_removal_boundaries(FrameRange(30, 50), snap(*WIDE, tolerance=0), policy)
    assert clean == ()


def test_audio_event_truncated() -> None:
    words = (word("a", 0, 10), word("laugh", 20, 40, kind=TranscriptTokenKind.AUDIO_EVENT))
    findings = check_removal_boundaries(FrameRange(25, 60), snap(*words), POLICY)
    assert codes(findings, CutEdge.START) == {C.AUDIO_EVENT_TRUNCATED}
    assert findings[0].severity is FindingSeverity.UNSAFE


def test_speaker_handoff_tight_on_join() -> None:
    words = (word("a", 0, 10, "A"), word("x", 13, 20, "A"), word("b", 23, 30, "B"))
    findings = check_removal_boundaries(FrameRange(12, 22), snap(*words), POLICY)
    join = [f for f in findings if f.edge is CutEdge.JOIN]
    assert [f.code for f in join] == [C.SPEAKER_HANDOFF_TIGHT]
    assert join[0].distance_frames == 3
    same = (word("a", 0, 10, "A"), word("x", 13, 20, "A"), word("b", 23, 30, "A"))
    assert C.SPEAKER_HANDOFF_TIGHT not in codes(
        check_removal_boundaries(FrameRange(12, 22), snap(*same), POLICY)
    )
    roomy = check_removal_boundaries(FrameRange(12, 22), snap(*words), BoundaryPolicy(0, 0, 3))
    assert C.SPEAKER_HANDOFF_TIGHT not in codes(roomy)


def test_untimed_neighbour_is_timing_unknown() -> None:
    words = (word("a", 0, 10), word("ghost", None), word("b", 30, 40), word("c", 60, 70))
    findings = check_removal_boundaries(FrameRange(20, 50), snap(*words), POLICY)
    start = [f for f in findings if f.edge is CutEdge.START]
    assert [f.code for f in start] == [C.TIMING_UNKNOWN]
    assert start[0].word_ref == "ghost"
    assert C.TIMING_UNKNOWN not in codes(findings, CutEdge.END)


def test_untimed_only_transcript_is_timing_unknown() -> None:
    findings = check_removal_boundaries(FrameRange(0, 10), snap(word("a", None)), POLICY)
    assert [f.code for f in findings] == [C.TIMING_UNKNOWN]


def test_removal_inside_single_word_flags_both_edges() -> None:
    findings = check_removal_boundaries(FrameRange(32, 38), snap(*WIDE), POLICY)
    assert [(f.edge, f.code) for f in findings] == [
        (CutEdge.START, C.CUTS_INSIDE_WORD),
        (CutEdge.END, C.CUTS_INSIDE_WORD),
    ]


def test_findings_are_deterministic_and_ordered() -> None:
    words = (word("a", 0, 10, "A"), word("x", 11, 20, "A"), word("b", 21, 30, "B"))
    first = check_removal_boundaries(FrameRange(10, 21), snap(*words, tolerance=1), POLICY)
    second = check_removal_boundaries(FrameRange(10, 21), snap(*words, tolerance=1), POLICY)
    assert first == second
    order = {CutEdge.START: 0, CutEdge.END: 1, CutEdge.JOIN: 2}
    assert [order[f.edge] for f in first] == sorted(order[f.edge] for f in first)


def test_policy_and_value_validation() -> None:
    with pytest.raises(ValueError):
        BoundaryPolicy(-1, 0, 0)
    with pytest.raises(ValueError):
        BoundaryPolicy(0, 5, 4)
    with pytest.raises(ValueError):
        BoundaryPolicy(True, 0, 0)
    with pytest.raises(ValueError):
        SnapSuggestion(1, 3, 1, True)
    with pytest.raises(ValueError):
        SnapSuggestion(1, 1, 0, True)
    with pytest.raises(ValueError):
        BoundaryFinding(C.GAP_REVIEW, FindingSeverity.UNSAFE, CutEdge.START, 0, None, 1, "x")
    with pytest.raises(ValueError):
        BoundaryFinding(C.UNKNOWN, FindingSeverity.REVIEW, CutEdge.START, 0, None, 1, "x")
    with pytest.raises(TypeError):
        check_removal_boundaries((0, 5), snap(*WIDE), POLICY)  # type: ignore[arg-type]
