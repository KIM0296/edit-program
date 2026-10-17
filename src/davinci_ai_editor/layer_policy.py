"""LAYER-001: per-track edit policy and layer preservation for approved cuts.

Product precondition (Free and Studio): layers are never merged. Until the
final render every track is preserved and each track is edited on its own.

Per-track policy for one approved cut (``TrackEditPolicy``):

- ``CUT_WITH_SOURCE``: the approved range is removed from this track (clips are
  split 1:1, later items ripple left).
- ``SHIFT_WITH_RIPPLE``: nothing on this track is cut; items entirely after the
  cut move left by the removed duration, items entirely before stay. This is a
  ripple delete of an *empty* range, so it is only allowed when no item of the
  track touches the removed range.
- ``KEEP_IN_PLACE``: nothing on this track is cut or moved.
- ``UNKNOWN``: never applied.

Default assignment per cut: a track whose items covering the cut range all come
from the candidate's source media (the dialogue clip and its linked A/V) is
``CUT_WITH_SOURCE``; every other track is ``SHIFT_WITH_RIPPLE``. ``KEEP`` is
never a default. Users override per track (track name or ``KIND:n`` label) in
the confirmation input; an override applies to every cut.

Blocking issues skip the cut (never split, truncate or drop automatically):

- ``LAYER_CONFLICT``: an item on a SHIFT/KEEP track spans or partially overlaps
  the removed range (a music bed or title running across the cut). Only an
  explicit ``CUT_WITH_SOURCE`` override for that track lets the cut through.
- ``LAYER_UNSUPPORTED_ITEM``: a pass-through item (generator, transition,
  nested sequence, retimed or otherwise unmodelled clip) would have to be cut,
  or its extent is UNKNOWN on a track that has to change.

Warnings (shown in the confirmation and bound by its digest):
``SYNC_SHIFT`` (a KEEP track next to rippling tracks: lists what will no longer
line up), ``EFFECT_SPLIT_REVIEW`` (a clipitem with filters is cut: the filter
elements are kept on each piece but keyframes may not line up) and
``MARKER_MOVED_TO_CUT`` (a sequence marker inside a removed range is kept and
moved to the cut point, never dropped).

Layer preservation checks (:func:`compare_layers`) compare two timelines track
by track: same track set and order per kind, same track state (enabled /
locked / attributes / settings), and every pass-through item present verbatim
(MATCH), moved with identical content (MOVED), changed (CHANGED, UNKNOWN), lost
(LOST) or added (ADDED). RT-001 and VER-001 consume these findings.

No rendering, no media, no Resolve API.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum

from .domain import FrameRange, RippleDisplacement, TrackId
from .handoff_model import (
    HandoffClip,
    HandoffGap,
    HandoffItem,
    HandoffMarker,
    HandoffTrack,
    HandoffTrackKind,
    PassthroughItem,
    SequenceMarker,
    TimelineStructure,
)
from .layer_xml import content_key, cut_piece_raw, marker_raw_at, raw_markers, shifted_raw
from .xmeml_reader import TrackKey, UnknownRegion, UnsupportedConstruct, track_keys


class TrackEditPolicy(str, Enum):
    UNKNOWN = "UNKNOWN"
    CUT_WITH_SOURCE = "CUT_WITH_SOURCE"
    SHIFT_WITH_RIPPLE = "SHIFT_WITH_RIPPLE"
    KEEP_IN_PLACE = "KEEP_IN_PLACE"


RIPPLING = frozenset({TrackEditPolicy.CUT_WITH_SOURCE, TrackEditPolicy.SHIFT_WITH_RIPPLE})


class PolicySource(str, Enum):
    UNKNOWN = "UNKNOWN"
    DEFAULT = "DEFAULT"
    OVERRIDE = "OVERRIDE"


class LayerIssueCode(str, Enum):
    UNKNOWN = "UNKNOWN"
    LAYER_CONFLICT = "LAYER_CONFLICT"
    LAYER_UNSUPPORTED_ITEM = "LAYER_UNSUPPORTED_ITEM"
    SYNC_SHIFT = "SYNC_SHIFT"
    EFFECT_SPLIT_REVIEW = "EFFECT_SPLIT_REVIEW"
    MARKER_MOVED_TO_CUT = "MARKER_MOVED_TO_CUT"
    LAYER_LOSS_RISK = "LAYER_LOSS_RISK"


BLOCKING_CODES = frozenset({LayerIssueCode.LAYER_CONFLICT, LayerIssueCode.LAYER_UNSUPPORTED_ITEM})


class TrackEffectKind(str, Enum):
    UNKNOWN = "UNKNOWN"
    CUT = "CUT"
    SHIFTED = "SHIFTED"
    UNCHANGED = "UNCHANGED"
    CONFLICT = "CONFLICT"


class LayerFindingKind(str, Enum):
    UNKNOWN = "UNKNOWN"
    MATCH = "MATCH"
    MOVED = "MOVED"
    CHANGED = "CHANGED"
    LOST = "LOST"
    ADDED = "ADDED"
    TRACK_MISSING = "TRACK_MISSING"
    TRACK_ADDED = "TRACK_ADDED"
    TRACK_STATE_CHANGED = "TRACK_STATE_CHANGED"


def _typed(value: object, enum: type[Enum], label: str) -> None:
    if not isinstance(value, enum):
        raise TypeError(f"Typed {label} required")


@dataclass(frozen=True)
class TrackPolicyOverride:
    """User input: ``track`` is an Actual track name (``Audio 3``) or label (``AUDIO:3``)."""

    track: str
    policy: TrackEditPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.track, str) or not self.track.strip():
            raise ValueError("Override track must be a nonempty string")
        _typed(self.policy, TrackEditPolicy, "policy")
        if self.policy is TrackEditPolicy.UNKNOWN:
            raise ValueError("An override must name a concrete policy, never UNKNOWN")


@dataclass(frozen=True)
class TrackPolicyAssignment:
    track: TrackKey
    track_name: str
    policy: TrackEditPolicy
    source: PolicySource

    def __post_init__(self) -> None:
        if not isinstance(self.track, TrackKey):
            raise TypeError("Assignment requires a TrackKey")
        _typed(self.policy, TrackEditPolicy, "policy")
        _typed(self.source, PolicySource, "policy source")
        if self.policy is TrackEditPolicy.UNKNOWN or self.source is PolicySource.UNKNOWN:
            raise ValueError("UNKNOWN policy is never assigned to an approved cut")


@dataclass(frozen=True)
class LayerIssue:
    code: LayerIssueCode
    candidate_id: str
    track: TrackKey | None
    track_name: str
    detail: str

    def __post_init__(self) -> None:
        _typed(self.code, LayerIssueCode, "issue code")
        if self.track is not None and not isinstance(self.track, TrackKey):
            raise TypeError("Issue track must be a TrackKey or None")
        for value in (self.candidate_id, self.track_name, self.detail):
            if not isinstance(value, str):
                raise TypeError("Issue text fields must be strings")

    def render(self) -> str:
        where = f" {self.track_name} [{self.track.label}]" if self.track is not None else ""
        who = f" {self.candidate_id}" if self.candidate_id else ""
        return f"{self.code.value}{who}{where}: {self.detail}"


@dataclass(frozen=True)
class TrackEffect:
    """Per-track result of the approved cuts (shown in the confirmation)."""

    track: TrackKey
    track_name: str
    effect: TrackEffectKind
    cut_frames: int
    shift_frames: int
    override: TrackEditPolicy | None
    conflicts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "conflicts", tuple(self.conflicts))
        _typed(self.effect, TrackEffectKind, "effect")
        if self.override is not None:
            _typed(self.override, TrackEditPolicy, "override")
        if type(self.cut_frames) is not int or type(self.shift_frames) is not int:
            raise TypeError("Frame counts must be ints")

    def render(self) -> str:
        policy = "per-cut default" if self.override is None else f"{self.override.value} (override)"
        parts: list[str] = []
        if self.cut_frames:
            parts.append(f"cut {self.cut_frames}f")
        if self.shift_frames:
            parts.append(f"shifted by -{self.shift_frames}f")
        if not parts:
            parts.append("unchanged")
        if self.conflicts:
            parts.append("conflict: " + ", ".join(self.conflicts))
        return (
            f"{self.track_name} [{self.track.label}] {policy} -> "
            f"{self.effect.value}: {'; '.join(parts)}"
        )


# --- layer item views ------------------------------------------------------------


@dataclass(frozen=True)
class LayerItemView:
    """A modelled clip or a pass-through item of one track, in timeline coordinates."""

    track: TrackKey
    track_name: str
    label: str
    timeline_range: FrameRange | None
    media_id: str | None
    clip: HandoffClip | None
    passthrough: PassthroughItem | None
    link_group: str | None = None

    @property
    def describe(self) -> str:
        kind = "clip" if self.passthrough is None else self.passthrough.kind.value
        extent = self.timeline_range
        where = "[UNKNOWN extent]" if extent is None else f"[{extent.start},{extent.end})"
        return f"{kind} {self.label!r} {where}"


def track_items(key: TrackKey, track: HandoffTrack) -> tuple[LayerItemView, ...]:
    result: list[LayerItemView] = []
    for start, clip in track.placements():
        result.append(
            LayerItemView(
                key,
                track.name,
                clip.name,
                FrameRange(start, start + clip.duration),
                clip.media.media_id,
                clip,
                None,
                clip.link_group,
            )
        )
    for item in track.passthrough:
        result.append(
            LayerItemView(
                key,
                track.name,
                item.label,
                item.timeline_range,
                item.media_id,
                None,
                item,
                item.link_group,
            )
        )
    return tuple(result)


def _touches(view: LayerItemView, cut: FrameRange) -> bool:
    return view.timeline_range is None or view.timeline_range.overlaps(cut)


# --- policy -------------------------------------------------------------------------


def resolve_overrides(
    timeline: TimelineStructure, overrides: Sequence[TrackPolicyOverride]
) -> dict[TrackKey, TrackEditPolicy]:
    """Map overrides to tracks; unknown, ambiguous or duplicate references refuse."""
    keyed = track_keys(timeline)
    result: dict[TrackKey, TrackEditPolicy] = {}
    for override in overrides:
        if not isinstance(override, TrackPolicyOverride):
            raise TypeError("Overrides must be TrackPolicyOverride values")
        wanted = override.track.strip()
        hits = [
            key
            for key, track in keyed
            if track.name == wanted or key.label.casefold() == wanted.casefold()
        ]
        if len(hits) != 1:
            raise ValueError(
                f"Override track {wanted!r} matches {len(hits)} tracks; nothing is guessed"
            )
        if hits[0] in result:
            raise ValueError(f"Duplicate override for {hits[0].label}")
        result[hits[0]] = override.policy
    return result


def default_policy(
    views: Sequence[LayerItemView],
    cut: FrameRange,
    candidate_media: str,
    candidate_link: str | None = None,
) -> TrackEditPolicy:
    """CUT when every item covering the cut is the candidate's source media or is in
    the candidate clip's file ``<link>`` group (e.g. separate-recorder audio)."""

    def with_source(view: LayerItemView) -> bool:
        if view.media_id == candidate_media:
            return True
        return candidate_link is not None and view.link_group == candidate_link

    covering = [v for v in views if _touches(v, cut)]
    if covering and all(with_source(v) for v in covering):
        return TrackEditPolicy.CUT_WITH_SOURCE
    return TrackEditPolicy.SHIFT_WITH_RIPPLE


def assign_policies(
    timeline: TimelineStructure,
    cut: FrameRange,
    candidate_media: str,
    overrides: Mapping[TrackKey, TrackEditPolicy],
    candidate_link: str | None = None,
) -> tuple[TrackPolicyAssignment, ...]:
    result: list[TrackPolicyAssignment] = []
    for key, track in track_keys(timeline):
        override = overrides.get(key)
        if override is not None:
            result.append(TrackPolicyAssignment(key, track.name, override, PolicySource.OVERRIDE))
            continue
        policy = default_policy(track_items(key, track), cut, candidate_media, candidate_link)
        result.append(TrackPolicyAssignment(key, track.name, policy, PolicySource.DEFAULT))
    return tuple(result)


def check_cut_layers(
    timeline: TimelineStructure,
    cut: FrameRange,
    candidate_id: str,
    assignments: Sequence[TrackPolicyAssignment],
) -> tuple[tuple[LayerIssue, ...], tuple[LayerIssue, ...]]:
    """(blocking issues, warnings) for one cut under the given per-track policies."""
    policies = {a.track: a.policy for a in assignments}
    blocking: list[LayerIssue] = []
    warnings: list[LayerIssue] = []
    keep_after: list[str] = []
    rippling = any(p in RIPPLING for p in policies.values())
    span = f"[{cut.start},{cut.end})"
    for key, track in track_keys(timeline):
        policy = policies.get(key, TrackEditPolicy.UNKNOWN)
        views = track_items(key, track)

        def issue(
            code: LayerIssueCode, detail: str, key: TrackKey = key, name: str = track.name
        ) -> LayerIssue:
            return LayerIssue(code, candidate_id, key, name, detail)

        if policy is TrackEditPolicy.UNKNOWN:
            blocking.append(issue(LayerIssueCode.LAYER_CONFLICT, "track policy UNKNOWN"))
            continue
        for view in views:
            item = view.passthrough
            extent = view.timeline_range
            if policy is TrackEditPolicy.KEEP_IN_PLACE:
                if extent is not None and extent.overlaps(cut):
                    blocking.append(
                        issue(
                            LayerIssueCode.LAYER_CONFLICT,
                            f"{view.describe} overlaps the removed range {span} "
                            "on a KEEP_IN_PLACE track",
                        )
                    )
                elif extent is not None and extent.start >= cut.end and rippling:
                    keep_after.append(f"{track.name} {view.describe}")
                continue
            if extent is None:
                blocking.append(
                    issue(
                        LayerIssueCode.LAYER_UNSUPPORTED_ITEM,
                        f"{view.describe} has no determinable position; it cannot be moved "
                        f"for the cut {span}",
                    )
                )
                continue
            if not extent.overlaps(cut):
                continue
            if policy is TrackEditPolicy.SHIFT_WITH_RIPPLE:
                blocking.append(
                    issue(
                        LayerIssueCode.LAYER_CONFLICT,
                        f"{view.describe} spans or overlaps the removed range {span}; "
                        "it is not split or truncated (set this track to CUT_WITH_SOURCE "
                        "to cut it)",
                    )
                )
            elif item is not None and not item.cuttable:
                blocking.append(
                    issue(
                        LayerIssueCode.LAYER_UNSUPPORTED_ITEM,
                        f"{view.describe} lies in the removed range {span} and cannot be cut "
                        "without corrupting it",
                    )
                )
            elif item is not None and item.has_filters:
                warnings.append(
                    issue(
                        LayerIssueCode.EFFECT_SPLIT_REVIEW,
                        f"{view.describe} is cut at {span}; its filters are kept on every "
                        "piece but keyframes may not line up",
                    )
                )
    if keep_after:
        warnings.append(
            LayerIssue(
                LayerIssueCode.SYNC_SHIFT,
                candidate_id,
                None,
                "",
                f"KEEP_IN_PLACE items after {span} stay while other tracks ripple; "
                "no longer lined up: " + "; ".join(keep_after),
            )
        )
    return tuple(blocking), tuple(warnings)


def track_effects(
    timeline: TimelineStructure,
    applied: Sequence[tuple[FrameRange, Sequence[TrackPolicyAssignment]]],
    conflicts: Mapping[TrackKey, Sequence[str]],
    overrides: Mapping[TrackKey, TrackEditPolicy],
) -> tuple[TrackEffect, ...]:
    result: list[TrackEffect] = []
    for key, track in track_keys(timeline):
        cut_frames = 0
        shift_frames = 0
        for cut, assignments in applied:
            policy = next(a.policy for a in assignments if a.track == key)
            if policy is TrackEditPolicy.CUT_WITH_SOURCE:
                cut_frames += cut.duration
            elif policy is TrackEditPolicy.SHIFT_WITH_RIPPLE:
                shift_frames += cut.duration
        hits = tuple(sorted(set(conflicts.get(key, ()))))
        if cut_frames:
            effect = TrackEffectKind.CUT
        elif shift_frames:
            effect = TrackEffectKind.SHIFTED
        elif hits:
            effect = TrackEffectKind.CONFLICT
        else:
            effect = TrackEffectKind.UNCHANGED
        result.append(
            TrackEffect(key, track.name, effect, cut_frames, shift_frames, overrides.get(key), hits)
        )
    return tuple(result)


# --- apply (per track) -------------------------------------------------------------


def subtract(span: FrameRange, cuts: tuple[FrameRange, ...]) -> list[FrameRange]:
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


def ripple_delta(frame: int, cuts: tuple[FrameRange, ...]) -> int:
    return -sum(c.duration for c in cuts if c.end <= frame)


def piece_link_group(
    group: str | None, piece_start: int, split: bool, all_cuts: tuple[FrameRange, ...]
) -> str | None:
    """Link group of one piece of a split item.

    Pieces of linked items cut by the same approved cuts get the same suffix
    (the number of approved cuts before the piece), so piece k of the video stays
    linked with piece k of its audio; an unsplit item keeps its group.
    """
    if group is None or not split:
        return group
    return f"{group}.{sum(1 for c in all_cuts if c.end <= piece_start)}"


def _piece(
    clip: HandoffClip,
    span_start: int,
    piece: FrameRange,
    link_group: str | None,
) -> HandoffClip:
    offset = clip.source_range.start - span_start
    source = FrameRange(piece.start + offset, piece.end + offset)
    markers: tuple[HandoffMarker, ...] = tuple(
        m for m in clip.markers if source.contains(m.frame_range)
    )
    return replace(clip, source_range=source, markers=markers, link_group=link_group)


class LayerLossRisk(ValueError):
    """Applying would lose or corrupt a layer item; nothing is emitted."""


def _passthrough_after_cuts(
    item: PassthroughItem,
    remove: tuple[FrameRange, ...],
    cut_ranges: frozenset[FrameRange],
    all_cuts: tuple[FrameRange, ...],
) -> tuple[list[PassthroughItem], list[tuple[FrameRange, int]]]:
    """(resulting items, moved pieces as (original range, delta))."""
    extent = item.timeline_range
    if not remove:
        return [item], []
    if extent is None:
        raise LayerLossRisk(f"{item.kind.value} {item.label!r} has no position on a rippled track")
    touching = [c for c in remove if c.overlaps(extent)]
    if not touching:
        delta = ripple_delta(extent.start, remove)
        if delta == 0:
            return [item], []
        moved = replace(
            item,
            timeline_range=FrameRange(extent.start + delta, extent.end + delta),
            raw_xml=shifted_raw(item.raw_xml, delta),
        )
        return [moved], [(extent, delta)]
    source = item.source_range
    if source is None or any(c not in cut_ranges for c in touching):
        raise LayerLossRisk(f"{item.kind.value} {item.label!r} would have to be cut")
    pieces: list[PassthroughItem] = []
    moves: list[tuple[FrameRange, int]] = []
    offset = source.start - extent.start
    split_pieces = subtract(extent, remove)
    for piece in split_pieces:
        delta = ripple_delta(piece.start, remove)
        piece_source = FrameRange(piece.start + offset, piece.end + offset)
        start = piece.start + delta
        pieces.append(
            replace(
                item,
                timeline_range=FrameRange(start, start + piece.duration),
                source_range=piece_source,
                raw_xml=cut_piece_raw(item.raw_xml, start, piece_source),
                link_group=piece_link_group(
                    item.link_group, piece.start, len(split_pieces) > 1, all_cuts
                ),
            )
        )
        if delta:
            moves.append((piece, delta))
    return pieces, moves


def apply_track_cuts(
    track: HandoffTrack,
    remove: tuple[FrameRange, ...],
    cut_ranges: frozenset[FrameRange],
    all_cuts: tuple[FrameRange, ...] | None = None,
) -> tuple[HandoffTrack, list[RippleDisplacement]]:
    """Ripple-delete ``remove`` (sorted) from one track; ``cut_ranges`` are its CUT ranges.

    ``all_cuts`` (every approved cut, default ``remove``) numbers the pieces of
    split linked items so their ``link_group`` stays paired across tracks.

    SHIFT ranges contain no item (checked at confirmation), so removing them only
    shrinks gaps and moves later items. Track identity, flags and settings are kept.
    """
    every_cut = remove if all_cuts is None else all_cuts
    items: list[HandoffItem] = []
    displacements: list[RippleDisplacement] = []
    cursor = 0
    for item in track.items:
        span = FrameRange(cursor, cursor + item.duration)
        cursor = span.end
        pieces = subtract(span, remove)
        if isinstance(item, HandoffClip) and any(
            c.overlaps(span) and c not in cut_ranges for c in remove
        ):
            raise LayerLossRisk(f"clip {item.name!r} would be cut on a non-CUT track")
        for piece in pieces:
            if isinstance(item, HandoffGap):
                if items and isinstance(items[-1], HandoffGap):
                    items[-1] = HandoffGap(items[-1].duration + piece.duration)
                else:
                    items.append(HandoffGap(piece.duration))
                continue
            group = piece_link_group(item.link_group, piece.start, len(pieces) > 1, every_cut)
            items.append(_piece(item, span.start, piece, group))
            delta = ripple_delta(piece.start, remove)
            if delta:
                displacements.append(RippleDisplacement(TrackId(track.name), piece, delta))
    while items and isinstance(items[-1], HandoffGap):
        items.pop()
    passthrough: list[PassthroughItem] = []
    for entry in track.passthrough:
        kept, moves = _passthrough_after_cuts(entry, remove, cut_ranges, every_cut)
        passthrough.extend(kept)
        displacements.extend(
            RippleDisplacement(TrackId(track.name), original, delta) for original, delta in moves
        )
    return replace(track, items=tuple(items), passthrough=tuple(passthrough)), displacements


def passthrough_markers(
    timeline: TimelineStructure,
) -> tuple[tuple[FrameRange, str], ...]:
    """Markers inside cuttable pass-through clipitems, in timeline coordinates."""
    result: list[tuple[FrameRange, str]] = []
    for _, track in track_keys(timeline):
        for item in track.passthrough:
            if item.source_range is None or item.timeline_range is None:
                continue
            offset = item.timeline_range.start - item.source_range.start
            for frame_range, name in raw_markers(item.raw_xml):
                result.append(
                    (FrameRange(frame_range.start + offset, frame_range.end + offset), name)
                )
    return tuple(result)


# --- layer preservation checks --------------------------------------------------------


@dataclass(frozen=True)
class LayerFinding:
    """Expected-vs-Actual comparison of one track or one pass-through item."""

    finding_id: str
    track: TrackKey
    kind: LayerFindingKind
    label: str
    expected_range: FrameRange | None
    actual_range: FrameRange | None
    expected_index: int | None
    actual_index: int | None
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.track, TrackKey):
            raise TypeError("Finding requires a TrackKey")
        _typed(self.kind, LayerFindingKind, "finding kind")
        for value in (self.finding_id, self.label, self.detail):
            if not isinstance(value, str):
                raise TypeError("Finding text fields must be strings")


def _track_state(track: HandoffTrack) -> dict[str, object]:
    return {
        "enabled": track.enabled,
        "locked": track.locked,
        "attributes": track.attributes,
        "settings": track.extra_xml,
    }


def _compare_track(
    key: TrackKey, expected: HandoffTrack, actual: HandoffTrack
) -> list[LayerFinding]:
    findings: list[LayerFinding] = []
    want, got = _track_state(expected), _track_state(actual)
    changed = sorted(name for name in want if want[name] != got[name])
    if changed:
        findings.append(
            LayerFinding(
                f"T:{key.label}",
                key,
                LayerFindingKind.TRACK_STATE_CHANGED,
                actual.name,
                None,
                None,
                None,
                None,
                "changed: " + ", ".join(changed),
            )
        )
    used: set[int] = set()
    pending: list[int] = []
    for index, item in enumerate(expected.passthrough):
        hit = next(
            (j for j, other in enumerate(actual.passthrough) if j not in used and other == item),
            None,
        )
        if hit is None:
            pending.append(index)
            continue
        used.add(hit)
        findings.append(
            LayerFinding(
                f"L:{key.label}:{index}",
                key,
                LayerFindingKind.MATCH,
                item.label,
                item.timeline_range,
                item.timeline_range,
                index,
                hit,
                f"{item.kind.value} preserved verbatim",
            )
        )
    for index in pending:
        item = expected.passthrough[index]
        same = [
            j
            for j, other in enumerate(actual.passthrough)
            if j not in used and content_key(other.raw_xml) == content_key(item.raw_xml)
        ]
        if len(same) == 1:
            other = actual.passthrough[same[0]]
            used.add(same[0])
            findings.append(
                LayerFinding(
                    f"L:{key.label}:{index}",
                    key,
                    LayerFindingKind.MOVED,
                    item.label,
                    item.timeline_range,
                    other.timeline_range,
                    index,
                    same[0],
                    f"{item.kind.value} content identical, position differs",
                )
            )
            continue
        extent = item.timeline_range
        overlapping = [
            j
            for j, other in enumerate(actual.passthrough)
            if j not in used
            and (
                extent is None
                or other.timeline_range is None
                or other.timeline_range.overlaps(extent)
            )
        ]
        if overlapping:
            used.update(overlapping)
            findings.append(
                LayerFinding(
                    f"L:{key.label}:{index}",
                    key,
                    LayerFindingKind.CHANGED,
                    item.label,
                    extent,
                    actual.passthrough[overlapping[0]].timeline_range,
                    index,
                    overlapping[0],
                    f"{item.kind.value} content differs (UNKNOWN; not interpreted)",
                )
            )
            continue
        findings.append(
            LayerFinding(
                f"L:{key.label}:{index}",
                key,
                LayerFindingKind.LOST,
                item.label,
                extent,
                None,
                index,
                None,
                f"{item.kind.value} missing in Actual",
            )
        )
    for j, other in enumerate(actual.passthrough):
        if j not in used:
            findings.append(
                LayerFinding(
                    f"LA:{key.label}:{j}",
                    key,
                    LayerFindingKind.ADDED,
                    other.label,
                    None,
                    other.timeline_range,
                    None,
                    j,
                    f"{other.kind.value} not in Expected",
                )
            )
    return findings


def compare_layers(
    expected: TimelineStructure, actual: TimelineStructure
) -> tuple[LayerFinding, ...]:
    """Track set/order/state and pass-through presence, deterministic order."""
    exp = dict(track_keys(expected))
    act = dict(track_keys(actual))
    findings: list[LayerFinding] = []
    for key, track in track_keys(expected):
        if key not in act:
            findings.append(
                LayerFinding(
                    f"T:{key.label}",
                    key,
                    LayerFindingKind.TRACK_MISSING,
                    track.name,
                    None,
                    None,
                    None,
                    None,
                    "track missing in Actual",
                )
            )
            continue
        findings.extend(_compare_track(key, track, act[key]))
    for key, track in track_keys(actual):
        if key in exp:
            continue
        findings.append(
            LayerFinding(
                f"T:{key.label}",
                key,
                LayerFindingKind.TRACK_ADDED,
                track.name,
                None,
                None,
                None,
                None,
                "track not in Expected",
            )
        )
        empty = HandoffTrack(track.name, track.kind)
        findings.extend(
            f for f in _compare_track(key, empty, track) if f.kind is LayerFindingKind.ADDED
        )
    findings.extend(_compare_sequence_markers(expected.markers, actual.markers))
    return tuple(findings)


_RESOLVED = frozenset({LayerFindingKind.MATCH, LayerFindingKind.MOVED, LayerFindingKind.ADDED})
_WHOLE_TRACK_CAPTURED = frozenset(
    {
        UnsupportedConstruct.TRACK_DISABLED,
        UnsupportedConstruct.TRANSITION_ADJACENT_BOUNDARY,
        UnsupportedConstruct.UNKNOWN_ELEMENT,
        UnsupportedConstruct.GENERATOR,
        UnsupportedConstruct.TRANSITION,
    }
)


def _covered(region: FrameRange, extents: list[FrameRange]) -> bool:
    cursor = region.start
    for extent in sorted(extents, key=lambda r: (r.start, r.end)):
        if extent.start > cursor:
            return False
        cursor = max(cursor, extent.end)
        if cursor >= region.end:
            return True
    return cursor >= region.end


def resolve_passthrough_regions(
    regions: tuple[UnknownRegion, ...],
    expected: TimelineStructure,
    actual: TimelineStructure,
    findings: tuple[LayerFinding, ...],
) -> tuple[UnknownRegion, ...]:
    """Drop UNKNOWN regions fully explained by verbatim-compared pass-through items.

    A region stays UNKNOWN when an Expected modelled clip overlaps it, when any
    Actual pass-through item in it changed (CHANGED), or when it is not fully
    covered by resolved (MATCH / MOVED / ADDED) items. Resolved non-MATCH items
    are still locked by RT-001 through the findings.
    """
    exp = dict(track_keys(expected))
    act = dict(track_keys(actual))
    resolved: dict[TrackKey, set[int]] = {}
    for finding in findings:
        if finding.kind in _RESOLVED and finding.actual_index is not None:
            resolved.setdefault(finding.track, set()).add(finding.actual_index)
    remaining: list[UnknownRegion] = []
    for region in regions:
        actual_track = act.get(region.track)
        expected_track = exp.get(region.track)
        if actual_track is None:
            remaining.append(region)
            continue
        done = resolved.get(region.track, set())
        expected_spans = (
            []
            if expected_track is None
            else [FrameRange(s, s + c.duration) for s, c in expected_track.placements()]
        )
        if region.frame_range is None:
            explained = (
                region.construct in _WHOLE_TRACK_CAPTURED
                and not expected_spans
                and not actual_track.placements()
                and len(done) == len(actual_track.passthrough)
            )
        else:
            frame_range = region.frame_range
            inside = [
                (j, p)
                for j, p in enumerate(actual_track.passthrough)
                if p.timeline_range is None or p.timeline_range.overlaps(frame_range)
            ]
            extents = [p.timeline_range for _, p in inside if p.timeline_range is not None]
            explained = (
                bool(inside)
                and all(j in done for j, _ in inside)
                and not any(span.overlaps(frame_range) for span in expected_spans)
                and _covered(frame_range, extents)
            )
        if not explained:
            remaining.append(region)
    return tuple(remaining)


# --- sequence (timeline) markers ------------------------------------------------------

SEQUENCE_TRACK = TrackKey(HandoffTrackKind.UNKNOWN, 1)
"""Pseudo track key for sequence-level findings (sequence markers live on no track)."""


def ripple_frame(frame: int, cuts: tuple[FrameRange, ...]) -> int:
    """Timeline position after removing ``cuts``; a frame inside a cut maps to the cut point."""
    return frame - sum(max(0, min(frame, c.end) - c.start) for c in cuts if c.start < frame)


def ripple_sequence_markers(
    markers: tuple[SequenceMarker, ...], cuts: tuple[FrameRange, ...]
) -> tuple[SequenceMarker, ...]:
    """Shift sequence markers with the timeline ripple; never drop one.

    A marker (or the part of it) inside a removed range is moved to the cut point;
    a marker collapsing to nothing becomes a one-frame marker at the cut point.
    """
    result: list[SequenceMarker] = []
    for marker in markers:
        start = ripple_frame(marker.frame_range.start, cuts)
        end = max(ripple_frame(marker.frame_range.end, cuts), start + 1)
        moved = FrameRange(start, end)
        if moved == marker.frame_range:
            result.append(marker)
        else:
            result.append(
                replace(marker, frame_range=moved, raw_xml=marker_raw_at(marker.raw_xml, moved))
            )
    return tuple(result)


def sequence_marker_warnings(
    markers: tuple[SequenceMarker, ...], cut: FrameRange, candidate_id: str
) -> tuple[LayerIssue, ...]:
    span = f"[{cut.start},{cut.end})"
    return tuple(
        LayerIssue(
            LayerIssueCode.MARKER_MOVED_TO_CUT,
            candidate_id,
            None,
            "",
            f"sequence marker {m.name!r} [{m.frame_range.start},{m.frame_range.end}) lies in "
            f"the removed range {span}; it is kept and moved to the cut point",
        )
        for m in markers
        if m.frame_range.overlaps(cut)
    )


def _compare_sequence_markers(
    expected: tuple[SequenceMarker, ...], actual: tuple[SequenceMarker, ...]
) -> list[LayerFinding]:
    findings: list[LayerFinding] = []
    used: set[int] = set()
    pending: list[int] = []
    for index, marker in enumerate(expected):
        hit = next((j for j, o in enumerate(actual) if j not in used and o == marker), None)
        if hit is None:
            pending.append(index)
            continue
        used.add(hit)
        findings.append(
            LayerFinding(
                f"M:SEQUENCE:{index}",
                SEQUENCE_TRACK,
                LayerFindingKind.MATCH,
                marker.name,
                marker.frame_range,
                marker.frame_range,
                index,
                hit,
                "sequence marker preserved verbatim",
            )
        )
    for index in pending:
        marker = expected[index]
        key = content_key(marker.raw_xml, ("in", "out"))
        same = [
            j
            for j, o in enumerate(actual)
            if j not in used and content_key(o.raw_xml, ("in", "out")) == key
        ]
        if len(same) == 1:
            used.add(same[0])
            findings.append(
                LayerFinding(
                    f"M:SEQUENCE:{index}",
                    SEQUENCE_TRACK,
                    LayerFindingKind.MOVED,
                    marker.name,
                    marker.frame_range,
                    actual[same[0]].frame_range,
                    index,
                    same[0],
                    "sequence marker content identical, position differs",
                )
            )
            continue
        findings.append(
            LayerFinding(
                f"M:SEQUENCE:{index}",
                SEQUENCE_TRACK,
                LayerFindingKind.LOST,
                marker.name,
                marker.frame_range,
                None,
                index,
                None,
                "sequence marker missing in Actual",
            )
        )
    for j, other in enumerate(actual):
        if j not in used:
            findings.append(
                LayerFinding(
                    f"MA:SEQUENCE:{j}",
                    SEQUENCE_TRACK,
                    LayerFindingKind.ADDED,
                    other.name,
                    None,
                    other.frame_range,
                    None,
                    j,
                    "sequence marker not in Expected",
                )
            )
    return findings
