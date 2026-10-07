"""ADR-025 exact consequences and synthetic comparison; no Safety or execution."""

from dataclasses import dataclass, replace
from enum import Enum
from typing import TypeVar

from .domain import FrameRange, MediaId, TimelineObjectId, TrackId
from .pause_planning import PauseEditProposal, PlanningBinding
from .temporal_mapping import MappingKind, NativeSnapshotRef

T = TypeVar("T")


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Reference/version must be a nonempty string")


def _typed(value: object, kind: type[object]) -> None:
    if not isinstance(value, kind):
        raise TypeError(f"Expected {kind.__name__}")


def _values(values: tuple[T, ...], kind: type[T]) -> tuple[T, ...]:
    result = tuple(values)
    for value in result:
        _typed(value, kind)
    if len(set(result)) != len(result):
        raise ValueError("Duplicate values are not evidence")
    return tuple(sorted(result, key=repr))


def _unique_ids(ids: tuple[TimelineObjectId, ...]) -> None:
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate placement identity; concrete correspondence required")


class ParticipationStatus(str, Enum):
    RESOLVED = "RESOLVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CONFLICT = "CONFLICT"
    UNSUPPORTED = "UNSUPPORTED"
    STALE = "STALE"


class ExpectedDiffStatus(str, Enum):
    READY_FOR_PREFLIGHT = "READY_FOR_PREFLIGHT"
    INCOMPLETE = "INCOMPLETE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    STALE = "STALE"
    UNSUPPORTED = "UNSUPPORTED"


class ExpectedDiffReason(str, Enum):
    READY_FOR_PREFLIGHT = "READY_FOR_PREFLIGHT"
    STALE_BASE = "STALE_BASE"
    PARTICIPATION_UNRESOLVED = "PARTICIPATION_UNRESOLVED"
    PARTICIPATION_CONFLICT = "PARTICIPATION_CONFLICT"
    PARTICIPATION_UNSUPPORTED = "PARTICIPATION_UNSUPPORTED"
    CROSSING_OBJECT_UNSUPPORTED = "CROSSING_OBJECT_UNSUPPORTED"
    NONUNIFORM_DISPLACEMENT_UNSUPPORTED = "NONUNIFORM_DISPLACEMENT_UNSUPPORTED"
    GAP_INTERACTION_UNRESOLVED = "GAP_INTERACTION_UNRESOLVED"
    SCOPE_INCOMPLETE = "SCOPE_INCOMPLETE"
    BEFORE_STATE_CONFLICT = "BEFORE_STATE_CONFLICT"
    PRIMARY_OUTSIDE_PLACEMENT = "PRIMARY_OUTSIDE_PLACEMENT"
    UNSUPPORTED_RETIME = "UNSUPPORTED_RETIME"
    UNSUPPORTED_TOPOLOGY_CHANGE = "UNSUPPORTED_TOPOLOGY_CHANGE"
    UNSUPPORTED_CONTRACT = "UNSUPPORTED_CONTRACT"


@dataclass(frozen=True)
class PlacementState:
    """Caller-supplied concrete fake placement, not production persistent identity."""

    object_id: TimelineObjectId
    media_id: MediaId
    track_id: TrackId
    timeline_range: FrameRange
    source_range: FrameRange
    retime: MappingKind = MappingKind.UNKNOWN

    def __post_init__(self) -> None:
        _typed(self.object_id, TimelineObjectId)
        _text(self.media_id)
        _text(self.track_id)
        _typed(self.timeline_range, FrameRange)
        _typed(self.source_range, FrameRange)
        _typed(self.retime, MappingKind)


@dataclass(frozen=True)
class DiffBinding:
    proposal_ref: str
    planning_binding: PlanningBinding
    geometry_ref: str
    primary_range: FrameRange

    def __post_init__(self) -> None:
        _text(self.proposal_ref)
        _text(self.geometry_ref)
        _typed(self.planning_binding, PlanningBinding)
        _typed(self.primary_range, FrameRange)


@dataclass(frozen=True)
class DisplacementParticipant:
    before: PlacementState
    delta_frames: int
    after_track_id: TrackId

    def __post_init__(self) -> None:
        _typed(self.before, PlacementState)
        if type(self.delta_frames) is not int:
            raise TypeError("Delta must be an integer, without rounding")
        _text(self.after_track_id)


@dataclass(frozen=True)
class DisplacementParticipationAssessment:
    assessment_ref: str
    binding: DiffBinding
    status: ParticipationStatus
    participants: tuple[DisplacementParticipant, ...]
    uniform_consequence_verified: bool = False
    known_impacted_ids: tuple[TimelineObjectId, ...] = ()
    protected_risk_ids: tuple[TimelineObjectId, ...] = ()

    def __post_init__(self) -> None:
        _text(self.assessment_ref)
        _typed(self.binding, DiffBinding)
        _typed(self.status, ParticipationStatus)
        if type(self.uniform_consequence_verified) is not bool:
            raise TypeError("Uniform consequence fact must be explicitly boolean")
        participants = _values(self.participants, DisplacementParticipant)
        _unique_ids(tuple(p.before.object_id for p in participants))
        object.__setattr__(self, "participants", participants)
        for field in ("known_impacted_ids", "protected_risk_ids"):
            object.__setattr__(self, field, _values(getattr(self, field), TimelineObjectId))


@dataclass(frozen=True)
class PreservationScope:
    scope_ref: str
    binding: DiffBinding
    objects: tuple[PlacementState, ...]

    def __post_init__(self) -> None:
        _text(self.scope_ref)
        _typed(self.binding, DiffBinding)
        objects = _values(self.objects, PlacementState)
        _unique_ids(tuple(o.object_id for o in objects))
        object.__setattr__(self, "objects", objects)


@dataclass(frozen=True)
class CompilerProvenance:
    compiler_name: str
    compiler_version: str
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        for value in (self.compiler_name, self.compiler_version, self.contract_version):
            _text(value)


@dataclass(frozen=True)
class DiffCompilationInput:
    expected_diff_ref: str
    proposal: PauseEditProposal
    participation: DisplacementParticipationAssessment
    scope: PreservationScope
    current_snapshot: NativeSnapshotRef
    provenance: CompilerProvenance

    def __post_init__(self) -> None:
        _text(self.expected_diff_ref)
        _typed(self.proposal, PauseEditProposal)
        _typed(self.participation, DisplacementParticipationAssessment)
        _typed(self.scope, PreservationScope)
        _typed(self.current_snapshot, NativeSnapshotRef)
        _typed(self.provenance, CompilerProvenance)


@dataclass(frozen=True)
class RangeRemovalEffect:
    change_id: str
    proposal_ref: str
    before: PlacementState
    removed_timeline_range: FrameRange
    geometry_ref: str

    def __post_init__(self) -> None:
        for value in (self.change_id, self.proposal_ref, self.geometry_ref):
            _text(value)
        _typed(self.before, PlacementState)
        _typed(self.removed_timeline_range, FrameRange)
        # Actual effects may violate containment; comparison must be able to report this.


@dataclass(frozen=True)
class TemporalDisplacement:
    before: PlacementState
    after: PlacementState
    delta_frames: int
    source_change_id: str

    def __post_init__(self) -> None:
        _typed(self.before, PlacementState)
        _typed(self.after, PlacementState)
        _text(self.source_change_id)
        if type(self.delta_frames) is not int:
            raise TypeError("Exact integer delta required")
        if replace(self.after, timeline_range=self.before.timeline_range) != self.before:
            raise ValueError("Pure displacement must preserve all non-position metadata")
        a, b = self.after.timeline_range, self.before.timeline_range
        if a.start - b.start != self.delta_frames or a.end - b.end != self.delta_frames:
            raise ValueError("Both boundaries must translate by the exact same delta")


def _problems(
    inputs: DiffCompilationInput,
) -> tuple[tuple[ExpectedDiffStatus, ExpectedDiffReason], ...]:
    problems: list[tuple[ExpectedDiffStatus, ExpectedDiffReason]] = []
    p, assessment, scope = inputs.proposal, inputs.participation, inputs.scope
    binding = DiffBinding(
        p.proposal_ref, p.binding, p.geometry.geometry_ref, p.affected_primary_range
    )
    S, R = ExpectedDiffStatus, ExpectedDiffReason
    if (
        p.binding.snapshot_ref != inputs.current_snapshot
        or assessment.binding != binding
        or scope.binding != binding
        or assessment.status == ParticipationStatus.STALE
    ):
        problems.append((S.STALE, R.STALE_BASE))
    if (
        inputs.provenance.contract_version != "v1"
        or p.planning_contract_version != "v1"
        or p.geometry.geometry_contract_version != "v1"
    ):
        problems.append((S.UNSUPPORTED, R.UNSUPPORTED_CONTRACT))
    status_blocks = {
        ParticipationStatus.REVIEW_REQUIRED: (S.REVIEW_REQUIRED, R.PARTICIPATION_UNRESOLVED),
        ParticipationStatus.CONFLICT: (S.REVIEW_REQUIRED, R.PARTICIPATION_CONFLICT),
        ParticipationStatus.UNSUPPORTED: (S.UNSUPPORTED, R.PARTICIPATION_UNSUPPORTED),
    }
    if assessment.status in status_blocks:
        problems.append(status_blocks[assessment.status])
    if not assessment.uniform_consequence_verified:
        problems.append((S.REVIEW_REQUIRED, R.GAP_INTERACTION_UNRESOLVED))
    objects = {o.object_id: o for o in scope.objects}
    impacted = {
        p.binding.object_id,
        *assessment.known_impacted_ids,
        *assessment.protected_risk_ids,
        *(v.before.object_id for v in assessment.participants),
    }
    if not impacted <= objects.keys():
        problems.append((S.INCOMPLETE, R.SCOPE_INCOMPLETE))
    primary = objects.get(p.binding.object_id)
    if primary is not None and not primary.timeline_range.contains(p.binding.original_pause_range):
        problems.append((S.UNSUPPORTED, R.PRIMARY_OUTSIDE_PLACEMENT))
    changed = ([primary] if primary is not None else []) + [
        v.before for v in assessment.participants
    ]
    for state in changed:
        if state.retime not in (MappingKind.IDENTITY_1X, MappingKind.AFFINE_FORWARD):
            problems.append((S.UNSUPPORTED, R.UNSUPPORTED_RETIME))
        if state.object_id.track_id != state.track_id:
            problems.append((S.UNSUPPORTED, R.UNSUPPORTED_TOPOLOGY_CHANGE))
    for v in assessment.participants:
        if v.before.object_id in objects and objects[v.before.object_id] != v.before:
            problems.append((S.REVIEW_REQUIRED, R.BEFORE_STATE_CONFLICT))
        if (
            v.before.object_id == p.binding.object_id
            or v.before.timeline_range.start < p.affected_primary_range.end
        ):
            problems.append((S.UNSUPPORTED, R.CROSSING_OBJECT_UNSUPPORTED))
        if v.delta_frames != -p.affected_primary_range.duration:
            problems.append((S.UNSUPPORTED, R.NONUNIFORM_DISPLACEMENT_UNSUPPORTED))
        if v.after_track_id != v.before.track_id:
            problems.append((S.UNSUPPORTED, R.UNSUPPORTED_TOPOLOGY_CHANGE))
    return tuple(problems)


def _effects(
    inputs: DiffCompilationInput,
) -> tuple[RangeRemovalEffect, tuple[TemporalDisplacement, ...]]:
    p = inputs.proposal
    before = next(o for o in inputs.scope.objects if o.object_id == p.binding.object_id)
    primary = RangeRemovalEffect(
        f"{inputs.expected_diff_ref}:primary",
        p.proposal_ref,
        before,
        p.affected_primary_range,
        p.geometry.geometry_ref,
    )
    delta = -primary.removed_timeline_range.duration
    displacements = tuple(
        TemporalDisplacement(
            v.before,
            replace(
                v.before,
                timeline_range=FrameRange(
                    v.before.timeline_range.start + delta, v.before.timeline_range.end + delta
                ),
            ),
            delta,
            primary.change_id,
        )
        for v in inputs.participation.participants
    )
    return primary, displacements


@dataclass(frozen=True)
class ExpectedDiff:
    inputs: DiffCompilationInput
    primary_changes: tuple[RangeRemovalEffect, ...]
    displacements: tuple[TemporalDisplacement, ...]
    expected_topology_changes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _typed(self.inputs, DiffCompilationInput)
        primary = _values(self.primary_changes, RangeRemovalEffect)
        displacements = _values(self.displacements, TemporalDisplacement)
        if _problems(self.inputs):
            raise ValueError("Incomplete/non-current inputs cannot carry a complete ExpectedDiff")
        required_primary, required_moves = _effects(self.inputs)
        if primary != (required_primary,) or displacements != _values(
            required_moves, TemporalDisplacement
        ):
            raise ValueError("ExpectedDiff must describe exactly the supplied primary/participants")
        if tuple(self.expected_topology_changes):
            raise ValueError("Pause v1 cannot expect topology mutation")
        object.__setattr__(self, "primary_changes", primary)
        object.__setattr__(self, "displacements", displacements)
        object.__setattr__(self, "expected_topology_changes", ())

    @property
    def expected_diff_ref(self) -> str:
        return self.inputs.expected_diff_ref

    @property
    def base_snapshot(self) -> NativeSnapshotRef:
        return self.inputs.proposal.binding.snapshot_ref

    @property
    def unchanged_object_ids(self) -> tuple[TimelineObjectId, ...]:
        changed = {e.before.object_id for e in self.primary_changes} | {
            d.before.object_id for d in self.displacements
        }
        return tuple(
            sorted(
                (o.object_id for o in self.inputs.scope.objects if o.object_id not in changed),
                key=repr,
            )
        )


@dataclass(frozen=True)
class DiffCompilationResult:
    inputs: DiffCompilationInput
    status: ExpectedDiffStatus
    reasons: tuple[ExpectedDiffReason, ...]
    expected_diff: ExpectedDiff | None = None

    def __post_init__(self) -> None:
        _typed(self.inputs, DiffCompilationInput)
        _typed(self.status, ExpectedDiffStatus)
        reasons = tuple(self.reasons)
        for reason in reasons:
            _typed(reason, ExpectedDiffReason)
        reasons = tuple(sorted(set(reasons), key=lambda r: r.value))
        if not reasons:
            raise ValueError("Result requires reasons")
        if (self.status == ExpectedDiffStatus.READY_FOR_PREFLIGHT) != (
            self.expected_diff is not None
        ):
            raise ValueError("Only READY_FOR_PREFLIGHT carries a complete ExpectedDiff")
        if self.expected_diff is not None:
            _typed(self.expected_diff, ExpectedDiff)
            if self.expected_diff.inputs != self.inputs:
                raise ValueError("Result must retain original input")
        object.__setattr__(self, "reasons", reasons)


def compile_expected_diff(inputs: DiffCompilationInput) -> DiffCompilationResult:
    """Validate precomputed consequences without choosing participants or judging Safety."""
    _typed(inputs, DiffCompilationInput)
    problems = _problems(inputs)
    if problems:
        precedence = (
            ExpectedDiffStatus.STALE,
            ExpectedDiffStatus.UNSUPPORTED,
            ExpectedDiffStatus.REVIEW_REQUIRED,
            ExpectedDiffStatus.INCOMPLETE,
        )
        status = next(s for s in precedence if any(p[0] == s for p in problems))
        return DiffCompilationResult(inputs, status, tuple(r for _, r in problems))
    primary, moves = _effects(inputs)
    return DiffCompilationResult(
        inputs,
        ExpectedDiffStatus.READY_FOR_PREFLIGHT,
        (ExpectedDiffReason.READY_FOR_PREFLIGHT,),
        ExpectedDiff(inputs, (primary,), moves),
    )


class PostRelationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    STALE = "STALE"


@dataclass(frozen=True)
class ActualObjectObservation:
    """Semantic correspondence slot; mismatching before/after identities remain diagnosable."""

    object_id: TimelineObjectId
    before: PlacementState | None
    after: PlacementState | None

    def __post_init__(self) -> None:
        _typed(self.object_id, TimelineObjectId)
        for state in (self.before, self.after):
            if state is not None:
                _typed(state, PlacementState)
        if self.before is None and self.after is None:
            raise ValueError("Empty observation is not evidence")


@dataclass(frozen=True)
class ActualDiff:
    actual_diff_ref: str
    expected_diff_ref: str
    base_snapshot: NativeSnapshotRef
    post_snapshot: NativeSnapshotRef
    primary_changes: tuple[RangeRemovalEffect, ...]
    observations: tuple[ActualObjectObservation, ...]
    post_relation_status: PostRelationStatus = PostRelationStatus.UNVERIFIED
    post_relation_evidence_ref: str | None = None
    identity_evidence_ref: str | None = None
    topology_change_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.actual_diff_ref)
        _text(self.expected_diff_ref)
        _typed(self.base_snapshot, NativeSnapshotRef)
        _typed(self.post_snapshot, NativeSnapshotRef)
        _typed(self.post_relation_status, PostRelationStatus)
        for ref in (self.post_relation_evidence_ref, self.identity_evidence_ref):
            if ref is not None:
                _text(ref)
        primary = _values(self.primary_changes, RangeRemovalEffect)
        if len({p.change_id for p in primary}) != len(primary):
            raise ValueError("Duplicate change ID")
        observations = _values(self.observations, ActualObjectObservation)
        _unique_ids(tuple(o.object_id for o in observations))
        topology = _values(self.topology_change_refs, str)
        for ref in topology:
            _text(ref)
        object.__setattr__(self, "primary_changes", primary)
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "topology_change_refs", topology)


class DiffVerificationStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNVERIFIED = "UNVERIFIED"
    STALE = "STALE"


class DiffVerificationReason(str, Enum):
    MATCHED = "MATCHED"
    MISSING_EXPECTED_CHANGE = "MISSING_EXPECTED_CHANGE"
    UNEXPECTED_CHANGE = "UNEXPECTED_CHANGE"
    WRONG_PRIMARY_RANGE = "WRONG_PRIMARY_RANGE"
    WRONG_DISPLACEMENT = "WRONG_DISPLACEMENT"
    MEDIA_IDENTITY_CHANGED = "MEDIA_IDENTITY_CHANGED"
    SOURCE_RANGE_CHANGED = "SOURCE_RANGE_CHANGED"
    DURATION_CHANGED = "DURATION_CHANGED"
    TRACK_MEMBERSHIP_CHANGED = "TRACK_MEMBERSHIP_CHANGED"
    PLACEMENT_IDENTITY_CHANGED = "PLACEMENT_IDENTITY_CHANGED"
    BEFORE_STATE_MISMATCH = "BEFORE_STATE_MISMATCH"
    RETIME_CHANGED = "RETIME_CHANGED"
    IDENTITY_UNVERIFIABLE = "IDENTITY_UNVERIFIABLE"
    POST_RELATION_UNVERIFIED = "POST_RELATION_UNVERIFIED"
    POST_SNAPSHOT_STALE = "POST_SNAPSHOT_STALE"
    SCOPE_OBSERVATION_INCOMPLETE = "SCOPE_OBSERVATION_INCOMPLETE"


@dataclass(frozen=True)
class DiffVerificationResult:
    expected_diff_ref: str
    actual_diff_ref: str
    status: DiffVerificationStatus
    reasons: tuple[DiffVerificationReason, ...]
    affected_object_ids: tuple[TimelineObjectId, ...] = ()

    def __post_init__(self) -> None:
        _text(self.expected_diff_ref)
        _text(self.actual_diff_ref)
        _typed(self.status, DiffVerificationStatus)
        reasons = tuple(self.reasons)
        for reason in reasons:
            _typed(reason, DiffVerificationReason)
        if not reasons:
            raise ValueError("Verification requires reasons")
        if (self.status == DiffVerificationStatus.MATCH) != (
            set(reasons) == {DiffVerificationReason.MATCHED}
        ):
            raise ValueError("MATCH cannot carry unresolved or mismatch reasons")
        object.__setattr__(self, "reasons", tuple(sorted(set(reasons), key=lambda r: r.value)))
        object.__setattr__(
            self, "affected_object_ids", _values(self.affected_object_ids, TimelineObjectId)
        )


def verify_diff(
    expected: ExpectedDiff, actual: ActualDiff, current_post_snapshot: NativeSnapshotRef
) -> DiffVerificationResult:
    """Compare synthetic semantic evidence. MATCH is scoped, not native certification."""
    _typed(expected, ExpectedDiff)
    _typed(actual, ActualDiff)
    _typed(current_post_snapshot, NativeSnapshotRef)
    R, S = DiffVerificationReason, DiffVerificationStatus
    reasons: set[DiffVerificationReason] = set()
    affected: set[TimelineObjectId] = set()

    def flag(reason: DiffVerificationReason, object_id: TimelineObjectId) -> None:
        reasons.add(reason)
        affected.add(object_id)

    stale = (
        actual.base_snapshot != expected.base_snapshot
        or actual.expected_diff_ref != expected.expected_diff_ref
        or actual.post_snapshot != current_post_snapshot
        or actual.post_snapshot.timeline_id != expected.base_snapshot.timeline_id
        or actual.post_relation_status == PostRelationStatus.STALE
    )
    if stale:
        reasons.add(R.POST_SNAPSHOT_STALE)
    identity_missing = actual.identity_evidence_ref is None
    relation_missing = (
        actual.post_relation_status != PostRelationStatus.VERIFIED
        or actual.post_relation_evidence_ref is None
    )
    if identity_missing:
        reasons.add(R.IDENTITY_UNVERIFIABLE)
    if relation_missing and actual.post_relation_status != PostRelationStatus.STALE:
        reasons.add(R.POST_RELATION_UNVERIFIED)
    if actual.topology_change_refs:
        reasons.add(R.TRACK_MEMBERSHIP_CHANGED)
    required_primary = {p.change_id: p for p in expected.primary_changes}
    observed_primary = {p.change_id: p for p in actual.primary_changes}
    for change_id, p in required_primary.items():
        got = observed_primary.get(change_id)
        if got is None:
            flag(R.MISSING_EXPECTED_CHANGE, p.before.object_id)
        elif got != p:
            flag(R.WRONG_PRIMARY_RANGE, p.before.object_id)
    for change_id, p in observed_primary.items():
        if change_id not in required_primary:
            flag(R.UNEXPECTED_CHANGE, p.before.object_id)
    objects = {o.object_id: o for o in expected.inputs.scope.objects}
    primary_ids = {p.before.object_id for p in expected.primary_changes}
    moves = {d.before.object_id: d for d in expected.displacements}
    observations = {o.object_id: o for o in actual.observations}
    incomplete = False
    for oid, before in objects.items():
        if oid in primary_ids:
            continue
        obs = observations.get(oid)
        if obs is None:
            if oid in moves:
                flag(R.MISSING_EXPECTED_CHANGE, oid)
            else:
                incomplete = True
                flag(R.SCOPE_OBSERVATION_INCOMPLETE, oid)
            continue
        if obs.before != before:
            flag(R.BEFORE_STATE_MISMATCH, oid)
        want = moves[oid].after if oid in moves else before
        after = obs.after
        if after is None:
            flag(R.UNEXPECTED_CHANGE, oid)
            continue
        if after.object_id != want.object_id:
            flag(R.PLACEMENT_IDENTITY_CHANGED, oid)
        if after.media_id != want.media_id:
            flag(R.MEDIA_IDENTITY_CHANGED, oid)
        if after.source_range != want.source_range:
            flag(R.SOURCE_RANGE_CHANGED, oid)
        if after.track_id != want.track_id:
            flag(R.TRACK_MEMBERSHIP_CHANGED, oid)
        if after.retime != want.retime:
            flag(R.RETIME_CHANGED, oid)
        if after.timeline_range.duration != want.timeline_range.duration:
            flag(R.DURATION_CHANGED, oid)
        if after.timeline_range != want.timeline_range:
            flag(R.WRONG_DISPLACEMENT if oid in moves else R.UNEXPECTED_CHANGE, oid)
    for oid, obs in observations.items():
        if oid in primary_ids or (oid not in objects and obs.before != obs.after):
            flag(R.UNEXPECTED_CHANGE, oid)
    non_mismatch = {
        R.POST_SNAPSHOT_STALE,
        R.IDENTITY_UNVERIFIABLE,
        R.POST_RELATION_UNVERIFIED,
        R.SCOPE_OBSERVATION_INCOMPLETE,
    }
    if stale:
        status = S.STALE
    elif identity_missing or relation_missing:
        status = S.UNVERIFIED
    elif reasons - non_mismatch:
        status = S.MISMATCH
    elif incomplete:
        status = S.UNVERIFIED
    else:
        status = S.MATCH
        reasons.add(R.MATCHED)
    return DiffVerificationResult(
        expected.expected_diff_ref, actual.actual_diff_ref, status, tuple(reasons), tuple(affected)
    )
