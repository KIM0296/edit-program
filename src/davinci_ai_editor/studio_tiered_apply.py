"""STUDIO-T1 tiered apply port (tiers 1-4) on the FAKE Resolve object graph.

Qualification: CODE_COMPLETE / TEST_ONLY_SUPPORT. Never native: native read and
mutation stay HOLD (TASK-020). No ``DaVinciResolveScript`` import, no
``hasattr``: every call goes through an explicit allowlist (``TIERED_READ_METHODS``
/ ``TIERED_MUTATION_METHODS``) and a declared capability grant.

- :meth:`TieredApplyPort.plan` reads the live timeline, the grade state and the
  project's timeline list, then calls the pure planner
  (``studio_apply_planner.plan_studio_apply``).
- :meth:`TieredApplyPort.execute` is the single confirm button. It needs the
  APPLY-001 ``confirmation_digest`` AND the ``plan_digest`` echoed exactly
  (``ApplyRefused`` otherwise), re-reads the live timeline (STALE otherwise),
  performs the plan's tier once, never retries, and verifies by read-back:

  - tier 1: write the shared Expected (APPLY-001 result) as FCP7 XML with a
    unique version name INSIDE the file, refuse an existing name before the
    call, ``MediaPool.ImportTimelineFromFile`` (importSourceClips=False,
    sourceClipsFolders=[root]), require a NEW timeline id carrying that name
    (the documented "returns the existing timeline / None" quirks are FAILED,
    read-back UNVERIFIED), read the new timeline back (VER-001 geometry, marker
    colours excluded: FCP7 cannot carry them), check layers (track count, kind,
    order and names; names restored with ``SetTrackName`` only when granted),
    then open it (``SetCurrentTimeline``). The original stays untouched as the
    backup.
  - tier 2: tier 1, then per original graded item, ``CopyGrades`` to its
    corresponding new pieces (correspondence from the applied geometry: same
    track, same media, source range inside the original's) and Fusion comps by
    ``ExportFusionComp`` / ``ImportFusionComp``. Read-back per item: structural
    fingerprint MATCH / MISMATCH / UNVERIFIED; grade VALUES stay UNVERIFIED.
  - tier 3: ``ResolveMutationPort.apply_confirmed_cuts`` (T0, in place).
  - tier 4: :meth:`razor_goto` moves the playhead to each listed frame (the
    editor blades); ``execute`` then requires ``NEUTRAL_SPLIT`` and deletes the
    middle pieces through the T0 port with ``neutral_splits``.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Literal, TypeVar

from .apply_cuts import ApplyConfirmation, ApplyRefused, apply_approved_cuts
from .handoff_model import HandoffClip, HandoffTimeline, MarkerColor, ReimportedTimeline
from .roundtrip_diff import timeline_digest
from .roundtrip_verification import (
    ActualProvenance,
    VerificationReport,
    VerificationStatus,
    verify_roundtrip,
)
from .runtime_ports import PortIssueKind
from .studio_apply_planner import (
    TIER_1_CAPABILITIES,
    TIER_2_CAPABILITIES,
    ApplyTier,
    GradeReadResult,
    GradeState,
    ItemGradeInfo,
    PlanStatus,
    StudioApplyPlan,
    UserChoice,
    grade_state_from_items,
    plan_studio_apply,
)
from .studio_capabilities import (
    QUALIFICATION,
    CapabilityGrant,
    StudioCapability,
    StudioCapabilityProfile,
)
from .studio_razor import RazorStep, SplitChangeKind, SplitClassification, classify_split_change
from .studio_transport import (
    STUDIO_EVIDENCE,
    STUDIO_EVIDENCE_LABEL,
    MutationOutcome,
    MutationStatus,
    ResolveMutationPort,
    ResolveObjectKind,
    ResolveReadPort,
    StudioEvidence,
    StudioReadResult,
    TrackCutPolicy,
    _Blocked,
    _invoke,
    diff_studio_read,
)
from .trust_evidence import artifact_revision
from .xmeml_writer import write_xmeml

_C = StudioCapability
_K = ResolveObjectKind
_T = TypeVar("_T")

TIERED_READ_METHODS: Mapping[ResolveObjectKind, frozenset[str]] = MappingProxyType(
    {
        _K.PROJECT: frozenset(
            {
                "GetCurrentTimeline",
                "GetTimelineCount",
                "GetTimelineByIndex",
                "GetMediaPool",
                "GetSetting",
            }
        ),
        _K.TIMELINE: frozenset(
            {
                "GetName",
                "GetUniqueId",
                "GetStartFrame",
                "GetTrackCount",
                "GetItemListInTrack",
                "GetTrackName",
                "GetCurrentTimecode",
            }
        ),
        _K.TIMELINE_ITEM: frozenset(
            {
                "GetStart",
                "GetEnd",
                "GetLeftOffset",
                "GetMediaPoolItem",
                "GetNodeGraph",
                "GetFusionCompCount",
                "GetFusionCompNameList",
                "GetVersionNameList",
                "GetCurrentVersion",
            }
        ),
        _K.MEDIA_POOL_ITEM: frozenset({"GetName"}),
        _K.MEDIA_POOL: frozenset({"GetRootFolder"}),
        _K.GRAPH: frozenset({"GetNumNodes", "GetNodeLabel", "GetToolsInNode"}),
    }
)
TIERED_MUTATION_METHODS: Mapping[ResolveObjectKind, frozenset[str]] = MappingProxyType(
    {
        _K.PROJECT: frozenset({"SetCurrentTimeline"}),
        _K.MEDIA_POOL: frozenset({"ImportTimelineFromFile"}),
        _K.TIMELINE: frozenset({"SetTrackName", "SetCurrentTimecode"}),
        _K.TIMELINE_ITEM: frozenset({"CopyGrades", "ExportFusionComp", "ImportFusionComp"}),
    }
)
IMPORT_FORMAT: Literal["FCP7_XML"] = "FCP7_XML"
FORMAT_LOSSES = ("MARKER_COLOR", "MARKER_CUSTOM_DATA")
_TRACK_APIS = ("video", "audio")


class _Invalid(Exception):
    pass


def _int(value: object) -> int | None:
    return value if type(value) is int else None


def _str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _digits(value: object) -> int | None:
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    return None


def _strings(value: object) -> tuple[str, ...] | None:
    if isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
        return tuple(value)
    return None


def _combine(*statuses: VerificationStatus) -> VerificationStatus:
    if any(s is VerificationStatus.MISMATCH for s in statuses):
        return VerificationStatus.MISMATCH
    if statuses and all(s is VerificationStatus.MATCH for s in statuses):
        return VerificationStatus.MATCH
    return VerificationStatus.UNVERIFIED


def _uncoloured(timeline: _T) -> _T:
    """Marker colours -> UNKNOWN (FCP7 xmeml carries none; a documented format loss)."""
    if not isinstance(timeline, (HandoffTimeline, ReimportedTimeline)):
        raise TypeError("A timeline is required")
    tracks = tuple(
        replace(
            track,
            items=tuple(
                replace(
                    item,
                    markers=tuple(replace(m, color=MarkerColor.UNKNOWN) for m in item.markers),
                )
                if isinstance(item, HandoffClip)
                else item
                for item in track.items
            ),
        )
        for track in timeline.tracks
    )
    return replace(timeline, tracks=tracks)


def _layer_shape(
    before: ReimportedTimeline | None, after: ReimportedTimeline | None
) -> VerificationStatus:
    if before is None or after is None:
        return VerificationStatus.UNVERIFIED
    shape = [(t.kind, t.name) for t in before.tracks]
    return (
        VerificationStatus.MATCH
        if shape == [(t.kind, t.name) for t in after.tracks]
        else VerificationStatus.MISMATCH
    )


# --- results -------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemTransfer:
    original: str
    targets: tuple[str, ...]
    status: VerificationStatus
    detail: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "targets", tuple(self.targets))
        if not isinstance(self.status, VerificationStatus):
            raise TypeError("Typed transfer status required")


@dataclass(frozen=True)
class GradeTransferReport:
    """Per-item structural read-back of a tier-2 transfer. Values are never claimed."""

    structure: VerificationStatus
    items: tuple[ItemTransfer, ...]
    values: Literal[VerificationStatus.UNVERIFIED] = VerificationStatus.UNVERIFIED
    evidence: StudioEvidence = STUDIO_EVIDENCE

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        if self.values is not VerificationStatus.UNVERIFIED:
            raise ValueError("Grade values (keyframes, LUT) are UNVERIFIED in T1")
        if self.structure is not _combine(*(i.status for i in self.items)) and self.items:
            raise ValueError("Structure status is the combination of the item statuses")

    @property
    def mismatched(self) -> tuple[str, ...]:
        return tuple(i.original for i in self.items if i.status is VerificationStatus.MISMATCH)


@dataclass(frozen=True)
class TieredApplyOutcome:
    tier: ApplyTier
    status: MutationStatus
    issue: PortIssueKind | None
    detail: str
    geometry: VerificationStatus
    layers: VerificationStatus
    grades: GradeTransferReport | None
    readback: VerificationStatus
    calls: tuple[tuple[str, object], ...]
    new_timeline_name: str | None
    backup_timeline_name: str | None
    report: VerificationReport | None
    readback_read: StudioReadResult | None
    expected: HandoffTimeline | None
    split: SplitClassification | None
    in_place: MutationOutcome | None
    confirmation_digest: str
    plan_digest: str
    format_losses: tuple[str, ...] = ()
    current_timeline_switched: bool = False
    retried: Literal[False] = False
    evidence_label: Literal["STUDIO_API_READ"] = STUDIO_EVIDENCE_LABEL
    evidence_domain: Literal["TEST_ONLY_SUPPORT"] = QUALIFICATION
    native_evidence: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "calls", tuple(self.calls))
        object.__setattr__(self, "format_losses", tuple(self.format_losses))
        for value in (self.geometry, self.layers, self.readback):
            if not isinstance(value, VerificationStatus):
                raise TypeError("Typed verification statuses required")
        if not isinstance(self.status, MutationStatus) or not isinstance(self.tier, ApplyTier):
            raise TypeError("Typed status and tier required")
        if (
            self.readback is VerificationStatus.MATCH
            and self.status is not MutationStatus.PERFORMED
        ):
            raise ValueError("MATCH requires every planned call to have been performed")
        if self.status in (MutationStatus.REFUSED, MutationStatus.UNSUPPORTED) and self.mutated:
            raise ValueError("A refused or unsupported apply performed no call")
        parts = [self.geometry, self.layers]
        if self.grades is not None:
            parts.append(self.grades.structure)
        if self.readback is VerificationStatus.MATCH and _combine(*parts) is not (
            VerificationStatus.MATCH
        ):
            raise ValueError("MATCH needs geometry, layers and grade structure MATCH")
        if (
            self.retried is not False
            or self.evidence_domain != QUALIFICATION
            or self.native_evidence is not False
            or self.evidence_label != STUDIO_EVIDENCE_LABEL
        ):
            raise ValueError("Studio-T1 applies are single-shot TEST_ONLY_SUPPORT")

    @property
    def mutated(self) -> bool:
        return bool(self.calls) or (self.in_place is not None and self.in_place.mutated)

    @property
    def evidence(self) -> StudioEvidence:
        return STUDIO_EVIDENCE


@dataclass(frozen=True)
class RazorGotoResult:
    status: MutationStatus
    step: RazorStep | None
    readback: VerificationStatus
    observed_timecode: str | None
    detail: str
    retried: Literal[False] = False
    evidence_label: Literal["STUDIO_API_READ"] = STUDIO_EVIDENCE_LABEL
    native_evidence: Literal[False] = False

    def __post_init__(self) -> None:
        if (
            self.readback is VerificationStatus.MATCH
            and self.status is not MutationStatus.PERFORMED
        ):
            raise ValueError("MATCH requires the playhead call to have been performed")


# --- the port ------------------------------------------------------------------------


@dataclass(frozen=True)
class _Placed:
    obj: object
    api: str
    index: int
    start: int  # timeline-relative
    end: int
    left: int
    media: str

    @property
    def track(self) -> str:
        return f"{self.api.capitalize()} {self.index}"

    @property
    def label(self) -> str:
        return f"{self.track}@{self.start}"

    def inside(self, other: "_Placed") -> bool:
        return (
            (self.api, self.index, self.media) == (other.api, other.index, other.media)
            and other.left <= self.left
            and self.left + (self.end - self.start) <= other.left + (other.end - other.start)
        )


class _Calls:
    def __init__(self, profile: StudioCapabilityProfile) -> None:
        self.profile = profile
        self.log: list[tuple[str, object]] = []

    def get(
        self,
        obj: object,
        kind: ResolveObjectKind,
        method: str,
        cap: StudioCapability,
        *args: object,
    ) -> object:
        return _invoke(self.profile, TIERED_READ_METHODS, obj, kind, method, cap, *args)

    def safe(
        self,
        obj: object,
        kind: ResolveObjectKind,
        method: str,
        cap: StudioCapability,
        *args: object,
    ) -> object:
        try:
            return self.get(obj, kind, method, cap, *args)
        except _Blocked:
            return None

    def mutate(
        self,
        obj: object,
        kind: ResolveObjectKind,
        method: str,
        cap: StudioCapability,
        *args: object,
    ) -> object:
        try:
            result = _invoke(self.profile, TIERED_MUTATION_METHODS, obj, kind, method, cap, *args)
        except _Blocked:
            self.log.append((f"{kind.value}.{method}", None))
            raise
        self.log.append((f"{kind.value}.{method}", result))
        return result


class _Stop(Exception):
    """A mutation returned a failure value; stop, never retry."""


class TieredApplyPort:
    """Plan and execute the four STUDIO-T1 tiers. One instance per live project."""

    def __init__(self, project: object, read_port: ResolveReadPort, *, work_dir: Path) -> None:
        if not isinstance(read_port, ResolveReadPort):
            raise TypeError("A ResolveReadPort is required")
        if not isinstance(work_dir, Path):
            raise TypeError("work_dir must be a Path")
        self._project = project
        self._read = read_port
        self._profile = read_port.profile
        self._mutation = ResolveMutationPort(project, read_port)
        self._work_dir = work_dir

    def _granted(self, *capabilities: StudioCapability) -> bool:
        return all(
            self._profile.grant(c) is CapabilityGrant.GRANTED_TEST_ONLY for c in capabilities
        )

    # -- reads -------------------------------------------------------------------
    def _current(self, calls: _Calls) -> object:
        timeline = calls.get(
            self._project, _K.PROJECT, "GetCurrentTimeline", _C.READ_CURRENT_TIMELINE
        )
        if timeline is None:
            raise _Invalid("no current timeline")
        return timeline

    def _placed(
        self, calls: _Calls, timeline: object, apis: Sequence[str] = _TRACK_APIS
    ) -> tuple[_Placed, ...]:
        t, i = _K.TIMELINE, _K.TIMELINE_ITEM
        origin = _int(calls.get(timeline, t, "GetStartFrame", _C.READ_TIMELINE_START_FRAME))
        if origin is None:
            raise _Invalid("timeline start UNKNOWN")
        result: list[_Placed] = []
        for api in apis:
            count = _int(calls.get(timeline, t, "GetTrackCount", _C.READ_TRACK_COUNT, api))
            if count is None:
                raise _Invalid(f"{api} track count UNKNOWN")
            for index in range(1, count + 1):
                listed = calls.get(
                    timeline, t, "GetItemListInTrack", _C.READ_TRACK_ITEMS, api, index
                )
                if not isinstance(listed, (list, tuple)):
                    raise _Invalid(f"{api} {index} items UNKNOWN")
                for obj in listed:
                    start = _int(calls.get(obj, i, "GetStart", _C.READ_ITEM_START))
                    end = _int(calls.get(obj, i, "GetEnd", _C.READ_ITEM_END_EXCLUSIVE))
                    left = _int(calls.get(obj, i, "GetLeftOffset", _C.READ_ITEM_LEFT_OFFSET))
                    pool = calls.get(obj, i, "GetMediaPoolItem", _C.READ_ITEM_MEDIA_POOL_ITEM)
                    media = (
                        None
                        if pool is None
                        else _str(
                            calls.get(pool, _K.MEDIA_POOL_ITEM, "GetName", _C.READ_MEDIA_NAME)
                        )
                    )
                    if start is None or end is None or left is None or not media:
                        raise _Invalid(f"{api} {index} item UNKNOWN")
                    result.append(
                        _Placed(obj, api, index, start - origin, end - origin, left, media)
                    )
        return tuple(sorted(result, key=lambda p: (p.api, p.index, p.start)))

    def _grade_info(self, calls: _Calls, item: _Placed) -> ItemGradeInfo:
        i, g = _K.TIMELINE_ITEM, _K.GRAPH
        graph = calls.safe(item.obj, i, "GetNodeGraph", _C.READ_GRADE_GRAPH)
        count = (
            None
            if graph is None
            else _int(calls.safe(graph, g, "GetNumNodes", _C.READ_GRADE_GRAPH))
        )
        labels: tuple[str, ...] | None = None
        tools: tuple[tuple[str, ...], ...] | None = None
        if count is not None and count >= 0:
            raw_labels = [
                _str(calls.safe(graph, g, "GetNodeLabel", _C.READ_GRADE_GRAPH, n))
                for n in range(1, count + 1)
            ]
            raw_tools = [
                _strings(calls.safe(graph, g, "GetToolsInNode", _C.READ_GRADE_GRAPH, n))
                for n in range(1, count + 1)
            ]
            if all(v is not None for v in raw_labels):
                labels = tuple(v for v in raw_labels if v is not None)
            if all(v is not None for v in raw_tools):
                tools = tuple(v for v in raw_tools if v is not None)
        versions = _strings(
            calls.safe(item.obj, i, "GetVersionNameList", _C.READ_GRADE_VERSIONS, 0)
        )
        current_raw = calls.safe(item.obj, i, "GetCurrentVersion", _C.READ_GRADE_VERSIONS)
        current = _str(current_raw.get("versionName")) if isinstance(current_raw, dict) else None
        comp_count = _int(calls.safe(item.obj, i, "GetFusionCompCount", _C.READ_FUSION_COMPS))
        comps = _strings(calls.safe(item.obj, i, "GetFusionCompNameList", _C.READ_FUSION_COMPS))
        if comps is not None and comp_count != len(comps):
            comps = None
        return ItemGradeInfo(
            item.track, item.start, item.end, count, labels, tools, versions, current, comps
        )

    def read_grade_state(self) -> GradeReadResult:
        """Capability-gated structural grade read of every video item on the live timeline."""
        calls = _Calls(self._profile)
        try:
            items = self._placed(calls, self._current(calls), ("video",))
        except (_Blocked, _Invalid) as exc:
            reason = exc.diagnostic.message if isinstance(exc, _Blocked) else str(exc)
            return GradeReadResult(GradeState.UNKNOWN, (), None, (f"grade read failed: {reason}",))
        infos = [self._grade_info(calls, item) for item in items]
        layers = _digits(
            calls.safe(
                self._project,
                _K.PROJECT,
                "GetSetting",
                _C.READ_NODE_STACK_LAYERS,
                "nodeStackLayers",
            )
        )
        return grade_state_from_items(
            infos, layers, absence_inference=self._profile.grant(_C.GRADE_ABSENCE_INFERENCE)
        )

    def _timelines(self, calls: _Calls) -> tuple[tuple[str, str], ...]:
        p, t = _K.PROJECT, _K.TIMELINE
        count = _int(calls.get(self._project, p, "GetTimelineCount", _C.LIST_PROJECT_TIMELINES))
        if count is None:
            raise _Invalid("timeline count UNKNOWN")
        listing: list[tuple[str, str]] = []
        for index in range(1, count + 1):
            timeline = calls.get(
                self._project, p, "GetTimelineByIndex", _C.LIST_PROJECT_TIMELINES, index
            )
            name = (
                None
                if timeline is None
                else _str(calls.get(timeline, t, "GetName", _C.READ_TIMELINE_NAME))
            )
            uid = (
                None
                if timeline is None
                else _str(calls.get(timeline, t, "GetUniqueId", _C.LIST_PROJECT_TIMELINES))
            )
            if name is None or uid is None:
                raise _Invalid(f"timeline {index} UNKNOWN")
            listing.append((name, uid))
        return tuple(listing)

    def existing_timelines(self) -> tuple[tuple[str, str], ...] | None:
        try:
            return self._timelines(_Calls(self._profile))
        except (_Blocked, _Invalid):
            return None

    def _track_names(self, calls: _Calls, timeline: object) -> tuple[tuple[str, int, str], ...]:
        t = _K.TIMELINE
        names: list[tuple[str, int, str]] = []
        for api in _TRACK_APIS:
            count = _int(calls.get(timeline, t, "GetTrackCount", _C.READ_TRACK_COUNT, api))
            if count is None:
                raise _Invalid(f"{api} track count UNKNOWN")
            for index in range(1, count + 1):
                name = _str(calls.get(timeline, t, "GetTrackName", _C.READ_TRACK_NAME, api, index))
                if name is None:
                    raise _Invalid(f"{api} {index} track name UNKNOWN")
                names.append((api, index, name))
        return tuple(names)

    # -- plan --------------------------------------------------------------------
    def plan(
        self,
        confirmation: ApplyConfirmation,
        *,
        user_choice: UserChoice = UserChoice.NONE,
        track_policies: Mapping[str, TrackCutPolicy] | None = None,
    ) -> StudioApplyPlan:
        live = self._read.read()
        grade = self.read_grade_state()
        listing = self.existing_timelines()
        return plan_studio_apply(
            confirmation,
            live,
            grade,
            self._profile,
            existing_timeline_names=None if listing is None else [n for n, _ in listing],
            user_choice=user_choice,
            track_policies=track_policies,
        )

    # -- tier 4 helper -------------------------------------------------------------
    def razor_goto(self, plan: StudioApplyPlan, step_index: int) -> RazorGotoResult:
        """Move the playhead to razor step ``step_index`` (1-based). Never blades."""
        if not isinstance(plan, StudioApplyPlan):
            raise TypeError("A StudioApplyPlan is required")
        if plan.status is not PlanStatus.READY or plan.tier is not ApplyTier.TIER_4_RAZOR_ASSIST:
            return RazorGotoResult(
                MutationStatus.REFUSED,
                None,
                VerificationStatus.UNVERIFIED,
                None,
                "not a tier-4 plan",
            )
        if not 1 <= step_index <= len(plan.razor_steps):
            raise ValueError("step_index out of range")
        step = plan.razor_steps[step_index - 1]
        calls = _Calls(self._profile)
        try:
            timeline = self._current(calls)
            result = calls.mutate(
                timeline, _K.TIMELINE, "SetCurrentTimecode", _C.PLAYHEAD_SET_TIMECODE, step.timecode
            )
        except _Invalid as exc:
            return RazorGotoResult(
                MutationStatus.REFUSED, step, VerificationStatus.UNVERIFIED, None, str(exc)
            )
        except _Blocked as blocked:
            status = MutationStatus.FAILED if calls.log else MutationStatus.REFUSED
            return RazorGotoResult(
                status, step, VerificationStatus.UNVERIFIED, None, blocked.diagnostic.message
            )
        if result is not True:
            return RazorGotoResult(
                MutationStatus.FAILED,
                step,
                VerificationStatus.UNVERIFIED,
                None,
                f"SetCurrentTimecode returned {result!r}; not retried",
            )
        observed = _str(
            calls.safe(timeline, _K.TIMELINE, "GetCurrentTimecode", _C.PLAYHEAD_GET_TIMECODE)
        )
        if observed is None:
            readback = VerificationStatus.UNVERIFIED
        elif observed == step.timecode:
            readback = VerificationStatus.MATCH
        else:
            readback = VerificationStatus.MISMATCH
        return RazorGotoResult(
            MutationStatus.PERFORMED,
            step,
            readback,
            observed,
            f"playhead {step.timecode}; blade {', '.join(step.tracks)}",
        )

    # -- execute (the confirm button) ------------------------------------------------
    def execute(
        self,
        plan: StudioApplyPlan,
        confirmation: ApplyConfirmation,
        *,
        confirmed_digest: str,
        confirmed_plan_digest: str,
    ) -> TieredApplyOutcome:
        applied = apply_approved_cuts(confirmation, confirmed_digest=confirmed_digest)
        if not isinstance(plan, StudioApplyPlan):
            raise TypeError("A StudioApplyPlan is required")
        if plan.confirmation_digest != confirmation.confirmation_digest:
            raise ApplyRefused("The plan is not bound to this confirmation; nothing applied")
        if not isinstance(confirmed_plan_digest, str) or confirmed_plan_digest != plan.plan_digest:
            raise ApplyRefused("Plan digest not echoed exactly; nothing applied")
        if plan.status is not PlanStatus.READY:
            return self._outcome(
                plan, MutationStatus.REFUSED, PortIssueKind.UNKNOWN, f"plan {plan.status.value}"
            )
        if plan.tier is ApplyTier.TIER_3_DELETE_ALIGNED_IN_PLACE:
            in_place = self._mutation.apply_confirmed_cuts(
                confirmation, confirmed_digest=confirmed_digest, track_policies=plan.policy_map()
            )
            return self._from_in_place(plan, confirmation, in_place, None)
        if plan.tier is ApplyTier.TIER_4_RAZOR_ASSIST:
            return self._finish_razor(plan, confirmation, confirmed_digest)
        return self._import(plan, confirmation, applied.timeline)

    def _outcome(
        self,
        plan: StudioApplyPlan,
        status: MutationStatus,
        issue: PortIssueKind | None,
        detail: str,
        **extra: object,
    ) -> TieredApplyOutcome:
        values: dict[str, object] = {
            "geometry": VerificationStatus.UNVERIFIED,
            "layers": VerificationStatus.UNVERIFIED,
            "grades": None,
            "readback": VerificationStatus.UNVERIFIED,
            "calls": (),
            "new_timeline_name": plan.new_timeline_name,
            "backup_timeline_name": plan.backup_timeline_name,
            "report": None,
            "readback_read": None,
            "expected": None,
            "split": None,
            "in_place": None,
        }
        values.update(extra)
        return TieredApplyOutcome(
            plan.tier,
            status,
            issue,
            detail,
            confirmation_digest=plan.confirmation_digest,
            plan_digest=plan.plan_digest,
            **values,  # type: ignore[arg-type]
        )

    def _from_in_place(
        self,
        plan: StudioApplyPlan,
        confirmation: ApplyConfirmation,
        in_place: MutationOutcome,
        split: SplitClassification | None,
    ) -> TieredApplyOutcome:
        after = None if in_place.readback_read is None else in_place.readback_read.actual
        layers = (
            _layer_shape(confirmation.actual, after)
            if in_place.status is MutationStatus.PERFORMED
            else VerificationStatus.UNVERIFIED
        )
        readback = _combine(in_place.readback, layers)
        if in_place.status is not MutationStatus.PERFORMED:
            readback = VerificationStatus.UNVERIFIED
        return self._outcome(
            plan,
            in_place.status,
            in_place.issue,
            in_place.detail,
            geometry=in_place.readback,
            layers=layers,
            readback=readback,
            report=in_place.report,
            readback_read=in_place.readback_read,
            expected=in_place.expected,
            split=split,
            in_place=in_place,
        )

    def _finish_razor(
        self, plan: StudioApplyPlan, confirmation: ApplyConfirmation, confirmed_digest: str
    ) -> TieredApplyOutcome:
        live = self._read.read()
        if live.actual is None:
            return self._outcome(
                plan,
                MutationStatus.REFUSED,
                PortIssueKind.UNKNOWN,
                f"live read {live.consistency.value}; nothing mutated",
                readback_read=live,
            )
        split = classify_split_change(confirmation.actual, live.actual, plan.split_plan_map())
        if split.kind is not SplitChangeKind.NEUTRAL_SPLIT:
            lock = " (human edit: HARD_LOCK on the next run)" if split.hard_lock else ""
            missing = ", ".join(f"{t}@{f}" for t, f in split.missing)
            return self._outcome(
                plan,
                MutationStatus.REFUSED,
                PortIssueKind.STALE if split.hard_lock else PortIssueKind.UNRESOLVED,
                f"razor result {split.kind.value}{lock}: "
                + ("; ".join(split.reasons) or f"missing {missing}")
                + "; nothing mutated",
                readback_read=live,
                split=split,
            )
        in_place = self._mutation.apply_confirmed_cuts(
            confirmation,
            confirmed_digest=confirmed_digest,
            track_policies=plan.policy_map(),
            neutral_splits=plan.split_plan_map(),
        )
        return self._from_in_place(plan, confirmation, in_place, split)

    # -- tiers 1 and 2 --------------------------------------------------------------
    def _verify_import(
        self, expected: HandoffTimeline, readback: StudioReadResult
    ) -> tuple[VerificationStatus, VerificationReport]:
        bare = _uncoloured(expected)
        if readback.actual is not None:
            readback = replace(readback, actual=_uncoloured(readback.actual))
        report = verify_roundtrip(
            artifact_revision("studio-t1-import", bare.name, bare),
            bare,
            diff_studio_read(bare, readback),
            provenance=ActualProvenance.IMMEDIATE_REEXPORT,
        )
        return report.status, report

    def _layers(
        self,
        calls: _Calls,
        before: ReimportedTimeline,
        after: ReimportedTimeline | None,
        original_names: tuple[tuple[str, int, str], ...],
        new_timeline: object,
    ) -> tuple[VerificationStatus, str]:
        shape = _layer_shape(before, after)
        if shape is not VerificationStatus.MATCH:
            return shape, f"track count/kind/order {shape.value}"
        try:
            names = self._track_names(calls, new_timeline)
        except (_Blocked, _Invalid):
            return VerificationStatus.UNVERIFIED, "track names unreadable"
        if [n[:2] for n in names] != [n[:2] for n in original_names]:
            return VerificationStatus.MISMATCH, "track list differs"
        wrong = [want for want, got in zip(original_names, names, strict=True) if want != got]
        if wrong and self._granted(_C.SET_TRACK_NAME):
            for api, index, name in wrong:
                if (
                    calls.mutate(
                        new_timeline,
                        _K.TIMELINE,
                        "SetTrackName",
                        _C.SET_TRACK_NAME,
                        api,
                        index,
                        name,
                    )
                    is not True
                ):
                    raise _Stop(f"SetTrackName {api} {index} failed")
            try:
                names = self._track_names(calls, new_timeline)
            except (_Blocked, _Invalid):
                return VerificationStatus.UNVERIFIED, "track names unreadable after restore"
            wrong = [want for want, got in zip(original_names, names, strict=True) if want != got]
            if not wrong:
                return VerificationStatus.MATCH, "track names restored with SetTrackName"
        if wrong:
            listed = ", ".join(f"{a.capitalize()} {i}='{n}'" for a, i, n in wrong)
            return VerificationStatus.MISMATCH, f"track names not preserved: {listed}"
        return VerificationStatus.MATCH, "tracks preserved (count, kind, order, names)"

    def _transfer(
        self, calls: _Calls, original: object, new_timeline: object, tag: str
    ) -> GradeTransferReport:
        sources = self._placed(calls, original, ("video",))
        targets_all = self._placed(calls, new_timeline, ("video",))
        items: list[ItemTransfer] = []
        for source in sources:
            info = self._grade_info(calls, source)
            if not info.positive:
                continue
            targets = [t for t in targets_all if t.inside(source)]
            labels = tuple(t.label for t in targets)
            if not targets:
                continue  # the whole graded item was cut away: nothing to carry
            before = [self._grade_info(calls, t) for t in targets]
            if any(b.fingerprint is None for b in before):
                items.append(
                    ItemTransfer(
                        source.label,
                        labels,
                        VerificationStatus.UNVERIFIED,
                        "target grade unreadable; not copied",
                    )
                )
                continue
            if any(b.positive for b in before):
                items.append(
                    ItemTransfer(
                        source.label,
                        labels,
                        VerificationStatus.MISMATCH,
                        "target already graded; CopyGrades would overwrite it (unrecoverable)",
                    )
                )
                continue
            if (info.node_count or 0) > 1 or (info.node_tools and any(info.node_tools)):
                result = calls.mutate(
                    source.obj,
                    _K.TIMELINE_ITEM,
                    "CopyGrades",
                    _C.GRADE_COPY_GRADES,
                    [t.obj for t in targets],
                )
                if result is not True:
                    raise _Stop(f"CopyGrades {source.label} returned {result!r}")
            for number, _name in enumerate(info.comp_names or (), start=1):
                path = (
                    self._work_dir
                    / f"{tag}-{source.api}{source.index}-{source.start}-comp{number}.comp"
                )
                if (
                    calls.mutate(
                        source.obj,
                        _K.TIMELINE_ITEM,
                        "ExportFusionComp",
                        _C.FUSION_COMP_EXPORT,
                        str(path),
                        number,
                    )
                    is not True
                ):
                    raise _Stop(f"ExportFusionComp {source.label} #{number} failed")
                for target in targets:
                    if (
                        calls.mutate(
                            target.obj,
                            _K.TIMELINE_ITEM,
                            "ImportFusionComp",
                            _C.FUSION_COMP_IMPORT,
                            str(path),
                        )
                        is None
                    ):
                        raise _Stop(f"ImportFusionComp {target.label} failed")
            want = info.fingerprint
            got = [self._grade_info(calls, t).fingerprint for t in targets]
            if want is None or any(g is None for g in got):
                status, detail = VerificationStatus.UNVERIFIED, "fingerprint unreadable"
            elif all(g == want for g in got):
                status, detail = VerificationStatus.MATCH, "structure matches (values UNVERIFIED)"
            else:
                bad = ", ".join(t.label for t, g in zip(targets, got, strict=True) if g != want)
                status, detail = VerificationStatus.MISMATCH, f"structure differs on {bad}"
            items.append(ItemTransfer(source.label, labels, status, detail))
        structure = _combine(*(i.status for i in items)) if items else VerificationStatus.MATCH
        return GradeTransferReport(structure, tuple(items))

    def _import(
        self, plan: StudioApplyPlan, confirmation: ApplyConfirmation, applied: HandoffTimeline
    ) -> TieredApplyOutcome:
        tier2 = plan.tier is ApplyTier.TIER_2_IMPORT_WITH_GRADE_TRANSFER
        needed = TIER_1_CAPABILITIES + (TIER_2_CAPABILITIES if tier2 else ())
        if not self._granted(*needed):
            return self._outcome(
                plan,
                MutationStatus.REFUSED,
                PortIssueKind.UNAVAILABLE,
                "tier capabilities not granted",
            )
        new_name = plan.new_timeline_name
        if new_name is None:
            raise AssertionError("import tiers carry a new timeline name")
        live = self._read.read()
        if live.actual is None or timeline_digest(live.actual) != plan.live_actual_digest:
            return self._outcome(
                plan,
                MutationStatus.REFUSED,
                PortIssueKind.STALE if live.actual is not None else PortIssueKind.UNKNOWN,
                f"live timeline is not the planned Actual ({live.consistency.value}); nothing mutated",
                readback_read=live,
            )
        calls = _Calls(self._profile)
        try:
            original = self._current(calls)
            original_names = self._track_names(calls, original)
            listing = self._timelines(calls)
            pool = calls.get(self._project, _K.PROJECT, "GetMediaPool", _C.MEDIA_POOL_ROOT_FOLDER)
            root = (
                None
                if pool is None
                else calls.get(pool, _K.MEDIA_POOL, "GetRootFolder", _C.MEDIA_POOL_ROOT_FOLDER)
            )
            if root is None:
                raise _Invalid("media pool root UNKNOWN")
        except (_Blocked, _Invalid) as exc:
            reason = exc.diagnostic.message if isinstance(exc, _Blocked) else str(exc)
            return self._outcome(plan, MutationStatus.REFUSED, PortIssueKind.UNKNOWN, reason)
        names = {n for n, _ in listing}
        uids = {u for _, u in listing}
        if new_name in names:
            return self._outcome(
                plan,
                MutationStatus.REFUSED,
                PortIssueKind.CONFLICT,
                f"NAME_COLLISION: '{new_name}' already exists (FCP7 import would return the existing "
                "timeline); nothing imported",
            )
        expected = replace(applied, name=new_name)
        written = write_xmeml(expected)
        if written.text is None:
            return self._outcome(
                plan,
                MutationStatus.REFUSED,
                PortIssueKind.UNSUPPORTED,
                "Expected not writable as FCP7 XML",
            )
        path = self._work_dir / f"studio-t1-{plan.plan_digest[:16]}.xml"
        path.write_text(written.text, encoding="utf-8")
        options = {
            "timelineName": new_name,
            "importSourceClips": False,
            "sourceClipsFolders": [root],
        }
        extra: dict[str, object] = {"expected": expected, "format_losses": FORMAT_LOSSES}

        def failed(detail: str, **more: object) -> TieredApplyOutcome:
            values = {**extra, **more}
            return self._outcome(
                plan,
                MutationStatus.FAILED,
                PortIssueKind.UNKNOWN,
                detail + "; stopped, not retried",
                calls=tuple(calls.log),
                **values,
            )

        try:
            new = calls.mutate(
                pool,
                _K.MEDIA_POOL,
                "ImportTimelineFromFile",
                _C.IMPORT_TIMELINE_FROM_FILE,
                str(path),
                options,
            )
        except _Blocked as blocked:
            return failed(f"ImportTimelineFromFile {blocked.diagnostic.code.value}")
        if new is None:
            return failed("ImportTimelineFromFile returned None (documented for a repeated name)")
        new_uid = _str(calls.safe(new, _K.TIMELINE, "GetUniqueId", _C.LIST_PROJECT_TIMELINES))
        got_name = _str(calls.safe(new, _K.TIMELINE, "GetName", _C.READ_TIMELINE_NAME))
        if new_uid is None or new_uid in uids:
            return failed("IMPORT_RETURNED_EXISTING: the returned timeline is not new (UNVERIFIED)")
        if got_name != new_name:
            return failed(
                f"IMPORT_NAME_MISMATCH: got {got_name!r}, expected {new_name!r} (UNVERIFIED)"
            )
        readback = self._read.read(new)
        geometry, report = self._verify_import(expected, readback)
        extra.update(report=report, readback_read=readback, geometry=geometry)
        if geometry is not VerificationStatus.MATCH:
            return self._outcome(
                plan,
                MutationStatus.PERFORMED,
                None,
                f"new version imported; geometry {geometry.value}; left closed, original current",
                calls=tuple(calls.log),
                readback=geometry,
                **extra,
            )
        grades: GradeTransferReport | None = None
        try:
            layers, layer_detail = self._layers(
                calls, live.actual, readback.actual, original_names, new
            )
            if tier2:
                grades = self._transfer(calls, original, new, plan.plan_digest[:12])
        except _Stop as stop:
            return failed(str(stop), grades=grades)
        except (_Blocked, _Invalid) as exc:
            reason = exc.diagnostic.message if isinstance(exc, _Blocked) else str(exc)
            return failed(reason, grades=grades)
        parts = [geometry, layers] + ([grades.structure] if grades is not None else [])
        readback_status = _combine(*parts)
        switched = False
        notes = [layer_detail]
        if readback_status is VerificationStatus.MATCH and self._granted(_C.SET_CURRENT_TIMELINE):
            try:
                ok = calls.mutate(
                    self._project, _K.PROJECT, "SetCurrentTimeline", _C.SET_CURRENT_TIMELINE, new
                )
            except _Blocked as blocked:
                return failed(
                    f"SetCurrentTimeline {blocked.diagnostic.code.value}",
                    layers=layers,
                    grades=grades,
                )
            current = calls.safe(
                self._project, _K.PROJECT, "GetCurrentTimeline", _C.READ_CURRENT_TIMELINE
            )
            current_uid = (
                None
                if current is None
                else _str(
                    calls.safe(current, _K.TIMELINE, "GetUniqueId", _C.LIST_PROJECT_TIMELINES)
                )
            )
            if ok is not True or current_uid != new_uid:
                return failed(
                    "SetCurrentTimeline not confirmed by read-back", layers=layers, grades=grades
                )
            switched = True
            notes.append("new version opened")
        elif readback_status is VerificationStatus.MATCH:
            notes.append("open the new version by hand (SET_CURRENT_TIMELINE not granted)")
        if grades is not None and grades.mismatched:
            notes.append("grade transfer MISMATCH on " + ", ".join(grades.mismatched))
        return self._outcome(
            plan,
            MutationStatus.PERFORMED,
            None,
            f"'{new_name}' imported; original '{plan.backup_timeline_name}' kept as backup; "
            + "; ".join(notes),
            calls=tuple(calls.log),
            layers=layers,
            grades=grades,
            readback=readback_status,
            current_timeline_switched=switched,
            **extra,
        )
