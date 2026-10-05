"""Pure candidate state contracts. Supplied evidence is fake data, not native proof.

Nothing here applies an edit, runs postflight, observes Resolve or authorizes bypassing
Safety Core. Production result identity and authority storage remain OPEN-002/008.
"""

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import NewType, TypeAlias

from .domain import TimelineId, TimelineVersion

CandidateId = NewType("CandidateId", str)


class SelectionState(str, Enum):
    UNSELECTED = "UNSELECTED"
    SELECTED = "SELECTED"


class ApprovalState(str, Enum):
    NOT_APPROVED = "NOT_APPROVED"
    APPROVED = "APPROVED"


class CandidateValidity(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"


class ApplicationState(str, Enum):
    NOT_APPLIED = "NOT_APPLIED"
    APPLIED = "APPLIED"


class VerificationState(str, Enum):
    NOT_VERIFIED = "NOT_VERIFIED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class PromotionState(str, Enum):
    NOT_PROMOTED = "NOT_PROMOTED"
    PROMOTED = "PROMOTED"


class WorkPhase(str, Enum):
    """Descriptive progress only; no scheduler, DIRTY or recomputation semantics."""

    ANALYZING = "ANALYZING"
    BUILDING_CANDIDATE = "BUILDING_CANDIDATE"
    READY = "READY"


class TransitionReason(str, Enum):
    ACCEPTED = "ACCEPTED"
    ELIGIBLE_FOR_ATTEMPT = "ELIGIBLE_FOR_ATTEMPT"
    STALE = "STALE"
    NOT_APPROVED = "NOT_APPROVED"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    NOT_APPLIED = "NOT_APPLIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    ALREADY_VERIFIED = "ALREADY_VERIFIED"
    ALREADY_PROMOTED = "ALREADY_PROMOTED"
    EVIDENCE_MISMATCH = "EVIDENCE_MISMATCH"
    RESULT_MISMATCH = "RESULT_MISMATCH"
    WRONG_AUTHORITY = "WRONG_AUTHORITY"
    OLDER_OBSERVATION = "OLDER_OBSERVATION"
    UNSUPPORTED_EVENT = "UNSUPPORTED_EVENT"


def _identity(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("Identity must be a string")
    if not value.strip():
        raise ValueError("Identity must not be empty")


@dataclass(frozen=True)
class CandidateBase:
    timeline_id: TimelineId
    timeline_version: TimelineVersion

    def __post_init__(self) -> None:
        _identity(self.timeline_id)
        if type(self.timeline_version) is not int:
            raise TypeError("Version must be an integer")
        if self.timeline_version < 0:
            raise ValueError("Version must be nonnegative")


@dataclass(frozen=True)
class CandidateLineage:
    ancestors: tuple[CandidateId, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ancestors", tuple(self.ancestors))
        for ancestor in self.ancestors:
            _identity(ancestor)
        if len(set(self.ancestors)) != len(self.ancestors):
            raise ValueError("Candidate lineage cannot contain cycles or duplicate ancestors")


@dataclass(frozen=True)
class CandidateResultRef:
    """Caller-supplied opaque fake result token and observed reference, not Resolve ID."""

    result_id: str
    reference: CandidateBase

    def __post_init__(self) -> None:
        _identity(self.result_id)
        if not isinstance(self.reference, CandidateBase):
            raise TypeError("Result requires a timeline/version observation")


@dataclass(frozen=True)
class ApplicationRecord:
    """Externally supplied fact for contract tests, never an Apply implementation."""

    candidate_id: CandidateId
    base: CandidateBase
    result: CandidateResultRef

    def __post_init__(self) -> None:
        _identity(self.candidate_id)
        if not isinstance(self.base, CandidateBase) or not isinstance(
            self.result, CandidateResultRef
        ):
            raise TypeError("Application record requires typed base and result")
        if (
            self.base.timeline_id == self.result.reference.timeline_id
            and self.result.reference.timeline_version < self.base.timeline_version
        ):
            raise ValueError("Application result cannot move the same timeline version backward")


@dataclass(frozen=True)
class Candidate:
    candidate_id: CandidateId
    base: CandidateBase
    lineage: CandidateLineage = field(default_factory=CandidateLineage)
    selection: SelectionState = SelectionState.UNSELECTED
    approval: ApprovalState = ApprovalState.NOT_APPROVED
    validity: CandidateValidity = CandidateValidity.FRESH
    application: ApplicationState = ApplicationState.NOT_APPLIED
    verification: VerificationState = VerificationState.NOT_VERIFIED
    promotion: PromotionState = PromotionState.NOT_PROMOTED
    work_phase: WorkPhase = WorkPhase.ANALYZING
    application_record: ApplicationRecord | None = None

    def __post_init__(self) -> None:
        _identity(self.candidate_id)
        if not isinstance(self.base, CandidateBase) or not isinstance(
            self.lineage, CandidateLineage
        ):
            raise TypeError("Candidate requires typed base and lineage")
        if self.candidate_id in self.lineage.ancestors:
            raise ValueError("Candidate cannot be its own ancestor")
        for value, enum in (
            (self.selection, SelectionState),
            (self.approval, ApprovalState),
            (self.validity, CandidateValidity),
            (self.application, ApplicationState),
            (self.verification, VerificationState),
            (self.promotion, PromotionState),
            (self.work_phase, WorkPhase),
        ):
            if not isinstance(value, enum):
                raise TypeError("Candidate axes require their corresponding enum types")
        evidence = self.application_record
        if evidence is not None and not isinstance(evidence, ApplicationRecord):
            raise TypeError("Application evidence must be an ApplicationRecord")
        if (self.application == ApplicationState.APPLIED) != (evidence is not None):
            raise ValueError("Application state and evidence must agree")
        if evidence is not None and (
            self.approval != ApprovalState.APPROVED
            or evidence.candidate_id != self.candidate_id
            or evidence.base != self.base
        ):
            raise ValueError(
                "Applied candidate requires approval and exact candidate/base evidence"
            )
        if self.verification != VerificationState.NOT_VERIFIED and evidence is None:
            raise ValueError("Verification requires an application record")
        if (
            self.promotion == PromotionState.PROMOTED
            and self.verification != VerificationState.VERIFIED
        ):
            raise ValueError("Promotion requires verified application")


@dataclass(frozen=True)
class WorkingAuthority:
    """Fake comparison context, not the production authority persistence schema."""

    reference: CandidateBase
    promoted_candidate_id: CandidateId | None = None
    promoted_result: CandidateResultRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reference, CandidateBase):
            raise TypeError("Authority requires a typed observation")
        if (self.promoted_candidate_id is None) != (self.promoted_result is None):
            raise ValueError("Promotion provenance requires both candidate and result")
        if self.promoted_candidate_id is not None:
            _identity(self.promoted_candidate_id)
        if self.promoted_result is not None:
            if not isinstance(self.promoted_result, CandidateResultRef):
                raise TypeError("Promotion provenance requires a typed result")
            origin = self.promoted_result.reference
            if origin.timeline_id != self.reference.timeline_id or (
                origin.timeline_version > self.reference.timeline_version
            ):
                raise ValueError("Authority observation must contain or follow its promoted result")


@dataclass(frozen=True)
class CandidateWorkState:
    candidate: Candidate
    authority: WorkingAuthority
    active_timeline_id: TimelineId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, Candidate) or not isinstance(
            self.authority, WorkingAuthority
        ):
            raise TypeError("Work state requires typed candidate and authority")
        if self.active_timeline_id is not None:
            _identity(self.active_timeline_id)
        if self.candidate.base != self.authority.reference:
            object.__setattr__(
                self, "candidate", replace(self.candidate, validity=CandidateValidity.STALE)
            )


@dataclass(frozen=True)
class ApplyEligibility:
    eligible: bool
    reason: TransitionReason


@dataclass(frozen=True)
class CandidateTransitionResult:
    accepted: bool
    state: CandidateWorkState
    reason: TransitionReason


@dataclass(frozen=True)
class SelectCandidate:
    pass


@dataclass(frozen=True)
class ApproveCandidate:
    pass


@dataclass(frozen=True)
class SetWorkPhase:
    phase: WorkPhase

    def __post_init__(self) -> None:
        if not isinstance(self.phase, WorkPhase):
            raise TypeError("Phase requires WorkPhase")


@dataclass(frozen=True)
class ActivateTimeline:
    timeline_id: TimelineId

    def __post_init__(self) -> None:
        _identity(self.timeline_id)


@dataclass(frozen=True)
class ObserveHumanVersion:
    observation: CandidateBase

    def __post_init__(self) -> None:
        if not isinstance(self.observation, CandidateBase):
            raise TypeError("Human observation requires typed reference")


@dataclass(frozen=True)
class RecordApplication:
    record: ApplicationRecord

    def __post_init__(self) -> None:
        if not isinstance(self.record, ApplicationRecord):
            raise TypeError("Application event requires bound evidence")


@dataclass(frozen=True)
class RecordVerification:
    record: ApplicationRecord
    passed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.record, ApplicationRecord) or type(self.passed) is not bool:
            raise TypeError(
                "Verification requires exact application evidence and a boolean outcome"
            )


@dataclass(frozen=True)
class PromoteCandidate:
    result_observation: CandidateBase

    def __post_init__(self) -> None:
        if not isinstance(self.result_observation, CandidateBase):
            raise TypeError("Promotion requires a current result observation")


CandidateEvent: TypeAlias = (
    SelectCandidate
    | ApproveCandidate
    | SetWorkPhase
    | ActivateTimeline
    | ObserveHumanVersion
    | RecordApplication
    | RecordVerification
    | PromoteCandidate
)


def branch_candidate(parent: Candidate, candidate_id: CandidateId) -> Candidate:
    """New exploration on the same source base, not a branch from an applied result."""
    return Candidate(
        candidate_id,
        parent.base,
        CandidateLineage(parent.lineage.ancestors + (parent.candidate_id,)),
        validity=parent.validity,
    )


def apply_eligibility(state: CandidateWorkState) -> ApplyEligibility:
    """Authority preconditions only; not Safety Core approval or live edit authorization."""
    candidate = state.candidate
    if candidate.validity == CandidateValidity.STALE or candidate.base != state.authority.reference:
        return ApplyEligibility(False, TransitionReason.STALE)
    if candidate.approval != ApprovalState.APPROVED:
        return ApplyEligibility(False, TransitionReason.NOT_APPROVED)
    if candidate.application != ApplicationState.NOT_APPLIED:
        return ApplyEligibility(False, TransitionReason.ALREADY_APPLIED)
    return ApplyEligibility(True, TransitionReason.ELIGIBLE_FOR_ATTEMPT)


def transition(state: CandidateWorkState, event: CandidateEvent) -> CandidateTransitionResult:
    """Apply an event to immutable state only. Invalid transitions preserve the entire input."""
    candidate = state.candidate

    def reject(reason: TransitionReason) -> CandidateTransitionResult:
        return CandidateTransitionResult(False, state, reason)

    def accept(updated: CandidateWorkState) -> CandidateTransitionResult:
        return CandidateTransitionResult(True, updated, TransitionReason.ACCEPTED)

    if isinstance(event, SelectCandidate):
        return accept(
            replace(state, candidate=replace(candidate, selection=SelectionState.SELECTED))
        )
    if isinstance(event, ActivateTimeline):
        return accept(replace(state, active_timeline_id=event.timeline_id))
    if isinstance(event, SetWorkPhase):
        return accept(replace(state, candidate=replace(candidate, work_phase=event.phase)))
    if isinstance(event, ObserveHumanVersion):
        current = state.authority.reference
        if event.observation.timeline_id != current.timeline_id:
            return reject(TransitionReason.WRONG_AUTHORITY)
        if event.observation.timeline_version < current.timeline_version:
            return reject(TransitionReason.OLDER_OBSERVATION)
        return accept(
            replace(state, authority=replace(state.authority, reference=event.observation))
        )
    if not isinstance(
        event, (ApproveCandidate, RecordApplication, RecordVerification, PromoteCandidate)
    ):
        return reject(TransitionReason.UNSUPPORTED_EVENT)
    if candidate.validity == CandidateValidity.STALE or candidate.base != state.authority.reference:
        return reject(TransitionReason.STALE)
    if isinstance(event, ApproveCandidate):
        if candidate.application != ApplicationState.NOT_APPLIED:
            return reject(TransitionReason.ALREADY_APPLIED)
        return accept(replace(state, candidate=replace(candidate, approval=ApprovalState.APPROVED)))
    if isinstance(event, RecordApplication):
        eligibility = apply_eligibility(state)
        if not eligibility.eligible:
            return reject(eligibility.reason)
        if (
            event.record.candidate_id != candidate.candidate_id
            or event.record.base != candidate.base
        ):
            return reject(TransitionReason.EVIDENCE_MISMATCH)
        return accept(
            replace(
                state,
                candidate=replace(
                    candidate, application=ApplicationState.APPLIED, application_record=event.record
                ),
            )
        )
    evidence = candidate.application_record
    if isinstance(event, RecordVerification):
        if evidence is None:
            return reject(TransitionReason.NOT_APPLIED)
        if event.record != evidence:
            return reject(TransitionReason.EVIDENCE_MISMATCH)
        if candidate.verification != VerificationState.NOT_VERIFIED:
            return reject(TransitionReason.ALREADY_VERIFIED)
        outcome = VerificationState.VERIFIED if event.passed else VerificationState.FAILED
        return accept(replace(state, candidate=replace(candidate, verification=outcome)))
    if candidate.approval != ApprovalState.APPROVED:
        return reject(TransitionReason.NOT_APPROVED)
    if evidence is None:
        return reject(TransitionReason.NOT_APPLIED)
    if candidate.verification != VerificationState.VERIFIED:
        return reject(TransitionReason.NOT_VERIFIED)
    if candidate.promotion == PromotionState.PROMOTED:
        return reject(TransitionReason.ALREADY_PROMOTED)
    if event.result_observation != evidence.result.reference:
        return reject(TransitionReason.RESULT_MISMATCH)
    return accept(
        replace(
            state,
            candidate=replace(candidate, promotion=PromotionState.PROMOTED),
            authority=WorkingAuthority(
                evidence.result.reference, candidate.candidate_id, evidence.result
            ),
        )
    )
