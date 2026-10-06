"""ADR-023 pure planning. Supplied geometry/facts only; no Safety or execution."""

from dataclasses import dataclass
from enum import Enum

from .domain import FrameRange, MediaId, TimelineObjectId
from .native_snapshot import ReadinessStatus
from .pause import PauseAction, PauseCandidate
from .temporal_mapping import MappingStatus, NativeSnapshotRef


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Opaque reference/version must be a nonempty string")


@dataclass(frozen=True)
class PlanningBinding:
    candidate_ref: str
    snapshot_ref: NativeSnapshotRef
    object_id: TimelineObjectId
    original_pause_range: FrameRange

    def __post_init__(self) -> None:
        _text(self.candidate_ref)
        if not isinstance(self.snapshot_ref, NativeSnapshotRef) or not isinstance(
            self.object_id, TimelineObjectId
        ):
            raise TypeError("Binding requires typed snapshot and placement")
        if not isinstance(self.original_pause_range, FrameRange):
            raise TypeError("Binding requires integer half-open pause range")


class GeometrySource(str, Enum):
    CALLER_SUPPLIED = "CALLER_SUPPLIED"


@dataclass(frozen=True)
class GeometryProvenance:
    source_ref: str
    source_version: str
    source: GeometrySource = GeometrySource.CALLER_SUPPLIED

    def __post_init__(self) -> None:
        _text(self.source_ref)
        _text(self.source_version)
        if not isinstance(self.source, GeometrySource):
            raise TypeError("TASK-012 only records explicit caller supply")


@dataclass(frozen=True)
class PauseCutGeometry:
    geometry_ref: str
    binding: PlanningBinding
    removed_ranges: tuple[FrameRange, ...]
    retained_duration_frames: int
    provenance: GeometryProvenance
    geometry_contract_version: str

    def __post_init__(self) -> None:
        _text(self.geometry_ref)
        _text(self.geometry_contract_version)
        if not isinstance(self.binding, PlanningBinding) or not isinstance(
            self.provenance, GeometryProvenance
        ):
            raise TypeError("Geometry requires typed binding/provenance")
        ranges = tuple(self.removed_ranges)
        if any(not isinstance(r, FrameRange) for r in ranges):
            raise TypeError("Geometry requires integer half-open ranges")
        if type(self.retained_duration_frames) is not int or self.retained_duration_frames < 0:
            raise ValueError("Retained duration must be a nonnegative integer")
        # Retain supplied order/shape, including unsupported geometry, for diagnosis. Never repair.
        object.__setattr__(self, "removed_ranges", ranges)


class TemporalEditIntent(str, Enum):
    PRESERVE = "PRESERVE"
    SHORTEN_GAP = "SHORTEN_GAP"
    CLOSE_GAP = "CLOSE_GAP"
    REVIEW_ONLY = "REVIEW_ONLY"


@dataclass(frozen=True)
class TargetReadinessInput:
    """Precomputed primary-range fact, not a mapping constructor or native ID bridge."""

    assessment_ref: str
    binding: PlanningBinding
    status: MappingStatus
    media_id: MediaId
    placement_range: FrameRange | None
    resolved_range: FrameRange | None

    def __post_init__(self) -> None:
        _text(self.assessment_ref)
        _text(self.media_id)
        if not isinstance(self.binding, PlanningBinding) or not isinstance(
            self.status, MappingStatus
        ):
            raise TypeError("Target fact requires typed binding/status")
        for value in (self.placement_range, self.resolved_range):
            if value is not None and not isinstance(value, FrameRange):
                raise TypeError("Target ranges must be typed or absent")
        if self.status == MappingStatus.EXACT and (
            self.placement_range is None or self.resolved_range is None
        ):
            raise ValueError("EXACT target fact requires explicit placement and primary ranges")


@dataclass(frozen=True)
class SnapshotReadinessInput:
    assessment_ref: str
    binding: PlanningBinding
    status: ReadinessStatus
    profile_ref: str

    def __post_init__(self) -> None:
        _text(self.assessment_ref)
        _text(self.profile_ref)
        if not isinstance(self.binding, PlanningBinding) or not isinstance(
            self.status, ReadinessStatus
        ):
            raise TypeError("Snapshot fact requires typed binding/status")


class DependencyStatus(str, Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    CONFLICT = "CONFLICT"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class DependencyReadinessInput:
    assessment_ref: str
    binding: PlanningBinding
    status: DependencyStatus
    geometry_ref: str | None = None
    primary_range: FrameRange | None = None
    temporal_intent: TemporalEditIntent | None = None

    def __post_init__(self) -> None:
        _text(self.assessment_ref)
        if not isinstance(self.binding, PlanningBinding) or not isinstance(
            self.status, DependencyStatus
        ):
            raise TypeError("Dependency fact requires typed binding/status")
        if self.geometry_ref is not None:
            _text(self.geometry_ref)
        if self.primary_range is not None and not isinstance(self.primary_range, FrameRange):
            raise TypeError("Dependency primary range must be typed")
        if self.temporal_intent is not None and not isinstance(
            self.temporal_intent, TemporalEditIntent
        ):
            raise TypeError("Dependency temporal intent must be typed")
        if self.status == DependencyStatus.RESOLVED and (
            self.geometry_ref is None or self.primary_range is None or self.temporal_intent is None
        ):
            raise ValueError("Resolved assessment must bind explicit geometry/range/intent")


@dataclass(frozen=True)
class PausePlanningInput:
    proposal_ref: str
    candidate: PauseCandidate
    binding: PlanningBinding
    current_snapshot: NativeSnapshotRef
    geometry: PauseCutGeometry | None = None
    target: TargetReadinessInput | None = None
    snapshot_readiness: SnapshotReadinessInput | None = None
    dependency: DependencyReadinessInput | None = None
    planning_contract_version: str = "v1"

    def __post_init__(self) -> None:
        _text(self.proposal_ref)
        _text(self.planning_contract_version)
        for value, expected in (
            (self.candidate, PauseCandidate),
            (self.binding, PlanningBinding),
            (self.current_snapshot, NativeSnapshotRef),
        ):
            if not isinstance(value, expected):
                raise TypeError("Planning requires typed candidate/binding/current snapshot")
        for optional_value, optional_type in (
            (self.geometry, PauseCutGeometry),
            (self.target, TargetReadinessInput),
            (self.snapshot_readiness, SnapshotReadinessInput),
            (self.dependency, DependencyReadinessInput),
        ):
            if optional_value is not None and not isinstance(optional_value, optional_type):
                raise TypeError("Planning inputs must be typed precomputed facts")


class PlanningDisposition(str, Enum):
    NO_OP = "NO_OP"
    REVIEW_ONLY = "REVIEW_ONLY"
    TARGET_RESOLUTION_REQUIRED = "TARGET_RESOLUTION_REQUIRED"
    GEOMETRY_REQUIRED = "GEOMETRY_REQUIRED"
    DEPENDENCY_RESOLUTION_REQUIRED = "DEPENDENCY_RESOLUTION_REQUIRED"
    READY_FOR_PREFLIGHT = "READY_FOR_PREFLIGHT"
    STALE = "STALE"
    UNSUPPORTED = "UNSUPPORTED"


class PlanningReason(str, Enum):
    KEEP_NO_OP = "KEEP_NO_OP"
    REVIEW_DECISION = "REVIEW_DECISION"
    STALE_CANDIDATE = "STALE_CANDIDATE"
    STALE_BINDING = "STALE_BINDING"
    STALE_TARGET = "STALE_TARGET"
    STALE_SNAPSHOT = "STALE_SNAPSHOT"
    TARGET_NOT_EXACT = "TARGET_NOT_EXACT"
    TARGET_UNSUPPORTED = "TARGET_UNSUPPORTED"
    TARGET_RANGE_MISMATCH = "TARGET_RANGE_MISMATCH"
    SNAPSHOT_NOT_READY = "SNAPSHOT_NOT_READY"
    SNAPSHOT_UNSUPPORTED = "SNAPSHOT_UNSUPPORTED"
    BINDING_MISMATCH = "BINDING_MISMATCH"
    GEOMETRY_MISSING = "GEOMETRY_MISSING"
    GEOMETRY_INVALID = "GEOMETRY_INVALID"
    GEOMETRY_CONFLICT = "GEOMETRY_CONFLICT"
    MULTI_RANGE_GEOMETRY_UNSUPPORTED = "MULTI_RANGE_GEOMETRY_UNSUPPORTED"
    CROSS_PLACEMENT_UNSUPPORTED = "CROSS_PLACEMENT_UNSUPPORTED"
    DEPENDENCY_UNRESOLVED = "DEPENDENCY_UNRESOLVED"
    DEPENDENCY_CONFLICT = "DEPENDENCY_CONFLICT"
    DEPENDENCY_UNSUPPORTED = "DEPENDENCY_UNSUPPORTED"
    DEPENDENCY_ASSESSMENT_MISMATCH = "DEPENDENCY_ASSESSMENT_MISMATCH"
    UNSUPPORTED_CONTRACT = "UNSUPPORTED_CONTRACT"
    READY_FOR_PREFLIGHT = "READY_FOR_PREFLIGHT"


@dataclass(frozen=True)
class PauseEditProposal:
    """An exact primary temporal change considered for later preflight, not an EditPlan."""

    proposal_ref: str
    binding: PlanningBinding
    temporal_intent: TemporalEditIntent
    geometry: PauseCutGeometry
    affected_primary_range: FrameRange
    target_assessment_ref: str
    snapshot_assessment_ref: str
    dependency_assessment_ref: str
    planning_contract_version: str = "v1"

    def __post_init__(self) -> None:
        for value in (
            self.proposal_ref,
            self.target_assessment_ref,
            self.snapshot_assessment_ref,
            self.dependency_assessment_ref,
            self.planning_contract_version,
        ):
            _text(value)
        if not isinstance(self.binding, PlanningBinding) or not isinstance(
            self.geometry, PauseCutGeometry
        ):
            raise TypeError("Proposal requires typed binding/geometry")
        if not isinstance(self.temporal_intent, TemporalEditIntent) or self.temporal_intent not in (
            TemporalEditIntent.SHORTEN_GAP,
            TemporalEditIntent.CLOSE_GAP,
        ):
            raise ValueError("Only explicit temporal change belongs in a proposal")
        if not isinstance(self.affected_primary_range, FrameRange):
            raise TypeError("Primary range must be typed")
        if self.geometry.binding != self.binding or self.geometry.removed_ranges != (
            self.affected_primary_range,
        ):
            raise ValueError("Proposal must retain exact geometry binding and range")
        pause = self.binding.original_pause_range
        retained = self.geometry.retained_duration_frames
        if (
            not pause.contains(self.affected_primary_range)
            or self.affected_primary_range.duration != pause.duration - retained
        ):
            raise ValueError("Proposal geometry must satisfy retained arithmetic")
        if self.temporal_intent == TemporalEditIntent.CLOSE_GAP:
            if retained != 0 or self.affected_primary_range != pause:
                raise ValueError("CLOSE_GAP requires explicit full-pause geometry")
        elif not 0 < retained < pause.duration:
            raise ValueError("SHORTEN_GAP must preserve positive duration")


@dataclass(frozen=True)
class PausePlanningResult:
    inputs: PausePlanningInput
    disposition: PlanningDisposition
    reasons: tuple[PlanningReason, ...]
    proposal: PauseEditProposal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.inputs, PausePlanningInput) or not isinstance(
            self.disposition, PlanningDisposition
        ):
            raise TypeError("Planning result requires typed input/disposition")
        reasons = tuple(self.reasons)
        if not reasons or any(not isinstance(r, PlanningReason) for r in reasons):
            raise ValueError("Planning result requires typed reasons")
        if (self.disposition == PlanningDisposition.READY_FOR_PREFLIGHT) != (
            self.proposal is not None
        ):
            raise ValueError("Only READY_FOR_PREFLIGHT carries a destructive proposal")
        if self.proposal is not None:
            if not isinstance(self.proposal, PauseEditProposal):
                raise TypeError("Proposal must be typed")
            if (
                self.inputs.candidate.action not in (PauseAction.TIGHTEN, PauseAction.REMOVE)
                or self.proposal.geometry != self.inputs.geometry
                or self.proposal.binding != self.inputs.binding
                or self.proposal.proposal_ref != self.inputs.proposal_ref
            ):
                raise ValueError("Proposal must retain the supplied destructive intent/geometry")
        object.__setattr__(self, "reasons", tuple(sorted(set(reasons), key=lambda r: r.value)))


def plan_pause(inputs: PausePlanningInput) -> PausePlanningResult:
    """Consume facts without calling any resolver, evaluator, Safety or executor."""
    if not isinstance(inputs, PausePlanningInput):
        raise TypeError("Planner requires immutable typed inputs")
    candidate = inputs.candidate
    if candidate.action == PauseAction.KEEP:
        return PausePlanningResult(inputs, PlanningDisposition.NO_OP, (PlanningReason.KEEP_NO_OP,))
    if candidate.action == PauseAction.REVIEW:
        return PausePlanningResult(
            inputs, PlanningDisposition.REVIEW_ONLY, (PlanningReason.REVIEW_DECISION,)
        )
    reasons: set[PlanningReason] = set()
    blocked: set[PlanningDisposition] = set()

    def block(disposition: PlanningDisposition, reason: PlanningReason) -> None:
        blocked.add(disposition)
        reasons.add(reason)

    binding, current = inputs.binding, inputs.current_snapshot
    observation = candidate.observation
    if binding.snapshot_ref != current or (observation.timeline_id, observation.base_version) != (
        binding.snapshot_ref.timeline_id,
        binding.snapshot_ref.timeline_version,
    ):
        block(PlanningDisposition.STALE, PlanningReason.STALE_CANDIDATE)
    if (observation.object_id, observation.pause_range) != (
        binding.object_id,
        binding.original_pause_range,
    ):
        block(PlanningDisposition.TARGET_RESOLUTION_REQUIRED, PlanningReason.BINDING_MISMATCH)
    if inputs.planning_contract_version != "v1":
        block(PlanningDisposition.UNSUPPORTED, PlanningReason.UNSUPPORTED_CONTRACT)

    def check_binding(other: PlanningBinding, failure: PlanningDisposition) -> None:
        if other.snapshot_ref != binding.snapshot_ref or other.snapshot_ref != current:
            block(PlanningDisposition.STALE, PlanningReason.STALE_BINDING)
        if other.object_id != binding.object_id:
            block(PlanningDisposition.UNSUPPORTED, PlanningReason.CROSS_PLACEMENT_UNSUPPORTED)
        if (other.candidate_ref, other.original_pause_range) != (
            binding.candidate_ref,
            binding.original_pause_range,
        ):
            block(failure, PlanningReason.BINDING_MISMATCH)

    geometry = inputs.geometry
    primary: FrameRange | None = None
    intent = (
        TemporalEditIntent.SHORTEN_GAP
        if candidate.action == PauseAction.TIGHTEN
        else TemporalEditIntent.CLOSE_GAP
    )
    if geometry is None:
        block(PlanningDisposition.GEOMETRY_REQUIRED, PlanningReason.GEOMETRY_MISSING)
    else:
        check_binding(geometry.binding, PlanningDisposition.GEOMETRY_REQUIRED)
        if geometry.geometry_contract_version != "v1":
            block(PlanningDisposition.UNSUPPORTED, PlanningReason.UNSUPPORTED_CONTRACT)
        if len(geometry.removed_ranges) > 1:
            block(PlanningDisposition.UNSUPPORTED, PlanningReason.MULTI_RANGE_GEOMETRY_UNSUPPORTED)
        elif not geometry.removed_ranges:
            block(PlanningDisposition.GEOMETRY_REQUIRED, PlanningReason.GEOMETRY_INVALID)
        else:
            primary = geometry.removed_ranges[0]
            pause = binding.original_pause_range
            if not pause.contains(primary):
                block(PlanningDisposition.GEOMETRY_REQUIRED, PlanningReason.GEOMETRY_INVALID)
            retained = (
                candidate.suggested_retained_frames
                if candidate.action == PauseAction.TIGHTEN
                else 0
            )
            if (
                retained is None
                or geometry.retained_duration_frames != retained
                or primary.duration != pause.duration - retained
                or (candidate.action == PauseAction.REMOVE and primary != pause)
            ):
                block(PlanningDisposition.GEOMETRY_REQUIRED, PlanningReason.GEOMETRY_CONFLICT)
    target = inputs.target
    if target is None:
        block(PlanningDisposition.TARGET_RESOLUTION_REQUIRED, PlanningReason.TARGET_NOT_EXACT)
    else:
        check_binding(target.binding, PlanningDisposition.TARGET_RESOLUTION_REQUIRED)
        if target.status == MappingStatus.STALE:
            block(PlanningDisposition.STALE, PlanningReason.STALE_TARGET)
        elif target.status == MappingStatus.UNSUPPORTED:
            block(PlanningDisposition.UNSUPPORTED, PlanningReason.TARGET_UNSUPPORTED)
        elif target.status != MappingStatus.EXACT:
            block(PlanningDisposition.TARGET_RESOLUTION_REQUIRED, PlanningReason.TARGET_NOT_EXACT)
        if target.status == MappingStatus.EXACT:
            if target.placement_range is None or not target.placement_range.contains(
                binding.original_pause_range
            ):
                block(PlanningDisposition.UNSUPPORTED, PlanningReason.CROSS_PLACEMENT_UNSUPPORTED)
            if primary is not None and target.resolved_range != primary:
                block(
                    PlanningDisposition.TARGET_RESOLUTION_REQUIRED,
                    PlanningReason.TARGET_RANGE_MISMATCH,
                )
    snapshot = inputs.snapshot_readiness
    if snapshot is None:
        block(PlanningDisposition.TARGET_RESOLUTION_REQUIRED, PlanningReason.SNAPSHOT_NOT_READY)
    else:
        check_binding(snapshot.binding, PlanningDisposition.TARGET_RESOLUTION_REQUIRED)
        if snapshot.status == ReadinessStatus.STALE:
            block(PlanningDisposition.STALE, PlanningReason.STALE_SNAPSHOT)
        elif snapshot.status == ReadinessStatus.UNSUPPORTED:
            block(PlanningDisposition.UNSUPPORTED, PlanningReason.SNAPSHOT_UNSUPPORTED)
        elif snapshot.status != ReadinessStatus.READY:
            block(PlanningDisposition.TARGET_RESOLUTION_REQUIRED, PlanningReason.SNAPSHOT_NOT_READY)
    dependency = inputs.dependency
    if dependency is None:
        block(
            PlanningDisposition.DEPENDENCY_RESOLUTION_REQUIRED, PlanningReason.DEPENDENCY_UNRESOLVED
        )
    else:
        check_binding(dependency.binding, PlanningDisposition.DEPENDENCY_RESOLUTION_REQUIRED)
        if dependency.status == DependencyStatus.UNSUPPORTED:
            block(PlanningDisposition.UNSUPPORTED, PlanningReason.DEPENDENCY_UNSUPPORTED)
        elif dependency.status == DependencyStatus.CONFLICT:
            block(
                PlanningDisposition.DEPENDENCY_RESOLUTION_REQUIRED,
                PlanningReason.DEPENDENCY_CONFLICT,
            )
        elif dependency.status != DependencyStatus.RESOLVED:
            block(
                PlanningDisposition.DEPENDENCY_RESOLUTION_REQUIRED,
                PlanningReason.DEPENDENCY_UNRESOLVED,
            )
        if (
            geometry is not None
            and primary is not None
            and dependency.status == DependencyStatus.RESOLVED
            and (
                dependency.geometry_ref != geometry.geometry_ref
                or dependency.primary_range != primary
                or dependency.temporal_intent != intent
            )
        ):
            block(
                PlanningDisposition.DEPENDENCY_RESOLUTION_REQUIRED,
                PlanningReason.DEPENDENCY_ASSESSMENT_MISMATCH,
            )
    if blocked:
        disposition = next(
            d
            for d in (
                PlanningDisposition.STALE,
                PlanningDisposition.UNSUPPORTED,
                PlanningDisposition.TARGET_RESOLUTION_REQUIRED,
                PlanningDisposition.GEOMETRY_REQUIRED,
                PlanningDisposition.DEPENDENCY_RESOLUTION_REQUIRED,
            )
            if d in blocked
        )
        return PausePlanningResult(inputs, disposition, tuple(reasons))
    assert geometry is not None and primary is not None
    assert target is not None and snapshot is not None and dependency is not None
    proposal = PauseEditProposal(
        inputs.proposal_ref,
        binding,
        intent,
        geometry,
        primary,
        target.assessment_ref,
        snapshot.assessment_ref,
        dependency.assessment_ref,
        inputs.planning_contract_version,
    )
    return PausePlanningResult(
        inputs,
        PlanningDisposition.READY_FOR_PREFLIGHT,
        (PlanningReason.READY_FOR_PREFLIGHT,),
        proposal,
    )
