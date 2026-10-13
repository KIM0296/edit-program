"""Synthetic port contract tests only; no native qualification or execution evidence.

VERIFIED enum values below are deliberately supplied test data, as in test_execution_ir.
They do not establish capability/currentness for any installed runtime.
"""

import ast
from dataclasses import replace
from pathlib import Path

import pytest
from support import vs001_simulation as sim
from test_vs001_vertical_slice import POST, fixture

from davinci_ai_editor import authority as a
from davinci_ai_editor import cut_geometry as g
from davinci_ai_editor import execution_ir as ir
from davinci_ai_editor import expected_diff as d
from davinci_ai_editor import orchestration as o
from davinci_ai_editor import pause as p
from davinci_ai_editor import safety_preflight as s
from davinci_ai_editor import transaction as t
from davinci_ai_editor.domain import FrameRange, TimelineVersion
from davinci_ai_editor.native_snapshot import IdentityScope, ObservedValue


def preparation_inputs() -> o.PreparationInputs:
    req = fixture()
    planning = req.safety.inputs.compilation.inputs.proposal
    binding = planning.binding
    editorial = req.safety.inputs.compilation.inputs.proposal
    observation = req.candidate.candidate.base
    # Recover only qualified semantic fixture inputs; no simulator in production.
    from davinci_ai_editor import pause as p
    from davinci_ai_editor.temporal_mapping import MappingStatus

    pause = p.PauseObservation(
        observation.timeline_id,
        observation.timeline_version,
        binding.object_id,
        binding.original_pause_range,
        p.RelativePauseBand.LONG,
        p.PauseBoundaryKind.SENTENCE_BOUNDARY,
        (),
        48,
        p.ContentMode.SPOKEN_CONTENT,
    )
    candidate = p.classify_pause(pause)
    explicit = g.ExplicitGeometryInput(
        "explicit",
        binding,
        editorial.geometry.removed_ranges,
        g.GeometryProducerRef(g.GeometryProducerKind.EXPLICIT_CALLER, "fixture", "1", "v1"),
        g.GeometryConfidence.STRONG,
    )
    geometry = g.GeometryResolutionInput(
        "geometry",
        candidate,
        binding,
        binding.snapshot_ref,
        FrameRange(0, 420),
        MappingStatus.EXACT,
        explicit_geometries=(explicit,),
    )
    from davinci_ai_editor import pause_planning as pp
    from davinci_ai_editor.native_snapshot import ReadinessStatus

    return o.PreparationInputs(
        replace(req.candidate.candidate, approval=a.ApprovalState.NOT_APPROVED),
        pause,
        geometry,
        planning.proposal_ref,
        req.diff.expected_diff_ref,
        "safety",
        pp.TargetReadinessInput(
            "target",
            binding,
            MappingStatus.EXACT,
            req.diff.primary_changes[0].before.media_id,
            FrameRange(0, 420),
            FrameRange(348, 420),
        ),
        pp.SnapshotReadinessInput("snapshot", binding, ReadinessStatus.READY, "synthetic"),
        pp.DependencyReadinessInput(
            "dependency",
            binding,
            pp.DependencyStatus.RESOLVED,
            planning.geometry.geometry_ref,
            FrameRange(348, 420),
            pp.TemporalEditIntent.SHORTEN_GAP,
        ),
        req.diff.inputs.participation,
        req.diff.inputs.scope,
        req.diff.inputs.provenance,
        req.safety.inputs.protection,
        req.safety.inputs.evidence,
    )


def prepared() -> o.PreparedEdit:
    result = o.prepare_edit(preparation_inputs())
    assert result.status == o.CompositionStatus.READY and result.prepared is not None
    return result.prepared


def approval_for(value: o.PreparedEdit) -> o.BoundApproval:
    candidate = value.inputs.authority_candidate
    return o.BoundApproval(
        "test-human-approval", value, candidate.candidate_id, candidate.base, value.binding
    )


def approved_state(value: o.PreparedEdit) -> a.CandidateWorkState:
    candidate = value.inputs.authority_candidate
    work = a.CandidateWorkState(candidate, a.WorkingAuthority(candidate.base))
    result = a.transition(work, a.ApproveCandidate())
    assert result.accepted
    return result.state


def authorized() -> tuple[o.AuthorizedEdit, a.CandidateWorkState]:
    value = prepared()
    work = approved_state(value)
    result = o.authorize_edit(value, approval_for(value), work)
    assert result.authorized is not None
    return result.authorized, work


def runtime_admission(auth: o.AuthorizedEdit) -> o.RuntimeAdmissionEvidence:
    """Independent synthetic runtime port fixture, never a native support claim."""
    diff = auth.prepared.expected_diff
    binding = auth.prepared.binding
    profile = ir.RuntimeProfile("test-port", "1", "no-runtime", "test", "test-session")
    effects: tuple[d.RangeRemovalEffect | d.TemporalDisplacement, ...] = (
        *diff.primary_changes,
        *diff.displacements,
    )
    targets = tuple(
        ir.ExecutionTargetBinding(
            f"target-{i}",
            binding,
            effect.before,
            IdentityScope.SESSION_LOCAL_VERIFIED,
            ir.TargetResolutionStatus.VERIFIED,
            "test-session",
            f"test-locator-{i}",
            "test-identity-proof",
            "test-locator-proof",
            "test-mutation-proof",
            "test-post-proof",
        )
        for i, effect in enumerate(effects)
    )
    ops: tuple[ir.ExecutionOp, ...] = (
        ir.RemoveRangeOp("remove", targets[0].target_ref, diff.primary_changes[0]),
        *(
            ir.TranslatePlacementOp(f"translate-{i}", targets[i + 1].target_ref, effect)
            for i, effect in enumerate(diff.displacements)
        ),
    )
    logical = ir.ExecutionIR("test-ir", auth.authorization, ops, targets)
    cap = ir.NativeCapabilityStatus.SUPPORTED_VERIFIED
    manifest = ir.ExecutorCapabilityManifest(
        profile,
        (ir.PrimitiveCapability("test-primitive", cap),),
        cap,
        cap,
        cap,
    )
    model = ir.NativeEffectModel(
        "test-model",
        binding,
        profile,
        ir.EffectModelStatus.VERIFIED,
        ("step",),
        ("test-primitive",),
        tuple(op.op_ref for op in ops),
        effects,
        tuple(effect.before.object_id for effect in effects),
        ("test-model-evidence",),
    )
    recon = ir.ReconciliationSpec(
        "test-reconciliation",
        binding,
        profile,
        "step",
        ir.EffectModelStatus.VERIFIED,
        tuple(effect.before for effect in effects),
        "test-applied",
        "test-not-applied",
        ("test-read",),
        ("test-reconciliation-evidence",),
    )
    step = ir.NativeExecutionStep(
        "step", "test-primitive", tuple(x.target_ref for x in targets), recon, cap
    )
    plan = ir.NativeLoweringPlan(
        "test-lowering",
        "test-ir",
        binding,
        profile,
        (step,),
        (ir.LoweringRealization("realization", tuple(op.op_ref for op in ops), ("step",), model),),
    )
    v = ir.ExecutionIRValidationInput(
        diff,
        auth.prepared.inputs.safety_result_ref,
        auth.prepared.safety,
        logical,
        plan,
        manifest,
        binding.base_snapshot,
        profile,
        ObservedValue.TRUE,
    )
    definition = t.TransactionDefinition("test-transaction", binding, auth.authorization, ("step",))
    facts = t.PrecommitFacts(
        binding,
        auth.authorization.authorization_ref,
        binding.base_snapshot,
        auth.prepared.safety.status,
        auth.prepared.safety.verdict,
        ObservedValue.TRUE,
        ObservedValue.TRUE,
        ObservedValue.TRUE,
        ObservedValue.TRUE,
        False,
    )
    return o.RuntimeAdmissionEvidence(v, definition, facts)


def append_event(
    tx: t.Transaction, kind: t.TransactionEventKind, payload: t.EventPayload = None
) -> t.Transaction:
    return t.transition(
        tx,
        t.TransactionEvent(
            tx.definition.transaction_ref, tx.journal.events[-1].sequence_no + 1, kind, payload
        ),
    )


def completion() -> tuple[o.AuthorizedEdit, o.RuntimeFinalizationEvidence, a.CandidateWorkState]:
    auth, work = authorized()
    admission = o.admit_execution(auth, runtime_admission(auth), work)
    assert admission.status == o.CompositionStatus.READY
    tx = admission.transaction
    assert tx is not None
    # The test runtime/event port records start BEFORE supplying a result.
    tx = append_event(tx, t.TransactionEventKind.STEP_STARTED, "step")
    tx = append_event(
        tx,
        t.TransactionEventKind.STEP_SUCCEEDED,
        t.ExecutionStepResult("step", t.ExecutionStepStatus.SUCCEEDED, "test-step-result", True),
    )
    request = fixture()
    run = sim.execute(request, request.base, POST)
    produced = sim.derive_actual(request.base, run.state, run.receipt, sim.correlations(request))
    actual = produced.actual
    assert actual is not None and actual.identity_evidence_ref is not None
    post = t.CurrentAuthorityFacts(
        auth.prepared.binding,
        auth.authorization.authorization_ref,
        POST,
        ObservedValue.TRUE,
        ObservedValue.TRUE,
        False,
    )
    record = a.ApplicationRecord(
        work.candidate.candidate_id,
        work.candidate.base,
        a.CandidateResultRef(
            "test-result", a.CandidateBase(POST.timeline_id, POST.timeline_version)
        ),
    )
    result = o.ApplicationResultEvidence(
        "test-result-correspondence",
        record,
        tx.definition.transaction_ref,
        auth.authorization.authorization_ref,
        actual.actual_diff_ref,
        POST,
        actual.identity_evidence_ref,
    )
    return (
        auth,
        o.RuntimeFinalizationEvidence(
            admission,
            tx,
            actual,
            POST,
            "test-verification",
            post,
            "test-post-observation",
            replace(post),
            "test-separate-promotion-observation",
            result,
        ),
        work,
    )


def test_happy_prepare_retains_artifacts_and_distinct_candidates() -> None:
    value = prepared()
    assert isinstance(value.editorial_candidate, p.PauseCandidate)
    assert isinstance(value.inputs.authority_candidate, a.Candidate)
    assert value.geometry_resolution.inputs is value.inputs.geometry_inputs
    assert value.selected_geometry is value.geometry_resolution.candidates[0]
    assert value.safety.inputs.compilation is value.compilation
    assert value.compilation.inputs.proposal is value.planning.proposal
    assert value.expected_diff.primary_changes[0].removed_timeline_range == FrameRange(348, 420)
    assert value.safety.verdict == s.SafetyVerdict.PASS
    assert not hasattr(value, "execution_ir") and not hasattr(value, "actual_diff")


def test_ambiguous_geometry_rejected() -> None:
    inputs = preparation_inputs()
    explicit = inputs.geometry_inputs.explicit_geometries[0]
    other = replace(explicit, input_id="other", removed_ranges=(FrameRange(300, 372),))
    result = o.prepare_edit(
        replace(
            inputs,
            geometry_inputs=replace(inputs.geometry_inputs, explicit_geometries=(explicit, other)),
        )
    )
    assert result.prepared is None and result.diagnostics == ("GEOMETRY_NOT_UNIQUE",)


def test_safety_pass_is_not_approval() -> None:
    value = prepared()
    state = a.CandidateWorkState(
        value.inputs.authority_candidate, a.WorkingAuthority(value.inputs.authority_candidate.base)
    )
    assert o.authorize_edit(value, approval_for(value), state).authorized is None


def test_exact_bound_approval_accepted() -> None:
    auth, _ = authorized()
    assert auth.authorization.binding == auth.prepared.binding


@pytest.mark.parametrize("field", ["candidate", "base", "binding", "prepared"])
def test_authority_approval_without_exact_bound_approval_rejected(field: str) -> None:
    value = prepared()
    bound = approval_for(value)
    if field == "candidate":
        bound = replace(bound, candidate_id=a.CandidateId("other"))
    elif field == "base":
        bound = replace(bound, base=replace(bound.base, timeline_version=TimelineVersion(2)))
    elif field == "binding":
        bound = replace(bound, binding=replace(bound.binding, safety_result_ref="other"))
    else:
        changed = o.prepare_edit(
            replace(value.inputs, compiler_provenance=d.CompilerProvenance("different", "1"))
        ).prepared
        assert changed is not None and changed.binding == value.binding
        bound = replace(bound, prepared=changed)
    assert o.authorize_edit(value, bound, approved_state(value)).authorized is None


def test_same_ref_different_artifacts_rejected_at_admission() -> None:
    auth, work = authorized()
    runtime = runtime_admission(auth)
    changed = o.prepare_edit(
        replace(auth.prepared.inputs, compiler_provenance=d.CompilerProvenance("other", "1"))
    ).prepared
    assert changed is not None and changed.binding == auth.prepared.binding
    runtime = replace(
        runtime,
        validation_inputs=replace(runtime.validation_inputs, expected_diff=changed.expected_diff),
    )
    result = o.admit_execution(auth, runtime, work)
    assert result.status != o.CompositionStatus.READY and result.transaction is None


def test_pre_execution_human_change_is_stale() -> None:
    auth, work = authorized()
    human = a.transition(
        work,
        a.ObserveHumanVersion(replace(work.candidate.base, timeline_version=TimelineVersion(2))),
    ).state
    result = o.admit_execution(auth, runtime_admission(auth), human)
    assert result.status == o.CompositionStatus.STALE and result.transaction is None


@pytest.mark.parametrize("value", [ObservedValue.UNKNOWN, ObservedValue.FALSE])
@pytest.mark.parametrize(
    "field", ["authorization_current", "safety_current", "targets_resolvable", "executor_ready"]
)
def test_runtime_currentness_and_readiness_fail_closed(field: str, value: ObservedValue) -> None:
    auth, work = authorized()
    runtime = runtime_admission(auth)
    facts = runtime.precommit_facts
    if field == "authorization_current":
        facts = replace(facts, authorization_current=value)
    elif field == "safety_current":
        facts = replace(facts, safety_current=value)
    elif field == "targets_resolvable":
        facts = replace(facts, targets_resolvable=value)
    else:
        facts = replace(facts, executor_ready=value)
    runtime = replace(runtime, precommit_facts=facts)
    result = o.admit_execution(auth, runtime, work)
    assert result.status != o.CompositionStatus.READY and result.transaction is None


def test_ir_non_ready_rejected() -> None:
    auth, work = authorized()
    runtime = runtime_admission(auth)
    v = runtime.validation_inputs
    v = replace(v, manifest=replace(v.manifest, primitives=()))
    result = o.admit_execution(auth, replace(runtime, validation_inputs=v), work)
    assert result.status == o.CompositionStatus.BLOCKED and result.transaction is None


def test_precommit_recovery_blocks() -> None:
    auth, work = authorized()
    runtime = runtime_admission(auth)
    result = o.admit_execution(
        auth,
        replace(runtime, precommit_facts=replace(runtime.precommit_facts, recovery_required=True)),
        work,
    )
    assert result.status == o.CompositionStatus.BLOCKED and result.transaction is None


def test_actual_match_to_semantic_promotion_only() -> None:
    auth, runtime, work = completion()
    before = runtime.transaction.journal.events
    result = o.finalize_edit(auth, runtime, work)
    assert (
        result.verification is not None
        and result.verification.status == d.DiffVerificationStatus.MATCH
    )
    assert result.transaction_outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    assert result.transaction.journal.events[: len(before)] == before
    assert len(result.authority_transitions) == 3
    candidate = result.authority_after.candidate
    assert (
        candidate.application,
        candidate.verification,
        candidate.promotion,
        candidate.validity,
    ) == (
        a.ApplicationState.APPLIED,
        a.VerificationState.VERIFIED,
        a.PromotionState.PROMOTED,
        a.CandidateValidity.STALE,
    )
    assert result.durable_promotion == "NOT_PERFORMED" and result.authority_before is work


def test_actual_mismatch_never_commits() -> None:
    auth, runtime, work = completion()
    assert runtime.actual_diff is not None
    effect = runtime.actual_diff.primary_changes[0]
    actual = replace(
        runtime.actual_diff,
        primary_changes=(replace(effect, removed_timeline_range=FrameRange(347, 420)),),
    )
    result = o.finalize_edit(auth, replace(runtime, actual_diff=actual), work)
    assert (
        result.verification is not None
        and result.verification.status == d.DiffVerificationStatus.MISMATCH
    )
    assert result.transaction_outcome != t.TransactionOutcome.VERIFIED_COMMITTED
    assert result.authority_after is work


def test_missing_actual_never_synthesizes_postflight() -> None:
    auth, runtime, work = completion()
    result = o.finalize_edit(auth, replace(runtime, actual_diff=None), work)
    assert result.verification is None and result.transaction is runtime.transaction
    assert result.authority_after is work


def test_unknown_execution_remains_unknown() -> None:
    auth, runtime, work = completion()
    tx = runtime.admission.transaction
    assert tx is not None
    tx = append_event(tx, t.TransactionEventKind.STEP_STARTED, "step")
    tx = append_event(
        tx,
        t.TransactionEventKind.STEP_OUTCOME_UNKNOWN,
        t.ExecutionStepResult("step", t.ExecutionStepStatus.OUTCOME_UNKNOWN, "test-unknown", True),
    )
    result = o.finalize_edit(auth, replace(runtime, transaction=tx), work)
    assert result.transaction is tx and result.transaction.state.unresolved_step_outcome
    assert result.verification is None and result.authority_after is work


def test_missing_execution_history_not_synthesized() -> None:
    auth, runtime, work = completion()
    tx = runtime.admission.transaction
    assert tx is not None
    result = o.finalize_edit(auth, replace(runtime, transaction=tx), work)
    assert (
        result.transaction is tx
        and result.transaction_outcome != t.TransactionOutcome.VERIFIED_COMMITTED
    )


def test_post_execution_human_change_blocks_commit() -> None:
    auth, runtime, work = completion()
    changed = replace(POST, timeline_version=TimelineVersion(3), state_token="human")
    assert runtime.postflight_facts is not None
    evidence = replace(
        runtime,
        current_post_snapshot=changed,
        postflight_facts=replace(runtime.postflight_facts, current_snapshot=changed),
    )
    result = o.finalize_edit(auth, evidence, work)
    assert (
        result.verification is not None
        and result.verification.status == d.DiffVerificationStatus.STALE
    )
    assert result.transaction_outcome != t.TransactionOutcome.VERIFIED_COMMITTED
    assert result.authority_after is work


def test_commit_remains_historical_after_human_edit_before_promotion() -> None:
    auth, runtime, work = completion()
    first = o.finalize_edit(auth, replace(runtime, promotion_facts=None), work)
    assert first.transaction_outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    changed = replace(POST, timeline_version=TimelineVersion(3), state_token="human")
    human = a.transition(
        work, a.ObserveHumanVersion(a.CandidateBase(changed.timeline_id, changed.timeline_version))
    ).state
    assert runtime.promotion_facts is not None
    result = o.finalize_edit(
        auth,
        replace(
            runtime,
            transaction=first.transaction,
            prior_postflight=first.postflight_record,
            promotion_facts=replace(runtime.promotion_facts, current_snapshot=changed),
        ),
        human,
    )
    assert result.transaction is first.transaction
    assert result.transaction_outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    assert result.promotion_eligibility == t.PromotionEligibility.NOT_ELIGIBLE
    assert result.authority_after is human


@pytest.mark.parametrize(
    "field", ["record", "transaction_ref", "post_snapshot", "identity_evidence_ref"]
)
def test_application_result_mismatch_rejected(field: str) -> None:
    auth, runtime, work = completion()
    evidence = runtime.application_result
    assert evidence is not None
    if field == "record":
        evidence = replace(
            evidence, record=replace(evidence.record, candidate_id=a.CandidateId("other"))
        )
    elif field == "post_snapshot":
        evidence = replace(evidence, post_snapshot=replace(POST, state_token="other"))
    elif field == "transaction_ref":
        evidence = replace(evidence, transaction_ref="other")
    else:
        evidence = replace(evidence, identity_evidence_ref="other")
    result = o.finalize_edit(auth, replace(runtime, application_result=evidence), work)
    assert result.transaction_outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    assert result.authority_after is work and result.diagnostics == ("APPLICATION_RESULT_MISMATCH",)


@pytest.mark.parametrize("missing", ["facts", "ref", "reused"])
def test_separate_fresh_promotion_observation_required(missing: str) -> None:
    auth, runtime, work = completion()
    if missing == "facts":
        runtime = replace(runtime, promotion_facts=None)
    elif missing == "ref":
        runtime = replace(runtime, promotion_observation_ref=None)
    else:
        runtime = replace(runtime, promotion_observation_ref=runtime.postflight_observation_ref)
    result = o.finalize_edit(auth, runtime, work)
    assert result.transaction_outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    assert result.authority_after is work and result.durable_promotion == "NOT_PERFORMED"


def test_production_has_no_simulator_native_or_human_version_dispatch() -> None:
    source = Path(o.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "ObserveHumanVersion" not in names
    assert not {"execute", "derive_actual", "scriptapp", "GetCurrentProject"} & names
    assert "vs001_simulation" not in source and "SimulationState" not in source
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "ActualDiff" not in calls


def test_prepare_primary_media_conflict_rejected() -> None:
    inputs = preparation_inputs()
    assert inputs.target is not None
    from davinci_ai_editor.domain import MediaId

    result = o.prepare_edit(
        replace(inputs, target=replace(inputs.target, media_id=MediaId("other")))
    )
    assert result.prepared is None and result.diagnostics == ("PRIMARY_FACT_CONFLICT",)


@pytest.mark.parametrize("change", ["target", "participation", "evidence", "mixed_base"])
def test_missing_or_mixed_preparation_facts_fail_closed(change: str) -> None:
    inputs = preparation_inputs()
    if change == "target":
        inputs = replace(inputs, target=None)
    elif change == "participation":
        inputs = replace(
            inputs, participation=replace(inputs.participation, uniform_consequence_verified=False)
        )
    elif change == "evidence":
        inputs = replace(inputs, safety_evidence=None)
    else:
        inputs = replace(
            inputs,
            geometry_inputs=replace(
                inputs.geometry_inputs,
                current_snapshot=replace(
                    inputs.geometry_inputs.current_snapshot, state_token="different"
                ),
            ),
        )
    result = o.prepare_edit(inputs)
    if result.prepared is not None:
        value = result.prepared
        assert (
            o.authorize_edit(value, approval_for(value), approved_state(value)).authorized is None
        )
    else:
        assert result.status != o.CompositionStatus.READY


def test_evaluated_safety_non_pass_cannot_authorize() -> None:
    inputs = preparation_inputs()
    assert inputs.safety_evidence is not None
    evidence = replace(
        inputs.safety_evidence,
        track_locks=tuple(
            replace(lock, locked=ObservedValue.TRUE) for lock in inputs.safety_evidence.track_locks
        ),
    )
    value = o.prepare_edit(replace(inputs, safety_evidence=evidence)).prepared
    assert value is not None and value.safety.verdict != s.SafetyVerdict.PASS
    assert o.authorize_edit(value, approval_for(value), approved_state(value)).authorized is None


def test_mutated_prepared_artifact_rejected_even_with_new_bound_approval() -> None:
    value = prepared()
    other = p.classify_pause(replace(value.inputs.observation, local_reference_pause_frames=47))
    changed = replace(value, editorial_candidate=other)
    assert (
        o.authorize_edit(changed, approval_for(changed), approved_state(value)).authorized is None
    )


def test_lowering_step_set_and_rollback_capability_must_correspond() -> None:
    auth, work = authorized()
    runtime = runtime_admission(auth)
    wrong_steps = replace(
        runtime,
        transaction_definition=replace(runtime.transaction_definition, step_refs=("different",)),
    )
    assert o.admit_execution(auth, wrong_steps, work).transaction is None
    wrong_rollback = replace(
        runtime,
        transaction_definition=replace(
            runtime.transaction_definition,
            rollback=t.RollbackSettings(
                t.RollbackCapability.SUPPORTED_VERIFIED, t.RollbackPolicy.AUTO_ELIGIBLE
            ),
        ),
    )
    assert o.admit_execution(auth, wrong_rollback, work).transaction is None


def test_actual_unverified_never_commits() -> None:
    auth, runtime, work = completion()
    assert runtime.actual_diff is not None
    actual = replace(runtime.actual_diff, identity_evidence_ref=None)
    result = o.finalize_edit(auth, replace(runtime, actual_diff=actual), work)
    assert result.verification is not None
    assert result.verification.status == d.DiffVerificationStatus.UNVERIFIED
    assert result.transaction_outcome != t.TransactionOutcome.VERIFIED_COMMITTED


@pytest.mark.parametrize("field", ["authorization_current", "safety_pass_current"])
def test_post_currentness_unknown_blocks_commit(field: str) -> None:
    auth, runtime, work = completion()
    assert runtime.postflight_facts is not None
    facts = (
        replace(runtime.postflight_facts, authorization_current=ObservedValue.UNKNOWN)
        if field == "authorization_current"
        else replace(runtime.postflight_facts, safety_pass_current=ObservedValue.UNKNOWN)
    )
    result = o.finalize_edit(auth, replace(runtime, postflight_facts=facts), work)
    assert result.transaction_outcome != t.TransactionOutcome.VERIFIED_COMMITTED
    assert result.authority_after is work


def test_post_human_authority_blocks_commit_even_if_runtime_facts_claim_current() -> None:
    auth, runtime, work = completion()
    human = a.transition(
        work,
        a.ObserveHumanVersion(replace(work.candidate.base, timeline_version=TimelineVersion(3))),
    ).state
    result = o.finalize_edit(auth, runtime, human)
    assert result.transaction_outcome != t.TransactionOutcome.VERIFIED_COMMITTED
    assert result.authority_after is human


def test_later_fresh_promotion_does_not_reconstruct_journal() -> None:
    auth, runtime, work = completion()
    first = o.finalize_edit(auth, replace(runtime, promotion_facts=None), work)
    later = replace(
        runtime, transaction=first.transaction, prior_postflight=first.postflight_record
    )
    result = o.finalize_edit(auth, later, work)
    assert result.transaction is first.transaction
    assert result.authority_after.candidate.promotion == a.PromotionState.PROMOTED
    repeated = o.finalize_edit(auth, later, result.authority_after)
    assert repeated.transaction is first.transaction
    assert repeated.authority_after is result.authority_after
    assert not repeated.authority_transitions


def test_same_actual_ref_different_evidence_cannot_replace_committed_record() -> None:
    auth, runtime, work = completion()
    first = o.finalize_edit(auth, replace(runtime, promotion_facts=None), work)
    assert runtime.actual_diff is not None
    changed = replace(runtime.actual_diff, identity_evidence_ref="different-proof")
    result = o.finalize_edit(
        auth,
        replace(
            runtime,
            transaction=first.transaction,
            prior_postflight=first.postflight_record,
            actual_diff=changed,
        ),
        work,
    )
    assert result.transaction is first.transaction
    assert result.transaction_outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    assert result.authority_after is work
    assert result.diagnostics == ("PRIOR_POSTFLIGHT_ARTIFACT_MISMATCH",)
