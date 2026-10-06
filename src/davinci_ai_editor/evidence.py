"""ADR-020 descriptive evidence; no intelligence, editorial decision or execution."""

from dataclasses import dataclass
from enum import Enum
from itertools import combinations

from .domain import FrameRange, TimelineId, TimelineObjectId, TimelineSnapshot, TimelineVersion
from .pause import ContentMode, PauseBoundaryKind, PauseObservation, PauseSignal, RelativePauseBand

CONTRACT_VERSION = "v1"


class ProducerKind(str, Enum):
    HUMAN_SUPPLIED = "HUMAN_SUPPLIED"
    VAD = "VAD"
    STT = "STT"
    DIARIZATION = "DIARIZATION"
    PROSODY = "PROSODY"
    SEMANTIC = "SEMANTIC"
    TIMELINE_ADAPTER = "TIMELINE_ADAPTER"
    RULE = "RULE"


class EvidenceAssertion(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


class EvidenceStrength(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    UNKNOWN = "UNKNOWN"


class EvidenceKind(str, Enum):
    SILENCE_REGION = "SILENCE_REGION"
    SPEECH_REGION = "SPEECH_REGION"
    TRANSCRIPT_BOUNDARY = "TRANSCRIPT_BOUNDARY"
    QUESTION_ANSWER_BOUNDARY = "QUESTION_ANSWER_BOUNDARY"
    SPEAKER_CHANGE = "SPEAKER_CHANGE"
    SPEAKER_OVERLAP = "SPEAKER_OVERLAP"
    NATURAL_BREATH_CUE = "NATURAL_BREATH_CUE"
    HESITATION_CUE = "HESITATION_CUE"
    THINKING_CUE = "THINKING_CUE"
    EMOTIONAL_CUE = "EMOTIONAL_CUE"
    RECORDING_DEAD_AIR_CUE = "RECORDING_DEAD_AIR_CUE"
    FAILED_TAKE_GAP_CUE = "FAILED_TAKE_GAP_CUE"
    RELATIVE_PAUSE_BAND = "RELATIVE_PAUSE_BAND"
    LOCAL_PAUSE_REFERENCE = "LOCAL_PAUSE_REFERENCE"
    CONTENT_MODE = "CONTENT_MODE"


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Identity/version must be a nonempty string")


def _version(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("Snapshot version must be a nonnegative integer")


@dataclass(frozen=True)
class ProducerRef:
    producer_kind: ProducerKind
    producer_name: str
    producer_version: str
    evidence_contract_version: str
    producer_config_ref: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.producer_kind, ProducerKind):
            raise TypeError("Producer kind must be typed")
        for value in (self.producer_name, self.producer_version, self.evidence_contract_version):
            _text(value)
        if self.producer_config_ref is not None:
            _text(self.producer_config_ref)


@dataclass(frozen=True)
class EvidenceBinding:
    """Already-aligned fake placement binding; not proof of native correspondence."""

    timeline_id: TimelineId
    base_version: TimelineVersion
    object_id: TimelineObjectId
    observed_range: FrameRange

    def __post_init__(self) -> None:
        _text(self.timeline_id)
        _version(self.base_version)
        if not isinstance(self.object_id, TimelineObjectId) or not isinstance(
            self.observed_range, FrameRange
        ):
            raise TypeError("Binding requires typed placement and aligned range")


@dataclass(frozen=True)
class Presence:
    """Marker: semantic cue/region is specified by EvidenceKind, never inferred."""


@dataclass(frozen=True)
class LocalPauseReference:
    frames: int

    def __post_init__(self) -> None:
        if type(self.frames) is not int:
            raise TypeError("Local reference requires integer frames")
        if self.frames <= 0:
            raise ValueError("Local reference requires positive frames")


EvidencePayload = (
    Presence | LocalPauseReference | PauseBoundaryKind | RelativePauseBand | ContentMode
)
_BOUNDARIES = frozenset(
    (
        EvidenceKind.TRANSCRIPT_BOUNDARY,
        EvidenceKind.QUESTION_ANSWER_BOUNDARY,
        EvidenceKind.SPEAKER_CHANGE,
    )
)
_CUES = {
    EvidenceKind.NATURAL_BREATH_CUE: PauseSignal.NATURAL_BREATH,
    EvidenceKind.HESITATION_CUE: PauseSignal.HESITATION,
    EvidenceKind.THINKING_CUE: PauseSignal.THINKING,
    EvidenceKind.EMOTIONAL_CUE: PauseSignal.EMOTIONAL,
    EvidenceKind.RECORDING_DEAD_AIR_CUE: PauseSignal.RECORDING_DEAD_AIR,
    EvidenceKind.FAILED_TAKE_GAP_CUE: PauseSignal.FAILED_TAKE_GAP,
}
_REMOVAL = frozenset((EvidenceKind.RECORDING_DEAD_AIR_CUE, EvidenceKind.FAILED_TAKE_GAP_CUE))
_PRESERVE = frozenset(_CUES) - _REMOVAL


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    binding: EvidenceBinding
    producer: ProducerRef
    kind: EvidenceKind
    assertion: EvidenceAssertion
    strength: EvidenceStrength
    payload: EvidencePayload
    note: str | None = None

    def __post_init__(self) -> None:
        _text(self.evidence_id)
        for value, expected in (
            (self.binding, EvidenceBinding),
            (self.producer, ProducerRef),
            (self.kind, EvidenceKind),
            (self.assertion, EvidenceAssertion),
            (self.strength, EvidenceStrength),
        ):
            if not isinstance(value, expected):
                raise TypeError("Evidence fields require their declared types")
        expected_payload: type[EvidencePayload] = Presence
        if self.kind in _BOUNDARIES:
            expected_payload = PauseBoundaryKind
        elif self.kind == EvidenceKind.RELATIVE_PAUSE_BAND:
            expected_payload = RelativePauseBand
        elif self.kind == EvidenceKind.CONTENT_MODE:
            expected_payload = ContentMode
        elif self.kind == EvidenceKind.LOCAL_PAUSE_REFERENCE:
            expected_payload = LocalPauseReference
        if not isinstance(self.payload, expected_payload):
            raise TypeError("Payload does not match evidence kind")
        if (
            self.kind == EvidenceKind.QUESTION_ANSWER_BOUNDARY
            and self.payload != PauseBoundaryKind.QUESTION_ANSWER
        ):
            raise ValueError("Question/answer kind requires its explicit boundary")
        if (
            self.kind == EvidenceKind.SPEAKER_CHANGE
            and self.payload != PauseBoundaryKind.SPEAKER_TRANSITION
        ):
            raise ValueError("Speaker change requires its explicit boundary")
        if self.note is not None and not isinstance(self.note, str):
            raise TypeError("Note must be nonauthoritative text")


@dataclass(frozen=True)
class EvidenceBundle:
    bundle_id: str
    timeline_id: TimelineId
    base_version: TimelineVersion
    target_object_id: TimelineObjectId
    target_pause_range: FrameRange
    evidence: tuple[EvidenceRecord, ...]
    evidence_contract_version: str
    context_range: FrameRange | None = None

    def __post_init__(self) -> None:
        _text(self.bundle_id)
        _text(self.evidence_contract_version)
        EvidenceBinding(
            self.timeline_id, self.base_version, self.target_object_id, self.target_pause_range
        )
        context = self.context_range or self.target_pause_range
        if not isinstance(context, FrameRange):
            raise TypeError("Context must be an aligned FrameRange")
        if not context.contains(self.target_pause_range):
            raise ValueError("Context must contain the target pause")
        records = tuple(self.evidence)
        if any(not isinstance(r, EvidenceRecord) for r in records):
            raise TypeError("Bundle requires typed immutable evidence records")
        if len({r.evidence_id for r in records}) != len(records):
            raise ValueError("Duplicate evidence identity")
        for record in records:
            binding = record.binding
            if (binding.timeline_id, binding.base_version, binding.object_id) != (
                self.timeline_id,
                self.base_version,
                self.target_object_id,
            ):
                raise ValueError("Mixed timeline/version/placement binding")
            if not context.contains(binding.observed_range):
                raise ValueError("Evidence is outside declared target/context")
        object.__setattr__(self, "evidence", tuple(sorted(records, key=lambda r: r.evidence_id)))


class PreparationStatus(str, Enum):
    READY = "READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    STALE = "STALE"
    UNSUPPORTED = "UNSUPPORTED"


class PreparationReason(str, Enum):
    CONSISTENT_EVIDENCE = "CONSISTENT_EVIDENCE"
    STALE_SNAPSHOT = "STALE_SNAPSHOT"
    TIMELINE_MISMATCH = "TIMELINE_MISMATCH"
    UNSUPPORTED_CONTRACT = "UNSUPPORTED_CONTRACT"
    UNSUPPORTED_PLACEMENT = "UNSUPPORTED_PLACEMENT"
    UNSUPPORTED_CONTENT = "UNSUPPORTED_CONTENT"
    MISSING_REQUIRED_VALUE = "MISSING_REQUIRED_VALUE"
    UNKNOWN_EVIDENCE = "UNKNOWN_EVIDENCE"
    CONFLICTING_VALUES = "CONFLICTING_VALUES"
    CONTRADICTORY_ASSERTIONS = "CONTRADICTORY_ASSERTIONS"
    SEMANTIC_CONFLICT = "SEMANTIC_CONFLICT"
    SPEAKER_OVERLAP = "SPEAKER_OVERLAP"
    UNSAFE_LOCAL_REFERENCE = "UNSAFE_LOCAL_REFERENCE"


@dataclass(frozen=True)
class EvidenceConflict:
    reason: PreparationReason
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.reason, PreparationReason):
            raise TypeError("Conflict reason must be typed")
        ids = tuple(self.evidence_ids)
        for value in ids:
            _text(value)
        if len(set(ids)) < 2:
            raise ValueError("Conflict requires at least two evidence IDs")
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(ids))))


@dataclass(frozen=True)
class PreparationResult:
    bundle: EvidenceBundle
    status: PreparationStatus
    reasons: tuple[PreparationReason, ...]
    conflicts: tuple[EvidenceConflict, ...] = ()
    observation: PauseObservation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.bundle, EvidenceBundle) or not isinstance(
            self.status, PreparationStatus
        ):
            raise TypeError("Result requires typed bundle and status")
        reasons, conflicts = tuple(self.reasons), tuple(self.conflicts)
        if not reasons or any(not isinstance(r, PreparationReason) for r in reasons):
            raise ValueError("Result requires typed reasons")
        if any(not isinstance(c, EvidenceConflict) for c in conflicts):
            raise TypeError("Result conflicts must be typed")
        ids = {r.evidence_id for r in self.bundle.evidence}
        if any(not set(c.evidence_ids) <= ids for c in conflicts):
            raise ValueError("Conflict must reference bundle evidence")
        if (self.status == PreparationStatus.READY) != (self.observation is not None):
            raise ValueError("Only READY contains an observation")
        if self.status == PreparationStatus.READY and conflicts:
            raise ValueError("Conflicts cannot be READY")
        if self.observation is not None:
            o, b = self.observation, self.bundle
            if not isinstance(o, PauseObservation):
                raise TypeError("Observation must be typed")
            if (o.timeline_id, o.base_version, o.object_id, o.pause_range) != (
                b.timeline_id,
                b.base_version,
                b.target_object_id,
                b.target_pause_range,
            ):
                raise ValueError("Prepared observation must retain original binding")
        object.__setattr__(self, "reasons", tuple(sorted(set(reasons), key=lambda r: r.value)))
        object.__setattr__(
            self,
            "conflicts",
            tuple(sorted(set(conflicts), key=lambda c: (c.reason.value, c.evidence_ids))),
        )


def _preserves(record: EvidenceRecord) -> bool:
    return record.kind in _PRESERVE or (
        record.kind in _BOUNDARIES
        and record.payload
        in (PauseBoundaryKind.QUESTION_ANSWER, PauseBoundaryKind.SPEAKER_TRANSITION)
    )


def _conflicts(bundle: EvidenceBundle) -> tuple[EvidenceConflict, ...]:
    conflicts = []
    for left, right in combinations(bundle.evidence, 2):
        same_value_axis = left.kind == right.kind or (
            left.kind in _BOUNDARIES and right.kind in _BOUNDARIES
        )
        both_present = left.assertion == right.assertion == EvidenceAssertion.PRESENT
        reason = None
        if (
            same_value_axis
            and left.payload == right.payload
            and {left.assertion, right.assertion}
            == {EvidenceAssertion.PRESENT, EvidenceAssertion.ABSENT}
        ):
            reason = PreparationReason.CONTRADICTORY_ASSERTIONS
        elif both_present:
            if same_value_axis and left.payload != right.payload:
                reason = PreparationReason.CONFLICTING_VALUES
            elif (_preserves(left) and right.kind in _REMOVAL) or (
                _preserves(right) and left.kind in _REMOVAL
            ):
                reason = PreparationReason.SEMANTIC_CONFLICT
            elif {left.kind, right.kind} == {
                EvidenceKind.SILENCE_REGION,
                EvidenceKind.SPEECH_REGION,
            } and left.binding.observed_range.overlaps(right.binding.observed_range):
                reason = PreparationReason.CONTRADICTORY_ASSERTIONS
        if reason is not None:
            conflicts.append(EvidenceConflict(reason, (left.evidence_id, right.evidence_id)))
    return tuple(conflicts)


def prepare_observation(
    bundle: EvidenceBundle, current_snapshot: TimelineSnapshot
) -> PreparationResult:
    """Read supplied aligned evidence/snapshot only; never infer or execute an edit."""
    if not isinstance(bundle, EvidenceBundle) or not isinstance(current_snapshot, TimelineSnapshot):
        raise TypeError("Preparation requires immutable bundle and current snapshot")
    conflicts = _conflicts(bundle)
    reasons = {c.reason for c in conflicts}
    unsupported = False
    if bundle.timeline_id != current_snapshot.timeline_id:
        reasons.add(PreparationReason.TIMELINE_MISMATCH)
        unsupported = True
    stale = bundle.base_version != current_snapshot.version
    if stale:
        reasons.add(PreparationReason.STALE_SNAPSHOT)
    if bundle.evidence_contract_version != CONTRACT_VERSION or any(
        r.producer.evidence_contract_version != CONTRACT_VERSION for r in bundle.evidence
    ):
        reasons.add(PreparationReason.UNSUPPORTED_CONTRACT)
        unsupported = True
    scope = bundle.context_range or bundle.target_pause_range
    matches = [
        clip
        for track in current_snapshot.tracks
        if track.track_id == bundle.target_object_id.track_id
        for clip in track.clips
        if clip.clip_id == bundle.target_object_id.clip_id and clip.timeline_range.contains(scope)
    ]
    if len(matches) != 1:
        reasons.add(PreparationReason.UNSUPPORTED_PLACEMENT)
        unsupported = True
    present = [r for r in bundle.evidence if r.assertion == EvidenceAssertion.PRESENT]
    if any(r.assertion == EvidenceAssertion.UNKNOWN for r in bundle.evidence):
        reasons.add(PreparationReason.UNKNOWN_EVIDENCE)
    bands = {r.payload for r in present if isinstance(r.payload, RelativePauseBand)}
    boundaries = {r.payload for r in present if isinstance(r.payload, PauseBoundaryKind)}
    modes = {r.payload for r in present if isinstance(r.payload, ContentMode)}
    references = {r.payload.frames for r in present if isinstance(r.payload, LocalPauseReference)}
    if not bands or not boundaries or not modes:
        reasons.add(PreparationReason.MISSING_REQUIRED_VALUE)
    if RelativePauseBand.UNKNOWN in bands or PauseBoundaryKind.UNKNOWN in boundaries:
        reasons.add(PreparationReason.UNKNOWN_EVIDENCE)
    if modes and modes != {ContentMode.SPOKEN_CONTENT}:
        reasons.add(PreparationReason.UNSUPPORTED_CONTENT)
        # Conflicting content values are a reviewable conflict, not a winning mode.
        unsupported = unsupported or len(modes) == 1
    if any(r.kind == EvidenceKind.SPEAKER_OVERLAP for r in present):
        reasons.add(PreparationReason.SPEAKER_OVERLAP)
    if any(not 0 < n < bundle.target_pause_range.duration for n in references):
        reasons.add(PreparationReason.UNSAFE_LOCAL_REFERENCE)
    if reasons:
        status = (
            PreparationStatus.UNSUPPORTED
            if unsupported
            else PreparationStatus.STALE
            if stale
            else PreparationStatus.REVIEW_REQUIRED
        )
        return PreparationResult(bundle, status, tuple(reasons), conflicts)
    observation = PauseObservation(
        bundle.timeline_id,
        bundle.base_version,
        bundle.target_object_id,
        bundle.target_pause_range,
        next(iter(bands)),
        next(iter(boundaries)),
        tuple(_CUES[r.kind] for r in present if r.kind in _CUES),
        next(iter(references), None),
        next(iter(modes)),
    )
    return PreparationResult(
        bundle,
        PreparationStatus.READY,
        (PreparationReason.CONSISTENT_EVIDENCE,),
        observation=observation,
    )
