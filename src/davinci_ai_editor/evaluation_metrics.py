"""Reproducible ADR-019 metrics from immutable evidence; no collection or gate policy."""

from dataclasses import dataclass, field, replace
from enum import Enum
from fractions import Fraction

from .evaluation import (
    ActivityKind,
    AIProposalSnapshot,
    Ambiguity,
    DecisionProducerRef,
    EvaluationRecord,
    FeedbackEventType,
    FeedbackLog,
    FinalDecisionPayload,
    MeasurementSource,
    RunEvidence,
    RunFinalizedPayload,
    RunMode,
    SourceKind,
    validate_feedback,
)
from .pause import PauseAction

METRIC_DEFINITION_VERSION = "evaluation-metrics-v1"


class CorrectionClass(str, Enum):
    NONE = "NONE"
    KEEP_INSTEAD = "KEEP_INSTEAD"
    REMOVE_INSTEAD = "REMOVE_INSTEAD"
    TIGHTEN_INSTEAD = "TIGHTEN_INSTEAD"
    TIGHTEN_MORE = "TIGHTEN_MORE"
    TIGHTEN_LESS = "TIGHTEN_LESS"
    RESTORE_REMOVED_PAUSE = "RESTORE_REMOVED_PAUSE"
    OTHER_ACTION_CHANGE = "OTHER_ACTION_CHANGE"


class TightenRange(str, Enum):
    IN_RANGE = "IN_RANGE"
    OUT_OF_RANGE = "OUT_OF_RANGE"


def _freeze(value: object, *names: str) -> None:
    for name in names:
        object.__setattr__(value, name, tuple(getattr(value, name)))


@dataclass(frozen=True)
class UserFinalOutcome:
    case_id: str
    proposal_id: str
    source_event_ids: tuple[str, ...]
    finalized: bool
    run_id: str | None
    final_action: PauseAction | None
    final_retained_frames: int | None
    accepted_as_is: bool | None
    modified: bool | None
    reverted: bool
    restored_removed_pause: bool
    correction: CorrectionClass | None
    metric_definition_version: str = field(default=METRIC_DEFINITION_VERSION, init=False)

    def __post_init__(self) -> None:
        _freeze(self, "source_event_ids")


def _correction(
    proposal: AIProposalSnapshot, action: PauseAction | None, retained: int | None, restored: bool
) -> CorrectionClass | None:
    if restored:
        return CorrectionClass.RESTORE_REMOVED_PAUSE
    if action is None:
        return None
    if (action, retained) == (proposal.action, proposal.suggested_retained_frames):
        return CorrectionClass.NONE
    if action == PauseAction.TIGHTEN:
        if proposal.action != PauseAction.TIGHTEN:
            return CorrectionClass.TIGHTEN_INSTEAD
        assert retained is not None and proposal.suggested_retained_frames is not None
        return (
            CorrectionClass.TIGHTEN_MORE
            if retained < proposal.suggested_retained_frames
            else CorrectionClass.TIGHTEN_LESS
        )
    if action == PauseAction.KEEP:
        return CorrectionClass.KEEP_INSTEAD
    if action == PauseAction.REMOVE:
        return CorrectionClass.REMOVE_INSTEAD
    return CorrectionClass.OTHER_ACTION_CHANGE


def derive_user_final_outcome(proposal: AIProposalSnapshot, log: FeedbackLog) -> UserFinalOutcome:
    validate_feedback(proposal, log)
    action: PauseAction | None = None
    retained: int | None = None
    reverted = restored = finalized = False
    run_id: str | None = None
    for event in log.events:
        if event.event_type == FeedbackEventType.PROPOSAL_ACCEPTED:
            action, retained = proposal.action, proposal.suggested_retained_frames
        elif isinstance(event.payload, FinalDecisionPayload):
            action, retained = event.payload.final_action, event.payload.final_retained_frames
        elif event.event_type == FeedbackEventType.PROPOSAL_REVERTED:
            reverted = True
            action, retained = None, None
        elif event.event_type == FeedbackEventType.REMOVED_PAUSE_RESTORED:
            restored = True
            action, retained = PauseAction.KEEP, None
        elif isinstance(event.payload, RunFinalizedPayload):
            finalized, run_id = True, event.payload.run_id
    if not finalized:
        action, retained = None, None
    same = (action, retained) == (proposal.action, proposal.suggested_retained_frames)
    accepted = False if reverted or restored else same if action is not None else None
    modified = not same if action is not None else None
    return UserFinalOutcome(
        proposal.case_id,
        proposal.proposal_id,
        tuple(e.event_id for e in log.events),
        finalized,
        run_id,
        action,
        retained,
        accepted,
        modified,
        reverted,
        restored,
        _correction(proposal, action, retained, restored),
    )


@dataclass(frozen=True)
class TimingMetrics:
    run_id: str
    evaluation_scope_id: str
    source_case_ids: tuple[str, ...]
    source_activity_ids: tuple[str, ...]
    measurement_sources: tuple[MeasurementSource, ...]
    human_active_time_ms: int | None
    mandatory_attention_time_ms: int | None
    assisted_human_cost_ms: int | None
    correction_debt_ms: int | None
    metric_definition_version: str = field(default=METRIC_DEFINITION_VERSION, init=False)

    def __post_init__(self) -> None:
        _freeze(self, "source_case_ids", "source_activity_ids", "measurement_sources")


_ACTIVE = (
    ActivityKind.INSTRUCTION,
    ActivityKind.REVIEW,
    ActivityKind.CORRECTION,
    ActivityKind.MANUAL_COMPLETION,
    ActivityKind.RECOVERY_REVERT,
)
_ATTENTION = tuple(kind for kind in _ACTIVE if kind != ActivityKind.MANUAL_COMPLETION)


def derive_timing_metrics(evidence: RunEvidence) -> TimingMetrics:
    def total(kinds: tuple[ActivityKind, ...]) -> int | None:
        result = 0
        for kind in kinds:
            if kind not in evidence.run.complete_activity_kinds:
                return None
            durations = [a.duration_ms for a in evidence.activities if a.activity_kind == kind]
            if not durations:
                return None
            for duration in durations:
                if duration is None:
                    return None
                result += duration
        return result

    return TimingMetrics(
        evidence.run.run_id,
        evidence.run.evaluation_scope_id,
        evidence.run.case_ids,
        tuple(a.activity_id for a in evidence.activities),
        tuple(sorted({a.measurement_source for a in evidence.activities}, key=lambda s: s.value)),
        total(_ACTIVE),
        total(_ATTENTION),
        total(_ACTIVE + (ActivityKind.AI_BLOCKED_IDLE,)),
        total((ActivityKind.CORRECTION, ActivityKind.RECOVERY_REVERT)),
    )


@dataclass(frozen=True)
class NetTimeSaved:
    manual_run_id: str | None
    assisted_run_id: str | None
    evaluation_scope_id: str | None
    source_case_ids: tuple[str, ...]
    source_activities: tuple[tuple[str, str], ...]
    net_time_saved_ms: int | None
    net_time_saved_rate: Fraction | None
    metric_definition_version: str = field(default=METRIC_DEFINITION_VERSION, init=False)

    def __post_init__(self) -> None:
        _freeze(self, "source_case_ids")
        object.__setattr__(
            self, "source_activities", tuple(tuple(x) for x in self.source_activities)
        )


def derive_net_time_saved(manual: RunEvidence | None, assisted: RunEvidence | None) -> NetTimeSaved:
    if manual is not None and manual.run.run_mode != RunMode.MANUAL_BASELINE:
        raise ValueError("Manual baseline required")
    if assisted is not None and assisted.run.run_mode != RunMode.AI_ASSISTED:
        raise ValueError("AI assisted run required")
    existing = manual or assisted
    base = NetTimeSaved(
        manual_run_id=manual.run.run_id if manual else None,
        assisted_run_id=assisted.run.run_id if assisted else None,
        evaluation_scope_id=existing.run.evaluation_scope_id if existing else None,
        source_case_ids=existing.run.case_ids if existing else (),
        source_activities=tuple(
            sorted(
                (e.run.run_id, a.activity_id)
                for e in (manual, assisted)
                if e is not None
                for a in e.activities
            )
        ),
        net_time_saved_ms=None,
        net_time_saved_rate=None,
    )
    if manual is None or assisted is None:
        return base
    if (
        manual.run.evaluation_scope_id != assisted.run.evaluation_scope_id
        or manual.run.case_ids != assisted.run.case_ids
        or manual.run.run_id == assisted.run.run_id
    ):
        raise ValueError("Paired runs require same scope/cases and distinct IDs")
    baseline = derive_timing_metrics(manual).human_active_time_ms
    cost = derive_timing_metrics(assisted).assisted_human_cost_ms
    saved = baseline - cost if baseline is not None and cost is not None else None
    rate = (
        Fraction(saved, baseline)
        if saved is not None and baseline is not None and baseline > 0
        else None
    )
    return replace(base, net_time_saved_ms=saved, net_time_saved_rate=rate)


@dataclass(frozen=True)
class CaseMetrics:
    case_id: str
    proposal_id: str
    source_kind: SourceKind
    schema_version: str
    producer_ref: DecisionProducerRef
    reference_version: str | None
    reference_ambiguity: Ambiguity | None
    critical_false_removal: bool | None
    tighten_range: TightenRange | None
    outcome: UserFinalOutcome | None
    metric_definition_version: str = field(default=METRIC_DEFINITION_VERSION, init=False)


@dataclass(frozen=True)
class EditorialMetrics:
    cases: tuple[CaseMetrics, ...]
    evaluated_case_count: int
    reference_case_count: int
    missing_reference_count: int
    critical_false_removal_count: int
    critical_false_removal_denominator: int
    critical_false_removal_rate: Fraction | None
    review_count: int
    review_load: Fraction | None
    decision_interruptions: int | None
    known_outcome_count: int
    unknown_outcome_count: int
    accepted_as_is_count: int
    accepted_as_is_rate: Fraction | None
    metric_definition_version: str = field(default=METRIC_DEFINITION_VERSION, init=False)

    def __post_init__(self) -> None:
        _freeze(self, "cases")


def derive_editorial_metrics(records: tuple[EvaluationRecord, ...]) -> EditorialMetrics:
    records = tuple(sorted(records, key=lambda r: r.case.case_id))
    if len({r.case.case_id for r in records}) != len(records) or len(
        {r.proposal.proposal_id for r in records}
    ) != len(records):
        raise ValueError("Select exactly one distinct proposal per distinct case")
    event_ids = [e.event_id for r in records if r.feedback for e in r.feedback.events]
    if len(set(event_ids)) != len(event_ids):
        raise ValueError("Duplicate event IDs across evaluation batch")
    results = []
    reference_count = missing = false_removal = at_risk = reviews = known = accepted = 0
    interruptions = 0
    complete_logs = True
    for record in records:
        p, ref = record.proposal, record.reference
        critical: bool | None = None
        range_result: TightenRange | None = None
        if ref is not None:
            reference_count += 1
            preserving = ref.assessment.action in (PauseAction.KEEP, PauseAction.REVIEW)
            at_risk += int(preserving)
            critical = preserving and p.action == PauseAction.REMOVE
            false_removal += int(critical)
            if ref.assessment.action == p.action == PauseAction.TIGHTEN:
                low, high = (
                    ref.assessment.acceptable_min_frames,
                    ref.assessment.acceptable_max_frames,
                )
                target = p.suggested_retained_frames
                assert low is not None and high is not None and target is not None
                range_result = (
                    TightenRange.IN_RANGE if low <= target <= high else TightenRange.OUT_OF_RANGE
                )
        elif record.case.source_kind != SourceKind.PRODUCT_FEEDBACK:
            missing += 1
        reviews += int(p.action == PauseAction.REVIEW)
        outcome = None
        if record.feedback is None:
            complete_logs = False
        else:
            interruptions += sum(
                e.event_type == FeedbackEventType.ATTENTION_REQUESTED
                for e in record.feedback.events
            )
            outcome = derive_user_final_outcome(p, record.feedback)
            if outcome.final_action is not None:
                known += 1
                accepted += int(outcome.accepted_as_is is True)
        results.append(
            CaseMetrics(
                record.case.case_id,
                p.proposal_id,
                record.case.source_kind,
                record.case.schema_version,
                p.producer_ref,
                ref.reference_version if ref else None,
                ref.ambiguity if ref else None,
                critical,
                range_result,
                outcome,
            )
        )
    return EditorialMetrics(
        tuple(results),
        len(records),
        reference_count,
        missing,
        false_removal,
        at_risk,
        Fraction(false_removal, at_risk) if at_risk else None,
        reviews,
        Fraction(reviews, len(records)) if records else None,
        interruptions if complete_logs else None,
        known,
        len(records) - known,
        accepted,
        Fraction(accepted, known) if known else None,
    )
