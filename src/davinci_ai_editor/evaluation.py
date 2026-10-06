"""ADR-019 immutable raw evidence. No storage, telemetry, training or editing."""

from dataclasses import dataclass, field, replace
from enum import Enum

from .pause import CandidateRouting, Confidence, PauseAction

SCHEMA_VERSION = "evaluation-v1"


class SourceKind(str, Enum):
    BENCHMARK = "BENCHMARK"
    PILOT = "PILOT"
    PRODUCT_FEEDBACK = "PRODUCT_FEEDBACK"


class ProducerKind(str, Enum):
    RULE = "RULE"
    VAD = "VAD"
    STT = "STT"
    PROSODY = "PROSODY"
    SEMANTIC = "SEMANTIC"
    LLM = "LLM"
    MANUAL = "MANUAL"


class Ambiguity(str, Enum):
    CLEAR = "CLEAR"
    AMBIGUOUS = "AMBIGUOUS"


class AdjudicationStatus(str, Enum):
    SINGLE_ANNOTATOR = "SINGLE_ANNOTATOR"
    AGREED = "AGREED"
    ADJUDICATED = "ADJUDICATED"


class FeedbackActor(str, Enum):
    EDITOR = "EDITOR"
    SYSTEM = "SYSTEM"


class FeedbackEventType(str, Enum):
    ATTENTION_REQUESTED = "ATTENTION_REQUESTED"
    REVIEW_OPENED = "REVIEW_OPENED"
    PROPOSAL_ACCEPTED = "PROPOSAL_ACCEPTED"
    FINAL_DECISION_SET = "FINAL_DECISION_SET"
    PROPOSAL_REVERTED = "PROPOSAL_REVERTED"
    REMOVED_PAUSE_RESTORED = "REMOVED_PAUSE_RESTORED"
    RUN_FINALIZED = "RUN_FINALIZED"


class ActivityKind(str, Enum):
    INSTRUCTION = "INSTRUCTION"
    REVIEW = "REVIEW"
    CORRECTION = "CORRECTION"
    MANUAL_COMPLETION = "MANUAL_COMPLETION"
    RECOVERY_REVERT = "RECOVERY_REVERT"
    AI_BLOCKED_IDLE = "AI_BLOCKED_IDLE"


class MeasurementSource(str, Enum):
    INSTRUMENTED = "INSTRUMENTED"
    MANUAL_ESTIMATE = "MANUAL_ESTIMATE"


class RunMode(str, Enum):
    MANUAL_BASELINE = "MANUAL_BASELINE"
    AI_ASSISTED = "AI_ASSISTED"


def _text(*values: str) -> None:
    for value in values:
        if not isinstance(value, str):
            raise TypeError("Opaque references and versions must be strings")
        if not value.strip():
            raise ValueError("References and versions must be nonempty")


def _int(value: int, minimum: int = 0) -> None:
    if type(value) is not int:
        raise TypeError("Expected integer, not bool/float")
    if value < minimum:
        raise ValueError("Integer is below the allowed minimum")


def _enum(value: Enum, expected: type[Enum]) -> None:
    if not isinstance(value, expected):
        raise TypeError("Expected typed enum")


def _reasons(values: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(values, str):
        raise TypeError("Reasons must be a collection of codes")
    copied = tuple(values)
    if not copied:
        raise ValueError("Decision reasons are required")
    _text(*copied)
    return tuple(sorted(set(copied)))


def _decision(action: PauseAction, target: int | None, original: int | None = None) -> None:
    _enum(action, PauseAction)
    if action == PauseAction.TIGHTEN:
        if target is None:
            raise ValueError("TIGHTEN requires retained frames")
        _int(target, 1)
        if original is not None and target >= original:
            raise ValueError("Retained frames must be shorter than original pause")
    elif target is not None:
        raise ValueError("Only TIGHTEN may have retained frames")


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    source_kind: SourceKind
    evaluation_scope_id: str
    pause_subject_ref: str
    schema_version: str

    def __post_init__(self) -> None:
        _text(self.case_id, self.evaluation_scope_id, self.pause_subject_ref, self.schema_version)
        _enum(self.source_kind, SourceKind)
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("Unsupported evaluation schema version")


@dataclass(frozen=True)
class DecisionProducerRef:
    producer_kind: ProducerKind
    producer_name: str
    producer_version: str
    decision_contract_version: str
    feature_contract_version: str

    def __post_init__(self) -> None:
        _enum(self.producer_kind, ProducerKind)
        _text(
            self.producer_name,
            self.producer_version,
            self.decision_contract_version,
            self.feature_contract_version,
        )


@dataclass(frozen=True)
class AIProposalSnapshot:
    proposal_id: str
    case_id: str
    action: PauseAction
    confidence: Confidence
    reasons: tuple[str, ...]
    original_pause_frames: int
    suggested_retained_frames: int | None
    routing_hint: CandidateRouting
    producer_ref: DecisionProducerRef

    def __post_init__(self) -> None:
        _text(self.proposal_id, self.case_id)
        _int(self.original_pause_frames, 1)
        _enum(self.confidence, Confidence)
        _enum(self.routing_hint, CandidateRouting)
        if not isinstance(self.producer_ref, DecisionProducerRef):
            raise TypeError("Proposal requires producer provenance")
        _decision(self.action, self.suggested_retained_frames, self.original_pause_frames)
        object.__setattr__(self, "reasons", _reasons(self.reasons))


@dataclass(frozen=True)
class ReferenceAssessment:
    action: PauseAction
    confidence: Confidence
    reasons: tuple[str, ...]
    original_pause_frames: int
    preferred_retained_frames: int | None
    acceptable_min_frames: int | None
    acceptable_max_frames: int | None

    def __post_init__(self) -> None:
        _int(self.original_pause_frames, 1)
        _enum(self.confidence, Confidence)
        _decision(self.action, self.preferred_retained_frames, self.original_pause_frames)
        object.__setattr__(self, "reasons", _reasons(self.reasons))
        low, high, preferred = (
            self.acceptable_min_frames,
            self.acceptable_max_frames,
            self.preferred_retained_frames,
        )
        if self.action == PauseAction.TIGHTEN:
            if low is None or high is None or preferred is None:
                raise ValueError("TIGHTEN reference requires an acceptable range")
            _int(low, 1)
            _int(high, 1)
            if not low <= preferred <= high < self.original_pause_frames:
                raise ValueError("Invalid TIGHTEN reference interval")
        elif low is not None or high is not None:
            raise ValueError("Non-TIGHTEN reference must not have range targets")


@dataclass(frozen=True)
class ReferenceAnnotation:
    annotation_id: str
    case_id: str
    annotator_ref: str
    assessment: ReferenceAssessment

    def __post_init__(self) -> None:
        _text(self.annotation_id, self.case_id, self.annotator_ref)
        if not isinstance(self.assessment, ReferenceAssessment):
            raise TypeError("Annotation requires typed assessment")


@dataclass(frozen=True)
class ReferenceJudgment:
    case_id: str
    reference_version: str
    assessment: ReferenceAssessment
    ambiguity: Ambiguity
    adjudication_status: AdjudicationStatus

    def __post_init__(self) -> None:
        _text(self.case_id, self.reference_version)
        if not isinstance(self.assessment, ReferenceAssessment):
            raise TypeError("Reference requires typed assessment")
        _enum(self.ambiguity, Ambiguity)
        _enum(self.adjudication_status, AdjudicationStatus)


@dataclass(frozen=True)
class EmptyPayload:
    pass


@dataclass(frozen=True)
class FinalDecisionPayload:
    final_action: PauseAction
    final_retained_frames: int | None

    def __post_init__(self) -> None:
        _decision(self.final_action, self.final_retained_frames)


@dataclass(frozen=True)
class RunFinalizedPayload:
    run_id: str

    def __post_init__(self) -> None:
        _text(self.run_id)


@dataclass(frozen=True)
class FeedbackEvent:
    event_id: str
    case_id: str
    proposal_id: str
    sequence_no: int
    actor: FeedbackActor
    event_type: FeedbackEventType
    payload: EmptyPayload | FinalDecisionPayload | RunFinalizedPayload = field(
        default_factory=EmptyPayload
    )

    def __post_init__(self) -> None:
        _text(self.event_id, self.case_id, self.proposal_id)
        _int(self.sequence_no, 1)
        _enum(self.actor, FeedbackActor)
        _enum(self.event_type, FeedbackEventType)
        expected = (
            FinalDecisionPayload
            if self.event_type == FeedbackEventType.FINAL_DECISION_SET
            else RunFinalizedPayload
            if self.event_type == FeedbackEventType.RUN_FINALIZED
            else EmptyPayload
        )
        if not isinstance(self.payload, expected):
            raise TypeError("Event type and payload do not match")


@dataclass(frozen=True)
class FeedbackLog:
    case_id: str
    proposal_id: str
    events: tuple[FeedbackEvent, ...] = ()

    def __post_init__(self) -> None:
        _text(self.case_id, self.proposal_id)
        copied = tuple(self.events)
        if any(not isinstance(e, FeedbackEvent) for e in copied):
            raise TypeError("FeedbackLog requires typed events")
        ordered = tuple(sorted(copied, key=lambda e: e.sequence_no))
        object.__setattr__(self, "events", ordered)
        if len({e.event_id for e in ordered}) != len(ordered):
            raise ValueError("Duplicate event ID")
        if tuple(e.sequence_no for e in ordered) != tuple(range(1, len(ordered) + 1)):
            raise ValueError("Event sequence must be unique and contiguous from 1")
        if any(e.case_id != self.case_id or e.proposal_id != self.proposal_id for e in ordered):
            raise ValueError("Feedback event has wrong case/proposal")
        if any(e.event_type == FeedbackEventType.RUN_FINALIZED for e in ordered[:-1]):
            raise ValueError("No events may follow finalization in this episode")

    def append(self, event: FeedbackEvent) -> "FeedbackLog":
        if not isinstance(event, FeedbackEvent):
            raise TypeError("Append requires a typed event")
        if event.sequence_no != len(self.events) + 1:
            raise ValueError("Append must use the next sequence")
        return replace(self, events=self.events + (event,))


def validate_feedback(proposal: AIProposalSnapshot, log: FeedbackLog) -> None:
    if log.case_id != proposal.case_id or log.proposal_id != proposal.proposal_id:
        raise ValueError("Feedback does not bind this proposal")
    for event in log.events:
        if isinstance(event.payload, FinalDecisionPayload):
            _decision(
                event.payload.final_action,
                event.payload.final_retained_frames,
                proposal.original_pause_frames,
            )
        if (
            event.event_type == FeedbackEventType.REMOVED_PAUSE_RESTORED
            and proposal.action != PauseAction.REMOVE
        ):
            raise ValueError("Restore event requires a REMOVE proposal")


@dataclass(frozen=True)
class EvaluationRecord:
    case: EvaluationCase
    proposal: AIProposalSnapshot
    reference: ReferenceJudgment | None = None
    annotations: tuple[ReferenceAnnotation, ...] = ()
    feedback: FeedbackLog | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.case, EvaluationCase) or not isinstance(
            self.proposal, AIProposalSnapshot
        ):
            raise TypeError("Evaluation record requires case and proposal")
        if self.case.case_id != self.proposal.case_id:
            raise ValueError("Proposal case mismatch")
        annotations = tuple(self.annotations)
        if any(not isinstance(a, ReferenceAnnotation) for a in annotations):
            raise TypeError("Expected typed annotations")
        object.__setattr__(
            self, "annotations", tuple(sorted(annotations, key=lambda a: a.annotation_id))
        )
        if len({a.annotation_id for a in annotations}) != len(annotations):
            raise ValueError("Duplicate annotation ID")
        if self.case.source_kind == SourceKind.PRODUCT_FEEDBACK and (self.reference or annotations):
            raise ValueError("Product feedback cannot carry benchmark reference evidence")
        if self.reference is not None and not isinstance(self.reference, ReferenceJudgment):
            raise TypeError("Expected typed reference")
        bound = ((self.reference,) if self.reference is not None else ()) + annotations
        if any(
            r.case_id != self.case.case_id
            or r.assessment.original_pause_frames != self.proposal.original_pause_frames
            for r in bound
        ):
            raise ValueError("Reference/annotation case or original frames mismatch")
        if self.feedback is not None:
            if not isinstance(self.feedback, FeedbackLog):
                raise TypeError("Expected typed feedback")
            validate_feedback(self.proposal, self.feedback)


@dataclass(frozen=True)
class ActivityRecord:
    activity_id: str
    run_id: str
    case_id: str | None
    activity_kind: ActivityKind
    duration_ms: int | None
    measurement_source: MeasurementSource

    def __post_init__(self) -> None:
        _text(self.activity_id, self.run_id)
        if self.case_id is not None:
            _text(self.case_id)
        _enum(self.activity_kind, ActivityKind)
        _enum(self.measurement_source, MeasurementSource)
        if self.duration_ms is not None:
            _int(self.duration_ms)


@dataclass(frozen=True)
class WorkflowRun:
    run_id: str
    evaluation_scope_id: str
    run_mode: RunMode
    producer_ref: DecisionProducerRef
    case_ids: tuple[str, ...]
    complete_activity_kinds: tuple[ActivityKind, ...] = ()

    def __post_init__(self) -> None:
        _text(self.run_id, self.evaluation_scope_id)
        _enum(self.run_mode, RunMode)
        if not isinstance(self.producer_ref, DecisionProducerRef):
            raise TypeError("Workflow requires producer provenance")
        if isinstance(self.case_ids, str):
            raise TypeError("Case IDs must be a collection")
        cases = tuple(self.case_ids)
        _text(*cases)
        kinds = tuple(self.complete_activity_kinds)
        for kind in kinds:
            _enum(kind, ActivityKind)
        if len(set(cases)) != len(cases) or len(set(kinds)) != len(kinds):
            raise ValueError("Duplicate case or activity coverage")
        object.__setattr__(self, "case_ids", tuple(sorted(cases)))
        object.__setattr__(
            self, "complete_activity_kinds", tuple(sorted(kinds, key=lambda k: k.value))
        )


@dataclass(frozen=True)
class RunEvidence:
    run: WorkflowRun
    activities: tuple[ActivityRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.run, WorkflowRun):
            raise TypeError("Run evidence requires WorkflowRun")
        activities = tuple(self.activities)
        if any(not isinstance(a, ActivityRecord) for a in activities):
            raise TypeError("Expected typed activities")
        object.__setattr__(
            self, "activities", tuple(sorted(activities, key=lambda a: a.activity_id))
        )
        if len({a.activity_id for a in activities}) != len(activities):
            raise ValueError("Duplicate activity ID")
        if any(
            a.run_id != self.run.run_id
            or (a.case_id is not None and a.case_id not in self.run.case_ids)
            for a in activities
        ):
            raise ValueError("Activity does not belong to run/case")
