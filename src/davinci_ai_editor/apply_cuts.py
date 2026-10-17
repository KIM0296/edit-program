"""APPLY-001: approved candidate cuts -> a NEW Expected timeline artifact (video + audio).

Axes stay separate (ADR-015, docs/CANDIDATE_AUTHORITY.md):

- SELECTION: ``candidate_markers.read_marker_selections`` (marker names the
  editor changed inside the NLE). Never an approval.
- CONFIRMATION: :func:`build_apply_confirmation` turns a selection into a
  human-readable summary plus a ``confirmation_digest`` that binds exactly the
  Expected artifact digest, the re-imported Actual digest and the approved cut
  set. Building it approves nothing.
- APPROVAL: :func:`apply_approved_cuts` refuses unless the caller passes
  ``confirmed_digest == confirmation.confirmation_digest`` - that explicit
  echo of the digest the user saw is the approval event.
- APPLY (to an artifact): the cuts are applied to the *Actual* re-imported
  timeline (the human's current state - Human Edit Wins) and emitted as a new
  Expected timeline artifact (``<name> AIE v2``). Nothing touches Resolve,
  media or rendering; importing the file is a manual user action and the
  result is not VERIFIED until VER-001 checks the next round trip.

Cut semantics (ripple delete on every track): each approved range, in Actual
timeline frames, is removed from every VIDEO and AUDIO track at the same
frames, so linked picture and sound stay in sync. Clips are split as needed
(source ranges are cut 1:1), gaps shrink, and everything after a cut moves left
by the removed duration. Every surviving clip piece that moves is reported as a
``domain.RippleDisplacement`` (track id = Actual track name, ``original_range``
= the piece in Actual coordinates, ``delta_frames`` < 0) - the same explicit
displacement semantics as ``safety.propose_ripple_displacements``; nothing
moves implicitly.

Skipped, never applied (with reasons in the summary): UNKNOWN decisions
(missing / duplicated / malformed / colour conflict / moved = stale), REJECTED,
PENDING, cuts overlapping a HARD_LOCK human-edit or UNKNOWN region derived by
RT-001 (``HUMAN_EDIT_LOCKED``; whole-UNKNOWN diffs lock everything), and cuts
whose range overlaps any other marker (``MARKER_CONFLICT``; markers are never
silently destroyed). Editing a candidate marker (the approval channel) is not
treated as a content edit: marker-only differences on ``AIE-`` markers do not
create locks. HARD_LOCK content after a cut is not edited but is shifted; each
such shift is listed in the confirmation summary and bound by the digest
(see docs/APPLY_001_STATUS.md, open question on Safety alignment).
"""

import hashlib
import itertools
import re
from dataclasses import dataclass, replace
from enum import Enum
from typing import Literal

from .candidate_markers import (
    CandidateDecision,
    MarkerSelection,
    MarkerSelectionSet,
    is_candidate_marker_name,
    parse_candidate_marker_name,
)
from .domain import FrameRange, ProtectedRange, RippleDisplacement, TrackId
from .handoff_model import (
    ARTIFACT_KIND,
    HandoffClip,
    HandoffGap,
    HandoffItem,
    HandoffMarker,
    HandoffTimeline,
    HandoffTrack,
    ReimportedTimeline,
)
from .roundtrip_diff import (
    AttributeChange,
    ChangeKind,
    DiffStatus,
    RoundTripChange,
    RoundTripDiff,
    derive_human_edit_protection,
    timeline_digest,
)
from .timecode import frames_to_seconds
from .trust_evidence import PreparedArtifactRevision, artifact_revision, canonical_bytes
from .xmeml_reader import track_keys

_VERSION_RE = re.compile(r"^(.*) AIE v(\d+)$")


class SkipReason(str, Enum):
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"
    PENDING = "PENDING"
    HUMAN_EDIT_LOCKED = "HUMAN_EDIT_LOCKED"
    MARKER_CONFLICT = "MARKER_CONFLICT"


SKIP_LABELS_KO = {
    SkipReason.UNKNOWN: "판단 불가 - 적용하지 않음",
    SkipReason.REJECTED: "제외됨",
    SkipReason.PENDING: "보류(미결정)",
    SkipReason.HUMAN_EDIT_LOCKED: "사람이 수정한 구간 - 보호",
    SkipReason.MARKER_CONFLICT: "다른 마커와 겹침",
}


class ApplyRefused(ValueError):
    """The confirmation digest was not echoed exactly: nothing is applied."""


@dataclass(frozen=True)
class ApprovedCut:
    candidate_id: str
    timeline_range: FrameRange  # Actual timeline coordinates
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.timeline_range, FrameRange):
            raise TypeError("Approved cut requires a FrameRange")
        if not isinstance(self.candidate_id, str) or not isinstance(self.reason, str):
            raise TypeError("Approved cut id and reason must be strings")


@dataclass(frozen=True)
class SkippedCandidate:
    candidate_id: str
    reason: SkipReason
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.reason, SkipReason):
            raise TypeError("Typed skip reason required")


@dataclass(frozen=True)
class ShiftedLock:
    """HARD_LOCK content that is not edited but moves left because of earlier cuts."""

    lock: ProtectedRange
    delta_frames: int


def confirmation_digest_for(
    expected_digest: str, actual_digest: str, cuts: tuple[ApprovedCut, ...]
) -> str:
    payload = {
        "approved_cuts": list(cuts),
        "actual_digest": actual_digest,
        "expected_digest": expected_digest,
        "schema": "apply-001-confirmation-v1",
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class ApplyConfirmation:
    """What will be applied, shown to the user before approval. Not an approval."""

    expected_digest: str
    actual_digest: str
    diff_digest: str
    actual: ReimportedTimeline
    approved_cuts: tuple[ApprovedCut, ...]
    skipped: tuple[SkippedCandidate, ...]
    locks: tuple[ProtectedRange, ...]
    shifted_locks: tuple[ShiftedLock, ...]
    summary: str
    confirmation_digest: str
    axis: Literal["CONFIRMATION"] = "CONFIRMATION"
    authorizes_apply: Literal[False] = False

    def __post_init__(self) -> None:
        for name in ("approved_cuts", "skipped", "locks", "shifted_locks"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not isinstance(self.actual, ReimportedTimeline):
            raise TypeError("Confirmation applies to a ReimportedTimeline (Actual)")
        if self.actual_digest != timeline_digest(self.actual):
            raise ValueError("Confirmation is not bound to this Actual")
        if self.axis != "CONFIRMATION" or self.authorizes_apply is not False:
            raise ValueError("A confirmation never authorizes apply by itself")
        ordered = sorted(self.approved_cuts, key=lambda c: c.timeline_range.start)
        if list(self.approved_cuts) != ordered:
            raise ValueError("Approved cuts must be ordered by timeline position")
        for left, right in itertools.pairwise(ordered):
            if left.timeline_range.overlaps(right.timeline_range):
                raise ValueError("Approved cuts must not overlap")
        for cut in self.approved_cuts:
            if any(cut.timeline_range.overlaps(lock.frame_range) for lock in self.locks):
                raise ValueError("An approved cut overlaps a HARD_LOCK region")
        expected = confirmation_digest_for(
            self.expected_digest, self.actual_digest, self.approved_cuts
        )
        if self.confirmation_digest != expected:
            raise ValueError("Confirmation digest does not bind these artifacts and cuts")

    @property
    def removed_frames(self) -> int:
        return sum(c.timeline_range.duration for c in self.approved_cuts)


@dataclass(frozen=True)
class AppliedTimeline:
    """The new Expected timeline artifact with the approved cuts applied (no rendering)."""

    timeline: HandoffTimeline
    expected_digest: str
    actual_digest: str
    confirmation_digest: str
    applied_cuts: tuple[ApprovedCut, ...]
    ripple_displacements: tuple[RippleDisplacement, ...]
    remaining_candidate_ids: tuple[str, ...]
    approval: Literal["EXPLICIT_CONFIRMATION_DIGEST"] = "EXPLICIT_CONFIRMATION_DIGEST"
    artifact_kind: Literal["EXPECTED_TIMELINE_ARTIFACT"] = ARTIFACT_KIND
    authorizes_import: Literal[False] = False
    verified: Literal[False] = False

    def __post_init__(self) -> None:
        for name in ("applied_cuts", "ripple_displacements", "remaining_candidate_ids"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not isinstance(self.timeline, HandoffTimeline):
            raise TypeError("The applied result is an Expected HandoffTimeline")
        if (
            self.artifact_kind != ARTIFACT_KIND
            or self.authorizes_import is not False
            or self.verified is not False
        ):
            raise ValueError("Applied timelines are unverified Expected artifacts only")

    @property
    def revision(self) -> PreparedArtifactRevision:
        """Content-addressed revision of the new Expected (input to VER-001)."""
        return artifact_revision("apply-001", self.timeline.name, self.timeline)


# --- confirmation -----------------------------------------------------------------


def _non_candidate_markers(
    clips: tuple[HandoffClip, ...],
) -> frozenset[tuple[int, int, str, str]]:
    return frozenset(
        (m.frame_range.start, m.frame_range.end, m.name, m.note)
        for c in clips
        for m in c.markers
        if not is_candidate_marker_name(m.name)
    )


def _without_candidate_marker_edits(change: RoundTripChange) -> RoundTripChange:
    """Candidate-marker renames/moves are the approval channel, not content edits."""
    if (
        change.kind is not ChangeKind.UNCHANGED
        or change.expected is None
        or AttributeChange.MARKERS not in change.attribute_changes
    ):
        return change
    actual = tuple(a.clip for a in change.actual)
    if _non_candidate_markers((change.expected.clip,)) != _non_candidate_markers(actual):
        return change
    remaining = tuple(a for a in change.attribute_changes if a is not AttributeChange.MARKERS)
    return replace(change, attribute_changes=remaining, regions=change.regions if remaining else ())


def apply_locks(diff: RoundTripDiff) -> tuple[ProtectedRange, ...]:
    """RT-001 HARD_LOCKs, ignoring edits that touched only ``AIE-`` candidate markers."""
    filtered = replace(
        diff, changes=tuple(_without_candidate_marker_edits(c) for c in diff.changes)
    )
    return derive_human_edit_protection(filtered)


@dataclass(frozen=True)
class _AnyMarker:
    timeline_range: FrameRange
    name: str


def _all_markers(actual: ReimportedTimeline) -> tuple[_AnyMarker, ...]:
    result: list[_AnyMarker] = []
    for _, track in track_keys(actual):
        for start, clip in track.placements():
            offset = start - clip.source_range.start
            for marker in clip.markers:
                frame_range = FrameRange(
                    marker.frame_range.start + offset, marker.frame_range.end + offset
                )
                result.append(_AnyMarker(frame_range, marker.name))
    return tuple(result)


def _seconds(frames: int, actual: ReimportedTimeline) -> str:
    value = frames_to_seconds(frames, actual.rate)
    millis = (value.numerator * 1000) // value.denominator
    return f"{millis // 1000}.{millis % 1000:03d}"


def _render_summary(
    actual: ReimportedTimeline,
    cuts: tuple[ApprovedCut, ...],
    skipped: tuple[SkippedCandidate, ...],
    shifted: tuple[ShiftedLock, ...],
    digest: str,
) -> str:
    removed = sum(c.timeline_range.duration for c in cuts)
    lines = [
        "APPLY-001 적용 확인 / apply confirmation",
        "Expected artifact only: no rendering, no Resolve API; import is a manual user action.",
        f"대상 타임라인(Actual): {actual.name}",
        (
            f"승인된 컷 {len(cuts)}개 / approved cuts: {len(cuts)}, "
            f"총 제거 {removed}프레임 ({_seconds(removed, actual)}초) - 비디오와 오디오 모든 트랙"
        ),
    ]
    for cut in cuts:
        r = cut.timeline_range
        lines.append(
            f"  {cut.candidate_id} [{r.start},{r.end}) {r.duration}f "
            f"{_seconds(r.duration, actual)}s - {cut.reason}"
        )
    lines.append(f"건너뜀 {len(skipped)}개 / skipped: {len(skipped)}")
    for item in skipped:
        lines.append(
            f"  {item.candidate_id} {item.reason.value} ({SKIP_LABELS_KO[item.reason]})"
            + (f" - {item.detail}" if item.detail else "")
        )
    if shifted:
        lines.append("보호 구간 이동(편집 없음) / HARD_LOCK regions shifted, not edited:")
        for entry in shifted:
            r = entry.lock.frame_range
            lines.append(f"  {entry.lock.track_id} [{r.start},{r.end}) {entry.delta_frames:+d}f")
    lines.append(f"confirmation_digest: {digest}")
    return "\n".join(lines) + "\n"


def _skip_for(selection: MarkerSelection) -> SkippedCandidate | None:
    decision = selection.decision
    if decision is CandidateDecision.APPROVED:
        return None
    if decision is CandidateDecision.REJECTED:
        return SkippedCandidate(selection.candidate_id, SkipReason.REJECTED, "")
    if decision is CandidateDecision.PENDING:
        return SkippedCandidate(selection.candidate_id, SkipReason.PENDING, "")
    detail = selection.issue.value + (f": {selection.detail}" if selection.detail else "")
    return SkippedCandidate(selection.candidate_id, SkipReason.UNKNOWN, detail)


def build_apply_confirmation(
    selection: MarkerSelectionSet, expected: HandoffTimeline, diff: RoundTripDiff
) -> ApplyConfirmation:
    """Summarize what an apply would do. Refuses (ValueError) on stale bindings."""
    if not isinstance(selection, MarkerSelectionSet):
        raise TypeError("A MarkerSelectionSet is required")
    if not isinstance(expected, HandoffTimeline) or not isinstance(diff, RoundTripDiff):
        raise TypeError("Expected HandoffTimeline and RoundTripDiff are required")
    expected_digest = timeline_digest(expected)
    if diff.expected_digest != expected_digest:
        raise ValueError("Diff is not bound to this Expected artifact (stale)")
    if diff.actual_digest != selection.actual_digest:
        raise ValueError("Diff and selection are not bound to the same Actual (stale)")
    actual = selection.actual
    locks = apply_locks(diff)
    markers = _all_markers(actual)
    approved: list[ApprovedCut] = []
    skipped: list[SkippedCandidate] = []
    for item in selection.selections:
        skip = _skip_for(item)
        if skip is not None:
            skipped.append(skip)
            continue
        cut_range = item.actual_range
        if cut_range is None:
            raise AssertionError("approved selections are located")
        hit = next((lock for lock in locks if lock.frame_range.overlaps(cut_range)), None)
        if diff.status is DiffStatus.UNKNOWN or hit is not None:
            if diff.status is DiffStatus.UNKNOWN or hit is None:
                detail = "Whole round-trip diff UNKNOWN"
            else:
                detail = f"{hit.track_id} [{hit.frame_range.start},{hit.frame_range.end})"
            skipped.append(
                SkippedCandidate(item.candidate_id, SkipReason.HUMAN_EDIT_LOCKED, detail)
            )
            continue
        others = sorted(
            {
                m.name
                for m in markers
                if m.name != item.marker_name and m.timeline_range.overlaps(cut_range)
            }
        )
        if others:
            skipped.append(
                SkippedCandidate(
                    item.candidate_id, SkipReason.MARKER_CONFLICT, "overlaps " + ", ".join(others)
                )
            )
            continue
        approved.append(ApprovedCut(item.candidate_id, cut_range, item.reason))
    cuts = tuple(sorted(approved, key=lambda c: c.timeline_range.start))
    shifted: list[ShiftedLock] = []
    for lock in locks:
        delta = -sum(
            c.timeline_range.duration
            for c in cuts
            if c.timeline_range.end <= lock.frame_range.start
        )
        if delta:
            shifted.append(ShiftedLock(lock, delta))
    digest = confirmation_digest_for(expected_digest, selection.actual_digest, cuts)
    summary = _render_summary(
        actual, cuts, tuple(sorted(skipped, key=lambda s: s.candidate_id)), tuple(shifted), digest
    )
    return ApplyConfirmation(
        expected_digest,
        selection.actual_digest,
        diff.digest,
        actual,
        cuts,
        tuple(sorted(skipped, key=lambda s: s.candidate_id)),
        locks,
        tuple(shifted),
        summary,
        digest,
    )


# --- apply ------------------------------------------------------------------------


def _subtract(span: FrameRange, cuts: tuple[FrameRange, ...]) -> list[FrameRange]:
    pieces: list[FrameRange] = []
    cursor = span.start
    for cut in cuts:
        if cut.end <= cursor or cut.start >= span.end:
            continue
        if cut.start > cursor:
            pieces.append(FrameRange(cursor, cut.start))
        cursor = max(cursor, cut.end)
    if cursor < span.end:
        pieces.append(FrameRange(cursor, span.end))
    return pieces


def _shift(frame: int, cuts: tuple[FrameRange, ...]) -> int:
    return -sum(c.duration for c in cuts if c.end <= frame)


def _piece(clip: HandoffClip, span_start: int, piece: FrameRange) -> HandoffClip:
    offset = clip.source_range.start - span_start
    source = FrameRange(piece.start + offset, piece.end + offset)
    markers: tuple[HandoffMarker, ...] = tuple(
        m for m in clip.markers if source.contains(m.frame_range)
    )
    return replace(clip, source_range=source, markers=markers)


def _apply_track(
    track: HandoffTrack, cuts: tuple[FrameRange, ...]
) -> tuple[HandoffTrack, list[RippleDisplacement]]:
    items: list[HandoffItem] = []
    displacements: list[RippleDisplacement] = []
    cursor = 0
    for item in track.items:
        span = FrameRange(cursor, cursor + item.duration)
        cursor = span.end
        for piece in _subtract(span, cuts):
            if isinstance(item, HandoffGap):
                if items and isinstance(items[-1], HandoffGap):
                    items[-1] = HandoffGap(items[-1].duration + piece.duration)
                else:
                    items.append(HandoffGap(piece.duration))
                continue
            items.append(_piece(item, span.start, piece))
            delta = _shift(piece.start, cuts)
            if delta:
                displacements.append(RippleDisplacement(TrackId(track.name), piece, delta))
    while items and isinstance(items[-1], HandoffGap):
        items.pop()
    return replace(track, items=tuple(items)), displacements


def next_version_name(name: str) -> str:
    match = _VERSION_RE.match(name)
    if match is None:
        return f"{name} AIE v2"
    return f"{match.group(1)} AIE v{int(match.group(2)) + 1}"


def apply_approved_cuts(
    confirmation: ApplyConfirmation, *, confirmed_digest: str
) -> AppliedTimeline:
    """Apply the confirmed cuts to the Actual and emit a new Expected artifact.

    ``confirmed_digest`` must equal ``confirmation.confirmation_digest`` exactly;
    that explicit echo is the approval. Otherwise :class:`ApplyRefused`.
    """
    if not isinstance(confirmation, ApplyConfirmation):
        raise TypeError("An ApplyConfirmation is required")
    if (
        not isinstance(confirmed_digest, str)
        or confirmed_digest != confirmation.confirmation_digest
    ):
        raise ApplyRefused("Confirmation digest not echoed exactly; nothing applied")
    actual = confirmation.actual
    cuts = tuple(c.timeline_range for c in confirmation.approved_cuts)
    tracks: list[HandoffTrack] = []
    displacements: list[RippleDisplacement] = []
    for track in actual.tracks:
        new_track, moved = _apply_track(track, cuts)
        tracks.append(new_track)
        displacements.extend(moved)
    timeline = HandoffTimeline(
        next_version_name(actual.name), actual.rate, actual.start_frame, tuple(tracks)
    )
    applied_ids = {c.candidate_id for c in confirmation.approved_cuts}
    tokens = {
        parse_candidate_marker_name(m.name)[0]
        for track in tracks
        for item in track.items
        if isinstance(item, HandoffClip)
        for m in item.markers
    }
    remaining = sorted(t for t in tokens if t is not None and t not in applied_ids)
    return AppliedTimeline(
        timeline,
        confirmation.expected_digest,
        confirmation.actual_digest,
        confirmation.confirmation_digest,
        confirmation.approved_cuts,
        tuple(displacements),
        tuple(remaining),
    )
