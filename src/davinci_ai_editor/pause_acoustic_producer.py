"""Deterministic PCM acoustic facts only: silence is not editorial meaning."""

import hashlib
import json
import struct
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from .domain import FrameRange
from .evidence import (
    EvidenceAssertion,
    EvidenceBinding,
    EvidenceBundle,
    EvidenceKind,
    EvidenceRecord,
    EvidenceStrength,
    LocalPauseReference,
    Presence,
    ProducerKind,
    ProducerRef,
)
from .native_snapshot import NativeTimelineSnapshot
from .observation_pipeline import (
    AnalysisCoverage,
    CoverageStatus,
    NativePausePreparation,
    ObservationDiagnostic,
    ObservationPlacementLink,
    prepare_pause_candidates_from_native,
)
from .pause import RelativePauseBand
from .temporal_mapping import (
    MappingRequest,
    MappingStatus,
    NativeSnapshotRef,
    SourceFrameRange,
    TemporalMappingResult,
    map_range,
)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class PcmInput:
    """Already decoded interleaved PCM; channel selection is mandatory.

    source_range refers to source frames, not sample frames. The caller owns
    acquisition/authenticity. Raw bytes never travel into the result/evidence.
    """

    data: bytes | None
    sample_format: str
    sample_rate: int
    channels: int
    selected_channel: int
    source_range: SourceFrameRange
    source_ref: str
    link: ObservationPlacementLink

    def __post_init__(self) -> None:
        if self.data is not None and not isinstance(self.data, bytes):
            raise TypeError("Immutable decoded bytes or explicit unavailable None required")
        if any(
            type(v) is not int for v in (self.sample_rate, self.channels, self.selected_channel)
        ):
            raise TypeError("Integer PCM metadata required")
        if not isinstance(self.source_range, SourceFrameRange) or not isinstance(
            self.link, ObservationPlacementLink
        ):
            raise TypeError("Typed source range and explicit analysis link required")
        if not isinstance(self.sample_format, str) or not self.source_ref.strip():
            raise ValueError("Explicit format and acquisition/source reference required")


@dataclass(frozen=True)
class AcousticConfig:
    """Explicit uncalibrated baseline. No product/editorial defaults.

    Neighborhood: absolute distance between source-frame starts, inclusive.
    Statistic: lower median of emitted neighboring pause lengths, excluding self.
    Window-edge runs remain acoustic observations but are excluded from timing.
    Band boundaries: inclusive duration/reference ratios, in ascending order.
    """

    version: str
    mean_square_threshold: int
    minimum_silent_frames: int
    neighborhood_source_frames: int
    minimum_neighbors: int
    short_ratio: Fraction
    normal_ratio: Fraction
    long_ratio: Fraction

    def __post_init__(self) -> None:
        integers = (
            self.mean_square_threshold,
            self.minimum_silent_frames,
            self.neighborhood_source_frames,
            self.minimum_neighbors,
        )
        if any(type(v) is not int for v in integers):
            raise TypeError("Integer threshold/population configuration required")
        if not 0 <= self.mean_square_threshold <= 32768**2 or any(v <= 0 for v in integers[1:]):
            raise ValueError("Invalid energy threshold, run length or population")
        ratios = (self.short_ratio, self.normal_ratio, self.long_ratio)
        if any(not isinstance(r, Fraction) for r in ratios):
            raise TypeError("Exact rational band boundaries required")
        if (
            not 0 < self.short_ratio < self.normal_ratio < self.long_ratio
            or not self.version.strip()
        ):
            raise ValueError("Explicit ordered positive ratios/version required")

    @property
    def config_ref(self) -> str:
        return "pcm-config:" + _digest(
            [
                self.version,
                self.mean_square_threshold,
                self.minimum_silent_frames,
                self.neighborhood_source_frames,
                self.minimum_neighbors,
                [
                    [r.numerator, r.denominator]
                    for r in (self.short_ratio, self.normal_ratio, self.long_ratio)
                ],
            ]
        )


class PcmDiagnostic(str, Enum):
    FORMAT_UNSUPPORTED = "FORMAT_UNSUPPORTED"
    CONFIG_UNSUPPORTED = "CONFIG_UNSUPPORTED"
    INVALID_CHANNEL = "INVALID_CHANNEL"
    INVALID_SAMPLE_RATE = "INVALID_SAMPLE_RATE"
    NON_INTEGRAL_SAMPLES_PER_FRAME = "NON_INTEGRAL_SAMPLES_PER_FRAME"
    MALFORMED_BYTES = "MALFORMED_BYTES"
    SAMPLE_COUNT_MISMATCH = "SAMPLE_COUNT_MISMATCH"
    PCM_UNAVAILABLE = "PCM_UNAVAILABLE"
    NOT_EVALUATED = "NOT_EVALUATED"
    OBS_BLOCKED = "OBS_BLOCKED"
    STALE = "STALE"
    MAPPING_NOT_EXACT = "MAPPING_NOT_EXACT"
    MAPPING_UNSUPPORTED = "MAPPING_UNSUPPORTED"
    CONTEXT_MISMATCH = "CONTEXT_MISMATCH"


@dataclass(frozen=True)
class AcousticResult:
    source_ref: str
    pcm_digest: str | None
    sample_format: str
    sample_rate: int
    channels: int
    selected_channel: int
    source_range: SourceFrameRange
    config: AcousticConfig
    producer: ProducerRef
    records: tuple[EvidenceRecord, ...]
    mappings: tuple[TemporalMappingResult, ...]
    preparation: NativePausePreparation
    diagnostics: tuple[PcmDiagnostic, ...]

    def __post_init__(self) -> None:
        for name in ("records", "mappings", "diagnostics"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


def produce_pause_evidence(
    pcm: PcmInput,
    config: AcousticConfig,
    native: NativeTimelineSnapshot,
    current_snapshot: NativeSnapshotRef,
    *,
    context: tuple[EvidenceRecord, ...] = (),
    analyze: bool = True,
) -> AcousticResult:
    """Analyze a bounded window, then delegate preparation entirely to OBS-001.

    Context records must bind exactly one detected pause's timeline range. They
    are never inferred, retargeted or spread across pauses. No context is required
    to report acoustic evidence. Partial windows remain PARTIALLY_ANALYZED.
    """
    if (
        not isinstance(pcm, PcmInput)
        or not isinstance(config, AcousticConfig)
        or type(analyze) is not bool
    ):
        raise TypeError("Typed input/config and explicit analysis switch required")
    context = tuple(context)
    if any(not isinstance(r, EvidenceRecord) for r in context):
        raise TypeError("Existing typed contextual EvidenceRecords required")
    producer = ProducerRef(ProducerKind.RULE, "local-pcm-acoustic", "v1", "v1", config.config_ref)
    b = pcm.link.binding
    pcm_digest = hashlib.sha256(pcm.data).hexdigest() if pcm.data is not None else None
    prefix = "pcm:" + _digest(
        [
            pcm.source_ref,
            pcm_digest,
            pcm.sample_format,
            pcm.sample_rate,
            pcm.channels,
            pcm.selected_channel,
            config.config_ref,
            pcm.link.link_ref,
            [
                b.snapshot_ref.timeline_id,
                b.snapshot_ref.timeline_version,
                b.snapshot_ref.state_token,
            ],
            [b.object_id.track_id, b.object_id.clip_id, b.media_id, b.mapping_ref],
            [pcm.source_range.frames.start, pcm.source_range.frames.end],
        ]
    )
    covered = b.timeline_range.frames
    coverage_meaning = (
        "Placement envelope only, not the requested window or analyzed frames; "
        "no exact requested-window mapping has been established."
    )
    mappings: list[TemporalMappingResult] = []

    def finish(
        status: CoverageStatus,
        diagnostics: tuple[PcmDiagnostic, ...] = (),
        records: tuple[EvidenceRecord, ...] = (),
        bundles: tuple[EvidenceBundle, ...] = (),
    ) -> AcousticResult:
        retained = records + tuple(r for bundle in bundles for r in bundle.evidence)
        producers = tuple(dict.fromkeys((producer, *(r.producer for r in retained))))
        coverage = AnalysisCoverage(
            prefix + ":coverage",
            b.snapshot_ref,
            pcm.link.link_ref,
            b.object_id,
            pcm.link.placement.object_ref,
            covered,
            producers,
            (pcm.source_ref, *(r.evidence_id for r in retained)),
            status,
            (
                "Acoustic threshold baseline only; no semantic inference or acquisition authentication.",
                coverage_meaning,
            ),
        )
        prepared = prepare_pause_candidates_from_native(
            native,
            current_snapshot,
            links=(pcm.link,),
            coverage=coverage,
            bundles=bundles,
        )
        return AcousticResult(
            pcm.source_ref,
            pcm_digest,
            pcm.sample_format,
            pcm.sample_rate,
            pcm.channels,
            pcm.selected_channel,
            pcm.source_range,
            config,
            producer,
            records,
            tuple(mappings),
            prepared,
            diagnostics,
        )

    # Reuse OBS's link/readiness gate, without claiming analysis before it occurs.
    probe = finish(CoverageStatus.NOT_EVALUATED)
    if any(d != ObservationDiagnostic.COVERAGE_NOT_ANALYZED for d in probe.preparation.diagnostics):
        stale = probe.preparation.coverage_status == CoverageStatus.STALE
        return finish(
            CoverageStatus.STALE if stale else CoverageStatus.NOT_EVALUATED,
            (PcmDiagnostic.STALE if stale else PcmDiagnostic.OBS_BLOCKED,),
        )

    def mapped(source: SourceFrameRange) -> TemporalMappingResult:
        result = map_range(
            MappingRequest(b.snapshot_ref, b.object_id, b.media_id, source), (b,), current_snapshot
        )
        mappings.append(result)
        return result

    window = mapped(pcm.source_range)
    if window.status != MappingStatus.EXACT or window.timeline_range is None:
        return finish(CoverageStatus.UNAVAILABLE, (PcmDiagnostic.MAPPING_NOT_EXACT,))
    covered = window.timeline_range.frames
    coverage_meaning = (
        "Exact mapped requested PCM window; unavailable/not-evaluated status "
        "does not claim these frames were analyzed."
    )
    if not analyze:
        return finish(CoverageStatus.NOT_EVALUATED, (PcmDiagnostic.NOT_EVALUATED,))
    if pcm.data is None:
        return finish(CoverageStatus.UNAVAILABLE, (PcmDiagnostic.PCM_UNAVAILABLE,))

    issue = None
    if config.version != "pcm-frame-energy-v1":
        issue = PcmDiagnostic.CONFIG_UNSUPPORTED
    elif pcm.sample_format != "PCM16LE":
        issue = PcmDiagnostic.FORMAT_UNSUPPORTED
    elif pcm.channels <= 0 or not 0 <= pcm.selected_channel < pcm.channels:
        issue = PcmDiagnostic.INVALID_CHANNEL
    elif pcm.sample_rate <= 0:
        issue = PcmDiagnostic.INVALID_SAMPLE_RATE
    if issue is not None:
        return finish(CoverageStatus.UNAVAILABLE, (issue,))
    samples_per_frame, remainder = divmod(
        pcm.sample_rate * b.source_rate.denominator, b.source_rate.numerator
    )
    if remainder or samples_per_frame <= 0:
        return finish(CoverageStatus.UNAVAILABLE, (PcmDiagnostic.NON_INTEGRAL_SAMPLES_PER_FRAME,))
    if len(pcm.data) % (2 * pcm.channels):
        return finish(CoverageStatus.UNAVAILABLE, (PcmDiagnostic.MALFORMED_BYTES,))
    if len(pcm.data) != pcm.source_range.frames.duration * samples_per_frame * pcm.channels * 2:
        return finish(CoverageStatus.UNAVAILABLE, (PcmDiagnostic.SAMPLE_COUNT_MISMATCH,))

    if b.timeline_range.frames.duration != b.source_range.frames.duration:
        return finish(CoverageStatus.UNAVAILABLE, (PcmDiagnostic.MAPPING_UNSUPPORTED,))

    regions: list[FrameRange] = []
    start: int | None = None
    span = pcm.source_range.frames
    for index in range(span.duration + 1):
        silent = False
        if index < span.duration:
            energy = sum(
                struct.unpack_from(
                    "<h",
                    pcm.data,
                    ((index * samples_per_frame + sample) * pcm.channels + pcm.selected_channel)
                    * 2,
                )[0]
                ** 2
                for sample in range(samples_per_frame)
            )
            silent = energy <= config.mean_square_threshold * samples_per_frame
        if silent and start is None:
            start = index
        elif not silent and start is not None:
            if index - start >= config.minimum_silent_frames:
                regions.append(FrameRange(span.start + start, span.start + index))
            start = None
    timeline: list[FrameRange] = []
    for region in regions:
        result = mapped(SourceFrameRange(region))
        if result.status != MappingStatus.EXACT or result.timeline_range is None:
            return finish(CoverageStatus.UNAVAILABLE, (PcmDiagnostic.MAPPING_NOT_EXACT,))
        timeline.append(result.timeline_range.frames)

    all_records: list[EvidenceRecord] = []
    groups: list[tuple[EvidenceRecord, ...]] = []
    silence_ids = [f"{prefix}:{r.start}:{r.end}:silence" for r in regions]
    for index, interval in enumerate(timeline):
        binding = EvidenceBinding(
            b.snapshot_ref.timeline_id, b.snapshot_ref.timeline_version, b.object_id, interval
        )
        records = [
            EvidenceRecord(
                silence_ids[index],
                binding,
                producer,
                EvidenceKind.SILENCE_REGION,
                EvidenceAssertion.PRESENT,
                EvidenceStrength.MODERATE,
                Presence(),
            )
        ]
        neighbors = [
            j
            for j, r in enumerate(regions)
            if j != index
            and span.start < r.start
            and r.end < span.end
            and abs(r.start - regions[index].start) <= config.neighborhood_source_frames
        ]
        enclosed = span.start < regions[index].start and regions[index].end < span.end
        if enclosed and len(neighbors) >= config.minimum_neighbors:
            lengths = sorted(timeline[j].duration for j in neighbors)
            reference = lengths[(len(lengths) - 1) // 2]
            band = RelativePauseBand.VERY_LONG
            for limit, value in (
                (config.short_ratio, RelativePauseBand.SHORT),
                (config.normal_ratio, RelativePauseBand.NORMAL),
                (config.long_ratio, RelativePauseBand.LONG),
            ):
                if interval.duration * limit.denominator <= reference * limit.numerator:
                    band = value
                    break
            note = json.dumps(
                {
                    "rule": "lower-median-excluding-self",
                    "neighbors": [silence_ids[j] for j in neighbors],
                },
                sort_keys=True,
            )
            records.append(
                EvidenceRecord(
                    silence_ids[index] + ":band",
                    binding,
                    producer,
                    EvidenceKind.RELATIVE_PAUSE_BAND,
                    EvidenceAssertion.PRESENT,
                    EvidenceStrength.MODERATE,
                    band,
                    note,
                )
            )
            if 0 < reference < interval.duration:
                records.append(
                    EvidenceRecord(
                        silence_ids[index] + ":reference",
                        binding,
                        producer,
                        EvidenceKind.LOCAL_PAUSE_REFERENCE,
                        EvidenceAssertion.PRESENT,
                        EvidenceStrength.MODERATE,
                        LocalPauseReference(reference),
                        note,
                    )
                )
        groups.append(tuple(records))
        all_records.extend(records)
    status = (
        CoverageStatus.ANALYZED
        if pcm.source_range == b.source_range
        else CoverageStatus.PARTIALLY_ANALYZED
    )
    records_tuple = tuple(all_records)
    ids = [r.evidence_id for r in (*records_tuple, *context)]
    if len(ids) != len(set(ids)) or any(
        r.binding.timeline_id != b.snapshot_ref.timeline_id
        or r.binding.base_version != b.snapshot_ref.timeline_version
        or r.binding.object_id != b.object_id
        or r.binding.observed_range not in timeline
        for r in context
    ):
        return finish(status, (PcmDiagnostic.CONTEXT_MISMATCH,), records_tuple)
    bundles = tuple(
        EvidenceBundle(
            f"{prefix}:subject:{index}",
            b.snapshot_ref.timeline_id,
            b.snapshot_ref.timeline_version,
            b.object_id,
            interval,
            group + tuple(r for r in context if r.binding.observed_range == interval),
            "v1",
        )
        for index, (interval, group) in enumerate(zip(timeline, groups))
    )
    return finish(status, records=records_tuple, bundles=bundles)
