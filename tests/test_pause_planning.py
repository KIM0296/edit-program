from dataclasses import FrozenInstanceError, replace

import pytest

from davinci_ai_editor import (
    authority,
    dependency,
    evidence,
    native_snapshot,
    pause,
    safety,
    temporal_mapping,
)
from davinci_ai_editor.domain import FrameRange, TimelineObjectId
from davinci_ai_editor.fake_timeline import FakeTimeline
from davinci_ai_editor.native_snapshot import ReadinessStatus
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
from davinci_ai_editor.pause_planning import (
    DependencyReadinessInput,
    GeometryProvenance,
    PauseCutGeometry,
    PausePlanningInput,
    PlanningBinding,
    SnapshotReadinessInput,
    TargetReadinessInput,
    plan_pause,
)
from davinci_ai_editor.pause_planning import (
    DependencyStatus as DS,
)
from davinci_ai_editor.pause_planning import (
    PlanningDisposition as D,
)
from davinci_ai_editor.pause_planning import (
    PlanningReason as R,
)
from davinci_ai_editor.pause_planning import (
    TemporalEditIntent as I,
)
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
PROVENANCE = GeometryProvenance("explicit-source", "v1")
GEOMETRY = PauseCutGeometry("geometry", BINDING, (CUT,), 20, PROVENANCE, "v1")
TARGET = TargetReadinessInput(
    "mapping-assessment", BINDING, MappingStatus.EXACT, "media", FrameRange(0, 200), CUT
)
SNAPSHOT = SnapshotReadinessInput(
    "snapshot-assessment", BINDING, ReadinessStatus.READY, "PAUSE_ANALYSIS/v1"
)
DEPENDENCY = DependencyReadinessInput(
    "dependency-assessment", BINDING, DS.RESOLVED, "geometry", CUT, I.SHORTEN_GAP
)
INPUT = PausePlanningInput(
    "proposal", CANDIDATE, BINDING, SNAP, GEOMETRY, TARGET, SNAPSHOT, DEPENDENCY
)


def result(**changes):
    return plan_pause(replace(INPUT, **changes))


def remove_input():
    candidate = PauseCandidate(
        OBS, PauseAction.REMOVE, Confidence.HIGH, (DecisionReason.EXPLICIT_DEAD_AIR,)
    )
    geometry = replace(GEOMETRY, removed_ranges=(PAUSE,), retained_duration_frames=0)
    return replace(
        INPUT,
        candidate=candidate,
        geometry=geometry,
        target=replace(TARGET, resolved_range=PAUSE),
        dependency=replace(DEPENDENCY, primary_range=PAUSE, temporal_intent=I.CLOSE_GAP),
    )


@pytest.mark.parametrize(
    "action,disposition", [(PauseAction.KEEP, D.NO_OP), (PauseAction.REVIEW, D.REVIEW_ONLY)]
)
def test_keep_review_never_use_geometry_even_when_stale_or_invalid(action, disposition):
    candidate = PauseCandidate(OBS, action, Confidence.LOW, (DecisionReason.INSUFFICIENT_CONTEXT,))
    geometry = replace(
        GEOMETRY, removed_ranges=(FrameRange(0, 1000),), retained_duration_frames=999
    )
    output = result(
        candidate=candidate,
        geometry=geometry,
        current_snapshot=replace(SNAP, state_token="new"),
        target=None,
        snapshot_readiness=None,
        dependency=None,
    )
    assert output.disposition == disposition and output.proposal is None


@pytest.mark.parametrize("data", [INPUT, remove_input()])
def test_explicit_geometry_required_even_with_high_confidence(data):
    output = plan_pause(replace(data, geometry=None))
    assert output.disposition == D.GEOMETRY_REQUIRED and R.GEOMETRY_MISSING in output.reasons
    assert output.proposal is None


def test_valid_tighten_only_primary_temporal_intent():
    output = result()
    assert output.disposition == D.READY_FOR_PREFLIGHT
    assert output.proposal.geometry == GEOMETRY
    assert output.proposal.affected_primary_range == CUT
    assert output.proposal.temporal_intent == I.SHORTEN_GAP
    for obj in (output, output.proposal):
        for field in ("safety_pass", "approved", "ripple", "apply", "verified", "promoted"):
            assert not hasattr(obj, field)


def test_valid_remove_needs_separate_full_pause_geometry():
    output = plan_pause(remove_input())
    assert output.disposition == D.READY_FOR_PREFLIGHT
    assert output.proposal.temporal_intent == I.CLOSE_GAP
    assert output.proposal.geometry.removed_ranges == (PAUSE,)


def test_multirange_unsupported_even_if_total_duration_matches():
    geometry = replace(GEOMETRY, removed_ranges=(FrameRange(100, 120), FrameRange(140, 160)))
    output = result(geometry=geometry)
    assert output.disposition == D.UNSUPPORTED
    assert R.MULTI_RANGE_GEOMETRY_UNSUPPORTED in output.reasons


@pytest.mark.parametrize("removed", [FrameRange(99, 139), FrameRange(121, 161)])
def test_no_clamp_or_shift_outside_by_one_frame(removed):
    geometry = replace(GEOMETRY, removed_ranges=(removed,))
    output = result(geometry=geometry)
    assert output.proposal is None and R.GEOMETRY_INVALID in output.reasons
    assert output.inputs.geometry.removed_ranges == (removed,)


@pytest.mark.parametrize(
    "geometry",
    [
        replace(GEOMETRY, retained_duration_frames=22),
        replace(GEOMETRY, removed_ranges=(FrameRange(110, 148),)),
        replace(GEOMETRY, retained_duration_frames=0),
        replace(GEOMETRY, removed_ranges=()),
    ],
)
def test_geometry_arithmetic_never_repaired(geometry):
    output = result(geometry=geometry)
    assert output.disposition != D.READY_FOR_PREFLIGHT and output.proposal is None
    assert R.GEOMETRY_CONFLICT in output.reasons or R.GEOMETRY_INVALID in output.reasons
    assert output.inputs.candidate.suggested_retained_frames == 20


@pytest.mark.parametrize(
    "field,value", [("timeline_id", "other"), ("timeline_version", 43), ("state_token", "other")]
)
def test_geometry_snapshot_mismatch_stale(field, value):
    geometry = replace(
        GEOMETRY, binding=replace(BINDING, snapshot_ref=replace(SNAP, **{field: value}))
    )
    output = result(geometry=geometry)
    assert output.disposition == D.STALE and output.proposal is None
    assert output.inputs.geometry == geometry


@pytest.mark.parametrize(
    "binding",
    [
        replace(BINDING, object_id=TimelineObjectId("audio", "same-media-other-placement")),
        replace(BINDING, original_pause_range=FrameRange(101, 161)),
        replace(BINDING, candidate_ref="other"),
    ],
)
def test_geometry_candidate_object_pause_binding_mismatch(binding):
    output = result(geometry=replace(GEOMETRY, binding=binding))
    assert output.disposition != D.READY_FOR_PREFLIGHT and output.proposal is None


@pytest.mark.parametrize(
    "ranges,retained",
    [
        ((FrameRange(110, 150),), 0),
        ((FrameRange(99, 160),), 0),
        ((FrameRange(100, 161),), 0),
        ((PAUSE,), 1),
    ],
)
def test_remove_partial_or_speech_expansion_invalid(ranges, retained):
    data = remove_input()
    output = plan_pause(
        replace(
            data,
            geometry=replace(
                data.geometry, removed_ranges=ranges, retained_duration_frames=retained
            ),
        )
    )
    assert output.proposal is None and output.disposition != D.READY_FOR_PREFLIGHT


def test_stale_candidate_and_current_version_no_rebase():
    output = result(current_snapshot=replace(SNAP, timeline_version=45))
    assert output.disposition == D.STALE
    assert output.inputs.candidate.observation.base_version == 42
    old = replace(CANDIDATE, observation=replace(OBS, base_version=41))
    assert result(candidate=old).disposition == D.STALE


@pytest.mark.parametrize("status", list(MappingStatus))
def test_precomputed_target_status_only_exact_can_continue(status):
    output = result(target=replace(TARGET, status=status))
    assert (output.disposition == D.READY_FOR_PREFLIGHT) == (status == MappingStatus.EXACT)
    if status == MappingStatus.STALE:
        assert output.disposition == D.STALE


@pytest.mark.parametrize("status", list(ReadinessStatus))
def test_required_snapshot_status_consumed_not_recomputed(status):
    output = result(snapshot_readiness=replace(SNAPSHOT, status=status))
    assert (output.disposition == D.READY_FOR_PREFLIGHT) == (status == ReadinessStatus.READY)
    if status == ReadinessStatus.STALE:
        assert output.disposition == D.STALE


@pytest.mark.parametrize("status", [DS.UNRESOLVED, DS.CONFLICT, DS.UNSUPPORTED])
def test_dependencies_block_without_cascade(status):
    output = result(dependency=replace(DEPENDENCY, status=status))
    assert output.proposal is None
    assert output.disposition in (D.DEPENDENCY_RESOLUTION_REQUIRED, D.UNSUPPORTED)


@pytest.mark.parametrize("field", ["target", "snapshot_readiness", "dependency"])
def test_missing_precomputed_assessment_blocks(field):
    output = result(**{field: None})
    assert output.disposition != D.READY_FOR_PREFLIGHT and output.proposal is None


@pytest.mark.parametrize("field", ["target", "snapshot_readiness", "dependency"])
def test_each_assessment_must_share_snapshot_token(field):
    fact = getattr(INPUT, field)
    fact = replace(fact, binding=replace(BINDING, snapshot_ref=replace(SNAP, state_token="old")))
    assert result(**{field: fact}).disposition == D.STALE


def test_full_pause_exact_not_reused_for_different_cut_boundaries():
    output = result(target=replace(TARGET, resolved_range=PAUSE))
    assert output.disposition == D.TARGET_RESOLUTION_REQUIRED and output.proposal is None


def test_cross_placement_pause_not_accepted_even_if_target_claims_exact():
    output = result(target=replace(TARGET, placement_range=FrameRange(100, 130)))
    assert output.disposition == D.UNSUPPORTED
    assert R.CROSS_PLACEMENT_UNSUPPORTED in output.reasons


@pytest.mark.parametrize(
    "field,value",
    [("geometry_ref", "other"), ("primary_range", PAUSE), ("temporal_intent", I.CLOSE_GAP)],
)
def test_dependency_assessment_binds_exact_geometry_and_intent(field, value):
    output = result(dependency=replace(DEPENDENCY, **{field: value}))
    assert output.disposition == D.DEPENDENCY_RESOLUTION_REQUIRED


def test_deterministic_and_defensive_copy():
    ranges = [CUT]
    geometry = replace(GEOMETRY, removed_ranges=ranges)
    ranges.clear()
    assert geometry == GEOMETRY and result(geometry=geometry) == result()


@pytest.mark.parametrize(
    "value,field",
    [
        (BINDING, "candidate_ref"),
        (PROVENANCE, "source_ref"),
        (GEOMETRY, "removed_ranges"),
        (TARGET, "status"),
        (SNAPSHOT, "status"),
        (DEPENDENCY, "status"),
        (INPUT, "geometry"),
        (result(), "disposition"),
        (result().proposal, "temporal_intent"),
    ],
)
def test_frozen_nested_values(value, field):
    with pytest.raises(FrozenInstanceError):
        setattr(value, field, None)


def test_no_layer_invocation(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Planner crossed a pure input-consumption boundary")

    for module, name in [
        (temporal_mapping, "map_range"),
        (native_snapshot, "evaluate_readiness"),
        (pause, "classify_pause"),
        (safety, "preflight"),
        (authority, "transition"),
        (evidence, "prepare_observation"),
    ]:
        monkeypatch.setattr(module, name, forbidden)
    for name in dir(dependency):
        if name.startswith("compile"):
            monkeypatch.setattr(dependency, name, forbidden)
    monkeypatch.setattr(FakeTimeline, "apply", forbidden)
    assert result().disposition == D.READY_FOR_PREFLIGHT


@pytest.mark.parametrize("confidence", [Confidence.MEDIUM, Confidence.HIGH])
def test_confidence_does_not_skip_any_required_input(confidence):
    candidate = replace(CANDIDATE, confidence=confidence)
    for field in ("geometry", "target", "snapshot_readiness", "dependency"):
        output = result(candidate=candidate, **{field: None})
        assert output.proposal is None and output.disposition != D.READY_FOR_PREFLIGHT


@pytest.mark.parametrize(
    "field,value",
    [
        ("retained_duration_frames", -1),
        ("retained_duration_frames", True),
        ("retained_duration_frames", 20.0),
        ("removed_ranges", ((110, 150),)),
        ("provenance", {}),
        ("geometry_ref", ""),
    ],
)
def test_malformed_geometry_rejected_without_normalization(field, value):
    with pytest.raises((TypeError, ValueError)):
        replace(GEOMETRY, **{field: value})


@pytest.mark.parametrize("retained", [0, 60, -1])
def test_invalid_tighten_candidate_still_rejected_by_existing_domain(retained):
    with pytest.raises(ValueError):
        replace(CANDIDATE, suggested_retained_frames=retained)


@pytest.mark.parametrize("field", ["target", "snapshot_readiness", "dependency"])
def test_same_media_does_not_rebind_other_placement_readiness(field):
    fact = getattr(INPUT, field)
    other = replace(BINDING, object_id=TimelineObjectId("audio", "different-placement"))
    output = result(**{field: replace(fact, binding=other)})
    assert output.proposal is None and output.disposition == D.UNSUPPORTED


@pytest.mark.parametrize(
    "field,value",
    [("object_id", TimelineObjectId("video", "other")), ("pause_range", FrameRange(101, 161))],
)
def test_candidate_observation_matches_planning_binding(field, value):
    candidate = replace(CANDIDATE, observation=replace(OBS, **{field: value}))
    assert result(candidate=candidate).disposition == D.TARGET_RESOLUTION_REQUIRED


def test_changed_geometry_artifact_does_not_reuse_resolved_dependency():
    geometry = replace(GEOMETRY, geometry_ref="refreshed")
    assert result(geometry=geometry).disposition == D.DEPENDENCY_RESOLUTION_REQUIRED
    assert INPUT.geometry == GEOMETRY


def test_unsupported_contracts_fail_closed():
    assert result(planning_contract_version="v2").disposition == D.UNSUPPORTED
    assert (
        result(geometry=replace(GEOMETRY, geometry_contract_version="v2")).disposition
        == D.UNSUPPORTED
    )


def test_multiple_failures_keep_all_reasons_with_stale_precedence():
    output = result(
        current_snapshot=replace(SNAP, state_token="new"),
        geometry=None,
        dependency=None,
        target=replace(TARGET, status=MappingStatus.NON_INTEGRAL),
    )
    assert output.disposition == D.STALE
    assert {
        R.STALE_CANDIDATE,
        R.GEOMETRY_MISSING,
        R.TARGET_NOT_EXACT,
        R.DEPENDENCY_UNRESOLVED,
    } <= set(output.reasons)


def test_supplied_primary_range_not_moved_to_leading_trailing_or_center():
    # Several valid positions are supplied explicitly; planner preserves each verbatim.
    for start in (100, 101, 107, 119, 120):
        cut = FrameRange(start, start + 40)
        geometry = replace(GEOMETRY, removed_ranges=(cut,))
        output = result(
            geometry=geometry,
            target=replace(TARGET, resolved_range=cut),
            dependency=replace(DEPENDENCY, primary_range=cut),
        )
        assert output.disposition == D.READY_FOR_PREFLIGHT
        assert output.proposal.affected_primary_range == cut


def test_result_defensive_reasons_and_no_proposal_on_failure():
    ready = result()
    reasons = list(ready.reasons)
    copied = replace(ready, reasons=reasons)
    reasons.clear()
    assert copied == ready
    with pytest.raises(ValueError):
        replace(ready, disposition=D.GEOMETRY_REQUIRED)
    with pytest.raises(ValueError):
        replace(ready, proposal=None)


def test_no_resolver_adapter_or_execution_imports():
    import ast
    import inspect

    from davinci_ai_editor import pause_planning

    tree = ast.parse(inspect.getsource(pause_planning))
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    allowed = {
        "dataclasses": {"dataclass"},
        "enum": {"Enum"},
        "domain": {"FrameRange", "MediaId", "TimelineObjectId"},
        "native_snapshot": {"ReadinessStatus"},
        "pause": {"PauseAction", "PauseCandidate"},
        "temporal_mapping": {"MappingStatus", "NativeSnapshotRef"},
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module in allowed
            assert {a.name for a in node.names} <= allowed[node.module]
