"""Pure shared composition. No native access, execution, or durable authority store.

Runtime facts are assertions supplied by qualified ports, not facts certified here.
In-process structural equality binds artifacts; it is not a security/currentness token.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from . import authority as a
from . import cut_geometry as g
from . import execution_ir as ir
from . import expected_diff as d
from . import pause as p
from . import pause_planning as pp
from . import safety_preflight as s
from . import transaction as t
from .temporal_mapping import NativeSnapshotRef


class CompositionStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    STALE = "STALE"


@dataclass(frozen=True)
class PreparationInputs:
    """Qualified, explicit inputs. No participant discovery or evidence qualification."""

    authority_candidate: a.Candidate
    observation: p.PauseObservation
    geometry_inputs: g.GeometryResolutionInput
    proposal_ref: str
    expected_diff_ref: str
    safety_result_ref: str
    target: pp.TargetReadinessInput | None
    snapshot_readiness: pp.SnapshotReadinessInput | None
    dependency: pp.DependencyReadinessInput | None
    participation: d.DisplacementParticipationAssessment
    scope: d.PreservationScope
    compiler_provenance: d.CompilerProvenance
    protection: s.ProtectionContext | None
    safety_evidence: s.CurrentSafetyEvidence | None
    proofs: tuple[s.PreservationProof, ...] = ()

    def __post_init__(self) -> None:
        if not self.safety_result_ref.strip():
            raise ValueError("Safety result reference required")
        object.__setattr__(self, "proofs", tuple(self.proofs))


@dataclass(frozen=True)
class PreparedEdit:
    inputs: PreparationInputs
    editorial_candidate: p.PauseCandidate
    geometry_resolution: g.GeometryResolutionResult
    selected_geometry: g.CutGeometryCandidate
    geometry: pp.PauseCutGeometry
    planning: pp.PausePlanningResult
    compilation: d.DiffCompilationResult
    safety: s.SafetyPreflightResult

    @property
    def expected_diff(self) -> d.ExpectedDiff:
        value = self.compilation.expected_diff
        if value is None:
            raise ValueError("Prepared edit requires complete ExpectedDiff")
        return value

    @property
    def binding(self) -> t.ArtifactBinding:
        return t.ArtifactBinding(
            self.expected_diff.expected_diff_ref,
            self.inputs.safety_result_ref,
            self.expected_diff.base_snapshot,
        )


@dataclass(frozen=True)
class PreparationResult:
    status: CompositionStatus
    prepared: PreparedEdit | None
    diagnostics: tuple[str, ...] = ()
    geometry_resolution: g.GeometryResolutionResult | None = None
    planning: pp.PausePlanningResult | None = None
    compilation: d.DiffCompilationResult | None = None
    safety: s.SafetyPreflightResult | None = None


def prepare_edit(inputs: PreparationInputs) -> PreparationResult:
    """Compose existing functions; READY describes preparation, never native readiness."""
    editorial_candidate = p.classify_pause(inputs.observation)
    gi = inputs.geometry_inputs
    binding, base = gi.binding, gi.current_snapshot
    authority_candidate = inputs.authority_candidate
    if (
        authority_candidate.validity == a.CandidateValidity.STALE
        or authority_candidate.base != a.CandidateBase(base.timeline_id, base.timeline_version)
        or binding.snapshot_ref != base
        or inputs.observation.timeline_id != base.timeline_id
        or inputs.observation.base_version != base.timeline_version
    ):
        return PreparationResult(CompositionStatus.STALE, None, ("STALE_BASE",))
    if (
        gi.candidate != editorial_candidate
        or binding.candidate_ref != authority_candidate.candidate_id
        or binding.object_id != inputs.observation.object_id
        or binding.original_pause_range != inputs.observation.pause_range
    ):
        return PreparationResult(CompositionStatus.BLOCKED, None, ("CANDIDATE_BINDING",))
    resolution = g.resolve_geometry(gi)
    if resolution.status != g.GeometryResolutionStatus.RESOLVED or len(resolution.candidates) != 1:
        status = (
            CompositionStatus.STALE
            if resolution.status == g.GeometryResolutionStatus.STALE
            else CompositionStatus.BLOCKED
        )
        return PreparationResult(status, None, ("GEOMETRY_NOT_UNIQUE",), resolution)
    selected = resolution.candidates[0]
    geometry = pp.PauseCutGeometry(
        selected.geometry_id,
        binding,
        (selected.removed_range,),
        selected.retained_total_frames,
        pp.GeometryProvenance(gi.resolution_ref, gi.geometry_contract_version),
        gi.geometry_contract_version,
    )
    planning = pp.plan_pause(
        pp.PausePlanningInput(
            inputs.proposal_ref,
            editorial_candidate,
            binding,
            base,
            geometry,
            inputs.target,
            inputs.snapshot_readiness,
            inputs.dependency,
        )
    )
    if planning.proposal is None:
        status = (
            CompositionStatus.STALE
            if planning.disposition == pp.PlanningDisposition.STALE
            else CompositionStatus.BLOCKED
        )
        return PreparationResult(status, None, ("PLANNING_NOT_READY",), resolution, planning)
    primary = next(
        (obj for obj in inputs.scope.objects if obj.object_id == binding.object_id), None
    )
    target = inputs.target
    if (
        primary is None
        or target is None
        or primary.media_id != target.media_id
        or primary.timeline_range != target.placement_range
        or primary.timeline_range != gi.placement_range
    ):
        return PreparationResult(
            CompositionStatus.BLOCKED, None, ("PRIMARY_FACT_CONFLICT",), resolution, planning
        )
    compilation = d.compile_expected_diff(
        d.DiffCompilationInput(
            inputs.expected_diff_ref,
            planning.proposal,
            inputs.participation,
            inputs.scope,
            base,
            inputs.compiler_provenance,
        )
    )
    if compilation.expected_diff is None:
        status = (
            CompositionStatus.STALE
            if compilation.status == d.ExpectedDiffStatus.STALE
            else CompositionStatus.BLOCKED
        )
        return PreparationResult(
            status, None, ("DIFF_NOT_READY",), resolution, planning, compilation
        )
    safety = s.preflight(
        s.SafetyPreflightInput(
            compilation,
            planning.proposal,
            base,
            inputs.protection,
            inputs.safety_evidence,
            proofs=inputs.proofs,
        )
    )
    if safety.status != s.PreflightStatus.EVALUATED:
        status = (
            CompositionStatus.STALE
            if safety.status == s.PreflightStatus.STALE
            else CompositionStatus.BLOCKED
        )
        return PreparationResult(
            status, None, ("SAFETY_NOT_EVALUATED",), resolution, planning, compilation, safety
        )
    prepared = PreparedEdit(
        inputs, editorial_candidate, resolution, selected, geometry, planning, compilation, safety
    )
    return PreparationResult(
        CompositionStatus.READY, prepared, (), resolution, planning, compilation, safety
    )


@dataclass(frozen=True)
class BoundApproval:
    """Artifact correlation only. ApprovalState in authority remains the sole approval axis."""

    approval_ref: str
    prepared: PreparedEdit
    candidate_id: a.CandidateId
    base: a.CandidateBase
    binding: t.ArtifactBinding

    def __post_init__(self) -> None:
        if not self.approval_ref.strip():
            raise ValueError("Explicit human approval reference required")


@dataclass(frozen=True)
class AuthorizedEdit:
    prepared: PreparedEdit
    bound_approval: BoundApproval
    authorization: t.ExecutionAuthorization


@dataclass(frozen=True)
class AuthorizationResult:
    status: CompositionStatus
    authorized: AuthorizedEdit | None
    diagnostics: tuple[str, ...] = ()


def _authority_matches(prepared: PreparedEdit, state: a.CandidateWorkState) -> bool:
    original = prepared.inputs.authority_candidate
    return (
        state.candidate.candidate_id == original.candidate_id
        and state.candidate.base == original.base
        and state.candidate.lineage == original.lineage
    )


def _authority_stale(state: a.CandidateWorkState) -> bool:
    return (
        state.candidate.validity == a.CandidateValidity.STALE
        or state.candidate.base != state.authority.reference
    )


def _prepared_valid(prepared: PreparedEdit) -> bool:
    return prepare_edit(prepared.inputs).prepared == prepared


def _approval_bound(prepared: PreparedEdit, approval: BoundApproval) -> bool:
    candidate = prepared.inputs.authority_candidate
    return (
        approval.prepared == prepared
        and approval.candidate_id == candidate.candidate_id
        and approval.base == candidate.base
        and approval.binding == prepared.binding
    )


def _authorized_valid(authorized: AuthorizedEdit) -> bool:
    return (
        _prepared_valid(authorized.prepared)
        and _approval_bound(authorized.prepared, authorized.bound_approval)
        and authorized.authorization
        == t.ExecutionAuthorization(
            authorized.bound_approval.approval_ref,
            authorized.bound_approval.approval_ref,
            authorized.prepared.binding,
        )
        and authorized.prepared.safety.verdict == s.SafetyVerdict.PASS
    )


def authorize_edit(
    prepared: PreparedEdit,
    bound_approval: BoundApproval,
    authority_state: a.CandidateWorkState,
) -> AuthorizationResult:
    if not _prepared_valid(prepared) or not _approval_bound(prepared, bound_approval):
        return AuthorizationResult(CompositionStatus.BLOCKED, None, ("ARTIFACT_MISMATCH",))
    if not _authority_matches(prepared, authority_state):
        return AuthorizationResult(CompositionStatus.BLOCKED, None, ("AUTHORITY_BINDING",))
    if _authority_stale(authority_state):
        return AuthorizationResult(CompositionStatus.STALE, None, ("STALE_AUTHORITY",))
    if not a.apply_eligibility(authority_state).eligible:
        return AuthorizationResult(CompositionStatus.BLOCKED, None, ("AUTHORITY_NOT_ELIGIBLE",))
    if prepared.safety.verdict != s.SafetyVerdict.PASS:
        return AuthorizationResult(CompositionStatus.BLOCKED, None, ("SAFETY_NOT_PASS",))
    # One-to-one in-process authorization reference; not a security or currentness token.
    authorization = t.ExecutionAuthorization(
        bound_approval.approval_ref, bound_approval.approval_ref, prepared.binding
    )
    return AuthorizationResult(
        CompositionStatus.READY, AuthorizedEdit(prepared, bound_approval, authorization)
    )


@dataclass(frozen=True)
class RuntimeAdmissionEvidence:
    validation_inputs: ir.ExecutionIRValidationInput
    transaction_definition: t.TransactionDefinition
    precommit_facts: t.PrecommitFacts


@dataclass(frozen=True)
class AdmissionResult:
    authorized: AuthorizedEdit
    evidence: RuntimeAdmissionEvidence
    authority_state: a.CandidateWorkState
    status: CompositionStatus
    ir_validation: ir.ExecutionIRValidationResult
    precommit: t.PrecommitResult
    transaction: t.Transaction | None
    diagnostics: tuple[str, ...]


def _append(
    tx: t.Transaction, kind: t.TransactionEventKind, payload: t.EventPayload = None
) -> t.Transaction:
    return t.transition(
        tx,
        t.TransactionEvent(
            tx.definition.transaction_ref,
            tx.journal.events[-1].sequence_no + 1,
            kind,
            payload,
        ),
    )


def admit_execution(
    authorized: AuthorizedEdit,
    runtime_admission_evidence: RuntimeAdmissionEvidence,
    authority_state: a.CandidateWorkState,
) -> AdmissionResult:
    """Evaluate supplied runtime evidence, creating only the pre-execution journal prefix."""
    runtime = runtime_admission_evidence
    v, definition, facts = (
        runtime.validation_inputs,
        runtime.transaction_definition,
        runtime.precommit_facts,
    )
    validation = ir.validate_execution_ir(v)
    precommit = t.validate_precommit(definition, facts)
    problems: list[str] = []
    prepared = authorized.prepared
    if not _authorized_valid(authorized):
        problems.append("AUTHORIZATION_ARTIFACT_MISMATCH")
    if not _authority_matches(prepared, authority_state):
        problems.append("AUTHORITY_BINDING")
    stale = _authority_stale(authority_state) or precommit.status == t.PrecommitStatus.STALE
    if stale:
        problems.append("STALE_AUTHORITY_OR_RUNTIME")
    if not a.apply_eligibility(authority_state).eligible:
        problems.append("AUTHORITY_NOT_ELIGIBLE")
    if (
        v.expected_diff != prepared.expected_diff
        or v.safety != prepared.safety
        or v.safety_result_ref != prepared.inputs.safety_result_ref
        or v.execution_ir.authorization != authorized.authorization
        or definition.authorization != authorized.authorization
        or definition.binding != prepared.binding
        or v.current_snapshot != facts.current_snapshot
        or v.authorization_current != facts.authorization_current
        or facts.safety_status != prepared.safety.status
        or facts.safety_verdict != prepared.safety.verdict
    ):
        problems.append("RUNTIME_ARTIFACT_MISMATCH")
    if definition.step_refs != tuple(step.step_ref for step in v.lowering.steps):
        problems.append("LOWERING_STEP_MISMATCH")
    if definition.rollback.capability != v.manifest.rollback_capability:
        problems.append("ROLLBACK_CAPABILITY_MISMATCH")
    if validation.status != ir.ExecutionIRValidationStatus.READY_FOR_EXECUTION:
        problems.append("IR_NOT_READY")
    if precommit.status != t.PrecommitStatus.READY:
        problems.append("PRECOMMIT_NOT_READY")
    tx = None
    if not problems:
        tx = t.prepare_transaction(definition)
        tx = _append(tx, t.TransactionEventKind.PRECOMMIT_STARTED)
        tx = _append(tx, t.TransactionEventKind.PRECOMMIT_PASSED, facts)
    status = (
        CompositionStatus.STALE
        if stale
        else CompositionStatus.BLOCKED
        if problems
        else CompositionStatus.READY
    )
    return AdmissionResult(
        authorized, runtime, authority_state, status, validation, precommit, tx, tuple(problems)
    )


@dataclass(frozen=True)
class ApplicationResultEvidence:
    """Runtime/result-identity port assertion; this layer cannot certify its native truth."""

    evidence_ref: str
    record: a.ApplicationRecord
    transaction_ref: str
    authorization_ref: str
    actual_diff_ref: str
    post_snapshot: NativeSnapshotRef
    identity_evidence_ref: str

    def __post_init__(self) -> None:
        for value in (
            self.evidence_ref,
            self.transaction_ref,
            self.authorization_ref,
            self.actual_diff_ref,
            self.identity_evidence_ref,
        ):
            if not value.strip():
                raise ValueError("Explicit result correspondence references required")


@dataclass(frozen=True)
class PostflightRecord:
    """Retain exact evidence content for later finalization; no hash or persistence claim."""

    expected_diff: d.ExpectedDiff
    actual_diff: d.ActualDiff
    verification: d.DiffVerificationResult
    evidence: t.PostflightEvidence


@dataclass(frozen=True)
class RuntimeFinalizationEvidence:
    admission: AdmissionResult
    transaction: t.Transaction
    actual_diff: d.ActualDiff | None
    current_post_snapshot: NativeSnapshotRef
    verification_ref: str
    postflight_facts: t.CurrentAuthorityFacts | None
    postflight_observation_ref: str | None
    promotion_facts: t.CurrentAuthorityFacts | None
    promotion_observation_ref: str | None
    application_result: ApplicationResultEvidence | None
    prior_postflight: PostflightRecord | None = None


@dataclass(frozen=True)
class FinalizationResult:
    transaction: t.Transaction
    verification: d.DiffVerificationResult | None
    promotion_eligibility: t.PromotionEligibility
    authority_before: a.CandidateWorkState
    authority_after: a.CandidateWorkState
    authority_transitions: tuple[a.CandidateTransitionResult, ...] = ()
    diagnostics: tuple[str, ...] = ()
    postflight_record: PostflightRecord | None = None
    durable_promotion: Literal["NOT_PERFORMED"] = field(default="NOT_PERFORMED", init=False)

    @property
    def transaction_outcome(self) -> t.TransactionOutcome:
        return self.transaction.state.outcome


def finalize_edit(
    authorized: AuthorizedEdit,
    runtime_finalization_evidence: RuntimeFinalizationEvidence,
    authority_state: a.CandidateWorkState,
) -> FinalizationResult:
    """Append legal postflight only; never reconstruct execution or produce ActualDiff.

    Returns an in-memory authority proposal. Freshness/authenticity of port evidence and
    conditional durable publication remain external obligations (OPEN-002/008).
    """
    runtime = runtime_finalization_evidence
    tx = runtime.transaction
    verification: d.DiffVerificationResult | None = None
    eligibility = t.PromotionEligibility.NOT_ELIGIBLE
    retained_postflight = runtime.prior_postflight

    def stop(reason: str) -> FinalizationResult:
        return FinalizationResult(
            tx,
            verification,
            eligibility,
            authority_state,
            authority_state,
            diagnostics=(reason,),
            postflight_record=retained_postflight,
        )

    admission = runtime.admission
    checked = admit_execution(authorized, admission.evidence, admission.authority_state)
    prefix = checked.transaction
    if (
        checked != admission
        or checked.status != CompositionStatus.READY
        or prefix is None
        or tx.definition != prefix.definition
        or tx.journal.events[: len(prefix.journal.events)] != prefix.journal.events
    ):
        return stop("ADMISSION_OR_JOURNAL_MISMATCH")
    if not _authority_matches(authorized.prepared, authority_state):
        return stop("AUTHORITY_BINDING")
    if tx.state.unresolved_step_outcome:
        return stop("EXECUTION_OUTCOME_UNRESOLVED")
    actual = runtime.actual_diff
    if actual is None:
        return stop("ACTUAL_DIFF_MISSING")
    if tx.state.postflight is not None:
        prior = runtime.prior_postflight
        if (
            prior is None
            or prior.expected_diff != authorized.prepared.expected_diff
            or prior.actual_diff != actual
            or prior.evidence != tx.state.postflight
            or prior.verification
            != d.verify_diff(
                prior.expected_diff, prior.actual_diff, prior.evidence.current.current_snapshot
            )
            or prior.verification.status != prior.evidence.status
        ):
            return stop("PRIOR_POSTFLIGHT_ARTIFACT_MISMATCH")
    elif runtime.prior_postflight is not None:
        return stop("UNEXPECTED_PRIOR_POSTFLIGHT")
    verification = d.verify_diff(
        authorized.prepared.expected_diff, actual, runtime.current_post_snapshot
    )
    post_facts = runtime.postflight_facts
    if post_facts is None or not runtime.postflight_observation_ref or not runtime.verification_ref:
        return stop("POSTFLIGHT_FACTS_MISSING")
    if (
        post_facts.binding != authorized.prepared.binding
        or post_facts.authorization_ref != authorized.authorization.authorization_ref
        or post_facts.current_snapshot != runtime.current_post_snapshot
    ):
        return stop("POSTFLIGHT_BINDING_MISMATCH")
    if tx.state.phase != t.TransactionPhase.TERMINAL:
        if tx.state.phase == t.TransactionPhase.APPLYING:
            if not all(step.status == t.ExecutionStepStatus.SUCCEEDED for step in tx.state.steps):
                return stop("EXECUTION_NOT_SUCCEEDED")
            tx = _append(tx, t.TransactionEventKind.POSTFLIGHT_STARTED)
        if tx.state.phase != t.TransactionPhase.POSTFLIGHT_VERIFYING:
            return stop("POSTFLIGHT_PHASE_UNAVAILABLE")
        post = t.PostflightEvidence(
            runtime.verification_ref,
            authorized.prepared.binding,
            verification.status,
            actual.post_snapshot,
            post_facts,
        )
        if tx.state.postflight is None:
            kind = {
                d.DiffVerificationStatus.MATCH: t.TransactionEventKind.POSTFLIGHT_MATCHED,
                d.DiffVerificationStatus.MISMATCH: t.TransactionEventKind.POSTFLIGHT_MISMATCH,
                d.DiffVerificationStatus.UNVERIFIED: t.TransactionEventKind.POSTFLIGHT_UNVERIFIED,
                d.DiffVerificationStatus.STALE: t.TransactionEventKind.POSTFLIGHT_STALE,
            }[verification.status]
            tx = _append(tx, kind, post)
            retained_postflight = PostflightRecord(
                authorized.prepared.expected_diff, actual, verification, post
            )
        elif tx.state.postflight != post:
            return stop("EXISTING_POSTFLIGHT_MISMATCH")
        if verification.status != d.DiffVerificationStatus.MATCH:
            return stop("POSTFLIGHT_NOT_MATCH")
        if _authority_stale(authority_state) or not a.apply_eligibility(authority_state).eligible:
            return stop("AUTHORITY_NO_LONGER_ELIGIBLE")
        try:
            tx = _append(
                tx,
                t.TransactionEventKind.TRANSACTION_TERMINATED,
                t.TransactionOutcome.VERIFIED_COMMITTED,
            )
        except ValueError:
            return stop("COMMIT_FACTS_NOT_CURRENT")
    if tx.state.outcome != t.TransactionOutcome.VERIFIED_COMMITTED:
        return stop("TRANSACTION_NOT_COMMITTED")
    # Existing terminal history is never rewritten when a later observation is stale.
    if verification.status != d.DiffVerificationStatus.MATCH:
        return stop("CURRENT_POST_NOT_MATCH")
    recorded_post = tx.state.postflight
    if (
        recorded_post is None
        or recorded_post.verification_ref != runtime.verification_ref
        or recorded_post.observed_snapshot != actual.post_snapshot
    ):
        return stop("COMMITTED_POST_BINDING_MISMATCH")
    promotion = runtime.promotion_facts
    if (
        promotion is None
        or not runtime.promotion_observation_ref
        or runtime.promotion_observation_ref == runtime.postflight_observation_ref
    ):
        return stop("FRESH_PROMOTION_FACTS_MISSING")
    if _authority_stale(authority_state) or not a.apply_eligibility(authority_state).eligible:
        return stop("AUTHORITY_NO_LONGER_ELIGIBLE")
    eligibility = t.promotion_eligibility(tx, promotion)
    if eligibility != t.PromotionEligibility.ELIGIBLE:
        return stop("PROMOTION_NOT_ELIGIBLE")
    result = runtime.application_result
    if result is None:
        return stop("APPLICATION_RESULT_MISSING")
    record = result.record
    if (
        result.transaction_ref != tx.definition.transaction_ref
        or result.authorization_ref != authorized.authorization.authorization_ref
        or result.actual_diff_ref != actual.actual_diff_ref
        or result.post_snapshot != actual.post_snapshot
        or result.identity_evidence_ref != actual.identity_evidence_ref
        or record.candidate_id != authority_state.candidate.candidate_id
        or record.base != authority_state.candidate.base
        or record.result.reference
        != a.CandidateBase(actual.post_snapshot.timeline_id, actual.post_snapshot.timeline_version)
    ):
        return stop("APPLICATION_RESULT_MISMATCH")
    events: tuple[a.CandidateEvent, ...] = (
        a.RecordApplication(record),
        a.RecordVerification(record, True),
        a.PromoteCandidate(record.result.reference),
    )
    work = authority_state
    transitions: list[a.CandidateTransitionResult] = []
    for event in events:
        transition = a.transition(work, event)
        transitions.append(transition)
        if not transition.accepted:
            return FinalizationResult(
                tx,
                verification,
                eligibility,
                authority_state,
                authority_state,
                tuple(transitions),
                ("AUTHORITY_REJECTED",),
                retained_postflight,
            )
        work = transition.state
    return FinalizationResult(
        tx,
        verification,
        eligibility,
        authority_state,
        work,
        tuple(transitions),
        postflight_record=retained_postflight,
    )
