"""ADR-024 pure exact geometry resolution. No confidence derivation, ranking or execution."""

from dataclasses import dataclass
from enum import Enum

from .domain import FrameRange
from .pause import PauseAction, PauseCandidate
from .pause_planning import PlanningBinding
from .temporal_mapping import MappingStatus, NativeSnapshotRef


class GeometryConstraintKind(str, Enum):
    CUT_START_ANCHOR = "CUT_START_ANCHOR"
    CUT_END_ANCHOR = "CUT_END_ANCHOR"
    MUST_PRESERVE_RANGE = "MUST_PRESERVE_RANGE"
    ALLOWED_REMOVAL_RANGE = "ALLOWED_REMOVAL_RANGE"


class GeometryConfidence(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    UNKNOWN = "UNKNOWN"


class GeometryProducerKind(str, Enum):
    EXPLICIT_CALLER = "EXPLICIT_CALLER"
    DETERMINISTIC_RULE = "DETERMINISTIC_RULE"
    FUTURE_MODEL = "FUTURE_MODEL"


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Opaque reference/version must be nonempty")


@dataclass(frozen=True)
class GeometryProducerRef:
    producer_kind: GeometryProducerKind
    producer_name: str
    producer_version: str
    geometry_contract_version: str
    producer_config_ref: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.producer_kind, GeometryProducerKind):
            raise TypeError("Producer kind must be typed")
        for value in (self.producer_name, self.producer_version, self.geometry_contract_version):
            _text(value)
        if self.producer_config_ref is not None:
            _text(self.producer_config_ref)


def _metadata(
    binding: PlanningBinding, producer: GeometryProducerRef, confidence: GeometryConfidence
) -> None:
    if not isinstance(binding, PlanningBinding) or not isinstance(producer, GeometryProducerRef):
        raise TypeError("Geometry evidence requires typed binding and producer")
    if not isinstance(confidence, GeometryConfidence):
        raise TypeError("GeometryConfidence must be explicitly supplied, not converted")


@dataclass(frozen=True)
class GeometryConstraint:
    constraint_id: str
    binding: PlanningBinding
    kind: GeometryConstraintKind
    payload: int | FrameRange
    producer: GeometryProducerRef
    confidence: GeometryConfidence

    def __post_init__(self) -> None:
        _text(self.constraint_id)
        _metadata(self.binding, self.producer, self.confidence)
        if not isinstance(self.kind, GeometryConstraintKind):
            raise TypeError("Exactly the four typed v1 constraint kinds are supported")
        if self.kind in (
            GeometryConstraintKind.CUT_START_ANCHOR,
            GeometryConstraintKind.CUT_END_ANCHOR,
        ):
            if type(self.payload) is not int:
                raise TypeError("Anchor must be an already-aligned integer timeline boundary")
            if self.payload < 0:
                raise ValueError("Anchor cannot be negative")
        elif not isinstance(self.payload, FrameRange):
            raise TypeError("Preserve/allowed payload must be an integer FrameRange")


@dataclass(frozen=True)
class ExplicitGeometryInput:
    input_id: str
    binding: PlanningBinding
    removed_ranges: tuple[FrameRange, ...]
    producer: GeometryProducerRef
    confidence: GeometryConfidence

    def __post_init__(self) -> None:
        _text(self.input_id)
        _metadata(self.binding, self.producer, self.confidence)
        ranges = tuple(self.removed_ranges)
        if any(not isinstance(r, FrameRange) for r in ranges):
            raise TypeError("Explicit geometry needs typed integer ranges")
        object.__setattr__(self, "removed_ranges", ranges)


@dataclass(frozen=True)
class GeometryResolutionInput:
    resolution_ref: str
    candidate: PauseCandidate
    binding: PlanningBinding
    current_snapshot: NativeSnapshotRef
    placement_range: FrameRange
    mapping_status: MappingStatus
    constraints: tuple[GeometryConstraint, ...] = ()
    explicit_geometries: tuple[ExplicitGeometryInput, ...] = ()
    geometry_contract_version: str = "v1"

    def __post_init__(self) -> None:
        _text(self.resolution_ref)
        _text(self.geometry_contract_version)
        for value, expected in (
            (self.candidate, PauseCandidate),
            (self.binding, PlanningBinding),
            (self.current_snapshot, NativeSnapshotRef),
            (self.placement_range, FrameRange),
            (self.mapping_status, MappingStatus),
        ):
            if not isinstance(value, expected):
                raise TypeError("Resolution requires typed current aligned input")
        constraints, explicit = tuple(self.constraints), tuple(self.explicit_geometries)
        if any(not isinstance(c, GeometryConstraint) for c in constraints) or any(
            not isinstance(g, ExplicitGeometryInput) for g in explicit
        ):
            raise TypeError("Geometry evidence must be typed")
        ids = [c.constraint_id for c in constraints] + [g.input_id for g in explicit]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate geometry source identity")
        object.__setattr__(
            self, "constraints", tuple(sorted(constraints, key=lambda c: c.constraint_id))
        )
        object.__setattr__(
            self, "explicit_geometries", tuple(sorted(explicit, key=lambda g: g.input_id))
        )


@dataclass(frozen=True)
class GeometrySupport:
    """A supplied confidence/provenance record, never an aggregate geometry score."""

    source_ref: str
    producer: GeometryProducerRef
    confidence: GeometryConfidence
    source_constraint_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.source_ref)
        if not isinstance(self.producer, GeometryProducerRef) or not isinstance(
            self.confidence, GeometryConfidence
        ):
            raise TypeError("Support retains typed producer and supplied confidence")
        ids = tuple(self.source_constraint_ids)
        for value in ids:
            _text(value)
        object.__setattr__(self, "source_constraint_ids", tuple(sorted(set(ids))))


@dataclass(frozen=True)
class CutGeometryCandidate:
    geometry_id: str
    binding: PlanningBinding
    removed_range: FrameRange
    supports: tuple[GeometrySupport, ...]

    def __post_init__(self) -> None:
        _text(self.geometry_id)
        if not isinstance(self.binding, PlanningBinding) or not isinstance(
            self.removed_range, FrameRange
        ):
            raise TypeError("Candidate requires typed binding and one range")
        if not self.binding.original_pause_range.contains(self.removed_range):
            raise ValueError("Candidate must stay inside pause")
        supports = tuple(self.supports)
        if not supports or any(not isinstance(s, GeometrySupport) for s in supports):
            raise ValueError("Candidate requires explicit supplied provenance")
        object.__setattr__(self, "supports", tuple(sorted(set(supports), key=repr)))

    @property
    def retained_leading_frames(self) -> int:
        return self.removed_range.start - self.binding.original_pause_range.start

    @property
    def retained_trailing_frames(self) -> int:
        return self.binding.original_pause_range.end - self.removed_range.end

    @property
    def retained_total_frames(self) -> int:
        return self.retained_leading_frames + self.retained_trailing_frames

    @property
    def geometry_confidences(self) -> tuple[GeometryConfidence, ...]:
        """All supplied labels for inspection, not a selected/derived confidence."""
        return tuple(sorted({s.confidence for s in self.supports}, key=lambda c: c.value))

    @property
    def source_constraint_ids(self) -> tuple[str, ...]:
        return tuple(sorted({ref for s in self.supports for ref in s.source_constraint_ids}))

    @property
    def support_input_ids(self) -> tuple[str, ...]:
        return tuple(sorted({s.source_ref for s in self.supports}))


class GeometryResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNRESOLVED = "UNRESOLVED"
    STALE = "STALE"
    UNSUPPORTED = "UNSUPPORTED"


class GeometryResolutionReason(str, Enum):
    UNIQUE_GEOMETRY = "UNIQUE_GEOMETRY"
    MULTIPLE_GEOMETRIES = "MULTIPLE_GEOMETRIES"
    INSUFFICIENT_CONSTRAINTS = "INSUFFICIENT_CONSTRAINTS"
    NO_VALID_GEOMETRY = "NO_VALID_GEOMETRY"
    NO_VALID_ANCHOR_PAIR = "NO_VALID_ANCHOR_PAIR"
    REQUIRED_DURATION_MISMATCH = "REQUIRED_DURATION_MISMATCH"
    PRESERVE_RANGE_CONFLICT = "PRESERVE_RANGE_CONFLICT"
    OUTSIDE_ALLOWED_REMOVAL = "OUTSIDE_ALLOWED_REMOVAL"
    OUTSIDE_PAUSE = "OUTSIDE_PAUSE"
    STALE_BINDING = "STALE_BINDING"
    MIXED_BINDING = "MIXED_BINDING"
    MULTI_RANGE_UNSUPPORTED = "MULTI_RANGE_UNSUPPORTED"
    CROSS_PLACEMENT_UNSUPPORTED = "CROSS_PLACEMENT_UNSUPPORTED"
    UNSUPPORTED_CONTRACT = "UNSUPPORTED_CONTRACT"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    MAPPING_NOT_EXACT = "MAPPING_NOT_EXACT"
    EMPTY_GEOMETRY = "EMPTY_GEOMETRY"


@dataclass(frozen=True)
class GeometryDiagnostic:
    reason: GeometryResolutionReason
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.reason, GeometryResolutionReason):
            raise TypeError("Resolution diagnostics must be typed")
        ids = tuple(self.source_ids)
        for value in ids:
            _text(value)
        object.__setattr__(self, "source_ids", tuple(sorted(set(ids))))


@dataclass(frozen=True)
class GeometryResolutionResult:
    inputs: GeometryResolutionInput
    status: GeometryResolutionStatus
    candidates: tuple[CutGeometryCandidate, ...]
    diagnostics: tuple[GeometryDiagnostic, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.inputs, GeometryResolutionInput) or not isinstance(
            self.status, GeometryResolutionStatus
        ):
            raise TypeError("Resolution result requires typed input/status")
        candidates, diagnostics = tuple(self.candidates), tuple(self.diagnostics)
        if any(not isinstance(c, CutGeometryCandidate) for c in candidates):
            raise TypeError("Result requires typed candidates")
        if not diagnostics or any(not isinstance(d, GeometryDiagnostic) for d in diagnostics):
            raise ValueError("Result requires typed diagnostics")
        if len({c.removed_range for c in candidates}) != len(candidates):
            raise ValueError("Equal ranges must preserve provenance in one canonical candidate")
        expected = (
            GeometryResolutionStatus.UNRESOLVED
            if not candidates
            else GeometryResolutionStatus.RESOLVED
            if len(candidates) == 1
            else GeometryResolutionStatus.REVIEW_REQUIRED
        )
        if self.status in (GeometryResolutionStatus.STALE, GeometryResolutionStatus.UNSUPPORTED):
            if candidates:
                raise ValueError("Blocked resolution cannot contain usable candidates")
        elif self.status != expected:
            raise ValueError("Resolution follows distinct-range count, never confidence")
        ids = {c.constraint_id for c in self.inputs.constraints} | {
            g.input_id for g in self.inputs.explicit_geometries
        }
        for candidate in candidates:
            if (
                candidate.binding != self.inputs.binding
                or candidate.retained_total_frames
                != self.inputs.candidate.suggested_retained_frames
            ):
                raise ValueError("Geometry must preserve the original bound retained intent")
            if not set(candidate.support_input_ids) <= ids:
                raise ValueError("Geometry support must reference supplied evidence")
        if any(not set(d.source_ids) <= ids for d in diagnostics):
            raise ValueError("Diagnostic IDs must reference supplied evidence")
        object.__setattr__(
            self,
            "candidates",
            tuple(sorted(candidates, key=lambda c: (c.removed_range.start, c.removed_range.end))),
        )
        object.__setattr__(
            self,
            "diagnostics",
            tuple(sorted(set(diagnostics), key=lambda d: (d.reason.value, d.source_ids))),
        )


def _support(item: GeometryConstraint | ExplicitGeometryInput) -> GeometrySupport:
    if isinstance(item, GeometryConstraint):
        return GeometrySupport(
            item.constraint_id, item.producer, item.confidence, (item.constraint_id,)
        )
    return GeometrySupport(item.input_id, item.producer, item.confidence, ())


def resolve_geometry(inputs: GeometryResolutionInput) -> GeometryResolutionResult:
    """Exact explicit ranges/anchor pairs only. No location defaults, ranking or repair."""
    if not isinstance(inputs, GeometryResolutionInput):
        raise TypeError("Resolver requires immutable typed inputs")
    diagnostics: list[GeometryDiagnostic] = []
    stale, unsupported = False, False

    def diagnostic(reason: GeometryResolutionReason, *ids: str) -> None:
        diagnostics.append(GeometryDiagnostic(reason, ids))

    binding, candidate = inputs.binding, inputs.candidate
    observation = candidate.observation
    pause = binding.original_pause_range
    if binding.snapshot_ref != inputs.current_snapshot or (
        observation.timeline_id,
        observation.base_version,
    ) != (binding.snapshot_ref.timeline_id, binding.snapshot_ref.timeline_version):
        stale = True
        diagnostic(GeometryResolutionReason.STALE_BINDING)
    if (observation.object_id, observation.pause_range) != (binding.object_id, pause):
        unsupported = True
        diagnostic(GeometryResolutionReason.MIXED_BINDING)
    if candidate.action != PauseAction.TIGHTEN:
        unsupported = True
        diagnostic(GeometryResolutionReason.UNSUPPORTED_ACTION)
    if inputs.geometry_contract_version != "v1":
        unsupported = True
        diagnostic(GeometryResolutionReason.UNSUPPORTED_CONTRACT)
    if inputs.mapping_status == MappingStatus.STALE:
        stale = True
        diagnostic(GeometryResolutionReason.STALE_BINDING)
    elif inputs.mapping_status != MappingStatus.EXACT:
        unsupported = True
        diagnostic(GeometryResolutionReason.MAPPING_NOT_EXACT)
    if not inputs.placement_range.contains(pause):
        unsupported = True
        diagnostic(GeometryResolutionReason.CROSS_PLACEMENT_UNSUPPORTED)
    items: tuple[GeometryConstraint | ExplicitGeometryInput, ...] = (
        *inputs.constraints,
        *inputs.explicit_geometries,
    )
    for item in items:
        ref = item.constraint_id if isinstance(item, GeometryConstraint) else item.input_id
        if item.binding.snapshot_ref != binding.snapshot_ref:
            stale = True
            diagnostic(GeometryResolutionReason.STALE_BINDING, ref)
        if item.binding != binding:
            unsupported = True
            diagnostic(GeometryResolutionReason.MIXED_BINDING, ref)
        if item.binding.object_id != binding.object_id:
            diagnostic(GeometryResolutionReason.CROSS_PLACEMENT_UNSUPPORTED, ref)
        if item.producer.geometry_contract_version != inputs.geometry_contract_version:
            unsupported = True
            diagnostic(GeometryResolutionReason.UNSUPPORTED_CONTRACT, ref)
        if isinstance(item, GeometryConstraint):
            value = item.payload
            if (isinstance(value, FrameRange) and not pause.contains(value)) or (
                isinstance(value, int) and not pause.start <= value <= pause.end
            ):
                unsupported = True
                diagnostic(GeometryResolutionReason.OUTSIDE_PAUSE, ref)
        elif len(item.removed_ranges) > 1:
            unsupported = True
            diagnostic(GeometryResolutionReason.MULTI_RANGE_UNSUPPORTED, ref)
    if stale or unsupported:
        status = GeometryResolutionStatus.STALE if stale else GeometryResolutionStatus.UNSUPPORTED
        return GeometryResolutionResult(inputs, status, (), tuple(diagnostics))
    retained = candidate.suggested_retained_frames
    assert retained is not None
    required = pause.duration - retained
    filters = tuple(
        c
        for c in inputs.constraints
        if c.kind
        in (
            GeometryConstraintKind.MUST_PRESERVE_RANGE,
            GeometryConstraintKind.ALLOWED_REMOVAL_RANGE,
        )
    )
    grouped: dict[FrameRange, set[GeometrySupport]] = {}

    def consider(removed: FrameRange, supports: tuple[GeometrySupport, ...]) -> None:
        ids = tuple(s.source_ref for s in supports)
        valid = True
        if not pause.contains(removed):
            diagnostic(GeometryResolutionReason.OUTSIDE_PAUSE, *ids)
            valid = False
        if removed.duration != required:
            diagnostic(GeometryResolutionReason.REQUIRED_DURATION_MISMATCH, *ids)
            valid = False
        for constraint in filters:
            value = constraint.payload
            assert isinstance(value, FrameRange)
            if constraint.kind == GeometryConstraintKind.MUST_PRESERVE_RANGE and removed.overlaps(
                value
            ):
                diagnostic(
                    GeometryResolutionReason.PRESERVE_RANGE_CONFLICT, *ids, constraint.constraint_id
                )
                valid = False
            if (
                constraint.kind == GeometryConstraintKind.ALLOWED_REMOVAL_RANGE
                and not value.contains(removed)
            ):
                diagnostic(
                    GeometryResolutionReason.OUTSIDE_ALLOWED_REMOVAL, *ids, constraint.constraint_id
                )
                valid = False
        if valid:
            grouped.setdefault(removed, set()).update((*supports, *(_support(c) for c in filters)))

    for geometry in inputs.explicit_geometries:
        if geometry.removed_ranges:
            consider(geometry.removed_ranges[0], (_support(geometry),))
        else:
            diagnostic(GeometryResolutionReason.EMPTY_GEOMETRY, geometry.input_id)
    starts = tuple(
        c for c in inputs.constraints if c.kind == GeometryConstraintKind.CUT_START_ANCHOR
    )
    ends = tuple(c for c in inputs.constraints if c.kind == GeometryConstraintKind.CUT_END_ANCHOR)
    exact_pair = False
    for start in starts:
        for end in ends:
            assert isinstance(start.payload, int) and isinstance(end.payload, int)
            if start.payload < end.payload and end.payload - start.payload == required:
                exact_pair = True
                consider(FrameRange(start.payload, end.payload), (_support(start), _support(end)))
            else:
                diagnostic(
                    GeometryResolutionReason.REQUIRED_DURATION_MISMATCH,
                    start.constraint_id,
                    end.constraint_id,
                )
    if (starts or ends) and not exact_pair:
        diagnostic(GeometryResolutionReason.NO_VALID_ANCHOR_PAIR)
    if not inputs.explicit_geometries and (not starts or not ends):
        diagnostic(GeometryResolutionReason.INSUFFICIENT_CONSTRAINTS)
    candidates = tuple(
        CutGeometryCandidate(
            f"{inputs.resolution_ref}:{r.start}:{r.end}", binding, r, tuple(supports)
        )
        for r, supports in grouped.items()
    )
    if not candidates:
        status = GeometryResolutionStatus.UNRESOLVED
        diagnostic(GeometryResolutionReason.NO_VALID_GEOMETRY)
    elif len(candidates) == 1:
        status = GeometryResolutionStatus.RESOLVED
        diagnostic(GeometryResolutionReason.UNIQUE_GEOMETRY)
    else:
        status = GeometryResolutionStatus.REVIEW_REQUIRED
        diagnostic(GeometryResolutionReason.MULTIPLE_GEOMETRIES)
    return GeometryResolutionResult(inputs, status, candidates, tuple(diagnostics))
