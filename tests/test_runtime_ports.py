"""TEST_ONLY_SUPPORT: scripted port contracts, never native qualification.

All TRUE/VERIFIED literals, identities, acquisitions, and publication receipts are
supplied synthetic fixtures. No adapter, transport, persistence, or execution exists.
The tiny integration helpers below demonstrate obligations, not production algorithms.
"""

import ast
import inspect
from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path
from typing import Literal, TypeVar

import pytest
from support import vs001_simulation as sim
from test_orchestration import append_event, authorized, completion, runtime_admission
from test_vs001_vertical_slice import POST, fixture

from davinci_ai_editor import authority as a
from davinci_ai_editor import execution_ir as ir
from davinci_ai_editor import expected_diff as d
from davinci_ai_editor import native_snapshot as n
from davinci_ai_editor import orchestration as o
from davinci_ai_editor import runtime_ports as rp
from davinci_ai_editor import safety_preflight as s
from davinci_ai_editor import transaction as t
from davinci_ai_editor.domain import TimelineVersion
from davinci_ai_editor.temporal_mapping import NativeSnapshotRef

T = TypeVar("T")
V, E, K = n.ObservedValue, t.TransactionEventKind, rp.PortIssueKind


def receipt(acquisition: str | None = "test-read") -> rp.PortReceipt:
    return rp.PortReceipt(
        "test-receipt",
        "TEST_ONLY_SUPPORT",
        acquisition,
        () if acquisition is None else (acquisition,),
        ("Synthetic only; no native authenticity or observation-to-execution atomicity",),
        "TEST_ONLY_SUPPORT",
    )


def available(value: T, acquisition: str = "test-read") -> rp.PortValue[T]:
    return rp.PortValue(value, receipt(acquisition))


def issue(kind: rp.PortIssueKind, reason: str = "Synthetic uncertainty") -> rp.PortIssue:
    return rp.PortIssue(kind, reason, receipt(None))


def snapshot(ref: NativeSnapshotRef, acquisition: str = "test-read") -> n.NativeTimelineSnapshot:
    # Scalar capture carrier only. Actual semantic before/post observations are
    # supplied by the existing simulator, not inferred from this partial capture.
    return n.NativeTimelineSnapshot(
        acquisition,
        n.IdentityRef(ref.timeline_id, n.IdentityScope.UNKNOWN, n.IdentityBasis.UNKNOWN),
        ref.timeline_version,
        ref.state_token,
        None,
        (),
        (),
        n.AdapterProvenance("TEST_ONLY_SUPPORT", "1", "v1"),
        n.CapabilityManifest(
            (n.AdapterCapability(n.CapabilityKind.FRESHNESS, n.CapabilityState.SUPPORTED),)
        ),
        n.CaptureConsistency.UNVERIFIED,
        n.SnapshotCompleteness.PARTIAL,
    )


@dataclass
class SyntheticObserver:
    """TEST_ONLY_SUPPORT; scripted currentness plus existing independent simulator reader."""

    current: NativeSnapshotRef
    acquisition: str = "test-read"
    authorization_current: n.ObservedValue = V.TRUE
    safety_current: n.ObservedValue = V.TRUE
    facts_constructed: int = 0
    simulation: tuple[sim.SimulationState, sim.Run, sim.Correlations] | None = None

    def observe_currentness(
        self,
        authorization: t.ExecutionAuthorization,
        safety: s.SafetyPreflightResult,
        authority: rp.PortValue[a.CandidateWorkState],
        recovery: rp.PortValue[n.ObservedValue],
        *,
        purpose: Literal["admission", "postflight", "promotion"],
    ) -> rp.PortResult[rp.CurrentnessPayload]:
        if recovery.value == V.UNKNOWN:
            return issue(K.UNKNOWN, "Recovery not established; no boolean facts constructed")
        facts = t.CurrentAuthorityFacts(
            authorization.binding,
            authorization.authorization_ref,
            self.current,
            self.authorization_current,
            self.safety_current,
            recovery.value == V.TRUE,
        )
        self.facts_constructed += 1
        return available((snapshot(self.current, self.acquisition), facts), self.acquisition)

    def observe_postflight(
        self,
        binding: t.ArtifactBinding,
        scope: d.PreservationScope,
        before: rp.PortValue[rp.CurrentnessPayload],
        *,
        targets: tuple[ir.ExecutionTargetBinding, ...] = (),
        transaction: t.Transaction | None = None,
    ) -> rp.PortResult[rp.PostflightPayload]:
        if self.simulation is None:
            return issue(K.UNAVAILABLE, "No synthetic runtime observation")
        base, run, correlations = self.simulation
        if (
            binding.base_snapshot != base.snapshot
            or before.value[1].current_snapshot != base.snapshot
        ):
            return issue(K.STALE)
        # Only correlation/scope, never scope's desired values, enters the reader.
        if binding.expected_diff_ref != correlations.expected_diff_ref or {
            p.object_id for p in scope.objects
        } != set(correlations.scope_ids):
            return issue(K.UNRESOLVED)
        evidence = sim.derive_actual(base, run.state, run.receipt, correlations)
        if evidence.actual is None or not evidence.complete:
            return issue(K.UNKNOWN, "Incomplete synthetic observation")
        return available((snapshot(run.state.snapshot), evidence.actual), self.acquisition)


@dataclass
class SyntheticResolution:
    """TEST_ONLY_SUPPORT: pre-supplied IR, not a native resolver."""

    supplied: o.RuntimeAdmissionEvidence
    failure: rp.PortIssue | None = None

    def resolve_execution(
        self,
        authorized: o.AuthorizedEdit,
        currentness: rp.PortValue[rp.CurrentnessPayload],
    ) -> rp.PortResult[rp.ResolutionPayload]:
        if self.failure is not None:
            return self.failure
        facts = currentness.value[1]
        inputs = replace(
            self.supplied.validation_inputs,
            current_snapshot=facts.current_snapshot,
            authorization_current=facts.authorization_current,
        )
        return available(
            (
                inputs,
                self.supplied.transaction_definition,
                self.supplied.precommit_facts.targets_resolvable,
                self.supplied.precommit_facts.executor_ready,
            )
        )


def admit_from_ports(
    auth: o.AuthorizedEdit,
    work: a.CandidateWorkState,
    observer: rp.RuntimeObservationPort,
    resolver: rp.ExecutionResolutionPort,
    recovery: rp.PortResult[n.ObservedValue],
) -> o.AdmissionResult | rp.PortIssue:
    """TEST_ONLY_SUPPORT thin assembly; no defaults for missing facts."""
    if isinstance(recovery, rp.PortIssue):
        return recovery
    current = observer.observe_currentness(
        auth.authorization,
        auth.prepared.safety,
        available(work),
        recovery,
        purpose="admission",
    )
    if isinstance(current, rp.PortIssue):
        return current
    resolved = resolver.resolve_execution(auth, current)
    if isinstance(resolved, rp.PortIssue):
        return resolved
    inputs, definition, targets, executor = resolved.value
    facts = current.value[1]
    precommit = t.PrecommitFacts(
        facts.binding,
        facts.authorization_ref,
        facts.current_snapshot,
        auth.prepared.safety.status,
        auth.prepared.safety.verdict,
        facts.authorization_current,
        facts.safety_pass_current,
        targets,
        executor,
        facts.recovery_required,
    )
    return o.admit_execution(auth, o.RuntimeAdmissionEvidence(inputs, definition, precommit), work)


def admission(*, rollback: bool = False) -> o.AdmissionResult:
    auth, work = authorized()
    supplied = runtime_admission(auth)
    if rollback:
        cap = t.RollbackCapability.SUPPORTED_VERIFIED
        supplied = replace(
            supplied,
            validation_inputs=replace(
                supplied.validation_inputs,
                manifest=replace(supplied.validation_inputs.manifest, rollback_capability=cap),
            ),
            transaction_definition=replace(
                supplied.transaction_definition,
                rollback=t.RollbackSettings(cap, t.RollbackPolicy.AUTO_ELIGIBLE),
            ),
        )
    result = o.admit_execution(auth, supplied, work)
    assert result.transaction is not None
    return result


@dataclass
class SyntheticReadProducer:
    """TEST_ONLY_SUPPORT: explicitly supplied read evidence, not command acknowledgment."""

    reconciliation: rp.PortResult[t.StepReconciliation]
    base_verification: rp.PortResult[t.BaseVerificationEvidence]
    read_calls: int = 0

    def observe_reconciliation(self) -> rp.PortResult[t.StepReconciliation]:
        self.read_calls += 1
        return self.reconciliation

    def observe_base(self) -> rp.PortResult[t.BaseVerificationEvidence]:
        self.read_calls += 1
        return self.base_verification


@dataclass
class SyntheticLifecycle:
    """TEST_ONLY_SUPPORT scripted events; no native command or second state machine."""

    mode: Literal[
        "refuse", "missing", "unknown", "success", "failed", "defect_before", "defect_after"
    ] = "missing"
    read_producer: SyntheticReadProducer | None = None
    latest: t.Transaction | None = None
    dispatches: int = 0

    def observe_recovery_required(
        self,
        authorization: t.ExecutionAuthorization,
    ) -> rp.PortResult[n.ObservedValue]:
        # No session recovery ledger exists in this fixture. Never infer FALSE.
        return available(V.UNKNOWN)

    def execute_next(
        self,
        admission: o.AdmissionResult,
        transaction: t.Transaction,
    ) -> rp.LifecycleResult:
        prefix = admission.transaction
        if (
            prefix is None
            or transaction.journal.events[: len(prefix.journal.events)] != prefix.journal.events
        ):
            raise ValueError("Programming contract violation: wrong admission prefix")
        if self.latest is not None and transaction != self.latest:
            raise ValueError("Programming contract violation: journal regression")
        self.latest = transaction
        if transaction.state.unresolved_step_outcome:
            return transaction, issue(K.UNKNOWN, "Stop; never retry uncertain dispatch")
        if self.mode == "defect_before":
            raise ValueError("Synthetic instrumentation defect before dispatch")
        if self.mode == "refuse":
            return transaction, issue(K.UNAVAILABLE)
        step = next(
            p.step_ref
            for p in transaction.state.steps
            if p.status == t.ExecutionStepStatus.NOT_STARTED
        )
        self.latest = append_event(transaction, E.STEP_STARTED, step)
        # This models the event order explicitly; it invokes no executor.
        self.dispatches += 1
        try:
            if self.mode == "defect_after":
                raise RuntimeError("Synthetic loss of instrumentation after possible dispatch")
        except RuntimeError:
            self.latest = append_event(
                self.latest,
                E.STEP_OUTCOME_UNKNOWN,
                t.ExecutionStepResult(
                    step,
                    t.ExecutionStepStatus.OUTCOME_UNKNOWN,
                    "test-dispatch-uncertainty-report",
                    True,
                ),
            )
            return self.latest, issue(K.UNKNOWN, "Instrumentation lost; STOP")
        if self.mode == "missing":
            return self.latest, issue(K.UNKNOWN, "No outcome report; retain active step")
        status, kind = {
            "unknown": (t.ExecutionStepStatus.OUTCOME_UNKNOWN, E.STEP_OUTCOME_UNKNOWN),
            "success": (t.ExecutionStepStatus.SUCCEEDED, E.STEP_SUCCEEDED),
            "failed": (t.ExecutionStepStatus.FAILED, E.STEP_FAILED),
        }[self.mode]
        self.latest = append_event(
            self.latest, kind, t.ExecutionStepResult(step, status, "test-command-report", True)
        )
        return self.latest, issue(
            K.UNKNOWN
        ) if status == t.ExecutionStepStatus.OUTCOME_UNKNOWN else None

    def reconcile(
        self,
        admission: o.AdmissionResult,
        transaction: t.Transaction,
    ) -> rp.LifecycleResult:
        self.latest = transaction
        if self.read_producer is None:
            return transaction, issue(K.UNAVAILABLE, "Command report is not observation")
        observed = self.read_producer.observe_reconciliation()
        if isinstance(observed, rp.PortIssue):
            return transaction, observed
        proof = observed.value
        if proof.observed_snapshot != proof.current_snapshot:
            return transaction, issue(K.STALE)
        self.latest = append_event(transaction, E.RECONCILIATION_RECORDED, proof)
        return self.latest, None

    def rollback(
        self, admission: o.AdmissionResult, transaction: t.Transaction, request: t.RollbackRequest
    ) -> rp.LifecycleResult:
        self.latest = append_event(transaction, E.ROLLBACK_STARTED, request)
        self.latest = append_event(
            self.latest,
            E.ROLLBACK_COMMAND_COMPLETED,
            t.RollbackCommandReport("test-rollback-ack", t.ExecutionStepStatus.SUCCEEDED),
        )
        if self.read_producer is None:
            return self.latest, issue(K.UNKNOWN, "Acknowledgment is not verified recovery")
        observed = self.read_producer.observe_base()
        if isinstance(observed, rp.PortIssue):
            return self.latest, observed
        proof = observed.value
        if proof.status != d.DiffVerificationStatus.MATCH:
            return self.latest, issue(K.UNKNOWN, "Read did not establish base recovery")
        if proof.observed_snapshot != proof.current_snapshot:
            return self.latest, issue(K.STALE)
        self.latest = append_event(self.latest, E.ROLLBACK_VERIFIED, proof)
        self.latest = append_event(
            self.latest, E.TRANSACTION_TERMINATED, t.TransactionOutcome.FAILED_PARTIAL_RECOVERED
        )
        return self.latest, None


@dataclass
class SyntheticResultIdentity:
    """TEST_ONLY_SUPPORT: no result IDs, versions, or records constructed here."""

    reply: rp.PortResult[o.ApplicationResultEvidence]

    def resolve_application_result(
        self,
        authorized: o.AuthorizedEdit,
        transaction: t.Transaction,
        postflight: rp.PortValue[rp.PostflightPayload],
    ) -> rp.PortResult[o.ApplicationResultEvidence]:
        return self.reply


@dataclass(frozen=True)
class SyntheticAuthority:
    """TEST_ONLY_SUPPORT response fixture only; no store, writes, or concurrency algorithm."""

    state: rp.PortResult[a.CandidateWorkState]
    publication: rp.PortResult[rp.PublicationDisposition]

    def read(self, candidate_id: a.CandidateId) -> rp.PortResult[a.CandidateWorkState]:
        return self.state

    def publish(
        self,
        expected: rp.PortValue[a.CandidateWorkState],
        proposal: o.FinalizationResult,
        promotion: rp.PortValue[rp.CurrentnessPayload],
    ) -> rp.PortResult[rp.PublicationDisposition]:
        return self.publication


def gated_finalization(
    runtime: o.RuntimeFinalizationEvidence,
    post: rp.PortValue[rp.CurrentnessPayload],
    promotion: rp.PortValue[rp.CurrentnessPayload],
    acquisition_order: tuple[str, ...],
) -> o.RuntimeFinalizationEvidence:
    """TEST_ONLY_SUPPORT producer acquisition schedule, not a native ordering proof.

    Models the integration obligation that orchestration cannot authenticate.
    Receipt labels alone are intentionally ignored when checking this schedule.
    """
    p, q = post.receipt.acquisition_ref, promotion.receipt.acquisition_ref
    fresh = (
        p is not None
        and q is not None
        and p != q
        and p in acquisition_order
        and q in acquisition_order
        and acquisition_order.index(p) < acquisition_order.index(q)
    )
    return replace(
        runtime,
        postflight_facts=post.value[1],
        postflight_observation_ref=post.receipt.receipt_ref,
        promotion_facts=promotion.value[1] if fresh else None,
        promotion_observation_ref=promotion.receipt.receipt_ref if fresh else None,
    )


@pytest.mark.parametrize("field", ["authorization_current", "safety_current"])
def test_same_token_unknown_currentness_blocks_admission(field: str) -> None:
    auth, work = authorized()
    observer = SyntheticObserver(auth.prepared.binding.base_snapshot)
    setattr(observer, field, V.UNKNOWN)
    result = admit_from_ports(
        auth, work, observer, SyntheticResolution(runtime_admission(auth)), available(V.FALSE)
    )
    assert isinstance(result, o.AdmissionResult)
    assert result.evidence.precommit_facts.current_snapshot == auth.prepared.binding.base_snapshot
    assert result.status == o.CompositionStatus.BLOCKED and result.transaction is None


def test_unknown_recovery_returns_issue_before_boolean_facts() -> None:
    auth, work = authorized()
    observer = SyntheticObserver(auth.prepared.binding.base_snapshot)
    lifecycle: rp.ExecutionLifecyclePort = SyntheticLifecycle()
    result = admit_from_ports(
        auth,
        work,
        observer,
        SyntheticResolution(runtime_admission(auth)),
        lifecycle.observe_recovery_required(auth.authorization),
    )
    assert isinstance(result, rp.PortIssue) and result.kind == K.UNKNOWN
    assert observer.facts_constructed == 0


def test_known_recovery_required_blocks_without_becoming_false() -> None:
    auth, work = authorized()
    result = admit_from_ports(
        auth,
        work,
        SyntheticObserver(auth.prepared.binding.base_snapshot),
        SyntheticResolution(runtime_admission(auth)),
        available(V.TRUE),
    )
    assert isinstance(result, o.AdmissionResult)
    assert result.evidence.precommit_facts.recovery_required is True
    assert result.transaction is None


def test_existing_admission_components_are_reused() -> None:
    auth, work = authorized()
    supplied = runtime_admission(auth)
    result = admit_from_ports(
        auth,
        work,
        SyntheticObserver(auth.prepared.binding.base_snapshot),
        SyntheticResolution(supplied),
        available(V.FALSE),
    )
    assert isinstance(result, o.AdmissionResult) and result.status == o.CompositionStatus.READY
    assert result.evidence.transaction_definition is supplied.transaction_definition
    assert result.evidence.validation_inputs.execution_ir is supplied.validation_inputs.execution_ir


@pytest.mark.parametrize("kind", list(K))
def test_ordinary_uncertainty_is_typed_and_not_an_empty_success(kind: rp.PortIssueKind) -> None:
    auth, work = authorized()
    failure = issue(kind)
    result = admit_from_ports(
        auth,
        work,
        SyntheticObserver(auth.prepared.binding.base_snapshot),
        SyntheticResolution(runtime_admission(auth), failure),
        available(V.FALSE),
    )
    assert result is failure and result.kind == kind
    assert not isinstance(result, rp.PortValue)


@pytest.mark.parametrize("mode", ["missing", "unknown", "defect_after"])
def test_uncertain_dispatch_preserves_latest_journal_and_never_retries(
    mode: Literal["missing", "unknown", "defect_after"],
) -> None:
    admitted = admission()
    original = admitted.transaction
    assert original is not None
    implementation = SyntheticLifecycle(mode)
    port: rp.ExecutionLifecyclePort = implementation
    latest, failure = port.execute_next(admitted, original)
    assert latest is implementation.latest
    assert latest.journal.events[: len(original.journal.events)] == original.journal.events
    assert latest.journal.events[len(original.journal.events)].kind == E.STEP_STARTED
    assert latest.state.unresolved_step_outcome
    assert failure is not None and failure.kind == K.UNKNOWN
    assert implementation.dispatches == 1
    if mode == "missing":
        assert latest.state.active_step_ref == "step"
        assert latest.journal.events[-1].kind == E.STEP_STARTED
    else:
        assert latest.journal.events[-1].kind == E.STEP_OUTCOME_UNKNOWN
        assert latest.state.steps[0].status == t.ExecutionStepStatus.OUTCOME_UNKNOWN
    repeated, again = port.execute_next(admitted, latest)
    assert repeated is latest and again is not None and implementation.dispatches == 1
    assert all(
        event.kind not in (E.STEP_SUCCEEDED, E.STEP_FAILED) for event in latest.journal.events
    )


def test_predispatch_unavailable_preserves_pre_mutation_history() -> None:
    admitted = admission()
    assert admitted.transaction is not None
    implementation = SyntheticLifecycle("refuse")
    latest, failure = implementation.execute_next(admitted, admitted.transaction)
    assert latest is admitted.transaction and implementation.dispatches == 0
    assert failure is not None and failure.kind == K.UNAVAILABLE
    assert not latest.state.unresolved_step_outcome


def test_programming_violation_may_raise_before_dispatch() -> None:
    admitted = admission()
    assert admitted.transaction is not None
    implementation = SyntheticLifecycle("defect_before")
    with pytest.raises(ValueError, match="before dispatch"):
        implementation.execute_next(admitted, admitted.transaction)
    assert implementation.latest is admitted.transaction and implementation.dispatches == 0


@pytest.mark.parametrize("kind", [K.UNAVAILABLE, K.AMBIGUOUS, K.STALE, K.UNKNOWN])
def test_reconciliation_failure_preserves_unknown_journal(kind: rp.PortIssueKind) -> None:
    admitted = admission()
    assert admitted.transaction is not None
    read = SyntheticReadProducer(issue(kind), issue(K.UNAVAILABLE))
    port = SyntheticLifecycle("unknown", read)
    latest, _ = port.execute_next(admitted, admitted.transaction)
    returned, failure = port.reconcile(admitted, latest)
    assert returned is latest and failure is read.reconciliation
    assert returned.state.unresolved_step_outcome and read.read_calls == 1


def test_reconciliation_requires_independent_observation_not_command_report() -> None:
    admitted = admission()
    assert admitted.transaction is not None
    port = SyntheticLifecycle("unknown")
    latest, _ = port.execute_next(admitted, admitted.transaction)
    returned, failure = port.reconcile(admitted, latest)
    assert returned is latest and failure is not None
    assert E.RECONCILIATION_RECORDED not in [e.kind for e in returned.journal.events]
    proof = t.StepReconciliation(
        latest.definition.binding,
        "test-command-report",
        t.ExecutionStepResult(
            "step", t.ExecutionStepStatus.SUCCEEDED, "test-read-classification", True
        ),
        POST,
        POST,
        "test-independent-observation",
    )
    reader = SyntheticReadProducer(available(proof), issue(K.UNAVAILABLE))
    port.read_producer = reader
    reconciled, failure = port.reconcile(admitted, latest)
    assert failure is None and reader.read_calls == 1
    assert reconciled.journal.events[:-1] == latest.journal.events
    assert reconciled.journal.events[-1].payload is proof
    assert not reconciled.state.unresolved_step_outcome
    assert not reconciled.state.retry_eligible and port.dispatches == 1


def test_rollback_ack_alone_does_not_verify_recovery() -> None:
    admitted = admission(rollback=True)
    assert admitted.transaction is not None
    port: rp.ExecutionLifecyclePort = SyntheticLifecycle("failed")
    failed, _ = port.execute_next(admitted, admitted.transaction)
    rolled, uncertainty = port.rollback(admitted, failed, t.RollbackRequest(False))
    assert rolled.journal.events[: len(failed.journal.events)] == failed.journal.events
    assert rolled.journal.events[-1].kind == E.ROLLBACK_COMMAND_COMPLETED
    assert rolled.state.base_verification is None
    assert rolled.state.outcome == t.TransactionOutcome.NONE
    assert uncertainty is not None and uncertainty.kind == K.UNKNOWN
    recovery = port.observe_recovery_required(admitted.authorized.authorization)
    assert isinstance(recovery, rp.PortValue) and recovery.value == V.UNKNOWN


def test_rollback_verification_uses_read_producer() -> None:
    admitted = admission(rollback=True)
    assert admitted.transaction is not None
    binding = admitted.transaction.definition.binding
    proof = t.BaseVerificationEvidence(
        "test-base-read",
        binding,
        d.DiffVerificationStatus.MATCH,
        binding.base_snapshot,
        binding.base_snapshot,
    )
    read = SyntheticReadProducer(issue(K.UNAVAILABLE), available(proof))
    port = SyntheticLifecycle("failed", read)
    failed, _ = port.execute_next(admitted, admitted.transaction)
    recovered, failure = port.rollback(admitted, failed, t.RollbackRequest(False))
    assert failure is None and read.read_calls == 1
    assert recovered.state.base_verification is proof
    assert recovered.state.outcome == t.TransactionOutcome.FAILED_PARTIAL_RECOVERED


def test_actual_diff_independent_of_changed_expected_effects() -> None:
    request = fixture()
    run = sim.execute(request, request.base, POST)
    observer: rp.RuntimeObservationPort = SyntheticObserver(
        POST,
        simulation=(request.base, run, sim.correlations(request)),
    )
    auth, work = authorized()
    before = SyntheticObserver(request.base.snapshot).observe_currentness(
        auth.authorization,
        auth.prepared.safety,
        available(work),
        available(V.FALSE),
        purpose="admission",
    )
    assert isinstance(before, rp.PortValue)
    original = request.diff
    changed_inputs = replace(
        original.inputs,
        participation=replace(
            original.inputs.participation,
            participants=(),
        ),
    )
    changed = d.compile_expected_diff(changed_inputs).expected_diff
    assert changed is not None and changed.displacements != original.displacements
    actuals = []
    history = admission().transaction
    assert history is not None
    for expected in (original, changed):
        result = observer.observe_postflight(
            t.ArtifactBinding(
                expected.expected_diff_ref, request.safety_ref, expected.base_snapshot
            ),
            expected.inputs.scope,
            before,
            targets=(),
            transaction=history,
        )
        assert isinstance(result, rp.PortValue)
        actuals.append(result.value[1])
    assert actuals[0] == actuals[1]
    assert (
        d._verify_legacy_semantics(original, actuals[0], POST).status
        == d.DiffVerificationStatus.MATCH
    )
    assert (
        d._verify_legacy_semantics(changed, actuals[1], POST).status
        == d.DiffVerificationStatus.MISMATCH
    )


@pytest.mark.parametrize("relabel", ["none", "receipt", "receipt_and_acquisition"])
def test_reused_or_relabelled_observation_does_not_make_promotion_fresh(relabel: str) -> None:
    auth, runtime, work = completion()
    assert runtime.postflight_facts is not None
    post = available((snapshot(POST), runtime.postflight_facts), "test-post-capture")
    promotion = post
    if relabel != "none":
        promotion = replace(post, receipt=replace(post.receipt, receipt_ref="new-label"))
    if relabel == "receipt_and_acquisition":
        promotion = replace(
            promotion, receipt=replace(promotion.receipt, acquisition_ref="invented")
        )
    assembled = gated_finalization(runtime, post, promotion, ("test-post-capture",))
    result = o.finalize_edit(auth, assembled, work)
    assert result.transaction_outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    assert result.authority_after is work
    assert result.diagnostics == ("FRESH_PROMOTION_FACTS_MISSING",)


def test_separate_acquisitions_and_existing_orchestration_ref_guard() -> None:
    auth, runtime, work = completion()
    assert runtime.postflight_facts is not None and runtime.promotion_facts is not None
    post = available((snapshot(POST), runtime.postflight_facts), "capture-1")
    promotion = available((snapshot(POST), runtime.promotion_facts), "capture-2")
    # Separate acquisitions with the same public observation ref still fail VS-001E.
    assembled = gated_finalization(runtime, post, promotion, ("capture-1", "capture-2"))
    rejected = o.finalize_edit(auth, assembled, work)
    assert rejected.diagnostics == ("FRESH_PROMOTION_FACTS_MISSING",)
    promotion = replace(promotion, receipt=replace(promotion.receipt, receipt_ref="promotion-ref"))
    assembled = gated_finalization(runtime, post, promotion, ("capture-1", "capture-2"))
    accepted = o.finalize_edit(auth, assembled, work)
    assert accepted.authority_after.candidate.promotion == a.PromotionState.PROMOTED
    assert accepted.durable_promotion == "NOT_PERFORMED"


@pytest.mark.parametrize("kind", [K.UNAVAILABLE, K.UNRESOLVED, K.AMBIGUOUS, K.STALE, K.UNKNOWN])
def test_missing_result_identity_keeps_commit_and_blocks_promotion(kind: rp.PortIssueKind) -> None:
    auth, runtime, work = completion()
    committed = o.finalize_edit(auth, replace(runtime, promotion_facts=None), work)
    assert runtime.actual_diff is not None
    port: rp.ApplicationResultPort = SyntheticResultIdentity(issue(kind))
    result = port.resolve_application_result(
        auth,
        committed.transaction,
        available((snapshot(POST), runtime.actual_diff)),
    )
    assert isinstance(result, rp.PortIssue) and result.kind == kind
    finalized = o.finalize_edit(
        auth,
        replace(
            runtime,
            transaction=committed.transaction,
            prior_postflight=committed.postflight_record,
            application_result=None,
        ),
        work,
    )
    assert finalized.transaction is committed.transaction
    assert finalized.transaction_outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    assert finalized.authority_after is work and finalized.diagnostics == (
        "APPLICATION_RESULT_MISSING",
    )


def test_resolved_identity_returns_only_supplied_record() -> None:
    auth, runtime, _ = completion()
    assert runtime.application_result is not None and runtime.actual_diff is not None
    supplied = available(runtime.application_result)
    port: rp.ApplicationResultPort = SyntheticResultIdentity(supplied)
    assert (
        port.resolve_application_result(
            auth,
            runtime.transaction,
            available((snapshot(POST), runtime.actual_diff)),
        )
        is supplied
    )


def test_human_change_after_commit_preserves_history() -> None:
    auth, runtime, work = completion()
    first = o.finalize_edit(auth, replace(runtime, promotion_facts=None), work)
    human_snapshot = replace(POST, timeline_version=TimelineVersion(3), state_token="test-human")
    human_state = a.transition(
        work,
        a.ObserveHumanVersion(
            a.CandidateBase(
                human_snapshot.timeline_id,
                human_snapshot.timeline_version,
            )
        ),
    ).state
    authority: rp.AuthorityPort = SyntheticAuthority(available(human_state), issue(K.STALE))
    loaded = authority.read(work.candidate.candidate_id)
    assert isinstance(loaded, rp.PortValue)
    current = SyntheticObserver(human_snapshot).observe_currentness(
        auth.authorization,
        auth.prepared.safety,
        loaded,
        available(V.FALSE),
        purpose="promotion",
    )
    assert isinstance(current, rp.PortValue)
    final = o.finalize_edit(
        auth,
        replace(
            runtime,
            transaction=first.transaction,
            prior_postflight=first.postflight_record,
            promotion_facts=current.value[1],
        ),
        loaded.value,
    )
    assert final.transaction is first.transaction
    assert final.transaction_outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    assert final.authority_after is human_state
    assert final.promotion_eligibility == t.PromotionEligibility.NOT_ELIGIBLE


@pytest.mark.parametrize("kind", [K.STALE, K.CONFLICT, K.UNAVAILABLE, K.UNKNOWN])
def test_persistence_non_success_is_distinct_and_preserves_history(kind: rp.PortIssueKind) -> None:
    auth, runtime, work = completion()
    proposal = o.finalize_edit(auth, runtime, work)
    assert runtime.promotion_facts is not None
    before = proposal.transaction.journal
    scripted = issue(kind)
    port: rp.AuthorityPort = SyntheticAuthority(available(work), scripted)
    reply = port.publish(
        available(work), proposal, available((snapshot(POST), runtime.promotion_facts))
    )
    assert reply is scripted and reply.kind == kind
    assert proposal.transaction.journal is before
    assert proposal.transaction_outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    assert proposal.durable_promotion == "NOT_PERFORMED"


@pytest.mark.parametrize("disposition", ["PERSISTED", "DUPLICATE"])
def test_publication_success_requires_separate_supplied_receipt(
    disposition: rp.PublicationDisposition,
) -> None:
    auth, runtime, work = completion()
    proposal = o.finalize_edit(auth, runtime, work)
    assert runtime.promotion_facts is not None
    supplied = available(disposition, "test-prior-durable-publication")
    port: rp.AuthorityPort = SyntheticAuthority(available(work), supplied)
    reply = port.publish(
        available(work), proposal, available((snapshot(POST), runtime.promotion_facts))
    )
    assert reply is supplied
    assert proposal.durable_promotion == "NOT_PERFORMED"
    # This frozen fixture neither compares state nor implements a store.
    assert isinstance(port, SyntheticAuthority) and isinstance(port.state, rp.PortValue)
    assert port.state.value is work


def test_test_only_receipt_does_not_claim_native_qualification() -> None:
    supplied = available(V.TRUE)
    assert supplied.receipt.evidence_domain == "TEST_ONLY_SUPPORT"
    assert supplied.receipt.limitations
    assert snapshot(POST).capture_consistency == n.CaptureConsistency.UNVERIFIED
    with pytest.raises(FrozenInstanceError):
        supplied.receipt.receipt_ref = "rewrite"  # type: ignore[misc]
    with pytest.raises(ValueError, match="not qualification"):
        replace(supplied.receipt, evidence_domain="NATIVE_VERIFIED")  # type: ignore[arg-type]


def test_public_protocols_are_neutral_and_production_is_declarations_only() -> None:
    source = Path(rp.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    protocols = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(isinstance(base, ast.Name) and base.id == "Protocol" for base in node.bases)
    ]
    assert {node.name for node in protocols} == {
        "RuntimeObservationPort",
        "ExecutionResolutionPort",
        "ExecutionLifecyclePort",
        "ApplicationResultPort",
        "AuthorityPort",
    }
    for protocol in protocols:
        text = ast.get_source_segment(source, protocol)
        assert text is not None
        for forbidden in (
            "studio",
            "free",
            "lua",
            "python",
            "ipc",
            "filesystem",
            "socket",
            "clipboard",
        ):
            assert forbidden not in text.lower()
        for method in (node for node in protocol.body if isinstance(node, ast.FunctionDef)):
            body = method.body[1:] if ast.get_docstring(method) else method.body
            assert len(body) == 1 and isinstance(body[0], ast.Expr)
            assert isinstance(body[0].value, ast.Constant) and body[0].value.value is Ellipsis
    assert {node.name for node in tree.body if isinstance(node, ast.ClassDef)} == {
        *(node.name for node in protocols),
        "PortIssueKind",
        "PortReceipt",
        "PortValue",
        "PortIssue",
    }
    assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in tree.body)
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports <= {None, "dataclasses", "enum", "typing"}
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    annotations = inspect.signature(rp.RuntimeObservationPort.observe_postflight).parameters
    assert all("ExpectedDiff" not in str(p.annotation) for p in annotations.values())
