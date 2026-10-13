"""VS-001 shared composition; exclusively synthetic state and evidence."""

from dataclasses import replace

import pytest
from support import vs001_simulation as sim

from davinci_ai_editor import authority as a
from davinci_ai_editor import cut_geometry as g
from davinci_ai_editor import execution_ir as ir
from davinci_ai_editor import expected_diff as d
from davinci_ai_editor import pause as p
from davinci_ai_editor import pause_planning as pp
from davinci_ai_editor import safety_preflight as s
from davinci_ai_editor import transaction as t
from davinci_ai_editor.domain import (
    ClipId,
    MediaId,
    TimelineId,
    TimelineVersion,
    TrackId,
    TrackType,
)
from davinci_ai_editor.domain import FrameRange as R
from davinci_ai_editor.domain import TimelineObjectId as O
from davinci_ai_editor.native_snapshot import IdentityScope, ReadinessStatus
from davinci_ai_editor.native_snapshot import ObservedValue as V
from davinci_ai_editor.temporal_mapping import MappingKind as M
from davinci_ai_editor.temporal_mapping import MappingStatus, NativeSnapshotRef


def fixture(*, unchanged_scope: bool = False) -> sim.Request:
    base = NativeSnapshotRef(TimelineId("vs001"), TimelineVersion(1), "simulation:base")
    primary_id, following_id = O(TrackId("V1"), ClipId("primary")), O(TrackId("V1"), ClipId("downstream"))
    observation = p.PauseObservation(
        TimelineId("vs001"), TimelineVersion(1), primary_id, R(300, 420), p.RelativePauseBand.LONG,
        p.PauseBoundaryKind.SENTENCE_BOUNDARY, (), 48, p.ContentMode.SPOKEN_CONTENT,
    )
    candidate = p.classify_pause(observation)
    assert (candidate.action, candidate.confidence) == (p.PauseAction.TIGHTEN, p.Confidence.MEDIUM)
    binding = pp.PlanningBinding("candidate", base, primary_id, observation.pause_range)
    explicit = g.ExplicitGeometryInput(
        "explicit", binding, (R(348, 420),),
        g.GeometryProducerRef(g.GeometryProducerKind.EXPLICIT_CALLER, "fixture", "1", "v1"),
        g.GeometryConfidence.STRONG,
    )
    resolution = g.resolve_geometry(g.GeometryResolutionInput(
        "geometry", candidate, binding, base, R(0, 420), MappingStatus.EXACT,
        explicit_geometries=(explicit,),
    ))
    assert resolution.status == g.GeometryResolutionStatus.RESOLVED
    resolved = resolution.candidates[0]
    geometry = pp.PauseCutGeometry(
        resolved.geometry_id, binding, (resolved.removed_range,), resolved.retained_total_frames,
        pp.GeometryProvenance("geometry", "v1"), "v1",
    )
    planned = pp.plan_pause(pp.PausePlanningInput(
        "proposal", candidate, binding, base, geometry,
        pp.TargetReadinessInput("target", binding, MappingStatus.EXACT, MediaId("primary-media"),
                                R(0, 420), R(348, 420)),
        pp.SnapshotReadinessInput("snapshot", binding, ReadinessStatus.READY, "synthetic"),
        pp.DependencyReadinessInput("dependency", binding, pp.DependencyStatus.RESOLVED,
                                    geometry.geometry_ref, R(348, 420),
                                    pp.TemporalEditIntent.SHORTEN_GAP),
    ))
    assert planned.proposal is not None
    primary = d.PlacementState(primary_id, MediaId("primary-media"), TrackId("V1"), R(0, 420), R(0, 420),
                               M.IDENTITY_1X)
    following = d.PlacementState(following_id, MediaId("following-media"), TrackId("V1"), R(420, 540),
                                 R(500, 620), M.IDENTITY_1X)
    db = d.DiffBinding("proposal", binding, geometry.geometry_ref, R(348, 420))
    untouched = d.PlacementState(O(TrackId("V1"), ClipId("untouched")), MediaId("untouched"),
                                TrackId("V1"), R(800, 900), R(0, 100), M.IDENTITY_1X)
    scope = d.PreservationScope("scope", db, (primary, following, untouched)
                               if unchanged_scope else (primary, following))
    participation = d.DisplacementParticipationAssessment(
        "participation", db, d.ParticipationStatus.RESOLVED,
        (d.DisplacementParticipant(following, -72, TrackId("V1")),), True, (following_id,),
    )
    compilation = d.compile_expected_diff(d.DiffCompilationInput(
        "diff", planned.proposal, participation, scope, base, d.CompilerProvenance("fixture", "1"),
    ))
    diff = compilation.expected_diff
    assert diff is not None
    absent = s.StructureObservation(s.StructureState.KNOWN_ABSENT)
    evidence = s.CurrentSafetyEvidence(
        "evidence", "diff", base, (s.TrackLockEvidence(TrackId("V1"), V.FALSE),),
        tuple(s.ObjectSafetyEvidence(subject, M.IDENTITY_1X, V.TRUE, absent, absent, absent)
              for subject in (s.SafetySubject(primary_id, R(348, 420)),
                              s.SafetySubject(following_id, R(420, 540)))),
        s.AssessmentState.RESOLVED, "relationships", s.AssessmentState.RESOLVED, "dependency",
    )
    safety = s.preflight(s.SafetyPreflightInput(
        compilation, planned.proposal, base, s.ProtectionContext("protection", base, True, (), "v1"),
        evidence,
    ))
    assert safety.verdict == s.SafetyVerdict.PASS and len(safety.checks) == 17
    work = a.CandidateWorkState(a.Candidate(a.CandidateId("candidate"), a.CandidateBase(TimelineId("vs001"), TimelineVersion(1))),
                                a.WorkingAuthority(a.CandidateBase(TimelineId("vs001"), TimelineVersion(1))))
    approval = a.transition(work, a.ApproveCandidate())
    assert approval.accepted
    artifact = t.ArtifactBinding("diff", "safety", base)
    authorization = t.ExecutionAuthorization("authorization", "explicit-human-approval", artifact)
    targets = tuple(ir.ExecutionTargetBinding(
        name, artifact, before, IdentityScope.SNAPSHOT_LOCAL, ir.TargetResolutionStatus.UNRESOLVED,
        "simulation-session",
    ) for name, before in (("primary-target", primary), ("following-target", following)))
    logical = ir.ExecutionIR("logical", authorization, (
        ir.RemoveRangeOp("01-remove", "primary-target", diff.primary_changes[0]),
        ir.TranslatePlacementOp("02-translate", "following-target", diff.displacements[0]),
    ), targets)
    return sim.Request(sim.SimulationState(base, scope.objects, (("V1", TrackType.VIDEO),)),
                       diff, safety, "safety", logical, approval.state, authorization.approval_ref)


POST = NativeSnapshotRef(TimelineId("vs001"), TimelineVersion(2), "simulation:post")


def run_fixture() -> tuple[sim.Request, sim.Run]:
    request = fixture()
    return request, sim.execute(request, request.base, POST)


def test_happy_path_to_verified_commit_and_historical_promotion() -> None:
    request, run = run_fixture()
    assert run.receipt.outcome == "COMPLETED" and run.receipt.published
    assert [r.result for r in run.receipt.operations] == ["EVALUATED", "EVALUATED"]
    objects = {o.object_id.clip_id: o for o in run.state.objects}
    assert objects[ClipId("primary")].timeline_range == objects[ClipId("primary")].source_range == R(0, 348)
    assert objects[ClipId("downstream")].timeline_range == R(348, 468)
    assert objects[ClipId("downstream")].source_range == R(500, 620)
    evidence = sim.derive_actual(request.base, run.state, run.receipt, sim.correlations(request))
    assert evidence.actual is not None and evidence.complete
    assert evidence.actual.primary_changes[0] == request.diff.primary_changes[0]
    assert evidence.actual.primary_changes[0] is not request.diff.primary_changes[0]
    verified = d._verify_legacy_semantics(request.diff, evidence.actual, POST)
    assert verified.status == d.DiffVerificationStatus.MATCH
    tx = sim.finish_transaction(request, run, evidence, run.state)
    assert tx.state.outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    promoted = sim.promote(request, tx, run, evidence, run.state)
    c = promoted.candidate
    assert (c.application, c.verification, c.promotion, c.validity) == (
        a.ApplicationState.APPLIED, a.VerificationState.VERIFIED,
        a.PromotionState.PROMOTED, a.CandidateValidity.STALE,
    )


def test_a_human_v2_stale_before_execution() -> None:
    req = fixture()
    human = replace(req.base, snapshot=NativeSnapshotRef(TimelineId("vs001"), TimelineVersion(2), "human"))
    work = a.transition(req.candidate, a.ObserveHumanVersion(a.CandidateBase(TimelineId("vs001"), TimelineVersion(2)))).state
    req = replace(req, candidate=work)
    run = sim.execute(req, human, NativeSnapshotRef(TimelineId("vs001"), TimelineVersion(3), "unused"))
    assert run.state is human and run.receipt.outcome == "REJECTED_STALE"
    assert all(not r.attempted for r in run.receipt.operations)
    tx = sim.finish_transaction(req, run, sim.Evidence(None, False, ("NOT_EXECUTED",)), human)
    assert tx.state.outcome == t.TransactionOutcome.ABORTED_STALE
    with pytest.raises(ValueError):
        sim.promote(req, tx, run, sim.Evidence(None, False, ()), human)
    assert work.candidate.verification == a.VerificationState.NOT_VERIFIED


def test_b_same_token_changed_contents() -> None:
    req = fixture()
    changed = replace(req.base, objects=tuple(replace(o, media_id=MediaId("human-change"))
                                             for o in req.base.objects))
    run = sim.execute(req, changed, POST)
    assert run.state is changed and run.receipt.outcome == "REJECTED_STALE"
    assert not run.receipt.published and all(not r.attempted for r in run.receipt.operations)


def test_c_actual_primary_off_by_one(monkeypatch: pytest.MonkeyPatch) -> None:
    original = sim._evaluate

    def faulty(op: ir.ExecutionOp, before: d.PlacementState) -> d.PlacementState:
        after = original(op, before)
        if isinstance(op, ir.RemoveRangeOp):
            return replace(after, timeline_range=R(0, 347), source_range=R(0, 347))
        return after

    monkeypatch.setattr(sim, "_evaluate", faulty)
    req, run = run_fixture()
    evidence = sim.derive_actual(req.base, run.state, run.receipt, sim.correlations(req))
    assert evidence.actual is not None
    assert evidence.actual.primary_changes[0].removed_timeline_range == R(347, 420)
    assert d._verify_legacy_semantics(req.diff, evidence.actual, POST).status == d.DiffVerificationStatus.MISMATCH
    assert sim.finish_transaction(req, run, evidence, run.state).state.outcome != (
        t.TransactionOutcome.VERIFIED_COMMITTED
    )


def test_d_actual_wrong_translation(monkeypatch: pytest.MonkeyPatch) -> None:
    original = sim._evaluate

    def faulty(op: ir.ExecutionOp, before: d.PlacementState) -> d.PlacementState:
        after = original(op, before)
        return replace(after, timeline_range=R(349, 469)) if isinstance(
            op, ir.TranslatePlacementOp) else after

    monkeypatch.setattr(sim, "_evaluate", faulty)
    req, run = run_fixture()
    evidence = sim.derive_actual(req.base, run.state, run.receipt, sim.correlations(req))
    assert evidence.actual is not None
    assert d._verify_legacy_semantics(req.diff, evidence.actual, POST).status == d.DiffVerificationStatus.MISMATCH


def test_e_unexpected_extra_object_mutation() -> None:
    req, run = run_fixture()
    extra = d.PlacementState(O(TrackId("V1"), ClipId("extra")), MediaId("extra-media"), TrackId("V1"), R(800, 900), R(0, 100),
                             M.IDENTITY_1X)
    actual_state = replace(run.state, objects=(*run.state.objects, extra))
    evidence = sim.derive_actual(req.base, actual_state, run.receipt, sim.correlations(req))
    assert evidence.actual is not None
    assert d._verify_legacy_semantics(req.diff, evidence.actual, POST).status == d.DiffVerificationStatus.MISMATCH


def test_f_invalid_second_operation_rejects_entire_batch() -> None:
    req = fixture()
    second = req.logical.ops[1]
    assert isinstance(second, ir.TranslatePlacementOp)
    bad = replace(second, target_ref="missing")
    req = replace(req, logical=replace(req.logical, ops=(req.logical.ops[0], bad)))
    run = sim.execute(req, req.base, POST)
    assert run.state is req.base and not run.receipt.published
    assert all(r.result == "NOT_ATTEMPTED" for r in run.receipt.operations)


def test_draft_failure_does_not_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    original = sim._evaluate

    def fail(op: ir.ExecutionOp, before: d.PlacementState) -> d.PlacementState:
        if isinstance(op, ir.TranslatePlacementOp):
            raise TypeError("injected")
        return original(op, before)

    monkeypatch.setattr(sim, "_evaluate", fail)
    req, run = run_fixture()
    assert run.state is req.base and not run.receipt.published
    assert [r.result for r in run.receipt.operations] == ["EVALUATED", "ERROR"]


def test_missing_correspondence_never_matches() -> None:
    req, run = run_fixture()
    receipt = replace(run.receipt, operations=())
    evidence = sim.derive_actual(req.base, run.state, receipt, sim.correlations(req))
    assert not evidence.complete
    assert evidence.actual is None or d._verify_legacy_semantics(
        req.diff, evidence.actual, POST).status != d.DiffVerificationStatus.MATCH


def test_missing_participant_receipt_is_unverified() -> None:
    req, run = run_fixture()
    receipt = replace(run.receipt, operations=run.receipt.operations[:1])
    evidence = sim.derive_actual(req.base, run.state, receipt, sim.correlations(req))
    assert not evidence.complete and evidence.actual is not None
    assert d._verify_legacy_semantics(req.diff, evidence.actual, POST).status == d.DiffVerificationStatus.UNVERIFIED


def test_safety_pass_is_not_approval() -> None:
    req = fixture()
    unapproved = a.CandidateWorkState(
        a.Candidate(req.candidate.candidate.candidate_id, req.candidate.candidate.base),
        req.candidate.authority,
    )
    run = sim.execute(replace(req, candidate=unapproved), req.base, POST)
    assert not run.receipt.published and run.state is req.base
    assert all(not record.attempted for record in run.receipt.operations)


def test_first_failure_leaves_remaining_operation_not_attempted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(op: ir.ExecutionOp, before: d.PlacementState) -> d.PlacementState:
        raise RuntimeError("injected first operation failure")

    monkeypatch.setattr(sim, "_evaluate", fail)
    req, run = run_fixture()
    assert run.state is req.base and not run.receipt.published
    assert [r.result for r in run.receipt.operations] == ["ERROR", "NOT_ATTEMPTED"]


def test_duplicate_object_identity_rejected() -> None:
    req = fixture()
    with pytest.raises(ValueError, match="duplicate object"):
        replace(req.base, objects=(*req.base.objects, req.base.objects[0]))


def test_actual_topology_change_is_observed_and_mismatches() -> None:
    req, run = run_fixture()
    post = replace(run.state, tracks=(*run.state.tracks, ("V2", TrackType.VIDEO)))
    evidence = sim.derive_actual(req.base, post, run.receipt, sim.correlations(req))
    assert evidence.actual is not None and evidence.actual.topology_change_refs
    assert d._verify_legacy_semantics(req.diff, evidence.actual, POST).status == d.DiffVerificationStatus.MISMATCH


def test_post_publication_human_change_cannot_commit_or_promote() -> None:
    req, run = run_fixture()
    evidence = sim.derive_actual(req.base, run.state, run.receipt, sim.correlations(req))
    current = replace(run.state, tracks=(*run.state.tracks, ("V2", TrackType.VIDEO)))
    tx = sim.finish_transaction(req, run, evidence, current)
    assert tx.state.outcome != t.TransactionOutcome.VERIFIED_COMMITTED
    with pytest.raises(ValueError):
        sim.promote(req, tx, run, evidence, current)


def test_unlisted_scoped_object_preserved_and_unexpected_mutation_detected() -> None:
    req = fixture(unchanged_scope=True)
    run = sim.execute(req, req.base, POST)
    assert run.receipt.published
    before = next(o for o in req.base.objects if o.object_id.clip_id == "untouched")
    after = next(o for o in run.state.objects if o.object_id == before.object_id)
    assert before == after
    evidence = sim.derive_actual(req.base, run.state, run.receipt, sim.correlations(req))
    assert evidence.actual is not None
    assert d._verify_legacy_semantics(req.diff, evidence.actual, POST).status == d.DiffVerificationStatus.MATCH
    damaged = replace(run.state, objects=tuple(
        replace(o, timeline_range=R(799, 899)) if o.object_id == before.object_id else o
        for o in run.state.objects))
    actual = sim.derive_actual(req.base, damaged, run.receipt, sim.correlations(req)).actual
    assert actual is not None
    assert d._verify_legacy_semantics(req.diff, actual, POST).status == d.DiffVerificationStatus.MISMATCH
