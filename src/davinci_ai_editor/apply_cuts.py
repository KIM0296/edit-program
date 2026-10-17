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

Cut semantics (LAYER-001 per-track policy, see ``layer_policy``): layers are
never merged and each track is edited on its own. For every approved cut each
track gets a ``TrackEditPolicy``: by default ``CUT_WITH_SOURCE`` for tracks
whose items covering the range come from the candidate's source media (the
dialogue clip and its linked A/V) and ``SHIFT_WITH_RIPPLE`` for every other
track (music beds, B-roll, titles, SFX: not cut, later items move left);
``KEEP_IN_PLACE`` only by user override. An item on a SHIFT/KEEP track that
touches the removed range skips the cut (``LAYER_CONFLICT``) unless the user
set that track to CUT; a pass-through item that would need cutting skips it
(``LAYER_UNSUPPORTED_ITEM``). On CUT tracks clips are split 1:1, gaps shrink
and later items move left. Every surviving clip piece or pass-through item that
moves is reported as a ``domain.RippleDisplacement`` (track id = Actual track
name, ``original_range`` = the piece in Actual coordinates, ``delta_frames`` <
0) - the same explicit displacement semantics as
``safety.propose_ripple_displacements``; nothing moves implicitly. The output
keeps exactly the Actual tracks (count, order, names, kinds, flags, settings);
pass-through items are kept verbatim. Sequence (timeline) markers ripple with
the timeline; one inside a removed range is kept and moved to the cut point
(``MARKER_MOVED_TO_CUT`` warning). File ``<link>`` groups count as linked A/V
for the default policy. Anything the new file could not carry (e.g. a
malformed sequence marker) makes apply refuse with ``LAYER_LOSS_RISK``.

The confirmation digest binds the resolved status of every candidate
(``CandidateStatus``) and an Actual digest with marker colours neutralized
(:func:`actual_binding_digest`), not the raw marker colour.

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
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum
from typing import Literal

from .candidate_markers import (
    CandidateDecision,
    MarkerSelection,
    MarkerSelectionSet,
    SelectionIssue,
    is_candidate_marker_name,
    parse_candidate_marker_name,
)
from .domain import FrameRange, ProtectedRange, RippleDisplacement
from .handoff_model import (
    ARTIFACT_KIND,
    EVIDENCE_CLASS,
    HandoffClip,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
    MarkerColor,
    ReimportedTimeline,
)
from .layer_policy import (
    RIPPLING,
    LayerIssue,
    LayerIssueCode,
    LayerLossRisk,
    PolicySource,
    TrackEditPolicy,
    TrackEffect,
    TrackPolicyAssignment,
    TrackPolicyOverride,
    apply_track_cuts,
    assign_policies,
    check_cut_layers,
    passthrough_markers,
    resolve_overrides,
    ripple_sequence_markers,
    sequence_marker_warnings,
    track_effects,
)
from .layer_xml import content_key
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
from .xmeml_reader import TrackKey, track_keys

_VERSION_RE = re.compile(r"^(.*) AIE v(\d+)$")


class SkipReason(str, Enum):
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"
    PENDING = "PENDING"
    HUMAN_EDIT_LOCKED = "HUMAN_EDIT_LOCKED"
    MARKER_CONFLICT = "MARKER_CONFLICT"
    LAYER_CONFLICT = "LAYER_CONFLICT"
    LAYER_UNSUPPORTED_ITEM = "LAYER_UNSUPPORTED_ITEM"


SKIP_LABELS_KO = {
    SkipReason.UNKNOWN: "판단 불가 - 적용하지 않음",
    SkipReason.REJECTED: "제외됨",
    SkipReason.PENDING: "보류(미결정)",
    SkipReason.HUMAN_EDIT_LOCKED: "사람이 수정한 구간 - 보호",
    SkipReason.MARKER_CONFLICT: "다른 마커와 겹침",
    SkipReason.LAYER_CONFLICT: "다른 레이어 항목이 컷에 걸침 - 자르지 않음",
    SkipReason.LAYER_UNSUPPORTED_ITEM: "모델이 이해하지 못하는 레이어 항목 - 자르지 않음",
}


class ApplyRefused(ValueError):
    """The confirmation digest was not echoed exactly: nothing is applied."""


@dataclass(frozen=True)
class ApprovedCut:
    candidate_id: str
    timeline_range: FrameRange  # Actual timeline coordinates
    reason: str
    track_policies: tuple[TrackPolicyAssignment, ...] = ()  # LAYER-001, one per Actual track

    def __post_init__(self) -> None:
        object.__setattr__(self, "track_policies", tuple(self.track_policies))
        if not isinstance(self.timeline_range, FrameRange):
            raise TypeError("Approved cut requires a FrameRange")
        if not isinstance(self.candidate_id, str) or not isinstance(self.reason, str):
            raise TypeError("Approved cut id and reason must be strings")
        if any(not isinstance(a, TrackPolicyAssignment) for a in self.track_policies):
            raise TypeError("Track policies must be TrackPolicyAssignment values")

    def policy(self, track: TrackKey) -> TrackEditPolicy:
        for assignment in self.track_policies:
            if assignment.track == track:
                return assignment.policy
        return TrackEditPolicy.UNKNOWN


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


@dataclass(frozen=True)
class CandidateStatus:
    """Resolved selection status of one candidate (after name + colour resolution)."""

    candidate_id: str
    decision: CandidateDecision
    issue: SelectionIssue

    def __post_init__(self) -> None:
        if not isinstance(self.decision, CandidateDecision) or not isinstance(
            self.issue, SelectionIssue
        ):
            raise TypeError("Typed candidate status required")


_ClipSlot = tuple[TrackKey, int]  # (Actual track, timeline start) of a modelled clip


def _implied_link_partition(actual: ReimportedTimeline) -> frozenset[frozenset[_ClipSlot]]:
    """Link groups the APPLY-001 writer rule derives on its own (same media, timeline
    range and source range; exactly one video member and at least one audio)."""
    groups: dict[tuple[str, int, int, int, int], list[_ClipSlot]] = {}
    for key, track in track_keys(actual):
        for start, clip in track.placements():
            rule = (
                clip.media.media_id,
                start,
                start + clip.duration,
                clip.source_range.start,
                clip.source_range.end,
            )
            groups.setdefault(rule, []).append((key, start))
    result: set[frozenset[_ClipSlot]] = set()
    for members in groups.values():
        videos = [m for m in members if m[0].kind is HandoffTrackKind.VIDEO]
        audios = [m for m in members if m[0].kind is HandoffTrackKind.AUDIO]
        if len(videos) == 1 and audios:
            result.add(frozenset(members))
    return frozenset(result)


def _links_are_implied(actual: ReimportedTimeline) -> bool:
    """True when the Actual's file ``<link>`` groups carry no information beyond the
    APPLY-001 rule (or there are none): dropping them changes no apply result."""
    file_groups: dict[str, list[_ClipSlot]] = {}
    for key, track in track_keys(actual):
        if any(item.link_group is not None for item in track.passthrough):
            return False
        for start, clip in track.placements():
            if clip.link_group is not None:
                file_groups.setdefault(clip.link_group, []).append((key, start))
    if not file_groups:
        return True
    partition = frozenset(frozenset(members) for members in file_groups.values())
    return partition == _implied_link_partition(actual)


def actual_binding_digest(actual: ReimportedTimeline) -> str:
    """Digest of the Actual with transport-only evidence canonicalized.

    - Marker colour is only a secondary approval signal (FCP7 xmeml carries none,
      OTIO and the Studio read do); its effect is bound through the resolved
      ``CandidateStatus`` instead.
    - The evidence class (``FILE_ROUNDTRIP`` / ``STUDIO_API_READ``) names the
      transport, not the content.
    - File ``<link>`` groups are dropped ONLY when they are exactly the groups the
      APPLY-001 rule derives by itself (same media, timeline range and source
      range), i.e. when they carry no extra information. Any other link structure
      (separate-recorder audio, J/L-cuts, links on pass-through items) stays bound.

    So the same approvals on the same content give the same confirmation digest
    whichever transport read the Actual.
    """
    drop_links = _links_are_implied(actual)
    tracks = tuple(
        replace(
            track,
            items=tuple(
                replace(
                    item,
                    markers=tuple(replace(m, color=MarkerColor.UNKNOWN) for m in item.markers),
                    link_group=None if drop_links else item.link_group,
                )
                if isinstance(item, HandoffClip)
                else item
                for item in track.items
            ),
        )
        for track in actual.tracks
    )
    return timeline_digest(replace(actual, tracks=tracks, evidence_class=EVIDENCE_CLASS))


def confirmation_digest_for(
    expected_digest: str,
    actual_binding: str,
    cuts: tuple[ApprovedCut, ...],
    statuses: tuple[CandidateStatus, ...] = (),
    track_effects: tuple[TrackEffect, ...] = (),
    layer_warnings: tuple[LayerIssue, ...] = (),
    loss_risks: tuple[LayerIssue, ...] = (),
) -> str:
    """Binds the artifacts, the resolved candidate statuses, the cut set with
    per-track policies and the layer plan. ``actual_binding`` is
    :func:`actual_binding_digest` (raw marker colours are not bound)."""
    payload = {
        "actual_binding": actual_binding,
        "approved_cuts": list(cuts),
        "candidate_statuses": list(statuses),
        "expected_digest": expected_digest,
        "layer_loss_risks": list(loss_risks),
        "layer_warnings": list(layer_warnings),
        "schema": "apply-001-confirmation-v3-layer-001",
        "track_effects": list(track_effects),
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
    lock_tracks: tuple[TrackKey | None, ...]  # Actual track of each lock (None = UNKNOWN)
    candidate_statuses: tuple[CandidateStatus, ...]
    shifted_locks: tuple[ShiftedLock, ...]
    track_effects: tuple[TrackEffect, ...]
    layer_warnings: tuple[LayerIssue, ...]
    loss_risks: tuple[LayerIssue, ...]
    summary: str
    confirmation_digest: str
    axis: Literal["CONFIRMATION"] = "CONFIRMATION"
    authorizes_apply: Literal[False] = False

    def __post_init__(self) -> None:
        for name in (
            "approved_cuts",
            "skipped",
            "locks",
            "lock_tracks",
            "candidate_statuses",
            "shifted_locks",
            "track_effects",
            "layer_warnings",
            "loss_risks",
        ):
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
        keys = tuple(key for key, _ in track_keys(self.actual))
        if len(self.lock_tracks) != len(self.locks):
            raise ValueError("Every lock needs its Actual track (or None = UNKNOWN)")
        for cut in self.approved_cuts:
            if tuple(a.track for a in cut.track_policies) != keys:
                raise ValueError("Every approved cut needs exactly one policy per Actual track")
            for lock, key in zip(self.locks, self.lock_tracks, strict=True):
                policy = TrackEditPolicy.UNKNOWN if key is None else cut.policy(key)
                if policy is not TrackEditPolicy.KEEP_IN_PLACE and (
                    cut.timeline_range.overlaps(lock.frame_range)
                ):
                    raise ValueError("An approved cut overlaps a HARD_LOCK region")
        if any(i.code is not LayerIssueCode.LAYER_LOSS_RISK for i in self.loss_risks):
            raise ValueError("Loss risks carry the LAYER_LOSS_RISK code")
        expected = confirmation_digest_for(
            self.expected_digest,
            actual_binding_digest(self.actual),
            self.approved_cuts,
            self.candidate_statuses,
            self.track_effects,
            self.layer_warnings,
            self.loss_risks,
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
    track_effects: tuple[TrackEffect, ...] = ()
    layer_warnings: tuple[LayerIssue, ...] = ()
    approval: Literal["EXPLICIT_CONFIRMATION_DIGEST"] = "EXPLICIT_CONFIRMATION_DIGEST"
    artifact_kind: Literal["EXPECTED_TIMELINE_ARTIFACT"] = ARTIFACT_KIND
    authorizes_import: Literal[False] = False
    verified: Literal[False] = False

    def __post_init__(self) -> None:
        for name in (
            "applied_cuts",
            "ripple_displacements",
            "remaining_candidate_ids",
            "track_effects",
            "layer_warnings",
        ):
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
    for frame_range, name in passthrough_markers(actual):
        result.append(_AnyMarker(frame_range, name))
    return tuple(result)


def _lock_track_keys(
    diff: RoundTripDiff, locks: tuple[ProtectedRange, ...]
) -> tuple[TrackKey | None, ...]:
    """Actual track of each lock; an ambiguous protection id stays None (UNKNOWN)."""
    by_id: dict[str, list[TrackKey]] = {}
    for extent in diff.actual_tracks:
        by_id.setdefault(extent.protection_track_id, []).append(extent.track)
    result: list[TrackKey | None] = []
    for lock in locks:
        hits = by_id.get(str(lock.track_id), [])
        result.append(hits[0] if len(hits) == 1 else None)
    return tuple(result)


def _candidate_clip(actual: ReimportedTimeline, selection: MarkerSelection) -> HandoffClip | None:
    """The anchor clip that carries the approved candidate marker."""
    cut = selection.actual_range
    if cut is None or selection.actual_track is None:
        return None
    for key, track in track_keys(actual):
        if key != selection.actual_track:
            continue
        for start, clip in track.placements():
            if FrameRange(start, start + clip.duration).contains(cut):
                return clip
    return None


def _seconds(frames: int, actual: ReimportedTimeline) -> str:
    value = frames_to_seconds(frames, actual.rate)
    millis = (value.numerator * 1000) // value.denominator
    return f"{millis // 1000}.{millis % 1000:03d}"


_POLICY_SHORT = {
    TrackEditPolicy.CUT_WITH_SOURCE: "CUT",
    TrackEditPolicy.SHIFT_WITH_RIPPLE: "SHIFT",
    TrackEditPolicy.KEEP_IN_PLACE: "KEEP",
    TrackEditPolicy.UNKNOWN: "UNKNOWN",
}


@dataclass(frozen=True)
class _LayerPlan:
    track_effects: tuple[TrackEffect, ...]
    warnings: tuple[LayerIssue, ...]
    loss_risks: tuple[LayerIssue, ...]


def _render_summary(
    actual: ReimportedTimeline,
    cuts: tuple[ApprovedCut, ...],
    skipped: tuple[SkippedCandidate, ...],
    shifted: tuple[ShiftedLock, ...],
    plan: _LayerPlan,
    digest: str,
) -> str:
    removed = sum(c.timeline_range.duration for c in cuts)
    lines = [
        "APPLY-001 적용 확인 / apply confirmation",
        "Expected artifact only: no rendering, no Resolve API; import is a manual user action.",
        f"대상 타임라인(Actual): {actual.name}",
        "레이어는 병합되지 않음 - 트랙별로 따로 편집 / layers are never merged, each track edited alone",
        (
            f"승인된 컷 {len(cuts)}개 / approved cuts: {len(cuts)}, "
            f"총 제거 {removed}프레임 ({_seconds(removed, actual)}초) - 트랙별 정책 / per-track policy"
        ),
    ]
    for cut in cuts:
        r = cut.timeline_range
        lines.append(
            f"  {cut.candidate_id} [{r.start},{r.end}) {r.duration}f "
            f"{_seconds(r.duration, actual)}s - {cut.reason}"
        )
        policies = ", ".join(
            f"{a.track_name}={_POLICY_SHORT[a.policy]}"
            + ("(override)" if a.source is PolicySource.OVERRIDE else "")
            for a in cut.track_policies
        )
        lines.append(f"    트랙 정책 / track policy: {policies}")
    lines.append(f"건너뜀 {len(skipped)}개 / skipped: {len(skipped)}")
    for item in skipped:
        lines.append(
            f"  {item.candidate_id} {item.reason.value} ({SKIP_LABELS_KO[item.reason]})"
            + (f" - {item.detail}" if item.detail else "")
        )
    lines.append("트랙별 결과 / per-track effect:")
    for effect in plan.track_effects:
        lines.append(f"  {effect.render()}")
    if plan.warnings:
        lines.append("경고 / warnings:")
        for issue in plan.warnings:
            lines.append(f"  {issue.render()}")
    if plan.loss_risks:
        lines.append(
            "레이어 손실 위험 - 적용 거부 / LAYER_LOSS_RISK - apply refused until resolved:"
        )
        for issue in plan.loss_risks:
            lines.append(f"  {issue.render()}")
    if shifted:
        lines.append("보호 구간 이동(편집 없음) / HARD_LOCK regions shifted, not edited:")
        for entry in shifted:
            r = entry.lock.frame_range
            lines.append(f"  {entry.lock.track_id} [{r.start},{r.end}) {entry.delta_frames:+d}f")
    lines.append(f"confirmation_digest: {digest}")
    return "\n".join(lines) + "\n"


def _loss_risks(actual: ReimportedTimeline) -> tuple[LayerIssue, ...]:
    return tuple(
        LayerIssue(
            LayerIssueCode.LAYER_LOSS_RISK,
            "",
            None,
            "",
            f"{description} cannot be carried by the new file",
        )
        for description in actual.unpreserved
    )


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
    selection: MarkerSelectionSet,
    expected: HandoffTimeline,
    diff: RoundTripDiff,
    *,
    track_overrides: Sequence[TrackPolicyOverride] = (),
) -> ApplyConfirmation:
    """Summarize what an apply would do. Refuses (ValueError) on stale bindings.

    ``track_overrides`` (LAYER-001) set a per-track policy for every cut by Actual
    track name or ``KIND:n`` label; unknown or ambiguous references refuse.
    """
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
    overrides = resolve_overrides(actual, tuple(track_overrides))
    locks = apply_locks(diff)
    lock_tracks = _lock_track_keys(diff, locks)
    markers = _all_markers(actual)
    approved: list[ApprovedCut] = []
    skipped: list[SkippedCandidate] = []
    warnings: list[LayerIssue] = []
    conflicts: dict[TrackKey, list[str]] = {}
    for item in selection.selections:
        skip = _skip_for(item)
        if skip is not None:
            skipped.append(skip)
            continue
        cut_range = item.actual_range
        if cut_range is None:
            raise AssertionError("approved selections are located")
        if diff.status is DiffStatus.UNKNOWN:
            skipped.append(
                SkippedCandidate(
                    item.candidate_id, SkipReason.HUMAN_EDIT_LOCKED, "Whole round-trip diff UNKNOWN"
                )
            )
            continue
        anchor = _candidate_clip(actual, item)
        if anchor is None:
            skipped.append(
                SkippedCandidate(item.candidate_id, SkipReason.UNKNOWN, "Candidate clip not found")
            )
            continue
        policies = assign_policies(
            actual, cut_range, anchor.media.media_id, overrides, anchor.link_group
        )
        blocking, cut_warnings = check_cut_layers(actual, cut_range, item.candidate_id, policies)
        if blocking:
            unsupported = [i for i in blocking if i.code is LayerIssueCode.LAYER_UNSUPPORTED_ITEM]
            reason = SkipReason.LAYER_UNSUPPORTED_ITEM if unsupported else SkipReason.LAYER_CONFLICT
            for issue in blocking:
                if issue.track is not None:
                    conflicts.setdefault(issue.track, []).append(item.candidate_id)
            detail = "; ".join(
                f"{i.track_name} [{i.track.label}] {i.detail}" if i.track is not None else i.detail
                for i in blocking
            )
            skipped.append(SkippedCandidate(item.candidate_id, reason, detail))
            continue
        policy_of = {a.track: a.policy for a in policies}
        hit = next(
            (
                lock
                for lock, key in zip(locks, lock_tracks, strict=True)
                if lock.frame_range.overlaps(cut_range)
                and (key is None or policy_of.get(key) is not TrackEditPolicy.KEEP_IN_PLACE)
            ),
            None,
        )
        if hit is not None:
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
        approved.append(ApprovedCut(item.candidate_id, cut_range, item.reason, policies))
        warnings.extend(cut_warnings)
        warnings.extend(sequence_marker_warnings(actual.markers, cut_range, item.candidate_id))
    cuts = tuple(sorted(approved, key=lambda c: c.timeline_range.start))
    shifted: list[ShiftedLock] = []
    for lock, key in zip(locks, lock_tracks, strict=True):
        delta = -sum(
            c.timeline_range.duration
            for c in cuts
            if c.timeline_range.end <= lock.frame_range.start
            and (key is None or c.policy(key) in RIPPLING)
        )
        if delta:
            shifted.append(ShiftedLock(lock, delta))
    applied_ids = {c.candidate_id for c in cuts}
    plan = _LayerPlan(
        track_effects(
            actual,
            [(c.timeline_range, c.track_policies) for c in cuts],
            conflicts,
            overrides,
        ),
        tuple(w for w in warnings if w.candidate_id in applied_ids),
        _loss_risks(actual),
    )
    ordered_skips = tuple(sorted(skipped, key=lambda s: s.candidate_id))
    statuses = tuple(
        CandidateStatus(s.candidate_id, s.decision, s.issue)
        for s in sorted(selection.selections, key=lambda s: s.candidate_id)
    )
    digest = confirmation_digest_for(
        expected_digest,
        actual_binding_digest(actual),
        cuts,
        statuses,
        plan.track_effects,
        plan.warnings,
        plan.loss_risks,
    )
    summary = _render_summary(actual, cuts, ordered_skips, tuple(shifted), plan, digest)
    return ApplyConfirmation(
        expected_digest,
        selection.actual_digest,
        diff.digest,
        actual,
        cuts,
        ordered_skips,
        locks,
        lock_tracks,
        statuses,
        tuple(shifted),
        plan.track_effects,
        plan.warnings,
        plan.loss_risks,
        summary,
        digest,
    )


# --- apply ------------------------------------------------------------------------


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
    if confirmation.loss_risks:
        listed = "; ".join(issue.detail for issue in confirmation.loss_risks)
        raise ApplyRefused(f"LAYER_LOSS_RISK: {listed}; nothing applied")
    actual = confirmation.actual
    all_cuts = tuple(c.timeline_range for c in confirmation.approved_cuts)
    tracks: list[HandoffTrack] = []
    displacements: list[RippleDisplacement] = []
    for key, track in track_keys(actual):
        remove = tuple(
            c.timeline_range for c in confirmation.approved_cuts if c.policy(key) in RIPPLING
        )
        cut_ranges = frozenset(
            c.timeline_range
            for c in confirmation.approved_cuts
            if c.policy(key) is TrackEditPolicy.CUT_WITH_SOURCE
        )
        try:
            new_track, moved = apply_track_cuts(track, remove, cut_ranges, all_cuts)
        except (LayerLossRisk, ValueError) as exc:
            raise ApplyRefused(f"LAYER_LOSS_RISK on {track.name}: {exc}; nothing applied") from exc
        tracks.append(new_track)
        displacements.extend(moved)
    timeline = HandoffTimeline(
        next_version_name(actual.name),
        actual.rate,
        actual.start_frame,
        tuple(tracks),
        ripple_sequence_markers(actual.markers, all_cuts),
    )
    _check_layers_kept(actual, timeline)
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
        confirmation.track_effects,
        confirmation.layer_warnings,
    )


def _check_layers_kept(actual: ReimportedTimeline, result: HandoffTimeline) -> None:
    """Defensive LAYER-001 postcondition: same tracks, same state, no lost item kinds."""
    before, after = track_keys(actual), track_keys(result)
    if [k for k, _ in before] != [k for k, _ in after]:
        raise ApplyRefused("LAYER_LOSS_RISK: track set or order changed; nothing applied")
    for (_, old), (_, new) in zip(before, after, strict=True):
        if (old.name, old.kind, old.enabled, old.locked, old.attributes, old.extra_xml) != (
            new.name,
            new.kind,
            new.enabled,
            new.locked,
            new.attributes,
            new.extra_xml,
        ):
            raise ApplyRefused(f"LAYER_LOSS_RISK: track state of {old.name} changed")
        # Non-cuttable pass-through items are only ever moved: each must survive with
        # identical content (cuttable 1:1 clipitems may be split like modelled clips).
        kept_before = sorted(content_key(p.raw_xml) for p in old.passthrough if not p.cuttable)
        kept_after = sorted(content_key(p.raw_xml) for p in new.passthrough if not p.cuttable)
        if kept_before != kept_after:
            raise ApplyRefused(f"LAYER_LOSS_RISK: a pass-through item of {old.name} changed")
