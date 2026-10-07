from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from davinci_ai_editor.domain import FrameRange, TimelineObjectId
from davinci_ai_editor.expected_diff import (
    CompilerProvenance,
    DiffBinding,
    DiffCompilationInput,
    DiffCompilationResult,
    DisplacementParticipant,
    DisplacementParticipationAssessment,
    ExpectedDiffReason,
    ExpectedDiffStatus,
    ParticipationStatus,
    PlacementState,
    PreservationScope,
    compile_expected_diff,
)
from davinci_ai_editor.native_snapshot import ObservedValue
from davinci_ai_editor.pause_planning import (
    GeometryProvenance,
    PauseCutGeometry,
    PauseEditProposal,
    PlanningBinding,
    TemporalEditIntent,
)
from davinci_ai_editor.safety_preflight import (
    PAUSE_DESTRUCTIVE_PREFLIGHT_V1,
    AssessmentState,
    CurrentSafetyEvidence,
    ObjectSafetyEvidence,
    PreservationProof,
    PreservationProofKind,
    ProofOutcome,
    ProtectedRangeRecord,
    ProtectionContext,
    SafetyPreflightInput,
    SafetySubject,
    StructureObservation,
    TrackLockEvidence,
    preflight,
)
from davinci_ai_editor.safety_preflight import (
    PreflightStatus as S,
)
from davinci_ai_editor.safety_preflight import (
    SafetyCheckKind as K,
)
from davinci_ai_editor.safety_preflight import (
    SafetyCheckOutcome as O,
)
from davinci_ai_editor.safety_preflight import (
    SafetyVerdict as V,
)
from davinci_ai_editor.safety_preflight import (
    StructureState as F,
)
from davinci_ai_editor.temporal_mapping import MappingKind, NativeSnapshotRef

BASE = NativeSnapshotRef("main", 42, "base")
PRIMARY_ID = TimelineObjectId("audio", "dialogue")
A_ID = TimelineObjectId("audio", "following")
U_ID = TimelineObjectId("audio", "unchanged")
CUT = FrameRange(110, 150)
BINDING = PlanningBinding("candidate", BASE, PRIMARY_ID, FrameRange(100, 160))
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
DB = DiffBinding("proposal", BINDING, "geometry", CUT)
PRIMARY = PlacementState(
    PRIMARY_ID, "media", "audio", FrameRange(0, 200), FrameRange(0, 200), MappingKind.IDENTITY_1X
)
A = PlacementState(
    A_ID, "media", "audio", FrameRange(200, 260), FrameRange(10, 70), MappingKind.IDENTITY_1X
)
UNCHANGED = PlacementState(
    U_ID, "media", "audio", FrameRange(300, 400), FrameRange(0, 100), MappingKind.IDENTITY_1X
)
SCOPE = PreservationScope("scope", DB, (PRIMARY, A, UNCHANGED))
ASSESSMENT = DisplacementParticipationAssessment(
    "participation",
    DB,
    ParticipationStatus.RESOLVED,
    (DisplacementParticipant(A, -40, "audio"),),
    True,
)
DIFF_INPUT = DiffCompilationInput(
    "diff", PROPOSAL, ASSESSMENT, SCOPE, BASE, CompilerProvenance("compiler", "v1")
)
COMPILED = compile_expected_diff(DIFF_INPUT)
PS = SafetySubject(PRIMARY_ID, CUT)
AS = SafetySubject(A_ID, A.timeline_range)
ABSENT = StructureObservation(F.KNOWN_ABSENT)
PE = ObjectSafetyEvidence(PS, MappingKind.IDENTITY_1X, ObservedValue.TRUE, ABSENT, ABSENT, ABSENT)
AE = replace(PE, subject=AS)
EVIDENCE = CurrentSafetyEvidence(
    "evidence",
    "diff",
    BASE,
    (TrackLockEvidence("audio", ObservedValue.FALSE),),
    (PE, AE),
    AssessmentState.RESOLVED,
    "relationship-assessment",
    AssessmentState.RESOLVED,
    "dependency-assessment",
)
PROTECTION = ProtectionContext("protection", BASE, True, (), "v1")
INPUT = SafetyPreflightInput(COMPILED, PROPOSAL, BASE, PROTECTION, EVIDENCE)


def result(**changes):
    return preflight(replace(INPUT, **changes))


def check(value, kind):
    return next(c for c in value.checks if c.kind == kind)


def structure_result(field, state, proofs=(), proof_ref=None):
    pe = replace(PE, **{field: StructureObservation(state, proof_ref)})
    return result(evidence=replace(EVIDENCE, objects=(pe, AE)), proofs=proofs)


def proof(kind=PreservationProofKind.TRANSITION, **changes):
    p = PreservationProof(
        "proof",
        kind,
        BASE,
        "diff",
        PS,
        "v1",
        ProofOutcome.PRESERVATION_PROVEN,
        "synthetic-caller",
        "1",
        ("evidence-ref",),
    )
    return replace(p, **changes)


def corrupt_diff(field, value):
    compiled = deepcopy(COMPILED)
    object.__setattr__(compiled.expected_diff, field, value)
    return compiled


def test_profile_exact_and_complete_pass():
    names = {
        "BASE_FRESHNESS",
        "EXPECTED_DIFF_INTEGRITY",
        "PROTECTION_CONTEXT",
        "PROTECTED_RANGE",
        "TRACK_LOCK",
        "RELATIONSHIP_INTEGRITY",
        "TEMPORAL_DEPENDENCY_COVERAGE",
        "RETIME_SUPPORT",
        "MEDIA_IDENTITY_PRESERVATION",
        "SOURCE_RANGE_PRESERVATION",
        "DURATION_PRESERVATION",
        "TRACK_MEMBERSHIP_PRESERVATION",
        "TOPOLOGY_PRESERVATION",
        "TRANSITION_INTEGRITY",
        "EFFECT_EDITABILITY",
        "KEYFRAME_EDITABILITY",
        "PRESERVATION_SCOPE",
    }
    assert {k.value for k in PAUSE_DESTRUCTIVE_PREFLIGHT_V1.required_checks} == names
    assert len(PAUSE_DESTRUCTIVE_PREFLIGHT_V1.required_checks) == 17
    r = result()
    assert r.status == S.EVALUATED and r.verdict == V.PASS
    assert len(r.checks) == 17 and all(c.outcome == O.PASS for c in r.checks)
    assert r.inputs == INPUT


@pytest.mark.parametrize("status", [S.STALE, S.UNSUPPORTED, S.INCOMPLETE])
def test_non_evaluated_cannot_carry_verdict(status):
    with pytest.raises(ValueError):
        replace(result(), status=status)


def test_evaluated_requires_verdict_and_exact_checks():
    r = result()
    with pytest.raises(ValueError):
        replace(r, verdict=None)
    with pytest.raises(ValueError):
        replace(r, checks=r.checks[:-1])
    with pytest.raises(ValueError):
        replace(r, checks=(*r.checks, r.checks[0]))
    with pytest.raises(ValueError):
        replace(PAUSE_DESTRUCTIVE_PREFLIGHT_V1, required_checks=(K.BASE_FRESHNESS,))


@pytest.mark.parametrize(
    "snapshot",
    [
        NativeSnapshotRef("other", 42, "base"),
        NativeSnapshotRef("main", 43, "base"),
        NativeSnapshotRef("main", 42, "human"),
    ],
)
def test_stale_base(snapshot):
    r = result(current_snapshot=snapshot)
    assert r.status == S.STALE and r.verdict is None


@pytest.mark.parametrize("field", ["protection", "evidence"])
def test_stale_safety_context(field):
    value = PROTECTION if field == "protection" else EVIDENCE
    r = result(**{field: replace(value, snapshot=NativeSnapshotRef("main", 43, "human"))})
    assert r.status == S.STALE and r.verdict is None


@pytest.mark.parametrize(
    "diff_status,want",
    [
        (ExpectedDiffStatus.INCOMPLETE, S.INCOMPLETE),
        (ExpectedDiffStatus.REVIEW_REQUIRED, S.INCOMPLETE),
        (ExpectedDiffStatus.UNSUPPORTED, S.UNSUPPORTED),
        (ExpectedDiffStatus.STALE, S.STALE),
    ],
)
def test_not_ready_diff(diff_status, want):
    c = DiffCompilationResult(DIFF_INPUT, diff_status, (ExpectedDiffReason.SCOPE_INCOMPLETE,))
    r = result(compilation=c)
    assert r.status == want and r.verdict is None


def test_primary_tampering_reject_no_repair():
    effect = replace(
        COMPILED.expected_diff.primary_changes[0], removed_timeline_range=FrameRange(111, 150)
    )
    c = corrupt_diff("primary_changes", (effect,))
    r = result(compilation=c)
    assert r.verdict != V.PASS
    assert check(r, K.EXPECTED_DIFF_INTEGRITY).outcome == O.REJECT
    assert c.expected_diff.primary_changes[0].removed_timeline_range == FrameRange(111, 150)


def test_other_valid_proposal_cannot_reuse_diff():
    geometry = replace(GEOMETRY, geometry_ref="other", removed_ranges=(FrameRange(115, 155),))
    proposal = replace(PROPOSAL, geometry=geometry, affected_primary_range=FrameRange(115, 155))
    r = result(proposal=proposal)
    assert r.verdict != V.PASS
    assert check(r, K.EXPECTED_DIFF_INTEGRITY).outcome == O.REJECT


@pytest.mark.parametrize("context", [None, replace(PROTECTION, complete=False)])
def test_incomplete_empty_context_not_known_none(context):
    r = result(protection=context)
    assert r.status == S.INCOMPLETE and r.verdict is None


@pytest.mark.parametrize(
    "record",
    [
        ProtectedRangeRecord("range", "audio", FrameRange(110, 111)),
        ProtectedRangeRecord("object", "audio", object_id=PRIMARY_ID),
        ProtectedRangeRecord("following", "audio", object_id=A_ID),
        ProtectedRangeRecord("following-range", "audio", FrameRange(220, 221)),
        ProtectedRangeRecord("incoming-range", "audio", FrameRange(180, 190)),
    ],
)
def test_protected_direct_or_displacement_reject(record):
    r = result(protection=replace(PROTECTION, records=(record,)))
    assert r.status == S.EVALUATED and r.verdict == V.REJECT
    assert check(r, K.PROTECTED_RANGE).outcome == O.REJECT


@pytest.mark.parametrize(
    "value,status,verdict",
    [
        (ObservedValue.FALSE, S.EVALUATED, V.PASS),
        (ObservedValue.TRUE, S.EVALUATED, V.REJECT),
        (ObservedValue.UNKNOWN, S.INCOMPLETE, None),
    ],
)
def test_track_lock(value, status, verdict):
    r = result(evidence=replace(EVIDENCE, track_locks=(TrackLockEvidence("audio", value),)))
    assert (r.status, r.verdict) == (status, verdict)


@pytest.mark.parametrize("field", ["relationship_status", "dependency_status"])
@pytest.mark.parametrize("state", [AssessmentState.UNKNOWN, AssessmentState.UNRESOLVED])
def test_unresolved_precomputed_dependency(field, state):
    r = result(evidence=replace(EVIDENCE, **{field: state}))
    assert r.status == S.INCOMPLETE and r.verdict is None


@pytest.mark.parametrize(
    "kind,status",
    [
        (MappingKind.IDENTITY_1X, S.EVALUATED),
        (MappingKind.AFFINE_FORWARD, S.EVALUATED),
        (MappingKind.UNKNOWN, S.INCOMPLETE),
        (MappingKind.REVERSE, S.UNSUPPORTED),
        (MappingKind.FREEZE, S.UNSUPPORTED),
        (MappingKind.VARIABLE_RETIME, S.UNSUPPORTED),
    ],
)
def test_retime_matrix(kind, status):
    compilation = COMPILED
    if kind == MappingKind.AFFINE_FORWARD:
        primary = replace(PRIMARY, retime=kind)
        compilation = compile_expected_diff(
            replace(DIFF_INPUT, scope=replace(SCOPE, objects=(primary, A, UNCHANGED)))
        )
    r = result(
        compilation=compilation, evidence=replace(EVIDENCE, objects=(replace(PE, retime=kind), AE))
    )
    assert r.status == status
    if status != S.EVALUATED:
        assert r.verdict is None


@pytest.mark.parametrize(
    "field,value,kind",
    [
        ("media_id", "other", K.MEDIA_IDENTITY_PRESERVATION),
        ("source_range", FrameRange(11, 71), K.SOURCE_RANGE_PRESERVATION),
        ("timeline_range", FrameRange(160, 221), K.DURATION_PRESERVATION),
        ("track_id", "video", K.TRACK_MEMBERSHIP_PRESERVATION),
    ],
)
def test_corrupted_pure_displacement_is_hard_reject(field, value, kind):
    moves = deepcopy(COMPILED.expected_diff.displacements)
    object.__setattr__(moves[0], "after", replace(moves[0].after, **{field: value}))
    r = result(compilation=corrupt_diff("displacements", moves))
    assert r.verdict == V.REJECT and check(r, kind).outcome == O.REJECT


def test_topology_mutation_unsupported():
    r = result(compilation=corrupt_diff("expected_topology_changes", ("add-track",)))
    assert r.status == S.UNSUPPORTED and r.verdict is None


@pytest.mark.parametrize(
    "field,kind,proof_kind",
    [
        ("transition", K.TRANSITION_INTEGRITY, PreservationProofKind.TRANSITION),
        ("effect", K.EFFECT_EDITABILITY, PreservationProofKind.EFFECT),
        ("keyframe", K.KEYFRAME_EDITABILITY, PreservationProofKind.KEYFRAME),
    ],
)
@pytest.mark.parametrize(
    "state,status,verdict",
    [
        (F.KNOWN_ABSENT, S.EVALUATED, V.PASS),
        (F.UNKNOWN, S.INCOMPLETE, None),
        (F.KNOWN_PRESENT_WITHOUT_PROOF, S.EVALUATED, V.REVIEW_REQUIRED),
        (F.PRESERVATION_PROVEN, S.EVALUATED, V.PASS),
        (F.EXPLICIT_VIOLATION, S.EVALUATED, V.REJECT),
    ],
)
def test_structure_five_state_matrix(field, kind, proof_kind, state, status, verdict):
    p = proof(proof_kind)
    r = structure_result(
        field,
        state,
        (p,) if state == F.PRESERVATION_PROVEN else (),
        p.proof_ref if state == F.PRESERVATION_PROVEN else None,
    )
    assert (r.status, r.verdict) == (status, verdict)
    assert check(r, kind).outcome == (None if verdict is None else O(verdict.value))


@pytest.mark.parametrize(
    "changes",
    [
        {"expected_diff_ref": "wrong"},
        {"subject": AS},
        {"proof_kind": PreservationProofKind.EFFECT},
        {"proof_contract_version": "v2"},
        {"outcome": ProofOutcome.UNVERIFIED},
    ],
)
def test_invalid_bound_proof_cannot_pass(changes):
    p = proof(**changes)
    r = structure_result("transition", F.PRESERVATION_PROVEN, (p,), "proof")
    assert r.verdict == V.REVIEW_REQUIRED


def test_stale_proof():
    p = proof(snapshot=NativeSnapshotRef("main", 43, "human"))
    r = structure_result("transition", F.PRESERVATION_PROVEN, (p,), "proof")
    assert r.status == S.STALE and r.verdict is None
    assert any(f.outcome == O.REVIEW_REQUIRED for f in check(r, K.TRANSITION_INTEGRITY).findings)


def test_no_proof_generation():
    r = structure_result("effect", F.PRESERVATION_PROVEN)
    assert r.verdict == V.REVIEW_REQUIRED and r.inputs.proofs == ()


def test_known_scope_omission():
    missing = TimelineObjectId("audio", "missing")
    for field in ("known_impacted_ids", "known_dependent_ids"):
        r = result(evidence=replace(EVIDENCE, **{field: (missing,)}))
        assert r.status == S.INCOMPLETE
        assert check(r, K.PRESERVATION_SCOPE).outcome is None


def test_changed_scope_omission():
    c = deepcopy(COMPILED)
    scope = replace(SCOPE, objects=(PRIMARY, UNCHANGED))
    object.__setattr__(c.expected_diff.inputs, "scope", scope)
    r = result(compilation=c)
    assert r.status == S.INCOMPLETE and r.verdict is None


def test_findings_retained_and_verdict_precedence():
    protection = replace(
        PROTECTION, records=(ProtectedRangeRecord("protected", "audio", object_id=A_ID),)
    )
    evidence = replace(
        EVIDENCE,
        track_locks=(TrackLockEvidence("audio", ObservedValue.TRUE),),
        objects=(replace(PE, transition=StructureObservation(F.KNOWN_PRESENT_WITHOUT_PROOF)), AE),
    )
    r = result(protection=protection, evidence=evidence)
    assert r.verdict == V.REJECT
    assert check(r, K.PROTECTED_RANGE).outcome == O.REJECT
    assert check(r, K.TRACK_LOCK).outcome == O.REJECT
    assert check(r, K.TRANSITION_INTEGRITY).outcome == O.REVIEW_REQUIRED
    assert len(r.checks) == 17


def test_status_precedence_with_retained_hard_findings():
    protection = replace(
        PROTECTION,
        complete=False,
        records=(ProtectedRangeRecord("protected", "audio", object_id=A_ID),),
    )
    evidence = replace(EVIDENCE, objects=(replace(PE, retime=MappingKind.REVERSE), AE))
    r = result(protection=protection, evidence=evidence)
    assert r.status == S.UNSUPPORTED and r.verdict is None
    assert any(f.outcome == O.REJECT for f in check(r, K.PROTECTED_RANGE).findings)
    r = result(
        protection=protection,
        evidence=evidence,
        current_snapshot=NativeSnapshotRef("main", 43, "human"),
    )
    assert r.status == S.STALE and r.verdict is None


def test_immutable_and_defensive_ordering():
    locks = list(EVIDENCE.track_locks)
    objects = [AE, PE]
    ev = replace(EVIDENCE, track_locks=locks, objects=objects)
    locks.clear()
    objects.clear()
    assert result(evidence=ev) == result()
    r = result()
    for obj in (
        INPUT,
        EVIDENCE,
        PE,
        PE.subject,
        ABSENT,
        PROTECTION,
        proof(),
        r,
        r.checks[0],
        r.checks[0].findings[0],
        PAUSE_DESTRUCTIVE_PREFLIGHT_V1,
    ):
        with pytest.raises(FrozenInstanceError):
            obj.accidental = "mutation"


def test_no_other_layer_calls(monkeypatch):
    from davinci_ai_editor import (
        authority,
        cut_geometry,
        dependency,
        expected_diff,
        native_snapshot,
        pause,
        pause_planning,
        safety,
        temporal_mapping,
    )
    from davinci_ai_editor.fake_timeline import FakeTimeline

    def forbidden(*args, **kwargs):
        pytest.fail("unexpected execution")

    for module, name in [
        (temporal_mapping, "map_range"),
        (native_snapshot, "evaluate_readiness"),
        (pause_planning, "plan_pause"),
        (cut_geometry, "resolve_geometry"),
        (expected_diff, "compile_expected_diff"),
        (pause, "classify_pause"),
        (safety, "preflight"),
        (authority, "transition"),
        (FakeTimeline, "apply"),
    ]:
        monkeypatch.setattr(module, name, forbidden)
    for name in vars(dependency):
        if name.startswith("compile"):
            monkeypatch.setattr(dependency, name, forbidden)
    assert result().verdict == V.PASS


@pytest.mark.parametrize(
    "changes",
    [
        {"evidence": None},
        {"evidence": replace(EVIDENCE, track_locks=())},
        {"evidence": replace(EVIDENCE, objects=(AE,))},
        {"evidence": replace(EVIDENCE, relationship_assessment_ref=None)},
        {"evidence": replace(EVIDENCE, dependency_assessment_ref=None)},
        {"evidence": replace(EVIDENCE, objects=(ObjectSafetyEvidence(PS), AE))},
    ],
)
def test_missing_mandatory_evidence_is_never_pass(changes):
    r = result(**changes)
    assert r.status == S.INCOMPLETE and r.verdict is None
    assert len(r.checks) == 17


@pytest.mark.parametrize("value", [ObservedValue.FALSE, ObservedValue.UNKNOWN])
def test_exact_forward_proof_required(value):
    r = result(evidence=replace(EVIDENCE, objects=(replace(PE, exact_forward=value), AE)))
    assert r.status == S.INCOMPLETE


def test_supported_retime_conflict_not_silently_resolved():
    r = result(
        evidence=replace(EVIDENCE, objects=(replace(PE, retime=MappingKind.AFFINE_FORWARD), AE))
    )
    assert r.status == S.INCOMPLETE and r.verdict is None


@pytest.mark.parametrize(
    "mapping,status", [(MappingKind.UNKNOWN, S.INCOMPLETE), (MappingKind.REVERSE, S.UNSUPPORTED)]
)
def test_planned_retime_cannot_be_overridden_by_supplied_one_x(mapping, status):
    effect = replace(
        COMPILED.expected_diff.primary_changes[0], before=replace(PRIMARY, retime=mapping)
    )
    r = result(compilation=corrupt_diff("primary_changes", (effect,)))
    assert r.status == status and r.verdict is None


def test_all_diagnostics_with_partial_structure_evidence():
    pe = replace(PE, transition=StructureObservation(F.EXPLICIT_VIOLATION))
    ae = replace(
        AE,
        transition=StructureObservation(F.KNOWN_PRESENT_WITHOUT_PROOF),
        effect=StructureObservation(F.UNKNOWN),
    )
    r = result(evidence=replace(EVIDENCE, objects=(pe, ae)))
    assert r.status == S.INCOMPLETE and r.verdict is None
    outcomes = {f.outcome for f in check(r, K.TRANSITION_INTEGRITY).findings}
    assert {O.REJECT, O.REVIEW_REQUIRED} <= outcomes
    assert check(r, K.KEYFRAME_EDITABILITY).outcome == O.PASS


def test_incomplete_protection_retains_known_violation():
    r = result(
        protection=replace(
            PROTECTION,
            complete=False,
            records=(ProtectedRangeRecord("known", "audio", object_id=PRIMARY_ID),),
        )
    )
    assert r.status == S.INCOMPLETE
    protected = check(r, K.PROTECTED_RANGE)
    assert protected.outcome is None
    assert {f.status for f in protected.findings} == {S.INCOMPLETE, S.EVALUATED}
    assert any(f.outcome == O.REJECT for f in protected.findings)


def test_half_open_protection_and_unaffected_objects():
    records = (
        ProtectedRangeRecord("touching", "audio", FrameRange(150, 160)),
        ProtectedRangeRecord("unchanged", "audio", object_id=U_ID),
        ProtectedRangeRecord("other-track", "video", FrameRange(100, 300)),
    )
    assert result(protection=replace(PROTECTION, records=records)).verdict == V.PASS


def test_object_bound_range_does_not_protect_same_media_other_placement():
    record = ProtectedRangeRecord("only-unlisted", "audio", FrameRange(200, 260), U_ID)
    assert result(protection=replace(PROTECTION, records=(record,))).verdict == V.PASS


def test_every_affected_track_lock_is_evaluated():
    b = replace(A, object_id=TimelineObjectId("video", "b"), track_id="video")
    assessment = replace(
        ASSESSMENT,
        participants=(*ASSESSMENT.participants, DisplacementParticipant(b, -40, "video")),
    )
    scope = replace(SCOPE, objects=(*SCOPE.objects, b))
    compilation = compile_expected_diff(replace(DIFF_INPUT, participation=assessment, scope=scope))
    be = replace(AE, subject=SafetySubject(b.object_id, b.timeline_range))
    ev = replace(
        EVIDENCE,
        objects=(*EVIDENCE.objects, be),
        track_locks=(
            TrackLockEvidence("audio", ObservedValue.TRUE),
            TrackLockEvidence("video", ObservedValue.UNKNOWN),
        ),
    )
    r = result(compilation=compilation, evidence=ev)
    assert r.status == S.INCOMPLETE
    assert any(f.outcome == O.REJECT for f in check(r, K.TRACK_LOCK).findings)
    ev = replace(
        ev,
        track_locks=(
            TrackLockEvidence("audio", ObservedValue.FALSE),
            TrackLockEvidence("video", ObservedValue.TRUE),
        ),
    )
    assert result(compilation=compilation, evidence=ev).verdict == V.REJECT


def test_unaffected_track_lock_not_inferred_as_affected():
    ev = replace(
        EVIDENCE,
        track_locks=(*EVIDENCE.track_locks, TrackLockEvidence("video", ObservedValue.TRUE)),
    )
    assert result(evidence=ev).verdict == V.PASS


@pytest.mark.parametrize(
    "snapshot",
    [
        NativeSnapshotRef("other", 42, "base"),
        NativeSnapshotRef("main", 41, "base"),
        NativeSnapshotRef("main", 42, "different"),
    ],
)
def test_all_proof_snapshot_coordinates_are_binding(snapshot):
    p = proof(snapshot=snapshot)
    r = structure_result("transition", F.PRESERVATION_PROVEN, (p,), "proof")
    assert r.status == S.STALE and r.verdict is None


def test_proof_subject_range_must_match_exactly():
    p = proof(subject=replace(PS, frame_range=FrameRange(109, 151)))
    assert (
        structure_result("transition", F.PRESERVATION_PROVEN, (p,), "proof").verdict
        == V.REVIEW_REQUIRED
    )


def test_invalid_unused_proof_is_not_hidden():
    assert result(proofs=(proof(expected_diff_ref="other"),)).verdict == V.REVIEW_REQUIRED


def test_displaced_object_needs_its_own_preservation_proof():
    ae = replace(AE, effect=StructureObservation(F.PRESERVATION_PROVEN, "proof"))
    p = proof(PreservationProofKind.EFFECT, subject=AS)
    assert result(evidence=replace(EVIDENCE, objects=(PE, ae)), proofs=(p,)).verdict == V.PASS
    assert (
        result(
            evidence=replace(EVIDENCE, objects=(PE, ae)), proofs=(replace(p, subject=PS),)
        ).verdict
        == V.REVIEW_REQUIRED
    )


def test_valid_proof_does_not_hide_explicit_violation_elsewhere():
    p = proof()
    pe = replace(PE, transition=StructureObservation(F.PRESERVATION_PROVEN, "proof"))
    ae = replace(AE, transition=StructureObservation(F.EXPLICIT_VIOLATION))
    r = result(evidence=replace(EVIDENCE, objects=(pe, ae)), proofs=(p,))
    assert r.verdict == V.REJECT
    assert {f.outcome for f in check(r, K.TRANSITION_INTEGRITY).findings} == {O.PASS, O.REJECT}


def test_evidence_wrong_diff_ref_and_wrong_subject_cannot_pass():
    assert result(evidence=replace(EVIDENCE, expected_diff_ref="other")).status == S.INCOMPLETE
    wrong = replace(PE, subject=replace(PS, frame_range=FrameRange(111, 150)))
    assert result(evidence=replace(EVIDENCE, objects=(wrong, AE))).status == S.INCOMPLETE


def test_profile_or_contract_unknown_unsupported():
    assert result(safety_contract_version="v2").status == S.UNSUPPORTED
    assert (
        result(profile=replace(PAUSE_DESTRUCTIVE_PREFLIGHT_V1, profile_version="v2")).status
        == S.UNSUPPORTED
    )


def test_no_missing_checks_or_forged_verdict_constructors():
    r = structure_result("effect", F.KNOWN_PRESENT_WITHOUT_PROOF)
    with pytest.raises(ValueError):
        replace(r, verdict=V.PASS)
    with pytest.raises(ValueError):
        replace(r.checks[0], findings=())
    with pytest.raises(ValueError):
        replace(r.checks[0].findings[0], status=S.INCOMPLETE, outcome=O.PASS)
    with pytest.raises(ValueError):
        replace(r, status=S.INCOMPLETE, verdict=None)
    assert all(c.invariant_refs for c in r.checks)


def test_no_generic_override_or_confidence_bypass():
    from davinci_ai_editor.evidence import EvidenceStrength
    from davinci_ai_editor.pause import Confidence

    for value in (Confidence.HIGH, EvidenceStrength.STRONG, 1.0):
        with pytest.raises(TypeError):
            replace(PE, transition=StructureObservation(value))
        with pytest.raises(TypeError):
            replace(proof(), outcome=value)
    for value in (INPUT, proof(), PAUSE_DESTRUCTIVE_PREFLIGHT_V1):
        with pytest.raises(TypeError):
            replace(value, confidence=1.0)
        with pytest.raises(TypeError):
            replace(value, override=True)
    record = ProtectedRangeRecord("protected", "audio", object_id=PRIMARY_ID)
    with pytest.raises(ValueError):
        replace(record, policy="ALLOW_OVERRIDE")
    r = result(protection=replace(PROTECTION, records=(record,)))
    assert r.verdict == V.REJECT


@pytest.mark.parametrize(
    "producer", ["HUMAN", "highest-confidence-model", "latest-trusted-producer"]
)
def test_producer_name_cannot_make_bad_proof_valid(producer):
    p = proof(producer_name=producer, outcome=ProofOutcome.UNVERIFIED)
    assert (
        structure_result("transition", F.PRESERVATION_PROVEN, (p,), "proof").verdict
        == V.REVIEW_REQUIRED
    )


def test_duplicate_evidence_rejects_instead_of_latest_wins():
    with pytest.raises(ValueError):
        replace(EVIDENCE, objects=(PE, replace(PE, retime=MappingKind.REVERSE)))
    with pytest.raises(ValueError):
        replace(
            EVIDENCE,
            track_locks=(
                TrackLockEvidence("audio", ObservedValue.TRUE),
                TrackLockEvidence("audio", ObservedValue.FALSE),
            ),
        )
    with pytest.raises(ValueError):
        replace(INPUT, proofs=(proof(), proof(outcome=ProofOutcome.UNVERIFIED)))
    record = ProtectedRangeRecord("same", "audio", object_id=PRIMARY_ID)
    with pytest.raises(ValueError):
        replace(PROTECTION, records=(record, replace(record, object_id=A_ID)))


def test_result_keeps_all_context_and_proof_refs_and_copies():
    p = proof()
    proofs = [p]
    records = [ProtectedRangeRecord("untouched", "audio", object_id=U_ID)]
    i = replace(INPUT, proofs=proofs, protection=replace(PROTECTION, records=records))
    proofs.clear()
    records.clear()
    r = preflight(i)
    assert r.inputs.proofs == (p,) and len(r.inputs.protection.records) == 1
    checks = list(r.checks)
    r2 = replace(r, checks=checks)
    checks.clear()
    assert r == r2 and r.inputs.current_snapshot == BASE
    assert r.inputs.compilation.inputs.expected_diff_ref == "diff"
    assert r.inputs.profile.profile_id == "PAUSE_DESTRUCTIVE_PREFLIGHT_V1"


def test_retained_raw_input_and_no_replanning():
    c = deepcopy(COMPILED)
    before = deepcopy(c)
    r = result(
        compilation=c,
        evidence=replace(EVIDENCE, track_locks=(TrackLockEvidence("audio", ObservedValue.TRUE),)),
    )
    assert r.verdict == V.REJECT and c == before
    assert r.inputs.proposal.geometry == GEOMETRY
    assert r.inputs.compilation.expected_diff.displacements == COMPILED.expected_diff.displacements


def test_wrong_delta_does_not_get_repaired():
    moves = deepcopy(COMPILED.expected_diff.displacements)
    object.__setattr__(moves[0], "delta_frames", -39)
    c = corrupt_diff("displacements", moves)
    r = result(compilation=c)
    assert check(r, K.EXPECTED_DIFF_INTEGRITY).outcome == O.REJECT
    assert c.expected_diff.displacements[0].delta_frames == -39


def test_tampered_scope_geometry_binding_nonpass():
    c = deepcopy(COMPILED)
    object.__setattr__(c.expected_diff.inputs.scope, "binding", replace(DB, geometry_ref="other"))
    assert check(result(compilation=c), K.EXPECTED_DIFF_INTEGRITY).outcome == O.REJECT


def test_no_runtime_imports():
    import ast
    from pathlib import Path

    from davinci_ai_editor import safety_preflight

    tree = ast.parse(Path(safety_preflight.__file__).read_text(encoding="utf-8-sig"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports <= {
        "dataclasses",
        "enum",
        "typing",
        "domain",
        "expected_diff",
        "native_snapshot",
        "pause_planning",
        "temporal_mapping",
    }
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))


@pytest.mark.parametrize("stale", [False, True])
@pytest.mark.parametrize("unsupported", [False, True])
@pytest.mark.parametrize("incomplete", [False, True])
def test_all_status_precedence_combinations(stale, unsupported, incomplete):
    ev = replace(
        EVIDENCE,
        objects=(
            replace(
                PE,
                retime=MappingKind.REVERSE if unsupported else MappingKind.IDENTITY_1X,
                effect=StructureObservation(F.UNKNOWN if incomplete else F.KNOWN_ABSENT),
            ),
            AE,
        ),
    )
    r = result(
        evidence=ev, current_snapshot=NativeSnapshotRef("main", 43, "human") if stale else BASE
    )
    want = (
        S.STALE
        if stale
        else S.UNSUPPORTED
        if unsupported
        else S.INCOMPLETE
        if incomplete
        else S.EVALUATED
    )
    assert r.status == want
    assert r.verdict == (V.PASS if want == S.EVALUATED else None)
    assert len(r.checks) == 17


@pytest.mark.parametrize(
    "first", [F.KNOWN_ABSENT, F.KNOWN_PRESENT_WITHOUT_PROOF, F.EXPLICIT_VIOLATION]
)
@pytest.mark.parametrize(
    "second", [F.KNOWN_ABSENT, F.KNOWN_PRESENT_WITHOUT_PROOF, F.EXPLICIT_VIOLATION]
)
def test_all_evaluated_verdict_combinations(first, second):
    pe = replace(PE, effect=StructureObservation(first))
    ae = replace(AE, keyframe=StructureObservation(second))
    r = result(evidence=replace(EVIDENCE, objects=(pe, ae)))
    want = (
        V.REJECT
        if F.EXPLICIT_VIOLATION in (first, second)
        else V.REVIEW_REQUIRED
        if F.KNOWN_PRESENT_WITHOUT_PROOF in (first, second)
        else V.PASS
    )
    assert r.status == S.EVALUATED and r.verdict == want


def test_corrupt_primary_does_not_hide_protected_findings():
    effect = replace(
        COMPILED.expected_diff.primary_changes[0], removed_timeline_range=FrameRange(100, 150)
    )
    c = corrupt_diff("primary_changes", (effect,))
    protection = replace(
        PROTECTION, records=(ProtectedRangeRecord("new-overlap", "audio", FrameRange(100, 105)),)
    )
    r = result(compilation=c, protection=protection)
    assert check(r, K.EXPECTED_DIFF_INTEGRITY).outcome == O.REJECT
    assert any(f.outcome == O.REJECT for f in check(r, K.PROTECTED_RANGE).findings)
    assert r.verdict != V.PASS


def test_every_safety_record_is_frozen_and_copied():
    from davinci_ai_editor.safety_preflight import SafetyFinding, SafetyReason

    record = ProtectedRangeRecord("r", "audio", object_id=A_ID)
    finding = SafetyFinding(S.EVALUATED, O.REJECT, SafetyReason.TRACK_LOCKED, [PS], ["ev"])
    for value in (record, EVIDENCE.track_locks[0], finding):
        with pytest.raises(FrozenInstanceError):
            value.changed = True
    subjects = [PS]
    refs = ["proof-evidence"]
    copied = replace(finding, subjects=subjects, evidence_refs=refs)
    subjects.clear()
    refs.clear()
    assert copied.subjects == (PS,) and copied.evidence_refs == ("proof-evidence",)


def test_three_valid_proofs_and_order_independence():
    proofs = [proof(kind, proof_ref=kind.value) for kind in PreservationProofKind]
    pe = replace(
        PE,
        transition=StructureObservation(F.PRESERVATION_PROVEN, "TRANSITION"),
        effect=StructureObservation(F.PRESERVATION_PROVEN, "EFFECT"),
        keyframe=StructureObservation(F.PRESERVATION_PROVEN, "KEYFRAME"),
    )
    r = result(evidence=replace(EVIDENCE, objects=(pe, AE)), proofs=proofs)
    assert r.verdict == V.PASS
    assert result(evidence=replace(EVIDENCE, objects=(AE, pe)), proofs=tuple(reversed(proofs))) == r
    proofs.clear()
    assert len(r.inputs.proofs) == 3
