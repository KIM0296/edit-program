"""ADR-027 pure transaction history; no native commands, retries or Authority calls."""

from dataclasses import dataclass
from enum import Enum
from itertools import pairwise
from typing import TypeAlias

from .expected_diff import DiffVerificationStatus
from .native_snapshot import ObservedValue
from .safety_preflight import PreflightStatus, SafetyVerdict
from .temporal_mapping import NativeSnapshotRef


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Nonempty opaque reference/version required")


def _typed(value: object, kind: type[object]) -> None:
    if not isinstance(value, kind):
        raise TypeError(f"Expected {kind.__name__}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


class TransactionPhase(str, Enum):
    PREPARED = "PREPARED"
    PRECOMMIT_VALIDATING = "PRECOMMIT_VALIDATING"
    APPLYING = "APPLYING"
    POSTFLIGHT_VERIFYING = "POSTFLIGHT_VERIFYING"
    ROLLING_BACK = "ROLLING_BACK"
    TERMINAL = "TERMINAL"


class TransactionOutcome(str, Enum):
    NONE = "NONE"
    VERIFIED_COMMITTED = "VERIFIED_COMMITTED"
    ABORTED_STALE = "ABORTED_STALE"
    FAILED_BEFORE_MUTATION = "FAILED_BEFORE_MUTATION"
    FAILED_PARTIAL_RECOVERED = "FAILED_PARTIAL_RECOVERED"
    FAILED_PARTIAL_UNRECOVERED = "FAILED_PARTIAL_UNRECOVERED"
    FAILED_POSTFLIGHT_RECOVERED = "FAILED_POSTFLIGHT_RECOVERED"
    FAILED_POSTFLIGHT_UNRECOVERED = "FAILED_POSTFLIGHT_UNRECOVERED"
    UNVERIFIED_APPLY = "UNVERIFIED_APPLY"


class ExecutionStepStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class RollbackCapability(str, Enum):
    SUPPORTED_VERIFIED = "SUPPORTED_VERIFIED"
    SUPPORTED_UNVERIFIED = "SUPPORTED_UNVERIFIED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class RollbackPolicy(str, Enum):
    AUTO_ELIGIBLE = "AUTO_ELIGIBLE"
    MANUAL_ONLY = "MANUAL_ONLY"
    NOT_AVAILABLE = "NOT_AVAILABLE"


def derive_rollback_policy(capability: RollbackCapability) -> RollbackPolicy:
    _typed(capability, RollbackCapability)
    return {
        RollbackCapability.SUPPORTED_VERIFIED: RollbackPolicy.AUTO_ELIGIBLE,
        RollbackCapability.SUPPORTED_UNVERIFIED: RollbackPolicy.MANUAL_ONLY,
        RollbackCapability.UNSUPPORTED: RollbackPolicy.NOT_AVAILABLE,
        RollbackCapability.UNKNOWN: RollbackPolicy.NOT_AVAILABLE,
    }[capability]


@dataclass(frozen=True)
class RollbackSettings:
    capability: RollbackCapability
    policy: RollbackPolicy

    def __post_init__(self) -> None:
        _typed(self.capability, RollbackCapability)
        _typed(self.policy, RollbackPolicy)
        order = (
            RollbackPolicy.NOT_AVAILABLE,
            RollbackPolicy.MANUAL_ONLY,
            RollbackPolicy.AUTO_ELIGIBLE,
        )
        _require(
            order.index(self.policy) <= order.index(derive_rollback_policy(self.capability)),
            "Policy cannot exceed supplied capability",
        )


@dataclass(frozen=True)
class ArtifactBinding:
    expected_diff_ref: str
    safety_result_ref: str
    base_snapshot: NativeSnapshotRef

    def __post_init__(self) -> None:
        _text(self.expected_diff_ref)
        _text(self.safety_result_ref)
        _typed(self.base_snapshot, NativeSnapshotRef)


@dataclass(frozen=True)
class ExecutionAuthorization:
    authorization_ref: str
    approval_ref: str
    binding: ArtifactBinding
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        _text(self.authorization_ref)
        _text(self.approval_ref)
        _text(self.contract_version)
        _typed(self.binding, ArtifactBinding)


@dataclass(frozen=True)
class TransactionDefinition:
    transaction_ref: str
    binding: ArtifactBinding
    authorization: ExecutionAuthorization
    step_refs: tuple[str, ...]
    rollback: RollbackSettings = RollbackSettings(
        RollbackCapability.UNKNOWN, RollbackPolicy.NOT_AVAILABLE
    )
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        _text(self.transaction_ref)
        _text(self.contract_version)
        _typed(self.binding, ArtifactBinding)
        _typed(self.authorization, ExecutionAuthorization)
        _typed(self.rollback, RollbackSettings)
        refs = tuple(self.step_refs)
        for ref in refs:
            _text(ref)
        _require(
            bool(refs) and len(set(refs)) == len(refs), "Explicit unique ordered steps required"
        )
        object.__setattr__(self, "step_refs", refs)


@dataclass(frozen=True)
class PrecommitFacts:
    binding: ArtifactBinding
    authorization_ref: str
    current_snapshot: NativeSnapshotRef
    safety_status: PreflightStatus
    safety_verdict: SafetyVerdict | None
    authorization_current: ObservedValue
    safety_current: ObservedValue
    targets_resolvable: ObservedValue
    executor_ready: ObservedValue
    recovery_required: bool

    def __post_init__(self) -> None:
        _typed(self.binding, ArtifactBinding)
        _text(self.authorization_ref)
        _typed(self.current_snapshot, NativeSnapshotRef)
        _typed(self.safety_status, PreflightStatus)
        if self.safety_verdict is not None:
            _typed(self.safety_verdict, SafetyVerdict)
        _require(
            (self.safety_status == PreflightStatus.EVALUATED) == (self.safety_verdict is not None),
            "Safety status/verdict axes must agree",
        )
        for fact in (
            self.authorization_current,
            self.safety_current,
            self.targets_resolvable,
            self.executor_ready,
        ):
            _typed(fact, ObservedValue)
        _typed_bool(self.recovery_required)


def _typed_bool(value: bool) -> None:
    if type(value) is not bool:
        raise TypeError("Explicit boolean required")


class PrecommitStatus(str, Enum):
    READY = "READY"
    STALE = "STALE"
    BLOCKED = "BLOCKED"


class PrecommitReason(str, Enum):
    READY = "READY"
    STALE_BASE = "STALE_BASE"
    ARTIFACT_MISMATCH = "ARTIFACT_MISMATCH"
    AUTHORIZATION_NOT_CURRENT = "AUTHORIZATION_NOT_CURRENT"
    SAFETY_NOT_CURRENT_PASS = "SAFETY_NOT_CURRENT_PASS"
    TARGETS_UNRESOLVED = "TARGETS_UNRESOLVED"
    EXECUTOR_NOT_READY = "EXECUTOR_NOT_READY"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    UNSUPPORTED_CONTRACT = "UNSUPPORTED_CONTRACT"


def _precommit_decision(
    definition: TransactionDefinition, facts: PrecommitFacts
) -> tuple[PrecommitStatus, tuple[PrecommitReason, ...]]:
    R = PrecommitReason
    reasons: set[PrecommitReason] = set()
    auth, binding = definition.authorization, definition.binding
    stale = (
        facts.current_snapshot != binding.base_snapshot
        or facts.binding.base_snapshot != binding.base_snapshot
        or auth.binding.base_snapshot != binding.base_snapshot
        or facts.safety_status == PreflightStatus.STALE
        or facts.authorization_current == ObservedValue.FALSE
        or facts.safety_current == ObservedValue.FALSE
    )
    if stale:
        reasons.add(R.STALE_BASE)
    if (
        facts.binding != binding
        or auth.binding != binding
        or facts.authorization_ref != auth.authorization_ref
    ):
        reasons.add(R.ARTIFACT_MISMATCH)
    if facts.authorization_current != ObservedValue.TRUE:
        reasons.add(R.AUTHORIZATION_NOT_CURRENT)
    if (
        facts.safety_current != ObservedValue.TRUE
        or facts.safety_status != PreflightStatus.EVALUATED
        or facts.safety_verdict != SafetyVerdict.PASS
    ):
        reasons.add(R.SAFETY_NOT_CURRENT_PASS)
    if facts.targets_resolvable != ObservedValue.TRUE:
        reasons.add(R.TARGETS_UNRESOLVED)
    if facts.executor_ready != ObservedValue.TRUE:
        reasons.add(R.EXECUTOR_NOT_READY)
    if facts.recovery_required:
        reasons.add(R.RECOVERY_REQUIRED)
    if definition.contract_version != "v1" or auth.contract_version != "v1":
        reasons.add(R.UNSUPPORTED_CONTRACT)
    status = (
        PrecommitStatus.STALE
        if stale
        else PrecommitStatus.BLOCKED
        if reasons
        else PrecommitStatus.READY
    )
    return status, tuple(sorted(reasons or {R.READY}, key=lambda r: r.value))


@dataclass(frozen=True)
class PrecommitResult:
    definition: TransactionDefinition
    facts: PrecommitFacts
    status: PrecommitStatus
    reasons: tuple[PrecommitReason, ...]

    def __post_init__(self) -> None:
        _typed(self.definition, TransactionDefinition)
        _typed(self.facts, PrecommitFacts)
        _typed(self.status, PrecommitStatus)
        reasons = tuple(self.reasons)
        for reason in reasons:
            _typed(reason, PrecommitReason)
        reasons = tuple(sorted(set(reasons), key=lambda r: r.value))
        _require(
            (self.status, reasons) == _precommit_decision(self.definition, self.facts),
            "Precommit result must retain actual fact evaluation",
        )
        object.__setattr__(self, "reasons", reasons)


def validate_precommit(definition: TransactionDefinition, facts: PrecommitFacts) -> PrecommitResult:
    _typed(definition, TransactionDefinition)
    _typed(facts, PrecommitFacts)
    status, reasons = _precommit_decision(definition, facts)
    return PrecommitResult(definition, facts, status, reasons)


@dataclass(frozen=True)
class CurrentAuthorityFacts:
    binding: ArtifactBinding
    authorization_ref: str
    current_snapshot: NativeSnapshotRef
    authorization_current: ObservedValue
    safety_pass_current: ObservedValue
    recovery_required: bool

    def __post_init__(self) -> None:
        _typed(self.binding, ArtifactBinding)
        _text(self.authorization_ref)
        _typed(self.current_snapshot, NativeSnapshotRef)
        _typed(self.authorization_current, ObservedValue)
        _typed(self.safety_pass_current, ObservedValue)
        _typed_bool(self.recovery_required)


def _authority_current(
    definition: TransactionDefinition, facts: CurrentAuthorityFacts, observed: NativeSnapshotRef
) -> bool:
    return (
        facts.binding == definition.binding == definition.authorization.binding
        and facts.authorization_ref == definition.authorization.authorization_ref
        and facts.authorization_current == ObservedValue.TRUE
        and facts.safety_pass_current == ObservedValue.TRUE
        and not facts.recovery_required
        and facts.current_snapshot == observed
        and observed.timeline_id == definition.binding.base_snapshot.timeline_id
    )


@dataclass(frozen=True)
class ExecutionStepResult:
    step_ref: str
    status: ExecutionStepStatus = ExecutionStepStatus.NOT_STARTED
    report_ref: str | None = None
    may_have_mutated: bool = False

    def __post_init__(self) -> None:
        _text(self.step_ref)
        _typed(self.status, ExecutionStepStatus)
        _typed_bool(self.may_have_mutated)
        if self.report_ref is not None:
            _text(self.report_ref)
        if self.status == ExecutionStepStatus.NOT_STARTED:
            _require(
                self.report_ref is None and not self.may_have_mutated,
                "Unstarted step has no execution report",
            )
        else:
            _require(self.report_ref is not None, "Step outcome needs evidence reference")
        if self.status in (ExecutionStepStatus.SUCCEEDED, ExecutionStepStatus.OUTCOME_UNKNOWN):
            _require(self.may_have_mutated, "Success/uncertainty cannot assert no mutation")


@dataclass(frozen=True)
class StepReconciliation:
    binding: ArtifactBinding
    unknown_report_ref: str
    classification: ExecutionStepResult
    observed_snapshot: NativeSnapshotRef
    current_snapshot: NativeSnapshotRef
    evidence_ref: str

    def __post_init__(self) -> None:
        _typed(self.binding, ArtifactBinding)
        _text(self.unknown_report_ref)
        _text(self.evidence_ref)
        _typed(self.classification, ExecutionStepResult)
        _typed(self.observed_snapshot, NativeSnapshotRef)
        _typed(self.current_snapshot, NativeSnapshotRef)
        _require(
            self.classification.status
            in (ExecutionStepStatus.SUCCEEDED, ExecutionStepStatus.FAILED),
            "Reconciliation must explicitly classify the observation",
        )


@dataclass(frozen=True)
class PostflightEvidence:
    verification_ref: str
    binding: ArtifactBinding
    status: DiffVerificationStatus
    observed_snapshot: NativeSnapshotRef
    current: CurrentAuthorityFacts

    def __post_init__(self) -> None:
        _text(self.verification_ref)
        _typed(self.binding, ArtifactBinding)
        _typed(self.status, DiffVerificationStatus)
        _typed(self.observed_snapshot, NativeSnapshotRef)
        _typed(self.current, CurrentAuthorityFacts)


@dataclass(frozen=True)
class RollbackRequest:
    automatic: bool

    def __post_init__(self) -> None:
        _typed_bool(self.automatic)


@dataclass(frozen=True)
class RollbackCommandReport:
    report_ref: str
    status: ExecutionStepStatus

    def __post_init__(self) -> None:
        _text(self.report_ref)
        _typed(self.status, ExecutionStepStatus)
        _require(
            self.status != ExecutionStepStatus.NOT_STARTED,
            "Rollback command report requires an outcome",
        )


@dataclass(frozen=True)
class BaseVerificationEvidence:
    evidence_ref: str
    binding: ArtifactBinding
    status: DiffVerificationStatus
    observed_snapshot: NativeSnapshotRef
    current_snapshot: NativeSnapshotRef

    def __post_init__(self) -> None:
        _text(self.evidence_ref)
        _typed(self.binding, ArtifactBinding)
        _typed(self.status, DiffVerificationStatus)
        _typed(self.observed_snapshot, NativeSnapshotRef)
        _typed(self.current_snapshot, NativeSnapshotRef)


class TransactionEventKind(str, Enum):
    TRANSACTION_PREPARED = "TRANSACTION_PREPARED"
    PRECOMMIT_STARTED = "PRECOMMIT_STARTED"
    PRECOMMIT_PASSED = "PRECOMMIT_PASSED"
    PRECOMMIT_FAILED = "PRECOMMIT_FAILED"
    STEP_STARTED = "STEP_STARTED"
    STEP_SUCCEEDED = "STEP_SUCCEEDED"
    STEP_FAILED = "STEP_FAILED"
    STEP_OUTCOME_UNKNOWN = "STEP_OUTCOME_UNKNOWN"
    RECONCILIATION_RECORDED = "RECONCILIATION_RECORDED"
    POSTFLIGHT_STARTED = "POSTFLIGHT_STARTED"
    POSTFLIGHT_MATCHED = "POSTFLIGHT_MATCHED"
    POSTFLIGHT_MISMATCH = "POSTFLIGHT_MISMATCH"
    POSTFLIGHT_UNVERIFIED = "POSTFLIGHT_UNVERIFIED"
    POSTFLIGHT_STALE = "POSTFLIGHT_STALE"
    ROLLBACK_STARTED = "ROLLBACK_STARTED"
    ROLLBACK_COMMAND_COMPLETED = "ROLLBACK_COMMAND_COMPLETED"
    ROLLBACK_VERIFIED = "ROLLBACK_VERIFIED"
    ROLLBACK_FAILED = "ROLLBACK_FAILED"
    TRANSACTION_TERMINATED = "TRANSACTION_TERMINATED"


EventPayload: TypeAlias = (
    None
    | str
    | TransactionDefinition
    | PrecommitFacts
    | ExecutionStepResult
    | StepReconciliation
    | PostflightEvidence
    | RollbackRequest
    | RollbackCommandReport
    | BaseVerificationEvidence
    | TransactionOutcome
)


@dataclass(frozen=True)
class TransactionEvent:
    transaction_ref: str
    sequence_no: int
    kind: TransactionEventKind
    payload: EventPayload = None

    def __post_init__(self) -> None:
        _text(self.transaction_ref)
        if type(self.sequence_no) is not int or self.sequence_no <= 0:
            raise ValueError("Positive explicit integer sequence required")
        _typed(self.kind, TransactionEventKind)
        E = TransactionEventKind
        expected: dict[TransactionEventKind, type[object]] = {
            E.TRANSACTION_PREPARED: TransactionDefinition,
            E.PRECOMMIT_STARTED: type(None),
            E.PRECOMMIT_PASSED: PrecommitFacts,
            E.PRECOMMIT_FAILED: PrecommitFacts,
            E.STEP_STARTED: str,
            E.STEP_SUCCEEDED: ExecutionStepResult,
            E.STEP_FAILED: ExecutionStepResult,
            E.STEP_OUTCOME_UNKNOWN: ExecutionStepResult,
            E.RECONCILIATION_RECORDED: StepReconciliation,
            E.POSTFLIGHT_STARTED: type(None),
            E.POSTFLIGHT_MATCHED: PostflightEvidence,
            E.POSTFLIGHT_MISMATCH: PostflightEvidence,
            E.POSTFLIGHT_UNVERIFIED: PostflightEvidence,
            E.POSTFLIGHT_STALE: PostflightEvidence,
            E.ROLLBACK_STARTED: RollbackRequest,
            E.ROLLBACK_COMMAND_COMPLETED: RollbackCommandReport,
            E.ROLLBACK_VERIFIED: BaseVerificationEvidence,
            E.ROLLBACK_FAILED: BaseVerificationEvidence,
            E.TRANSACTION_TERMINATED: TransactionOutcome,
        }
        _typed(self.payload, expected[self.kind])
        if self.kind == E.STEP_STARTED:
            _require(type(self.payload) is str, "Step refs cannot be lifecycle enums")
            assert isinstance(self.payload, str)
            _text(self.payload)


@dataclass(frozen=True)
class TransactionJournal:
    events: tuple[TransactionEvent, ...]

    def __post_init__(self) -> None:
        events = tuple(self.events)
        for event in events:
            _typed(event, TransactionEvent)
        _require(
            all(a.sequence_no < b.sequence_no for a, b in pairwise(events)),
            "Journal sequence must be strictly increasing; never reorder evidence",
        )
        _require(len({e.transaction_ref for e in events}) <= 1, "Mixed transaction journal")
        object.__setattr__(self, "events", events)

    def append(self, event: TransactionEvent) -> "TransactionJournal":
        return TransactionJournal((*self.events, event))


@dataclass(frozen=True)
class TransactionState:
    definition: TransactionDefinition
    phase: TransactionPhase
    outcome: TransactionOutcome
    steps: tuple[ExecutionStepResult, ...]
    active_step_ref: str | None = None
    precommit: PrecommitResult | None = None
    postflight: PostflightEvidence | None = None
    rollback_origin: TransactionPhase | None = None
    rollback_report: RollbackCommandReport | None = None
    base_verification: BaseVerificationEvidence | None = None

    def __post_init__(self) -> None:
        _typed(self.definition, TransactionDefinition)
        _typed(self.phase, TransactionPhase)
        _typed(self.outcome, TransactionOutcome)
        steps = tuple(self.steps)
        for step in steps:
            _typed(step, ExecutionStepResult)
        _require(
            tuple(s.step_ref for s in steps) == self.definition.step_refs,
            "Every planned step must remain accounted for",
        )
        object.__setattr__(self, "steps", steps)
        _require(
            (self.phase == TransactionPhase.TERMINAL) == (self.outcome != TransactionOutcome.NONE),
            "Phase and terminal outcome axes must agree",
        )
        for value, kind in (
            (self.precommit, PrecommitResult),
            (self.postflight, PostflightEvidence),
            (self.rollback_report, RollbackCommandReport),
            (self.base_verification, BaseVerificationEvidence),
        ):
            if value is not None:
                _typed(value, kind)
        if self.active_step_ref is not None:
            _text(self.active_step_ref)
            _require(
                self.phase == TransactionPhase.APPLYING
                and any(
                    s.step_ref == self.active_step_ref
                    and s.status == ExecutionStepStatus.NOT_STARTED
                    for s in steps
                ),
                "Active step must be the unreported applying step",
            )
        if self.rollback_origin is not None:
            _typed(self.rollback_origin, TransactionPhase)
            _require(
                self.rollback_origin
                in (TransactionPhase.APPLYING, TransactionPhase.POSTFLIGHT_VERIFYING),
                "Rollback origin must preserve its failure stage",
            )
        if self.phase in (TransactionPhase.PREPARED, TransactionPhase.PRECOMMIT_VALIDATING):
            _require(
                self.precommit is None
                and self.postflight is None
                and self.rollback_origin is None
                and self.active_step_ref is None
                and all(s.status == ExecutionStepStatus.NOT_STARTED for s in steps),
                "Pre-mutation phases cannot contain execution evidence",
            )
        if self.phase in (
            TransactionPhase.APPLYING,
            TransactionPhase.POSTFLIGHT_VERIFYING,
            TransactionPhase.ROLLING_BACK,
        ):
            _require(
                self.precommit is not None and self.precommit.status == PrecommitStatus.READY,
                "Execution phases require a successful precommit",
            )
        if self.phase == TransactionPhase.APPLYING:
            _require(
                self.postflight is None and self.rollback_origin is None,
                "Applying cannot contain later-phase evidence",
            )
        if self.phase == TransactionPhase.POSTFLIGHT_VERIFYING:
            _require(
                self.all_steps_accounted
                and all(s.status == ExecutionStepStatus.SUCCEEDED for s in steps)
                and self.rollback_origin is None,
                "Postflight cannot skip successful step accounting",
            )
        if self.phase == TransactionPhase.ROLLING_BACK:
            _require(
                self.rollback_origin is not None and not self.unresolved_step_outcome,
                "Rollback must retain a reconciled failure origin",
            )
        if self.rollback_report is not None or self.base_verification is not None:
            _require(
                self.rollback_origin is not None, "Recovery evidence requires rollback history"
            )
        if self.outcome == TransactionOutcome.VERIFIED_COMMITTED:
            _require(
                _commit_ready(self),
                "Commit requires successful steps, precommit and current postflight MATCH",
            )
        if self.outcome in (
            TransactionOutcome.ABORTED_STALE,
            TransactionOutcome.FAILED_BEFORE_MUTATION,
        ):
            _require(
                self.active_step_ref is None and not any(s.may_have_mutated for s in steps),
                "Before-mutation failure cannot contain mutated or uncertain steps",
            )
        if self.outcome in (
            TransactionOutcome.FAILED_PARTIAL_RECOVERED,
            TransactionOutcome.FAILED_POSTFLIGHT_RECOVERED,
        ):
            _require(
                self.base_verification is not None
                and self.base_verification.status == DiffVerificationStatus.MATCH
                and self.rollback_report is not None
                and not self.unresolved_step_outcome,
                "Recovered failure requires explicit fresh base verification",
            )

    @property
    def unresolved_step_outcome(self) -> bool:
        return self.active_step_ref is not None or any(
            s.status == ExecutionStepStatus.OUTCOME_UNKNOWN for s in self.steps
        )

    @property
    def all_steps_accounted(self) -> bool:
        return self.active_step_ref is None and all(
            s.status in (ExecutionStepStatus.SUCCEEDED, ExecutionStepStatus.FAILED)
            for s in self.steps
        )

    @property
    def recovery_required(self) -> bool:
        return (
            self.outcome
            in (
                TransactionOutcome.FAILED_PARTIAL_UNRECOVERED,
                TransactionOutcome.FAILED_POSTFLIGHT_UNRECOVERED,
            )
            or (self.precommit is not None and self.precommit.facts.recovery_required)
            or (self.postflight is not None and self.postflight.current.recovery_required)
        )

    @property
    def new_destructive_execution_eligible(self) -> bool:
        """Lockdown gate only, never authorization for another transaction."""
        return (
            self.phase == TransactionPhase.TERMINAL
            and not self.recovery_required
            and self.outcome != TransactionOutcome.UNVERIFIED_APPLY
            and not self.unresolved_step_outcome
        )

    @property
    def retry_eligible(self) -> bool:
        return False  # No retry path is implemented, including after reconciliation.


def _commit_ready(state: TransactionState) -> bool:
    post = state.postflight
    return (
        state.precommit is not None
        and state.precommit.status == PrecommitStatus.READY
        and state.all_steps_accounted
        and all(s.status == ExecutionStepStatus.SUCCEEDED for s in state.steps)
        and post is not None
        and post.binding == state.definition.binding
        and post.status == DiffVerificationStatus.MATCH
        and _authority_current(state.definition, post.current, post.observed_snapshot)
        and not state.recovery_required
        and state.rollback_origin is None
    )


def _fresh(
    binding: ArtifactBinding, observed: NativeSnapshotRef, current: NativeSnapshotRef
) -> bool:
    return observed == current and observed.timeline_id == binding.base_snapshot.timeline_id


def _replay(definition: TransactionDefinition, journal: TransactionJournal) -> TransactionState:
    E, P, O, Step = TransactionEventKind, TransactionPhase, TransactionOutcome, ExecutionStepStatus
    _require(
        bool(journal.events) and journal.events[0].kind == E.TRANSACTION_PREPARED,
        "Journal must begin prepared",
    )
    _require(
        all(e.transaction_ref == definition.transaction_ref for e in journal.events),
        "Wrong transaction journal",
    )
    _require(
        journal.events[0].payload == definition,
        "Prepared artifact bindings cannot be swapped or reinterpreted",
    )
    phase, outcome = P.PREPARED, O.NONE
    steps = {ref: ExecutionStepResult(ref) for ref in definition.step_refs}
    active: str | None = None
    precommit: PrecommitResult | None = None
    post: PostflightEvidence | None = None
    origin: TransactionPhase | None = None
    rollback_report: RollbackCommandReport | None = None
    base_proof: BaseVerificationEvidence | None = None

    def state() -> TransactionState:
        return TransactionState(
            definition,
            phase,
            outcome,
            tuple(steps.values()),
            active,
            precommit,
            post,
            origin,
            rollback_report,
            base_proof,
        )

    for event in journal.events[1:]:
        _require(phase != P.TERMINAL, "Terminal history cannot be rewritten or resumed")
        kind, payload = event.kind, event.payload
        if kind == E.PRECOMMIT_STARTED:
            _require(phase == P.PREPARED, "Precommit must follow preparation")
            phase = P.PRECOMMIT_VALIDATING
        elif kind in (E.PRECOMMIT_PASSED, E.PRECOMMIT_FAILED):
            _require(phase == P.PRECOMMIT_VALIDATING, "Precommit result out of phase")
            assert isinstance(payload, PrecommitFacts)
            precommit = validate_precommit(definition, payload)
            _require(
                (kind == E.PRECOMMIT_PASSED) == (precommit.status == PrecommitStatus.READY),
                "Incorrect precommit event classification",
            )
            if precommit.status == PrecommitStatus.READY:
                phase = P.APPLYING
            else:
                phase = P.TERMINAL
                outcome = (
                    O.ABORTED_STALE
                    if precommit.status == PrecommitStatus.STALE
                    else O.FAILED_BEFORE_MUTATION
                )
        elif kind == E.STEP_STARTED:
            _require(
                phase == P.APPLYING and active is None, "Only one execution step may be active"
            )
            _require(
                not any(s.status in (Step.FAILED, Step.OUTCOME_UNKNOWN) for s in steps.values()),
                "Failure/uncertainty blocks destructive continuation",
            )
            assert isinstance(payload, str)
            next_step = next(
                (s.step_ref for s in steps.values() if s.status == Step.NOT_STARTED), None
            )
            _require(payload == next_step, "Steps must follow the declared order; no retry")
            active = payload
        elif kind in (E.STEP_SUCCEEDED, E.STEP_FAILED, E.STEP_OUTCOME_UNKNOWN):
            assert isinstance(payload, ExecutionStepResult)
            _require(
                phase == P.APPLYING and active == payload.step_ref,
                "Step report requires its active started step",
            )
            required_status = {
                E.STEP_SUCCEEDED: Step.SUCCEEDED,
                E.STEP_FAILED: Step.FAILED,
                E.STEP_OUTCOME_UNKNOWN: Step.OUTCOME_UNKNOWN,
            }[kind]
            _require(payload.status == required_status, "Step report event/status mismatch")
            steps[payload.step_ref] = payload
            active = None
        elif kind == E.RECONCILIATION_RECORDED:
            assert isinstance(payload, StepReconciliation)
            prior = steps.get(payload.classification.step_ref)
            _require(
                phase == P.APPLYING
                and active is None
                and prior is not None
                and prior.status == Step.OUTCOME_UNKNOWN
                and prior.report_ref == payload.unknown_report_ref,
                "Reconciliation must refer to the unresolved command report",
            )
            _require(
                payload.binding == definition.binding
                and _fresh(payload.binding, payload.observed_snapshot, payload.current_snapshot),
                "Reconciliation requires fresh bound observation",
            )
            steps[payload.classification.step_ref] = payload.classification
        elif kind == E.POSTFLIGHT_STARTED:
            _require(
                phase == P.APPLYING
                and active is None
                and all(s.status == Step.SUCCEEDED for s in steps.values()),
                "Postflight requires all steps successfully accounted for",
            )
            phase = P.POSTFLIGHT_VERIFYING
        elif kind in (
            E.POSTFLIGHT_MATCHED,
            E.POSTFLIGHT_MISMATCH,
            E.POSTFLIGHT_UNVERIFIED,
            E.POSTFLIGHT_STALE,
        ):
            assert isinstance(payload, PostflightEvidence)
            _require(
                phase == P.POSTFLIGHT_VERIFYING and post is None,
                "Postflight result out of phase or duplicate",
            )
            expected_status = {
                E.POSTFLIGHT_MATCHED: DiffVerificationStatus.MATCH,
                E.POSTFLIGHT_MISMATCH: DiffVerificationStatus.MISMATCH,
                E.POSTFLIGHT_UNVERIFIED: DiffVerificationStatus.UNVERIFIED,
                E.POSTFLIGHT_STALE: DiffVerificationStatus.STALE,
            }[kind]
            _require(
                payload.status == expected_status and payload.binding == definition.binding,
                "Postflight status/artifact mismatch",
            )
            if payload.status == DiffVerificationStatus.MATCH:
                _require(
                    _fresh(
                        payload.binding, payload.observed_snapshot, payload.current.current_snapshot
                    ),
                    "Stale observation cannot claim MATCH",
                )
            post = payload
        elif kind == E.ROLLBACK_STARTED:
            assert isinstance(payload, RollbackRequest)
            _require(
                _rollback_trigger(state()),
                "Rollback requires a reconciled failure with possible mutation",
            )
            policy = definition.rollback.policy
            _require(
                policy != RollbackPolicy.NOT_AVAILABLE
                and (not payload.automatic or policy == RollbackPolicy.AUTO_ELIGIBLE),
                "Rollback request exceeds supplied capability/policy",
            )
            origin, phase = phase, P.ROLLING_BACK
        elif kind == E.ROLLBACK_COMMAND_COMPLETED:
            assert isinstance(payload, RollbackCommandReport)
            _require(
                phase == P.ROLLING_BACK and rollback_report is None,
                "Unexpected or repeated rollback report",
            )
            rollback_report = payload
        elif kind in (E.ROLLBACK_VERIFIED, E.ROLLBACK_FAILED):
            assert isinstance(payload, BaseVerificationEvidence)
            _require(
                phase == P.ROLLING_BACK and rollback_report is not None and base_proof is None,
                "Base verification must follow rollback command report once",
            )
            _require(payload.binding == definition.binding, "Wrong rollback verification base")
            _require(
                (kind == E.ROLLBACK_VERIFIED) == (payload.status == DiffVerificationStatus.MATCH),
                "Incorrect recovery classification",
            )
            if payload.status == DiffVerificationStatus.MATCH:
                _require(
                    _fresh(payload.binding, payload.observed_snapshot, payload.current_snapshot),
                    "Stale base verification cannot recover",
                )
            base_proof = payload
        elif kind == E.TRANSACTION_TERMINATED:
            assert isinstance(payload, TransactionOutcome)
            before = state()
            _require(
                active is None,
                "An active command must be explicitly accounted for, including UNKNOWN",
            )
            mutated = any(s.may_have_mutated for s in steps.values())
            failed = any(s.status in (Step.FAILED, Step.OUTCOME_UNKNOWN) for s in steps.values())
            recovered = base_proof is not None and base_proof.status == DiffVerificationStatus.MATCH
            allowed: set[TransactionOutcome] = set()
            if phase == P.APPLYING:
                if not mutated:
                    allowed.add(O.FAILED_BEFORE_MUTATION)
                elif failed:
                    allowed.add(O.FAILED_PARTIAL_UNRECOVERED)
            elif phase == P.POSTFLIGHT_VERIFYING and post is not None:
                if _commit_ready(before):
                    allowed.add(O.VERIFIED_COMMITTED)
                else:
                    allowed.add(O.FAILED_POSTFLIGHT_UNRECOVERED)
                    if post.status != DiffVerificationStatus.MISMATCH:
                        allowed.add(O.UNVERIFIED_APPLY)
            elif phase == P.ROLLING_BACK:
                if origin == P.APPLYING:
                    allowed.add(
                        O.FAILED_PARTIAL_RECOVERED if recovered else O.FAILED_PARTIAL_UNRECOVERED
                    )
                elif origin == P.POSTFLIGHT_VERIFYING:
                    allowed.add(
                        O.FAILED_POSTFLIGHT_RECOVERED
                        if recovered
                        else O.FAILED_POSTFLIGHT_UNRECOVERED
                    )
            _require(
                payload in allowed,
                "Terminal outcome is not supported by this phase/history/evidence",
            )
            phase, outcome = P.TERMINAL, payload
        else:
            raise ValueError("Prepared event may occur only once")
    return state()


def _rollback_trigger(state: TransactionState) -> bool:
    if state.unresolved_step_outcome or not any(s.may_have_mutated for s in state.steps):
        return False
    if state.phase == TransactionPhase.APPLYING:
        return any(s.status == ExecutionStepStatus.FAILED for s in state.steps)
    return (
        state.phase == TransactionPhase.POSTFLIGHT_VERIFYING
        and state.postflight is not None
        and state.postflight.status != DiffVerificationStatus.MATCH
    )


@dataclass(frozen=True)
class Transaction:
    definition: TransactionDefinition
    journal: TransactionJournal

    def __post_init__(self) -> None:
        _typed(self.definition, TransactionDefinition)
        _typed(self.journal, TransactionJournal)
        _replay(self.definition, self.journal)

    @property
    def state(self) -> TransactionState:
        return _replay(self.definition, self.journal)


def prepare_transaction(definition: TransactionDefinition, sequence_no: int = 1) -> Transaction:
    _typed(definition, TransactionDefinition)
    return Transaction(
        definition,
        TransactionJournal(
            (
                TransactionEvent(
                    definition.transaction_ref,
                    sequence_no,
                    TransactionEventKind.TRANSACTION_PREPARED,
                    definition,
                ),
            )
        ),
    )


def transition(transaction: Transaction, event: TransactionEvent) -> Transaction:
    _typed(transaction, Transaction)
    _typed(event, TransactionEvent)
    return Transaction(transaction.definition, transaction.journal.append(event))


def automatic_rollback_eligible(transaction: Transaction) -> bool:
    _typed(transaction, Transaction)
    return (
        transaction.definition.rollback.capability == RollbackCapability.SUPPORTED_VERIFIED
        and transaction.definition.rollback.policy == RollbackPolicy.AUTO_ELIGIBLE
        and _rollback_trigger(transaction.state)
    )


class PromotionEligibility(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


def promotion_eligibility(
    transaction: Transaction, facts: CurrentAuthorityFacts
) -> PromotionEligibility:
    _typed(transaction, Transaction)
    _typed(facts, CurrentAuthorityFacts)
    state = transaction.state
    if (
        state.phase == TransactionPhase.TERMINAL
        and state.outcome == TransactionOutcome.VERIFIED_COMMITTED
        and _commit_ready(state)
        and state.postflight is not None
        and _authority_current(transaction.definition, facts, state.postflight.observed_snapshot)
    ):
        return PromotionEligibility.ELIGIBLE
    return PromotionEligibility.NOT_ELIGIBLE
