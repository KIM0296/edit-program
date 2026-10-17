"""APPLY-001 candidate markers: hand off cut candidates as markers, read the editor's choice.

Flow (file round-trip; no Resolve API, no media, no rendering):

1. :func:`attach_candidate_markers` puts one marker per cut candidate on the
   anchor clip (first VIDEO track) of an Expected ``HandoffTimeline``. The marker
   name carries a stable token and a pending mark, e.g. ``AIE-0012 ?``; the note
   carries the candidate id and a short reason.
2. The editor imports the written file manually and, inside the NLE, renames the
   marker: ``AIE-0012 OK`` / ``AIE-0012 승인`` = APPROVED, ``AIE-0012 X`` /
   ``AIE-0012 제외`` = REJECTED, unchanged ``?`` = PENDING (case-insensitive).
3. :func:`read_marker_selections` reads the re-imported Actual
   (``ReimportedTimeline``) and returns a :class:`MarkerSelectionSet`.

This module is SELECTION only (ADR-015: selection != approval != apply !=
verify). A selection never authorizes applying anything; approval is the
explicit confirmation digest in ``apply_cuts``.

Never guessed - each of these makes the candidate UNKNOWN (never applied):
missing token, duplicated token, malformed name, a marker colour that conflicts
with the name, and a marker that moved relative to the Expected candidate (its
media-relative range or media changed by even one frame - stale). Marker colour
is a secondary signal only where the format carries it (OTIO ``Marker.2``;
FCP7 xmeml markers carry none): GREEN = approve, RED = reject, any other colour
is neutral. A colour alone never approves: ``?`` with GREEN is a conflict.

Position semantics: "moved" is judged in media-relative frames of the clip the
marker sits on, so a human ripple elsewhere that shifts the clip on the
timeline does not make the candidate stale; the cut is then applied where that
content currently is in the Actual timeline (Human Edit Wins).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum
from typing import Literal

from .domain import FrameRange
from .handoff_model import (
    HandoffClip,
    HandoffItem,
    HandoffMarker,
    HandoffTimeline,
    HandoffTrackKind,
    MarkerColor,
    ReimportedTimeline,
)
from .roundtrip_diff import timeline_digest
from .xmeml_reader import TrackKey, track_keys

CANDIDATE_ID_RE = re.compile(r"^AIE-\d{4,}$")
_TOKEN_SEARCH_RE = re.compile(r"AIE-\d{4,}", re.IGNORECASE)
_TOKEN_PREFIX_RE = re.compile(r"AIE-", re.IGNORECASE)
_NAME_RE = re.compile(r"^\s*(AIE-\d{4,})\s+(\S+)\s*$", re.IGNORECASE)
MAX_REASON_CHARS = 120
ANCHOR_TRACK = TrackKey(HandoffTrackKind.VIDEO, 1)
PENDING_MARKER_COLOR = MarkerColor.YELLOW


class CandidateDecision(str, Enum):
    UNKNOWN = "UNKNOWN"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SelectionIssue(str, Enum):
    """Why a decision is UNKNOWN (``NONE`` for a clean read)."""

    NONE = "NONE"
    MISSING = "MISSING"
    DUPLICATED = "DUPLICATED"
    MALFORMED = "MALFORMED"
    COLOR_CONFLICT = "COLOR_CONFLICT"
    MOVED = "MOVED"


# Status word vocabulary (casefolded). Korean aliases allowed; codes stay English.
_VOCABULARY = {
    "?": CandidateDecision.PENDING,
    "ok": CandidateDecision.APPROVED,
    "승인": CandidateDecision.APPROVED,
    "x": CandidateDecision.REJECTED,
    "제외": CandidateDecision.REJECTED,
}
_STATUS_WORD = {
    CandidateDecision.PENDING: "?",
    CandidateDecision.APPROVED: "OK",
    CandidateDecision.REJECTED: "X",
}
_COLOR_SIGNAL = {
    MarkerColor.GREEN: CandidateDecision.APPROVED,
    MarkerColor.RED: CandidateDecision.REJECTED,
}


def is_candidate_marker_name(name: str) -> bool:
    """True for any marker name that mentions an ``AIE-`` token (well-formed or not)."""
    return bool(_TOKEN_PREFIX_RE.search(name))


def candidate_marker_name(
    candidate_id: str, decision: CandidateDecision = CandidateDecision.PENDING
) -> str:
    if not isinstance(candidate_id, str) or not CANDIDATE_ID_RE.match(candidate_id):
        raise ValueError("Candidate id must look like AIE-0012")
    word = _STATUS_WORD.get(decision)
    if word is None:
        raise ValueError("Only PENDING / APPROVED / REJECTED have a marker spelling")
    return f"{candidate_id} {word}"


def parse_candidate_marker_name(name: str) -> tuple[str | None, CandidateDecision]:
    """(token or None, decision). Malformed names give UNKNOWN; no token gives (None, UNKNOWN)."""
    match = _NAME_RE.match(name)
    if match is not None:
        token = match.group(1).upper()
        return token, _VOCABULARY.get(match.group(2).casefold(), CandidateDecision.UNKNOWN)
    found = _TOKEN_SEARCH_RE.search(name)
    return (None if found is None else found.group(0).upper()), CandidateDecision.UNKNOWN


@dataclass(frozen=True)
class CutCandidate:
    """A proposed cut in Expected timeline coordinates (frame 0 = timeline start)."""

    candidate_id: str
    timeline_range: FrameRange
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not CANDIDATE_ID_RE.match(self.candidate_id):
            raise ValueError("Candidate id must look like AIE-0012")
        if not isinstance(self.timeline_range, FrameRange):
            raise TypeError("Candidate requires a FrameRange")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("Candidate reason must be a nonempty string")
        if len(self.reason) > MAX_REASON_CHARS or any(c in self.reason for c in "\r\n\t"):
            raise ValueError("Candidate reason must be short single-line text")

    @property
    def marker_note(self) -> str:
        return f"candidate={self.candidate_id}; reason={self.reason.strip()}"


@dataclass(frozen=True)
class PlacedCandidate:
    """Where the candidate marker was written in the Expected artifact."""

    candidate: CutCandidate
    anchor_track: TrackKey
    media_id: str
    marker_range: FrameRange  # media-relative frames on the anchor clip

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, CutCandidate):
            raise TypeError("PlacedCandidate requires a CutCandidate")
        if not isinstance(self.anchor_track, TrackKey):
            raise TypeError("PlacedCandidate requires a TrackKey")
        if not isinstance(self.media_id, str) or not self.media_id.strip():
            raise ValueError("Media id required")
        if not isinstance(self.marker_range, FrameRange):
            raise TypeError("Marker range must be a FrameRange")
        if self.marker_range.duration != self.candidate.timeline_range.duration:
            raise ValueError("Marker range must have the candidate duration")

    @property
    def candidate_id(self) -> str:
        return self.candidate.candidate_id


@dataclass(frozen=True)
class CandidateHandoff:
    """Expected artifact with candidate markers plus where each marker went."""

    timeline: HandoffTimeline
    candidates: tuple[PlacedCandidate, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))
        if not isinstance(self.timeline, HandoffTimeline):
            raise TypeError("CandidateHandoff requires an Expected HandoffTimeline")
        if any(not isinstance(c, PlacedCandidate) for c in self.candidates):
            raise TypeError("Candidates must be PlacedCandidate values")
        ids = [c.candidate_id for c in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate candidate id")


def attach_candidate_markers(
    timeline: HandoffTimeline, candidates: Sequence[CutCandidate]
) -> CandidateHandoff:
    """Write one pending marker per candidate on the anchor clip (first VIDEO track).

    Each candidate must lie inside one clip of the anchor track; existing
    ``AIE-`` markers on the timeline are refused (tokens must stay unique).
    """
    if not isinstance(timeline, HandoffTimeline):
        raise TypeError("An Expected HandoffTimeline is required")
    items = tuple(candidates)
    if any(not isinstance(c, CutCandidate) for c in items):
        raise TypeError("Candidates must be CutCandidate values")
    ids = [c.candidate_id for c in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate candidate id")
    for track in timeline.tracks:
        for item in track.items:
            if isinstance(item, HandoffClip) and any(
                is_candidate_marker_name(m.name) for m in item.markers
            ):
                raise ValueError("Timeline already carries AIE- candidate markers")
    keyed = track_keys(timeline)
    anchor_position = next((i for i, (k, _) in enumerate(keyed) if k == ANCHOR_TRACK), None)
    if anchor_position is None:
        raise ValueError("No VIDEO track to anchor candidate markers")
    anchor = keyed[anchor_position][1]
    new_items: list[HandoffItem] = list(anchor.items)
    placed: list[PlacedCandidate] = []
    starts: list[int] = []
    cursor = 0
    for item in anchor.items:
        starts.append(cursor)
        cursor += item.duration
    for candidate in sorted(items, key=lambda c: (c.timeline_range.start, c.candidate_id)):
        target = candidate.timeline_range
        index = next(
            (
                i
                for i, item in enumerate(anchor.items)
                if isinstance(item, HandoffClip)
                and FrameRange(starts[i], starts[i] + item.duration).contains(target)
            ),
            None,
        )
        if index is None:
            raise ValueError(
                f"{candidate.candidate_id} must lie inside one clip of the anchor track"
            )
        clip = new_items[index]
        if not isinstance(clip, HandoffClip):
            raise TypeError("index selects a clip")
        offset = clip.source_range.start - starts[index]
        marker_range = FrameRange(target.start + offset, target.end + offset)
        marker = HandoffMarker(
            marker_range,
            candidate_marker_name(candidate.candidate_id),
            PENDING_MARKER_COLOR,
            candidate.marker_note,
        )
        markers = tuple(
            sorted(
                (*clip.markers, marker),
                key=lambda m: (m.frame_range.start, m.frame_range.end, m.name),
            )
        )
        new_items[index] = replace(clip, markers=markers)
        placed.append(PlacedCandidate(candidate, ANCHOR_TRACK, clip.media.media_id, marker_range))
    tracks = list(timeline.tracks)
    tracks[anchor_position] = replace(anchor, items=tuple(new_items))
    return CandidateHandoff(
        replace(timeline, tracks=tuple(tracks)),
        tuple(sorted(placed, key=lambda p: p.candidate_id)),
    )


# --- selection ------------------------------------------------------------------


@dataclass(frozen=True)
class MarkerSelection:
    """One candidate as read back from the Actual (SELECTION only)."""

    candidate_id: str
    decision: CandidateDecision
    issue: SelectionIssue
    marker_name: str | None
    actual_track: TrackKey | None
    actual_range: FrameRange | None  # Actual timeline coordinates of the marker
    reason: str
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.decision, CandidateDecision) or not isinstance(
            self.issue, SelectionIssue
        ):
            raise TypeError("Typed decision and issue required")
        if (self.decision is CandidateDecision.UNKNOWN) != (self.issue is not SelectionIssue.NONE):
            raise ValueError("UNKNOWN decisions carry an issue; known decisions carry none")
        if self.decision is not CandidateDecision.UNKNOWN and (
            self.actual_range is None or self.actual_track is None
        ):
            raise ValueError("A read decision locates its marker in the Actual")


@dataclass(frozen=True)
class MarkerSelectionSet:
    """Editor's marker decisions read from the Actual. Never an approval."""

    actual: ReimportedTimeline
    actual_digest: str
    selections: tuple[MarkerSelection, ...]
    unexpected_tokens: tuple[str, ...] = ()
    axis: Literal["SELECTION"] = "SELECTION"
    authorizes_apply: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "selections", tuple(self.selections))
        object.__setattr__(self, "unexpected_tokens", tuple(self.unexpected_tokens))
        if not isinstance(self.actual, ReimportedTimeline):
            raise TypeError("Selections are read from a ReimportedTimeline (Actual)")
        if self.actual_digest != timeline_digest(self.actual):
            raise ValueError("Selection is not bound to this Actual")
        if self.axis != "SELECTION" or self.authorizes_apply is not False:
            raise ValueError("A marker selection is SELECTION only and never authorizes apply")
        ids = [s.candidate_id for s in self.selections]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate candidate selection")

    def selection(self, candidate_id: str) -> MarkerSelection:
        for item in self.selections:
            if item.candidate_id == candidate_id:
                return item
        raise KeyError(candidate_id)


@dataclass(frozen=True)
class FoundCandidateMarker:
    """A marker in the Actual whose name mentions an ``AIE-`` token."""

    track: TrackKey
    clip_start: int
    clip: HandoffClip
    marker: HandoffMarker
    token: str | None
    decision: CandidateDecision

    @property
    def timeline_range(self) -> FrameRange:
        offset = self.clip_start - self.clip.source_range.start
        return FrameRange(
            self.marker.frame_range.start + offset, self.marker.frame_range.end + offset
        )


def actual_candidate_markers(actual: ReimportedTimeline) -> tuple[FoundCandidateMarker, ...]:
    found: list[FoundCandidateMarker] = []
    for key, track in track_keys(actual):
        for start, clip in track.placements():
            for marker in clip.markers:
                if not is_candidate_marker_name(marker.name):
                    continue
                token, decision = parse_candidate_marker_name(marker.name)
                found.append(FoundCandidateMarker(key, start, clip, marker, token, decision))
    return tuple(found)


def _unknown(
    candidate: PlacedCandidate,
    issue: SelectionIssue,
    detail: str,
    entry: FoundCandidateMarker | None = None,
) -> MarkerSelection:
    return MarkerSelection(
        candidate.candidate_id,
        CandidateDecision.UNKNOWN,
        issue,
        None if entry is None else entry.marker.name,
        None if entry is None else entry.track,
        None if entry is None else entry.timeline_range,
        candidate.candidate.reason,
        detail,
    )


def _select(candidate: PlacedCandidate, entries: Sequence[FoundCandidateMarker]) -> MarkerSelection:
    if not entries:
        return _unknown(candidate, SelectionIssue.MISSING, "No marker carries this token")
    if len(entries) > 1:
        return _unknown(candidate, SelectionIssue.DUPLICATED, f"{len(entries)} markers")
    entry = entries[0]
    if entry.decision is CandidateDecision.UNKNOWN:
        return _unknown(candidate, SelectionIssue.MALFORMED, "Unrecognized marker name", entry)
    if (
        entry.track != candidate.anchor_track
        or entry.clip.media.media_id != candidate.media_id
        or entry.marker.frame_range != candidate.marker_range
    ):
        return _unknown(
            candidate, SelectionIssue.MOVED, "Marker moved relative to the candidate", entry
        )
    signal = _COLOR_SIGNAL.get(entry.marker.color)
    if signal is not None and signal is not entry.decision:
        detail = f"Name says {entry.decision.value}, colour {entry.marker.color.value}"
        return _unknown(candidate, SelectionIssue.COLOR_CONFLICT, detail, entry)
    return MarkerSelection(
        candidate.candidate_id,
        entry.decision,
        SelectionIssue.NONE,
        entry.marker.name,
        entry.track,
        entry.timeline_range,
        candidate.candidate.reason,
    )


def read_marker_selections(
    actual: ReimportedTimeline, expected_candidates: Sequence[PlacedCandidate]
) -> MarkerSelectionSet:
    """Read the editor's marker decisions (SELECTION only; nothing is approved)."""
    if not isinstance(actual, ReimportedTimeline):
        raise TypeError("A ReimportedTimeline (Actual) is required")
    placed = tuple(expected_candidates)
    if any(not isinstance(p, PlacedCandidate) for p in placed):
        raise TypeError("Expected candidates must be PlacedCandidate values")
    found = actual_candidate_markers(actual)
    by_token: dict[str, list[FoundCandidateMarker]] = {}
    for entry in found:
        if entry.token is not None:
            by_token.setdefault(entry.token, []).append(entry)
    selections = tuple(
        _select(candidate, by_token.get(candidate.candidate_id, []))
        for candidate in sorted(placed, key=lambda p: p.candidate_id)
    )
    expected_ids = {p.candidate_id for p in placed}
    unexpected = sorted(
        {e.token for e in found if e.token is not None and e.token not in expected_ids}
    )
    return MarkerSelectionSet(actual, timeline_digest(actual), selections, tuple(unexpected))
