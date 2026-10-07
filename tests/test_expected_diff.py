from dataclasses import FrozenInstanceError, replace

import pytest

from davinci_ai_editor.domain import FrameRange, TimelineObjectId
from davinci_ai_editor.expected_diff import (
    ActualDiff,
    ActualObjectObservation,
    CompilerProvenance,
    DiffBinding,
    DiffCompilationInput,
    DisplacementParticipant,
    DisplacementParticipationAssessment,
    PlacementState,
    PostRelationStatus,
    PreservationScope,
    compile_expected_diff,
    verify_diff,
)
from davinci_ai_editor.expected_diff import (
    DiffVerificationStatus as V,
)
from davinci_ai_editor.expected_diff import (
    ExpectedDiffStatus as S,
)
from davinci_ai_editor.expected_diff import (
    ParticipationStatus as P,
)
from davinci_ai_editor.pause_planning import (
    GeometryProvenance,
    PauseCutGeometry,
    PauseEditProposal,
    PlanningBinding,
    TemporalEditIntent,
)
from davinci_ai_editor.temporal_mapping import MappingKind, NativeSnapshotRef

BASE = NativeSnapshotRef("main", 42, "base-state")
POST = NativeSnapshotRef("main", 43, "post-state")
PRIMARY_ID = TimelineObjectId("audio", "dialogue")
BINDING = PlanningBinding("candidate", BASE, PRIMARY_ID, FrameRange(100, 160))
CUT = FrameRange(110, 150)
GEOMETRY = PauseCutGeometry(
    "geometry", BINDING, (CUT,), 20, GeometryProvenance("caller", "v1"), "v1"
)
PROPOSAL = PauseEditProposal(
    "proposal",
    BINDING,
    TemporalEditIntent.SHORTEN_GAP,
    GEOMETRY,
    CUT,
    "target",
    "snapshot",
    "dependency",
)
DIFF_BINDING = DiffBinding("proposal", BINDING, "geometry", CUT)
PRIMARY = PlacementState(
    PRIMARY_ID, "media", "audio", FrameRange(0, 200), FrameRange(0, 200), MappingKind.IDENTITY_1X
)
A = PlacementState(
    TimelineObjectId("audio", "a"),
    "repeated-media",
    "audio",
    FrameRange(200, 260),
    FrameRange(10, 70),
    MappingKind.IDENTITY_1X,
)
B = PlacementState(
    TimelineObjectId("video", "b"),
    "repeated-media",
    "video",
    FrameRange(210, 290),
    FrameRange(10, 90),
    MappingKind.IDENTITY_1X,
)
UNCHANGED = PlacementState(
    TimelineObjectId("audio", "unlisted"),
    "media",
    "audio",
    FrameRange(300, 400),
    FrameRange(0, 100),
    MappingKind.IDENTITY_1X,
)
PA = DisplacementParticipant(A, -40, "audio")
PB = DisplacementParticipant(B, -40, "video")
ASSESSMENT = DisplacementParticipationAssessment(
    "assessment", DIFF_BINDING, P.RESOLVED, (PA, PB), True
)
SCOPE = PreservationScope("scope", DIFF_BINDING, (PRIMARY, A, B, UNCHANGED))
INPUT = DiffCompilationInput(
    "diff", PROPOSAL, ASSESSMENT, SCOPE, BASE, CompilerProvenance("pure-diff", "v1")
)


def compiled(**changes):
    return compile_expected_diff(replace(INPUT, **changes))


def expected():
    result = compiled()
    assert result.status == S.READY_FOR_PREFLIGHT
    assert result.expected_diff is not None
    return result.expected_diff


def actual(diff=None):
    diff = expected() if diff is None else diff
    observations = [
        ActualObjectObservation(d.before.object_id, d.before, d.after) for d in diff.displacements
    ]
    observations.append(ActualObjectObservation(UNCHANGED.object_id, UNCHANGED, UNCHANGED))
    return ActualDiff(
        "actual",
        diff.expected_diff_ref,
        BASE,
        POST,
        diff.primary_changes,
        tuple(observations),
        PostRelationStatus.VERIFIED,
        "post-relation-evidence",
        "identity-evidence",
    )


def verify(value):
    return verify_diff(expected(), value, POST)


def test_exact_effects_and_unchanged_scope():
    result = expected()
    assert result.primary_changes[0].removed_timeline_range == CUT
    assert result.primary_changes[0].before == PRIMARY
    assert {d.before.object_id for d in result.displacements} == {A.object_id, B.object_id}
    assert result.unchanged_object_ids == (UNCHANGED.object_id,)
    assert result.expected_topology_changes == ()
    for d in result.displacements:
        assert d.delta_frames == -40
        assert d.after.timeline_range == FrameRange(
            d.before.timeline_range.start - 40, d.before.timeline_range.end - 40
        )
        assert replace(d.after, timeline_range=d.before.timeline_range) == d.before
    assert verify(actual()).status == V.MATCH


@pytest.mark.parametrize(
    "status,want",
    [
        (P.REVIEW_REQUIRED, S.REVIEW_REQUIRED),
        (P.CONFLICT, S.REVIEW_REQUIRED),
        (P.UNSUPPORTED, S.UNSUPPORTED),
        (P.STALE, S.STALE),
    ],
)
def test_only_resolved_participation(status, want):
    result = compiled(participation=replace(ASSESSMENT, status=status))
    assert result.status == want and result.expected_diff is None


def test_no_implicit_participant_selection():
    assessment = replace(ASSESSMENT, participants=(PA,))
    diff = compiled(participation=assessment).expected_diff
    assert diff is not None and len(diff.displacements) == 1
    assert set(diff.unchanged_object_ids) == {B.object_id, UNCHANGED.object_id}


@pytest.mark.parametrize("delta", [-39, -20, 0, -41])
def test_nonuniform_no_gap_guess(delta):
    result = compiled(
        participation=replace(ASSESSMENT, participants=(replace(PA, delta_frames=delta), PB))
    )
    assert result.status == S.UNSUPPORTED
    assert result.expected_diff is None


def test_gap_consequence_requires_explicit_proof():
    assert (
        compiled(participation=replace(ASSESSMENT, uniform_consequence_verified=False)).status
        == S.REVIEW_REQUIRED
    )


@pytest.mark.parametrize("span", [FrameRange(100, 200), FrameRange(120, 200), FrameRange(0, 100)])
def test_not_fully_downstream_no_trim_move(span):
    state = replace(A, timeline_range=span)
    scope = replace(SCOPE, objects=(PRIMARY, state, B, UNCHANGED))
    result = compiled(
        scope=scope, participation=replace(ASSESSMENT, participants=(replace(PA, before=state), PB))
    )
    assert result.status == S.UNSUPPORTED


def test_cross_track_rejected():
    assert (
        compiled(
            participation=replace(
                ASSESSMENT, participants=(replace(PA, after_track_id="video"), PB)
            )
        ).status
        == S.UNSUPPORTED
    )


@pytest.mark.parametrize(
    "kind",
    [MappingKind.REVERSE, MappingKind.FREEZE, MappingKind.VARIABLE_RETIME, MappingKind.UNKNOWN],
)
def test_unsupported_retime(kind):
    state = replace(A, retime=kind)
    assert (
        compiled(
            scope=replace(SCOPE, objects=(PRIMARY, state, B, UNCHANGED)),
            participation=replace(ASSESSMENT, participants=(replace(PA, before=state), PB)),
        ).status
        == S.UNSUPPORTED
    )


def test_omitted_scope_and_known_impacts():
    assert compiled(scope=replace(SCOPE, objects=(PRIMARY, A, UNCHANGED))).status == S.INCOMPLETE
    absent = TimelineObjectId("video", "not-scoped")
    assert (
        compiled(participation=replace(ASSESSMENT, known_impacted_ids=(absent,))).status
        == S.INCOMPLETE
    )


def test_protected_risk_is_not_safety():
    diff = compiled(
        participation=replace(ASSESSMENT, protected_risk_ids=(A.object_id,))
    ).expected_diff
    assert diff is not None
    assert not any(hasattr(diff, name) for name in ("safe", "approved", "apply", "safety_pass"))


@pytest.mark.parametrize(
    "snapshot",
    [
        NativeSnapshotRef("other", 42, "base-state"),
        NativeSnapshotRef("main", 43, "base-state"),
        NativeSnapshotRef("main", 42, "drift"),
    ],
)
def test_current_mismatch_stale_no_rebase(snapshot):
    result = compiled(current_snapshot=snapshot)
    assert result.status == S.STALE and result.inputs.proposal == PROPOSAL


def test_scope_or_assessment_binding_stale():
    wrong = replace(DIFF_BINDING, proposal_ref="other")
    assert compiled(scope=replace(SCOPE, binding=wrong)).status == S.STALE
    assert compiled(participation=replace(ASSESSMENT, binding=wrong)).status == S.STALE


@pytest.mark.parametrize("remove_primary", [True, False])
def test_missing_expected_change_mismatch(remove_primary):
    a = actual()
    a = (
        replace(a, primary_changes=())
        if remove_primary
        else replace(a, observations=tuple(o for o in a.observations if o.object_id != A.object_id))
    )
    assert verify(a).status == V.MISMATCH


def test_missing_unchanged_observation_unverified():
    a = actual()
    assert (
        verify(
            replace(
                a,
                observations=tuple(o for o in a.observations if o.object_id != UNCHANGED.object_id),
            )
        ).status
        == V.UNVERIFIED
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("timeline_range", FrameRange(161, 221)),
        ("timeline_range", FrameRange(160, 221)),
        ("media_id", "changed"),
        ("source_range", FrameRange(11, 71)),
        ("track_id", "video"),
        ("object_id", TimelineObjectId("audio", "different")),
    ],
)
def test_mutated_displacement_mismatch(field, value):
    a = actual()
    obs = next(o for o in a.observations if o.object_id == A.object_id)
    changed = replace(obs, after=replace(obs.after, **{field: value}))
    assert (
        verify(
            replace(a, observations=tuple(changed if o == obs else o for o in a.observations))
        ).status
        == V.MISMATCH
    )


def test_wrong_primary_range_mismatch():
    a = actual()
    effect = replace(a.primary_changes[0], removed_timeline_range=FrameRange(111, 150))
    assert verify(replace(a, primary_changes=(effect,))).status == V.MISMATCH


def test_extra_changed_object_in_scope_mismatch():
    a = actual()
    obs = ActualObjectObservation(
        UNCHANGED.object_id, UNCHANGED, replace(UNCHANGED, timeline_range=FrameRange(260, 360))
    )
    assert (
        verify(
            replace(
                a,
                observations=tuple(
                    obs if o.object_id == UNCHANGED.object_id else o for o in a.observations
                ),
            )
        ).status
        == V.MISMATCH
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"identity_evidence_ref": None},
        {"post_relation_evidence_ref": None},
        {"post_relation_status": PostRelationStatus.UNVERIFIED},
    ],
)
def test_insufficient_identity_or_relation_unverified(changes):
    assert verify(replace(actual(), **changes)).status == V.UNVERIFIED


def test_stale_post_relation():
    assert (
        verify(replace(actual(), post_relation_status=PostRelationStatus.STALE)).status == V.STALE
    )
    assert (
        verify_diff(expected(), actual(), NativeSnapshotRef("main", 44, "human")).status == V.STALE
    )
    assert verify(replace(actual(), base_snapshot=POST)).status == V.STALE


def test_topology_mutation_mismatch():
    assert verify(replace(actual(), topology_change_refs=("track-reorder",))).status == V.MISMATCH


def test_deterministic_defensive_copies():
    participants = [PB, PA]
    objects = [UNCHANGED, B, A, PRIMARY]
    i = replace(
        INPUT,
        participation=replace(ASSESSMENT, participants=participants),
        scope=replace(SCOPE, objects=objects),
    )
    participants.clear()
    objects.clear()
    assert compile_expected_diff(i) == compiled()
    a = actual()
    assert verify(replace(a, observations=tuple(reversed(a.observations)))) == verify(a)


def test_frozen_nested_values():
    diff = expected()
    a = actual()
    for value in (
        INPUT,
        ASSESSMENT,
        PA,
        A,
        SCOPE,
        DIFF_BINDING,
        INPUT.provenance,
        diff,
        diff.primary_changes[0],
        diff.displacements[0],
        a,
        a.observations[0],
        verify(a),
    ):
        with pytest.raises(FrozenInstanceError):
            value.unexpected = True


def test_no_other_layer_calls(monkeypatch):
    from davinci_ai_editor import (
        authority,
        cut_geometry,
        dependency,
        native_snapshot,
        pause,
        pause_planning,
        safety,
        temporal_mapping,
    )
    from davinci_ai_editor.fake_timeline import FakeTimeline

    def forbidden(*args, **kwargs):
        pytest.fail("unexpected layer execution")

    for module, name in [
        (temporal_mapping, "map_range"),
        (native_snapshot, "evaluate_readiness"),
        (pause_planning, "plan_pause"),
        (cut_geometry, "resolve_geometry"),
        (pause, "classify_pause"),
        (safety, "preflight"),
        (authority, "transition"),
        (FakeTimeline, "apply"),
    ]:
        monkeypatch.setattr(module, name, forbidden)
    for name in vars(dependency):
        if name.startswith("compile"):
            monkeypatch.setattr(dependency, name, forbidden)
    assert verify(actual()).status == V.MATCH


@pytest.mark.parametrize(
    "field,value",
    [
        ("proposal_ref", "wrong"),
        ("geometry_ref", "wrong"),
        ("primary_range", FrameRange(111, 151)),
        ("planning_binding", replace(BINDING, snapshot_ref=POST)),
    ],
)
def test_all_bound_artifacts_must_agree(field, value):
    wrong = replace(DIFF_BINDING, **{field: value})
    for changes in (
        {"participation": replace(ASSESSMENT, binding=wrong)},
        {"scope": replace(SCOPE, binding=wrong)},
    ):
        result = compiled(**changes)
        assert result.status == S.STALE and result.expected_diff is None
        assert result.inputs.proposal.affected_primary_range == CUT


def test_primary_outside_placement_not_repaired():
    primary = replace(PRIMARY, timeline_range=FrameRange(120, 200))
    result = compiled(scope=replace(SCOPE, objects=(primary, A, B, UNCHANGED)))
    assert result.status == S.UNSUPPORTED
    assert result.inputs.proposal.affected_primary_range == CUT


def test_remove_proposal_exact_copy():
    pause = BINDING.original_pause_range
    geometry = replace(GEOMETRY, removed_ranges=(pause,), retained_duration_frames=0)
    proposal = replace(
        PROPOSAL,
        geometry=geometry,
        affected_primary_range=pause,
        temporal_intent=TemporalEditIntent.CLOSE_GAP,
    )
    binding = replace(DIFF_BINDING, primary_range=pause)
    assessment = replace(ASSESSMENT, binding=binding, participants=(replace(PA, delta_frames=-60),))
    result = compiled(
        proposal=proposal, participation=assessment, scope=replace(SCOPE, binding=binding)
    )
    assert result.expected_diff.primary_changes[0].removed_timeline_range == pause
    assert result.expected_diff.displacements[0].delta_frames == -60


def test_empty_resolved_set_does_not_discover_downstream_objects():
    result = compiled(participation=replace(ASSESSMENT, participants=())).expected_diff
    assert result is not None and result.displacements == ()
    assert set(result.unchanged_object_ids) == {A.object_id, B.object_id, UNCHANGED.object_id}


def test_scope_before_metadata_conflict():
    result = compiled(
        participation=replace(
            ASSESSMENT, participants=(replace(PA, before=replace(A, media_id="wrong")), PB)
        )
    )
    assert result.status == S.REVIEW_REQUIRED and result.expected_diff is None


def test_primary_is_never_its_own_displacement_participant():
    result = compiled(
        participation=replace(
            ASSESSMENT, participants=(DisplacementParticipant(PRIMARY, -40, "audio"),)
        )
    )
    assert result.status == S.UNSUPPORTED


def test_gap_and_j_l_cut_boundaries_stay_independent():
    # Arbitrarily large supplied downstream gaps do not become absorption rules.
    b = replace(B, timeline_range=FrameRange(1000, 1080))
    result = compiled(
        scope=replace(SCOPE, objects=(PRIMARY, A, b, UNCHANGED)),
        participation=replace(ASSESSMENT, participants=(PA, replace(PB, before=b))),
    ).expected_diff
    assert result is not None
    moves = {m.before.object_id: m for m in result.displacements}
    assert moves[b.object_id].after.timeline_range == FrameRange(960, 1040)
    assert moves[A.object_id].after.timeline_range == FrameRange(160, 220)
    assert moves[b.object_id].after.source_range == B.source_range


def test_affine_translation_preserves_source_without_mapping():
    a = replace(A, retime=MappingKind.AFFINE_FORWARD, source_range=FrameRange(10, 130))
    result = compiled(
        scope=replace(SCOPE, objects=(PRIMARY, a, B, UNCHANGED)),
        participation=replace(ASSESSMENT, participants=(replace(PA, before=a), PB)),
    ).expected_diff
    assert result is not None
    m = next(m for m in result.displacements if m.before.object_id == a.object_id)
    assert m.after.source_range == FrameRange(10, 130)
    assert m.after.timeline_range.duration == 60


@pytest.mark.parametrize("delta", [True, 1.0, "-40"])
def test_no_numeric_coercion(delta):
    with pytest.raises(TypeError):
        replace(PA, delta_frames=delta)


def test_unknown_retime_not_identity_default():
    state = PlacementState(A.object_id, A.media_id, A.track_id, A.timeline_range, A.source_range)
    assert state.retime == MappingKind.UNKNOWN
    assert (
        compiled(
            scope=replace(SCOPE, objects=(PRIMARY, state, B, UNCHANGED)),
            participation=replace(ASSESSMENT, participants=(replace(PA, before=state), PB)),
        ).status
        == S.UNSUPPORTED
    )


@pytest.mark.parametrize(
    "field,value", [("status", "RESOLVED"), ("uniform_consequence_verified", 1)]
)
def test_typed_assessment(field, value):
    with pytest.raises(TypeError):
        replace(ASSESSMENT, **{field: value})


def test_duplicate_placement_cannot_hide_nonuniform_or_ambiguous_fragments():
    with pytest.raises(ValueError):
        replace(ASSESSMENT, participants=(PA, replace(PA, delta_frames=-39)))
    with pytest.raises(ValueError):
        replace(SCOPE, objects=(A, replace(A, timeline_range=FrameRange(300, 360))))
    a = actual()
    with pytest.raises(ValueError):
        replace(a, observations=(*a.observations, a.observations[0]))


def test_output_constructor_cannot_invent_ready_or_change_geometry():
    from davinci_ai_editor.expected_diff import DiffCompilationResult, ExpectedDiffReason

    diff = expected()
    with pytest.raises(ValueError):
        replace(
            diff,
            primary_changes=(
                replace(diff.primary_changes[0], removed_timeline_range=FrameRange(111, 151)),
            ),
        )
    with pytest.raises(ValueError):
        replace(diff, displacements=())
    with pytest.raises(ValueError):
        replace(diff, inputs=replace(INPUT, current_snapshot=POST))
    with pytest.raises(ValueError):
        replace(diff, expected_topology_changes=("new-track",))
    with pytest.raises(ValueError):
        DiffCompilationResult(
            INPUT, S.READY_FOR_PREFLIGHT, (ExpectedDiffReason.READY_FOR_PREFLIGHT,)
        )


@pytest.mark.parametrize(
    "mutation",
    [
        {"media_id": "wrong"},
        {"source_range": FrameRange(11, 71)},
        {"track_id": "video"},
        {"timeline_range": FrameRange(159, 220)},
    ],
)
def test_translation_value_requires_pure_preservation(mutation):
    move = next(d for d in expected().displacements if d.before.object_id == A.object_id)
    with pytest.raises(ValueError):
        replace(move, after=replace(move.after, **mutation))


def test_unknown_contract_nonready():
    assert (
        compiled(provenance=replace(INPUT.provenance, contract_version="v2")).status
        == S.UNSUPPORTED
    )


@pytest.mark.parametrize("kind", ["added", "deleted", "before", "retime"])
def test_actual_preservation_failures(kind):
    a = actual()
    obs = next(o for o in a.observations if o.object_id == A.object_id)
    if kind == "added":
        changed = replace(obs, before=None)
    elif kind == "deleted":
        changed = replace(obs, after=None)
    elif kind == "before":
        changed = replace(obs, before=replace(A, media_id="other-base"))
    else:
        changed = replace(obs, after=replace(obs.after, retime=MappingKind.REVERSE))
    assert (
        verify(
            replace(a, observations=tuple(changed if o == obs else o for o in a.observations))
        ).status
        == V.MISMATCH
    )


def test_actual_extra_primary_and_outside_scope_change():
    a = actual()
    extra = replace(a.primary_changes[0], change_id="unexpected", before=UNCHANGED)
    assert verify(replace(a, primary_changes=(*a.primary_changes, extra))).status == V.MISMATCH
    before = replace(UNCHANGED, object_id=TimelineObjectId("audio", "outside"))
    obs = ActualObjectObservation(
        before.object_id, before, replace(before, timeline_range=FrameRange(301, 401))
    )
    assert verify(replace(a, observations=(*a.observations, obs))).status == V.MISMATCH


def test_actual_primary_has_no_hidden_secondary_change_class():
    a = actual()
    extra = ActualObjectObservation(PRIMARY_ID, PRIMARY, replace(PRIMARY, media_id="replaced"))
    assert verify(replace(a, observations=(*a.observations, extra))).status == V.MISMATCH


def test_fail_closed_precedence_preserves_reasons():
    from davinci_ai_editor.expected_diff import DiffVerificationReason as R

    a = replace(actual(), primary_changes=(), identity_evidence_ref=None)
    result = verify(a)
    assert result.status == V.UNVERIFIED
    assert {R.MISSING_EXPECTED_CHANGE, R.IDENTITY_UNVERIFIABLE} <= set(result.reasons)
    result = verify(replace(a, post_relation_status=PostRelationStatus.STALE))
    assert result.status == V.STALE and R.POST_SNAPSHOT_STALE in result.reasons


def test_actual_snapshot_binding_and_post_timeline_mismatch():
    assert verify(replace(actual(), expected_diff_ref="other")).status == V.STALE
    other = NativeSnapshotRef("other", 43, "post-state")
    assert verify_diff(expected(), replace(actual(), post_snapshot=other), other).status == V.STALE


def test_actual_collection_copy_and_result_copy():
    a = actual()
    observations = list(a.observations)
    effects = list(a.primary_changes)
    value = replace(a, observations=observations, primary_changes=effects)
    observations.clear()
    effects.clear()
    assert value == a
    r = verify(a)
    reasons = list(r.reasons)
    copied = replace(r, reasons=reasons)
    reasons.clear()
    assert copied == r


def test_no_runtime_import_dependencies():
    import ast
    from pathlib import Path

    from davinci_ai_editor import expected_diff

    tree = ast.parse(Path(expected_diff.__file__).read_text(encoding="utf-8-sig"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports <= {
        "dataclasses",
        "enum",
        "typing",
        "domain",
        "pause_planning",
        "temporal_mapping",
    }
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
