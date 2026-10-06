"""ADR-018 pure pause proposals over supplied evidence; never intelligence or execution."""

from dataclasses import dataclass
from enum import Enum

from .domain import FrameRange, TimelineId, TimelineObjectId, TimelineVersion


class RelativePauseBand(str, Enum):
    SHORT = "SHORT"
    NORMAL = "NORMAL"
    LONG = "LONG"
    VERY_LONG = "VERY_LONG"
    UNKNOWN = "UNKNOWN"


class PauseBoundaryKind(str, Enum):
    WITHIN_PHRASE = "WITHIN_PHRASE"
    SENTENCE_BOUNDARY = "SENTENCE_BOUNDARY"
    QUESTION_ANSWER = "QUESTION_ANSWER"
    SPEAKER_TRANSITION = "SPEAKER_TRANSITION"
    TAKE_GAP = "TAKE_GAP"
    UNKNOWN = "UNKNOWN"


class PauseSignal(str, Enum):
    NATURAL_BREATH = "NATURAL_BREATH"
    THINKING = "THINKING"
    EMOTIONAL = "EMOTIONAL"
    HESITATION = "HESITATION"
    RECORDING_DEAD_AIR = "RECORDING_DEAD_AIR"
    FAILED_TAKE_GAP = "FAILED_TAKE_GAP"
    UNKNOWN = "UNKNOWN"


class ContentMode(str, Enum):
    SPOKEN_CONTENT = "SPOKEN_CONTENT"
    UNSUPPORTED_NARRATIVE = "UNSUPPORTED_NARRATIVE"
    UNKNOWN = "UNKNOWN"


class PauseAction(str, Enum):
    KEEP = "KEEP"
    TIGHTEN = "TIGHTEN"
    REMOVE = "REMOVE"
    REVIEW = "REVIEW"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CandidateRouting(str, Enum):
    NO_CHANGE = "NO_CHANGE"
    SHADOW_ELIGIBLE = "SHADOW_ELIGIBLE"
    BATCH_REVIEW = "BATCH_REVIEW"


class DecisionReason(str, Enum):
    EXPLICIT_DEAD_AIR = "EXPLICIT_DEAD_AIR"
    FAILED_TAKE_GAP = "FAILED_TAKE_GAP"
    EMOTIONAL_CONTEXT = "EMOTIONAL_CONTEXT"
    THINKING_PAUSE = "THINKING_PAUSE"
    QUESTION_ANSWER_CONTEXT = "QUESTION_ANSWER_CONTEXT"
    SPEAKER_TRANSITION = "SPEAKER_TRANSITION"
    NATURAL_BREATH = "NATURAL_BREATH"
    HESITATION = "HESITATION"
    RELATIVELY_LONG_PAUSE = "RELATIVELY_LONG_PAUSE"
    NORMAL_LOCAL_PACING = "NORMAL_LOCAL_PACING"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    UNSUPPORTED_CONTENT_SCOPE = "UNSUPPORTED_CONTENT_SCOPE"
    NO_SAFE_TIGHTEN_TARGET = "NO_SAFE_TIGHTEN_TARGET"


@dataclass(frozen=True)
class PauseObservation:
    """Aligned caller evidence; fake placement identity, not a native binding proof."""

    timeline_id: TimelineId
    base_version: TimelineVersion
    object_id: TimelineObjectId
    pause_range: FrameRange
    relative_pause_band: RelativePauseBand
    boundary_kind: PauseBoundaryKind
    signals: tuple[PauseSignal, ...]
    local_reference_pause_frames: int | None
    content_mode: ContentMode

    def __post_init__(self) -> None:
        if not isinstance(self.timeline_id, str):
            raise TypeError("Timeline identity must be a string")
        if not self.timeline_id.strip():
            raise ValueError("Timeline identity must not be empty")
        if type(self.base_version) is not int:
            raise TypeError("Base version must be an integer")
        if self.base_version < 0:
            raise ValueError("Base version must be nonnegative")
        for value, expected in (
            (self.object_id, TimelineObjectId),
            (self.pause_range, FrameRange),
            (self.relative_pause_band, RelativePauseBand),
            (self.boundary_kind, PauseBoundaryKind),
            (self.content_mode, ContentMode),
        ):
            if not isinstance(value, expected):
                raise TypeError("Observation requires typed identity, range and context")
        signals = tuple(self.signals)
        if any(not isinstance(signal, PauseSignal) for signal in signals):
            raise TypeError("Signals require PauseSignal values")
        object.__setattr__(self, "signals", tuple(sorted(set(signals), key=lambda s: s.value)))
        if (
            self.local_reference_pause_frames is not None
            and type(self.local_reference_pause_frames) is not int
        ):
            raise TypeError("Local reference must be integer frames or None")


@dataclass(frozen=True)
class PauseCandidate:
    """Planning metadata only. No command, approval, authority or mutation capability."""

    observation: PauseObservation
    action: PauseAction
    confidence: Confidence
    reasons: tuple[DecisionReason, ...]
    suggested_retained_frames: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.observation, PauseObservation):
            raise TypeError("Candidate requires an immutable observation")
        if not isinstance(self.action, PauseAction) or not isinstance(self.confidence, Confidence):
            raise TypeError("Candidate requires typed action and confidence")
        reasons = tuple(self.reasons)
        if any(not isinstance(reason, DecisionReason) for reason in reasons):
            raise TypeError("Reasons require DecisionReason values")
        if not reasons:
            raise ValueError("Candidate requires decision reasons")
        object.__setattr__(self, "reasons", tuple(sorted(set(reasons), key=lambda r: r.value)))
        target = self.suggested_retained_frames
        if target is not None and type(target) is not int:
            raise TypeError("Retained frames must be an integer")
        if self.action == PauseAction.REMOVE and self.confidence != Confidence.HIGH:
            raise ValueError("REMOVE requires HIGH confidence")
        if self.action == PauseAction.TIGHTEN:
            if (
                self.confidence == Confidence.LOW
                or target is None
                or not 0 < target < self.observation.pause_range.duration
                or target != self.observation.local_reference_pause_frames
            ):
                raise ValueError("TIGHTEN requires a safe positive caller-supplied target")
        elif target is not None:
            raise ValueError("Only TIGHTEN may carry a retained-frame target")

    @property
    def routing_hint(self) -> CandidateRouting:
        """Shadow/review hint only, NEVER Main Apply eligibility or authority."""
        if self.confidence == Confidence.HIGH and self.action in (
            PauseAction.TIGHTEN,
            PauseAction.REMOVE,
        ):
            return CandidateRouting.SHADOW_ELIGIBLE
        if self.confidence == Confidence.MEDIUM or self.action == PauseAction.REVIEW:
            return CandidateRouting.BATCH_REVIEW
        return CandidateRouting.NO_CHANGE


_SIGNAL_REASONS = {
    PauseSignal.EMOTIONAL: DecisionReason.EMOTIONAL_CONTEXT,
    PauseSignal.THINKING: DecisionReason.THINKING_PAUSE,
    PauseSignal.NATURAL_BREATH: DecisionReason.NATURAL_BREATH,
    PauseSignal.HESITATION: DecisionReason.HESITATION,
    PauseSignal.RECORDING_DEAD_AIR: DecisionReason.EXPLICIT_DEAD_AIR,
    PauseSignal.FAILED_TAKE_GAP: DecisionReason.FAILED_TAKE_GAP,
}
_BOUNDARY_REASONS = {
    PauseBoundaryKind.QUESTION_ANSWER: DecisionReason.QUESTION_ANSWER_CONTEXT,
    PauseBoundaryKind.SPEAKER_TRANSITION: DecisionReason.SPEAKER_TRANSITION,
}


def classify_pause(observation: PauseObservation) -> PauseCandidate:
    """Deterministic conservative rules; duration only validates a supplied target."""
    if not isinstance(observation, PauseObservation):
        raise TypeError("Classifier requires PauseObservation")
    signals = set(observation.signals)
    reasons = {_SIGNAL_REASONS[s] for s in signals if s in _SIGNAL_REASONS}
    if observation.boundary_kind in _BOUNDARY_REASONS:
        reasons.add(_BOUNDARY_REASONS[observation.boundary_kind])

    def candidate(
        action: PauseAction,
        confidence: Confidence,
        extra: DecisionReason | None = None,
        target: int | None = None,
    ) -> PauseCandidate:
        evidence = reasons | ({extra} if extra else set())
        return PauseCandidate(observation, action, confidence, tuple(evidence), target)

    if observation.content_mode != ContentMode.SPOKEN_CONTENT:
        return PauseCandidate(
            observation,
            PauseAction.REVIEW,
            Confidence.LOW,
            (DecisionReason.UNSUPPORTED_CONTENT_SCOPE,),
        )
    removal = bool(signals & {PauseSignal.RECORDING_DEAD_AIR, PauseSignal.FAILED_TAKE_GAP})
    meaningful = bool(
        signals & {PauseSignal.EMOTIONAL, PauseSignal.THINKING}
        or observation.boundary_kind in _BOUNDARY_REASONS
    )
    texture = bool(signals & {PauseSignal.NATURAL_BREATH, PauseSignal.HESITATION})
    if removal and (meaningful or texture):
        return candidate(PauseAction.REVIEW, Confidence.MEDIUM, DecisionReason.CONFLICTING_EVIDENCE)
    if meaningful:
        return candidate(PauseAction.KEEP, Confidence.HIGH)
    if PauseSignal.UNKNOWN in signals:
        return candidate(PauseAction.KEEP, Confidence.LOW, DecisionReason.INSUFFICIENT_CONTEXT)
    if removal:
        return candidate(PauseAction.REMOVE, Confidence.HIGH)
    band = observation.relative_pause_band
    if band in (RelativePauseBand.SHORT, RelativePauseBand.NORMAL) and (
        PauseSignal.NATURAL_BREATH in signals
        or (not signals and observation.boundary_kind != PauseBoundaryKind.UNKNOWN)
    ):
        return candidate(PauseAction.KEEP, Confidence.HIGH, DecisionReason.NORMAL_LOCAL_PACING)
    if band in (RelativePauseBand.LONG, RelativePauseBand.VERY_LONG) and (
        texture or observation.boundary_kind != PauseBoundaryKind.UNKNOWN
    ):
        reasons.add(DecisionReason.RELATIVELY_LONG_PAUSE)
        target = observation.local_reference_pause_frames
        if target is not None and 0 < target < observation.pause_range.duration:
            return candidate(PauseAction.TIGHTEN, Confidence.MEDIUM, target=target)
        return candidate(
            PauseAction.REVIEW, Confidence.MEDIUM, DecisionReason.NO_SAFE_TIGHTEN_TARGET
        )
    return candidate(PauseAction.KEEP, Confidence.LOW, DecisionReason.INSUFFICIENT_CONTEXT)
