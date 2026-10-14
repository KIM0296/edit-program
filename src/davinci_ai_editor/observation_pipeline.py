"""Read-only composition of supplied native captures and aligned producer evidence.

No acquisition, inference, authority or execution. Producer assertions are retained,
not authenticated here. The projected domain snapshot is a placement-only view.
"""

from dataclasses import dataclass
from enum import Enum

from .domain import Clip, FrameRange, TimelineObjectId, TimelineSnapshot, Track
from .evidence import (
    EvidenceBundle,
    PreparationResult,
    PreparationStatus,
    ProducerRef,
    prepare_observation,
)
from .native_snapshot import (
    PAUSE_ANALYSIS,
    IdentityRef,
    NativePlacementSnapshot,
    NativeTimelineSnapshot,
    ReadinessResult,
    ReadinessStatus,
    evaluate_readiness,
)
from .pause import PauseCandidate, PauseObservation, classify_pause
from .temporal_mapping import (
    MappingRequest,
    MappingStatus,
    NativeSnapshotRef,
    PlacementTemporalBinding,
    TemporalMappingResult,
    TimelineFrameRange,
    map_range,
)


def _refs(values: tuple[str, ...]) -> tuple[str, ...]:
    result = tuple(values)
    if not result or any(not isinstance(v, str) or not v.strip() for v in result):
        raise ValueError("Explicit nonempty provenance references required")
    return result


@dataclass(frozen=True)
class ObservationPlacementLink:
    """Explicit producer-supplied identity link, never a geometry-based resolver.

    binding retains semantic identity, snapshot, media, ranges, rates and mapping;
    placement retains native identity/scope and track. Snapshot-local is sufficient
    only for analysis. This record grants no execution-grade qualification.
    """

    link_ref: str
    placement: NativePlacementSnapshot
    binding: PlacementTemporalBinding
    producer: ProducerRef
    source_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _refs((self.link_ref,))
        if (
            not isinstance(self.placement, NativePlacementSnapshot)
            or not isinstance(self.binding, PlacementTemporalBinding)
            or not isinstance(self.producer, ProducerRef)
        ):
            raise TypeError("Typed placement, temporal binding and producer required")
        object.__setattr__(self, "source_refs", _refs(self.source_refs))


class CoverageStatus(str, Enum):
    ANALYZED = "ANALYZED"
    PARTIALLY_ANALYZED = "PARTIALLY_ANALYZED"
    NOT_EVALUATED = "NOT_EVALUATED"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"


@dataclass(frozen=True)
class AnalysisCoverage:
    coverage_ref: str
    snapshot: NativeSnapshotRef
    link_ref: str
    object_id: TimelineObjectId
    native_object: IdentityRef
    covered_range: FrameRange
    producers: tuple[ProducerRef, ...]
    source_refs: tuple[str, ...]
    status: CoverageStatus
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _refs((self.coverage_ref, self.link_ref))
        for value, kind in (
            (self.snapshot, NativeSnapshotRef),
            (self.object_id, TimelineObjectId),
            (self.native_object, IdentityRef),
            (self.covered_range, FrameRange),
            (self.status, CoverageStatus),
        ):
            if not isinstance(value, kind):
                raise TypeError("Coverage requires typed bindings/status")
        producers = tuple(self.producers)
        if not producers or any(not isinstance(p, ProducerRef) for p in producers):
            raise ValueError("Coverage requires explicit producer provenance")
        object.__setattr__(self, "producers", producers)
        object.__setattr__(self, "source_refs", _refs(self.source_refs))
        object.__setattr__(self, "limitations", tuple(self.limitations))


class ObservationDiagnostic(str, Enum):
    NATIVE_NOT_READY = "NATIVE_NOT_READY"
    LINK_MISSING = "LINK_MISSING"
    LINK_AMBIGUOUS = "LINK_AMBIGUOUS"
    LINK_MISMATCH = "LINK_MISMATCH"
    STALE = "STALE"
    COVERAGE_MISSING = "COVERAGE_MISSING"
    COVERAGE_MISMATCH = "COVERAGE_MISMATCH"
    COVERAGE_NOT_ANALYZED = "COVERAGE_NOT_ANALYZED"
    EVIDENCE_PROVENANCE = "EVIDENCE_PROVENANCE"
    EVIDENCE_BINDING = "EVIDENCE_BINDING"
    MAPPING_NOT_EXACT = "MAPPING_NOT_EXACT"
    PROJECTION_UNSUPPORTED = "PROJECTION_UNSUPPORTED"


@dataclass(frozen=True)
class PreparedPauseSubject:
    bundle: EvidenceBundle
    mappings: tuple[TemporalMappingResult, ...] = ()
    preparation: PreparationResult | None = None
    candidate: PauseCandidate | None = None
    diagnostics: tuple[ObservationDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "mappings", tuple(self.mappings))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.preparation is not None and self.preparation.bundle != self.bundle:
            raise ValueError("Preparation must retain this subject's bundle")
        if self.candidate is not None and (
            self.preparation is None
            or self.preparation.status != PreparationStatus.READY
            or self.candidate.observation != self.preparation.observation
            or self.diagnostics
            or not self.mappings
            or any(m.status != MappingStatus.EXACT for m in self.mappings)
        ):
            raise ValueError("Candidate requires exact mapping and READY preparation")

    @property
    def observation(self) -> PauseObservation | None:
        return self.preparation.observation if self.preparation is not None else None


@dataclass(frozen=True)
class NativePausePreparation:
    """Evidence retention only; not a lifecycle or an authoritative timeline."""

    readiness: ReadinessResult
    links: tuple[ObservationPlacementLink, ...]
    coverage: AnalysisCoverage | None
    coverage_status: CoverageStatus | None
    subjects: tuple[PreparedPauseSubject, ...]
    diagnostics: tuple[ObservationDiagnostic, ...]
    projection: TimelineSnapshot | None = None

    def __post_init__(self) -> None:
        for name in ("links", "subjects", "diagnostics"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if any(s.candidate is not None for s in self.subjects) and (
            self.readiness.status != ReadinessStatus.READY
            or self.coverage_status
            not in (CoverageStatus.ANALYZED, CoverageStatus.PARTIALLY_ANALYZED)
            or self.diagnostics
            or self.projection is None
        ):
            raise ValueError("Candidates cannot bypass native readiness/coverage")


def _link_matches(native: NativeTimelineSnapshot, link: ObservationPlacementLink) -> bool:
    p, b = link.placement, link.binding
    return (
        p in native.placements
        and p.capture_id == native.capture_id
        and native.capture_id in link.source_refs
        and link.producer.evidence_contract_version == "v1"
        and b.snapshot_ref.timeline_id == native.timeline_ref.ref
        and b.snapshot_ref.timeline_version == native.timeline_version
        and b.snapshot_ref.state_token == native.state_token
        and b.media_id == p.media_ref.ref
        and b.timeline_range == p.timeline_range
        and b.source_range == p.source_range
        and b.object_id.track_id == p.track_ref
        and b.timeline_rate == p.timeline_rate == native.timeline_rate
        and b.source_rate == p.source_rate
        and b.mapping_kind == p.retime_kind
    )


def prepare_pause_candidates_from_native(
    native: NativeTimelineSnapshot,
    current_snapshot: NativeSnapshotRef,
    *,
    links: tuple[ObservationPlacementLink, ...],
    coverage: AnalysisCoverage | None,
    bundles: tuple[EvidenceBundle, ...],
) -> NativePausePreparation:
    """Compose one declared placement's zero-or-more pause subjects, without IO.

    Supply one explicit link. Multiple proposed links remain ambiguous; no first
    media/name/range match wins. Re-evaluate with a new current snapshot to expose
    staleness; immutable old outputs do not certify currentness forever.
    """
    links, bundles = tuple(links), tuple(bundles)
    if (
        any(not isinstance(x, ObservationPlacementLink) for x in links)
        or any(not isinstance(x, EvidenceBundle) for x in bundles)
        or (coverage is not None and not isinstance(coverage, AnalysisCoverage))
    ):
        raise TypeError("Typed links, coverage and evidence bundles required")
    readiness = evaluate_readiness(native, PAUSE_ANALYSIS, current_snapshot)
    D = ObservationDiagnostic
    diagnostics: list[ObservationDiagnostic] = []
    status = coverage.status if coverage is not None else None
    if readiness.status != ReadinessStatus.READY:
        diagnostics.append(D.NATIVE_NOT_READY)
    stale = (
        readiness.status == ReadinessStatus.STALE
        or any(link.binding.snapshot_ref != current_snapshot for link in links)
        or (coverage is not None and coverage.snapshot != current_snapshot)
    )
    if stale:
        status = CoverageStatus.STALE
        diagnostics.append(D.STALE)
    if len(links) != 1:
        diagnostics.append(D.LINK_MISSING if not links else D.LINK_AMBIGUOUS)
    if coverage is None:
        diagnostics.append(D.COVERAGE_MISSING)
    elif coverage.status not in (CoverageStatus.ANALYZED, CoverageStatus.PARTIALLY_ANALYZED):
        diagnostics.append(D.COVERAGE_NOT_ANALYZED)
    if len(links) == 1:
        link = links[0]
        if not _link_matches(native, link):
            diagnostics.append(D.LINK_MISMATCH)
        if coverage is not None and (
            coverage.link_ref != link.link_ref
            or coverage.object_id != link.binding.object_id
            or coverage.native_object != link.placement.object_ref
            or not link.binding.timeline_range.frames.contains(coverage.covered_range)
        ):
            diagnostics.append(D.COVERAGE_MISMATCH)
    if diagnostics:
        return NativePausePreparation(
            readiness,
            links,
            coverage,
            status,
            tuple(PreparedPauseSubject(b, diagnostics=tuple(diagnostics)) for b in bundles),
            tuple(diagnostics),
        )
    assert coverage is not None
    link = links[0]
    binding = link.binding
    subjects: list[PreparedPauseSubject] = []
    projection: TimelineSnapshot | None = None
    for bundle in bundles:
        context = bundle.context_range or bundle.target_pause_range
        issues: list[ObservationDiagnostic] = []
        if (
            bundle.timeline_id != binding.snapshot_ref.timeline_id
            or bundle.base_version != binding.snapshot_ref.timeline_version
            or bundle.target_object_id != binding.object_id
            or not coverage.covered_range.contains(context)
        ):
            issues.append(D.EVIDENCE_BINDING)
        if any(
            r.producer not in coverage.producers or r.evidence_id not in coverage.source_refs
            for r in bundle.evidence
        ):
            issues.append(D.EVIDENCE_PROVENANCE)
        ranges = (
            context,
            bundle.target_pause_range,
            *(r.binding.observed_range for r in bundle.evidence),
        )
        mappings = tuple(
            map_range(
                MappingRequest(
                    current_snapshot,
                    bundle.target_object_id,
                    binding.media_id,
                    TimelineFrameRange(interval),
                ),
                (binding,),
                current_snapshot,
            )
            for interval in ranges
        )
        if any(m.status != MappingStatus.EXACT for m in mappings):
            issues.append(D.MAPPING_NOT_EXACT)
        if binding.timeline_range.frames.duration != binding.source_range.frames.duration:
            issues.append(D.PROJECTION_UNSUPPORTED)
        if issues:
            subjects.append(PreparedPauseSubject(bundle, mappings, diagnostics=tuple(issues)))
            continue
        track = next(t for t in native.tracks if t.track_ref.ref == link.placement.track_ref)
        if projection is None:
            projection = TimelineSnapshot(
                current_snapshot.timeline_id,
                current_snapshot.timeline_version,
                (
                    Track(
                        binding.object_id.track_id,
                        (
                            Clip(
                                binding.object_id.clip_id,
                                binding.media_id,
                                binding.timeline_range.frames,
                                binding.source_range.frames,
                            ),
                        ),
                        track.track_type,
                    ),
                ),
            )
        preparation = prepare_observation(bundle, projection)
        candidate = None
        if preparation.status == PreparationStatus.READY:
            assert preparation.observation is not None
            candidate = classify_pause(preparation.observation)
        subjects.append(PreparedPauseSubject(bundle, mappings, preparation, candidate))
    return NativePausePreparation(
        readiness, links, coverage, status, tuple(subjects), (), projection
    )
