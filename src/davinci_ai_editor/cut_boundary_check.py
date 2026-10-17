"""LLM-001: advisory boundary check for a proposed removal against word timings.

Given a removed source-frame range ``[start, end)`` and a transcript snapshot,
report how the two cut edges relate to the surrounding words. This is ADVISORY
ONLY: it never clamps, snaps, widens or narrows the range, and it never marks a
cut safe or approved. :class:`SnapSuggestion` values are reported for a human
reviewer (or a later deterministic geometry step) and are never applied here.

Cut heuristics (never cut inside a word, keep padding around retained words,
classify the silence a cut lands in as clean/review/unsafe) follow the public
MIT-licensed ``video-use`` skill notes and the "report every move" stance of
``video-agent``'s snapping; no code was copied and no media is touched.

Transcript timings carry ``snapshot.timing_tolerance_frames`` of uncertainty, so
an edge within that tolerance of a word edge is a REVIEW finding, not clean.
Untimed words never get invented ranges; when one sits next to an edge the
result is ``TIMING_UNKNOWN``.
"""

from dataclasses import dataclass
from enum import Enum

from .domain import FrameRange
from .transcript import TranscriptSnapshot, TranscriptTokenKind, TranscriptWord


class BoundaryFindingCode(str, Enum):
    CUTS_INSIDE_WORD = "CUTS_INSIDE_WORD"
    AUDIO_EVENT_TRUNCATED = "AUDIO_EVENT_TRUNCATED"
    PADDING_BELOW_MIN = "PADDING_BELOW_MIN"
    NEAR_WORD_EDGE_WITHIN_TOLERANCE = "NEAR_WORD_EDGE_WITHIN_TOLERANCE"
    GAP_UNSAFE = "GAP_UNSAFE"
    GAP_REVIEW = "GAP_REVIEW"
    SPEAKER_HANDOFF_TIGHT = "SPEAKER_HANDOFF_TIGHT"
    TIMING_UNKNOWN = "TIMING_UNKNOWN"
    UNKNOWN = "UNKNOWN"


class FindingSeverity(str, Enum):
    UNSAFE = "UNSAFE"
    REVIEW = "REVIEW"
    UNKNOWN = "UNKNOWN"


class CutEdge(str, Enum):
    START = "START"
    END = "END"
    JOIN = "JOIN"
    UNKNOWN = "UNKNOWN"


_SEVERITY = {
    BoundaryFindingCode.CUTS_INSIDE_WORD: FindingSeverity.UNSAFE,
    BoundaryFindingCode.AUDIO_EVENT_TRUNCATED: FindingSeverity.UNSAFE,
    BoundaryFindingCode.GAP_UNSAFE: FindingSeverity.UNSAFE,
    BoundaryFindingCode.PADDING_BELOW_MIN: FindingSeverity.REVIEW,
    BoundaryFindingCode.NEAR_WORD_EDGE_WITHIN_TOLERANCE: FindingSeverity.REVIEW,
    BoundaryFindingCode.GAP_REVIEW: FindingSeverity.REVIEW,
    BoundaryFindingCode.SPEAKER_HANDOFF_TIGHT: FindingSeverity.REVIEW,
    BoundaryFindingCode.TIMING_UNKNOWN: FindingSeverity.REVIEW,
}
_EDGE_ORDER = {CutEdge.START: 0, CutEdge.END: 1, CutEdge.JOIN: 2}
_CODE_ORDER = {code: i for i, code in enumerate(BoundaryFindingCode)}


def _nonneg(value: object, message: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(message)
    return value


@dataclass(frozen=True)
class BoundaryPolicy:
    """Frame thresholds. Silence ``< unsafe_gap`` is unsafe, ``< review_gap`` review."""

    min_padding_frames: int
    unsafe_gap_frames: int
    review_gap_frames: int

    def __post_init__(self) -> None:
        _nonneg(self.min_padding_frames, "Nonnegative integer padding required")
        _nonneg(self.unsafe_gap_frames, "Nonnegative integer unsafe gap required")
        _nonneg(self.review_gap_frames, "Nonnegative integer review gap required")
        if self.unsafe_gap_frames > self.review_gap_frames:
            raise ValueError("Unsafe gap threshold cannot exceed review gap threshold")


@dataclass(frozen=True)
class SnapSuggestion:
    """A reported, never-applied edge move. ``within_tolerance`` compares |delta|
    with the snapshot's timing tolerance."""

    from_frame: int
    to_frame: int
    delta: int
    within_tolerance: bool

    def __post_init__(self) -> None:
        _nonneg(self.from_frame, "Nonnegative integer frame required")
        _nonneg(self.to_frame, "Nonnegative integer frame required")
        if type(self.delta) is not int or self.delta != self.to_frame - self.from_frame:
            raise ValueError("Delta must equal to_frame - from_frame")
        if self.delta == 0:
            raise ValueError("A suggestion must move the edge")
        if type(self.within_tolerance) is not bool:
            raise TypeError("Explicit boolean tolerance flag required")


@dataclass(frozen=True)
class BoundaryFinding:
    code: BoundaryFindingCode
    severity: FindingSeverity
    edge: CutEdge
    frame: int
    word_ref: str | None
    distance_frames: int | None
    detail: str
    suggestion: SnapSuggestion | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, BoundaryFindingCode) or self.code not in _SEVERITY:
            raise ValueError("Known finding code required")
        if self.severity is not _SEVERITY[self.code]:
            raise ValueError("Severity is fixed by the finding code")
        if not isinstance(self.edge, CutEdge) or self.edge is CutEdge.UNKNOWN:
            raise ValueError("Known cut edge required")
        _nonneg(self.frame, "Nonnegative integer frame required")
        if self.word_ref is not None and (
            not isinstance(self.word_ref, str) or not self.word_ref.strip()
        ):
            raise ValueError("Word reference must be nonblank when present")
        if self.distance_frames is not None:
            _nonneg(self.distance_frames, "Nonnegative integer distance required")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("Nonblank detail required")
        if self.suggestion is not None and not isinstance(self.suggestion, SnapSuggestion):
            raise TypeError("Typed snap suggestion required")


def _frames(word: TranscriptWord) -> FrameRange:
    assert word.source_range is not None
    return word.source_range.frames


class _Checker:
    def __init__(
        self, removal: FrameRange, snapshot: TranscriptSnapshot, policy: BoundaryPolicy
    ) -> None:
        self.removal = removal
        self.snapshot = snapshot
        self.policy = policy
        self.tol = snapshot.timing_tolerance_frames
        self.findings: list[BoundaryFinding] = []

    def add(
        self,
        code: BoundaryFindingCode,
        edge: CutEdge,
        frame: int,
        word: TranscriptWord | None,
        distance: int | None,
        detail: str,
        to_frame: int | None = None,
    ) -> None:
        suggestion = None
        if to_frame is not None and to_frame != frame and to_frame >= 0:
            delta = to_frame - frame
            suggestion = SnapSuggestion(frame, to_frame, delta, abs(delta) <= self.tol)
        self.findings.append(
            BoundaryFinding(
                code,
                _SEVERITY[code],
                edge,
                frame,
                None if word is None else word.word_ref,
                distance,
                detail,
                suggestion,
            )
        )

    def neighbours(self, frame: int) -> tuple[int | None, int | None, TranscriptWord | None]:
        """Indices (in snapshot.words) of the nearest timed word ending at/before
        ``frame`` and starting at/after it, plus a word strictly containing it."""

        before: int | None = None
        after: int | None = None
        for i, word in enumerate(self.snapshot.words):
            if word.source_range is None:
                continue
            r = word.source_range.frames
            if r.start < frame < r.end:
                return None, None, word
            if r.end <= frame:
                before = i
            elif after is None and r.start >= frame:
                after = i
        return before, after, None

    def untimed_between(self, lo: int | None, hi: int | None) -> TranscriptWord | None:
        words = self.snapshot.words
        start = -1 if lo is None else lo
        stop = len(words) if hi is None else hi
        for word in words[start + 1 : stop]:
            if not word.is_timed:
                return word
        return None

    def edge(self, edge: CutEdge, frame: int) -> tuple[TranscriptWord | None, int | None]:
        """Check one edge; return (retained neighbour word, padding) for the join."""

        words = self.snapshot.words
        before, after, inside = self.neighbours(frame)
        if inside is not None:
            r = _frames(inside)
            # Suggest the move that RETAINS the word (false removal costs more, ADR-018).
            retain_to = r.end if edge is CutEdge.START else r.start
            distance = min(frame - r.start, r.end - frame)
            if inside.kind == TranscriptTokenKind.AUDIO_EVENT:
                code = BoundaryFindingCode.AUDIO_EVENT_TRUNCATED
                detail = "Edge falls inside an audio-event token"
            else:
                code = BoundaryFindingCode.CUTS_INSIDE_WORD
                detail = "Edge falls strictly inside a timed word"
            self.add(code, edge, frame, inside, distance, detail, retain_to)
            return None, None

        unknown = self.untimed_between(before, after)
        if unknown is not None:
            self.add(
                BoundaryFindingCode.TIMING_UNKNOWN,
                edge,
                frame,
                unknown,
                None,
                "An untimed word sits next to this edge; its position is unknown",
            )

        prev = words[before] if before is not None else None
        nxt = words[after] if after is not None else None
        # Retained side: before START / after END. Removed side is the other.
        retained, removed = (prev, nxt) if edge is CutEdge.START else (nxt, prev)

        padding: int | None = None
        if retained is not None:
            r = _frames(retained)
            padding = frame - r.end if edge is CutEdge.START else r.start - frame
            if padding < self.policy.min_padding_frames:
                target = (
                    r.end + self.policy.min_padding_frames
                    if edge is CutEdge.START
                    else r.start - self.policy.min_padding_frames
                )
                self.add(
                    BoundaryFindingCode.PADDING_BELOW_MIN,
                    edge,
                    frame,
                    retained,
                    padding,
                    "Retained word keeps less than the minimum padding",
                    target,
                )

        if self.tol > 0:
            for word in (retained, removed):
                if word is None:
                    continue
                r = _frames(word)
                distance = frame - r.end if r.end <= frame else r.start - frame
                if distance <= self.tol:
                    self.add(
                        BoundaryFindingCode.NEAR_WORD_EDGE_WITHIN_TOLERANCE,
                        edge,
                        frame,
                        word,
                        distance,
                        "Edge is within transcript timing tolerance of a word edge",
                    )

        if prev is not None and nxt is not None:
            gap = _frames(nxt).start - _frames(prev).end
            if gap < self.policy.unsafe_gap_frames:
                self.add(
                    BoundaryFindingCode.GAP_UNSAFE,
                    edge,
                    frame,
                    None,
                    gap,
                    "Edge lands in a silence shorter than the unsafe threshold",
                )
            elif gap < self.policy.review_gap_frames:
                self.add(
                    BoundaryFindingCode.GAP_REVIEW,
                    edge,
                    frame,
                    None,
                    gap,
                    "Edge lands in a silence that needs review",
                )
        return retained, padding

    def run(self) -> tuple[BoundaryFinding, ...]:
        if not self.snapshot.timed_words:
            self.add(
                BoundaryFindingCode.TIMING_UNKNOWN,
                CutEdge.START,
                self.removal.start,
                None,
                None,
                "Transcript has no timed words",
            )
            return tuple(self.findings)
        left, left_pad = self.edge(CutEdge.START, self.removal.start)
        right, right_pad = self.edge(CutEdge.END, self.removal.end)
        if (
            left is not None
            and right is not None
            and left_pad is not None
            and right_pad is not None
            and left.speaker_ref is not None
            and right.speaker_ref is not None
            and left.speaker_ref != right.speaker_ref
        ):
            joined = left_pad + right_pad
            if joined < self.policy.review_gap_frames:
                self.add(
                    BoundaryFindingCode.SPEAKER_HANDOFF_TIGHT,
                    CutEdge.JOIN,
                    self.removal.start,
                    right,
                    joined,
                    "Removal joins two speakers with a short handoff",
                )
        return tuple(
            sorted(
                self.findings,
                key=lambda f: (_EDGE_ORDER[f.edge], _CODE_ORDER[f.code], f.word_ref or ""),
            )
        )


def check_removal_boundaries(
    removal: FrameRange, snapshot: TranscriptSnapshot, policy: BoundaryPolicy
) -> tuple[BoundaryFinding, ...]:
    """Advisory findings for removing source frames ``removal`` (never applied)."""

    if not isinstance(removal, FrameRange):
        raise TypeError("Removal must be an integer half-open FrameRange")
    if not isinstance(snapshot, TranscriptSnapshot):
        raise TypeError("Typed transcript snapshot required")
    if not isinstance(policy, BoundaryPolicy):
        raise TypeError("Typed boundary policy required")
    return _Checker(removal, snapshot, policy).run()
