"""PRE-G2 offline contracts and metrics. No media IO, extraction or qualification.

All receipts emitted by this harness are TEST_ONLY_SUPPORT. Supplied provenance,
blindness and ledger claims are audited for consistency, never authenticated.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections.abc import Callable
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from fractions import Fraction
from itertools import pairwise
from pathlib import Path

from davinci_ai_editor.evidence import EvidenceKind
from davinci_ai_editor.native_snapshot import NativeTimelineSnapshot
from davinci_ai_editor.pause_acoustic_producer import (
    AcousticConfig,
    PcmInput,
    produce_pause_evidence,
)
from davinci_ai_editor.temporal_mapping import FrameRate, MappingKind, NativeSnapshotRef

SCHEMA = "pcm-calibration-pre-g2-v1"
BOOTSTRAP_SEED = 1001
BOOTSTRAP_REPETITIONS = 1000


class Split(str, Enum):
    CALIBRATION = "CALIBRATION"
    VALIDATION = "VALIDATION"
    HOLDOUT = "HOLDOUT"


class Stratum(str, Enum):
    QUIET_INDOOR = "QUIET_INDOOR"
    BACKGROUND_NOISE = "BACKGROUND_NOISE"
    LEVEL_VARIATION = "LEVEL_VARIATION"
    IMPULSE_MUSIC_OVERLAP = "IMPULSE_MUSIC_OVERLAP"


class Label(str, Enum):
    QUIET = "REFERENCE_ACOUSTIC_QUIET"
    ACTIVITY = "AUDIBLE_ACTIVITY"
    AMBIGUOUS = "AMBIGUOUS"
    EXCLUDED = "EXCLUDED"


class Refusal(ValueError):
    """Typed offline refusal; preserve its code in a failure receipt."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str


def _pseudo(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value))


def _sha(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _canonical(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if value is None or type(value) in (str, int, bool):
        return value
    if isinstance(value, (tuple, list)):
        return [_canonical(v) for v in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _canonical(getattr(value, f.name)) for f in fields(value)}
    raise Refusal("NON_CANONICAL_VALUE")


def digest(value: object) -> str:
    encoded = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def samples_per_frame(sample_rate: int, rate: FrameRate) -> int:
    if type(sample_rate) is not int or sample_rate <= 0:
        raise Refusal("INVALID_SAMPLE_RATE")
    k, r = divmod(sample_rate * rate.denominator, rate.numerator)
    if r or k <= 0:
        raise Refusal("NON_INTEGRAL_PROFILE")
    return k


@dataclass(frozen=True)
class Extraction:
    operator_ref: str
    tool_ref: str
    tool_version: str
    code_sha256: str
    parameters: tuple[tuple[str, str], ...]
    input_sha256: str
    output_sha256: str
    output_bytes: int
    original_reread_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", tuple(sorted(tuple(p) for p in self.parameters)))


@dataclass(frozen=True)
class AcquisitionManifest:
    asset_ref: str
    session_ref: str
    permission_ref: str
    permission_expiry: str
    retention_ref: str
    recorder_ref: str
    acquired_at: str
    original_bytes: int
    original_sha256: str
    device_app_version: str
    processing: tuple[str, ...]
    container_ref: str
    header_facts_ref: str
    stream_ref: str
    channel_order: tuple[str, ...]
    selected_channel: int
    sample_rate: int
    bit_depth: int
    signed: bool
    endianness: str
    original_sample_frames: int
    sample_start: int
    sample_end: int
    sample_origin: int
    source_origin: int
    source_start: int
    source_end: int
    source_rate: FrameRate
    origin_correspondence_ref: str
    extraction: Extraction
    independent_extraction: Extraction | None
    independent_review_ref: str
    independent_review_result: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "processing", tuple(self.processing))
        object.__setattr__(self, "channel_order", tuple(self.channel_order))


def validate_acquisition(m: AcquisitionManifest) -> tuple[Finding, ...]:
    issues: list[Finding] = []

    def fail(code: str) -> None:
        issues.append(Finding(code, m.asset_ref))

    critical = (
        m.asset_ref,
        m.session_ref,
        m.permission_ref,
        m.retention_ref,
        m.recorder_ref,
        m.origin_correspondence_ref,
        m.stream_ref,
        m.container_ref,
        m.header_facts_ref,
    )
    if any(not _pseudo(v) or v == "UNKNOWN" for v in critical):
        fail("PROVENANCE_QUARANTINE")
    timestamps: list[datetime] = []
    for timestamp in (m.acquired_at, m.permission_expiry):
        try:
            stamp = datetime.fromisoformat(timestamp)
            if stamp.utcoffset() is None:
                fail("TIMEZONE_MISSING")
            else:
                timestamps.append(stamp)
        except ValueError:
            fail("TIMESTAMP_INVALID")
    if len(timestamps) == 2 and timestamps[1] <= timestamps[0]:
        fail("PERMISSION_EXPIRED_AT_ACQUISITION")
    if not m.device_app_version or not m.processing:
        fail("PROCESSING_PROVENANCE_MISSING")
    if not _sha(m.original_sha256) or m.original_bytes <= 0:
        fail("ORIGINAL_IDENTITY_INVALID")
    channels = len(m.channel_order)
    if (
        not channels
        or len(set(m.channel_order)) != channels
        or not 0 <= m.selected_channel < channels
    ):
        fail("CHANNEL_UNCLEAR")
    if m.bit_depth != 16 or m.signed is not True or m.endianness != "LE":
        fail("PCM_FORMAT_UNSUPPORTED")
    if not 0 <= m.sample_start < m.sample_end <= m.original_sample_frames:
        fail("SAMPLE_BOUNDS_INVALID")
    try:
        k = samples_per_frame(m.sample_rate, m.source_rate)
        if (
            m.source_end <= m.source_start
            or min(m.sample_origin, m.source_origin, m.source_start) < 0
            or m.sample_start != m.sample_origin + (m.source_start - m.source_origin) * k
            or m.sample_end != m.sample_origin + (m.source_end - m.source_origin) * k
        ):
            fail("SAMPLE_ORIGIN_MISMATCH")
        if m.extraction.output_bytes != (m.source_end - m.source_start) * k * channels * 2:
            fail("BYTE_COUNT_MISMATCH")
    except Refusal as exc:
        fail(exc.code)
    first, second = m.extraction, m.independent_extraction
    if not _pseudo(m.independent_review_ref) or m.independent_review_result != "BYTE_IDENTICAL":
        fail("INDEPENDENT_REVIEW_UNQUALIFIED")
    for extraction in (first,) if second is None else (first, second):
        if (
            not _pseudo(extraction.operator_ref)
            or not extraction.tool_ref
            or not extraction.tool_version
            or not extraction.parameters
            or len(dict(extraction.parameters)) != len(extraction.parameters)
            or not all(
                _sha(x)
                for x in (
                    extraction.code_sha256,
                    extraction.input_sha256,
                    extraction.output_sha256,
                    extraction.original_reread_sha256,
                )
            )
        ):
            fail("EXTRACTION_PROVENANCE_INVALID")
        if (
            extraction.input_sha256 != m.original_sha256
            or extraction.original_reread_sha256 != m.original_sha256
        ):
            fail("ORIGINAL_CHANGED_OR_MISMATCHED")
    if second is None:
        fail("INDEPENDENT_EXTRACTION_MISSING")
    elif (
        second.operator_ref in (first.operator_ref, m.recorder_ref)
        or second.output_sha256 != first.output_sha256
        or second.output_bytes != first.output_bytes
        or second.parameters != first.parameters
    ):
        fail("INDEPENDENT_EXTRACTION_MISMATCH")
    return tuple(issues)


@dataclass(frozen=True)
class Window:
    window_ref: str
    original_sha256: str
    sample_start: int
    sample_end: int
    sample_rate: int
    selected_channel: int


@dataclass(frozen=True)
class Session:
    session_ref: str
    stratum: Stratum
    split: Split
    lineage_refs: tuple[str, ...]
    windows: tuple[Window, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "lineage_refs", tuple(sorted(self.lineage_refs)))
        object.__setattr__(self, "windows", tuple(sorted(self.windows, key=lambda w: w.window_ref)))


def validate_splits(sessions: tuple[Session, ...], *, complete: bool = True) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    seen_sessions: set[str] = set()
    seen_windows: set[str] = set()
    origins: dict[str, str] = {}
    total = Fraction(0)
    for session in sessions:
        ref = session.session_ref
        if not isinstance(session.stratum, Stratum) or not isinstance(session.split, Split):
            findings.append(Finding("SPLIT_STRATUM_INVALID", ref))
        if ref in seen_sessions or not _pseudo(ref):
            findings.append(Finding("SESSION_ID_INVALID", ref))
        seen_sessions.add(ref)
        if not session.lineage_refs or any(not _pseudo(x) for x in session.lineage_refs):
            findings.append(Finding("LINEAGE_UNDECLARED", ref))
        for origin in (*session.lineage_refs, *(w.original_sha256 for w in session.windows)):
            if origin in origins and origins[origin] != ref:
                findings.append(Finding("SESSION_LEAKAGE", ref))
            origins[origin] = ref
        if len(session.windows) > 4 or (complete and len(session.windows) != 4):
            findings.append(Finding("WINDOW_COUNT", ref))
        for i, w in enumerate(session.windows):
            if (
                not _pseudo(w.window_ref)
                or w.window_ref in seen_windows
                or not _sha(w.original_sha256)
            ):
                findings.append(Finding("WINDOW_ID_INVALID", ref))
            seen_windows.add(w.window_ref)
            if (
                w.sample_rate != 48000
                or w.selected_channel < 0
                or not 0 <= w.sample_start < w.sample_end
            ):
                findings.append(Finding("WINDOW_PROFILE_INVALID", w.window_ref))
                continue
            duration = Fraction(w.sample_end - w.sample_start, w.sample_rate)
            total += duration
            if duration != 30:
                findings.append(Finding("WINDOW_DURATION", w.window_ref))
            for other in session.windows[:i]:
                if other.original_sha256 == w.original_sha256 and max(
                    other.sample_start, w.sample_start
                ) < min(other.sample_end, w.sample_end):
                    findings.append(Finding("OVERLAPPING_WINDOWS", w.window_ref))
    if len(sessions) > 12 or len(seen_windows) > 48 or total > 24 * 60:
        findings.append(Finding("RESOURCE_CAP", "dataset"))
    if complete:
        if len(sessions) != 12:
            findings.append(Finding("INCOMPLETE_DATASET", "dataset"))
        for split in Split:
            for stratum in Stratum:
                if sum(s.split == split and s.stratum == stratum for s in sessions) != 1:
                    findings.append(
                        Finding("SPLIT_STRATUM_ALLOCATION", split.value + ":" + stratum.value)
                    )
    return tuple(findings)


@dataclass(frozen=True)
class Region:
    start: int
    end: int
    label: Label


@dataclass(frozen=True)
class Annotation:
    window_ref: str
    pcm_sha256: str
    reviewer_ref: str
    version: str
    rubric_ref: str
    blindness_ref: str
    regions: tuple[Region, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "regions", tuple(self.regions))


def validate_annotation(a: Annotation, start: int, end: int) -> tuple[Finding, ...]:
    issues: list[Finding] = []
    if any(
        not _pseudo(v)
        for v in (a.window_ref, a.reviewer_ref, a.version, a.rubric_ref, a.blindness_ref)
    ) or not _sha(a.pcm_sha256):
        issues.append(Finding("ANNOTATION_PROVENANCE", a.window_ref))
    cursor = start
    for r in a.regions:
        if (
            r.start != cursor
            or r.end <= r.start
            or r.end > end
            or r.label not in (Label.QUIET, Label.ACTIVITY, Label.AMBIGUOUS)
        ):
            issues.append(Finding("ANNOTATION_PARTITION", a.window_ref))
        cursor = r.end
    if cursor != end or not a.regions:
        issues.append(Finding("ANNOTATION_INCOMPLETE", a.window_ref))
    return tuple(issues)


@dataclass(frozen=True)
class FrameTruth:
    labels: tuple[Label, ...]
    disagreement_frames: int
    boundary_frames: int
    annotation_digests: tuple[str, str]


def derive_truth(
    a: Annotation,
    b: Annotation,
    start: int,
    end: int,
    sample_rate: int,
    rate: FrameRate,
    *,
    sample_origin: int = 0,
    exclusions: tuple[tuple[int, int], ...] = (),
) -> FrameTruth:
    if validate_annotation(a, start, end) or validate_annotation(b, start, end):
        raise Refusal("ANNOTATION_INVALID")
    if a.reviewer_ref == b.reviewer_ref or (
        a.window_ref,
        a.pcm_sha256,
        a.rubric_ref,
        a.version,
    ) != (b.window_ref, b.pcm_sha256, b.rubric_ref, b.version):
        raise Refusal("ANNOTATION_PAIR_MISMATCH")
    k = samples_per_frame(sample_rate, rate)
    if start < sample_origin or (start - sample_origin) % k or (end - start) % k:
        raise Refusal("NON_ALIGNED_ANNOTATION_WINDOW")
    if any(not start <= lo < hi <= end for lo, hi in exclusions):
        raise Refusal("EXCLUSION_BOUNDS")
    labels: list[Label] = []
    disagreement = boundary = 0
    for frame in range(start, end, k):
        if any(lo < frame + k and frame < hi for lo, hi in exclusions):
            labels.append(Label.EXCLUDED)
            continue
        votes = [
            next((r.label for r in doc.regions if r.start <= frame and frame + k <= r.end), None)
            for doc in (a, b)
        ]
        if None in votes:
            boundary += 1
        elif votes[0] != votes[1]:
            disagreement += 1
        labels.append(
            votes[0]
            if votes[0] == votes[1] and votes[0] in (Label.QUIET, Label.ACTIVITY)
            else Label.AMBIGUOUS
        )
    return FrameTruth(tuple(labels), disagreement, boundary, (digest(a), digest(b)))


@dataclass(frozen=True)
class Rates:
    precision: Fraction | None
    recall: Fraction | None
    fpr: Fraction | None
    fnr: Fraction | None


def ratio(n: int, d: int) -> Fraction | None:
    return Fraction(n, d) if d else None


@dataclass(frozen=True)
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    ambiguous: int = 0
    excluded: int = 0

    def __post_init__(self) -> None:
        if any(type(v) is not int or v < 0 for v in self.values()):
            raise Refusal("NEGATIVE_OR_NONINTEGER_COUNTS")

    def values(self) -> tuple[int, ...]:
        return self.tp, self.fp, self.fn, self.tn, self.ambiguous, self.excluded

    @property
    def rates(self) -> Rates:
        return Rates(
            ratio(self.tp, self.tp + self.fp),
            ratio(self.tp, self.tp + self.fn),
            ratio(self.fp, self.fp + self.tn),
            ratio(self.fn, self.tp + self.fn),
        )

    @property
    def ambiguous_percentage(self) -> Fraction | None:
        return ratio(100 * self.ambiguous, self.tp + self.fp + self.fn + self.tn + self.ambiguous)

    @property
    def analyzed_seconds(self) -> Fraction:
        return Fraction(sum(self.values()), 25)


def frame_counts(truth: tuple[Label, ...], predicted: tuple[bool, ...]) -> Counts:
    if (
        len(truth) != len(predicted)
        or any(type(v) is not bool for v in predicted)
        or any(not isinstance(v, Label) for v in truth)
    ):
        raise Refusal("FRAME_VECTOR_MISMATCH")
    values = [0] * 6
    for label, positive in zip(truth, predicted):
        index = (
            (0 if positive else 2)
            if label == Label.QUIET
            else (1 if positive else 3)
            if label == Label.ACTIVITY
            else 4
            if label == Label.AMBIGUOUS
            else 5
        )
        values[index] += 1
    return Counts(*values)


def sum_counts(values: tuple[Counts, ...]) -> Counts:
    return Counts(*(sum(v.values()[i] for v in values) for i in range(6)))


@dataclass(frozen=True)
class SessionScore:
    session_ref: str
    stratum: Stratum
    split: Split
    counts: Counts


def aggregate(
    rows: tuple[SessionScore, ...],
) -> tuple[Counts, Rates, tuple[tuple[Stratum, Counts], ...]]:
    if not rows or len({r.session_ref for r in rows}) != len(rows):
        raise Refusal("SESSION_SCORES_REQUIRE_UNIQUE_SESSIONS")

    def mean(name: str) -> Fraction | None:
        values = [getattr(r.counts.rates, name) for r in rows]
        return None if None in values else sum(values, Fraction(0)) / len(values)

    macro = Rates(*(mean(name) for name in ("precision", "recall", "fpr", "fnr")))
    return (
        sum_counts(tuple(r.counts for r in rows)),
        macro,
        tuple((s, sum_counts(tuple(r.counts for r in rows if r.stratum == s))) for s in Stratum),
    )


@dataclass(frozen=True)
class Interval:
    low: Fraction | None
    high: Fraction | None
    valid_repetitions: int
    total_repetitions: int


def _quantile(values: tuple[Fraction, ...], numerator: int, denominator: int) -> Fraction:
    ordered = sorted(values)
    index = max(0, (len(ordered) * numerator + denominator - 1) // denominator - 1)
    return ordered[index]


def bootstrap_sessions(rows: tuple[SessionScore, ...]) -> tuple[tuple[str, Interval], ...]:
    aggregate(rows)
    rows = tuple(sorted(rows, key=lambda r: r.session_ref))
    rng = random.Random(BOOTSTRAP_SEED)
    draws: dict[str, list[Fraction]] = {key: [] for key in ("precision", "recall", "fpr", "fnr")}
    for _ in range(BOOTSTRAP_REPETITIONS):
        counts = sum_counts(tuple(rows[rng.randrange(len(rows))].counts for _ in rows))
        for name, values in draws.items():
            value = getattr(counts.rates, name)
            if value is not None:
                values.append(value)
    return tuple(
        (
            name,
            Interval(
                _quantile(tuple(v), 25, 1000) if v else None,
                _quantile(tuple(v), 975, 1000) if v else None,
                len(v),
                BOOTSTRAP_REPETITIONS,
            ),
        )
        for name, v in draws.items()
    )


@dataclass(frozen=True)
class Event:
    event_ref: str
    start: int
    end: int


@dataclass(frozen=True)
class EventMetrics:
    tp: int
    fp: int
    fn: int
    matches: tuple[tuple[str, str], ...]
    start_errors: tuple[int, ...]
    end_errors: tuple[int, ...]
    median_absolute_error: Fraction | None
    p95_absolute_error: Fraction | None
    max_absolute_error: int | None
    split_count: int
    merge_count: int


def match_events(reference: tuple[Event, ...], predicted: tuple[Event, ...]) -> EventMetrics:
    """Exact ordered interval DP; nonoverlapping events cannot have crossing matches."""
    reference = tuple(sorted(reference, key=lambda e: (e.start, e.event_ref)))
    predicted = tuple(sorted(predicted, key=lambda e: (e.start, e.event_ref)))
    for events in (reference, predicted):
        if (
            len({e.event_ref for e in events}) != len(events)
            or any(e.start < 0 or e.end <= e.start for e in events)
            or any(a.end > b.start for a, b in pairwise(events))
        ):
            raise Refusal("EVENTS_MUST_BE_DISTINCT_NONOVERLAPPING")

    def intersection(a: Event, b: Event) -> int:
        return max(0, min(a.end, b.end) - max(a.start, b.start))

    def iou(a: Event, b: Event) -> Fraction:
        overlap = intersection(a, b)
        return Fraction(overlap, a.end - a.start + b.end - b.start - overlap)

    table: dict[tuple[int, int], tuple[Fraction, tuple[tuple[int, int], ...]]] = {}
    for i in range(len(reference), -1, -1):
        for j in range(len(predicted), -1, -1):
            if i == len(reference) or j == len(predicted):
                table[i, j] = (Fraction(0), ())
                continue
            choices = [table[i + 1, j], table[i, j + 1]]
            weight = iou(reference[i], predicted[j])
            if weight >= Fraction(1, 2):
                score, pairs = table[i + 1, j + 1]
                choices.append((weight + score, ((i, j),) + pairs))
            table[i, j] = min(choices, key=lambda item: (-item[0], item[1]))
    pairs = table[0, 0][1]
    starts = tuple(predicted[j].start - reference[i].start for i, j in pairs)
    ends = tuple(predicted[j].end - reference[i].end for i, j in pairs)
    errors = tuple(sorted(Fraction(abs(v)) for v in (*starts, *ends)))
    median = ((errors[(len(errors) - 1) // 2] + errors[len(errors) // 2]) / 2) if errors else None
    return EventMetrics(
        len(pairs),
        len(predicted) - len(pairs),
        len(reference) - len(pairs),
        tuple((reference[i].event_ref, predicted[j].event_ref) for i, j in pairs),
        starts,
        ends,
        median,
        _quantile(errors, 95, 100) if errors else None,
        int(max(errors)) if errors else None,
        sum(sum(intersection(r, p) > 0 for p in predicted) > 1 for r in reference),
        sum(sum(intersection(r, p) > 0 for r in reference) > 1 for p in predicted),
    )


def calibration_grid() -> tuple[AcousticConfig, ...]:
    return tuple(
        AcousticConfig(
            "pcm-frame-energy-v1",
            threshold,
            minimum,
            250,
            3,
            Fraction(1, 2),
            Fraction(1),
            Fraction(2),
        )
        for threshold in (0, 16, 64, 256, 1024, 4096, 16384, 65536)
        for minimum in (1, 2, 3, 5, 10)
    )


def policy_digest() -> str:
    return digest(
        (
            SCHEMA,
            calibration_grid(),
            BOOTSTRAP_SEED,
            BOOTSTRAP_REPETITIONS,
            "session-resample-percentile-nearest-rank-2.5-97.5",
            "event-iou-half-max-total-start-id",
            "ambiguous-and-excluded-not-binary-truth",
            "macro-na-if-any-session-rate-na",
            "calibration-fpr-1pct-precision-95pct-max-recall-lower-threshold-longer-run",
            "validation-holdout-recall-80pct-stratum-fpr-5pct-quiet-activity-10s-ambiguity-20pct",
        )
    )


@dataclass(frozen=True)
class Freeze:
    experiment_ref: str
    split_digest: str
    annotation_digest: str
    rubric_ref: str
    exclusion_ref: str
    policy_sha256: str
    holdout_lineages: tuple[str, ...]
    rubric_sha256: str
    exclusion_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "holdout_lineages", tuple(sorted(self.holdout_lineages)))
        if (
            not all(
                _sha(v)
                for v in (
                    self.split_digest,
                    self.annotation_digest,
                    self.policy_sha256,
                    self.rubric_sha256,
                    self.exclusion_sha256,
                )
            )
            or not all(
                _pseudo(v) for v in (self.experiment_ref, self.rubric_ref, self.exclusion_ref)
            )
            or not self.holdout_lineages
            or any(not _pseudo(v) for v in self.holdout_lineages)
        ):
            raise Refusal("FREEZE_SCHEMA_INVALID")


def freeze_inputs(
    experiment_ref: str,
    sessions: tuple[Session, ...],
    annotations: tuple[Annotation, ...],
    rubric_ref: str,
    exclusion_ref: str,
    rubric_sha256: str,
    exclusion_sha256: str,
) -> Freeze:
    if (
        validate_splits(sessions)
        or not _pseudo(experiment_ref)
        or not _pseudo(rubric_ref)
        or not _pseudo(exclusion_ref)
    ):
        raise Refusal("FREEZE_INPUTS_INVALID")
    windows = {w.window_ref: w for s in sessions for w in s.windows}
    if any(a.window_ref not in windows for a in annotations):
        raise Refusal("ANNOTATION_UNKNOWN_WINDOW")
    for ref, w in windows.items():
        pair = tuple(a for a in annotations if a.window_ref == ref)
        if (
            len(pair) != 2
            or pair[0].reviewer_ref == pair[1].reviewer_ref
            or any(
                a.rubric_ref != rubric_ref or validate_annotation(a, w.sample_start, w.sample_end)
                for a in pair
            )
        ):
            raise Refusal("FREEZE_REQUIRES_TWO_VALID_BLIND_ANNOTATIONS")
        if pair[0].pcm_sha256 != pair[1].pcm_sha256 or pair[0].version != pair[1].version:
            raise Refusal("ANNOTATION_PAIR_MISMATCH")
    return Freeze(
        experiment_ref,
        digest(tuple(sorted(sessions, key=lambda s: s.session_ref))),
        digest(tuple(sorted(annotations, key=lambda a: (a.window_ref, a.reviewer_ref)))),
        rubric_ref,
        exclusion_ref,
        policy_digest(),
        tuple(
            sorted(
                {
                    x
                    for s in sessions
                    if s.split == Split.HOLDOUT
                    for x in (
                        *s.lineage_refs,
                        s.session_ref,
                        *(w.original_sha256 for w in s.windows),
                    )
                }
            )
        ),
        rubric_sha256,
        exclusion_sha256,
    )


@dataclass(frozen=True)
class ConfigEvaluation:
    config: AcousticConfig
    split: Split
    sessions: tuple[SessionScore, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "sessions", tuple(sorted(self.sessions, key=lambda r: r.session_ref))
        )
        if any(r.split != self.split for r in self.sessions):
            raise Refusal("EVALUATION_SPLIT_MISMATCH")
        aggregate(self.sessions)

    @property
    def counts(self) -> Counts:
        return sum_counts(tuple(s.counts for s in self.sessions))


@dataclass(frozen=True)
class CalibrationReport:
    freeze_sha256: str
    evaluations: tuple[ConfigEvaluation, ...]
    selected: AcousticConfig | None
    result: str


def _eligible(counts: Counts, *, recall: bool) -> bool:
    r = counts.rates
    return (
        r.fpr is not None
        and r.precision is not None
        and r.recall is not None
        and r.fpr <= Fraction(1, 100)
        and r.precision >= Fraction(95, 100)
        and (not recall or r.recall >= Fraction(80, 100))
    )


def _experiment_scores(result: ConfigEvaluation) -> None:
    """The registered experiment has four 120-second sessions per split at 25 fps."""
    if (
        len(result.sessions) != 4
        or any(sum(r.stratum == s for r in result.sessions) != 1 for s in Stratum)
        or any(sum(r.counts.values()) != 3000 for r in result.sessions)
    ):
        raise Refusal("EXPERIMENT_SCORE_COVERAGE_MISMATCH")


def evaluate_calibration(
    freeze: Freeze, evaluator: Callable[[AcousticConfig, Split], ConfigEvaluation]
) -> CalibrationReport:
    if freeze.policy_sha256 != policy_digest():
        raise Refusal("POLICY_CHANGED_NEW_EXPERIMENT_REQUIRED")
    evaluations = tuple(evaluator(config, Split.CALIBRATION) for config in calibration_grid())
    for config, evaluation in zip(calibration_grid(), evaluations):
        _experiment_scores(evaluation)
        if evaluation.config != config or evaluation.split != Split.CALIBRATION:
            raise Refusal("CALIBRATION_EVALUATOR_MISMATCH")
    eligible = [r for r in evaluations if _eligible(r.counts, recall=False)]
    # Eligibility establishes nonzero denominator; sort by exact recall, then fixed ties.
    selected = (
        min(
            eligible,
            key=lambda r: (
                -Fraction(r.counts.tp, r.counts.tp + r.counts.fn),
                r.config.mean_square_threshold,
                -r.config.minimum_silent_frames,
            ),
        ).config
        if eligible
        else None
    )
    return CalibrationReport(
        digest(freeze), evaluations, selected, "SELECTED" if selected else "NO_ACCEPTABLE_CONFIG"
    )


def evaluate_validation(report: CalibrationReport, result: ConfigEvaluation) -> str:
    _experiment_scores(result)
    if (
        report.selected is None
        or result.config != report.selected
        or result.split != Split.VALIDATION
    ):
        raise Refusal("VALIDATION_REQUIRES_EXACT_SELECTED_CONFIG")
    return "VALIDATION_CRITERIA_MET" if _eligible(result.counts, recall=True) else "VALIDATION_FAIL"


@dataclass(frozen=True)
class HoldoutUse:
    access_ref: str
    freeze_sha256: str
    experiment_ref: str
    policy_sha256: str
    selected_config_ref: str
    lineage_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "lineage_refs", tuple(sorted(self.lineage_refs)))


def audit_holdout_use(
    use: HoldoutUse,
    freeze: Freeze,
    report: CalibrationReport,
    validation: ConfigEvaluation,
    history: tuple[HoldoutUse, ...],
) -> tuple[Finding, ...]:
    issues: list[Finding] = []
    if (
        use.freeze_sha256 != digest(freeze)
        or report.freeze_sha256 != digest(freeze)
        or use.experiment_ref != freeze.experiment_ref
        or use.policy_sha256 != policy_digest()
        or freeze.policy_sha256 != policy_digest()
        or report.selected is None
        or use.selected_config_ref != report.selected.config_ref
        or use.lineage_refs != freeze.holdout_lineages
        or not use.lineage_refs
    ):
        issues.append(Finding("HOLDOUT_FREEZE_OR_POLICY_MISMATCH", use.access_ref))
    try:
        validation_ok = evaluate_validation(report, validation) == "VALIDATION_CRITERIA_MET"
    except Refusal:
        validation_ok = False
    if not validation_ok:
        issues.append(Finding("HOLDOUT_BLOCKED_BY_VALIDATION", use.access_ref))
    if any(
        old.access_ref == use.access_ref
        or old.experiment_ref == use.experiment_ref
        or set(old.lineage_refs) & set(use.lineage_refs)
        for old in history
    ):
        issues.append(Finding("HOLDOUT_ALREADY_CONSUMED", use.access_ref))
    return tuple(issues)


def evaluate_holdout(result: ConfigEvaluation, use: HoldoutUse) -> str:
    """Metric evaluation only; audit_holdout_use must precede any data access.

    Caller must retain the attempted use even on failure. This does not provide
    a trusted ledger, cross-process lock or protection against omitted history.
    """
    _experiment_scores(result)
    if result.split != Split.HOLDOUT or result.config.config_ref != use.selected_config_ref:
        raise Refusal("HOLDOUT_CONFIG_MISMATCH")
    _, _, strata = aggregate(result.sessions)
    for _, counts in strata:
        if (
            counts.tp + counts.fn < 250
            or counts.fp + counts.tn < 250
            or counts.ambiguous_percentage is None
            or counts.ambiguous_percentage > 20
        ):
            return "INSUFFICIENT_EVIDENCE"
    if not _eligible(result.counts, recall=True):
        return "HOLDOUT_FAIL"
    if any(c.rates.fpr is None or c.rates.fpr > Fraction(5, 100) for _, c in strata):
        return "HOLDOUT_FAIL"
    return "HOLDOUT_CRITERIA_MET_NOT_QUALIFICATION"


def score_pcm_window(
    pcm: PcmInput,
    config: AcousticConfig,
    native: NativeTimelineSnapshot,
    current: NativeSnapshotRef,
    truth: tuple[Label, ...],
) -> Counts:
    """Pure supplied-buffer adapter; never opens a file or uses a separate detector."""
    if (
        pcm.sample_rate != 48000
        or pcm.link.binding.source_rate != FrameRate(25, 1)
        or pcm.link.binding.timeline_rate != FrameRate(25, 1)
        or pcm.link.binding.mapping_kind != MappingKind.IDENTITY_1X
    ):
        raise Refusal("PRIMARY_MEASURED_PROFILE_REQUIRED")
    result = produce_pause_evidence(pcm, config, native, current)
    coverage = result.preparation.coverage
    if result.diagnostics or coverage is None or result.preparation.diagnostics:
        raise Refusal("PCM_PRODUCER_REFUSED")
    ranges = tuple(
        r.binding.observed_range for r in result.records if r.kind == EvidenceKind.SILENCE_REGION
    )
    predicted = tuple(
        any(r.start <= f < r.end for r in ranges)
        for f in range(coverage.covered_range.start, coverage.covered_range.end)
    )
    return frame_counts(truth, predicted)


@dataclass(frozen=True)
class Reproduction:
    process_ref: str
    original_sha256: str
    pcm_sha256: str
    selected_channel: int
    config_ref: str
    evidence_sha256: str
    metrics_sha256: str
    selection_sha256: str


def compare_reproduction(first: Reproduction, second: Reproduction) -> tuple[Finding, ...]:
    issues = []
    for value in (first, second):
        if (
            not _pseudo(value.process_ref)
            or value.selected_channel < 0
            or not _pseudo(value.config_ref)
            or not all(
                _sha(v)
                for v in (
                    value.original_sha256,
                    value.pcm_sha256,
                    value.evidence_sha256,
                    value.metrics_sha256,
                    value.selection_sha256,
                )
            )
        ):
            issues.append(Finding("REPRODUCTION_UNQUALIFIED", value.process_ref))
    if first.process_ref == second.process_ref:
        issues.append(Finding("INDEPENDENT_PROCESS_NOT_ESTABLISHED", second.process_ref))
    for field in fields(first):
        if field.name != "process_ref" and getattr(first, field.name) != getattr(
            second, field.name
        ):
            issues.append(Finding("REPRODUCTION_MISMATCH", field.name))
    return tuple(issues)


@dataclass(frozen=True)
class GateReceipt:
    gate: str
    receipt_ref: str
    input_digests: tuple[tuple[str, str], ...]
    metrics: tuple[tuple[str, int | Fraction | None], ...]
    findings: tuple[Finding, ...]
    # No PASS or promotion output is expressible by this PRE-G2 serializer.
    qualification: str = "TEST_ONLY_SUPPORT"

    def __post_init__(self) -> None:
        if self.gate not in ("G1", "G2", "G3", "G4", "G5", "G6", "FAILURE_CASES") or not _pseudo(
            self.receipt_ref
        ):
            raise Refusal("RECEIPT_SCHEMA_INVALID")
        if self.qualification != "TEST_ONLY_SUPPORT":
            raise Refusal("QUALIFICATION_PROMOTION_FORBIDDEN")
        for name in ("input_digests", "metrics", "findings"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if len(dict(self.input_digests)) != len(self.input_digests) or len(
            dict(self.metrics)
        ) != len(self.metrics):
            raise Refusal("RECEIPT_DUPLICATE_KEY")
        if any(not _pseudo(k) or not _sha(v) for k, v in self.input_digests):
            raise Refusal("RECEIPT_DIGEST_INVALID")
        if any(
            not _pseudo(k) or (v is not None and type(v) is not int and not isinstance(v, Fraction))
            for k, v in self.metrics
        ):
            raise Refusal("RECEIPT_RAW_OR_NONNUMERIC_PAYLOAD_FORBIDDEN")
        if any(not _pseudo(i.code) or not _pseudo(i.subject) for i in self.findings):
            raise Refusal("RECEIPT_FINDING_INVALID")


def receipt_json(receipt: GateReceipt) -> str:
    return (
        json.dumps(
            {"schema": SCHEMA, "receipt": _canonical(receipt), "sha256": digest(receipt)},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def write_receipt(path: Path, receipt: GateReceipt) -> None:
    """Exclusive creation preserves failures; no overwrite/delete or media IO."""
    with path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(receipt_json(receipt))
