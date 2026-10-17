"""PVP-001C TEST_ONLY_SUPPORT: hand-built sequences; no media, no Resolve."""

import ast
import inspect
import itertools
from dataclasses import replace

import pytest

from davinci_ai_editor import pause_cut_geometry as g
from davinci_ai_editor.domain import FrameRange

T, F = True, False
OFFSET = 100


def seq(text: str) -> tuple[bool, ...]:
    """'#' = active (non-silent), '.' = silent."""
    return tuple(c == "#" for c in text)


def regions_of(active: tuple[bool, ...], offset: int = OFFSET) -> tuple[FrameRange, ...]:
    out: list[FrameRange] = []
    start: int | None = None
    for i, a in enumerate((*active, True)):
        if not a and start is None:
            start = i
        elif a and start is not None:
            out.append(FrameRange(offset + start, offset + i))
            start = None
    return tuple(out)


def window_of(n: int, offset: int = OFFSET) -> FrameRange:
    return FrameRange(offset, offset + n)


def active_of(result: g.CutGeometryResult, n: int, offset: int = OFFSET) -> tuple[bool, ...]:
    out = [True] * n
    for s in result.spans:
        for f in range(s.interior.start, s.interior.end):
            out[f - offset] = False
    return tuple(out)


def policy(head: int = 0, tail: int = 0, bridge: int = 0, cut: int = 0) -> g.CutGeometryPolicy:
    return g.CutGeometryPolicy(head, tail, bridge, cut)


def derive(text: str, pol: g.CutGeometryPolicy) -> g.CutGeometryResult:
    a = seq(text)
    return g.derive_cut_candidate_geometry(regions_of(a), window_of(len(a)), pol)


def all_seqs(max_len: int = 10) -> list[tuple[bool, ...]]:
    return [b for n in range(1, max_len + 1) for b in itertools.product((F, T), repeat=n)]


# --- Ported layer: apply_margin ---------------------------------------------------


def test_margin_zero_is_identity_and_pure() -> None:
    a = [T, F, F, T]
    assert g.apply_margin(a, 0, 0) == (T, F, F, T)
    assert a == [T, F, F, T]


def test_positive_margins_extend_active_around_transitions() -> None:
    assert g.apply_margin(seq("..##....##.."), 1, 0) == seq(".###...###..")
    assert g.apply_margin(seq("..##....##.."), 0, 1) == seq("..###...###.")
    assert g.apply_margin(seq("..##....##.."), 2, 2) == seq("############")


def test_edges_are_not_transitions() -> None:
    assert g.apply_margin(seq("##...##"), 0, 0) == seq("##...##")
    assert g.apply_margin(seq("......"), 3, 3) == seq("......")
    assert g.apply_margin(seq("######"), -3, -3) == seq("######")
    assert g.apply_margin(seq("...##"), 0, 5) == seq("...##")


def test_negative_margins_shrink_active_runs() -> None:
    assert g.apply_margin(seq("..####.."), -1, 0) == seq("...###..")
    assert g.apply_margin(seq("..####.."), 0, -1) == seq("..###...")
    assert g.apply_margin(seq("..####.."), -2, -2) == seq("........")
    # Margins clamp at the sequence bounds.
    assert g.apply_margin(seq(".##"), -5, 0) == seq("...")
    assert g.apply_margin(seq("##."), 0, -5) == seq("...")


def test_start_margin_applied_before_end_margin() -> None:
    # Positive start then negative end on the same short run: end wins.
    assert g.apply_margin(seq("..#.."), 1, -1) == seq(".#...")
    # Negative start then positive end: end margin re-activates after the run.
    assert g.apply_margin(seq("..#.."), -1, 1) == seq("...#.")


def test_odd_lengths_and_empty() -> None:
    assert g.apply_margin((), 2, 2) == ()
    assert g.apply_margin(seq(".#."), 1, 1) == seq("###")
    assert g.apply_margin(seq("#.#.#"), 1, 0) == seq("#####")


# --- Ported layer: smooth_runs ----------------------------------------------------


def test_smoothing_zero_is_identity() -> None:
    for a in all_seqs(6):
        assert g.smooth_runs(a, 0, 0) == a


def test_mincut_fills_short_silences_including_edges() -> None:
    assert g.smooth_runs(seq("##.##...##"), 2, 0) == seq("#####...##")
    assert g.smooth_runs(seq(".####."), 2, 0) == seq("######")
    assert g.smooth_runs(seq("..###.."), 2, 0) == seq("..###..")


def test_minclip_removes_short_clips_including_edges() -> None:
    assert g.smooth_runs(seq("..#..##.."), 0, 2) == seq(".....##..")
    assert g.smooth_runs(seq("#....#"), 0, 2) == seq("......")


def test_two_cycle_guard_terminates() -> None:
    # A lone run shorter than both thresholds flips all-true <-> all-false.
    assert g.smooth_runs((T,), 2, 2) == (T,)
    assert g.smooth_runs((F,), 2, 2) == (F,)
    assert g.smooth_runs((T, T), 3, 3) == (T, T)


def test_smoothing_is_idempotent_when_no_cycle() -> None:
    for a in all_seqs(8):
        for mc, ml in ((2, 0), (0, 2), (3, 0), (0, 3)):
            once = g.smooth_runs(a, mc, ml)
            assert g.smooth_runs(once, mc, ml) == once


def test_smoothing_terminates_on_exhaustive_small_inputs() -> None:
    for a in all_seqs(8):
        for mc in range(4):
            for ml in range(4):
                out = g.smooth_runs(a, mc, ml)
                assert len(out) == len(a)


def test_ported_layer_rejects_bad_types() -> None:
    with pytest.raises(TypeError):
        g.apply_margin([1, 0], 0, 0)  # type: ignore[list-item]
    with pytest.raises(TypeError):
        g.apply_margin([T], True, 0)
    with pytest.raises(TypeError):
        g.smooth_runs([T], 1, False)
    with pytest.raises(TypeError):
        g.smooth_runs("#.", 1, 1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        g.smooth_runs([T], -1, 0)
    with pytest.raises(ValueError):
        g.smooth_runs([T], 0, -1)


# --- Policy -----------------------------------------------------------------------


def test_policy_validation_and_ref() -> None:
    p = policy(1, 2, 3, 4)
    assert p.policy_ref == policy(1, 2, 3, 4).policy_ref
    assert p.policy_ref.startswith("cut-geometry-policy:")
    refs = {policy(*v).policy_ref for v in itertools.permutations((1, 2, 3, 4))}
    assert len(refs) == 24
    with pytest.raises(TypeError):
        g.CutGeometryPolicy(True, 0, 0, 0)
    with pytest.raises(TypeError):
        g.CutGeometryPolicy(0, 0, 0, 1.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        g.CutGeometryPolicy(0, -1, 0, 0)


# --- Contract: validation ---------------------------------------------------------


def test_refuses_unordered_overlapping_touching_and_outside() -> None:
    w = FrameRange(0, 20)
    p = policy()
    bad = (
        (FrameRange(5, 8), FrameRange(1, 3)),
        (FrameRange(1, 5), FrameRange(4, 8)),
        (FrameRange(1, 5), FrameRange(5, 8)),
        (FrameRange(1, 5), FrameRange(1, 5)),
        (FrameRange(15, 21),),
    )
    for regions in bad:
        with pytest.raises(ValueError):
            g.derive_cut_candidate_geometry(regions, w, p)
        with pytest.raises(ValueError):
            g.bridge_short_active_gaps(regions, w, 0)
    with pytest.raises(TypeError):
        g.derive_cut_candidate_geometry(((1, 3),), w, p)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        g.derive_cut_candidate_geometry((), (0, 5), p)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        g.derive_cut_candidate_geometry((), w, (0, 0, 0, 0))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        g.bridge_short_active_gaps((), w, True)


# --- Contract: geometry -----------------------------------------------------------


def test_zero_handles_reproduce_regions() -> None:
    r = derive("##....###...##", policy())
    assert [s.interior for s in r.spans] == list(r.source_regions)
    assert all(s.head_keep == 0 and s.tail_keep == 0 for s in r.spans)
    assert r.derivation == "PVP-001C-geometry-v1"
    assert r.authorization == g.AUTHORIZATION_STATEMENT
    assert r.policy_ref == r.policy.policy_ref


def test_handles_shrink_interior_and_record_amounts() -> None:
    r = derive("##......##", policy(head=2, tail=1))
    (s,) = r.spans
    assert s.source_region == FrameRange(102, 108)
    assert s.interior == FrameRange(104, 107)
    assert (s.head_keep, s.tail_keep) == (2, 1)
    assert not s.clamped_at_window_start and not s.clamped_at_window_end


def test_handles_consuming_region_drop_it() -> None:
    r = derive("##...##", policy(head=2, tail=1))
    assert r.outcomes == (
        g.DroppedRegion(FrameRange(102, 105), g.DroppedReason.DROPPED_EMPTY_AFTER_HANDLES),
    )
    assert r.spans == ()


def test_window_edge_clamping_skips_handles() -> None:
    r = derive("...##.....##...", policy(head=1, tail=1))
    first, mid, last = r.outcomes
    assert isinstance(first, g.DerivedCutSpan) and isinstance(last, g.DerivedCutSpan)
    assert first.clamped_at_window_start and first.head_keep == 0 and first.tail_keep == 1
    assert first.interior == FrameRange(100, 102)
    assert last.clamped_at_window_end and last.tail_keep == 0 and last.head_keep == 1
    assert last.interior == FrameRange(113, 115)
    assert isinstance(mid, g.DerivedCutSpan) and mid.interior == FrameRange(106, 109)
    whole = derive(".....", policy(head=3, tail=3))
    (s,) = whole.spans
    assert s.interior == FrameRange(100, 105)
    assert s.clamped_at_window_start and s.clamped_at_window_end


def test_min_cut_drops_short_interiors() -> None:
    r = derive("#..#.....#", policy(cut=3))
    assert r.outcomes[0] == g.DroppedRegion(FrameRange(101, 103), g.DroppedReason.DROPPED_TOO_SHORT)
    assert isinstance(r.outcomes[1], g.DerivedCutSpan)
    # min_cut is judged after handles, as in auto-editor (margin before smoothing).
    r2 = derive("#.....#", policy(head=1, tail=1, cut=4))
    assert r2.outcomes[0] == g.DroppedRegion(
        FrameRange(101, 106), g.DroppedReason.DROPPED_TOO_SHORT
    )


def test_bridge_function_lists_every_bridged_gap() -> None:
    a = seq("#...#..##...#....")
    groups = g.bridge_short_active_gaps(regions_of(a), window_of(len(a)), 1)
    assert [grp.span for grp in groups] == [FrameRange(101, 107), FrameRange(109, 117)]
    assert groups[0].bridged == (FrameRange(104, 105),)
    assert groups[1].bridged == (FrameRange(112, 113),)
    assert groups[0].members == (FrameRange(101, 104), FrameRange(105, 107))
    assert g.bridge_short_active_gaps(regions_of(a), window_of(len(a)), 0) == tuple(
        g.BridgedGroup((r,), r, ()) for r in regions_of(a)
    )


def test_bridge_is_single_pass_chaining_left_to_right() -> None:
    a = seq("..#..#..#..")
    groups = g.bridge_short_active_gaps(regions_of(a), window_of(len(a)), 1)
    assert len(groups) == 1 and len(groups[0].bridged) == 3
    assert groups[0].span == FrameRange(100, 111)


def test_bridge_never_extends_to_window_edges() -> None:
    a = seq("#...#")
    groups = g.bridge_short_active_gaps(regions_of(a), window_of(len(a)), 5)
    assert [grp.span for grp in groups] == [FrameRange(101, 104)]


def test_derived_span_merges_and_reports_bridged_frames() -> None:
    r = derive("##.....#.....##", policy(head=1, tail=1, bridge=3))
    span, merged = r.outcomes
    assert isinstance(span, g.DerivedCutSpan)
    assert span.interior == FrameRange(103, 112)
    assert span.merged_regions == (FrameRange(108, 113),)
    assert span.bridged == (FrameRange(106, 109),)
    assert span.bridged_active == (FrameRange(107, 108),)
    assert (span.head_keep, span.tail_keep) == (1, 1)
    assert merged == g.DroppedRegion(
        FrameRange(108, 113),
        g.DroppedReason.MERGED_INTO_PRECEDING_SPAN,
        merged_into=FrameRange(102, 107),
    )


def test_group_shorter_than_min_cut_drops_every_member() -> None:
    r = derive("#..#..#", policy(bridge=1, cut=6))
    assert [o.reason for o in r.outcomes if isinstance(o, g.DroppedRegion)] == [
        g.DroppedReason.DROPPED_TOO_SHORT,
        g.DroppedReason.DROPPED_TOO_SHORT,
    ]


def test_determinism_and_raw_input_untouched() -> None:
    a = seq("#...#..##...#....##.")
    regions = list(regions_of(a))
    snapshot = list(regions)
    p = policy(1, 1, 2, 2)
    r1 = g.derive_cut_candidate_geometry(regions, window_of(len(a)), p)
    r2 = g.derive_cut_candidate_geometry(tuple(regions), window_of(len(a)), p)
    assert r1 == r2
    assert regions == snapshot
    assert r1.source_regions == tuple(snapshot)


def test_result_and_outcome_validation() -> None:
    r = derive("#....#", policy(head=1))
    with pytest.raises(ValueError):
        replace(r, authorization="AUTHORIZES REMOVE")
    with pytest.raises(ValueError):
        replace(r, derivation="other")
    with pytest.raises(ValueError):
        replace(r, policy_ref="cut-geometry-policy:x")
    with pytest.raises(ValueError):
        replace(r, outcomes=())
    (s,) = r.spans
    with pytest.raises(ValueError):
        replace(s, head_keep=2)
    with pytest.raises(ValueError):
        replace(s, clamped_at_window_start=True)
    with pytest.raises(TypeError):
        replace(s, clamped_at_window_end=0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        g.DroppedRegion(FrameRange(1, 2), g.DroppedReason.UNKNOWN)
    with pytest.raises(ValueError):
        g.DroppedRegion(FrameRange(1, 2), g.DroppedReason.MERGED_INTO_PRECEDING_SPAN)
    with pytest.raises(ValueError):
        g.DroppedRegion(
            FrameRange(1, 2), g.DroppedReason.DROPPED_TOO_SHORT, merged_into=FrameRange(0, 1)
        )


def test_module_emits_no_action_or_semantic_vocabulary() -> None:
    tree = ast.parse(inspect.getsource(g))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    forbidden = {"REMOVE", "TIGHTEN", "PauseAction", "ContentMode", "SPEECH", "CutDecision"}
    assert not forbidden & (names | attrs | imports)
    assert {m.value for m in g.DroppedReason} >= {"UNKNOWN"}


# --- Equivalence with the ported auto-editor functions ----------------------------


def _edge_clip_free(margined: tuple[bool, ...], minclip: int) -> bool:
    """True when auto-editor's edge-run minclip rule would not fire."""
    n = len(margined)
    lead = next((i for i, a in enumerate(margined) if not a), n)
    trail = next((i for i, a in enumerate(reversed(margined)) if not a), n)
    return not ((0 < lead < minclip) or (0 < trail < minclip))


def test_equivalence_margin_is_keep_handles() -> None:
    for a in all_seqs(10):
        for head, tail in ((0, 0), (1, 0), (0, 1), (1, 2), (2, 1), (3, 3)):
            r = g.derive_cut_candidate_geometry(
                regions_of(a), window_of(len(a)), policy(head, tail)
            )
            assert active_of(r, len(a)) == g.apply_margin(a, tail, head), (a, head, tail)


def test_equivalence_min_cut_is_mincut() -> None:
    for a in all_seqs(10):
        for head, tail, cut in ((0, 0, 2), (0, 0, 3), (1, 1, 2), (2, 0, 3)):
            r = g.derive_cut_candidate_geometry(
                regions_of(a), window_of(len(a)), policy(head, tail, 0, cut)
            )
            expected = g.smooth_runs(g.apply_margin(a, tail, head), cut, 0)
            assert active_of(r, len(a)) == expected, (a, head, tail, cut)


def test_equivalence_bridge_is_minclip_away_from_window_edges() -> None:
    checked = 0
    for a in all_seqs(10):
        for head, tail, bridge in ((0, 0, 1), (0, 0, 2), (1, 1, 1), (1, 0, 3)):
            margined = g.apply_margin(a, tail, head)
            if not _edge_clip_free(margined, bridge + 1):
                continue
            checked += 1
            r = g.derive_cut_candidate_geometry(
                regions_of(a), window_of(len(a)), policy(head, tail, bridge, 0)
            )
            expected = g.smooth_runs(margined, 0, bridge + 1)
            assert active_of(r, len(a)) == expected, (a, head, tail, bridge)
    assert checked > 1000


def test_documented_difference_edge_runs_are_not_bridged() -> None:
    a = seq("#....")
    r = g.derive_cut_candidate_geometry(regions_of(a), window_of(len(a)), policy(bridge=3))
    assert active_of(r, len(a)) == a
    assert g.smooth_runs(a, 0, 4) == seq(".....")


# --- Property-style invariants ----------------------------------------------------


def test_invariants_over_exhaustive_small_sequences() -> None:
    policies = [policy(*v) for v in itertools.product((0, 1, 2), (0, 2), (0, 1, 3), (0, 2))]
    for a in all_seqs(10):
        regions = regions_of(a)
        w = window_of(len(a))
        for p in policies:
            r = g.derive_cut_candidate_geometry(regions, w, p)
            assert r.source_regions == regions
            assert len(r.outcomes) == len(regions)
            prev_end = -1
            covered = set()
            for s in r.spans:
                assert w.contains(s.interior)
                assert s.interior.start > prev_end
                prev_end = s.interior.end
                assert s.interior.duration >= p.min_cut_frames
                assert s.source_region.start <= s.interior.start
                for m in (s.source_region, *s.merged_regions):
                    covered.add(m)
                # Every interior frame is silence unless listed as bridged active.
                for f in range(s.interior.start, s.interior.end):
                    assert (not a[f - OFFSET]) or any(
                        b.start <= f < b.end for b in s.bridged_active
                    )
            for o in r.outcomes:
                if isinstance(o, g.DroppedRegion) and o.merged_into is not None:
                    assert o.source_region in covered
