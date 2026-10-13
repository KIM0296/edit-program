"""Immutable presentation projections; no decisions, approval, or execution.

All coordinates, currentness, availability, and review assessments are supplied.
Correlation checks do not establish authenticity. Neither a mode switch nor a
projection creates domain events. No response preserves the native current state,
including human edits; it does not restore an earlier snapshot.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from .authority import CandidateValidity, CandidateWorkState
from .evidence import ProducerRef
from .expected_diff import ExpectedDiff, PreservationScope
from .pause import PauseAction, PauseCandidate
from .pause_planning import PauseCutGeometry
from .reference_style import EffectiveStyleContext
from .safety_preflight import SafetyPreflightResult
from .temporal_mapping import NativeSnapshotRef, TimelineFrameRange


class AssistMode(str, Enum):
    LINEAR_ASSIST = "LINEAR_ASSIST"
    REVIEW_QUEUE = "REVIEW_QUEUE"


class ReviewClassification(str, Enum):
    """Supplied attention advice, never a Safety verdict or an interruption order."""

    LOW_REVIEW_NEED = "LOW_REVIEW_NEED"
    REVIEW_RECOMMENDED = "REVIEW_RECOMMENDED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NOT_EVALUATABLE = "NOT_EVALUATABLE"


class PresentationAction(str, Enum):
    SELECT_PROPOSAL = "SELECT_PROPOSAL"
    KEEP_ORIGINAL = "KEEP_ORIGINAL"
    REQUEST_ADJUSTMENT = "REQUEST_ADJUSTMENT"
    DEFER_REVIEW = "DEFER_REVIEW"
    REQUEST_APPLY = "REQUEST_APPLY"


class PositionRelation(str, Enum):
    """Coordinate comparison only, not candidate or transaction lifecycle."""

    AHEAD = "AHEAD"
    AT_CONTEXT = "AT_CONTEXT"
    PASSED = "PASSED"
    OUTSIDE_WINDOW = "OUTSIDE_WINDOW"
    UNKNOWN = "UNKNOWN"


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Reference/text must be nonempty")


def _refs(values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple):
        raise TypeError("References must be an immutable tuple")
    for value in values:
        _text(value)


def _known(value: bool | None, basis: tuple[str, ...]) -> None:
    if value is not None and type(value) is not bool:
        raise TypeError("A supplied fact must be bool or None")
    _refs(basis)
    if value is not None and not basis:
        raise ValueError("Known facts require supplied basis references")


@dataclass(frozen=True)
class ReviewAssessment:
    classification: ReviewClassification
    producer: ProducerRef
    provenance_refs: tuple[str, ...]
    basis_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.classification, ReviewClassification):
            raise TypeError("Review classification must be typed")
        if not isinstance(self.producer, ProducerRef):
            raise TypeError("Reuse the existing ProducerRef")
        _refs(self.provenance_refs)
        _refs(self.basis_refs)
        if not self.provenance_refs or not self.basis_refs:
            raise ValueError("Assessment requires provenance and basis, including missingness")


@dataclass(frozen=True)
class ScopePresentation:
    """Opaque supplied scopes; no containment engine, reopening, or lock authority.

    conflict_refs=None means unassessed, () means supplied no conflict. Nonempty
    values identify supplied conflicts, including accepted-work intersections not
    explicitly reopened. The presentation cannot infer overlap from opaque IDs.
    """

    modification_scope_ref: str
    accepted_scope_refs: tuple[str, ...] = ()
    reopened_scope_refs: tuple[str, ...] = ()
    conflict_refs: tuple[str, ...] | None = None
    basis_refs: tuple[str, ...] = ()
    preservation_scope: PreservationScope | None = None

    def __post_init__(self) -> None:
        _text(self.modification_scope_ref)
        for refs in (self.accepted_scope_refs, self.reopened_scope_refs, self.basis_refs):
            _refs(refs)
        if self.conflict_refs is not None:
            _refs(self.conflict_refs)
            if not self.basis_refs:
                raise ValueError("Scope assessment requires supplied basis")
        if self.preservation_scope is not None and not isinstance(
            self.preservation_scope, PreservationScope
        ):
            raise TypeError("Preservation scope must reuse the existing domain type")


@dataclass(frozen=True)
class ActionAvailability:
    """Description of an external request path, never authorization to execute it."""

    action: PresentationAction
    available: bool | None = None
    basis_refs: tuple[str, ...] = ()
    explanation: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, PresentationAction):
            raise TypeError("Action must be typed")
        _known(self.available, self.basis_refs)
        if self.explanation is not None:
            _text(self.explanation)


@dataclass(frozen=True)
class CandidatePresentation:
    """Exact retained domain objects plus caller-supplied display facts.

    candidate_revision_ref binds the caller's immutable proposal revision. It is
    not a newly allocated authority candidate identity. Supplied timeline location
    is separate from PauseObservation's aligned range; no mapping is inferred.
    """

    presentation_ref: str
    candidate_revision_ref: str
    candidate: PauseCandidate
    snapshot: NativeSnapshotRef
    scope: ScopePresentation
    authority: CandidateWorkState | None = None
    location: TimelineFrameRange | None = None
    location_basis_refs: tuple[str, ...] = ()
    snapshot_is_current: bool | None = None
    currentness_basis_refs: tuple[str, ...] = ()
    expected_diff: ExpectedDiff | None = None
    safety: SafetyPreflightResult | None = None
    geometry: PauseCutGeometry | None = None
    style: EffectiveStyleContext | None = None
    review: ReviewAssessment | None = None
    proposal_summary: str | None = None
    reason: str | None = None
    uncertainty: str | None = None
    actions: tuple[ActionAvailability, ...] = ()

    def __post_init__(self) -> None:
        _text(self.presentation_ref)
        _text(self.candidate_revision_ref)
        for value, kind in (
            (self.candidate, PauseCandidate),
            (self.snapshot, NativeSnapshotRef),
            (self.scope, ScopePresentation),
        ):
            if not isinstance(value, kind):
                raise TypeError("Presentation requires existing typed bindings")
        for optional, optional_kind in (
            (self.authority, CandidateWorkState),
            (self.location, TimelineFrameRange),
            (self.expected_diff, ExpectedDiff),
            (self.safety, SafetyPreflightResult),
            (self.geometry, PauseCutGeometry),
            (self.style, EffectiveStyleContext),
            (self.review, ReviewAssessment),
        ):
            if optional is not None and not isinstance(optional, optional_kind):
                raise TypeError("Optional presentation facts must be typed or absent")
        _refs(self.location_basis_refs)
        if self.location is not None and not self.location_basis_refs:
            raise ValueError("Location requires supplied correspondence evidence")
        _known(self.snapshot_is_current, self.currentness_basis_refs)
        for text in (self.proposal_summary, self.reason, self.uncertainty):
            if text is not None:
                _text(text)
        if not isinstance(self.actions, tuple) or any(
            not isinstance(action, ActionAvailability) for action in self.actions
        ):
            raise TypeError("Action descriptions must be an immutable typed tuple")
        if len({action.action for action in self.actions}) != len(self.actions):
            raise ValueError("Duplicate action descriptions are ambiguous")


@dataclass(frozen=True)
class PositionWindow:
    """Supplied position and half-open visibility window, no default horizon."""

    snapshot: NativeSnapshotRef | None = None
    position_frame: int | None = None
    window: TimelineFrameRange | None = None
    basis_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _refs(self.basis_refs)
        if self.snapshot is not None and not isinstance(self.snapshot, NativeSnapshotRef):
            raise TypeError("Position requires a typed snapshot binding")
        if self.position_frame is not None and (
            type(self.position_frame) is not int or self.position_frame < 0
        ):
            raise ValueError("Position must be a supplied nonnegative integer frame")
        if self.window is not None and not isinstance(self.window, TimelineFrameRange):
            raise TypeError("Window must use supplied timeline coordinates")
        if (self.position_frame is not None or self.window is not None) and (
            self.snapshot is None or not self.basis_refs
        ):
            raise ValueError("Coordinates require snapshot and observation basis")


@dataclass(frozen=True)
class AssistCounts:
    """Independent supplied measurements, not inferred decision/execution records.

    Measurement scope/time is identified by basis_refs. Values need not equal one
    another or describe this projection; None remains unmeasured, never zero.
    """

    internal_observations: int | None = None
    visible_recommendations: int | None = None
    attention_requests: int | None = None
    explicit_human_decisions: int | None = None
    executed_changes: int | None = None
    basis_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _refs(self.basis_refs)
        values = (
            self.internal_observations,
            self.visible_recommendations,
            self.attention_requests,
            self.explicit_human_decisions,
            self.executed_changes,
        )
        for value in values:
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Counts must be nonnegative integers or absent")
        if any(value is not None for value in values) and not self.basis_refs:
            raise ValueError("Measured counts require supplied scope/provenance")


@dataclass(frozen=True)
class ProjectedAction:
    supplied: ActionAvailability
    available: bool | None
    inactive_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _refs(self.inactive_reasons)
        if not isinstance(self.supplied, ActionAvailability):
            raise TypeError("Projected action must retain its supplied description")
        if self.available is not None and type(self.available) is not bool:
            raise TypeError("Projected availability must be bool or None")
        if self.available is True and (
            self.supplied.available is not True or self.inactive_reasons
        ):
            raise ValueError("Projection cannot upgrade availability or ignore blockers")


@dataclass(frozen=True)
class ProjectedCandidate:
    source: CandidatePresentation
    relation: PositionRelation
    current: bool | None
    visible: bool
    inactive_reasons: tuple[str, ...]
    actions: tuple[ProjectedAction, ...]

    def __post_init__(self) -> None:
        _refs(self.inactive_reasons)
        if not isinstance(self.source, CandidatePresentation) or not isinstance(
            self.relation, PositionRelation
        ):
            raise TypeError("Projection requires typed source and coordinate relation")
        if type(self.visible) is not bool or (
            self.current is not None and type(self.current) is not bool
        ):
            raise TypeError("Projection visibility/currentness must be typed")
        if not isinstance(self.actions, tuple) or any(
            not isinstance(action, ProjectedAction) for action in self.actions
        ):
            raise TypeError("Projected actions must be immutable")

    @property
    def no_response_behavior(self) -> Literal["PRESERVE_CURRENT_STATE"]:
        return "PRESERVE_CURRENT_STATE"


@dataclass(frozen=True)
class UpcomingProjection:
    mode: AssistMode
    position: PositionWindow
    candidates: tuple[ProjectedCandidate, ...]
    counts: AssistCounts
    hidden_refs: tuple[str, ...]
    deferred_refs: tuple[str, ...]
    show_more: bool

    def __post_init__(self) -> None:
        _refs(self.hidden_refs)
        _refs(self.deferred_refs)
        if not isinstance(self.mode, AssistMode) or not isinstance(self.position, PositionWindow):
            raise TypeError("Projection requires typed mode/position")
        if not isinstance(self.counts, AssistCounts) or type(self.show_more) is not bool:
            raise TypeError("Projection requires typed measurements and display option")
        if not isinstance(self.candidates, tuple) or any(
            not isinstance(candidate, ProjectedCandidate) for candidate in self.candidates
        ):
            raise TypeError("Projected candidates must be immutable")


def _correlation_problems(source: CandidatePresentation) -> tuple[str, ...]:
    problems: list[str] = []
    snapshot, observation = source.snapshot, source.candidate.observation
    if (observation.timeline_id, observation.base_version) != (
        snapshot.timeline_id,
        snapshot.timeline_version,
    ):
        problems.append("CANDIDATE_SNAPSHOT_MISMATCH")
    if source.authority is not None:
        candidate = source.authority.candidate
        if candidate.validity == CandidateValidity.STALE:
            problems.append("STALE_AUTHORITY_CANDIDATE")
        if (candidate.base.timeline_id, candidate.base.timeline_version) != (
            snapshot.timeline_id,
            snapshot.timeline_version,
        ):
            problems.append("AUTHORITY_BASE_MISMATCH")
        if source.geometry is not None and (
            candidate.candidate_id != source.geometry.binding.candidate_ref
        ):
            problems.append("AUTHORITY_GEOMETRY_MISMATCH")
    if source.expected_diff is not None:
        if source.expected_diff.base_snapshot != snapshot:
            problems.append("DIFF_SNAPSHOT_MISMATCH")
        if source.scope.preservation_scope is not source.expected_diff.inputs.scope:
            problems.append("PRESERVATION_SCOPE_NOT_RETAINED")
        if source.geometry is not source.expected_diff.inputs.proposal.geometry:
            problems.append("DIFF_GEOMETRY_NOT_RETAINED")
    if source.safety is not None and (
        source.safety.inputs.compilation.expected_diff is not source.expected_diff
    ):
        problems.append("SAFETY_DIFF_NOT_RETAINED")
    if source.geometry is not None:
        binding = source.geometry.binding
        if (binding.snapshot_ref, binding.object_id, binding.original_pause_range) != (
            snapshot,
            observation.object_id,
            observation.pause_range,
        ):
            problems.append("GEOMETRY_CANDIDATE_MISMATCH")
    return tuple(problems)


def _relation(source: CandidatePresentation, position: PositionWindow) -> PositionRelation:
    if (
        source.location is None
        or position.snapshot != source.snapshot
        or position.position_frame is None
        or position.window is None
    ):
        return PositionRelation.UNKNOWN
    location, window = source.location.frames, position.window.frames
    if location.end <= position.position_frame:
        return PositionRelation.PASSED
    if location.end <= window.start or location.start >= window.end:
        return PositionRelation.OUTSIDE_WINDOW
    if location.start <= position.position_frame < location.end:
        return PositionRelation.AT_CONTEXT
    return PositionRelation.AHEAD


_UNMEASURED_COUNTS = AssistCounts()


def project_upcoming(
    candidates: tuple[CandidatePresentation, ...],
    position: PositionWindow,
    *,
    mode: AssistMode = AssistMode.LINEAR_ASSIST,
    counts: AssistCounts = _UNMEASURED_COUNTS,
    hidden_refs: tuple[str, ...] = (),
    deferred_refs: tuple[str, ...] = (),
    show_more: bool = False,
) -> UpcomingProjection:
    """Pure view; never seeks, classifies risk, rewrites candidates, or emits events.

    In linear mode only supplied in-window locations are shown by default. Queue
    mode/show_more permits inspection of late, stale, or unlocated records. KEEP
    is silent unless show_more is requested. Deferred items appear in queue mode.
    Scope/continuity uncertainty can suppress an external action description but
    cannot enable one. Even available REQUEST_APPLY describes a request only.
    """
    if not isinstance(candidates, tuple) or any(
        not isinstance(candidate, CandidatePresentation) for candidate in candidates
    ):
        raise TypeError("Candidates must be an immutable typed tuple")
    if not isinstance(position, PositionWindow) or not isinstance(mode, AssistMode):
        raise TypeError("Position and mode must be typed")
    if not isinstance(counts, AssistCounts) or type(show_more) is not bool:
        raise TypeError("Counts/show_more must be typed")
    _refs(hidden_refs)
    _refs(deferred_refs)
    if len({candidate.presentation_ref for candidate in candidates}) != len(candidates):
        raise ValueError("Presentation references must be unique")
    entries: list[ProjectedCandidate] = []
    for source in candidates:
        problems = list(_correlation_problems(source))
        current = source.snapshot_is_current
        if position.snapshot is None:
            problems.append("POSITION_SNAPSHOT_MISSING")
            current = None if current is not False else False
        elif position.snapshot != source.snapshot:
            problems.append("POSITION_SNAPSHOT_MISMATCH")
            current = False
        if problems:
            current = False if current is not None else None
        if current is not True:
            problems.append("STALE_OR_CURRENTNESS_UNKNOWN")
        if source.scope.conflict_refs is None:
            problems.append("SCOPE_CONFLICT_UNASSESSED")
        elif source.scope.conflict_refs:
            problems.append("ACCEPTED_SCOPE_CONFLICT")
        if source.style is not None and (
            source.style.modification_scope_ref != source.scope.modification_scope_ref
        ):
            problems.append("STYLE_MODIFICATION_SCOPE_MISMATCH")
        relation = _relation(source, position)
        visible = (
            show_more
            or mode == AssistMode.REVIEW_QUEUE
            or relation in (PositionRelation.AHEAD, PositionRelation.AT_CONTEXT)
        )
        if source.candidate.action == PauseAction.KEEP and not show_more:
            visible = False
        if source.presentation_ref in hidden_refs:
            visible = False
        if source.presentation_ref in deferred_refs and mode == AssistMode.LINEAR_ASSIST:
            visible = False
        actions: list[ProjectedAction] = []
        for supplied in source.actions:
            blocked = list(problems) if supplied.action != PresentationAction.DEFER_REVIEW else []
            if supplied.action == PresentationAction.REQUEST_APPLY and any(
                fact is None
                for fact in (source.authority, source.expected_diff, source.safety, source.geometry)
            ):
                blocked.append("EXTERNAL_APPLY_CONTEXT_MISSING")
            actions.append(
                ProjectedAction(supplied, False if blocked else supplied.available, tuple(blocked))
            )
        entries.append(
            ProjectedCandidate(source, relation, current, visible, tuple(problems), tuple(actions))
        )
    return UpcomingProjection(
        mode, position, tuple(entries), counts, hidden_refs, deferred_refs, show_more
    )
