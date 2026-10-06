"""ADR-021 pure mapping over supplied correspondence, never native discovery or authority."""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from math import gcd

from .domain import FrameRange, MediaId, TimelineId, TimelineObjectId, TimelineVersion


class TimeDomain(str, Enum):
    SOURCE_FRAME = "SOURCE_FRAME"
    TIMELINE_FRAME = "TIMELINE_FRAME"


@dataclass(frozen=True)
class FrameRate:
    """Exact cadence metadata, not a placement transform or timecode-label policy."""

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise TypeError("Frame rate requires integer numerator and denominator")
        if self.numerator <= 0 or self.denominator <= 0:
            raise ValueError("Frame rate must be positive")
        divisor = gcd(self.numerator, self.denominator)
        object.__setattr__(self, "numerator", self.numerator // divisor)
        object.__setattr__(self, "denominator", self.denominator // divisor)


@dataclass(frozen=True)
class SourceFrameRange:
    frames: FrameRange

    def __post_init__(self) -> None:
        if not isinstance(self.frames, FrameRange):
            raise TypeError("Source coordinates require an integer FrameRange")

    @property
    def domain(self) -> TimeDomain:
        return TimeDomain.SOURCE_FRAME


@dataclass(frozen=True)
class TimelineFrameRange:
    frames: FrameRange

    def __post_init__(self) -> None:
        if not isinstance(self.frames, FrameRange):
            raise TypeError("Timeline coordinates require an integer FrameRange")

    @property
    def domain(self) -> TimeDomain:
        return TimeDomain.TIMELINE_FRAME


CoordinateRange = SourceFrameRange | TimelineFrameRange


def _identity(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Opaque identity must be a nonempty string")


@dataclass(frozen=True)
class NativeSnapshotRef:
    """Caller-supplied state token; no claim of native identity generation/verification."""

    timeline_id: TimelineId
    timeline_version: TimelineVersion
    state_token: str

    def __post_init__(self) -> None:
        _identity(self.timeline_id)
        _identity(self.state_token)
        if type(self.timeline_version) is not int or self.timeline_version < 0:
            raise ValueError("Snapshot version must be a nonnegative integer")


class MappingKind(str, Enum):
    IDENTITY_1X = "IDENTITY_1X"
    AFFINE_FORWARD = "AFFINE_FORWARD"
    REVERSE = "REVERSE"
    FREEZE = "FREEZE"
    VARIABLE_RETIME = "VARIABLE_RETIME"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PlacementTemporalBinding:
    """Explicit single-fragment correspondence; object identity remains fake-only."""

    mapping_ref: str
    snapshot_ref: NativeSnapshotRef
    object_id: TimelineObjectId
    media_id: MediaId
    timeline_range: TimelineFrameRange
    source_range: SourceFrameRange
    timeline_rate: FrameRate
    source_rate: FrameRate
    mapping_kind: MappingKind

    def __post_init__(self) -> None:
        _identity(self.mapping_ref)
        _identity(self.media_id)
        for value, expected in (
            (self.snapshot_ref, NativeSnapshotRef),
            (self.object_id, TimelineObjectId),
            (self.timeline_range, TimelineFrameRange),
            (self.source_range, SourceFrameRange),
            (self.timeline_rate, FrameRate),
            (self.source_rate, FrameRate),
            (self.mapping_kind, MappingKind),
        ):
            if not isinstance(value, expected):
                raise TypeError("Binding requires typed snapshot, identity, ranges, rates and kind")
        if (
            self.mapping_kind == MappingKind.IDENTITY_1X
            and self.timeline_range.frames.duration != self.source_range.frames.duration
        ):
            raise ValueError("IDENTITY_1X requires equal explicit span lengths")


@dataclass(frozen=True)
class MappingRequest:
    snapshot_ref: NativeSnapshotRef
    object_id: TimelineObjectId
    media_id: MediaId
    interval: CoordinateRange

    def __post_init__(self) -> None:
        _identity(self.media_id)
        if not isinstance(self.snapshot_ref, NativeSnapshotRef):
            raise TypeError("Request requires a snapshot reference")
        if not isinstance(self.object_id, TimelineObjectId):
            raise TypeError("Request requires explicit placement identity")
        if not isinstance(self.interval, (SourceFrameRange, TimelineFrameRange)):
            raise TypeError("Request requires explicit source or timeline coordinates")


class MappingStatus(str, Enum):
    EXACT = "EXACT"
    STALE = "STALE"
    AMBIGUOUS = "AMBIGUOUS"
    NON_INTEGRAL = "NON_INTEGRAL"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    UNSUPPORTED = "UNSUPPORTED"


class MappingReason(str, Enum):
    EXACT_CORRESPONDENCE = "EXACT_CORRESPONDENCE"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    NO_EXPLICIT_BINDING = "NO_EXPLICIT_BINDING"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    MULTIPLE_BINDINGS = "MULTIPLE_BINDINGS"
    DUPLICATE_MAPPING_REFERENCE = "DUPLICATE_MAPPING_REFERENCE"
    CROSS_FRAGMENT_RANGE = "CROSS_FRAGMENT_RANGE"
    OUTSIDE_BOUND_SPAN = "OUTSIDE_BOUND_SPAN"
    UNSUPPORTED_KIND = "UNSUPPORTED_KIND"
    NON_INTEGRAL_START = "NON_INTEGRAL_START"
    NON_INTEGRAL_END = "NON_INTEGRAL_END"


def _bindings(values: tuple[PlacementTemporalBinding, ...]) -> tuple[PlacementTemporalBinding, ...]:
    copied = tuple(values)
    if any(not isinstance(value, PlacementTemporalBinding) for value in copied):
        raise TypeError("Explicit typed bindings are required")
    # repr consists solely of immutable typed values, no insertion order or external state.
    return tuple(sorted(copied, key=repr))


@dataclass(frozen=True)
class TemporalMappingResult:
    """Provenance plus a mathematical result; never approval or execution permission."""

    request: MappingRequest
    current_snapshot: NativeSnapshotRef
    candidate_bindings: tuple[PlacementTemporalBinding, ...]
    status: MappingStatus
    reasons: tuple[MappingReason, ...]
    binding: PlacementTemporalBinding | None = None
    source_range: SourceFrameRange | None = None
    timeline_range: TimelineFrameRange | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, MappingRequest) or not isinstance(
            self.current_snapshot, NativeSnapshotRef
        ):
            raise TypeError("Result requires request and current snapshot provenance")
        if not isinstance(self.status, MappingStatus):
            raise TypeError("Mapping status must be typed")
        candidates = _bindings(self.candidate_bindings)
        reasons = tuple(self.reasons)
        if not reasons or any(not isinstance(reason, MappingReason) for reason in reasons):
            raise ValueError("Result requires machine-readable reasons")
        if self.status == MappingStatus.EXACT:
            binding, source, timeline = self.binding, self.source_range, self.timeline_range
            if (
                not isinstance(binding, PlacementTemporalBinding)
                or not isinstance(source, SourceFrameRange)
                or not isinstance(timeline, TimelineFrameRange)
            ):
                raise ValueError("EXACT requires complete typed correspondence")
            req = self.request
            if (
                binding not in candidates
                or binding.snapshot_ref != self.current_snapshot
                or req.snapshot_ref != self.current_snapshot
                or binding.object_id != req.object_id
                or binding.media_id != req.media_id
            ):
                raise ValueError("EXACT must retain current snapshot and requested identities")
            if not binding.source_range.frames.contains(
                source.frames
            ) or not binding.timeline_range.frames.contains(timeline.frames):
                raise ValueError("EXACT ranges must stay inside the binding")
            if req.interval != (source if isinstance(req.interval, SourceFrameRange) else timeline):
                raise ValueError("EXACT must preserve requested coordinates")
            if binding.mapping_kind not in (MappingKind.IDENTITY_1X, MappingKind.AFFINE_FORWARD):
                raise ValueError("Unsupported mapping kind cannot be EXACT")
            for s, t in (
                (source.frames.start, timeline.frames.start),
                (source.frames.end, timeline.frames.end),
            ):
                if _boundary(s, binding.source_range.frames, binding.timeline_range.frames) != t:
                    raise ValueError("EXACT boundaries must match explicit correspondence")
        elif any(
            value is not None for value in (self.binding, self.source_range, self.timeline_range)
        ):
            raise ValueError("Only EXACT may carry a mapped pair/binding")
        object.__setattr__(self, "candidate_bindings", candidates)
        object.__setattr__(self, "reasons", tuple(sorted(set(reasons), key=lambda r: r.value)))


def _boundary(value: int, origin: FrameRange, destination: FrameRange) -> Fraction:
    return Fraction(destination.start) + Fraction(
        (value - origin.start) * destination.duration, origin.duration
    )


def _span(binding: PlacementTemporalBinding, interval: CoordinateRange) -> FrameRange:
    return (
        binding.source_range.frames
        if isinstance(interval, SourceFrameRange)
        else binding.timeline_range.frames
    )


def map_range(
    request: MappingRequest,
    bindings: tuple[PlacementTemporalBinding, ...],
    current_snapshot: NativeSnapshotRef,
) -> TemporalMappingResult:
    """Map exactly one explicit fragment. Rates never participate in the arithmetic."""
    if not isinstance(request, MappingRequest) or not isinstance(
        current_snapshot, NativeSnapshotRef
    ):
        raise TypeError("Mapping requires a typed request and current snapshot")
    candidates = _bindings(bindings)

    def failed(status: MappingStatus, *reasons: MappingReason) -> TemporalMappingResult:
        return TemporalMappingResult(request, current_snapshot, candidates, status, reasons)

    if request.snapshot_ref != current_snapshot:
        return failed(MappingStatus.STALE, MappingReason.SNAPSHOT_MISMATCH)
    if not candidates:
        return failed(MappingStatus.UNSUPPORTED, MappingReason.NO_EXPLICIT_BINDING)
    matching = tuple(
        b for b in candidates if b.object_id == request.object_id and b.media_id == request.media_id
    )
    if not matching:
        return failed(MappingStatus.AMBIGUOUS, MappingReason.IDENTITY_MISMATCH)
    if any(b.snapshot_ref != current_snapshot for b in matching):
        return failed(MappingStatus.STALE, MappingReason.SNAPSHOT_MISMATCH)
    if len({b.mapping_ref for b in matching}) != len(matching):
        return failed(MappingStatus.AMBIGUOUS, MappingReason.DUPLICATE_MAPPING_REFERENCE)
    interval = request.interval
    containing = tuple(b for b in matching if _span(b, interval).contains(interval.frames))
    if len(containing) > 1:
        return failed(MappingStatus.AMBIGUOUS, MappingReason.MULTIPLE_BINDINGS)
    if not containing:
        overlapping = tuple(
            b
            for b in candidates
            if b.snapshot_ref == current_snapshot and _span(b, interval).overlaps(interval.frames)
        )
        if len(overlapping) > 1:
            return failed(MappingStatus.AMBIGUOUS, MappingReason.CROSS_FRAGMENT_RANGE)
        return failed(MappingStatus.OUT_OF_RANGE, MappingReason.OUTSIDE_BOUND_SPAN)
    binding = containing[0]
    if binding.mapping_kind not in (MappingKind.IDENTITY_1X, MappingKind.AFFINE_FORWARD):
        return failed(MappingStatus.UNSUPPORTED, MappingReason.UNSUPPORTED_KIND)
    origin = _span(binding, interval)
    destination = (
        binding.timeline_range.frames
        if isinstance(interval, SourceFrameRange)
        else binding.source_range.frames
    )
    start = _boundary(interval.frames.start, origin, destination)
    end = _boundary(interval.frames.end, origin, destination)
    reasons = []
    if start.denominator != 1:
        reasons.append(MappingReason.NON_INTEGRAL_START)
    if end.denominator != 1:
        reasons.append(MappingReason.NON_INTEGRAL_END)
    if reasons:
        return failed(MappingStatus.NON_INTEGRAL, *reasons)
    mapped = FrameRange(start.numerator, end.numerator)
    source = interval if isinstance(interval, SourceFrameRange) else SourceFrameRange(mapped)
    timeline = interval if isinstance(interval, TimelineFrameRange) else TimelineFrameRange(mapped)
    return TemporalMappingResult(
        request,
        current_snapshot,
        candidates,
        MappingStatus.EXACT,
        (MappingReason.EXACT_CORRESPONDENCE,),
        binding,
        source,
        timeline,
    )
