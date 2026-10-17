"""RT-001 round-trip diff: Expected handoff artifact vs re-imported Actual file.

Flow (Resolve Free, file round-trip only): we write an Expected timeline file
(HANDOFF-001), the editor imports it, edits by hand, exports FCP7 XML or OTIO,
and we re-read that file. The re-read file is ``FILE_ROUNDTRIP`` evidence: it
is never native evidence, never VERIFIED_LIVE, and never feeds a Safety gate as
an observed native snapshot.

``diff_roundtrip`` classifies every Expected clip and every Actual clip as
UNCHANGED / TRIMMED / MOVED / SPLIT / MERGED / REMOVED_BY_HUMAN /
ADDED_BY_HUMAN / REPLACED / UNKNOWN. Ambiguous correspondences and anything
touching an UNSUPPORTED region stay UNKNOWN (never guessed). A rate or start
mismatch, or an unreadable Actual, makes the whole diff UNKNOWN.

``derive_human_edit_protection`` turns every region touched by a human change
and every UNKNOWN region into ``ProtectedRange`` HARD_LOCKs in *Actual*
timeline coordinates (Human Edit Wins / Preserve Accepted Work).

How the locks feed the existing path (not wired into orchestration here): an
AI re-run must build its base ``TimelineSnapshot`` from the authoritative
Actual state and pass these ranges as ``TimelineSnapshot.protected_ranges``
(``safety.preflight`` rejects any command that directly edits or ripples a
HARD_LOCK range) or as ``safety_preflight.ProtectedRangeRecord`` values with
``policy="HARD_LOCK"`` inside a ``ProtectionContext``. Candidate generation
must exclude these ranges before proposing. Locks are never relaxed by
re-running the AI; a stale plan built before the round-trip cannot
auto-execute and is never silently rebased onto the Actual.

LAYER-001: the diff also carries ``layer_findings`` (``layer_policy.compare_layers``):
track set/order/state and every pass-through item (generator, transition,
filtered clip, ...) compared verbatim on its canonical subtree. An UNSUPPORTED
region fully explained by pass-through items found identical (MATCH), moved
with identical content (MOVED) or newly added (ADDED) is no longer UNKNOWN;
MOVED / ADDED / CHANGED / LOST items and changed track state are HARD_LOCKed
like any other human change. A region with changed content, or overlapping an
Expected modelled clip, stays UNKNOWN.

INT-002 (requested by STUDIO-T1):

- Evidence class: a Studio API read (``RoundTripFormat.STUDIO_API_READ``) is
  labelled ``STUDIO_API_READ`` end to end (artifact reference, diff, VER-001
  report), never ``FILE_ROUNDTRIP``; it is still never native evidence and today
  only TEST_ONLY_SUPPORT (fake object graph).
- Expected split frames: ``diff_roundtrip(..., expected_splits=...)`` takes the
  split frames we listed to the editor (track name or ``KIND:n`` label -> Actual
  timeline frames). A split of one Expected clip into unmoved, source-contiguous
  pieces of the same media / name / enabled state whose every split frame is
  listed is ``NEUTRAL_SPLIT``: not a human edit and no HARD_LOCK (a marker change
  on the pieces still is). Any other split stays ``SPLIT`` (HARD_LOCK). The
  geometry rule is shared with ``studio_razor.classify_split_change``
  (:func:`contiguous_split_frames`).
"""

import hashlib
import itertools
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from .domain import FrameRange, ProtectedRange, TrackId
from .handoff_model import (
    EVIDENCE_CLASS,
    EVIDENCE_CLASSES,
    EVIDENCE_QUALIFICATION,
    STUDIO_EVIDENCE_CLASS,
    EvidenceClass,
    HandoffClip,
    HandoffDiagnostic,
    HandoffTimeline,
    HandoffTrackKind,
    ReimportedTimeline,
    TimelineStructure,
    is_windows_absolute,
)
from .layer_policy import (
    LayerFinding,
    LayerFindingKind,
    compare_layers,
    resolve_passthrough_regions,
)
from .otio_json import OtioReadResult
from .timecode import frames_per_24_hours
from .trust_evidence import canonical_bytes
from .xmeml_reader import (
    TrackKey,
    UnknownRegion,
    XmemlReadResult,
    track_keys,
)

_HEX = frozenset("0123456789abcdef")


class RoundTripFormat(str, Enum):
    UNKNOWN = "UNKNOWN"
    XMEML = "XMEML"
    OTIO_JSON = "OTIO_JSON"
    # STUDIO-T0: a getter-only read of a Resolve-like object graph (TEST_ONLY_SUPPORT,
    # fake only). Media is named by display name + path, like FCP7 xmeml.
    STUDIO_API_READ = "STUDIO_API_READ"


class MediaIdentityBasis(str, Enum):
    """How the Actual file names media: our metadata (OTIO) or a display name (xmeml).

    ``PATH_FALLBACK``: OTIO file where some clips lost our metadata; those clips
    are matched by target path + source range (WEAK), the rest by metadata.
    """

    UNKNOWN = "UNKNOWN"
    METADATA = "METADATA"
    DISPLAY_NAME = "DISPLAY_NAME"
    PATH_FALLBACK = "PATH_FALLBACK"


_BASIS_BY_FORMAT = {
    RoundTripFormat.XMEML: MediaIdentityBasis.DISPLAY_NAME,
    RoundTripFormat.OTIO_JSON: MediaIdentityBasis.METADATA,
    RoundTripFormat.STUDIO_API_READ: MediaIdentityBasis.DISPLAY_NAME,
    RoundTripFormat.UNKNOWN: MediaIdentityBasis.UNKNOWN,
}


class IdentityStrength(str, Enum):
    """UNKNOWN is also used for sides without a counterpart (removed/added)."""

    UNKNOWN = "UNKNOWN"
    STRONG = "STRONG"
    WEAK = "WEAK"


class ChangeKind(str, Enum):
    UNKNOWN = "UNKNOWN"
    UNCHANGED = "UNCHANGED"
    TRIMMED = "TRIMMED"
    MOVED = "MOVED"
    SPLIT = "SPLIT"
    # INT-002: a split exactly at frames we listed (razor assist); not a human edit
    NEUTRAL_SPLIT = "NEUTRAL_SPLIT"
    MERGED = "MERGED"
    REMOVED_BY_HUMAN = "REMOVED_BY_HUMAN"
    ADDED_BY_HUMAN = "ADDED_BY_HUMAN"
    REPLACED = "REPLACED"


class DiffStatus(str, Enum):
    UNKNOWN = "UNKNOWN"  # whole diff unknown
    COMPLETE = "COMPLETE"  # every item classified, none UNKNOWN
    PARTIAL = "PARTIAL"  # some items UNKNOWN


class DiffReason(str, Enum):
    NONE = "NONE"
    ACTUAL_UNREADABLE = "ACTUAL_UNREADABLE"
    RATE_MISMATCH = "RATE_MISMATCH"
    START_MISMATCH = "START_MISMATCH"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    IDENTITY_UNKNOWN = "IDENTITY_UNKNOWN"
    UNSUPPORTED_REGION = "UNSUPPORTED_REGION"
    UNKNOWN_FORMAT = "UNKNOWN_FORMAT"


class AttributeChange(str, Enum):
    ENABLED = "ENABLED"
    MARKERS = "MARKERS"


def evidence_class_for(fmt: RoundTripFormat) -> EvidenceClass:
    """The evidence class a round-trip format carries (never native)."""
    return STUDIO_EVIDENCE_CLASS if fmt is RoundTripFormat.STUDIO_API_READ else EVIDENCE_CLASS


@dataclass(frozen=True)
class RoundTripArtifactRef:
    """The re-read Actual: caller reference + exact content digest.

    ``FILE_ROUNDTRIP`` for a re-imported file; ``STUDIO_API_READ`` (INT-002) for a
    getter-only Studio read, where ``text_sha256`` is the raw-read snapshot digest.
    The class must match the format; neither is ever native evidence.
    """

    ref: str
    format: RoundTripFormat
    text_sha256: str
    evidence_class: EvidenceClass = EVIDENCE_CLASS
    native_evidence: Literal[False] = False

    def __post_init__(self) -> None:
        if not isinstance(self.ref, str) or not self.ref.strip():
            raise ValueError("Artifact reference must be a nonempty string")
        if not isinstance(self.format, RoundTripFormat):
            raise TypeError("Unknown round-trip format type")
        if (
            not isinstance(self.text_sha256, str)
            or len(self.text_sha256) != 64
            or any(c not in _HEX for c in self.text_sha256)
        ):
            raise ValueError("Lowercase SHA-256 hex digest required")
        if self.evidence_class not in EVIDENCE_CLASSES or self.native_evidence is not False:
            raise ValueError("A re-read Actual is FILE_ROUNDTRIP / STUDIO_API_READ, never native")
        if self.evidence_class != evidence_class_for(self.format):
            raise ValueError(
                f"Evidence class {self.evidence_class} does not match format {self.format.value}"
            )

    @property
    def evidence_domain(self) -> str:
        """``FILE_ROUNDTRIP`` or ``TEST_ONLY_SUPPORT`` (Studio reads exist only on the fake)."""
        return EVIDENCE_QUALIFICATION[self.evidence_class]


def roundtrip_artifact_ref(ref: str, text: str, fmt: RoundTripFormat) -> RoundTripArtifactRef:
    if not isinstance(text, str):
        raise TypeError("Artifact text must be a string")
    return RoundTripArtifactRef(
        ref, fmt, hashlib.sha256(text.encode("utf-8")).hexdigest(), evidence_class_for(fmt)
    )


def timeline_digest(timeline: TimelineStructure) -> str:
    """Same canonicalization/digest as ``trust_evidence.artifact_revision``.

    The canonical form includes the type name, so an Expected ``HandoffTimeline``
    and a ``ReimportedTimeline`` never share a digest.
    """
    if not isinstance(timeline, (HandoffTimeline, ReimportedTimeline)):
        raise TypeError("A HandoffTimeline or ReimportedTimeline is required")
    return hashlib.sha256(canonical_bytes(timeline)).hexdigest()


@dataclass(frozen=True)
class ClipPlacement:
    track: TrackKey
    item_index: int
    clip: HandoffClip
    timeline_range: FrameRange

    def __post_init__(self) -> None:
        if not isinstance(self.track, TrackKey) or not isinstance(self.clip, HandoffClip):
            raise TypeError("Placement requires a TrackKey and a HandoffClip")
        if type(self.item_index) is not int or self.item_index < 0:
            raise ValueError("Item index must be a nonnegative int")
        if self.timeline_range.duration != self.clip.duration:
            raise ValueError("Placement duration must equal the clip duration")

    @property
    def source_range(self) -> FrameRange:
        return self.clip.source_range


@dataclass(frozen=True)
class ActualRegion:
    track: TrackKey
    frame_range: FrameRange


@dataclass(frozen=True)
class RoundTripChange:
    change_id: str
    kind: ChangeKind
    expected: ClipPlacement | None
    actual: tuple[ClipPlacement, ...]
    identity: IdentityStrength
    reason: DiffReason = DiffReason.NONE
    timeline_delta: int | None = None
    head_delta: int | None = None
    tail_delta: int | None = None
    track_changed: bool = False
    attribute_changes: tuple[AttributeChange, ...] = ()
    regions: tuple[ActualRegion, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "actual", tuple(self.actual))
        object.__setattr__(self, "attribute_changes", tuple(self.attribute_changes))
        object.__setattr__(self, "regions", tuple(self.regions))
        if not isinstance(self.kind, ChangeKind) or not isinstance(self.identity, IdentityStrength):
            raise TypeError("Typed change kind and identity strength required")
        if not isinstance(self.reason, DiffReason):
            raise TypeError("Typed reason required")
        if not isinstance(self.change_id, str) or not self.change_id.strip():
            raise ValueError("Change ID required")
        n = len(self.actual)
        kind = self.kind
        if kind is ChangeKind.ADDED_BY_HUMAN:
            ok = self.expected is None and n == 1
        elif kind is ChangeKind.REMOVED_BY_HUMAN:
            ok = self.expected is not None and n == 0
        elif kind in (ChangeKind.SPLIT, ChangeKind.NEUTRAL_SPLIT):
            ok = self.expected is not None and n >= 2
        elif kind is ChangeKind.UNKNOWN:
            ok = self.expected is not None or n >= 1
        else:
            ok = self.expected is not None and n == 1
        if not ok:
            raise ValueError(f"Inconsistent sides for {kind.value}")
        if kind is not ChangeKind.UNKNOWN and self.reason is not DiffReason.NONE:
            raise ValueError("Only UNKNOWN changes carry a reason")
        if kind is ChangeKind.UNKNOWN and self.reason is DiffReason.NONE:
            raise ValueError("UNKNOWN changes require an explicit reason")

    @property
    def human_touched(self) -> bool:
        if self.kind in (ChangeKind.UNCHANGED, ChangeKind.NEUTRAL_SPLIT):
            return bool(self.attribute_changes)
        return True


@dataclass(frozen=True)
class TrackExtent:
    """Actual track and the ProtectedRange track ID used for it."""

    track: TrackKey
    protection_track_id: str
    duration: int


@dataclass(frozen=True)
class RoundTripDiff:
    expected_digest: str
    actual_digest: str | None
    artifact: RoundTripArtifactRef
    identity_basis: MediaIdentityBasis
    status: DiffStatus
    reasons: tuple[DiffReason, ...]
    changes: tuple[RoundTripChange, ...]
    unknown_regions: tuple[UnknownRegion, ...]
    actual_tracks: tuple[TrackExtent, ...]
    lock_horizon: int
    read_diagnostics: tuple[HandoffDiagnostic, ...] = ()
    layer_findings: tuple[LayerFinding, ...] = ()
    # INT-002: split frames listed to the editor (Actual track, frames), bound by digest
    expected_splits: tuple[tuple[TrackKey, tuple[int, ...]], ...] = ()
    evidence_class: EvidenceClass = EVIDENCE_CLASS

    def __post_init__(self) -> None:
        for name in (
            "reasons",
            "changes",
            "unknown_regions",
            "actual_tracks",
            "read_diagnostics",
            "layer_findings",
            "expected_splits",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not isinstance(self.artifact, RoundTripArtifactRef):
            raise TypeError("Artifact reference required")
        if (
            self.evidence_class not in EVIDENCE_CLASSES
            or self.evidence_class != self.artifact.evidence_class
        ):
            raise ValueError("A round-trip diff carries its artifact's evidence class")
        if not isinstance(self.status, DiffStatus):
            raise TypeError("Typed status required")
        has_unknown = any(c.kind is ChangeKind.UNKNOWN for c in self.changes)
        if self.status is DiffStatus.UNKNOWN and not self.reasons:
            raise ValueError("A whole-UNKNOWN diff requires a reason")
        if self.status is DiffStatus.COMPLETE and (has_unknown or self.unknown_regions):
            raise ValueError("COMPLETE diff cannot contain UNKNOWN items or regions")
        if self.status is DiffStatus.PARTIAL and not (has_unknown or self.unknown_regions):
            raise ValueError("PARTIAL diff requires an UNKNOWN item or region")
        if self.actual_digest is None and self.status is not DiffStatus.UNKNOWN:
            raise ValueError("Without a readable Actual the diff is UNKNOWN")
        if type(self.lock_horizon) is not int or self.lock_horizon <= 0:
            raise ValueError("Lock horizon must be a positive int")

    @property
    def evidence_domain(self) -> str:
        return EVIDENCE_QUALIFICATION[self.evidence_class]

    @property
    def digest(self) -> str:
        """Deterministic digest over the whole diff (both artifact digests included)."""
        return hashlib.sha256(canonical_bytes(self)).hexdigest()

    def change(self, change_id: str) -> RoundTripChange:
        for change in self.changes:
            if change.change_id == change_id:
                return change
        raise KeyError(change_id)


class ProtectionUnavailable(ValueError):
    """No Actual coordinates exist: the whole timeline must be treated as untouchable."""


# --- identity -----------------------------------------------------------------


def path_key(path: str | None) -> str | None:
    """Normalized comparison key for a media path (Windows drive letter / separators)."""
    if path is None:
        return None
    if is_windows_absolute(path):
        normalized = path.replace("\\", "/")
        return normalized[0].upper() + normalized[1:]
    return path


def identity_strength(
    expected: HandoffClip, actual: HandoffClip, basis: MediaIdentityBasis
) -> IdentityStrength | None:
    """``None`` = no correspondence (different media, or different source channel).

    LAYER-001 follow-up: when both clips carry FCP7 ``<sourcetrack>`` evidence
    (``source_track``) and it differs (e.g. the left vs right channel of one
    stereo file), they are different content and never correspond.
    """
    if (
        expected.source_track is not None
        and actual.source_track is not None
        and expected.source_track != actual.source_track
    ):
        return None
    e_media, a_media = expected.media, actual.media
    id_eq = e_media.media_id == a_media.media_id
    pe, pa = path_key(e_media.target_path), path_key(a_media.target_path)
    path_eq = pe is not None and pe == pa
    if not id_eq and not path_eq:
        return None
    if basis is MediaIdentityBasis.METADATA:
        if id_eq and (path_eq or pe is None or pa is None):
            return IdentityStrength.STRONG
        if id_eq:
            return IdentityStrength.WEAK  # same logical media, relinked path
        return IdentityStrength.UNKNOWN  # same file, different logical media IDs
    if basis in (MediaIdentityBasis.DISPLAY_NAME, MediaIdentityBasis.PATH_FALLBACK):
        if path_eq:
            return IdentityStrength.WEAK
        return IdentityStrength.UNKNOWN  # display-name collision with a different path
    return IdentityStrength.UNKNOWN


def contiguous_split_frames(
    start: int,
    original: HandoffClip,
    pieces: Sequence[tuple[int, HandoffClip]],
    same_piece: Callable[[HandoffClip], bool],
) -> tuple[int, ...] | str:
    """Split frames if ``pieces`` (timeline start, clip) are ``original`` (placed at
    ``start``) divided in place: the first piece starts where the original started,
    every next piece starts where the previous one ended in both timeline and source,
    every piece satisfies ``same_piece`` and the last ends where the original ended.
    Otherwise a short reason (str). Shared by RT-001 (NEUTRAL_SPLIT) and the Studio
    razor-assist classifier; frames are timeline frames of the caller's coordinates.
    """
    if not pieces:
        return "item missing"
    first_start, first = pieces[0]
    if (
        first_start != start
        or first.source_range.start != original.source_range.start
        or not same_piece(first)
    ):
        return "item changed"
    frames: list[int] = []
    position = first_start + first.duration
    source = first.source_range.end
    for next_start, piece in pieces[1:]:
        if next_start != position or piece.source_range.start != source or not same_piece(piece):
            return f"not a source-contiguous split at {position}"
        frames.append(position)
        position += piece.duration
        source = piece.source_range.end
    end = start + original.duration
    if position < end:
        return "item shortened"
    if position > end:
        return "item extended"
    return tuple(frames)


_STRENGTH_ORDER = {
    IdentityStrength.UNKNOWN: 0,
    IdentityStrength.WEAK: 1,
    IdentityStrength.STRONG: 2,
}


def _weakest(values: Iterable[IdentityStrength]) -> IdentityStrength:
    return min(values, key=lambda s: _STRENGTH_ORDER[s], default=IdentityStrength.UNKNOWN)


# --- helpers ------------------------------------------------------------------

_KIND_ORDER = {HandoffTrackKind.VIDEO: 0, HandoffTrackKind.AUDIO: 1, HandoffTrackKind.UNKNOWN: 2}


def _key_order(key: TrackKey) -> tuple[int, int]:
    return (_KIND_ORDER[key.kind], key.ordinal)


def _placements(timeline: TimelineStructure) -> dict[TrackKey, list[ClipPlacement]]:
    result: dict[TrackKey, list[ClipPlacement]] = {}
    for key, track in track_keys(timeline):
        cursor = 0
        items: list[ClipPlacement] = []
        for index, item in enumerate(track.items):
            if isinstance(item, HandoffClip):
                items.append(
                    ClipPlacement(key, index, item, FrameRange(cursor, cursor + item.duration))
                )
            cursor += item.duration
        result[key] = items
    return result


def _marker_keys(clips: Iterable[HandoffClip]) -> frozenset[tuple[int, int, str, str]]:
    return frozenset(
        (m.frame_range.start, m.frame_range.end, m.name, m.note) for c in clips for m in c.markers
    )


def _attribute_changes(
    expected: HandoffClip, actual: tuple[HandoffClip, ...]
) -> tuple[AttributeChange, ...]:
    changes: list[AttributeChange] = []
    if any(a.enabled != expected.enabled for a in actual):
        changes.append(AttributeChange.ENABLED)
    if _marker_keys((expected,)) != _marker_keys(actual):
        changes.append(AttributeChange.MARKERS)
    return tuple(changes)


def _hull(ranges: Iterable[FrameRange]) -> FrameRange:
    values = list(ranges)
    return FrameRange(min(r.start for r in values), max(r.end for r in values))


def _change_id(side: str, placement: ClipPlacement) -> str:
    return f"{side}:{placement.track.label}:{placement.item_index}"


class _Differ:
    def __init__(
        self,
        expected: HandoffTimeline,
        actual: ReimportedTimeline,
        basis: MediaIdentityBasis,
        regions: tuple[UnknownRegion, ...],
        expected_splits: Mapping[TrackKey, frozenset[int]] | None = None,
    ) -> None:
        self.basis = basis
        self.expected_splits = {} if expected_splits is None else dict(expected_splits)
        self.path_identified = frozenset(actual.path_identified_media_ids)
        self.regions = regions
        self.expected = _placements(expected)
        self.actual = _placements(actual)
        self.changes: list[RoundTripChange] = []
        self.matched_e: set[tuple[TrackKey, int]] = set()
        self.matched_a: set[tuple[TrackKey, int]] = set()
        # actual placements of matched expected clips: for REMOVED neighbourhoods
        self.e_to_a: dict[tuple[TrackKey, int], tuple[ClipPlacement, ...]] = {}

    def basis_for(self, actual: HandoffClip) -> MediaIdentityBasis:
        """Per-clip basis: path-identified OTIO media fall back to path matching (WEAK)."""
        if self.basis is MediaIdentityBasis.METADATA and actual.media.media_id in (
            self.path_identified
        ):
            return MediaIdentityBasis.PATH_FALLBACK
        return self.basis

    # --- unknown regions ----------------------------------------------------

    def kind_has_unknown(self, kind: HandoffTrackKind) -> bool:
        return any(r.track.kind is kind for r in self.regions)

    def overlaps_unknown(self, track: TrackKey, frame_range: FrameRange) -> bool:
        return any(
            r.track == track and (r.frame_range is None or r.frame_range.overlaps(frame_range))
            for r in self.regions
        )

    def whole_track_unknown(self, track: TrackKey) -> bool:
        return any(r.track == track and r.frame_range is None for r in self.regions)

    # --- recording ----------------------------------------------------------

    def record(self, change: RoundTripChange) -> None:
        self.changes.append(change)
        if change.expected is not None:
            self.matched_e.add((change.expected.track, change.expected.item_index))
            if change.actual:
                self.e_to_a[(change.expected.track, change.expected.item_index)] = change.actual
        for a in change.actual:
            self.matched_a.add((a.track, a.item_index))

    def unknown(
        self,
        expected: ClipPlacement | None,
        actual: tuple[ClipPlacement, ...],
        reason: DiffReason,
        identity: IdentityStrength = IdentityStrength.UNKNOWN,
    ) -> RoundTripChange:
        regions = [ActualRegion(a.track, a.timeline_range) for a in actual]
        if expected is not None:
            change_id = _change_id("E", expected)
        else:
            change_id = _change_id("A", actual[0])
        return RoundTripChange(
            change_id,
            ChangeKind.UNKNOWN,
            expected,
            actual,
            identity,
            reason,
            regions=tuple(regions),
        )

    def pair(
        self,
        e: ClipPlacement,
        fragments: tuple[ClipPlacement, ...],
        strength: IdentityStrength,
        kind_hint: ChangeKind | None = None,
    ) -> RoundTripChange:
        if strength is IdentityStrength.UNKNOWN:
            return self.unknown(e, fragments, DiffReason.IDENTITY_UNKNOWN)
        if any(self.overlaps_unknown(a.track, a.timeline_range) for a in fragments):
            return self.unknown(e, fragments, DiffReason.UNSUPPORTED_REGION, strength)
        first, last = fragments[0], fragments[-1]
        timeline_delta = first.timeline_range.start - e.timeline_range.start
        head = first.source_range.start - e.source_range.start
        tail = last.source_range.end - e.source_range.end
        track_changed = first.track != e.track
        attrs = _attribute_changes(e.clip, tuple(a.clip for a in fragments))
        regions: list[ActualRegion] = []
        if kind_hint is not None:
            kind = kind_hint
        elif len(fragments) > 1:
            kind = (
                ChangeKind.NEUTRAL_SPLIT
                if self.neutral_split(e, fragments, strength)
                else ChangeKind.SPLIT
            )
        elif head == 0 and tail == 0:
            kind = (
                ChangeKind.UNCHANGED
                if timeline_delta == 0 and not track_changed
                else ChangeKind.MOVED
            )
        else:
            kind = ChangeKind.TRIMMED
        actual_hull = _hull(a.timeline_range for a in fragments)
        if kind in (ChangeKind.UNCHANGED, ChangeKind.NEUTRAL_SPLIT):
            if attrs:
                regions.append(ActualRegion(first.track, actual_hull))
        elif kind is ChangeKind.TRIMMED:
            start = max(0, actual_hull.start - max(head, 0))
            end = actual_hull.end + max(-tail, 0)
            regions.append(ActualRegion(first.track, FrameRange(start, end)))
        elif kind is ChangeKind.MOVED:
            regions.append(ActualRegion(first.track, actual_hull))
            if e.track in self.actual:
                regions.append(ActualRegion(e.track, e.timeline_range))
        else:
            regions.append(ActualRegion(first.track, actual_hull))
        return RoundTripChange(
            _change_id("E", e),
            kind,
            e,
            fragments,
            strength,
            DiffReason.NONE,
            timeline_delta,
            head,
            tail,
            track_changed,
            attrs,
            tuple(regions),
        )

    def neutral_split(
        self,
        e: ClipPlacement,
        fragments: tuple[ClipPlacement, ...],
        strength: IdentityStrength,
    ) -> bool:
        """A split of ``e`` in place, only at listed frames (INT-002 NEUTRAL_SPLIT)."""
        listed = self.expected_splits.get(e.track)
        if not listed or strength is IdentityStrength.UNKNOWN:
            return False
        if any(a.track != e.track for a in fragments):
            return False

        def same(piece: HandoffClip) -> bool:
            return (
                piece.name == e.clip.name
                and piece.enabled == e.clip.enabled
                and identity_strength(e.clip, piece, self.basis_for(piece))
                in (IdentityStrength.WEAK, IdentityStrength.STRONG)
            )

        frames = contiguous_split_frames(
            e.timeline_range.start,
            e.clip,
            tuple((a.timeline_range.start, a.clip) for a in fragments),
            same,
        )
        return not isinstance(frames, str) and bool(frames) and set(frames) <= listed

    # --- passes -------------------------------------------------------------

    def same_track(self, key: TrackKey) -> None:
        expected = self.expected.get(key, [])
        actual = self.actual.get(key, [])
        if self.whole_track_unknown(key):
            for e in expected:
                self.record(self.unknown(e, (), DiffReason.UNSUPPORTED_REGION))
            return
        edges: dict[int, dict[int, IdentityStrength]] = {}
        for ei, e in enumerate(expected):
            for ai, a in enumerate(actual):
                if not e.source_range.overlaps(a.source_range):
                    continue
                strength = identity_strength(e.clip, a.clip, self.basis_for(a.clip))
                if strength is not None:
                    edges.setdefault(ei, {})[ai] = strength
        # connected components of the bipartite e-a graph
        seen_e: set[int] = set()
        for start in sorted(edges):
            if start in seen_e:
                continue
            comp_e: set[int] = set()
            comp_a: set[int] = set()
            stack: list[tuple[str, int]] = [("e", start)]
            while stack:
                side, index = stack.pop()
                if side == "e":
                    if index in comp_e:
                        continue
                    comp_e.add(index)
                    stack.extend(("a", ai) for ai in edges.get(index, {}))
                else:
                    if index in comp_a:
                        continue
                    comp_a.add(index)
                    stack.extend(("e", ei) for ei, row in edges.items() if index in row)
            seen_e |= comp_e
            self.component(
                [expected[i] for i in sorted(comp_e)],
                [actual[i] for i in sorted(comp_a)],
                {(ei, ai): s for ei in comp_e for ai, s in edges.get(ei, {}).items()},
                sorted(comp_e),
                sorted(comp_a),
            )

    def component(
        self,
        es: list[ClipPlacement],
        as_: list[ClipPlacement],
        edges: dict[tuple[int, int], IdentityStrength],
        e_idx: list[int],
        a_idx: list[int],
    ) -> None:
        strengths = tuple(edges.values())
        weakest = _weakest(strengths)
        if len(es) == 1:
            fragments = tuple(sorted(as_, key=lambda a: a.timeline_range.start))
            disjoint = all(
                not x.source_range.overlaps(y.source_range)
                for i, x in enumerate(fragments)
                for y in fragments[i + 1 :]
            )
            ordered = all(
                x.source_range.end <= y.source_range.start for x, y in itertools.pairwise(fragments)
            )
            if len(fragments) == 1 or (disjoint and ordered):
                self.record(self.pair(es[0], fragments, weakest))
            else:
                self.record(self.unknown(es[0], fragments, DiffReason.AMBIGUOUS_MATCH))
            return
        if len(as_) == 1 and self.is_merge(es, as_[0]):
            for e in es:
                self.record(self.pair(e, (as_[0],), weakest, ChangeKind.MERGED))
            return
        for position, e in enumerate(es):
            linked = tuple(
                as_[a_idx.index(ai)] for (ei, ai) in sorted(edges) if ei == e_idx[position]
            )
            self.record(self.unknown(e, linked, DiffReason.AMBIGUOUS_MATCH))

    @staticmethod
    def is_merge(es: list[ClipPlacement], a: ClipPlacement) -> bool:
        by_time = sorted(es, key=lambda e: e.timeline_range.start)
        for x, y in itertools.pairwise(by_time):
            if x.timeline_range.end != y.timeline_range.start:
                return False
            if x.source_range.end != y.source_range.start:
                return False
        return (
            a.source_range.start == by_time[0].source_range.start
            and a.source_range.end == by_time[-1].source_range.end
            and a.timeline_range.start == by_time[0].timeline_range.start
        )

    def leftovers_e(self, key: TrackKey) -> list[ClipPlacement]:
        return [e for e in self.expected.get(key, []) if (key, e.item_index) not in self.matched_e]

    def leftovers_a(self, key: TrackKey) -> list[ClipPlacement]:
        return [a for a in self.actual.get(key, []) if (key, a.item_index) not in self.matched_a]

    def cross_track(self, keys: list[TrackKey]) -> None:
        proposals: dict[tuple[TrackKey, int], list[tuple[ClipPlacement, IdentityStrength]]] = {}
        chosen: dict[tuple[TrackKey, int], ClipPlacement] = {}
        for key in keys:
            for e in self.leftovers_e(key):
                found: list[tuple[ClipPlacement, IdentityStrength]] = []
                for other in keys:
                    if other == key or other.kind is not key.kind:
                        continue
                    for a in self.leftovers_a(other):
                        if a.source_range != e.source_range:
                            continue
                        strength = identity_strength(e.clip, a.clip, self.basis_for(a.clip))
                        if strength is not None and strength is not IdentityStrength.UNKNOWN:
                            found.append((a, strength))
                if len(found) == 1:
                    a, strength = found[0]
                    proposals.setdefault((a.track, a.item_index), []).append((e, strength))
                    chosen[(e.track, e.item_index)] = a
        for (_, _), claims in sorted(
            proposals.items(), key=lambda kv: (_key_order(kv[0][0]), kv[0][1])
        ):
            if len(claims) != 1:
                continue
            e, strength = claims[0]
            a = chosen[(e.track, e.item_index)]
            self.record(self.pair(e, (a,), strength))

    def replaced(self, key: TrackKey) -> None:
        es = self.leftovers_e(key)
        as_ = self.leftovers_a(key)
        for e in es:
            hits = [a for a in as_ if a.timeline_range.overlaps(e.timeline_range)]
            if len(hits) != 1:
                continue
            a = hits[0]
            back = [x for x in es if x.timeline_range.overlaps(a.timeline_range)]
            if len(back) != 1:
                continue
            if self.overlaps_unknown(key, a.timeline_range):
                continue
            hull = _hull((a.timeline_range, e.timeline_range))
            self.record(
                RoundTripChange(
                    _change_id("E", e),
                    ChangeKind.REPLACED,
                    e,
                    (a,),
                    IdentityStrength.UNKNOWN,
                    timeline_delta=a.timeline_range.start - e.timeline_range.start,
                    regions=(ActualRegion(key, hull),),
                )
            )

    def neighbourhood(self, e: ClipPlacement) -> tuple[ActualRegion, ...]:
        key = e.track
        if key not in self.actual:
            return ()
        siblings = self.expected.get(key, [])
        prev_end = 0
        next_start: int | None = None
        for other in siblings:
            mapped = self.e_to_a.get((key, other.item_index))
            same = tuple(a for a in mapped or () if a.track == key)
            if not same:
                continue
            if other.timeline_range.start < e.timeline_range.start:
                prev_end = max(prev_end, max(a.timeline_range.end for a in same))
            elif other.timeline_range.start > e.timeline_range.start and next_start is None:
                next_start = min(a.timeline_range.start for a in same)
        if next_start is None:
            frame_range = FrameRange(prev_end, prev_end + e.timeline_range.duration)
        elif next_start > prev_end:
            frame_range = FrameRange(prev_end, next_start)
        else:
            low = min(prev_end, next_start)
            frame_range = FrameRange(max(0, low - 1), max(prev_end, next_start) + 1)
        return (ActualRegion(key, frame_range),)

    def finish(self, keys: list[TrackKey]) -> None:
        for key in keys:
            for e in self.leftovers_e(key):
                # An unmatched clip may be hidden inside an UNSUPPORTED region: UNKNOWN.
                hidden = self.kind_has_unknown(key.kind)
                self.record(
                    RoundTripChange(
                        _change_id("E", e),
                        ChangeKind.UNKNOWN if hidden else ChangeKind.REMOVED_BY_HUMAN,
                        e,
                        (),
                        IdentityStrength.UNKNOWN,
                        DiffReason.UNSUPPORTED_REGION if hidden else DiffReason.NONE,
                        regions=self.neighbourhood(e),
                    )
                )
        for key in keys:
            for a in self.leftovers_a(key):
                if self.overlaps_unknown(key, a.timeline_range):
                    self.record(self.unknown(None, (a,), DiffReason.UNSUPPORTED_REGION))
                else:
                    self.record(
                        RoundTripChange(
                            _change_id("A", a),
                            ChangeKind.ADDED_BY_HUMAN,
                            None,
                            (a,),
                            IdentityStrength.UNKNOWN,
                            regions=(ActualRegion(key, a.timeline_range),),
                        )
                    )

    def run(self) -> tuple[RoundTripChange, ...]:
        keys = sorted(set(self.expected) | set(self.actual), key=_key_order)
        for key in keys:
            self.same_track(key)
        self.cross_track(keys)
        for key in keys:
            self.replaced(key)
        self.finish(keys)
        return tuple(sorted(self.changes, key=_change_sort))


def _change_sort(change: RoundTripChange) -> tuple[int, tuple[int, int], int, str]:
    if change.expected is not None:
        p = change.expected
        return (0, _key_order(p.track), p.item_index, change.change_id)
    p = change.actual[0]
    return (1, _key_order(p.track), p.item_index, change.change_id)


def _extents(expected: HandoffTimeline, actual: ReimportedTimeline) -> tuple[TrackExtent, ...]:
    expected_names = {key: track.name for key, track in track_keys(expected)}
    return tuple(
        TrackExtent(key, expected_names.get(key, f"ROUNDTRIP:{key.label}"), track.duration)
        for key, track in track_keys(actual)
    )


def _whole_unknown(
    expected: HandoffTimeline,
    actual: ReimportedTimeline | None,
    artifact_ref: RoundTripArtifactRef,
    basis: MediaIdentityBasis,
    reasons: tuple[DiffReason, ...],
    regions: tuple[UnknownRegion, ...],
    diagnostics: tuple[HandoffDiagnostic, ...],
) -> RoundTripDiff:
    changes: list[RoundTripChange] = []
    for _, placements in sorted(_placements(expected).items(), key=lambda kv: _key_order(kv[0])):
        for e in placements:
            changes.append(
                RoundTripChange(
                    _change_id("E", e),
                    ChangeKind.UNKNOWN,
                    e,
                    (),
                    IdentityStrength.UNKNOWN,
                    reasons[0],
                )
            )
    if actual is not None:
        for key, placements in sorted(
            _placements(actual).items(), key=lambda kv: _key_order(kv[0])
        ):
            for a in placements:
                changes.append(
                    RoundTripChange(
                        _change_id("A", a),
                        ChangeKind.UNKNOWN,
                        None,
                        (a,),
                        IdentityStrength.UNKNOWN,
                        reasons[0],
                        regions=(ActualRegion(key, a.timeline_range),),
                    )
                )
    rate = expected.rate if actual is None else actual.rate
    return RoundTripDiff(
        timeline_digest(expected),
        None if actual is None else timeline_digest(actual),
        artifact_ref,
        basis,
        DiffStatus.UNKNOWN,
        reasons,
        tuple(changes),
        regions,
        () if actual is None else _extents(expected, actual),
        frames_per_24_hours(rate),
        diagnostics,
        evidence_class=artifact_ref.evidence_class,
    )


ExpectedSplits = Mapping[str, Iterable[int]]  # track name or KIND:n label -> frames


def resolve_expected_splits(
    timeline: TimelineStructure, splits: ExpectedSplits | None
) -> dict[TrackKey, frozenset[int]]:
    """Map listed split frames to tracks (name or ``KIND:n`` label, like LAYER-001
    overrides). Unknown, ambiguous or duplicate references and non-positive frames
    refuse (ValueError); nothing is guessed."""
    if splits is None:
        return {}
    keyed = track_keys(timeline)
    result: dict[TrackKey, frozenset[int]] = {}
    for reference, frames in splits.items():
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("Split track reference must be a nonempty string")
        wanted = reference.strip()
        hits = [
            key
            for key, track in keyed
            if track.name == wanted or key.label.casefold() == wanted.casefold()
        ]
        if len(hits) != 1:
            raise ValueError(f"Split track {wanted!r} matches {len(hits)} tracks; nothing guessed")
        values = frozenset(frames)
        if any(type(f) is not int or f <= 0 for f in values):
            raise ValueError("Split frames must be positive int timeline frames")
        if hits[0] in result:
            raise ValueError(f"Duplicate split list for {hits[0].label}")
        if values:
            result[hits[0]] = values
    return result


def diff_roundtrip(
    expected: HandoffTimeline,
    actual: ReimportedTimeline,
    *,
    artifact_ref: RoundTripArtifactRef,
    unknown_regions: tuple[UnknownRegion, ...] = (),
    read_diagnostics: tuple[HandoffDiagnostic, ...] = (),
    expected_splits: ExpectedSplits | None = None,
) -> RoundTripDiff:
    """Deterministic Expected-vs-Actual round-trip diff, digest-bound to both artifacts.

    The media identity basis follows ``artifact_ref.format``: OTIO carries our
    ``media_id`` metadata (STRONG possible); xmeml only carries a display name
    and path (WEAK at best). OTIO clips whose metadata the NLE dropped
    (``actual.path_identified_media_ids``) are matched by path + source range
    with WEAK identity instead of making the whole diff UNKNOWN.

    ``expected_splits`` (INT-002): split frames we listed to the editor (razor
    assist), in Actual timeline frames per track. A split exactly at listed frames
    is ``NEUTRAL_SPLIT`` (no HARD_LOCK); see :func:`contiguous_split_frames`.
    """
    if not isinstance(expected, HandoffTimeline):
        raise TypeError("Expected must be a HandoffTimeline (Expected artifact)")
    if not isinstance(actual, ReimportedTimeline):
        raise TypeError("Actual must be a ReimportedTimeline (re-read, never native)")
    if not isinstance(artifact_ref, RoundTripArtifactRef):
        raise TypeError("A RoundTripArtifactRef is required")
    if actual.evidence_class != artifact_ref.evidence_class:
        raise ValueError("The Actual and its artifact reference carry different evidence classes")
    regions = tuple(unknown_regions)
    if any(not isinstance(r, UnknownRegion) for r in regions):
        raise TypeError("Unknown regions must be UnknownRegion values")
    splits = resolve_expected_splits(expected, expected_splits)
    split_binding = tuple(
        (key, tuple(sorted(frames)))
        for key, frames in sorted(splits.items(), key=lambda kv: _key_order(kv[0]))
    )
    diagnostics = tuple(read_diagnostics)
    basis = _BASIS_BY_FORMAT[artifact_ref.format]
    if basis is MediaIdentityBasis.METADATA and actual.path_identified_media_ids:
        basis = MediaIdentityBasis.PATH_FALLBACK
    reasons: list[DiffReason] = []
    if basis is MediaIdentityBasis.UNKNOWN:
        reasons.append(DiffReason.UNKNOWN_FORMAT)
    if expected.rate != actual.rate:
        reasons.append(DiffReason.RATE_MISMATCH)
    if expected.start_frame != actual.start_frame:
        reasons.append(DiffReason.START_MISMATCH)
    if reasons:
        return _whole_unknown(
            expected, actual, artifact_ref, basis, tuple(reasons), regions, diagnostics
        )
    differ_basis = (
        MediaIdentityBasis.METADATA if basis is MediaIdentityBasis.PATH_FALLBACK else basis
    )
    findings = compare_layers(expected, actual)
    regions = resolve_passthrough_regions(regions, expected, actual, findings)
    changes = _Differ(expected, actual, differ_basis, regions, splits).run()
    partial = bool(regions) or any(c.kind is ChangeKind.UNKNOWN for c in changes)
    return RoundTripDiff(
        timeline_digest(expected),
        timeline_digest(actual),
        artifact_ref,
        basis,
        DiffStatus.PARTIAL if partial else DiffStatus.COMPLETE,
        (DiffReason.UNSUPPORTED_REGION,) if regions else (),
        changes,
        regions,
        _extents(expected, actual),
        frames_per_24_hours(actual.rate),
        diagnostics,
        findings,
        split_binding,
        artifact_ref.evidence_class,
    )


def diff_unreadable_roundtrip(
    expected: HandoffTimeline,
    *,
    artifact_ref: RoundTripArtifactRef,
    read_diagnostics: tuple[HandoffDiagnostic, ...],
) -> RoundTripDiff:
    """A refused re-import: the whole diff is UNKNOWN; no Actual coordinates exist."""
    if not isinstance(expected, HandoffTimeline):
        raise TypeError("Expected must be a HandoffTimeline")
    basis = _BASIS_BY_FORMAT[artifact_ref.format]
    return _whole_unknown(
        expected,
        None,
        artifact_ref,
        basis,
        (DiffReason.ACTUAL_UNREADABLE,),
        (),
        tuple(read_diagnostics),
    )


def diff_xmeml_roundtrip(
    expected: HandoffTimeline,
    result: XmemlReadResult,
    *,
    artifact_ref: RoundTripArtifactRef,
    expected_splits: ExpectedSplits | None = None,
) -> RoundTripDiff:
    if not isinstance(result, XmemlReadResult):
        raise TypeError("An XmemlReadResult is required")
    if artifact_ref.format is not RoundTripFormat.XMEML:
        raise ValueError("Artifact reference format must be XMEML")
    if result.timeline is None:
        return diff_unreadable_roundtrip(
            expected, artifact_ref=artifact_ref, read_diagnostics=result.diagnostics
        )
    return diff_roundtrip(
        expected,
        result.timeline,
        artifact_ref=artifact_ref,
        unknown_regions=result.unknown_regions,
        read_diagnostics=result.diagnostics,
        expected_splits=expected_splits,
    )


def diff_otio_roundtrip(
    expected: HandoffTimeline,
    result: OtioReadResult,
    *,
    artifact_ref: RoundTripArtifactRef,
    expected_splits: ExpectedSplits | None = None,
) -> RoundTripDiff:
    if not isinstance(result, OtioReadResult):
        raise TypeError("An OtioReadResult is required")
    if artifact_ref.format is not RoundTripFormat.OTIO_JSON:
        raise ValueError("Artifact reference format must be OTIO_JSON")
    if result.timeline is None:
        return diff_unreadable_roundtrip(
            expected, artifact_ref=artifact_ref, read_diagnostics=result.diagnostics
        )
    return diff_roundtrip(
        expected,
        result.timeline,
        artifact_ref=artifact_ref,
        read_diagnostics=result.diagnostics,
        expected_splits=expected_splits,
    )


# --- protection ---------------------------------------------------------------


def _merge(ranges: list[FrameRange]) -> list[FrameRange]:
    merged: list[FrameRange] = []
    for frame_range in sorted(ranges, key=lambda r: (r.start, r.end)):
        if merged and frame_range.start <= merged[-1].end:
            last = merged.pop()
            merged.append(FrameRange(last.start, max(last.end, frame_range.end)))
        else:
            merged.append(frame_range)
    return merged


_LAYER_LOCKED = frozenset(
    {
        LayerFindingKind.MOVED,
        LayerFindingKind.CHANGED,
        LayerFindingKind.ADDED,
        LayerFindingKind.LOST,
    }
)


def derive_human_edit_protection(diff: RoundTripDiff) -> tuple[ProtectedRange, ...]:
    """HARD_LOCK every human-touched and every UNKNOWN region (Actual coordinates).

    Whole-UNKNOWN diffs and whole-track UNKNOWN regions lock ``[0, lock_horizon)``
    (24 hours of frames at the Actual rate) on the affected tracks. Raises
    :class:`ProtectionUnavailable` when no Actual coordinates exist.
    """
    if not isinstance(diff, RoundTripDiff):
        raise TypeError("A RoundTripDiff is required")
    if diff.actual_digest is None:
        raise ProtectionUnavailable(
            "Actual unreadable: no coordinates; treat the whole timeline as untouchable"
        )
    track_ids = {extent.track: extent.protection_track_id for extent in diff.actual_tracks}
    whole = FrameRange(0, diff.lock_horizon)
    by_track: dict[TrackKey, list[FrameRange]] = {}

    def add(track: TrackKey, frame_range: FrameRange) -> None:
        if track not in track_ids:
            return  # no Actual track: nothing to lock in Actual coordinates
        by_track.setdefault(track, []).append(frame_range)

    if diff.status is DiffStatus.UNKNOWN:
        for track in track_ids:
            add(track, whole)
    for change in diff.changes:
        if change.kind is ChangeKind.UNKNOWN or change.human_touched:
            for region in change.regions:
                add(region.track, region.frame_range)
    for unknown in diff.unknown_regions:
        add(unknown.track, whole if unknown.frame_range is None else unknown.frame_range)
    for finding in diff.layer_findings:
        # LAYER-001: a moved / changed / added / lost pass-through item or a changed
        # track state is a human (or NLE) change: lock it like any other.
        if finding.kind in _LAYER_LOCKED:
            frame_range = finding.actual_range or finding.expected_range
            add(finding.track, whole if frame_range is None else frame_range)
        elif finding.kind is LayerFindingKind.TRACK_STATE_CHANGED:
            add(finding.track, whole)
    result: list[ProtectedRange] = []
    for track in sorted(by_track, key=_key_order):
        for frame_range in _merge(by_track[track]):
            result.append(ProtectedRange(TrackId(track_ids[track]), frame_range))
    return tuple(result)
