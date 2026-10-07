from dataclasses import FrozenInstanceError, replace
from itertools import permutations

import pytest

from davinci_ai_editor import (
    authority,
    dependency,
    evidence,
    native_snapshot,
    pause,
    pause_planning,
    safety,
    temporal_mapping,
)
from davinci_ai_editor.cut_geometry import (
    ExplicitGeometryInput,
    GeometryConstraint,
    GeometryProducerRef,
    GeometryResolutionInput,
    resolve_geometry,
)
from davinci_ai_editor.cut_geometry import (
    GeometryConfidence as GC,
)
from davinci_ai_editor.cut_geometry import (
    GeometryConstraintKind as K,
)
from davinci_ai_editor.cut_geometry import (
    GeometryProducerKind as PK,
)
from davinci_ai_editor.cut_geometry import (
    GeometryResolutionReason as R,
)
from davinci_ai_editor.cut_geometry import (
    GeometryResolutionStatus as S,
)
from davinci_ai_editor.domain import FrameRange, TimelineObjectId
from davinci_ai_editor.evidence import EvidenceStrength
from davinci_ai_editor.fake_timeline import FakeTimeline
from davinci_ai_editor.pause import (
    Confidence,
    ContentMode,
    DecisionReason,
    PauseAction,
    PauseBoundaryKind,
    PauseCandidate,
    PauseObservation,
    PauseSignal,
    RelativePauseBand,
)
from davinci_ai_editor.pause_planning import PlanningBinding
from davinci_ai_editor.temporal_mapping import MappingStatus, NativeSnapshotRef

SNAP = NativeSnapshotRef("main", 42, "state")
OBJECT = TimelineObjectId("audio", "placement")
PAUSE = FrameRange(100, 160)
CUT = FrameRange(110, 150)
OBS = PauseObservation(
    "main",
    42,
    OBJECT,
    PAUSE,
    RelativePauseBand.LONG,
    PauseBoundaryKind.WITHIN_PHRASE,
    (PauseSignal.HESITATION,),
    20,
    ContentMode.SPOKEN_CONTENT,
)
CANDIDATE = PauseCandidate(
    OBS, PauseAction.TIGHTEN, Confidence.MEDIUM, (DecisionReason.HESITATION,), 20
)
BINDING = PlanningBinding("candidate", SNAP, OBJECT, PAUSE)
PRODUCER = GeometryProducerRef(PK.EXPLICIT_CALLER, "caller", "1", "v1")
BASE = GeometryResolutionInput(
    "resolution", CANDIDATE, BINDING, SNAP, FrameRange(0, 200), MappingStatus.EXACT
)


def constraint(ref, kind, payload, confidence=GC.UNKNOWN, producer=PRODUCER):
    return GeometryConstraint(ref, BINDING, kind, payload, producer, confidence)


def explicit(ref="explicit", removed=CUT, confidence=GC.UNKNOWN, producer=PRODUCER):
    return ExplicitGeometryInput(ref, BINDING, (removed,), producer, confidence)


def resolve(constraints=(), geometries=(), **changes):
    return resolve_geometry(
        replace(BASE, constraints=constraints, explicit_geometries=geometries, **changes)
    )


def test_vocabulary_exactly_four_and_confidence_types_separate():
    assert {k.value for k in K} == {
        "CUT_START_ANCHOR",
        "CUT_END_ANCHOR",
        "MUST_PRESERVE_RANGE",
        "ALLOWED_REMOVAL_RANGE",
    }
    assert GC is not EvidenceStrength and GC is not Confidence
    for value in (EvidenceStrength.STRONG, Confidence.HIGH, "STRONG", 0.9):
        with pytest.raises(TypeError):
            explicit(confidence=value)


def test_duration_alone_is_unresolved_no_implicit_cut():
    result = resolve()
    assert result.status == S.UNRESOLVED and result.candidates == ()
    assert result.inputs.candidate.action == PauseAction.TIGHTEN


def test_unique_explicit_geometry_and_retained_metadata():
    result = resolve(geometries=(explicit(confidence=GC.WEAK),))
    assert result.status == S.RESOLVED and len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.removed_range == CUT and candidate.binding == BINDING
    assert candidate.retained_leading_frames == 10 and candidate.retained_trailing_frames == 10
    assert candidate.retained_total_frames == 20
    assert candidate.geometry_confidences == (GC.WEAK,)
    assert candidate.support_input_ids == ("explicit",)


@pytest.mark.parametrize(
    "removed,reason",
    [
        (FrameRange(110, 149), R.REQUIRED_DURATION_MISMATCH),
        (FrameRange(99, 139), R.OUTSIDE_PAUSE),
        (FrameRange(121, 161), R.OUTSIDE_PAUSE),
    ],
)
def test_invalid_explicit_geometry_not_repaired(removed, reason):
    item = explicit(removed=removed)
    result = resolve(geometries=(item,))
    assert result.status == S.UNRESOLVED and result.candidates == ()
    assert reason in {d.reason for d in result.diagnostics}
    assert result.inputs.explicit_geometries == (item,)


def test_valid_anchor_pair_only():
    constraints = (
        constraint("start", K.CUT_START_ANCHOR, 110, GC.STRONG),
        constraint("end", K.CUT_END_ANCHOR, 150, GC.MODERATE),
    )
    result = resolve(constraints)
    assert result.status == S.RESOLVED
    assert result.candidates[0].removed_range == CUT
    assert set(result.candidates[0].source_constraint_ids) == {"start", "end"}
    assert set(result.candidates[0].geometry_confidences) == {GC.STRONG, GC.MODERATE}


@pytest.mark.parametrize(
    "constraints",
    [
        (constraint("s", K.CUT_START_ANCHOR, 110),),
        (constraint("e", K.CUT_END_ANCHOR, 150),),
        (constraint("s", K.CUT_START_ANCHOR, 110), constraint("e", K.CUT_END_ANCHOR, 149)),
        (constraint("s", K.CUT_START_ANCHOR, 150), constraint("e", K.CUT_END_ANCHOR, 110)),
        (constraint("s", K.CUT_START_ANCHOR, 110), constraint("e", K.CUT_END_ANCHOR, 110)),
    ],
)
def test_missing_or_wrong_pair_never_nearest_anchor(constraints):
    assert resolve(constraints).status == S.UNRESOLVED
    assert resolve(constraints).candidates == ()


def test_multiple_anchor_geometries_require_review_not_lexical_preference():
    constraints = (
        constraint("z-start", K.CUT_START_ANCHOR, 110),
        constraint("a-start", K.CUT_START_ANCHOR, 120),
        constraint("z-end", K.CUT_END_ANCHOR, 150),
        constraint("a-end", K.CUT_END_ANCHOR, 160),
    )
    result = resolve(constraints)
    assert result.status == S.REVIEW_REQUIRED
    assert {c.removed_range for c in result.candidates} == {CUT, FrameRange(120, 160)}


@pytest.mark.parametrize("left", list(GC))
@pytest.mark.parametrize("right", list(GC))
def test_confidence_never_changes_two_candidate_resolution(left, right):
    result = resolve(
        geometries=(explicit("a", CUT, left), explicit("b", FrameRange(120, 160), right))
    )
    assert result.status == S.REVIEW_REQUIRED and len(result.candidates) == 2


def test_duplicate_geometry_merges_without_losing_producer_confidence_or_support():
    other = replace(
        PRODUCER, producer_kind=PK.FUTURE_MODEL, producer_name="future", producer_version="99"
    )
    constraints = (
        constraint("s", K.CUT_START_ANCHOR, 110),
        constraint("e", K.CUT_END_ANCHOR, 150),
        constraint("allowed", K.ALLOWED_REMOVAL_RANGE, PAUSE),
    )
    result = resolve(
        constraints,
        (
            explicit("one", confidence=GC.STRONG),
            explicit("two", confidence=GC.WEAK, producer=other),
        ),
    )
    assert result.status == S.RESOLVED and len(result.candidates) == 1
    candidate = result.candidates[0]
    assert set(candidate.support_input_ids) == {"s", "e", "allowed", "one", "two"}
    assert set(candidate.source_constraint_ids) == {"s", "e", "allowed"}
    assert {s.producer for s in candidate.supports} == {PRODUCER, other}
    assert set(candidate.geometry_confidences) == {GC.STRONG, GC.WEAK, GC.UNKNOWN}


def test_support_count_never_picks_winner():
    items = (explicit("a"), explicit("b"), explicit("c", FrameRange(120, 160)))
    assert resolve(geometries=items).status == S.REVIEW_REQUIRED


def test_preserve_overlap_rejects_without_shifting_cut():
    protected = constraint("p", K.MUST_PRESERVE_RANGE, FrameRange(110, 111))
    result = resolve((protected,), (explicit(),))
    assert result.status == S.UNRESOLVED and result.candidates == ()
    assert R.PRESERVE_RANGE_CONFLICT in {d.reason for d in result.diagnostics}
    assert result.inputs.explicit_geometries[0].removed_ranges == (CUT,)


def test_preserve_touching_half_open_boundary_is_valid():
    constraints = (
        constraint("left", K.MUST_PRESERVE_RANGE, FrameRange(100, 110)),
        constraint("right", K.MUST_PRESERVE_RANGE, FrameRange(150, 160)),
    )
    assert resolve(constraints, (explicit(),)).status == S.RESOLVED


def test_allowed_ranges_use_intersection_not_union():
    constraints = (
        constraint("a", K.ALLOWED_REMOVAL_RANGE, FrameRange(100, 150)),
        constraint("b", K.ALLOWED_REMOVAL_RANGE, FrameRange(110, 160)),
    )
    assert resolve(constraints, (explicit(),)).status == S.RESOLVED
    bad = constraints + (constraint("c", K.ALLOWED_REMOVAL_RANGE, FrameRange(120, 160)),)
    result = resolve(bad, (explicit(), explicit("other", FrameRange(120, 160))))
    assert result.status == S.UNRESOLVED
    assert R.OUTSIDE_ALLOWED_REMOVAL in {d.reason for d in result.diagnostics}


def test_preserve_or_allowed_constraints_alone_do_not_generate_geometry():
    constraints = (constraint("allowed", K.ALLOWED_REMOVAL_RANGE, CUT),)
    assert resolve(constraints).status == S.UNRESOLVED


@pytest.mark.parametrize(
    "field,value", [("timeline_id", "other"), ("timeline_version", 43), ("state_token", "other")]
)
def test_current_snapshot_mismatch_stale_no_rebase(field, value):
    result = resolve(geometries=(explicit(),), current_snapshot=replace(SNAP, **{field: value}))
    assert result.status == S.STALE and result.candidates == ()
    assert result.inputs.binding == BINDING


@pytest.mark.parametrize(
    "binding",
    [
        replace(BINDING, snapshot_ref=replace(SNAP, timeline_version=41)),
        replace(BINDING, snapshot_ref=replace(SNAP, timeline_id="other")),
        replace(BINDING, object_id=TimelineObjectId("audio", "other-placement")),
        replace(BINDING, original_pause_range=FrameRange(101, 161)),
        replace(BINDING, candidate_ref="other"),
    ],
)
def test_mixed_binding_blocks_constraints_and_explicit_inputs(binding):
    bad = replace(explicit(), binding=binding)
    assert resolve(geometries=(bad,)).status in (S.STALE, S.UNSUPPORTED)
    bad_constraint = replace(constraint("s", K.CUT_START_ANCHOR, 110), binding=binding)
    assert resolve((bad_constraint,), (explicit(),)).status in (S.STALE, S.UNSUPPORTED)


def test_cross_placement_span_and_multirange_unsupported():
    assert (
        resolve(geometries=(explicit(),), placement_range=FrameRange(100, 130)).status
        == S.UNSUPPORTED
    )
    multi = replace(explicit(), removed_ranges=(FrameRange(100, 120), FrameRange(140, 160)))
    assert resolve(geometries=(multi,)).status == S.UNSUPPORTED


@pytest.mark.parametrize("status", list(MappingStatus))
def test_nonexact_mapping_not_resolved_or_called(status):
    result = resolve(geometries=(explicit(),), mapping_status=status)
    assert (result.status == S.RESOLVED) == (status == MappingStatus.EXACT)
    if status == MappingStatus.STALE:
        assert result.status == S.STALE


def test_order_independence_and_defensive_input_copy():
    constraints = [constraint("s", K.CUT_START_ANCHOR, 110), constraint("e", K.CUT_END_ANCHOR, 150)]
    geometries = [explicit("b"), explicit("a", FrameRange(120, 160))]
    expected = resolve(constraints, geometries)
    for c in permutations(constraints):
        for g in permutations(geometries):
            assert resolve(c, g) == expected
    constraints.clear()
    geometries.clear()
    assert len(expected.inputs.constraints) == 2 and len(expected.inputs.explicit_geometries) == 2


@pytest.mark.parametrize(
    "value,field",
    [
        (PRODUCER, "producer_version"),
        (constraint("a", K.CUT_START_ANCHOR, 110), "payload"),
        (explicit(), "removed_ranges"),
        (BASE, "constraints"),
        (resolve(geometries=(explicit(),)), "status"),
        (resolve(geometries=(explicit(),)).candidates[0], "removed_range"),
    ],
)
def test_frozen_values(value, field):
    with pytest.raises(FrozenInstanceError):
        setattr(value, field, None)


def test_no_layer_invocations(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Geometry resolver crossed pure boundary")

    for module, name in [
        (temporal_mapping, "map_range"),
        (native_snapshot, "evaluate_readiness"),
        (pause, "classify_pause"),
        (pause_planning, "plan_pause"),
        (safety, "preflight"),
        (authority, "transition"),
        (evidence, "prepare_observation"),
    ]:
        monkeypatch.setattr(module, name, forbidden)
    for name in dir(dependency):
        if name.startswith("compile"):
            monkeypatch.setattr(dependency, name, forbidden)
    monkeypatch.setattr(FakeTimeline, "apply", forbidden)
    assert resolve(geometries=(explicit(),)).status == S.RESOLVED


@pytest.mark.parametrize(
    "kind,payload",
    [
        (K.CUT_START_ANCHOR, True),
        (K.CUT_END_ANCHOR, 150.0),
        (K.CUT_START_ANCHOR, FrameRange(110, 150)),
        (K.MUST_PRESERVE_RANGE, 110),
        (K.ALLOWED_REMOVAL_RANGE, {"start": 100, "end": 160}),
    ],
)
def test_constraint_payloads_are_typed_no_conversion(kind, payload):
    with pytest.raises(TypeError):
        constraint("bad", kind, payload)


def test_negative_anchor_rejected():
    with pytest.raises(ValueError):
        constraint("bad", K.CUT_START_ANCHOR, -1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("producer_name", ""),
        ("producer_version", " "),
        ("geometry_contract_version", ""),
        ("producer_kind", "EXPLICIT_CALLER"),
        ("producer_config_ref", ""),
    ],
)
def test_producer_metadata_required(field, value):
    with pytest.raises((ValueError, TypeError)):
        replace(PRODUCER, **{field: value})


def test_unsupported_contract_versions_block_whole_bundle():
    assert resolve(geometries=(explicit(),), geometry_contract_version="v2").status == S.UNSUPPORTED
    other = replace(PRODUCER, geometry_contract_version="v2")
    assert (
        resolve(geometries=(explicit(), explicit("other", producer=other))).status == S.UNSUPPORTED
    )


@pytest.mark.parametrize(
    "constraints",
    [
        (constraint("outside", K.MUST_PRESERVE_RANGE, FrameRange(99, 110)),),
        (constraint("outside", K.ALLOWED_REMOVAL_RANGE, FrameRange(90, 170)),),
        (constraint("outside", K.CUT_END_ANCHOR, 161),),
    ],
)
def test_out_of_scope_constraint_not_silently_ignored(constraints):
    assert resolve(constraints, (explicit(),)).status == S.UNSUPPORTED


def test_duplicate_source_ids_rejected_not_latest_wins():
    item = constraint("same", K.CUT_START_ANCHOR, 110)
    with pytest.raises(ValueError):
        resolve((item, item))
    with pytest.raises(ValueError):
        resolve((item,), (explicit("same"),))


def test_invalid_explicit_alternative_does_not_erase_valid_one_or_diagnostics():
    result = resolve(geometries=(explicit("valid"), explicit("invalid", FrameRange(110, 149))))
    assert result.status == S.RESOLVED
    assert result.candidates[0].support_input_ids == ("valid",)
    assert any(
        d.source_ids == ("invalid",) and d.reason == R.REQUIRED_DURATION_MISMATCH
        for d in result.diagnostics
    )
    assert len(result.inputs.explicit_geometries) == 2


def test_empty_geometry_is_unresolved_not_duration_default():
    item = replace(explicit(), removed_ranges=())
    assert resolve(geometries=(item,)).status == S.UNRESOLVED


def test_unsupported_multirange_not_hidden_by_valid_alternative():
    multi = replace(explicit("multi"), removed_ranges=(FrameRange(100, 120), FrameRange(140, 160)))
    assert resolve(geometries=(explicit(), multi)).status == S.UNSUPPORTED


@pytest.mark.parametrize("action", [PauseAction.KEEP, PauseAction.REVIEW, PauseAction.REMOVE])
def test_non_tighten_action_is_unchanged_unsupported(action):
    confidence = Confidence.HIGH if action == PauseAction.REMOVE else Confidence.LOW
    candidate = PauseCandidate(OBS, action, confidence, (DecisionReason.INSUFFICIENT_CONTEXT,))
    result = resolve(geometries=(explicit(),), candidate=candidate)
    assert result.status == S.UNSUPPORTED and result.candidates == ()
    assert result.inputs.candidate.action == action


def test_stale_candidate_observation_not_rebased_by_current_binding():
    candidate = replace(CANDIDATE, observation=replace(OBS, base_version=41))
    result = resolve(geometries=(explicit(),), candidate=candidate)
    assert result.status == S.STALE
    assert result.inputs.candidate.observation.base_version == 41


def test_both_boundary_positions_and_retained_totals_are_exact():
    for start in range(100, 121):
        removed = FrameRange(start, start + 40)
        result = resolve(geometries=(explicit(removed=removed),))
        candidate = result.candidates[0]
        assert result.status == S.RESOLVED
        assert candidate.removed_range == removed
        assert candidate.retained_leading_frames == start - 100
        assert candidate.retained_trailing_frames == 120 - start
        assert candidate.retained_total_frames == 20


def test_every_anchor_pair_uses_exact_duration_without_nearest_fallback():
    for start in range(100, 161, 5):
        for end in range(100, 161, 5):
            output = resolve(
                (constraint("s", K.CUT_START_ANCHOR, start), constraint("e", K.CUT_END_ANCHOR, end))
            )
            assert (output.status == S.RESOLVED) == (end - start == 40)
            if end - start == 40:
                assert output.candidates[0].removed_range == FrameRange(start, end)


def test_constraints_filter_anchor_path_too():
    anchors = (constraint("s", K.CUT_START_ANCHOR, 110), constraint("e", K.CUT_END_ANCHOR, 150))
    preserve = constraint("p", K.MUST_PRESERVE_RANGE, FrameRange(110, 111))
    allowed = constraint("a", K.ALLOWED_REMOVAL_RANGE, FrameRange(120, 160))
    assert resolve(anchors + (preserve,)).status == S.UNRESOLVED
    assert resolve(anchors + (allowed,)).status == S.UNRESOLVED


def test_producer_recency_or_kind_does_not_rank_alternatives():
    future = replace(PRODUCER, producer_kind=PK.FUTURE_MODEL, producer_version="999")
    output = resolve(
        geometries=(
            explicit("new", CUT, GC.STRONG, future),
            explicit("old", FrameRange(120, 160), GC.WEAK),
        )
    )
    assert output.status == S.REVIEW_REQUIRED


def test_frozen_support_diagnostic_and_defensive_result_collections():
    output = resolve(geometries=(explicit(),))
    candidate = output.candidates[0]
    with pytest.raises(FrozenInstanceError):
        candidate.supports[0].confidence = GC.STRONG
    with pytest.raises(FrozenInstanceError):
        output.diagnostics[0].reason = R.MULTIPLE_GEOMETRIES
    supports = list(candidate.supports)
    copied = replace(candidate, supports=supports)
    candidates = [copied]
    diagnostics = list(output.diagnostics)
    copy = replace(output, candidates=candidates, diagnostics=diagnostics)
    supports.clear()
    candidates.clear()
    diagnostics.clear()
    assert copy == output
    with pytest.raises(ValueError):
        replace(output, status=S.REVIEW_REQUIRED)
    with pytest.raises(ValueError):
        replace(output, candidates=output.candidates * 2)


def test_no_side_effect_or_media_imports():
    import ast
    import inspect

    from davinci_ai_editor import cut_geometry

    tree = ast.parse(inspect.getsource(cut_geometry))
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    allowed = {
        "dataclasses": {"dataclass"},
        "enum": {"Enum"},
        "domain": {"FrameRange"},
        "pause": {"PauseAction", "PauseCandidate"},
        "pause_planning": {"PlanningBinding"},
        "temporal_mapping": {"MappingStatus", "NativeSnapshotRef"},
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module in allowed and {a.name for a in node.names} <= allowed[node.module]
