"""VS-001G declarations only: supplied evidence, never runtime qualification.

The five ports own production, not certification by shared application code.
Existing immutable domain payloads and their state machines remain authoritative.
Receipts describe provenance; neither matching tokens nor new receipt strings prove
currentness. Authenticity, acquisition ordering, completeness, and the unresolved
observation-to-execution race remain producer obligations (OPEN-002/008).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Generic, Literal, Protocol, TypeAlias, TypeVar

from . import authority as a
from . import execution_ir as ir
from . import expected_diff as d
from . import native_snapshot as n
from . import orchestration as o
from . import safety_preflight as s
from . import transaction as t

T = TypeVar("T")


class PortIssueKind(str, Enum):
    """Call availability/uncertainty, not domain lifecycle or readiness states."""

    UNAVAILABLE = "UNAVAILABLE"
    UNSUPPORTED = "UNSUPPORTED"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    STALE = "STALE"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PortReceipt:
    """Producer assertion, not an authentication, freshness, or ordering proof.

    source_refs link the supplied payload to its actual inputs/observations. Producers
    retain the corresponding records and acquisition semantics. acquisition_ref names
    that acquisition, not this receipt; relabeling a receipt is not a fresh acquisition.
    None means no acquisition was established. Limitations must expose missing timing,
    atomicity, scope, or authenticity guarantees. No native token is generated here.
    """

    receipt_ref: str
    producer_ref: str
    acquisition_ref: str | None
    source_refs: tuple[str, ...]
    limitations: tuple[str, ...]
    evidence_domain: Literal["PRODUCER_ASSERTION", "TEST_ONLY_SUPPORT"]

    def __post_init__(self) -> None:
        for value in (self.receipt_ref, self.producer_ref):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Explicit receipt and producer references required")
        if self.acquisition_ref is not None and (
            not isinstance(self.acquisition_ref, str) or not self.acquisition_ref.strip()
        ):
            raise ValueError("Acquisition reference must be nonempty or absent")
        for name in ("source_refs", "limitations"):
            values = tuple(getattr(self, name))
            if any(not isinstance(value, str) or not value.strip() for value in values):
                raise ValueError("Receipt metadata must contain nonempty strings")
            object.__setattr__(self, name, values)
        if self.evidence_domain not in ("PRODUCER_ASSERTION", "TEST_ONLY_SUPPORT"):
            raise ValueError("Receipt domain is an assertion context, not qualification")


@dataclass(frozen=True)
class PortValue(Generic[T]):
    """An available immutable payload, not a claim that its domain status is READY."""

    value: T
    receipt: PortReceipt

    def __post_init__(self) -> None:
        if not isinstance(self.receipt, PortReceipt):
            raise TypeError("Typed producer receipt required")


@dataclass(frozen=True)
class PortIssue:
    """Ordinary non-success; never substitute this object for an execution journal."""

    kind: PortIssueKind
    reason: str
    receipt: PortReceipt

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PortIssueKind) or not isinstance(self.receipt, PortReceipt):
            raise TypeError("Typed issue kind and producer receipt required")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("Explicit non-success reason required")


PortResult: TypeAlias = PortValue[T] | PortIssue
CurrentnessPayload: TypeAlias = tuple[n.NativeTimelineSnapshot, t.CurrentAuthorityFacts]
PostflightPayload: TypeAlias = tuple[n.NativeTimelineSnapshot, d.ActualDiff]
ResolutionPayload: TypeAlias = tuple[
    ir.ExecutionIRValidationInput,
    t.TransactionDefinition,
    n.ObservedValue,  # targets_resolvable
    n.ObservedValue,  # executor_ready
]
LifecycleResult: TypeAlias = tuple[t.Transaction, PortIssue | None]
PublicationDisposition: TypeAlias = Literal["PERSISTED", "DUPLICATE"]


class RuntimeObservationPort(Protocol):
    """Read-only currentness and independent post-state observation (A + D)."""

    def observe_currentness(
        self,
        authorization: t.ExecutionAuthorization,
        safety: s.SafetyPreflightResult,
        authority: PortValue[a.CandidateWorkState],
        recovery: PortValue[n.ObservedValue],
        *,
        purpose: Literal["admission", "postflight", "promotion"],
    ) -> PortResult[CurrentnessPayload]:
        """UNKNOWN recovery returns PortIssue before constructing boolean facts.

        Read actual authorization/Safety/human-change evidence; equality alone is
        insufficient. No target capability, command, or state-token fabrication.
        Postflight and promotion require separate real acquisitions, not renamed
        receipts. Missing atomicity/authenticity guarantees remain explicit.
        """
        ...

    def observe_postflight(
        self,
        binding: t.ArtifactBinding,
        scope: d.PreservationScope,
        before: PortValue[CurrentnessPayload],
        *,
        targets: tuple[ir.ExecutionTargetBinding, ...],
        transaction: t.Transaction,
    ) -> PortResult[PostflightPayload]:
        """Derive ActualDiff from retained pre-state and fresh post observations.

        targets retain the admitted semantic/native correspondence and pre-reads;
        transaction supplies exact journal context for the post-read ordering link.
        Neither command acknowledgment nor expected effect values are actual evidence.

        Scope/binding references correlate evidence only; no expected changed
        values are inputs. Own identity, relation, topology, and scope coverage
        evidence. Missing coverage must not become an empty successful diff.
        Return existing unverified evidence where representable, otherwise issue.
        """
        ...


class ExecutionResolutionPort(Protocol):
    """Read-only target/capability/effect/lowering and readiness responsibility B."""

    def resolve_execution(
        self,
        authorized: o.AuthorizedEdit,
        currentness: PortValue[CurrentnessPayload],
    ) -> PortResult[ResolutionPayload]:
        """Return exact existing components and observed target/executor readiness.

        Construct execution-grade IR only after runtime resolution. Retain supplied
        currentness and exact approved artifacts, ordered lowering steps, runtime
        profile, and rollback capability. No mutation, ActualDiff, or commit.
        Integration composes PrecommitFacts and RuntimeAdmissionEvidence outside
        orchestration; unavailable required components yield an issue, not fillers.
        """
        ...


class ExecutionLifecyclePort(Protocol):
    """Responsibility C; transaction.py exclusively defines lifecycle semantics.

    All lifecycle methods return the latest Transaction, including ordinary
    uncertainty. Preserve exact prefix and events through transaction.transition.
    Retain STEP_STARTED before dispatch and real outcomes as they happen; never
    reconstruct execution after the fact. No parallel machine or automatic retry.
    Programming defects may raise, but a defect after possible dispatch must not
    discard history: stop and return the latest journal with explicit uncertainty.
    Crash-safe retention/exactly-once ownership remains unresolved, not promised.
    """

    def observe_recovery_required(
        self,
        authorization: t.ExecutionAuthorization,
    ) -> PortResult[n.ObservedValue]:
        """Assess relevant recovery context; absence of known history is not FALSE."""
        ...

    def execute_next(
        self,
        admission: o.AdmissionResult,
        transaction: t.Transaction,
    ) -> LifecycleResult:
        """Own STEP_STARTED and the actual step report for the next declared step.

        Require a READY admission and its exact journal prefix. Before dispatch,
        refusal may preserve a pre-mutation journal. After possible dispatch, keep
        STEP_STARTED; append OUTCOME_UNKNOWN only with an explicit valid report,
        otherwise keep the active step plus UNKNOWN issue. Never infer FAILED or
        SUCCEEDED from response loss. Stop; uncertainty does not authorize retry.
        """
        ...

    def reconcile(
        self,
        admission: o.AdmissionResult,
        transaction: t.Transaction,
    ) -> LifecycleResult:
        """Record StepReconciliation only from an actual read/observation producer.

        Acknowledgment/command return is not read evidence. Missing, ambiguous,
        stale, or failed observations preserve the journal and typed uncertainty.
        Reconciliation does not grant a retry; existing transaction rules apply.
        """
        ...

    def rollback(
        self,
        admission: o.AdmissionResult,
        transaction: t.Transaction,
        request: t.RollbackRequest,
    ) -> LifecycleResult:
        """Preserve rollback request/report events within existing capability policy.

        Command success is not recovery. BaseVerificationEvidence must come from
        independent read/observation before verified recovery can be represented.
        Unknown recovery remains UNKNOWN at the port layer; retain latest journal.
        """
        ...


class ApplicationResultPort(Protocol):
    """Responsibility E; production identity architecture remains OPEN-002."""

    def resolve_application_result(
        self,
        authorized: o.AuthorizedEdit,
        transaction: t.Transaction,
        postflight: PortValue[PostflightPayload],
    ) -> PortResult[o.ApplicationResultEvidence]:
        """Supply existing result correspondence only when independently established.

        VERIFIED_COMMITTED does not force success. Unavailable/unresolved/ambiguous/
        stale/unknown evidence blocks promotion while retaining historical commit.
        Never invent a result ID, next version, or ApplicationRecord from success.
        """
        ...


class AuthorityPort(Protocol):
    """Responsibility F: authority read and future conditional publication only.

    No concurrency algorithm, conditional-write mechanism, or exactly-once claim
    is selected. OPEN-008 remains open; semantic acceptance is not durable success.
    """

    def read(self, candidate_id: a.CandidateId) -> PortResult[a.CandidateWorkState]:
        """Return supplied authority state plus read receipt, not native certification."""
        ...

    def publish(
        self,
        expected: PortValue[a.CandidateWorkState],
        proposal: o.FinalizationResult,
        promotion: PortValue[CurrentnessPayload],
    ) -> PortResult[PublicationDisposition]:
        """Compare expected authority and conditionally publish accepted transitions.

        PERSISTED requires durable evidence of the complete proposal. DUPLICATE
        requires evidence of that same prior durable publication, not value equality.
        STALE/CONFLICT/UNAVAILABLE/UNKNOWN use distinct PortIssue kinds. Unknown write
        outcome is not failure certainty or permission to retry. Preserve historical
        Transaction and FinalizationResult.durable_promotion == NOT_PERFORMED.
        """
        ...
