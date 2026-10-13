"""Bounded choreography, not live mutation qualification or a lifecycle authority.

All truth comes from the five supplied ports. Receipts support correlation/reuse
checks only, not acquisition authenticity or atomic observation-and-dispatch.
OPEN-002/008, identity, interrupted recovery, durable retention, and exactly-once
execution/publication remain unresolved. There is no automatic progression/retry.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal, TypeAlias

from . import authority as a
from . import expected_diff as d
from . import native_snapshot as n
from . import orchestration as o
from . import runtime_ports as p
from . import safety_preflight as s
from . import transaction as t

PortReturn: TypeAlias = (
    p.PortValue[a.CandidateWorkState]
    | p.PortValue[n.ObservedValue]
    | p.PortValue[p.CurrentnessPayload]
    | p.PortValue[p.ResolutionPayload]
    | p.PortValue[p.PostflightPayload]
    | p.PortValue[o.ApplicationResultEvidence]
    | p.PortValue[p.PublicationDisposition]
    | p.PortIssue
)
OperationResult: TypeAlias = (
    PortReturn | p.LifecycleResult | o.AdmissionResult | o.FinalizationResult
)
CallInput: TypeAlias = (
    o.AuthorizedEdit
    | t.ExecutionAuthorization
    | o.RuntimeAdmissionEvidence
    | o.RuntimeFinalizationEvidence
    | o.AdmissionResult
    | o.FinalizationResult
    | t.Transaction
    | t.RollbackRequest
    | t.ArtifactBinding
    | d.PreservationScope
    | s.SafetyPreflightResult
    | PortReturn
    | a.CandidateWorkState
    | str
)


@dataclass(frozen=True)
class CallRecord:
    """Exact call objects. Order records this caller's trace, not native temporal proof."""

    operation: str
    inputs: tuple[CallInput, ...]
    result: OperationResult | Exception


@dataclass(frozen=True)
class IntegrationEvidence:
    """References only. No phase, readiness, retry, or lifecycle decision is stored.

    transaction is the latest returned Transaction, not a reconstructed history.
    If a lifecycle producer raises without returning it, transaction becomes None;
    the last known input and exception remain in calls. Such evidence cannot resume.
    """

    authorized: o.AuthorizedEdit
    transaction: t.Transaction | None = None
    calls: tuple[CallRecord, ...] = ()
    admission_authority: p.PortValue[a.CandidateWorkState] | None = None
    admission_recovery: p.PortValue[n.ObservedValue] | None = None
    admission_currentness: p.PortValue[p.CurrentnessPayload] | None = None
    resolution: p.PortValue[p.ResolutionPayload] | None = None
    admission_inputs: o.RuntimeAdmissionEvidence | None = None
    admission: o.AdmissionResult | None = None
    postflight: p.PortValue[p.PostflightPayload] | None = None
    postflight_authority: p.PortValue[a.CandidateWorkState] | None = None
    postflight_recovery: p.PortValue[n.ObservedValue] | None = None
    postflight_currentness: p.PortValue[p.CurrentnessPayload] | None = None
    postflight_inputs: o.RuntimeFinalizationEvidence | None = None
    postflight_result: o.FinalizationResult | None = None
    identity: p.PortValue[o.ApplicationResultEvidence] | None = None
    promotion_authority: p.PortValue[a.CandidateWorkState] | None = None
    promotion_recovery: p.PortValue[n.ObservedValue] | None = None
    promotion_currentness: p.PortValue[p.CurrentnessPayload] | None = None
    promotion_inputs: o.RuntimeFinalizationEvidence | None = None
    promotion_result: o.FinalizationResult | None = None
    publication: p.PortResult[p.PublicationDisposition] | None = None


@dataclass(frozen=True)
class IntegrationResult:
    evidence: IntegrationEvidence
    result: OperationResult


def _record(
    e: IntegrationEvidence,
    name: str,
    inputs: tuple[CallInput, ...],
    result: OperationResult | Exception,
) -> IntegrationEvidence:
    return replace(e, calls=(*e.calls, CallRecord(name, inputs, result)))


def _stop(
    e: IntegrationEvidence,
    reason: str,
    kind: p.PortIssueKind = p.PortIssueKind.UNRESOLVED,
    *,
    violation: bool = False,
) -> IntegrationResult:
    # A receipt of a comparison/stop, explicitly not a fabricated acquisition.
    refs = tuple(
        call.result.receipt.receipt_ref
        for call in e.calls
        if isinstance(call.result, (p.PortValue, p.PortIssue))
    )
    issue = p.PortIssue(
        kind,
        reason,
        p.PortReceipt(
            "integration-stop",
            "runtime-integration",
            None,
            refs,
            ("Correlation only; no acquisition or native truth certification",),
            "PRODUCER_ASSERTION",
        ),
    )
    return IntegrationResult(
        _record(e, "contract_violation" if violation else "integration.stop", (reason,), issue),
        issue,
    )


def _unsafe(e: IntegrationEvidence) -> bool:
    return any(call.operation == "contract_violation" for call in e.calls)


def _admitted(e: IntegrationEvidence) -> bool:
    adm, tx = e.admission, e.transaction
    return (
        not _unsafe(e)
        and adm is not None
        and adm.status == o.CompositionStatus.READY
        and adm.transaction is not None
        and tx is not None
        and adm.authorized is e.authorized
        and adm.evidence is e.admission_inputs
        and tx.definition == adm.transaction.definition
        and tx.journal.events[: len(adm.transaction.journal.events)]
        == adm.transaction.journal.events
    )


def _same_capture(snapshot: n.NativeTimelineSnapshot, facts: t.CurrentAuthorityFacts) -> bool:
    """Supplied identifiers correspond; no identity mapping or freshness is inferred."""
    ref = facts.current_snapshot
    return (
        snapshot.timeline_ref.ref == ref.timeline_id
        and snapshot.timeline_version == ref.timeline_version
        and snapshot.state_token == ref.state_token
    )


def _reused(value: p.PortValue[a.CandidateWorkState], e: IntegrationEvidence) -> bool:
    return any(
        old is not None
        and (
            value is old
            or value.receipt.receipt_ref == old.receipt.receipt_ref
            or (
                value.receipt.acquisition_ref is not None
                and value.receipt.acquisition_ref == old.receipt.acquisition_ref
            )
        )
        for old in (e.admission_authority, e.postflight_authority)
    )


Fence: TypeAlias = tuple[
    IntegrationEvidence,
    p.PortValue[a.CandidateWorkState],
    p.PortValue[n.ObservedValue],
    p.PortValue[p.CurrentnessPayload],
]


def _fence(
    e: IntegrationEvidence,
    purpose: Literal["admission", "postflight", "promotion"],
    authority: p.AuthorityPort,
    lifecycle: p.ExecutionLifecyclePort,
    observations: p.RuntimeObservationPort,
) -> Fence | IntegrationResult:
    auth = e.authorized
    candidate = auth.prepared.inputs.authority_candidate
    work = authority.read(candidate.candidate_id)
    e = _record(e, f"authority.read.{purpose}", (candidate.candidate_id,), work)
    if isinstance(work, p.PortIssue):
        return IntegrationResult(e, work)
    if purpose != "admission" and _reused(work, e):
        return _stop(e, "Authority read was reused", p.PortIssueKind.STALE)
    recovery = lifecycle.observe_recovery_required(auth.authorization)
    e = _record(e, f"lifecycle.recovery.{purpose}", (auth.authorization,), recovery)
    if isinstance(recovery, p.PortIssue):
        return IntegrationResult(e, recovery)
    if recovery.value == n.ObservedValue.UNKNOWN:
        return _stop(e, "Recovery UNKNOWN; no boolean currentness facts", p.PortIssueKind.UNKNOWN)
    current = observations.observe_currentness(
        auth.authorization,
        auth.prepared.safety,
        work,
        recovery,
        purpose=purpose,
    )
    e = _record(
        e,
        f"observations.currentness.{purpose}",
        (auth.authorization, auth.prepared.safety, work, recovery, purpose),
        current,
    )
    if isinstance(current, p.PortIssue):
        return IntegrationResult(e, current)
    snapshot, facts = current.value
    if (
        facts.binding != auth.prepared.binding
        or facts.authorization_ref != auth.authorization.authorization_ref
        or facts.recovery_required != (recovery.value == n.ObservedValue.TRUE)
        or not _same_capture(snapshot, facts)
    ):
        return _stop(
            e, "Currentness/recovery/binding correspondence mismatch", p.PortIssueKind.CONFLICT
        )
    # Explicit source linkage to the actual two input receipts, not arbitrary strings.
    if (
        current.receipt.acquisition_ref is None
        or not current.receipt.source_refs
        or not {work.receipt.receipt_ref, recovery.receipt.receipt_ref}
        <= set(current.receipt.source_refs)
    ):
        return _stop(
            e, "Missing currentness acquisition/source correlation", p.PortIssueKind.UNKNOWN
        )
    if purpose == "promotion":
        for old in (e.admission_currentness, e.postflight_currentness):
            if old is not None and (
                current is old
                or current.receipt.acquisition_ref == old.receipt.acquisition_ref
                or current.receipt.receipt_ref == old.receipt.receipt_ref
                or snapshot.capture_id == old.value[0].capture_id
            ):
                return _stop(e, "Promotion reuses an acquisition", p.PortIssueKind.STALE)
        if e.postflight is not None and (
            current.receipt.acquisition_ref == e.postflight.receipt.acquisition_ref
            or snapshot.capture_id == e.postflight.value[0].capture_id
        ):
            return _stop(e, "Promotion reuses post observation", p.PortIssueKind.STALE)
    return e, work, recovery, current


def compose_admission(
    authorized: o.AuthorizedEdit,
    *,
    authority: p.AuthorityPort,
    lifecycle: p.ExecutionLifecyclePort,
    observations: p.RuntimeObservationPort,
    resolution: p.ExecutionResolutionPort,
) -> IntegrationResult:
    acquired = _fence(
        IntegrationEvidence(authorized), "admission", authority, lifecycle, observations
    )
    if isinstance(acquired, IntegrationResult):
        return acquired
    e, work, recovery, current = acquired
    e = replace(
        e, admission_authority=work, admission_recovery=recovery, admission_currentness=current
    )
    resolved = resolution.resolve_execution(authorized, current)
    e = _record(e, "resolution.resolve_execution", (authorized, current), resolved)
    if isinstance(resolved, p.PortIssue):
        return IntegrationResult(e, resolved)
    e = replace(e, resolution=resolved)
    if current.receipt.receipt_ref not in resolved.receipt.source_refs:
        return _stop(e, "Resolution lacks currentness source correlation", p.PortIssueKind.UNKNOWN)
    validation, definition, targets, executor = resolved.value
    facts = current.value[1]
    if (
        validation.current_snapshot != facts.current_snapshot
        or validation.authorization_current != facts.authorization_current
    ):
        return _stop(e, "Resolution/currentness mismatch", p.PortIssueKind.CONFLICT)
    precommit = t.PrecommitFacts(
        facts.binding,
        facts.authorization_ref,
        facts.current_snapshot,
        authorized.prepared.safety.status,
        authorized.prepared.safety.verdict,
        facts.authorization_current,
        facts.safety_pass_current,
        targets,
        executor,
        facts.recovery_required,
    )
    inputs = o.RuntimeAdmissionEvidence(validation, definition, precommit)
    result = o.admit_execution(authorized, inputs, work.value)
    e = _record(e, "orchestration.admit_execution", (authorized, inputs, work.value), result)
    return IntegrationResult(
        replace(e, admission_inputs=inputs, admission=result, transaction=result.transaction),
        result,
    )


def _lifecycle(
    e: IntegrationEvidence,
    name: str,
    args: tuple[CallInput, ...],
    invoke: Callable[[], p.LifecycleResult],
    allowed: frozenset[t.TransactionEventKind],
) -> IntegrationResult:
    previous = e.transaction
    assert previous is not None
    try:
        returned = invoke()
    except Exception as error:  # noqa: BLE001 -- possible dispatch requires a bounded uncertainty result
        # Dispatch cannot be ruled out at this boundary. Do not label input as latest.
        e = _record(replace(e, transaction=None), name, args, error)
        return _stop(
            e,
            "Lifecycle exception: latest journal unavailable; STOP, no retry",
            p.PortIssueKind.UNKNOWN,
            violation=True,
        )
    tx, issue = returned
    e = _record(replace(e, transaction=tx), name, args, returned)
    old = previous.journal.events
    suffix = tx.journal.events[len(old) :]
    if tx.definition != previous.definition or tx.journal.events[: len(old)] != old:
        return _stop(
            e, "Lifecycle definition/prefix violation", p.PortIssueKind.CONFLICT, violation=True
        )
    starts = [event for event in suffix if event.kind == t.TransactionEventKind.STEP_STARTED]
    if (
        any(event.kind not in allowed for event in suffix)
        or len(starts) > 1
        or any(
            event.payload
            in {
                step.step_ref
                for step in previous.state.steps
                if step.status != t.ExecutionStepStatus.NOT_STARTED
            }
            for event in starts
        )
    ):
        return _stop(
            e, "Lifecycle exceeds bounded operation", p.PortIssueKind.CONFLICT, violation=True
        )
    if issue is not None:
        return IntegrationResult(e, returned)
    if tx.state.unresolved_step_outcome:
        return _stop(e, "Execution unresolved; STOP", p.PortIssueKind.UNKNOWN)
    if name == "lifecycle.rollback" and tx.state.base_verification is None:
        return _stop(e, "Rollback acknowledgment is not recovery proof", p.PortIssueKind.UNKNOWN)
    return IntegrationResult(e, returned)


def advance_execution_once(
    evidence: IntegrationEvidence, *, lifecycle: p.ExecutionLifecyclePort
) -> IntegrationResult:
    if not _admitted(evidence):
        return _stop(evidence, "No usable admitted transaction")
    tx, admission = evidence.transaction, evidence.admission
    assert tx is not None and admission is not None
    state = tx.state
    if (
        state.phase != t.TransactionPhase.APPLYING
        or state.unresolved_step_outcome
        or any(step.status == t.ExecutionStepStatus.FAILED for step in state.steps)
        or not any(step.status == t.ExecutionStepStatus.NOT_STARTED for step in state.steps)
    ):
        return _stop(evidence, "Transaction does not permit a new step")
    return _lifecycle(
        evidence,
        "lifecycle.execute_next",
        (admission, tx),
        lambda: lifecycle.execute_next(admission, tx),
        frozenset(
            (
                t.TransactionEventKind.STEP_STARTED,
                t.TransactionEventKind.STEP_SUCCEEDED,
                t.TransactionEventKind.STEP_FAILED,
                t.TransactionEventKind.STEP_OUTCOME_UNKNOWN,
            )
        ),
    )


def reconcile_execution(
    evidence: IntegrationEvidence, *, lifecycle: p.ExecutionLifecyclePort
) -> IntegrationResult:
    if not _admitted(evidence):
        return _stop(evidence, "No usable admitted transaction")
    tx, admission = evidence.transaction, evidence.admission
    assert tx is not None and admission is not None
    if (
        tx.state.phase != t.TransactionPhase.APPLYING
        or tx.state.active_step_ref is not None
        or not any(step.status == t.ExecutionStepStatus.OUTCOME_UNKNOWN for step in tx.state.steps)
    ):
        return _stop(evidence, "Existing explicit UNKNOWN report required; no event repair")
    return _lifecycle(
        evidence,
        "lifecycle.reconcile",
        (admission, tx),
        lambda: lifecycle.reconcile(admission, tx),
        frozenset((t.TransactionEventKind.RECONCILIATION_RECORDED,)),
    )


def request_rollback(
    evidence: IntegrationEvidence,
    request: t.RollbackRequest,
    *,
    lifecycle: p.ExecutionLifecyclePort,
) -> IntegrationResult:
    if not _admitted(evidence):
        return _stop(evidence, "No usable admitted transaction")
    tx, admission = evidence.transaction, evidence.admission
    assert tx is not None and admission is not None
    state = tx.state
    failed = state.phase == t.TransactionPhase.APPLYING and any(
        step.status == t.ExecutionStepStatus.FAILED for step in state.steps
    )
    failed_post = (
        state.phase == t.TransactionPhase.POSTFLIGHT_VERIFYING
        and state.postflight is not None
        and state.postflight.status != d.DiffVerificationStatus.MATCH
    )
    if (
        state.unresolved_step_outcome
        or not (failed or failed_post)
        or not any(step.may_have_mutated for step in state.steps)
        or tx.definition.rollback.policy == t.RollbackPolicy.NOT_AVAILABLE
        or (request.automatic and not t.automatic_rollback_eligible(tx))
    ):
        return _stop(evidence, "Existing rollback rules do not permit a new request")
    return _lifecycle(
        evidence,
        "lifecycle.rollback",
        (admission, tx, request),
        lambda: lifecycle.rollback(admission, tx, request),
        frozenset(
            (
                t.TransactionEventKind.ROLLBACK_STARTED,
                t.TransactionEventKind.ROLLBACK_COMMAND_COMPLETED,
                t.TransactionEventKind.ROLLBACK_VERIFIED,
                t.TransactionEventKind.ROLLBACK_FAILED,
                t.TransactionEventKind.TRANSACTION_TERMINATED,
            )
        ),
    )


def finalize_postflight(
    evidence: IntegrationEvidence,
    verification_ref: str,
    *,
    observations: p.RuntimeObservationPort,
    authority: p.AuthorityPort,
    lifecycle: p.ExecutionLifecyclePort,
) -> IntegrationResult:
    if not verification_ref.strip():
        raise ValueError("Explicit verification reference required")
    if not _admitted(evidence):
        return _stop(evidence, "No usable admitted transaction")
    tx, admission = evidence.transaction, evidence.admission
    before = evidence.admission_currentness
    assert tx is not None and admission is not None
    if (
        before is None
        or evidence.postflight_inputs is not None
        or tx.state.phase != t.TransactionPhase.APPLYING
        or tx.state.unresolved_step_outcome
        or not all(step.status == t.ExecutionStepStatus.SUCCEEDED for step in tx.state.steps)
    ):
        return _stop(evidence, "First postflight requires all steps SUCCEEDED")
    auth = evidence.authorized
    observed = observations.observe_postflight(
        auth.prepared.binding, auth.prepared.inputs.scope, before
    )
    e = _record(
        evidence,
        "observations.observe_postflight",
        (auth.prepared.binding, auth.prepared.inputs.scope, before),
        observed,
    )
    if isinstance(observed, p.PortIssue):
        return IntegrationResult(e, observed)
    e = replace(e, postflight=observed)
    acquired = _fence(e, "postflight", authority, lifecycle, observations)
    if isinstance(acquired, IntegrationResult):
        return acquired
    e, work, recovery, current = acquired
    e = replace(
        e, postflight_authority=work, postflight_recovery=recovery, postflight_currentness=current
    )
    snapshot, actual = observed.value
    facts = current.value[1]
    if (
        actual.base_snapshot != auth.prepared.binding.base_snapshot
        or actual.expected_diff_ref != auth.prepared.expected_diff.expected_diff_ref
        or actual.post_snapshot != facts.current_snapshot
        or not _same_capture(snapshot, facts)
    ):
        return _stop(
            e, "Postflight snapshot/binding correspondence mismatch", p.PortIssueKind.STALE
        )
    if (
        observed.receipt.acquisition_ref is None
        or before.receipt.receipt_ref not in observed.receipt.source_refs
    ):
        return _stop(e, "Missing postflight observation provenance", p.PortIssueKind.UNKNOWN)
    inputs = o.RuntimeFinalizationEvidence(
        admission,
        tx,
        actual,
        facts.current_snapshot,
        verification_ref,
        facts,
        current.receipt.receipt_ref,
        None,
        None,
        None,
    )
    result = o.finalize_edit(auth, inputs, work.value)
    e = _record(e, "orchestration.finalize_postflight", (auth, inputs, work.value), result)
    return IntegrationResult(
        replace(
            e, transaction=result.transaction, postflight_inputs=inputs, postflight_result=result
        ),
        result,
    )


def prepare_promotion(
    evidence: IntegrationEvidence,
    *,
    identity: p.ApplicationResultPort,
    authority: p.AuthorityPort,
    lifecycle: p.ExecutionLifecyclePort,
    observations: p.RuntimeObservationPort,
) -> IntegrationResult:
    if not _admitted(evidence):
        return _stop(evidence, "No usable admitted transaction")
    tx, admission = evidence.transaction, evidence.admission
    post, original, final = (
        evidence.postflight,
        evidence.postflight_inputs,
        evidence.postflight_result,
    )
    assert tx is not None and admission is not None
    if (
        tx.state.outcome != t.TransactionOutcome.VERIFIED_COMMITTED
        or post is None
        or original is None
        or final is None
        or final.postflight_record is None
        or evidence.publication is not None
    ):
        return _stop(evidence, "Retained committed postflight evidence required")
    if (
        original.actual_diff is not post.value[1]
        or final.postflight_record.actual_diff is not post.value[1]
        or tx is not final.transaction
    ):
        return _stop(evidence, "Committed evidence substitution", p.PortIssueKind.CONFLICT)
    auth = evidence.authorized
    # Earlier attempts remain in calls, but cannot serve as a new publication proposal.
    e = replace(
        evidence,
        identity=None,
        promotion_authority=None,
        promotion_recovery=None,
        promotion_currentness=None,
        promotion_inputs=None,
        promotion_result=None,
    )
    result_identity = identity.resolve_application_result(auth, tx, post)
    e = _record(e, "identity.resolve_application_result", (auth, tx, post), result_identity)
    if isinstance(result_identity, p.PortIssue):
        return IntegrationResult(e, result_identity)
    e = replace(e, identity=result_identity)
    if post.receipt.receipt_ref not in result_identity.receipt.source_refs:
        return _stop(e, "Identity lacks postflight source correlation", p.PortIssueKind.UNKNOWN)
    acquired = _fence(e, "promotion", authority, lifecycle, observations)
    if isinstance(acquired, IntegrationResult):
        return acquired
    e, work, recovery, current = acquired
    e = replace(
        e, promotion_authority=work, promotion_recovery=recovery, promotion_currentness=current
    )
    inputs = replace(
        original,
        transaction=tx,
        prior_postflight=final.postflight_record,
        promotion_facts=current.value[1],
        promotion_observation_ref=current.receipt.receipt_ref,
        application_result=result_identity.value,
    )
    result = o.finalize_edit(auth, inputs, work.value)
    e = _record(e, "orchestration.finalize_promotion", (auth, inputs, work.value), result)
    return IntegrationResult(
        replace(
            e, transaction=result.transaction, promotion_inputs=inputs, promotion_result=result
        ),
        result,
    )


def publish_promotion(
    evidence: IntegrationEvidence, *, authority: p.AuthorityPort
) -> IntegrationResult:
    if not _admitted(evidence):
        return _stop(evidence, "No usable admitted transaction")
    proposal, expected, current = (
        evidence.promotion_result,
        evidence.promotion_authority,
        evidence.promotion_currentness,
    )
    if evidence.publication is not None or any(
        c.operation == "authority.publish" for c in evidence.calls
    ):
        return _stop(
            evidence, "Publication already attempted; no retry policy", p.PortIssueKind.UNKNOWN
        )
    inputs = evidence.promotion_inputs
    if (
        proposal is None
        or expected is None
        or current is None
        or inputs is None
        or inputs.promotion_facts is not current.value[1]
        or inputs.promotion_observation_ref != current.receipt.receipt_ref
        or proposal.transaction is not evidence.transaction
        or proposal.authority_before is not expected.value
        or not proposal.authority_transitions
        or not all(result.accepted for result in proposal.authority_transitions)
        or proposal.authority_after.candidate.promotion != a.PromotionState.PROMOTED
        or proposal.durable_promotion != "NOT_PERFORMED"
    ):
        return _stop(evidence, "Exact accepted semantic promotion and fresh inputs required")
    for name, value in (
        ("authority.read.promotion", expected),
        ("observations.currentness.promotion", current),
        ("orchestration.finalize_promotion", proposal),
    ):
        if not any(call.operation == name and call.result is value for call in evidence.calls):
            return _stop(
                evidence,
                "Publication argument was not retained from its producing call",
                p.PortIssueKind.CONFLICT,
            )
    try:
        result = authority.publish(expected, proposal, current)
    except Exception as error:  # noqa: BLE001 -- publication may have occurred; retain and stop
        e = _record(evidence, "authority.publish", (expected, proposal, current), error)
        return _stop(
            e,
            "Publication contract failure; outcome unknown, no retry",
            p.PortIssueKind.UNKNOWN,
            violation=True,
        )
    e = _record(evidence, "authority.publish", (expected, proposal, current), result)
    return IntegrationResult(replace(e, publication=result), result)
