"""VER-001 plan-vs-actual verification over a file round-trip (FILE_ROUNDTRIP only).

Given the approved Expected artifact (its intended cut list: the clips and gaps
it was supposed to produce) and the RT-001 diff against a re-imported Actual
file, produce a :class:`VerificationReport`:

- per item: MATCH / MISSING_CUT / EXTRA_CUT / FRAME_DRIFT(delta) / MARKER_LOST /
  TRACK_FLATTENED / HUMAN_CHANGED / UNKNOWN, plus LAYER-001 layer items from
  ``diff.layer_findings`` (track ``T:<KIND>:<n>``, pass-through ``L:``/``LA:``):
  MATCH (present verbatim), FRAME_DRIFT (same content, moved), LAYER_LOST (item
  or track missing), LAYER_ADDED, TRACK_STATE_CHANGED (enabled / locked /
  attributes / settings) and UNKNOWN (content changed, not interpreted);
- overall: MATCH / MISMATCH / UNVERIFIED. Any UNKNOWN item, UNSUPPORTED region
  or whole-UNKNOWN diff makes the report UNVERIFIED; it is never MATCH.

Evidence class is the constant ``FILE_ROUNDTRIP``: the report is explicitly not
native evidence and not VERIFIED_LIVE, and it never satisfies a Safety gate or
promotes a candidate.

Attribution ("the human deliberately changed it" vs "the handoff lost it") is
decided only from explicit evidence, otherwise the item is UNKNOWN:

- ``ActualProvenance.IMMEDIATE_REEXPORT``: the user declared the file was
  exported right after import with no hand edits, so every discrepancy is a
  handoff loss (basis ``USER_DECLARED_NO_EDITS``).
- ``AFTER_HUMAN_EDIT`` with a *baseline* RT-001 diff (an immediate re-export
  taken before editing): a discrepancy absent from the baseline is
  HUMAN_CHANGED; the same discrepancy in the baseline is a handoff loss; any
  other combination is UNKNOWN.
- ``AFTER_HUMAN_EDIT`` without a baseline: a discrepancy whose RT-001 change IDs
  were all acknowledged by the user is HUMAN_CHANGED; otherwise UNKNOWN.

HUMAN_CHANGED is not an error: a report whose only deviations are
HUMAN_CHANGED is MATCH with ``human_changed_count > 0``.

Identity rule for MATCH (RT/VER decision 3): an item is MATCH only with STRONG
identity, or WEAK identity that is unique. WEAK identity (path / display name)
is unique when no *other* clip of the same track kind - in Expected or in
Actual - has the same media path with an overlapping source range (the WEAK
key is path + source range, as in the RT-001 matcher). Otherwise the item is
UNKNOWN with code ``IDENTITY_AMBIGUOUS`` and the report is UNVERIFIED.
"""

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from .domain import FrameRange
from .handoff_model import EVIDENCE_CLASS, HandoffClip, HandoffTimeline, HandoffTrackKind
from .layer_policy import LayerFinding, LayerFindingKind
from .roundtrip_diff import (
    AttributeChange,
    ChangeKind,
    ClipPlacement,
    DiffStatus,
    IdentityStrength,
    RoundTripArtifactRef,
    RoundTripChange,
    RoundTripDiff,
    path_key,
    timeline_digest,
)
from .trust_evidence import PreparedArtifactRevision, canonical_bytes
from .xmeml_reader import TrackKey, track_keys


class ItemStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    MATCH = "MATCH"
    MISSING_CUT = "MISSING_CUT"
    EXTRA_CUT = "EXTRA_CUT"
    FRAME_DRIFT = "FRAME_DRIFT"
    MARKER_LOST = "MARKER_LOST"
    TRACK_FLATTENED = "TRACK_FLATTENED"
    HUMAN_CHANGED = "HUMAN_CHANGED"
    # LAYER-001 layer preservation
    LAYER_LOST = "LAYER_LOST"
    LAYER_ADDED = "LAYER_ADDED"
    TRACK_STATE_CHANGED = "TRACK_STATE_CHANGED"


DEFECTS = frozenset(
    {
        ItemStatus.MISSING_CUT,
        ItemStatus.EXTRA_CUT,
        ItemStatus.FRAME_DRIFT,
        ItemStatus.MARKER_LOST,
        ItemStatus.TRACK_FLATTENED,
        ItemStatus.LAYER_LOST,
        ItemStatus.LAYER_ADDED,
        ItemStatus.TRACK_STATE_CHANGED,
    }
)

_LAYER_OBSERVED = {
    LayerFindingKind.MATCH: ItemStatus.MATCH,
    LayerFindingKind.MOVED: ItemStatus.FRAME_DRIFT,
    LayerFindingKind.CHANGED: ItemStatus.UNKNOWN,
    LayerFindingKind.LOST: ItemStatus.LAYER_LOST,
    LayerFindingKind.ADDED: ItemStatus.LAYER_ADDED,
    LayerFindingKind.TRACK_MISSING: ItemStatus.LAYER_LOST,
    LayerFindingKind.TRACK_ADDED: ItemStatus.LAYER_ADDED,
    LayerFindingKind.TRACK_STATE_CHANGED: ItemStatus.TRACK_STATE_CHANGED,
    LayerFindingKind.UNKNOWN: ItemStatus.UNKNOWN,
}


IDENTITY_AMBIGUOUS = "IDENTITY_AMBIGUOUS"


class VerificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"


class ActualProvenance(str, Enum):
    UNKNOWN = "UNKNOWN"
    IMMEDIATE_REEXPORT = "IMMEDIATE_REEXPORT"
    AFTER_HUMAN_EDIT = "AFTER_HUMAN_EDIT"


class Attribution(str, Enum):
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    HANDOFF_LOSS = "HANDOFF_LOSS"
    HUMAN_EDIT = "HUMAN_EDIT"


class AttributionBasis(str, Enum):
    NONE = "NONE"
    USER_DECLARED_NO_EDITS = "USER_DECLARED_NO_EDITS"
    BASELINE_REEXPORT = "BASELINE_REEXPORT"
    USER_ACKNOWLEDGED = "USER_ACKNOWLEDGED"


class IntendedKind(str, Enum):
    CLIP = "CLIP"
    GAP = "GAP"


@dataclass(frozen=True)
class IntendedItem:
    """One entry of the approved Expected cut list (Expected timeline coordinates)."""

    item_id: str
    track: TrackKey
    kind: IntendedKind
    timeline_range: FrameRange
    clip: HandoffClip | None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, IntendedKind) or not isinstance(self.track, TrackKey):
            raise TypeError("Typed intended item required")
        if (self.kind is IntendedKind.CLIP) != (self.clip is not None):
            raise ValueError("Clip items carry a clip; gap items do not")


def intended_cut_list(expected: HandoffTimeline) -> tuple[IntendedItem, ...]:
    """Clip IDs equal RT-001 Expected change IDs (``E:<KIND>:<n>:<index>``)."""
    if not isinstance(expected, HandoffTimeline):
        raise TypeError("A HandoffTimeline is required")
    items: list[IntendedItem] = []
    for key, track in track_keys(expected):
        cursor = 0
        for index, item in enumerate(track.items):
            frame_range = FrameRange(cursor, cursor + item.duration)
            if isinstance(item, HandoffClip):
                items.append(
                    IntendedItem(
                        f"E:{key.label}:{index}", key, IntendedKind.CLIP, frame_range, item
                    )
                )
            else:
                items.append(
                    IntendedItem(f"G:{key.label}:{index}", key, IntendedKind.GAP, frame_range, None)
                )
            cursor += item.duration
    return tuple(items)


@dataclass(frozen=True)
class FrameDrift:
    timeline_start_delta: int
    timeline_end_delta: int
    source_start_delta: int
    source_end_delta: int

    def __post_init__(self) -> None:
        values = (
            self.timeline_start_delta,
            self.timeline_end_delta,
            self.source_start_delta,
            self.source_end_delta,
        )
        if any(type(v) is not int for v in values):
            raise TypeError("Drift deltas must be ints")

    @property
    def delta(self) -> int:
        """Headline delta: timeline start shift in frames (exact, no tolerance)."""
        return self.timeline_start_delta


@dataclass(frozen=True)
class VerificationItem:
    item_id: str
    track: TrackKey
    status: ItemStatus
    observed: ItemStatus
    attribution: Attribution
    basis: AttributionBasis
    expected_range: FrameRange | None
    actual_ranges: tuple[FrameRange, ...]
    change_ids: tuple[str, ...]
    identity: IdentityStrength
    drift: FrameDrift | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "actual_ranges", tuple(self.actual_ranges))
        object.__setattr__(self, "change_ids", tuple(self.change_ids))
        for value, enum in (
            (self.status, ItemStatus),
            (self.observed, ItemStatus),
            (self.attribution, Attribution),
            (self.basis, AttributionBasis),
            (self.identity, IdentityStrength),
        ):
            if not isinstance(value, enum):
                raise TypeError("Typed verification item fields required")
        if self.observed is ItemStatus.HUMAN_CHANGED:
            raise ValueError("Observed discrepancy is a geometry code, never HUMAN_CHANGED")
        if self.status is ItemStatus.MATCH and self.observed is not ItemStatus.MATCH:
            raise ValueError("MATCH requires an observed MATCH")
        if (
            self.status is ItemStatus.HUMAN_CHANGED
            and self.attribution is not Attribution.HUMAN_EDIT
        ):
            raise ValueError("HUMAN_CHANGED requires HUMAN_EDIT attribution")
        if self.status in DEFECTS and self.attribution is not Attribution.HANDOFF_LOSS:
            raise ValueError("A reported defect requires HANDOFF_LOSS attribution")
        if (self.status is ItemStatus.FRAME_DRIFT) and self.drift is None:
            raise ValueError("FRAME_DRIFT requires a drift")


@dataclass(frozen=True)
class VerificationReport:
    approved_revision: PreparedArtifactRevision
    expected_digest: str
    actual_digest: str | None
    artifact: RoundTripArtifactRef
    diff_digest: str
    baseline_diff_digest: str | None
    provenance: ActualProvenance
    status: VerificationStatus
    items: tuple[VerificationItem, ...]
    reasons: tuple[str, ...]
    evidence_class: Literal["FILE_ROUNDTRIP"] = EVIDENCE_CLASS
    native_evidence: Literal[False] = False
    verified_live: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if (
            self.evidence_class != EVIDENCE_CLASS
            or self.native_evidence is not False
            or self.verified_live is not False
        ):
            raise ValueError("Round-trip verification is FILE_ROUNDTRIP: never native, never live")
        if not isinstance(self.status, VerificationStatus):
            raise TypeError("Typed overall status required")
        has_unknown = any(i.status is ItemStatus.UNKNOWN for i in self.items)
        has_defect = any(i.status in DEFECTS for i in self.items)
        if self.status is VerificationStatus.MATCH and (has_unknown or has_defect or self.reasons):
            raise ValueError("MATCH cannot contain UNKNOWN, defects or unverified reasons")
        if has_unknown and self.status is not VerificationStatus.UNVERIFIED:
            raise ValueError("Any UNKNOWN item makes the report UNVERIFIED")

    @property
    def human_changed_count(self) -> int:
        return sum(1 for i in self.items if i.status is ItemStatus.HUMAN_CHANGED)

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_bytes(self)).hexdigest()

    def item(self, item_id: str) -> VerificationItem:
        for item in self.items:
            if item.item_id == item_id:
                return item
        raise KeyError(item_id)


# --- observation (geometry only, no attribution) --------------------------------


@dataclass(frozen=True)
class _Observation:
    item_id: str
    track: TrackKey
    observed: ItemStatus
    expected_range: FrameRange | None
    actual: tuple[ClipPlacement, ...]
    change_ids: tuple[str, ...]
    identity: IdentityStrength
    drift: FrameDrift | None
    detail: str
    signature: tuple[object, ...]  # for baseline matching of actual-only items


def _marker_keys(clips: Iterable[HandoffClip]) -> frozenset[tuple[int, int, str, str]]:
    return frozenset(
        (m.frame_range.start, m.frame_range.end, m.name, m.note) for c in clips for m in c.markers
    )


def _drift(change: RoundTripChange) -> FrameDrift:
    expected = change.expected
    if expected is None or not change.actual:
        raise AssertionError("drift needs both sides")
    first, last = change.actual[0], change.actual[-1]
    return FrameDrift(
        first.timeline_range.start - expected.timeline_range.start,
        last.timeline_range.end - expected.timeline_range.end,
        first.source_range.start - expected.source_range.start,
        last.source_range.end - expected.source_range.end,
    )


def _media_key(clip: HandoffClip) -> tuple[str, str]:
    path = path_key(clip.media.target_path)
    return ("PATH", path) if path is not None else ("ID", clip.media.media_id)


def _kind_counts(keys: Iterable[TrackKey]) -> dict[HandoffTrackKind, int]:
    counts: dict[HandoffTrackKind, int] = {}
    for key in keys:
        counts[key.kind] = counts.get(key.kind, 0) + 1
    return counts


class _Observer:
    def __init__(self, expected: HandoffTimeline, diff: RoundTripDiff) -> None:
        self.diff = diff
        self.intended = intended_cut_list(expected)
        self.expected_counts = _kind_counts(k for k, _ in track_keys(expected))
        self.actual_keys = {extent.track for extent in diff.actual_tracks}
        self.actual_counts = _kind_counts(self.actual_keys)
        self.by_expected: dict[str, RoundTripChange] = {}
        for change in diff.changes:
            if change.expected is not None:
                placement = change.expected
                self.by_expected[f"E:{placement.track.label}:{placement.item_index}"] = change
        self.expected_media = [
            (item.track.kind, _media_key(item.clip), item.clip.source_range)
            for item in self.intended
            if item.clip is not None
        ]
        actual: dict[tuple[TrackKey, int], ClipPlacement] = {}
        for change in diff.changes:
            for a in change.actual:
                actual[(a.track, a.item_index)] = a
        self.actual_media = [
            (a.track.kind, _media_key(a.clip), a.source_range) for a in actual.values()
        ]

    def ambiguous(self, kind: HandoffTrackKind, clip: HandoffClip) -> bool:
        """WEAK identity is ambiguous when another same-kind clip shares path + source."""
        key = _media_key(clip)
        for media in (self.expected_media, self.actual_media):
            hits = sum(
                1 for k, m, r in media if k is kind and m == key and r.overlaps(clip.source_range)
            )
            if hits > 1:
                return True
        return False

    def flattened(self, key: TrackKey) -> bool:
        return self.actual_counts.get(key.kind, 0) < self.expected_counts.get(key.kind, 0)

    def clip(self, item: IntendedItem) -> _Observation:
        change = self.by_expected.get(item.item_id)
        if change is None or self.diff.status is DiffStatus.UNKNOWN:
            return self.make(item, ItemStatus.UNKNOWN, change, None, "No classification")
        kind = change.kind
        clip = item.clip
        if clip is None:
            raise AssertionError("clip item")
        observed = ItemStatus.MATCH
        drift: FrameDrift | None = None
        detail = kind.value
        if kind is ChangeKind.UNKNOWN:
            observed, detail = ItemStatus.UNKNOWN, f"UNKNOWN ({change.reason.value})"
        elif kind in (ChangeKind.REMOVED_BY_HUMAN, ChangeKind.MERGED, ChangeKind.REPLACED):
            observed = ItemStatus.MISSING_CUT
        elif kind is ChangeKind.SPLIT:
            observed = ItemStatus.EXTRA_CUT
        elif kind is ChangeKind.MOVED and change.track_changed:
            drift = _drift(change)
            if self.flattened(item.track):
                observed = ItemStatus.TRACK_FLATTENED
            else:
                observed, detail = ItemStatus.UNKNOWN, "Cross-track move without flattening"
        elif kind in (ChangeKind.MOVED, ChangeKind.TRIMMED):
            observed, drift = ItemStatus.FRAME_DRIFT, _drift(change)
            detail = f"{kind.value} {drift.delta:+d}"
        elif kind is ChangeKind.UNCHANGED:
            actual_clips = tuple(a.clip for a in change.actual)
            if AttributeChange.ENABLED in change.attribute_changes:
                observed = ItemStatus.MISSING_CUT if clip.enabled else ItemStatus.EXTRA_CUT
                detail = "enabled changed"
            elif not _marker_keys((clip,)) <= _marker_keys(actual_clips):
                observed, detail = ItemStatus.MARKER_LOST, "marker missing in Actual"
        if (
            observed is ItemStatus.MATCH
            and change.identity is not IdentityStrength.STRONG
            and (
                change.identity is not IdentityStrength.WEAK
                or self.ambiguous(item.track.kind, clip)
            )
        ):
            observed, detail = ItemStatus.UNKNOWN, IDENTITY_AMBIGUOUS
        return self.make(item, observed, change, drift, detail)

    def make(
        self,
        item: IntendedItem,
        observed: ItemStatus,
        change: RoundTripChange | None,
        drift: FrameDrift | None,
        detail: str,
    ) -> _Observation:
        actual = () if change is None else change.actual
        return _Observation(
            item.item_id,
            item.track,
            observed,
            item.timeline_range,
            actual,
            () if change is None else (change.change_id,),
            IdentityStrength.UNKNOWN if change is None else change.identity,
            drift,
            detail,
            (item.item_id,),
        )

    def gap(self, item: IntendedItem) -> _Observation:
        def result(observed: ItemStatus, ids: tuple[str, ...], detail: str) -> _Observation:
            return _Observation(
                item.item_id,
                item.track,
                observed,
                item.timeline_range,
                (),
                ids,
                IdentityStrength.UNKNOWN,
                None,
                detail,
                (item.item_id,),
            )

        if self.diff.status is DiffStatus.UNKNOWN:
            return result(ItemStatus.UNKNOWN, (), "Whole diff UNKNOWN")
        if item.track not in self.actual_keys:
            if self.flattened(item.track):
                return result(ItemStatus.TRACK_FLATTENED, (), "Track absent in Actual")
            return result(ItemStatus.UNKNOWN, (), "Track absent in Actual")
        for region in self.diff.unknown_regions:
            if region.track == item.track and (
                region.frame_range is None or region.frame_range.overlaps(item.timeline_range)
            ):
                return result(ItemStatus.UNKNOWN, (), "Overlaps UNSUPPORTED region")
        occupants = [
            c
            for c in self.diff.changes
            if any(
                a.track == item.track and a.timeline_range.overlaps(item.timeline_range)
                for a in c.actual
            )
        ]
        if not occupants:
            return result(ItemStatus.MATCH, (), "gap preserved")
        ids = tuple(sorted(c.change_id for c in occupants))
        kinds = {c.kind for c in occupants}
        if ChangeKind.UNKNOWN in kinds:
            return result(ItemStatus.UNKNOWN, ids, "Gap overlaps UNKNOWN content")
        if any(c.track_changed for c in occupants):
            observed = (
                ItemStatus.TRACK_FLATTENED
                if any(self.flattened(c.expected.track) for c in occupants if c.expected)
                else ItemStatus.UNKNOWN
            )
            return result(observed, ids, "Gap filled by cross-track content")
        if kinds & {ChangeKind.ADDED_BY_HUMAN, ChangeKind.SPLIT, ChangeKind.REPLACED}:
            return result(ItemStatus.EXTRA_CUT, ids, "Gap filled")
        return result(ItemStatus.FRAME_DRIFT, ids, "Neighbour drifted into gap")

    def actual_only(self) -> list[_Observation]:
        result: list[_Observation] = []
        for change in self.diff.changes:
            if change.expected is not None:
                continue
            a = change.actual[0]
            observed = (
                ItemStatus.EXTRA_CUT
                if change.kind is ChangeKind.ADDED_BY_HUMAN
                else ItemStatus.UNKNOWN
            )
            result.append(
                _Observation(
                    change.change_id,
                    a.track,
                    observed,
                    None,
                    change.actual,
                    (change.change_id,),
                    change.identity,
                    None,
                    change.kind.value,
                    (a.track, a.clip.media.media_id, a.source_range, observed),
                )
            )
        return result

    def layer(self, finding: LayerFinding) -> _Observation:
        """LAYER-001: track set/state and pass-through presence (verbatim compare)."""
        observed = _LAYER_OBSERVED[finding.kind]
        drift: FrameDrift | None = None
        if observed is ItemStatus.FRAME_DRIFT:
            if finding.expected_range is None or finding.actual_range is None:
                observed = ItemStatus.UNKNOWN
            else:
                drift = FrameDrift(
                    finding.actual_range.start - finding.expected_range.start,
                    finding.actual_range.end - finding.expected_range.end,
                    0,
                    0,
                )
        expected_range = finding.expected_range
        if finding.kind in (LayerFindingKind.ADDED, LayerFindingKind.TRACK_ADDED):
            expected_range = None
        return _Observation(
            finding.finding_id,
            finding.track,
            observed,
            expected_range,
            (),
            (finding.finding_id,),
            IdentityStrength.UNKNOWN,
            drift,
            f"{finding.kind.value}: {finding.label} - {finding.detail}",
            (finding.finding_id,)
            if expected_range is not None
            else (finding.finding_id, finding.kind, finding.actual_range),
        )

    def run(self) -> list[_Observation]:
        observations = [
            self.clip(item) if item.kind is IntendedKind.CLIP else self.gap(item)
            for item in self.intended
        ]
        layers = (
            [self.layer(f) for f in self.diff.layer_findings]
            if self.diff.status is not DiffStatus.UNKNOWN
            else []
        )
        return observations + self.actual_only() + layers


# --- attribution ----------------------------------------------------------------


def _same(a: _Observation, b: _Observation) -> bool:
    return a.observed is b.observed and a.drift == b.drift


def _attribute(
    observation: _Observation,
    provenance: ActualProvenance,
    baseline: dict[tuple[object, ...], _Observation] | None,
    acknowledged: frozenset[str],
) -> VerificationItem:
    observed = observation.observed

    def item(
        status: ItemStatus, attribution: Attribution, basis: AttributionBasis
    ) -> VerificationItem:
        return VerificationItem(
            observation.item_id,
            observation.track,
            status,
            observed,
            attribution,
            basis,
            observation.expected_range,
            tuple(a.timeline_range for a in observation.actual),
            observation.change_ids,
            observation.identity,
            observation.drift if status is not ItemStatus.MATCH else None,
            observation.detail,
        )

    if observed is ItemStatus.MATCH:
        return item(ItemStatus.MATCH, Attribution.NOT_APPLICABLE, AttributionBasis.NONE)
    if observed is ItemStatus.UNKNOWN:
        return item(ItemStatus.UNKNOWN, Attribution.UNKNOWN, AttributionBasis.NONE)
    if provenance is ActualProvenance.IMMEDIATE_REEXPORT:
        return item(observed, Attribution.HANDOFF_LOSS, AttributionBasis.USER_DECLARED_NO_EDITS)
    if baseline is not None:
        prior = baseline.get(observation.signature)
        if observation.expected_range is None:
            # actual-only: present in the baseline export -> handoff; absent -> human
            if prior is not None and _same(prior, observation):
                return item(observed, Attribution.HANDOFF_LOSS, AttributionBasis.BASELINE_REEXPORT)
            if prior is None:
                return item(
                    ItemStatus.HUMAN_CHANGED,
                    Attribution.HUMAN_EDIT,
                    AttributionBasis.BASELINE_REEXPORT,
                )
            return item(ItemStatus.UNKNOWN, Attribution.UNKNOWN, AttributionBasis.BASELINE_REEXPORT)
        if prior is not None and prior.observed is ItemStatus.MATCH:
            return item(
                ItemStatus.HUMAN_CHANGED, Attribution.HUMAN_EDIT, AttributionBasis.BASELINE_REEXPORT
            )
        if prior is not None and _same(prior, observation):
            return item(observed, Attribution.HANDOFF_LOSS, AttributionBasis.BASELINE_REEXPORT)
        return item(ItemStatus.UNKNOWN, Attribution.UNKNOWN, AttributionBasis.BASELINE_REEXPORT)
    if observation.change_ids and all(cid in acknowledged for cid in observation.change_ids):
        return item(
            ItemStatus.HUMAN_CHANGED, Attribution.HUMAN_EDIT, AttributionBasis.USER_ACKNOWLEDGED
        )
    return item(ItemStatus.UNKNOWN, Attribution.UNKNOWN, AttributionBasis.NONE)


def _sort_key(item: VerificationItem) -> tuple[int, str]:
    return (1 if item.item_id.startswith("A:") else 0, item.item_id)


def verify_roundtrip(
    approved: PreparedArtifactRevision,
    expected: HandoffTimeline,
    diff: RoundTripDiff,
    *,
    provenance: ActualProvenance,
    baseline: RoundTripDiff | None = None,
    acknowledged_change_ids: tuple[str, ...] = (),
) -> VerificationReport:
    """Verify the re-imported Actual against the approved Expected cut list.

    Refuses (``ValueError``) when the approval, the Expected and the diff are
    not bound to the same content digest: a stale plan is never verified.
    """
    if not isinstance(approved, PreparedArtifactRevision):
        raise TypeError("An approved PreparedArtifactRevision is required")
    if not isinstance(expected, HandoffTimeline) or not isinstance(diff, RoundTripDiff):
        raise TypeError("Expected HandoffTimeline and RoundTripDiff are required")
    if not isinstance(provenance, ActualProvenance):
        raise TypeError("Typed provenance required")
    digest = timeline_digest(expected)
    if not approved.matches(expected) or diff.expected_digest != digest:
        raise ValueError("Approval, Expected and diff are not bound to the same artifact")
    acknowledged = frozenset(acknowledged_change_ids)
    reasons: list[str] = []
    if diff.status is DiffStatus.UNKNOWN:
        reasons.extend(f"DIFF_{r.value}" for r in diff.reasons)
    if diff.unknown_regions:
        reasons.append("UNSUPPORTED_REGION")
    baseline_index: dict[tuple[object, ...], _Observation] | None = None
    if baseline is not None:
        if not isinstance(baseline, RoundTripDiff) or baseline.expected_digest != digest:
            raise ValueError("Baseline diff must be bound to the same Expected artifact")
        if (
            provenance is ActualProvenance.AFTER_HUMAN_EDIT
            and baseline.status is not DiffStatus.UNKNOWN
        ):
            baseline_index = {o.signature: o for o in _Observer(expected, baseline).run()}
    effective = (
        provenance
        if provenance is not ActualProvenance.UNKNOWN
        else ActualProvenance.AFTER_HUMAN_EDIT
    )
    items = tuple(
        sorted(
            (
                _attribute(o, effective, baseline_index, acknowledged)
                for o in _Observer(expected, diff).run()
            ),
            key=_sort_key,
        )
    )
    if any(i.status is ItemStatus.UNKNOWN and i.detail == IDENTITY_AMBIGUOUS for i in items):
        reasons.append(IDENTITY_AMBIGUOUS)
    if reasons or any(i.status is ItemStatus.UNKNOWN for i in items):
        status = VerificationStatus.UNVERIFIED
    elif any(i.status in DEFECTS for i in items):
        status = VerificationStatus.MISMATCH
    else:
        status = VerificationStatus.MATCH
    return VerificationReport(
        approved,
        digest,
        diff.actual_digest,
        diff.artifact,
        diff.digest,
        None if baseline is None else baseline.digest,
        provenance,
        status,
        items,
        tuple(reasons),
    )


# --- plain-text render ------------------------------------------------------------

KOREAN_LABELS = {
    "MATCH": "일치",
    "MISMATCH": "불일치",
    "UNVERIFIED": "검증 불가",
    "UNKNOWN": "알 수 없음",
    "MISSING_CUT": "컷 누락",
    "EXTRA_CUT": "추가 컷",
    "FRAME_DRIFT": "프레임 어긋남",
    "MARKER_LOST": "마커 유실",
    "TRACK_FLATTENED": "트랙 병합",
    "HUMAN_CHANGED": "사람이 수정함",
    "LAYER_LOST": "레이어 항목 유실",
    "LAYER_ADDED": "레이어 항목 추가",
    "TRACK_STATE_CHANGED": "트랙 상태 변경",
}


def _range(frame_range: FrameRange | None) -> str:
    return "-" if frame_range is None else f"[{frame_range.start},{frame_range.end})"


def render_report(report: VerificationReport, *, korean: bool = False) -> str:
    """Deterministic plain text for a review UI. Codes stay English."""

    def label(code: str) -> str:
        return f"{code} ({KOREAN_LABELS[code]})" if korean and code in KOREAN_LABELS else code

    lines = [
        "VER-001 round-trip verification",
        f"Evidence: {report.evidence_class} (file round-trip; not native, not live)",
        f"Overall: {label(report.status.value)}",
        (
            f"Artifact: {report.artifact.ref} {report.artifact.format.value} "
            f"sha256={report.artifact.text_sha256[:12]}"
        ),
        (
            f"Expected: {report.expected_digest[:12]}  Actual: "
            f"{(report.actual_digest or 'UNREADABLE')[:12]}  Provenance: {report.provenance.value}"
        ),
        f"Human changes: {report.human_changed_count}",
    ]
    if report.reasons:
        lines.append("Reasons: " + ", ".join(report.reasons))
    lines.append("Items:")
    for item in report.items:
        status = label(item.status.value)
        if item.drift is not None and item.status is ItemStatus.FRAME_DRIFT:
            status = f"{status} delta={item.drift.delta:+d}"
        actual = ",".join(_range(r) for r in item.actual_ranges) or "-"
        extra = ""
        if item.status is not item.observed:
            extra = f" observed={item.observed.value}"
        lines.append(
            f"  {item.item_id} {item.track.label} expected={_range(item.expected_range)} "
            f"actual={actual} {status}{extra} attribution={item.attribution.value} "
            f"basis={item.basis.value} identity={item.identity.value}"
        )
    return "\n".join(lines) + "\n"
