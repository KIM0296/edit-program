"""STUDIO-T1 tiered apply planner (pure). Chooses HOW confirmed cuts reach the live timeline.

Qualification: CODE_COMPLETE / TEST_ONLY_SUPPORT. No Resolve access here: the
inputs are the APPLY-001 confirmation, a Studio read of the live timeline, a
grade-state read and the declared capability profile.

Resolve's scripting API cannot split an item at a frame (STUDIO-T0). The
user-approved four-tier strategy, where the editor ideally only confirms:

1. ``TIER_1_IMPORT_NEW_VERSION`` (before grading, the common case): the same
   Expected artifact the file path produces is imported INSIDE Resolve
   (``MediaPool.ImportTimelineFromFile``) as a new version timeline; the
   original timeline is left untouched as the backup. No file handling.
2. ``TIER_2_IMPORT_WITH_GRADE_TRANSFER`` (after grading): tier 1, then each
   original item's grade / Fusion comps are copied to its corresponding new
   pieces (``CopyGrades``, ``ExportFusionComp`` / ``ImportFusionComp``). Only
   when every needed transfer capability is granted and nothing untransferable
   is present (several node-stack layers, several colour versions).
3. ``TIER_3_DELETE_ALIGNED_IN_PLACE``: every cut coincides with item
   boundaries, so ``DeleteClips(items, ripple)`` applies it in place (T0).
4. ``TIER_4_RAZOR_ASSIST`` (fallback): the playhead is moved to each split
   frame and the editor presses blade; listed source-contiguous splits are
   NEUTRAL_SPLIT (not a human edit), then tier 3 deletes the middle pieces.

Selection: all cuts aligned -> 3; else grades absent -> 1; grades present and
transferable -> 2; grades present, not transferable -> 4 (or 1 if the user
explicitly accepts grade loss). An UNKNOWN grade state never silently picks
tier 1: the plan is ``NEEDS_USER_CHOICE``.

The plan is bound to the confirmation digest, the live Actual digest and its
own content (``plan_digest``). Selection != approval != apply: a plan
authorizes nothing; execution needs both digests echoed exactly.

INT-002 (LAYER-001 merged): per-track policies come from the confirmation
(each approved cut's ``track_policies``; user overrides go through
``build_apply_confirmation(track_overrides=...)``), never from a separate
planner input. The shared Expected now expresses every concrete policy, so the
import tiers (1/2) carry CUT / SHIFT / KEEP exactly as the file path does; the
in-place tiers (3/4) carry CUT and SHIFT, and a KEEP_IN_PLACE track makes them
unavailable (no track-selective ripple, STUDIO-T0).
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Literal

from .apply_cuts import ApplyConfirmation, ApprovedCut, next_version_name
from .domain import FrameRange
from .handoff_model import HandoffTrackKind, ReimportedTimeline
from .layer_policy import TrackEditPolicy
from .roundtrip_diff import timeline_digest
from .studio_capabilities import (
    QUALIFICATION,
    CapabilityGrant,
    StudioCapability,
    StudioCapabilityProfile,
)
from .studio_razor import RazorStep, razor_steps
from .studio_transport import (
    STUDIO_EVIDENCE_LABEL,
    StudioReadResult,
)
from .trust_evidence import canonical_bytes
from .xmeml_reader import track_keys

_C = StudioCapability


class ApplyTier(str, Enum):
    UNKNOWN = "UNKNOWN"
    TIER_1_IMPORT_NEW_VERSION = "TIER_1_IMPORT_NEW_VERSION"
    TIER_2_IMPORT_WITH_GRADE_TRANSFER = "TIER_2_IMPORT_WITH_GRADE_TRANSFER"
    TIER_3_DELETE_ALIGNED_IN_PLACE = "TIER_3_DELETE_ALIGNED_IN_PLACE"
    TIER_4_RAZOR_ASSIST = "TIER_4_RAZOR_ASSIST"


class GradeState(str, Enum):
    UNKNOWN = "UNKNOWN"
    UNGRADED = "UNGRADED"
    GRADED = "GRADED"


class PlanStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    READY = "READY"
    NEEDS_USER_CHOICE = "NEEDS_USER_CHOICE"
    UNSUPPORTED = "UNSUPPORTED"
    REFUSED = "REFUSED"
    NOTHING_TO_APPLY = "NOTHING_TO_APPLY"


class UserChoice(str, Enum):
    NONE = "NONE"
    ACCEPT_GRADE_LOSS = "ACCEPT_GRADE_LOSS"
    USE_RAZOR_ASSIST = "USE_RAZOR_ASSIST"


class UserAction(str, Enum):
    NONE = "NONE"
    CONFIRM_ONLY = "CONFIRM_ONLY"
    CONFIRM_THEN_REVIEW_GRADES = "CONFIRM_THEN_REVIEW_GRADES"
    CONFIRM_ON_EDIT_PAGE = "CONFIRM_ON_EDIT_PAGE"
    RAZOR_THEN_CONFIRM = "RAZOR_THEN_CONFIRM"
    CHOOSE_OPTION = "CHOOSE_OPTION"
    USE_FILE_PATH = "USE_FILE_PATH"


# --- grade state ---------------------------------------------------------------------


@dataclass(frozen=True)
class ItemGradeInfo:
    """Structural grade read of one video item. ``None`` = unreadable (stays UNKNOWN)."""

    track: str
    start: int  # timeline-relative
    end: int
    node_count: int | None
    node_labels: tuple[str, ...] | None
    node_tools: tuple[tuple[str, ...], ...] | None
    version_names: tuple[str, ...] | None
    current_version: str | None
    comp_names: tuple[str, ...] | None

    @property
    def label(self) -> str:
        return f"{self.track}@{self.start}"

    @property
    def complete(self) -> bool:
        return None not in (
            self.node_count,
            self.node_labels,
            self.node_tools,
            self.version_names,
            self.comp_names,
        )

    @property
    def positive(self) -> bool:
        """Positive evidence of grading work (readable signals only)."""
        return bool(
            (self.node_count is not None and self.node_count > 1)
            or (self.node_tools is not None and any(self.node_tools))
            or (self.version_names is not None and len(self.version_names) > 1)
            or (self.comp_names is not None and len(self.comp_names) > 0)
        )

    @property
    def fingerprint(self) -> tuple[object, ...] | None:
        """Structural fingerprint (current layer + comp count). Never grade values.

        Comp NAMES are excluded: what ImportFusionComp names a comp is undocumented.
        """
        if self.comp_names is None:
            return None
        if None in (self.node_count, self.node_labels, self.node_tools):
            return None
        return (self.node_count, self.node_labels, self.node_tools, len(self.comp_names))


@dataclass(frozen=True)
class GradeReadResult:
    state: GradeState
    items: tuple[ItemGradeInfo, ...]
    node_stack_layers: int | None
    reasons: tuple[str, ...]
    evidence_label: Literal["STUDIO_API_READ"] = STUDIO_EVIDENCE_LABEL
    qualification: Literal["TEST_ONLY_SUPPORT"] = QUALIFICATION
    native_evidence: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if not isinstance(self.state, GradeState):
            raise TypeError("Typed grade state required")
        if self.native_evidence is not False or self.qualification != QUALIFICATION:
            raise ValueError("Grade reads are TEST_ONLY_SUPPORT, never native")

    @property
    def graded_items(self) -> tuple[ItemGradeInfo, ...]:
        return tuple(i for i in self.items if i.positive)


def grade_state_from_items(
    items: Sequence[ItemGradeInfo],
    node_stack_layers: int | None,
    *,
    absence_inference: CapabilityGrant,
    reasons: Sequence[str] = (),
) -> GradeReadResult:
    """GRADED on positive evidence; UNGRADED only with complete reads AND the inference grant."""
    notes = list(reasons)
    if any(i.positive for i in items) or (node_stack_layers is not None and node_stack_layers > 1):
        return GradeReadResult(GradeState.GRADED, tuple(items), node_stack_layers, tuple(notes))
    unknown = bool(notes)
    incomplete = [i.label for i in items if not i.complete]
    if incomplete:
        notes.append("grade read incomplete: " + ", ".join(incomplete))
        unknown = True
    if node_stack_layers is None:
        notes.append("nodeStackLayers UNKNOWN")
        unknown = True
    if absence_inference is not CapabilityGrant.GRANTED_TEST_ONLY:
        notes.append("GRADE_ABSENCE_INFERENCE not granted (UNVERIFIED): absence is not proof")
        unknown = True
    state = GradeState.UNKNOWN if unknown else GradeState.UNGRADED
    return GradeReadResult(state, tuple(items), node_stack_layers, tuple(notes))


# --- cut alignment -------------------------------------------------------------------


@dataclass(frozen=True)
class CutAssignment:
    candidate_id: str
    timeline_range: FrameRange
    aligned: bool  # deletable in place with whole-item DeleteClips
    splits: tuple[tuple[str, int], ...]  # (track, frame) needed for in-place apply
    covered: bool  # every cut frame on every CUT track holds an item (no gap)


def _cut_assignment(actual: ReimportedTimeline, approved: ApprovedCut) -> CutAssignment:
    candidate_id, cut = approved.candidate_id, approved.timeline_range
    splits: set[tuple[str, int]] = set()
    spans: list[tuple[int, int]] = []
    for key, track in track_keys(actual):
        if track.kind not in (HandoffTrackKind.VIDEO, HandoffTrackKind.AUDIO):
            continue
        if approved.policy(key) is not TrackEditPolicy.CUT_WITH_SOURCE:
            continue
        for start, clip in track.placements():
            end = start + clip.duration
            if not (start < cut.end and cut.start < end):
                continue
            if start < cut.start:
                splits.add((track.name, cut.start))
            if end > cut.end:
                splits.add((track.name, cut.end))
            spans.append((max(start, cut.start), min(end, cut.end)))
    # Same criterion as the T0 in-place planner: the CUT tracks together cover the cut.
    cursor = cut.start
    for start, end in sorted(spans):
        if start > cursor:
            break
        cursor = max(cursor, end)
    covered = cursor >= cut.end
    ordered = tuple(sorted(splits))
    return CutAssignment(candidate_id, cut, not ordered and covered, ordered, covered)


def _policy_blockers(
    actual: ReimportedTimeline, approved: Sequence[ApprovedCut]
) -> tuple[list[str], list[str]]:
    """(blockers for every tier, blockers for the in-place tiers 3/4 only).

    The confirmation never approves a cut with an UNKNOWN policy or a SHIFT/KEEP
    item across the cut (LAYER_CONFLICT); both are re-checked defensively. KEEP is
    expressed by the shared Expected (import tiers) but not in place.
    """
    reasons: list[str] = []
    in_place: list[str] = []
    for cut in approved:
        for key, track in track_keys(actual):
            policy = cut.policy(key)
            where = f"{cut.candidate_id} {track.name}"
            if policy is TrackEditPolicy.UNKNOWN:
                reasons.append(f"{where}: track policy UNKNOWN")
                continue
            if policy is TrackEditPolicy.CUT_WITH_SOURCE:
                continue
            if any(
                start < cut.timeline_range.end and cut.timeline_range.start < start + clip.duration
                for start, clip in track.placements()
            ):
                reasons.append(f"{where}: LAYER_CONFLICT ({policy.value} item at the cut)")
            elif policy is TrackEditPolicy.KEEP_IN_PLACE:
                in_place.append(
                    f"{where}: KEEP_IN_PLACE in place needs track-selective ripple "
                    "(TRACK_SELECTIVE_RIPPLE NOT_AVAILABLE); an imported version expresses it"
                )
    return reasons, in_place


# --- plan ----------------------------------------------------------------------------


def _granted(profile: StudioCapabilityProfile, *capabilities: StudioCapability) -> list[str]:
    """Names of the capabilities that are NOT granted (empty = all granted)."""
    return [
        c.value for c in capabilities if profile.grant(c) is not CapabilityGrant.GRANTED_TEST_ONLY
    ]


TIER_1_CAPABILITIES = (
    _C.IMPORT_TIMELINE_FROM_FILE,
    _C.IMPORT_NAME_AUTHORITY,
    _C.IMPORT_TRACK_NAMES_PRESERVED,
    _C.IMPORT_MEDIA_RELINK_EXACT,
    _C.LIST_PROJECT_TIMELINES,
    _C.MEDIA_POOL_ROOT_FOLDER,
    _C.READ_TRACK_NAME,
)
TIER_2_CAPABILITIES = (
    _C.GRADE_COPY_GRADES,
    _C.GRADE_COPY_ACROSS_TIMELINES,
    _C.READ_GRADE_GRAPH,
    _C.GRADE_STRUCTURE_FINGERPRINT,
)
TIER_2_COMP_CAPABILITIES = (_C.READ_FUSION_COMPS, _C.FUSION_COMP_EXPORT, _C.FUSION_COMP_IMPORT)
TIER_3_CAPABILITIES = (_C.DELETE_ITEMS_RIPPLE, _C.RIPPLE_SPAN_SEMANTICS)
TIER_4_CAPABILITIES = (
    *TIER_3_CAPABILITIES,
    _C.PLAYHEAD_SET_TIMECODE,
    _C.PLAYHEAD_GET_TIMECODE,
    _C.TIMECODE_STRING_FORMAT,
)


@dataclass(frozen=True)
class StudioApplyPlan:
    """What will happen, shown with the confirm button. Authorizes nothing by itself."""

    status: PlanStatus
    tier: ApplyTier
    user_action: UserAction
    cuts: tuple[CutAssignment, ...]
    grade_state: GradeState
    user_choice: UserChoice
    options: tuple[UserChoice, ...]
    confirmation_digest: str
    live_actual_digest: str | None
    original_timeline_name: str
    new_timeline_name: str | None
    backup_timeline_name: str | None
    razor_steps: tuple[RazorStep, ...]
    split_plan: tuple[tuple[str, tuple[int, ...]], ...]
    transfer_items: tuple[str, ...]
    track_policies: tuple[tuple[str, str, TrackEditPolicy], ...]  # (candidate, track, policy)
    reasons: tuple[str, ...]
    summary: str
    plan_digest: str
    axis: Literal["PLAN"] = "PLAN"
    authorizes_apply: Literal[False] = False
    evidence_label: Literal["STUDIO_API_READ"] = STUDIO_EVIDENCE_LABEL
    qualification: Literal["TEST_ONLY_SUPPORT"] = QUALIFICATION
    native_evidence: Literal[False] = False

    def __post_init__(self) -> None:
        for name in (
            "cuts",
            "options",
            "razor_steps",
            "split_plan",
            "transfer_items",
            "track_policies",
            "reasons",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        for value, enum in (
            (self.status, PlanStatus),
            (self.tier, ApplyTier),
            (self.user_action, UserAction),
            (self.grade_state, GradeState),
            (self.user_choice, UserChoice),
        ):
            if not isinstance(value, enum):
                raise TypeError("Typed plan fields required")
        if self.axis != "PLAN" or self.authorizes_apply is not False:
            raise ValueError("A plan never authorizes apply by itself")
        if self.native_evidence is not False or self.qualification != QUALIFICATION:
            raise ValueError("Studio plans are TEST_ONLY_SUPPORT, never native")
        if (self.status is PlanStatus.READY) != (self.tier is not ApplyTier.UNKNOWN):
            raise ValueError("Exactly the READY plans name a tier")
        if self.status is PlanStatus.NEEDS_USER_CHOICE and not self.options:
            raise ValueError("NEEDS_USER_CHOICE lists the options")
        if self.plan_digest != plan_digest_for(self):
            raise ValueError("plan_digest does not bind this plan")

    @property
    def confirm_only_promised(self) -> bool:
        """Customer-safe: 'just confirm' is promised for tier 1 only until native proof."""
        return self.status is PlanStatus.READY and self.tier is ApplyTier.TIER_1_IMPORT_NEW_VERSION

    def split_plan_map(self) -> Mapping[str, frozenset[int]]:
        return MappingProxyType({track: frozenset(frames) for track, frames in self.split_plan})


_DIGEST_FIELDS = (
    "status",
    "tier",
    "user_action",
    "cuts",
    "grade_state",
    "user_choice",
    "options",
    "confirmation_digest",
    "live_actual_digest",
    "original_timeline_name",
    "new_timeline_name",
    "backup_timeline_name",
    "razor_steps",
    "split_plan",
    "transfer_items",
    "track_policies",
    "reasons",
    "summary",
)


def _jsonable(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, FrameRange):
        return [value.start, value.end]
    if isinstance(value, CutAssignment):
        return [
            value.candidate_id,
            _jsonable(value.timeline_range),
            value.aligned,
            value.covered,
            _jsonable(value.splits),
        ]
    if isinstance(value, RazorStep):
        return [value.index, value.frame, value.absolute_frame, value.timecode, list(value.tracks)]
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    if value is None:
        return ""
    return value


def _digest_values(values: Mapping[str, object]) -> str:
    payload: dict[str, object] = {"schema": "studio-t1-plan-v1"}
    payload.update({name: _jsonable(values[name]) for name in _DIGEST_FIELDS})
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def plan_digest_for(plan: StudioApplyPlan) -> str:
    return _digest_values({name: getattr(plan, name) for name in _DIGEST_FIELDS})


@dataclass
class _Draft:
    confirmation: ApplyConfirmation
    status: PlanStatus = PlanStatus.UNKNOWN
    tier: ApplyTier = ApplyTier.UNKNOWN
    action: UserAction = UserAction.NONE
    cuts: tuple[CutAssignment, ...] = ()
    grade: GradeState = GradeState.UNKNOWN
    choice: UserChoice = UserChoice.NONE
    options: tuple[UserChoice, ...] = ()
    live_digest: str | None = None
    new_name: str | None = None
    steps: tuple[RazorStep, ...] = ()
    split_plan: tuple[tuple[str, tuple[int, ...]], ...] = ()
    transfer: tuple[str, ...] = ()
    policies: tuple[tuple[str, str, TrackEditPolicy], ...] = ()
    reasons: list[str] = field(default_factory=list)

    def build(self) -> StudioApplyPlan:
        original = self.confirmation.actual.name
        backup = original if self.tier in _IMPORT_TIERS else None
        new_name = self.new_name if self.tier in _IMPORT_TIERS else None
        summary = _summary(self, original, new_name)
        values: dict[str, object] = {
            "status": self.status,
            "tier": self.tier,
            "user_action": self.action,
            "cuts": self.cuts,
            "grade_state": self.grade,
            "user_choice": self.choice,
            "options": self.options,
            "confirmation_digest": self.confirmation.confirmation_digest,
            "live_actual_digest": self.live_digest,
            "original_timeline_name": original,
            "new_timeline_name": new_name,
            "backup_timeline_name": backup,
            "razor_steps": self.steps if self.tier is ApplyTier.TIER_4_RAZOR_ASSIST else (),
            "split_plan": self.split_plan if self.tier is ApplyTier.TIER_4_RAZOR_ASSIST else (),
            "transfer_items": self.transfer
            if self.tier is ApplyTier.TIER_2_IMPORT_WITH_GRADE_TRANSFER
            else (),
            "track_policies": self.policies,
            "reasons": tuple(self.reasons),
            "summary": summary,
        }
        return StudioApplyPlan(plan_digest=_digest_values(values), **values)  # type: ignore[arg-type]


_IMPORT_TIERS = (ApplyTier.TIER_1_IMPORT_NEW_VERSION, ApplyTier.TIER_2_IMPORT_WITH_GRADE_TRANSFER)


def _unique_name(base: str, existing: frozenset[str]) -> str:
    name = next_version_name(base)
    while name in existing:
        name = next_version_name(name)
    return name


def plan_studio_apply(
    confirmation: ApplyConfirmation,
    live: StudioReadResult,
    grade: GradeReadResult,
    profile: StudioCapabilityProfile,
    *,
    existing_timeline_names: Sequence[str] | None,
    user_choice: UserChoice = UserChoice.NONE,
) -> StudioApplyPlan:
    """Choose one tier for the confirmed cuts (pure; no call is made).

    Per-track policies are the confirmation's own (LAYER-001); see the module doc.
    """
    if not isinstance(confirmation, ApplyConfirmation):
        raise TypeError("An ApplyConfirmation is required")
    if not isinstance(live, StudioReadResult) or not isinstance(grade, GradeReadResult):
        raise TypeError("A StudioReadResult and a GradeReadResult are required")
    if not isinstance(profile, StudioCapabilityProfile) or not isinstance(user_choice, UserChoice):
        raise TypeError("Typed profile and user choice required")
    draft = _Draft(confirmation, choice=user_choice, grade=grade.state)
    if live.actual is None:
        draft.status = PlanStatus.REFUSED
        draft.reasons.append(f"live read {live.consistency.value}; no plan")
        return draft.build()
    draft.live_digest = timeline_digest(live.actual)
    if draft.live_digest != confirmation.actual_digest:
        draft.status = PlanStatus.REFUSED
        draft.reasons.append("STALE: the live timeline is not the confirmed Actual")
        return draft.build()
    actual = live.actual
    draft.policies = tuple(
        (c.candidate_id, a.track_name, a.policy)
        for c in confirmation.approved_cuts
        for a in c.track_policies
    )
    if not confirmation.approved_cuts:
        draft.status = PlanStatus.NOTHING_TO_APPLY
        return draft.build()
    blockers, in_place_blockers = _policy_blockers(actual, confirmation.approved_cuts)
    if blockers:
        draft.status = PlanStatus.UNSUPPORTED
        draft.action = UserAction.USE_FILE_PATH
        draft.reasons.extend(blockers)
        return draft.build()
    draft.cuts = tuple(_cut_assignment(actual, c) for c in confirmation.approved_cuts)
    # tier availability ------------------------------------------------------------
    missing_t3 = _granted(profile, *TIER_3_CAPABILITIES) + in_place_blockers
    missing_t1 = _granted(profile, *TIER_1_CAPABILITIES)
    if existing_timeline_names is None:
        missing_t1.append("timeline list UNKNOWN")
    else:
        draft.new_name = _unique_name(actual.name, frozenset(existing_timeline_names))
    missing_t4 = _granted(profile, *TIER_4_CAPABILITIES) + in_place_blockers
    if not all(c.covered for c in draft.cuts):
        missing_t4.append("a cut spans a gap on a CUT track (gap frames cannot be deleted)")
    split_map: dict[str, set[int]] = {}
    for assignment in draft.cuts:
        for track, frame in assignment.splits:
            split_map.setdefault(track, set()).add(frame)
    draft.split_plan = tuple((t, tuple(sorted(f))) for t, f in sorted(split_map.items()))
    steps = razor_steps(
        {t: frozenset(f) for t, f in split_map.items()}, actual.start_frame, actual.rate
    )
    if steps is None:
        missing_t4.append("timecode for this rate UNKNOWN (drop-frame setting unreadable)")
    else:
        draft.steps = steps
    missing_t2 = list(missing_t1) + _granted(profile, *TIER_2_CAPABILITIES)
    graded = grade.graded_items
    draft.transfer = tuple(i.label for i in graded)
    if any(i.comp_names for i in graded):
        missing_t2.extend(_granted(profile, *TIER_2_COMP_CAPABILITIES))
    if grade.node_stack_layers is None or grade.node_stack_layers > 1:
        missing_t2.append("nodeStackLayers > 1 or UNKNOWN (GRADE_COPY_ALL_LAYERS NOT_AVAILABLE)")
    multi = [i.label for i in graded if i.version_names is None or len(i.version_names) > 1]
    if multi:
        missing_t2.append(
            "colour versions not transferable (GRADE_COPY_VERSIONS NOT_AVAILABLE): "
            + ", ".join(multi)
        )
    unreadable = [i.label for i in graded if i.fingerprint is None]
    if unreadable:
        missing_t2.append("grade structure unreadable: " + ", ".join(unreadable))
    t1, t2, t3, t4 = not missing_t1, not missing_t2, not missing_t3, not missing_t4

    def ready(tier: ApplyTier, action: UserAction) -> StudioApplyPlan:
        draft.status, draft.tier, draft.action = PlanStatus.READY, tier, action
        return draft.build()

    def blocked(note: str) -> StudioApplyPlan:
        draft.status = PlanStatus.UNSUPPORTED
        draft.action = UserAction.USE_FILE_PATH
        draft.reasons.append(note)
        return draft.build()

    # selection --------------------------------------------------------------------
    if all(c.aligned for c in draft.cuts) and t3:
        return ready(ApplyTier.TIER_3_DELETE_ALIGNED_IN_PLACE, UserAction.CONFIRM_ON_EDIT_PAGE)
    if user_choice is UserChoice.ACCEPT_GRADE_LOSS:
        if t1:
            draft.reasons.append("user accepted grade loss on the new version (original kept)")
            return ready(ApplyTier.TIER_1_IMPORT_NEW_VERSION, UserAction.CONFIRM_ONLY)
        return blocked("tier 1 unavailable: " + "; ".join(missing_t1))
    if user_choice is UserChoice.USE_RAZOR_ASSIST:
        if t4:
            return ready(ApplyTier.TIER_4_RAZOR_ASSIST, UserAction.RAZOR_THEN_CONFIRM)
        return blocked("tier 4 unavailable: " + "; ".join(missing_t4))
    if grade.state is GradeState.UNGRADED:
        if t1:
            return ready(ApplyTier.TIER_1_IMPORT_NEW_VERSION, UserAction.CONFIRM_ONLY)
        draft.reasons.append("tier 1 unavailable: " + "; ".join(missing_t1))
        if t4:
            return ready(ApplyTier.TIER_4_RAZOR_ASSIST, UserAction.RAZOR_THEN_CONFIRM)
        return blocked("tier 4 unavailable: " + "; ".join(missing_t4))
    if grade.state is GradeState.GRADED:
        if t2:
            return ready(
                ApplyTier.TIER_2_IMPORT_WITH_GRADE_TRANSFER, UserAction.CONFIRM_THEN_REVIEW_GRADES
            )
        draft.reasons.append("tier 2 unavailable: " + "; ".join(missing_t2))
        if t4:
            return ready(ApplyTier.TIER_4_RAZOR_ASSIST, UserAction.RAZOR_THEN_CONFIRM)
        if t1:
            draft.status = PlanStatus.NEEDS_USER_CHOICE
            draft.action = UserAction.CHOOSE_OPTION
            draft.options = (UserChoice.ACCEPT_GRADE_LOSS,)
            return draft.build()
        return blocked("tier 4 unavailable: " + "; ".join(missing_t4))
    # UNKNOWN grade state: never silently tier 1
    draft.reasons.extend(grade.reasons)
    options = tuple(
        choice
        for choice, available in (
            (UserChoice.ACCEPT_GRADE_LOSS, t1),
            (UserChoice.USE_RAZOR_ASSIST, t4),
        )
        if available
    )
    if not options:
        return blocked("grade state UNKNOWN and neither tier 1 nor tier 4 is available")
    draft.status = PlanStatus.NEEDS_USER_CHOICE
    draft.action = UserAction.CHOOSE_OPTION
    draft.options = options
    return draft.build()


# --- human-readable plan (Korean; codes English) -------------------------------------


def _seconds(frames: int, confirmation: ApplyConfirmation) -> str:
    rate = confirmation.actual.rate
    return f"{frames * rate.denominator / rate.numerator:.2f}"


def _summary(draft: _Draft, original: str, new_name: str | None) -> str:
    conf = draft.confirmation
    removed = conf.removed_frames
    lines = [
        f"[Studio 적용 계획] status={draft.status.value} tier={draft.tier.value}",
        (
            f"- 승인된 컷 {len(conf.approved_cuts)}개, {removed}프레임"
            f" ({_seconds(removed, conf)}초) 제거"
        ),
        f"- grade_state={draft.grade.value} user_choice={draft.choice.value}",
        "- 트랙별 결과 (LAYER-001, 확인에서 정함):",
    ]
    for effect in conf.track_effects:
        lines.append(f"  {effect.render()}")
    tier = draft.tier
    if tier in _IMPORT_TIERS:
        lines += [
            f"- 새 타임라인 버전 '{new_name}' 을(를) Resolve 안에서 가져옵니다 (파일 작업 없음).",
            f"- 원본 '{original}' 은(는) 수정하지 않고 백업으로 그대로 둡니다.",
            "- 트랙(레이어) 개수·순서·이름을 유지하며 병합하지 않습니다.",
            "- 참고: 남은 후보 마커는 이름만 유지됩니다 (FCP7 XML 은 마커 색상을 담지 못함).",
        ]
    if tier is ApplyTier.TIER_1_IMPORT_NEW_VERSION:
        lines.append("당신이 할 일 (CONFIRM_ONLY): [확인] 버튼만 누르세요.")
    elif tier is ApplyTier.TIER_2_IMPORT_WITH_GRADE_TRANSFER:
        lines += [
            "- 색보정/Fusion 이전 대상: " + ", ".join(draft.transfer),
            "  (CopyGrades: 현재 노드 레이어만 복사, 키프레임·값은 UNVERIFIED)",
            (
                "당신이 할 일 (CONFIRM_THEN_REVIEW_GRADES): [확인]을 누른 뒤, 위 아이템의 "
                "색보정을 새 버전에서 눈으로 확인하세요 (실기 검증 전)."
            ),
        ]
    elif tier is ApplyTier.TIER_3_DELETE_ALIGNED_IN_PLACE:
        lines += [
            f"- 모든 컷이 클립 경계와 일치: 현재 타임라인 '{original}' 에서 바로 삭제(리플)합니다.",
            "당신이 할 일 (CONFIRM_ON_EDIT_PAGE): Edit 페이지를 연 상태에서 [확인]을 누르세요.",
        ]
    elif tier is ApplyTier.TIER_4_RAZOR_ASSIST:
        lines.append(
            "- 클립 중간 컷: 재생헤드를 아래 위치로 옮겨 드립니다. 각 위치에서 표시된 트랙만 "
            "블레이드(Ctrl+B) 해 주세요. 다른 편집은 하지 마세요."
        )
        for step in draft.steps:
            lines.append(f"  {step.index}) {step.timecode}  트랙: {', '.join(step.tracks)}")
        lines.append(
            "당신이 할 일 (RAZOR_THEN_CONFIRM): 블레이드를 모두 누른 뒤 [확인]을 누르세요. "
            "목록 밖의 분할이나 다른 변경이 있으면 적용하지 않습니다."
        )
    elif draft.status is PlanStatus.NEEDS_USER_CHOICE:
        lines.append("- 색보정 여부를 확인할 수 없거나 이전할 수 없습니다. 하나를 선택해 주세요:")
        for option in draft.options:
            if option is UserChoice.ACCEPT_GRADE_LOSS:
                lines.append(
                    "  ACCEPT_GRADE_LOSS: 새 버전 가져오기 (확인만). 새 버전에는 색보정/Fusion 이 "
                    "없습니다. 원본은 백업으로 남습니다."
                )
            elif option is UserChoice.USE_RAZOR_ASSIST:
                lines.append(
                    "  USE_RAZOR_ASSIST: 원본 타임라인에서 지정 위치마다 블레이드를 누르는 방식 "
                    "(색보정 보존)."
                )
    elif draft.status is PlanStatus.UNSUPPORTED:
        lines.append(
            "당신이 할 일 (USE_FILE_PATH): Studio 안에서 적용할 수 없습니다. 파일 경로를 쓰세요."
        )
    elif draft.status is PlanStatus.NOTHING_TO_APPLY:
        lines.append("- 적용할 컷이 없습니다.")
    for reason in draft.reasons:
        lines.append(f"- reason: {reason}")
    return "\n".join(lines)
