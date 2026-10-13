"""TEST_ONLY_SUPPORT: scripted producers and existing simulation, no native qualification."""

import ast
from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Literal, TypeVar

import pytest
from test_orchestration import completion, runtime_admission
from test_runtime_ports import SyntheticLifecycle, SyntheticReadProducer, snapshot

from davinci_ai_editor import authority as a
from davinci_ai_editor import execution_ir as ir
from davinci_ai_editor import expected_diff as d
from davinci_ai_editor import native_snapshot as n
from davinci_ai_editor import orchestration as o
from davinci_ai_editor import runtime_integration as i
from davinci_ai_editor import runtime_ports as p
from davinci_ai_editor import safety_preflight as s
from davinci_ai_editor import transaction as t
from davinci_ai_editor.domain import TimelineVersion
from davinci_ai_editor.temporal_mapping import NativeSnapshotRef

T = TypeVar("T")
V, E, K = n.ObservedValue, t.TransactionEventKind, p.PortIssueKind


def supplied(value: T, ref: str, sources: tuple[str, ...] = ()) -> p.PortValue[T]:
    return p.PortValue(
        value,
        p.PortReceipt(
            ref,
            "TEST_ONLY_SUPPORT",
            ref,
            sources,
            ("Synthetic; no authenticity or atomic dispatch proof",),
            "TEST_ONLY_SUPPORT",
        ),
    )


def issue(kind: p.PortIssueKind) -> p.PortIssue:
    return p.PortIssue(
        kind,
        "TEST_ONLY_SUPPORT ordinary uncertainty",
        p.PortReceipt(
            "test-issue", "TEST_ONLY_SUPPORT", None, (), ("Synthetic",), "TEST_ONLY_SUPPORT"
        ),
    )


def multiple_steps(value: o.RuntimeAdmissionEvidence) -> o.RuntimeAdmissionEvidence:
    """TEST_ONLY_SUPPORT explicit per-op lowering, using existing immutable types."""
    v = value.validation_inputs
    template = v.lowering.steps[0]
    recon = template.reconciliation
    assert recon is not None
    steps = []
    realizations = []
    for index, op in enumerate(v.execution_ir.ops):
        ref = f"step-{index}"
        step = replace(
            template,
            step_ref=ref,
            target_refs=(op.target_ref,),
            reconciliation=replace(recon, step_ref=ref, reconciliation_ref=f"read-{index}"),
        )
        model = replace(
            v.lowering.realizations[0].effect_model,
            effect_model_ref=f"model-{index}",
            step_refs=(ref,),
            op_refs=(op.op_ref,),
            predicted_effects=(op.effect,),
            possible_subjects=(op.effect.before.object_id,),
        )
        steps.append(step)
        realizations.append(
            ir.LoweringRealization(f"realization-{index}", (op.op_ref,), (ref,), model)
        )
    return replace(
        value,
        validation_inputs=replace(
            v, lowering=replace(v.lowering, steps=tuple(steps), realizations=tuple(realizations))
        ),
        transaction_definition=replace(
            value.transaction_definition, step_refs=tuple(step.step_ref for step in steps)
        ),
    )


class Harness:
    """TEST_ONLY_SUPPORT response scripts; all five structural Protocols, no store."""

    def __init__(self, *, multi: bool = False, rollback: bool = False) -> None:
        self.auth, self.completed, self.work = completion()
        self.admission_data = runtime_admission(self.auth)
        if multi:
            self.admission_data = multiple_steps(self.admission_data)
        if rollback:
            cap = t.RollbackCapability.SUPPORTED_VERIFIED
            value = self.admission_data
            self.admission_data = replace(
                value,
                transaction_definition=replace(
                    value.transaction_definition,
                    rollback=t.RollbackSettings(cap, t.RollbackPolicy.AUTO_ELIGIBLE),
                ),
                validation_inputs=replace(
                    value.validation_inputs,
                    manifest=replace(value.validation_inputs.manifest, rollback_capability=cap),
                ),
            )
        self.script = SyntheticLifecycle("success")
        self.trace: list[str] = []
        self.faults: dict[str, p.PortIssue] = {}
        self.reads = 0
        self.recoveries = 0
        self.current_calls = 0
        self.publications = 0
        self.recovery = V.FALSE
        self.auth_current = V.TRUE
        self.safety_current = V.TRUE
        self.promotion_mode = "normal"
        self.reuse_authority = False
        self.first_read: p.PortValue[a.CandidateWorkState] | None = None
        self.post_current: p.PortValue[p.CurrentnessPayload] | None = None
        self.current_snapshot: NativeSnapshotRef | None = None
        self.post_override: d.ActualDiff | None = None
        self.post_reply: p.PortValue[p.PostflightPayload] | None = None
        self.bad_resolution = False
        self.bad_resolution_sources = False
        self.raise_resolution = False
        self.publish_exception: Exception | None = None
        self.execution_override: (
            Callable[[o.AdmissionResult, t.Transaction], p.LifecycleResult] | None
        ) = None
        self.last_lifecycle: p.LifecycleResult | None = None
        self.publication_reply: p.PortResult[p.PublicationDisposition] = supplied(
            "PERSISTED", "publication"
        )
        self.publish_arguments: (
            tuple[
                p.PortValue[a.CandidateWorkState],
                o.FinalizationResult,
                p.PortValue[p.CurrentnessPayload],
            ]
            | None
        ) = None

    def read(self, candidate_id: a.CandidateId) -> p.PortResult[a.CandidateWorkState]:
        self.trace.append("authority.read")
        self.reads += 1
        if "authority" in self.faults:
            return self.faults["authority"]
        if self.reuse_authority and self.first_read is not None:
            return self.first_read
        value = supplied(self.work, f"authority-{self.reads}")
        if self.first_read is None:
            self.first_read = value
        return value

    def observe_recovery_required(
        self,
        authorization: t.ExecutionAuthorization,
    ) -> p.PortResult[n.ObservedValue]:
        self.trace.append("recovery")
        self.recoveries += 1
        return self.faults.get("recovery", supplied(self.recovery, f"recovery-{self.recoveries}"))

    def observe_currentness(
        self,
        authorization: t.ExecutionAuthorization,
        safety: s.SafetyPreflightResult,
        authority: p.PortValue[a.CandidateWorkState],
        recovery: p.PortValue[n.ObservedValue],
        *,
        purpose: Literal["admission", "postflight", "promotion"],
    ) -> p.PortResult[p.CurrentnessPayload]:
        self.trace.append(f"currentness.{purpose}")
        self.current_calls += 1
        if "currentness" in self.faults:
            return self.faults["currentness"]
        assert recovery.value != V.UNKNOWN
        ref = self.current_snapshot or (
            authorization.binding.base_snapshot
            if purpose == "admission"
            else self.completed.current_post_snapshot
        )
        acquisition = f"current-{purpose}-{self.current_calls}"
        facts = t.CurrentAuthorityFacts(
            authorization.binding,
            authorization.authorization_ref,
            ref,
            self.auth_current,
            self.safety_current,
            recovery.value == V.TRUE,
        )
        value = supplied(
            (snapshot(ref, acquisition), facts),
            acquisition,
            (authority.receipt.receipt_ref, recovery.receipt.receipt_ref),
        )
        if purpose == "postflight":
            self.post_current = value
        if purpose == "promotion" and self.promotion_mode != "normal":
            old = self.post_current
            assert old is not None
            if self.promotion_mode == "same_object":
                return old
            if self.promotion_mode == "same_acquisition":
                return replace(
                    value,
                    receipt=replace(value.receipt, acquisition_ref=old.receipt.acquisition_ref),
                )
            if self.promotion_mode == "relabel":
                return replace(old, receipt=replace(old.receipt, receipt_ref="relabel"))
            if self.promotion_mode == "same_capture":
                return replace(value, value=(old.value[0], facts))
            if self.promotion_mode == "no_acquisition":
                return replace(value, receipt=replace(value.receipt, acquisition_ref=None))
            if self.promotion_mode == "no_sources":
                return replace(value, receipt=replace(value.receipt, source_refs=()))
            if self.promotion_mode == "missing_recovery_source":
                return replace(
                    value,
                    receipt=replace(value.receipt, source_refs=(authority.receipt.receipt_ref,)),
                )
        return value

    def resolve_execution(
        self,
        authorized: o.AuthorizedEdit,
        currentness: p.PortValue[p.CurrentnessPayload],
    ) -> p.PortResult[p.ResolutionPayload]:
        self.trace.append("resolution")
        if self.raise_resolution:
            raise ValueError("TEST_ONLY_SUPPORT programming defect before any dispatch")
        if "resolution" in self.faults:
            return self.faults["resolution"]
        inputs = self.admission_data.validation_inputs
        if not self.bad_resolution:
            inputs = replace(
                inputs,
                current_snapshot=currentness.value[1].current_snapshot,
                authorization_current=currentness.value[1].authorization_current,
            )
        result = (
            inputs,
            self.admission_data.transaction_definition,
            self.admission_data.precommit_facts.targets_resolvable,
            self.admission_data.precommit_facts.executor_ready,
        )
        return supplied(
            result,
            "resolution",
            () if self.bad_resolution_sources else (currentness.receipt.receipt_ref,),
        )

    def execute_next(
        self,
        admission: o.AdmissionResult,
        transaction: t.Transaction,
    ) -> p.LifecycleResult:
        self.trace.append("execute")
        value = (
            self.execution_override(admission, transaction)
            if self.execution_override is not None
            else self.script.execute_next(admission, transaction)
        )
        self.last_lifecycle = value
        return value

    def reconcile(
        self,
        admission: o.AdmissionResult,
        transaction: t.Transaction,
    ) -> p.LifecycleResult:
        self.trace.append("reconcile")
        value = self.script.reconcile(admission, transaction)
        self.last_lifecycle = value
        return value

    def rollback(
        self, admission: o.AdmissionResult, transaction: t.Transaction, request: t.RollbackRequest
    ) -> p.LifecycleResult:
        self.trace.append("rollback")
        value = self.script.rollback(admission, transaction, request)
        self.last_lifecycle = value
        return value

    def observe_postflight(
        self,
        binding: t.ArtifactBinding,
        scope: d.PreservationScope,
        before: p.PortValue[p.CurrentnessPayload],
    ) -> p.PortResult[p.PostflightPayload]:
        self.trace.append("postflight")
        if "postflight" in self.faults:
            return self.faults["postflight"]
        # Already supplied observation produced by the existing independent simulator.
        # This method has no ExpectedDiff input and never measures values from scope.
        actual = self.post_override or self.completed.actual_diff
        assert actual is not None
        self.post_reply = supplied(
            (snapshot(actual.post_snapshot, "post-observation"), actual),
            "post-observation",
            (before.receipt.receipt_ref,),
        )
        return self.post_reply

    def resolve_application_result(
        self,
        authorized: o.AuthorizedEdit,
        transaction: t.Transaction,
        postflight: p.PortValue[p.PostflightPayload],
    ) -> p.PortResult[o.ApplicationResultEvidence]:
        self.trace.append("identity")
        if "identity" in self.faults:
            return self.faults["identity"]
        value = self.completed.application_result
        assert value is not None
        return supplied(value, "identity", (postflight.receipt.receipt_ref,))

    def publish(
        self,
        expected: p.PortValue[a.CandidateWorkState],
        proposal: o.FinalizationResult,
        promotion: p.PortValue[p.CurrentnessPayload],
    ) -> p.PortResult[p.PublicationDisposition]:
        self.trace.append("publish")
        self.publications += 1
        self.publish_arguments = expected, proposal, promotion
        if self.publish_exception is not None:
            raise self.publish_exception
        return self.publication_reply

    def admitted(self) -> i.IntegrationEvidence:
        result = i.compose_admission(
            self.auth, authority=self, lifecycle=self, observations=self, resolution=self
        )
        assert isinstance(result.result, o.AdmissionResult)
        assert result.result.status == o.CompositionStatus.READY
        return result.evidence

    def executed(self) -> i.IntegrationEvidence:
        evidence = self.admitted()
        for _ in self.admission_data.transaction_definition.step_refs:
            evidence = i.advance_execution_once(evidence, lifecycle=self).evidence
        return evidence

    def committed(self) -> i.IntegrationEvidence:
        result = i.finalize_postflight(
            self.executed(), "test-verification", observations=self, authority=self, lifecycle=self
        )
        assert isinstance(result.result, o.FinalizationResult)
        assert result.result.transaction_outcome == t.TransactionOutcome.VERIFIED_COMMITTED
        return result.evidence

    def promoted(self) -> i.IntegrationEvidence:
        result = i.prepare_promotion(
            self.committed(), identity=self, authority=self, lifecycle=self, observations=self
        )
        assert isinstance(result.result, o.FinalizationResult)
        assert result.result.authority_after.candidate.promotion == a.PromotionState.PROMOTED
        return result.evidence


def test_admission_order_and_exact_payload_retention() -> None:
    h = Harness()
    evidence = h.admitted()
    assert h.trace == ["authority.read", "recovery", "currentness.admission", "resolution"]
    assert evidence.admission is not None and evidence.admission_inputs is not None
    assert evidence.admission.evidence is evidence.admission_inputs
    assert evidence.transaction is evidence.admission.transaction
    assert evidence.resolution is not None and evidence.admission_currentness is not None
    assert evidence.admission_inputs.validation_inputs is evidence.resolution.value[0]
    assert (
        evidence.admission_inputs.precommit_facts.current_snapshot
        is evidence.admission_currentness.value[1].current_snapshot
    )
    assert evidence.calls[-1].inputs[1] is evidence.admission_inputs
    assert evidence.calls[-1].result is evidence.admission
    assert h.script.dispatches == 0


@pytest.mark.parametrize(
    "stage,count", [("authority", 1), ("recovery", 2), ("currentness", 3), ("resolution", 4)]
)
@pytest.mark.parametrize("kind", list(K))
def test_normal_admission_issues_are_retained_exactly_and_stop(
    stage: str, count: int, kind: p.PortIssueKind
) -> None:
    h = Harness()
    supplied_issue = issue(kind)
    h.faults[stage] = supplied_issue
    result = i.compose_admission(h.auth, authority=h, lifecycle=h, observations=h, resolution=h)
    assert result.result is supplied_issue and result.evidence.calls[-1].result is supplied_issue
    assert len(h.trace) == count and result.evidence.transaction is None


def test_unknown_recovery_stops_before_currentness_call() -> None:
    h = Harness()
    h.recovery = V.UNKNOWN
    result = i.compose_admission(h.auth, authority=h, lifecycle=h, observations=h, resolution=h)
    assert isinstance(result.result, p.PortIssue) and result.result.kind == K.UNKNOWN
    assert h.current_calls == 0 and h.trace == ["authority.read", "recovery"]
    assert isinstance(result.evidence.calls[1].result, p.PortValue)
    assert result.evidence.calls[1].result.value == V.UNKNOWN


@pytest.mark.parametrize(
    "value,status", [(V.UNKNOWN, o.CompositionStatus.BLOCKED), (V.FALSE, o.CompositionStatus.STALE)]
)
def test_admission_blocked_stale_remain_exact(
    value: n.ObservedValue, status: o.CompositionStatus
) -> None:
    h = Harness()
    h.auth_current = value
    result = i.compose_admission(h.auth, authority=h, lifecycle=h, observations=h, resolution=h)
    assert isinstance(result.result, o.AdmissionResult) and result.result.status == status
    assert result.result is result.evidence.admission and result.evidence.transaction is None


@pytest.mark.parametrize("field", ["targets_resolvable", "executor_ready"])
@pytest.mark.parametrize("value", [V.FALSE, V.UNKNOWN])
def test_readiness_is_not_overwritten(field: str, value: n.ObservedValue) -> None:
    h = Harness()
    facts = h.admission_data.precommit_facts
    h.admission_data = replace(
        h.admission_data,
        precommit_facts=(
            replace(facts, targets_resolvable=value)
            if field == "targets_resolvable"
            else replace(facts, executor_ready=value)
        ),
    )
    result = i.compose_admission(h.auth, authority=h, lifecycle=h, observations=h, resolution=h)
    assert (
        isinstance(result.result, o.AdmissionResult)
        and result.result.status == o.CompositionStatus.BLOCKED
    )
    assert getattr(result.result.evidence.precommit_facts, field) is value


@pytest.mark.parametrize("bad_sources", [False, True])
def test_resolution_mismatch_not_repaired(bad_sources: bool) -> None:
    h = Harness()
    h.bad_resolution_sources = bad_sources
    h.bad_resolution = not bad_sources
    h.auth_current = V.UNKNOWN
    result = i.compose_admission(h.auth, authority=h, lifecycle=h, observations=h, resolution=h)
    assert isinstance(result.result, p.PortIssue)
    assert result.evidence.admission is None and result.evidence.resolution is not None


def test_one_step_and_explicit_multiple_advancements() -> None:
    h = Harness(multi=True)
    evidence = h.admitted()
    assert evidence.transaction is not None and len(evidence.transaction.state.steps) == 2
    first = i.advance_execution_once(evidence, lifecycle=h)
    assert h.trace.count("execute") == 1 and h.script.dispatches == 1
    assert first.evidence.transaction is h.last_lifecycle[0] if h.last_lifecycle else False
    assert first.evidence.transaction is not None
    assert [s.status for s in first.evidence.transaction.state.steps] == [
        t.ExecutionStepStatus.SUCCEEDED,
        t.ExecutionStepStatus.NOT_STARTED,
    ]
    second = i.advance_execution_once(first.evidence, lifecycle=h)
    assert h.trace.count("execute") == 2 and h.script.dispatches == 2
    assert second.evidence.transaction is not None and all(
        s.status == t.ExecutionStepStatus.SUCCEEDED for s in second.evidence.transaction.state.steps
    )
    blocked = i.advance_execution_once(second.evidence, lifecycle=h)
    assert isinstance(blocked.result, p.PortIssue) and h.trace.count("execute") == 2


@pytest.mark.parametrize("mode", ["missing", "unknown", "failed", "defect_after"])
def test_unresolved_failed_and_issue_keep_latest_and_stop(
    mode: Literal["missing", "unknown", "failed", "defect_after"],
) -> None:
    h = Harness()
    h.script.mode = mode
    result = i.advance_execution_once(h.admitted(), lifecycle=h)
    assert h.last_lifecycle is not None and result.result is h.last_lifecycle
    assert result.evidence.transaction is h.last_lifecycle[0]
    blocked = i.advance_execution_once(result.evidence, lifecycle=h)
    assert isinstance(blocked.result, p.PortIssue) and h.script.dispatches == 1
    assert blocked.evidence.transaction is result.evidence.transaction


@pytest.mark.parametrize("damage", ["prefix", "definition", "multiple_steps"])
def test_producer_journal_violations_preserve_return_and_poison_further_dispatch(
    damage: str,
) -> None:
    h = Harness(multi=True)
    evidence = h.admitted()
    if damage == "prefix":
        evidence = i.advance_execution_once(evidence, lifecycle=h).evidence

    def corrupt(adm: o.AdmissionResult, tx: t.Transaction) -> p.LifecycleResult:
        assert adm.transaction is not None
        if damage == "prefix":
            return adm.transaction, None
        if damage == "definition":
            return t.prepare_transaction(replace(tx.definition, transaction_ref="other")), None
        latest, _ = h.script.execute_next(adm, tx)
        return h.script.execute_next(adm, latest)

    h.execution_override = corrupt
    result = i.advance_execution_once(evidence, lifecycle=h)
    assert isinstance(result.result, p.PortIssue)
    assert h.last_lifecycle is not None and result.evidence.transaction is h.last_lifecycle[0]
    count = h.trace.count("execute")
    again = i.advance_execution_once(result.evidence, lifecycle=h)
    assert isinstance(again.result, p.PortIssue) and h.trace.count("execute") == count
    assert any(c.operation == "contract_violation" for c in result.evidence.calls)


def test_active_step_is_not_repaired_for_reconciliation() -> None:
    h = Harness()
    h.script.mode = "missing"
    evidence = i.advance_execution_once(h.admitted(), lifecycle=h).evidence
    result = i.reconcile_execution(evidence, lifecycle=h)
    assert isinstance(result.result, p.PortIssue)
    assert result.evidence.transaction is evidence.transaction and "reconcile" not in h.trace


def test_reconciliation_requires_read_and_never_auto_advances() -> None:
    h = Harness(multi=True)
    h.script.mode = "unknown"
    evidence = i.advance_execution_once(h.admitted(), lifecycle=h).evidence
    failed = i.reconcile_execution(evidence, lifecycle=h)
    assert isinstance(failed.result, tuple) and failed.result[1] is not None
    assert failed.evidence.transaction is evidence.transaction
    tx = evidence.transaction
    assert tx is not None
    proof = t.StepReconciliation(
        tx.definition.binding,
        "test-command-report",
        t.ExecutionStepResult(
            tx.state.steps[0].step_ref, t.ExecutionStepStatus.SUCCEEDED, "independent-read", True
        ),
        h.completed.current_post_snapshot,
        h.completed.current_post_snapshot,
        "read-proof",
    )
    read = SyntheticReadProducer(supplied(proof, "read"), issue(K.UNAVAILABLE))
    h.script.read_producer = read
    reconciled = i.reconcile_execution(failed.evidence, lifecycle=h)
    assert reconciled.result is h.last_lifecycle and read.read_calls == 1
    assert h.script.dispatches == 1
    assert reconciled.evidence.transaction is not None
    assert reconciled.evidence.transaction.journal.events[-1].payload is proof
    assert (
        reconciled.evidence.transaction.state.steps[1].status == t.ExecutionStepStatus.NOT_STARTED
    )


@pytest.mark.parametrize("kind", [K.STALE, K.AMBIGUOUS, K.UNKNOWN])
def test_reconciliation_issue_keeps_journal(kind: p.PortIssueKind) -> None:
    h = Harness()
    h.script.mode = "unknown"
    failure = issue(kind)
    h.script.read_producer = SyntheticReadProducer(failure, issue(K.UNAVAILABLE))
    evidence = i.advance_execution_once(h.admitted(), lifecycle=h).evidence
    result = i.reconcile_execution(evidence, lifecycle=h)
    assert isinstance(result.result, tuple) and result.result[1] is failure
    assert result.evidence.transaction is evidence.transaction


@pytest.mark.parametrize("observed", [False, True])
def test_rollback_needs_independent_base_read_and_is_not_reissued(observed: bool) -> None:
    h = Harness(rollback=True)
    h.script.mode = "failed"
    evidence = i.advance_execution_once(h.admitted(), lifecycle=h).evidence
    tx = evidence.transaction
    assert tx is not None
    if observed:
        proof = t.BaseVerificationEvidence(
            "read-base",
            tx.definition.binding,
            d.DiffVerificationStatus.MATCH,
            tx.definition.binding.base_snapshot,
            tx.definition.binding.base_snapshot,
        )
        h.script.read_producer = SyntheticReadProducer(
            issue(K.UNAVAILABLE), supplied(proof, "base-read")
        )
    result = i.request_rollback(evidence, t.RollbackRequest(False), lifecycle=h)
    assert result.evidence.transaction is not None
    if observed:
        assert (
            result.evidence.transaction.state.outcome
            == t.TransactionOutcome.FAILED_PARTIAL_RECOVERED
        )
        assert h.script.read_producer is not None and h.script.read_producer.read_calls == 1
    else:
        assert result.evidence.transaction.state.base_verification is None
        assert isinstance(result.result, tuple) and result.result[1] is not None
    again = i.request_rollback(result.evidence, t.RollbackRequest(False), lifecycle=h)
    assert isinstance(again.result, p.PortIssue) and h.trace.count("rollback") == 1


def test_failed_all_steps_accounted_cannot_enter_postflight() -> None:
    h = Harness()
    h.script.mode = "failed"
    evidence = i.advance_execution_once(h.admitted(), lifecycle=h).evidence
    assert evidence.transaction is not None and evidence.transaction.state.all_steps_accounted
    result = i.finalize_postflight(evidence, "verify", observations=h, authority=h, lifecycle=h)
    assert isinstance(result.result, p.PortIssue) and "postflight" not in h.trace


def test_postflight_reacquires_and_commits_without_promotion() -> None:
    h = Harness()
    evidence = h.committed()
    assert h.trace[-4:] == ["postflight", "authority.read", "recovery", "currentness.postflight"]
    assert h.reads == h.recoveries == 2
    assert evidence.postflight_authority is not evidence.admission_authority
    result = evidence.postflight_result
    assert (
        result is not None and result.transaction_outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    )
    assert result.diagnostics == ("FRESH_PROMOTION_FACTS_MISSING",)
    assert result.authority_transitions == () and evidence.transaction is result.transaction
    assert evidence.postflight_inputs is not None and evidence.postflight is h.post_reply
    assert evidence.postflight is not None
    assert evidence.postflight_inputs.actual_diff is evidence.postflight.value[1]
    assert (
        result.postflight_record is not None
        and result.postflight_record.actual_diff is evidence.postflight.value[1]
    )


@pytest.mark.parametrize("stage", ["postflight", "authority", "recovery", "currentness"])
def test_postflight_issue_preserves_executed_transaction(stage: str) -> None:
    h = Harness()
    evidence = h.executed()
    failure = issue(K.UNKNOWN)
    h.faults[stage] = failure
    result = i.finalize_postflight(evidence, "verify", observations=h, authority=h, lifecycle=h)
    assert result.result is failure and result.evidence.transaction is evidence.transaction
    assert result.evidence.postflight_result is None


def test_postflight_snapshot_mismatch_is_not_fixed() -> None:
    h = Harness()
    evidence = h.executed()
    assert h.completed.actual_diff is not None
    h.post_override = replace(
        h.completed.actual_diff,
        post_snapshot=replace(h.completed.current_post_snapshot, state_token="other"),
    )
    result = i.finalize_postflight(evidence, "verify", observations=h, authority=h, lifecycle=h)
    assert isinstance(result.result, p.PortIssue) and result.result.kind == K.STALE
    assert result.evidence.transaction is evidence.transaction
    assert (
        result.evidence.postflight is not None
        and result.evidence.postflight.value[1] is h.post_override
    )


@pytest.mark.parametrize("damage", ["mismatch", "unverified"])
def test_postflight_failure_preserves_appended_history_without_promotion(damage: str) -> None:
    h = Harness()
    evidence = h.executed()
    actual = h.completed.actual_diff
    assert actual is not None
    h.post_override = (
        replace(actual, primary_changes=())
        if damage == "mismatch"
        else replace(actual, identity_evidence_ref=None)
    )
    result = i.finalize_postflight(evidence, "verify", observations=h, authority=h, lifecycle=h)
    assert isinstance(result.result, o.FinalizationResult)
    assert result.result.transaction_outcome != t.TransactionOutcome.VERIFIED_COMMITTED
    assert result.result.authority_transitions == ()
    assert result.evidence.transaction is result.result.transaction
    assert result.result.postflight_record is not None


def test_actual_diff_is_port_produced_and_not_changed_by_expected_displacements() -> None:
    h = Harness()
    evidence = h.committed()
    assert evidence.postflight is not None
    actual = evidence.postflight.value[1]
    expected = h.auth.prepared.expected_diff
    inputs = replace(
        expected.inputs, participation=replace(expected.inputs.participation, participants=())
    )
    changed = d.compile_expected_diff(inputs).expected_diff
    assert changed is not None and changed.displacements != expected.displacements
    assert actual is h.completed.actual_diff
    assert (
        d.verify_diff(changed, actual, actual.post_snapshot).status
        == d.DiffVerificationStatus.MISMATCH
    )
    assert (
        evidence.postflight_result is not None
        and evidence.postflight_result.postflight_record is not None
    )
    assert evidence.postflight_result.postflight_record.actual_diff is actual
    h.auth = replace(
        h.auth, prepared=replace(h.auth.prepared, compilation=d.compile_expected_diff(inputs))
    )
    assert h.auth.prepared.expected_diff == changed
    assert evidence.admission_currentness is not None
    observed_again = h.observe_postflight(
        h.auth.prepared.binding, h.auth.prepared.inputs.scope, evidence.admission_currentness
    )
    assert isinstance(observed_again, p.PortValue) and observed_again.value[1] is actual


@pytest.mark.parametrize("purpose", ["postflight", "promotion"])
def test_unknown_recovery_at_later_fences_never_becomes_false(purpose: str) -> None:
    h = Harness()
    evidence = h.executed() if purpose == "postflight" else h.committed()
    current_calls = h.current_calls
    h.recovery = V.UNKNOWN
    result = (
        i.finalize_postflight(evidence, "verify", observations=h, authority=h, lifecycle=h)
        if purpose == "postflight"
        else i.prepare_promotion(evidence, identity=h, authority=h, lifecycle=h, observations=h)
    )
    assert isinstance(result.result, p.PortIssue) and result.result.kind == K.UNKNOWN
    assert result.evidence.transaction is evidence.transaction
    assert h.current_calls == current_calls
    assert result.evidence.promotion_result is None


@pytest.mark.parametrize("stage", ["authority", "recovery", "currentness"])
def test_promotion_acquisition_issue_preserves_commit(stage: str) -> None:
    h = Harness()
    evidence = h.committed()
    failure = issue(K.UNKNOWN)
    h.faults[stage] = failure
    result = i.prepare_promotion(evidence, identity=h, authority=h, lifecycle=h, observations=h)
    assert result.result is failure
    assert result.evidence.transaction is evidence.transaction
    assert result.evidence.identity is not None and result.evidence.promotion_result is None
    assert result.evidence.calls[-1].result is failure


@pytest.mark.parametrize("kind", list(K))
def test_identity_issue_prevents_promotion_acquisition_and_keeps_commit(
    kind: p.PortIssueKind,
) -> None:
    h = Harness()
    evidence = h.committed()
    count = len(h.trace)
    failure = issue(kind)
    h.faults["identity"] = failure
    result = i.prepare_promotion(evidence, identity=h, authority=h, lifecycle=h, observations=h)
    assert result.result is failure and h.trace[count:] == ["identity"]
    assert result.evidence.transaction is evidence.transaction
    assert (
        result.evidence.transaction is not None
        and result.evidence.transaction.state.outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    )


def test_promotion_order_and_exact_original_evidence() -> None:
    h = Harness()
    committed = h.committed()
    result = i.prepare_promotion(committed, identity=h, authority=h, lifecycle=h, observations=h)
    evidence = result.evidence
    assert h.trace[-4:] == ["identity", "authority.read", "recovery", "currentness.promotion"]
    assert h.reads == h.recoveries == 3
    assert isinstance(result.result, o.FinalizationResult)
    assert result.result.authority_after.candidate.promotion == a.PromotionState.PROMOTED
    assert result.result.durable_promotion == "NOT_PERFORMED"
    inputs, original = evidence.promotion_inputs, committed.postflight_inputs
    assert inputs is not None and original is not None
    assert inputs.transaction is committed.transaction and inputs.admission is committed.admission
    assert (
        inputs.actual_diff is original.actual_diff
        and inputs.postflight_facts is original.postflight_facts
    )
    assert committed.postflight_result is not None
    assert inputs.prior_postflight is committed.postflight_result.postflight_record
    assert inputs.verification_ref == original.verification_ref
    assert inputs.promotion_observation_ref != inputs.postflight_observation_ref
    assert h.publications == 0


@pytest.mark.parametrize(
    "mode",
    [
        "same_object",
        "same_acquisition",
        "relabel",
        "same_capture",
        "no_acquisition",
        "no_sources",
        "missing_recovery_source",
    ],
)
def test_promotion_reuse_missing_provenance_fail_closed(mode: str) -> None:
    h = Harness()
    evidence = h.committed()
    h.promotion_mode = mode
    result = i.prepare_promotion(evidence, identity=h, authority=h, lifecycle=h, observations=h)
    assert isinstance(result.result, p.PortIssue)
    assert (
        result.evidence.transaction is evidence.transaction
        and result.evidence.promotion_result is None
    )


@pytest.mark.parametrize("operation", ["postflight", "promotion"])
def test_authority_portvalue_cannot_be_reused(operation: str) -> None:
    h = Harness()
    evidence = h.executed() if operation == "postflight" else h.committed()
    h.reuse_authority = True
    result = (
        i.finalize_postflight(evidence, "verify", observations=h, authority=h, lifecycle=h)
        if operation == "postflight"
        else i.prepare_promotion(evidence, identity=h, authority=h, lifecycle=h, observations=h)
    )
    assert isinstance(result.result, p.PortIssue) and result.result.kind == K.STALE
    assert result.evidence.transaction is evidence.transaction


def test_human_edit_after_commit_blocks_promotion_preserves_history() -> None:
    h = Harness()
    evidence = h.committed()
    post = h.completed.current_post_snapshot
    changed = replace(post, timeline_version=TimelineVersion(3), state_token="human")
    h.work = a.transition(
        h.work,
        a.ObserveHumanVersion(a.CandidateBase(changed.timeline_id, changed.timeline_version)),
    ).state
    h.current_snapshot = changed
    result = i.prepare_promotion(evidence, identity=h, authority=h, lifecycle=h, observations=h)
    assert isinstance(result.result, o.FinalizationResult)
    assert result.result.transaction is evidence.transaction
    assert result.result.transaction_outcome == t.TransactionOutcome.VERIFIED_COMMITTED
    assert result.result.authority_transitions == ()


@pytest.mark.parametrize("disposition", ["PERSISTED", "DUPLICATE"])
def test_publication_exact_arguments_separate_result_no_extra_read(
    disposition: p.PublicationDisposition,
) -> None:
    h = Harness()
    evidence = h.promoted()
    reply = supplied(disposition, "supplied-publication-proof")
    h.publication_reply = reply
    result = i.publish_promotion(evidence, authority=h)
    assert result.result is reply and result.evidence.publication is reply
    assert h.reads == 3 and h.trace[-1] == "publish"
    assert h.publish_arguments is not None
    assert h.publish_arguments[0] is evidence.promotion_authority
    assert h.publish_arguments[1] is evidence.promotion_result
    assert h.publish_arguments[2] is evidence.promotion_currentness
    assert result.evidence.transaction is evidence.transaction
    assert (
        evidence.promotion_result is not None
        and evidence.promotion_result.durable_promotion == "NOT_PERFORMED"
    )


@pytest.mark.parametrize("kind", [K.STALE, K.CONFLICT, K.UNAVAILABLE, K.UNKNOWN])
def test_publication_uncertainty_never_retries_or_rewrites(kind: p.PortIssueKind) -> None:
    h = Harness()
    evidence = h.promoted()
    failure = issue(kind)
    h.publication_reply = failure
    result = i.publish_promotion(evidence, authority=h)
    assert result.result is failure and result.evidence.publication is failure
    assert result.evidence.promotion_result is evidence.promotion_result
    assert result.evidence.transaction is evidence.transaction
    again = i.publish_promotion(result.evidence, authority=h)
    assert isinstance(again.result, p.PortIssue) and h.publications == 1


def test_publication_rejects_replacement_expected_receipt() -> None:
    h = Harness()
    evidence = h.promoted()
    assert evidence.promotion_authority is not None
    changed = replace(
        evidence,
        promotion_authority=replace(
            evidence.promotion_authority,
            receipt=replace(evidence.promotion_authority.receipt, receipt_ref="new"),
        ),
    )
    result = i.publish_promotion(changed, authority=h)
    assert isinstance(result.result, p.PortIssue) and h.publications == 0


def test_publication_bare_exception_is_unknown_and_never_retried() -> None:
    h = Harness()
    evidence = h.promoted()
    fault = RuntimeError("TEST_ONLY_SUPPORT lost publication instrumentation")
    h.publish_exception = fault
    result = i.publish_promotion(evidence, authority=h)
    assert isinstance(result.result, p.PortIssue) and result.result.kind == K.UNKNOWN
    assert result.evidence.transaction is evidence.transaction
    assert result.evidence.promotion_result is evidence.promotion_result
    assert any(
        c.operation == "authority.publish" and c.result is fault for c in result.evidence.calls
    )
    again = i.publish_promotion(result.evidence, authority=h)
    assert isinstance(again.result, p.PortIssue) and h.publications == 1


def test_programming_defect_before_dispatch_may_raise() -> None:
    h = Harness()
    h.raise_resolution = True
    with pytest.raises(ValueError, match="before any dispatch"):
        h.admitted()
    assert h.script.dispatches == 0


def test_bare_exception_after_possible_dispatch_keeps_last_known_not_claimed_latest() -> None:
    h = Harness()
    evidence = h.admitted()
    fault = RuntimeError("TEST_ONLY_SUPPORT producer violation after possible dispatch")

    def broken(adm: o.AdmissionResult, tx: t.Transaction) -> p.LifecycleResult:
        h.script.execute_next(adm, tx)
        raise fault

    h.execution_override = broken
    result = i.advance_execution_once(evidence, lifecycle=h)
    assert isinstance(result.result, p.PortIssue) and result.result.kind == K.UNKNOWN
    assert result.evidence.transaction is None
    call = next(c for c in result.evidence.calls if c.operation == "lifecycle.execute_next")
    assert call.result is fault and call.inputs[1] is evidence.transaction
    again = i.advance_execution_once(result.evidence, lifecycle=h)
    assert isinstance(again.result, p.PortIssue) and h.script.dispatches == 1


def test_records_are_immutable_and_all_five_protocols_typecheck() -> None:
    h = Harness()
    authority: p.AuthorityPort = h
    lifecycle: p.ExecutionLifecyclePort = h
    observations: p.RuntimeObservationPort = h
    resolution: p.ExecutionResolutionPort = h
    identity: p.ApplicationResultPort = h
    assert authority is h
    assert lifecycle is h
    assert observations is h
    assert resolution is h
    assert identity is h
    evidence = h.admitted()
    with pytest.raises(FrozenInstanceError):
        evidence.transaction = None  # type: ignore[misc]


def test_api_and_ast_no_second_machine_native_producer_or_transport() -> None:
    source = Path(i.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert {node.name for node in tree.body if isinstance(node, ast.ClassDef)} == {
        "CallRecord",
        "IntegrationEvidence",
        "IntegrationResult",
    }
    public = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    }
    assert public == {
        "compose_admission",
        "advance_execution_once",
        "reconcile_execution",
        "request_rollback",
        "finalize_postflight",
        "prepare_promotion",
        "publish_promotion",
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names & {
        "IntegrationPhase",
        "IntegrationOutcome",
        "WorkflowState",
        "WorkflowStatus",
        "SessionState",
        "next_phase",
        "can_continue",
        "is_complete",
    }
    for forbidden in (
        "studio",
        "lua",
        "external python",
        "ipc",
        "clipboard",
        "filesystem",
        "socket",
        "mcp",
        "timestamp",
        "sleep",
    ):
        assert forbidden not in source.lower()
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    assert {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} <= {
        None,
        "collections.abc",
        "dataclasses",
        "typing",
    }
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls & {
        "ActualDiff",
        "ApplicationRecord",
        "ExecutionIR",
        "ExecutionTargetBinding",
        "TransactionEvent",
        "transition",
        "prepare_transaction",
        "Candidate",
        "CandidateWorkState",
    }
