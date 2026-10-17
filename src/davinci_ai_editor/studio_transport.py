"""STUDIO-T0: Studio (in-Resolve) transport on the shared core. FAKE object graph only.

Qualification: CODE_COMPLETE / TEST_ONLY_SUPPORT. Never native, never live:
native Resolve read and mutation are HOLD and Studio runtime qualification is
HOLD (TASK-020). This module never imports ``DaVinciResolveScript``; it only
calls allowlisted method names on whatever object it is handed (in tests, the
fake graph in ``tests/support/fake_resolve.py``).

Two ports, one core:

- :class:`ResolveReadPort` calls getters only (explicit allowlist, typed
  validation, a ``None`` stays ``None``) and produces the same Actual model as
  the file path: a ``handoff_model.ReimportedTimeline``. RT-001
  (``diff_roundtrip``), VER-001 (``verify_roundtrip``) and APPLY-001
  (``read_marker_selections`` / ``build_apply_confirmation`` /
  ``apply_approved_cuts``) therefore run unchanged. Each read is repeated and
  fenced: ``CaptureConsistency.CONSISTENT`` (identical raw reads) /
  ``UNSTABLE`` (reads differ) / ``UNVERIFIED`` (a getter was unavailable,
  returned ``None`` or an invalid value, or a capability is not granted). Only a
  CONSISTENT read yields an Actual.
- :class:`ResolveMutationPort` adds / removes candidate markers and applies
  APPLY-001 confirmed cuts IN PLACE. Cuts need the exact
  ``confirmation_digest`` (APPLY-001 ``ApplyRefused`` otherwise), a live read
  bound to the confirmation's Actual digest (else STALE), and capability grants.
  No documented Resolve call splits an item at a frame
  (``studio_capabilities.SPLIT_ITEM_AT_FRAME`` = NOT_AVAILABLE), so a cut is
  applied in place only when it coincides with item boundaries on every track
  (whole-item ``DeleteClips(items, True)``); otherwise the outcome is
  UNSUPPORTED with ``fallback = FILE_PATH``. The transport never rebuilds a
  timeline. Every mutation is followed by a read-back verified with VER-001
  (Expected vs Actual) -> MATCH / MISMATCH / UNVERIFIED. Nothing is retried.

Evidence labels: the core RT/VER types carry the constant ``FILE_ROUNDTRIP``
("re-read Actual, never native"). STUDIO-T0 reuses them unchanged rather than
forking the core; the transport-level truth is carried by this module's
results (``evidence_domain = TEST_ONLY_SUPPORT``, ``native_evidence = False``)
and by ``RoundTripFormat.STUDIO_API_READ`` on the artifact reference.
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from types import MappingProxyType
from typing import Literal

from .apply_cuts import ApplyConfirmation, apply_approved_cuts
from .candidate_markers import (
    ANCHOR_TRACK,
    CandidateHandoff,
    is_candidate_marker_name,
    parse_candidate_marker_name,
)
from .domain import FrameRange
from .handoff_model import (
    HandoffClip,
    HandoffGap,
    HandoffItem,
    HandoffMarker,
    HandoffMediaRef,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
    MarkerColor,
    ReimportedTimeline,
)
from .native_snapshot import CaptureConsistency
from .roundtrip_diff import (
    RoundTripArtifactRef,
    RoundTripDiff,
    RoundTripFormat,
    diff_roundtrip,
    diff_unreadable_roundtrip,
    timeline_digest,
)
from .roundtrip_verification import (
    ActualProvenance,
    VerificationReport,
    VerificationStatus,
    verify_roundtrip,
)
from .runtime_ports import PortIssueKind
from .studio_capabilities import (
    QUALIFICATION,
    CapabilityGrant,
    ItemMarkerBasis,
    StudioCapability,
    StudioCapabilityProfile,
)
from .temporal_mapping import FrameRate
from .trust_evidence import artifact_revision, canonical_bytes
from .xmeml_reader import track_keys

_C = StudioCapability

# NOT a Resolve API: no split call exists (SPLIT_ITEM_AT_FRAME = NOT_AVAILABLE).
# The name only exists on the test fake, so the capability-flag path is testable.
# A profile must explicitly grant SPLIT_ITEM_AT_FRAME (test only) for it to be called.
TEST_ONLY_SPLIT_METHOD = "AieTestOnlySplitAt"


class ResolveObjectKind(str, Enum):
    UNKNOWN = "UNKNOWN"
    PROJECT = "PROJECT"
    TIMELINE = "TIMELINE"
    TIMELINE_ITEM = "TIMELINE_ITEM"
    MEDIA_POOL_ITEM = "MEDIA_POOL_ITEM"


_K = ResolveObjectKind

READ_METHODS: Mapping[ResolveObjectKind, frozenset[str]] = MappingProxyType(
    {
        _K.PROJECT: frozenset({"GetCurrentTimeline"}),
        _K.TIMELINE: frozenset(
            {
                "GetName",
                "GetUniqueId",
                "GetStartFrame",
                "GetEndFrame",
                "GetSetting",
                "GetTrackCount",
                "GetItemListInTrack",
                "GetMarkers",
            }
        ),
        _K.TIMELINE_ITEM: frozenset(
            {
                "GetName",
                "GetUniqueId",
                "GetStart",
                "GetEnd",
                "GetLeftOffset",
                "GetSourceStartFrame",
                "GetMediaPoolItem",
                "GetClipEnabled",
                "GetMarkers",
            }
        ),
        _K.MEDIA_POOL_ITEM: frozenset({"GetName", "GetUniqueId", "GetClipProperty"}),
    }
)
MUTATION_METHODS: Mapping[ResolveObjectKind, frozenset[str]] = MappingProxyType(
    {
        _K.TIMELINE: frozenset({"DeleteClips", TEST_ONLY_SPLIT_METHOD}),
        _K.TIMELINE_ITEM: frozenset({"AddMarker", "DeleteMarkerByCustomData"}),
    }
)

# Documented setting string -> rate. Anything else is UNKNOWN (never defaulted).
_RATE_STRINGS: Mapping[str, FrameRate] = MappingProxyType(
    {
        "23.976": FrameRate(24000, 1001),
        "24": FrameRate(24, 1),
        "25": FrameRate(25, 1),
        "29.97": FrameRate(30000, 1001),
        "30": FrameRate(30, 1),
        "47.952": FrameRate(48000, 1001),
        "48": FrameRate(48, 1),
        "50": FrameRate(50, 1),
        "59.94": FrameRate(60000, 1001),
        "60": FrameRate(60, 1),
    }
)
_COLOR_FROM_RESOLVE: Mapping[str, MarkerColor] = MappingProxyType(
    {
        "Red": MarkerColor.RED,
        "Green": MarkerColor.GREEN,
        "Blue": MarkerColor.BLUE,
        "Cyan": MarkerColor.CYAN,
        "Yellow": MarkerColor.YELLOW,
        "Pink": MarkerColor.PINK,
        "Purple": MarkerColor.PURPLE,
    }
)
_COLOR_TO_RESOLVE: Mapping[MarkerColor, str] = MappingProxyType(
    {color: name for name, color in _COLOR_FROM_RESOLVE.items()}
)
_TRACK_API = (
    (HandoffTrackKind.VIDEO, "video", "Video"),
    (HandoffTrackKind.AUDIO, "audio", "Audio"),
)


# --- diagnostics -------------------------------------------------------------------


class StudioDiagnosticCode(str, Enum):
    UNKNOWN = "UNKNOWN"
    CAPABILITY_ABSENT = "CAPABILITY_ABSENT"
    CAPABILITY_UNKNOWN = "CAPABILITY_UNKNOWN"
    METHOD_UNAVAILABLE = "METHOD_UNAVAILABLE"
    CALL_RAISED = "CALL_RAISED"
    NULL_VALUE = "NULL_VALUE"
    INVALID_VALUE = "INVALID_VALUE"
    NO_CURRENT_TIMELINE = "NO_CURRENT_TIMELINE"
    UNKNOWN_RATE = "UNKNOWN_RATE"
    NO_MEDIA = "NO_MEDIA"
    OVERLAPPING_ITEMS = "OVERLAPPING_ITEMS"
    END_FRAME_INCONSISTENT = "END_FRAME_INCONSISTENT"
    MARKER_BASIS_UNKNOWN = "MARKER_BASIS_UNKNOWN"
    INVALID_STRUCTURE = "INVALID_STRUCTURE"
    UNSTABLE_READ = "UNSTABLE_READ"
    SOURCE_START_DISAGREES = "SOURCE_START_DISAGREES"
    TIMELINE_MARKERS_NOT_MODELLED = "TIMELINE_MARKERS_NOT_MODELLED"


@dataclass(frozen=True)
class StudioDiagnostic:
    code: StudioDiagnosticCode
    location: str
    message: str
    blocking: bool

    def __post_init__(self) -> None:
        if not isinstance(self.code, StudioDiagnosticCode):
            raise TypeError("Typed diagnostic code required")
        if not isinstance(self.location, str) or not isinstance(self.message, str):
            raise TypeError("Diagnostic location and message must be strings")
        if type(self.blocking) is not bool:
            raise TypeError("blocking must be a bool")


class _Blocked(Exception):
    def __init__(self, diagnostic: StudioDiagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


def _invoke(
    profile: StudioCapabilityProfile,
    allow: Mapping[ResolveObjectKind, frozenset[str]],
    obj: object,
    kind: ResolveObjectKind,
    method: str,
    capability: StudioCapability,
    *args: object,
) -> object:
    """Call one allowlisted method. Capability comes from the declared profile, never hasattr."""
    if method not in allow.get(kind, frozenset()):
        raise AssertionError(f"{kind.value}.{method} is not allowlisted")
    location = f"{kind.value}.{method}"
    grant = profile.grant(capability)
    if grant is not CapabilityGrant.GRANTED_TEST_ONLY:
        code = (
            StudioDiagnosticCode.CAPABILITY_ABSENT
            if grant is CapabilityGrant.ABSENT
            else StudioDiagnosticCode.CAPABILITY_UNKNOWN
        )
        raise _Blocked(StudioDiagnostic(code, location, f"{capability.value} not granted", True))
    try:
        bound = getattr(obj, method)
    except Exception as exc:  # any failure to bind is UNAVAILABLE
        raise _Blocked(
            StudioDiagnostic(
                StudioDiagnosticCode.METHOD_UNAVAILABLE, location, type(exc).__name__, True
            )
        ) from exc
    if not callable(bound):
        raise _Blocked(
            StudioDiagnostic(
                StudioDiagnosticCode.METHOD_UNAVAILABLE, location, "not callable", True
            )
        )
    try:
        return bound(*args)
    except Exception as exc:  # a raising call is UNVERIFIED, never success
        raise _Blocked(
            StudioDiagnostic(StudioDiagnosticCode.CALL_RAISED, location, type(exc).__name__, True)
        ) from exc


# --- raw read model (None preserved) -------------------------------------------------


@dataclass(frozen=True)
class RawMarker:
    frame: int | None
    duration: int | None
    name: str | None
    note: str | None
    color: str | None
    custom_data: str | None


@dataclass(frozen=True)
class RawMedia:
    name: str | None
    path: str | None
    frames: int | None
    start: int | None
    unique_id: str | None


@dataclass(frozen=True)
class RawItem:
    name: str | None
    unique_id: str | None
    start: int | None
    end: int | None
    left_offset: int | None
    source_start_frame: int | None
    enabled: bool | None
    media: RawMedia | None
    markers: tuple[RawMarker, ...] | None


@dataclass(frozen=True)
class RawTrack:
    kind: HandoffTrackKind
    index: int
    items: tuple[RawItem, ...] | None


@dataclass(frozen=True)
class RawTimelineRead:
    name: str | None
    unique_id: str | None
    start_frame: int | None
    end_frame: int | None
    frame_rate: str | None
    tracks: tuple[RawTrack, ...]
    timeline_marker_count: int | None


def _integral(value: object) -> int | None:
    if type(value) is int:
        return value
    if type(value) is float and value.is_integer():
        return int(value)
    return None


def _digits(value: object) -> int | None:
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    return None


class _Pass:
    """One getter-only pass over the graph. Records diagnostics; None stays None."""

    def __init__(self, profile: StudioCapabilityProfile) -> None:
        self.profile = profile
        self.diagnostics: list[StudioDiagnostic] = []

    def note(
        self, code: StudioDiagnosticCode, location: str, message: str, blocking: bool = True
    ) -> None:
        self.diagnostics.append(StudioDiagnostic(code, location, message, blocking))

    @property
    def blocked(self) -> bool:
        return any(d.blocking for d in self.diagnostics)

    def call(
        self,
        obj: object,
        kind: ResolveObjectKind,
        method: str,
        capability: StudioCapability,
        *args: object,
    ) -> object:
        return _invoke(self.profile, READ_METHODS, obj, kind, method, capability, *args)

    def optional(
        self,
        obj: object,
        kind: ResolveObjectKind,
        method: str,
        capability: StudioCapability,
        *args: object,
    ) -> object:
        """Diagnostic-only getter: skipped (None) unless granted; failures are not blocking."""
        if self.profile.grant(capability) is not CapabilityGrant.GRANTED_TEST_ONLY:
            return None
        try:
            return self.call(obj, kind, method, capability, *args)
        except _Blocked as blocked:
            self.diagnostics.append(replace(blocked.diagnostic, blocking=False))
            return None

    def typed(
        self,
        value: object,
        expected: type,
        location: str,
        *,
        required: bool = True,
    ) -> object:
        if value is None:
            if required:
                self.note(StudioDiagnosticCode.NULL_VALUE, location, "getter returned None")
            return None
        if type(value) is not expected:
            self.note(StudioDiagnosticCode.INVALID_VALUE, location, type(value).__name__, required)
            return None
        return value

    def int_(self, value: object, location: str, *, required: bool = True) -> int | None:
        result = self.typed(value, int, location, required=required)
        return result if type(result) is int else None

    def str_(self, value: object, location: str, *, required: bool = True) -> str | None:
        result = self.typed(value, str, location, required=required)
        return result if isinstance(result, str) else None

    def bool_(self, value: object, location: str) -> bool | None:
        result = self.typed(value, bool, location)
        return result if type(result) is bool else None

    # -- traversal --
    def timeline(self, project: object) -> object:
        timeline = self.call(project, _K.PROJECT, "GetCurrentTimeline", _C.READ_CURRENT_TIMELINE)
        if timeline is None:
            self.note(StudioDiagnosticCode.NO_CURRENT_TIMELINE, "Project", "no current timeline")
        return timeline

    def run(self, project: object) -> RawTimelineRead | None:
        timeline = self.timeline(project)
        if timeline is None:
            return None
        t = _K.TIMELINE
        name = self.str_(self.call(timeline, t, "GetName", _C.READ_TIMELINE_NAME), "Timeline.name")
        uid = self.str_(
            self.optional(timeline, t, "GetUniqueId", _C.READ_CURRENT_TIMELINE),
            "Timeline.id",
            required=False,
        )
        start = self.int_(
            self.call(timeline, t, "GetStartFrame", _C.READ_TIMELINE_START_FRAME),
            "Timeline.start",
        )
        end = self.int_(
            self.call(timeline, t, "GetEndFrame", _C.READ_TIMELINE_END_FRAME_EXCLUSIVE),
            "Timeline.end",
        )
        rate = self.str_(
            self.call(timeline, t, "GetSetting", _C.READ_FRAME_RATE, "timelineFrameRate"),
            "Timeline.timelineFrameRate",
        )
        tracks: list[RawTrack] = []
        for kind, api, label in _TRACK_API:
            count = self.int_(
                self.call(timeline, t, "GetTrackCount", _C.READ_TRACK_COUNT, api),
                f"Timeline.trackCount.{api}",
            )
            for index in range(1, (count or 0) + 1):
                location = f"{label} {index}"
                listed = self.call(
                    timeline, t, "GetItemListInTrack", _C.READ_TRACK_ITEMS, api, index
                )
                if listed is None:
                    self.note(StudioDiagnosticCode.NULL_VALUE, location, "item list None")
                    tracks.append(RawTrack(kind, index, None))
                    continue
                if not isinstance(listed, (list, tuple)):
                    self.note(StudioDiagnosticCode.INVALID_VALUE, location, "item list type")
                    tracks.append(RawTrack(kind, index, None))
                    continue
                items = tuple(
                    self.item(obj, f"{location}[{n}]") for n, obj in enumerate(listed, start=1)
                )
                tracks.append(RawTrack(kind, index, items))
        markers = self.optional(timeline, t, "GetMarkers", _C.READ_TIMELINE_MARKERS)
        marker_count = len(markers) if isinstance(markers, dict) else None
        if marker_count:
            self.note(
                StudioDiagnosticCode.TIMELINE_MARKERS_NOT_MODELLED,
                "Timeline.markers",
                f"{marker_count} timeline markers reported, not modelled",
                False,
            )
        return RawTimelineRead(name, uid, start, end, rate, tuple(tracks), marker_count)

    def item(self, obj: object, location: str) -> RawItem:
        i = _K.TIMELINE_ITEM
        name = self.str_(self.call(obj, i, "GetName", _C.READ_ITEM_NAME), f"{location}.name")
        uid = self.str_(
            self.optional(obj, i, "GetUniqueId", _C.READ_ITEM_UNIQUE_ID),
            f"{location}.id",
            required=False,
        )
        start = self.int_(self.call(obj, i, "GetStart", _C.READ_ITEM_START), f"{location}.start")
        end = self.int_(self.call(obj, i, "GetEnd", _C.READ_ITEM_END_EXCLUSIVE), f"{location}.end")
        left = self.int_(
            self.call(obj, i, "GetLeftOffset", _C.READ_ITEM_LEFT_OFFSET), f"{location}.leftOffset"
        )
        source_start = self.int_(
            self.optional(obj, i, "GetSourceStartFrame", _C.READ_ITEM_SOURCE_START_FRAME),
            f"{location}.sourceStartFrame",
            required=False,
        )
        if source_start is not None and left is not None and source_start != left:
            self.note(
                StudioDiagnosticCode.SOURCE_START_DISAGREES,
                location,
                f"GetSourceStartFrame {source_start} != GetLeftOffset {left} (diagnostic only)",
                False,
            )
        enabled = self.bool_(
            self.call(obj, i, "GetClipEnabled", _C.READ_ITEM_ENABLED), f"{location}.enabled"
        )
        pool = self.call(obj, i, "GetMediaPoolItem", _C.READ_ITEM_MEDIA_POOL_ITEM)
        media = None
        if pool is None:
            self.note(StudioDiagnosticCode.NO_MEDIA, location, "no MediaPoolItem")
        else:
            media = self.media(pool, f"{location}.media")
        markers = self.markers(obj, location)
        return RawItem(name, uid, start, end, left, source_start, enabled, media, markers)

    def media(self, pool: object, location: str) -> RawMedia:
        m = _K.MEDIA_POOL_ITEM
        name = self.str_(
            self.call(pool, m, "GetName", _C.READ_MEDIA_NAME), f"{location}.name", required=False
        )
        path = self.str_(
            self.call(pool, m, "GetClipProperty", _C.READ_MEDIA_PATH, "File Path"),
            f"{location}.path",
            required=False,
        )
        frames = _digits(
            self.optional(pool, m, "GetClipProperty", _C.READ_MEDIA_FRAMES_AND_START, "Frames")
        )
        start = _digits(
            self.optional(pool, m, "GetClipProperty", _C.READ_MEDIA_FRAMES_AND_START, "Start")
        )
        uid = self.str_(
            self.optional(pool, m, "GetUniqueId", _C.READ_ITEM_UNIQUE_ID),
            f"{location}.id",
            required=False,
        )
        return RawMedia(name or None, path or None, frames, start, uid)

    def markers(self, obj: object, location: str) -> tuple[RawMarker, ...] | None:
        if self.profile.item_marker_basis is not ItemMarkerBasis.ITEM_START_RELATIVE:
            self.note(
                StudioDiagnosticCode.MARKER_BASIS_UNKNOWN,
                f"{location}.markers",
                "item marker frameId basis not granted (UNVERIFIED)",
            )
            return None
        value = self.call(obj, _K.TIMELINE_ITEM, "GetMarkers", _C.READ_ITEM_MARKERS)
        if value is None:
            self.note(StudioDiagnosticCode.NULL_VALUE, f"{location}.markers", "markers None")
            return None
        if not isinstance(value, dict):
            self.note(StudioDiagnosticCode.INVALID_VALUE, f"{location}.markers", "markers type")
            return None
        result: list[RawMarker] = []
        for key, info in value.items():
            where = f"{location}.marker[{key!r}]"
            if not isinstance(info, dict):
                self.note(StudioDiagnosticCode.INVALID_VALUE, where, "marker info type")
                continue
            frame = _integral(key)
            duration = _integral(info.get("duration"))
            if frame is None or duration is None:
                self.note(StudioDiagnosticCode.INVALID_VALUE, where, "non-integral frame/duration")
            name, note = info.get("name"), info.get("note")
            color, custom = info.get("color"), info.get("customData")
            result.append(
                RawMarker(
                    frame,
                    duration,
                    self.str_(name, f"{where}.name"),
                    self.str_(note, f"{where}.note"),
                    color if isinstance(color, str) else None,
                    custom if isinstance(custom, str) else None,
                )
            )
        return tuple(sorted(result, key=lambda m: (m.frame or 0, m.name or "")))


# --- raw -> Actual (same model as the file path) -------------------------------------


class _Invalid(Exception):
    pass


def _need(value: object, what: str) -> object:
    if value is None:
        raise _Invalid(f"{what} UNKNOWN")
    return value


def _clip_from_raw(item: RawItem, location: str) -> tuple[int, int, HandoffClip]:
    start, end, left = item.start, item.end, item.left_offset
    if start is None or end is None or left is None or item.name is None:
        raise _Invalid(f"{location} geometry UNKNOWN")
    if item.enabled is None or item.media is None or item.markers is None:
        raise _Invalid(f"{location} state UNKNOWN")
    if end <= start or left < 0:
        raise _Invalid(f"{location} empty or negative geometry")
    media = item.media
    media_id = media.name or media.path
    if media_id is None:
        raise _Invalid(f"{location} media identity UNKNOWN")
    available = None if not media.frames else FrameRange(0, media.frames)
    ref = HandoffMediaRef(media_id, media.path, available, media.start)
    source = FrameRange(left, left + (end - start))
    markers: list[HandoffMarker] = []
    for marker in item.markers:
        if (
            marker.frame is None
            or marker.duration is None
            or marker.name is None
            or marker.note is None
        ):
            raise _Invalid(f"{location} marker UNKNOWN")
        color = MarkerColor.UNKNOWN
        if marker.color is not None:
            color = _COLOR_FROM_RESOLVE.get(marker.color, MarkerColor.UNKNOWN)
        frame_range = FrameRange(left + marker.frame, left + marker.frame + marker.duration)
        markers.append(HandoffMarker(frame_range, marker.name, color, marker.note))
    clip = HandoffClip(item.name, ref, source, item.enabled, tuple(markers))
    return start, end, clip


def _actual_from_raw(raw: RawTimelineRead) -> ReimportedTimeline:
    name = raw.name
    start_frame = raw.start_frame
    if name is None or start_frame is None or raw.end_frame is None:
        raise _Invalid("timeline header UNKNOWN")
    rate = None if raw.frame_rate is None else _RATE_STRINGS.get(raw.frame_rate)
    if rate is None:
        raise _Invalid(f"rate {raw.frame_rate!r} UNKNOWN")
    tracks: list[HandoffTrack] = []
    last_end: int | None = None
    for track in raw.tracks:
        label = "Video" if track.kind is HandoffTrackKind.VIDEO else "Audio"
        location = f"{label} {track.index}"
        if track.items is None:
            raise _Invalid(f"{location} items UNKNOWN")
        placed = sorted(
            (_clip_from_raw(item, f"{location}[{n}]") for n, item in enumerate(track.items, 1)),
            key=lambda p: p[0],
        )
        items: list[HandoffItem] = []
        cursor = start_frame
        for start, end, clip in placed:
            if start < cursor:
                raise _Invalid(f"{location} overlapping or pre-start items")
            if start > cursor:
                items.append(HandoffGap(start - cursor))
            items.append(clip)
            cursor = end
            last_end = end if last_end is None else max(last_end, end)
        tracks.append(HandoffTrack(location, track.kind, tuple(items)))
    if last_end is not None and last_end != raw.end_frame:
        raise _Invalid(
            f"END_FRAME_INCONSISTENT: last item end {last_end} != timeline end {raw.end_frame}"
        )
    return ReimportedTimeline(name, rate, start_frame, tuple(tracks))


# --- read port ---------------------------------------------------------------------


@dataclass(frozen=True)
class StudioReadResult:
    """A fenced getter-only read. Only CONSISTENT carries an Actual. Never native."""

    consistency: CaptureConsistency
    actual: ReimportedTimeline | None
    snapshot_sha256: str
    timeline_ref: str
    reads: int
    diagnostics: tuple[StudioDiagnostic, ...]
    evidence_domain: Literal["TEST_ONLY_SUPPORT"] = QUALIFICATION
    native_evidence: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if not isinstance(self.consistency, CaptureConsistency):
            raise TypeError("Typed capture consistency required")
        if (self.consistency is CaptureConsistency.CONSISTENT) != (self.actual is not None):
            raise ValueError("Only a CONSISTENT read carries an Actual")
        if self.actual is not None and not isinstance(self.actual, ReimportedTimeline):
            raise TypeError("The Actual is a ReimportedTimeline")
        if self.evidence_domain != QUALIFICATION or self.native_evidence is not False:
            raise ValueError("Studio-T0 reads are TEST_ONLY_SUPPORT, never native")

    @property
    def artifact_ref(self) -> RoundTripArtifactRef:
        return RoundTripArtifactRef(
            f"studio-read:{self.timeline_ref}",
            RoundTripFormat.STUDIO_API_READ,
            self.snapshot_sha256,
        )


def _sha(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


class ResolveReadPort:
    """Getter-only read of the current timeline, repeated and fenced."""

    def __init__(
        self, project: object, profile: StudioCapabilityProfile, *, reads: int = 2
    ) -> None:
        if not isinstance(profile, StudioCapabilityProfile):
            raise TypeError("A StudioCapabilityProfile is required")
        if type(reads) is not int or reads < 2:
            raise ValueError("The repeated-read fence needs at least two reads")
        self._project = project
        self._profile = profile
        self._reads = reads

    @property
    def profile(self) -> StudioCapabilityProfile:
        return self._profile

    def read(self) -> StudioReadResult:
        raws: list[RawTimelineRead] = []
        diagnostics: list[StudioDiagnostic] = []
        for _ in range(self._reads):
            single = _Pass(self._profile)
            raw: RawTimelineRead | None
            try:
                raw = single.run(self._project)
            except _Blocked as blocked:
                single.diagnostics.append(blocked.diagnostic)
                raw = None
            diagnostics.extend(single.diagnostics)
            if raw is None or single.blocked:
                ref = "unknown" if raw is None else raw.unique_id or raw.name or "unknown"
                return StudioReadResult(
                    CaptureConsistency.UNVERIFIED,
                    None,
                    _sha(diagnostics),
                    ref,
                    len(raws) + 1,
                    tuple(diagnostics),
                )
            raws.append(raw)
        first = raws[0]
        ref = first.unique_id or first.name or "unknown"
        digest = _sha(first)
        if any(r != first for r in raws[1:]):
            diagnostics.append(
                StudioDiagnostic(
                    StudioDiagnosticCode.UNSTABLE_READ, "Timeline", "repeated reads differ", True
                )
            )
            return StudioReadResult(
                CaptureConsistency.UNSTABLE, None, digest, ref, len(raws), tuple(diagnostics)
            )
        try:
            actual = _actual_from_raw(first)
        except (_Invalid, ValueError, TypeError) as exc:
            code = (
                StudioDiagnosticCode.END_FRAME_INCONSISTENT
                if "END_FRAME_INCONSISTENT" in str(exc)
                else StudioDiagnosticCode.INVALID_STRUCTURE
            )
            diagnostics.append(StudioDiagnostic(code, "Timeline", str(exc), True))
            return StudioReadResult(
                CaptureConsistency.UNVERIFIED, None, digest, ref, len(raws), tuple(diagnostics)
            )
        return StudioReadResult(
            CaptureConsistency.CONSISTENT, actual, digest, ref, len(raws), tuple(diagnostics)
        )


def diff_studio_read(expected: HandoffTimeline, result: StudioReadResult) -> RoundTripDiff:
    """RT-001 diff of an Expected against a Studio read (whole-UNKNOWN unless CONSISTENT)."""
    if not isinstance(result, StudioReadResult):
        raise TypeError("A StudioReadResult is required")
    if result.actual is None:
        return diff_unreadable_roundtrip(
            expected, artifact_ref=result.artifact_ref, read_diagnostics=()
        )
    return diff_roundtrip(expected, result.actual, artifact_ref=result.artifact_ref)


def expected_from_actual(actual: ReimportedTimeline) -> HandoffTimeline:
    """The live timeline restated as an Expected base (Studio plans start from the Actual)."""
    if not isinstance(actual, ReimportedTimeline):
        raise TypeError("A ReimportedTimeline is required")
    return HandoffTimeline(actual.name, actual.rate, actual.start_frame, actual.tracks)


def strip_candidate_markers(
    timeline: HandoffTimeline, tokens: frozenset[str] | None = None
) -> HandoffTimeline:
    """Remove ``AIE-`` candidate markers (all, or those whose token is in ``tokens``)."""

    def keep(marker: HandoffMarker) -> bool:
        if not is_candidate_marker_name(marker.name):
            return True
        if tokens is None:
            return False
        return parse_candidate_marker_name(marker.name)[0] not in tokens

    tracks = tuple(
        replace(
            track,
            items=tuple(
                replace(item, markers=tuple(m for m in item.markers if keep(m)))
                if isinstance(item, HandoffClip)
                else item
                for item in track.items
            ),
        )
        for track in timeline.tracks
    )
    return replace(timeline, tracks=tracks)


# --- mutation port -----------------------------------------------------------------


class MutationKind(str, Enum):
    UNKNOWN = "UNKNOWN"
    ADD_CANDIDATE_MARKERS = "ADD_CANDIDATE_MARKERS"
    REMOVE_CANDIDATE_MARKERS = "REMOVE_CANDIDATE_MARKERS"
    APPLY_CUTS_IN_PLACE = "APPLY_CUTS_IN_PLACE"


class MutationStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    PERFORMED = "PERFORMED"  # every call returned True (acceptance = read-back)
    REFUSED = "REFUSED"  # nothing called (stale, unverified read, missing grant)
    UNSUPPORTED = "UNSUPPORTED"  # nothing called; the operation needs a missing capability
    FAILED = "FAILED"  # a call returned False/None or raised; stopped, never retried


class Fallback(str, Enum):
    NONE = "NONE"
    FILE_PATH = "FILE_PATH"  # APPLY-001 FCP7 XML: a new timeline the editor imports


class TrackCutPolicy(str, Enum):
    """Per-track policy for an in-place cut (LAYER-001 vocabulary; tracks never merge).

    CUT_WITH_SOURCE: items at the cut are removed (with ripple). SHIFT_WITH_RIPPLE:
    never cut; later items move left by the ripple; an item spanning the cut is a
    LAYER_CONFLICT. KEEP_IN_PLACE: never cut and never moved, which no documented
    call can express in place (TRACK_SELECTIVE_RIPPLE NOT_AVAILABLE) -> UNSUPPORTED.
    """

    UNKNOWN = "UNKNOWN"
    CUT_WITH_SOURCE = "CUT_WITH_SOURCE"
    SHIFT_WITH_RIPPLE = "SHIFT_WITH_RIPPLE"
    KEEP_IN_PLACE = "KEEP_IN_PLACE"


class OperationKind(str, Enum):
    UNKNOWN = "UNKNOWN"
    ADD_MARKER = "ADD_MARKER"
    DELETE_MARKER = "DELETE_MARKER"
    SPLIT_AT_FRAME = "SPLIT_AT_FRAME"
    DELETE_ITEMS_RIPPLE = "DELETE_ITEMS_RIPPLE"


@dataclass(frozen=True)
class PlannedOperation:
    kind: OperationKind
    track: str
    frame: int  # timeline-relative (frame 0 = timeline start)
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, OperationKind):
            raise TypeError("Typed operation kind required")


@dataclass(frozen=True)
class MutationOutcome:
    kind: MutationKind
    status: MutationStatus
    issue: PortIssueKind | None
    detail: str
    planned: tuple[PlannedOperation, ...]
    call_results: tuple[object, ...]
    readback: VerificationStatus
    report: VerificationReport | None
    readback_read: StudioReadResult | None
    expected: HandoffTimeline | None
    confirmation_digest: str | None = None
    fallback: Fallback = Fallback.NONE
    retried: Literal[False] = False
    evidence_domain: Literal["TEST_ONLY_SUPPORT"] = QUALIFICATION
    native_evidence: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "planned", tuple(self.planned))
        object.__setattr__(self, "call_results", tuple(self.call_results))
        if not isinstance(self.status, MutationStatus) or not isinstance(
            self.readback, VerificationStatus
        ):
            raise TypeError("Typed status and read-back required")
        if (
            self.readback is VerificationStatus.MATCH
            and self.status is not MutationStatus.PERFORMED
        ):
            raise ValueError("MATCH requires every planned call to have been performed")
        if self.status in (MutationStatus.REFUSED, MutationStatus.UNSUPPORTED) and (
            self.call_results
        ):
            raise ValueError("A refused or unsupported mutation performed no call")
        if (
            self.retried is not False
            or self.evidence_domain != QUALIFICATION
            or self.native_evidence is not False
        ):
            raise ValueError("Studio-T0 mutations are single-shot TEST_ONLY_SUPPORT")

    @property
    def mutated(self) -> bool:
        return bool(self.call_results)


@dataclass(frozen=True)
class _LiveItem:
    obj: object
    track_api: str
    track_index: int
    start: int  # timeline-relative
    end: int
    left_offset: int


def _overlaps(start: int, end: int, cut: FrameRange) -> bool:
    return start < cut.end and cut.start < end


class ResolveMutationPort:
    """Capability-gated single-shot mutations with post-mutation read-back verification."""

    def __init__(self, project: object, read_port: ResolveReadPort) -> None:
        if not isinstance(read_port, ResolveReadPort):
            raise TypeError("A ResolveReadPort is required")
        self._project = project
        self._read = read_port
        self._profile = read_port.profile

    # -- helpers --
    def _granted(self, capability: StudioCapability) -> CapabilityGrant:
        return self._profile.grant(capability)

    def _outcome(
        self,
        kind: MutationKind,
        status: MutationStatus,
        issue: PortIssueKind | None,
        detail: str,
        **extra: object,
    ) -> MutationOutcome:
        values: dict[str, object] = {
            "planned": (),
            "call_results": (),
            "readback": VerificationStatus.UNVERIFIED,
            "report": None,
            "readback_read": None,
            "expected": None,
        }
        values.update(extra)
        return MutationOutcome(kind, status, issue, detail, **values)  # type: ignore[arg-type]

    def _gate(
        self, kind: MutationKind, capabilities: Sequence[StudioCapability]
    ) -> MutationOutcome | None:
        for capability in capabilities:
            grant = self._granted(capability)
            if grant is CapabilityGrant.ABSENT:
                return self._outcome(
                    kind,
                    MutationStatus.UNSUPPORTED,
                    PortIssueKind.UNSUPPORTED,
                    f"{capability.value} not available",
                )
            if grant is not CapabilityGrant.GRANTED_TEST_ONLY:
                return self._outcome(
                    kind,
                    MutationStatus.REFUSED,
                    PortIssueKind.UNAVAILABLE,
                    f"{capability.value} not granted (UNKNOWN)",
                )
        return None

    def _live_read(self, kind: MutationKind) -> StudioReadResult | MutationOutcome:
        live = self._read.read()
        if live.actual is None:
            return self._outcome(
                kind,
                MutationStatus.REFUSED,
                PortIssueKind.UNKNOWN,
                f"live read {live.consistency.value}; nothing mutated",
                readback_read=live,
            )
        return live

    def _live_items(self) -> tuple[_LiveItem, ...]:
        """Allowlisted getters only; raises _Blocked/_Invalid on anything UNKNOWN."""
        single = _Pass(self._profile)
        timeline = single.timeline(self._project)
        if timeline is None:
            raise _Invalid("no current timeline")
        t = _K.TIMELINE
        origin = single.int_(
            single.call(timeline, t, "GetStartFrame", _C.READ_TIMELINE_START_FRAME), "start"
        )
        result: list[_LiveItem] = []
        for _, api, _label in _TRACK_API:
            count = single.int_(
                single.call(timeline, t, "GetTrackCount", _C.READ_TRACK_COUNT, api), api
            )
            for index in range(1, (count or 0) + 1):
                listed = single.call(
                    timeline, t, "GetItemListInTrack", _C.READ_TRACK_ITEMS, api, index
                )
                if not isinstance(listed, (list, tuple)):
                    raise _Invalid(f"{api} {index} items UNKNOWN")
                for obj in listed:
                    i = _K.TIMELINE_ITEM
                    start = single.int_(single.call(obj, i, "GetStart", _C.READ_ITEM_START), "s")
                    end = single.int_(
                        single.call(obj, i, "GetEnd", _C.READ_ITEM_END_EXCLUSIVE), "e"
                    )
                    left = single.int_(
                        single.call(obj, i, "GetLeftOffset", _C.READ_ITEM_LEFT_OFFSET), "l"
                    )
                    if start is None or end is None or left is None or origin is None:
                        raise _Invalid(f"{api} {index} geometry UNKNOWN")
                    result.append(_LiveItem(obj, api, index, start - origin, end - origin, left))
        if single.blocked:
            raise _Invalid("live geometry UNKNOWN")
        return tuple(result)

    def _timeline_obj(self) -> object:
        single = _Pass(self._profile)
        timeline = single.timeline(self._project)
        if timeline is None:
            raise _Invalid("no current timeline")
        return timeline

    def _origin(self, timeline: object) -> int:
        single = _Pass(self._profile)
        value = single.int_(
            single.call(timeline, _K.TIMELINE, "GetStartFrame", _C.READ_TIMELINE_START_FRAME),
            "start",
        )
        if value is None:
            raise _Invalid("timeline start UNKNOWN")
        return value

    def _mutate(
        self,
        obj: object,
        kind: ResolveObjectKind,
        method: str,
        cap: StudioCapability,
        *args: object,
    ) -> object:
        return _invoke(self._profile, MUTATION_METHODS, obj, kind, method, cap, *args)

    def _verify(
        self, kind: MutationKind, namespace: str, expected: HandoffTimeline
    ) -> tuple[VerificationStatus, VerificationReport, StudioReadResult]:
        readback = self._read.read()
        diff = diff_studio_read(expected, readback)
        report = verify_roundtrip(
            artifact_revision(namespace, expected.name, expected),
            expected,
            diff,
            provenance=ActualProvenance.IMMEDIATE_REEXPORT,
        )
        return report.status, report, readback

    def _finish(
        self,
        kind: MutationKind,
        namespace: str,
        expected: HandoffTimeline,
        planned: Sequence[PlannedOperation],
        results: Sequence[object],
        failure: str | None,
        confirmation_digest: str | None = None,
    ) -> MutationOutcome:
        status, report, readback = self._verify(kind, namespace, expected)
        if failure is not None:
            return self._outcome(
                kind,
                MutationStatus.FAILED,
                PortIssueKind.UNKNOWN,
                failure + "; stopped, not retried",
                planned=tuple(planned),
                call_results=tuple(results),
                readback=(
                    VerificationStatus.UNVERIFIED if status is VerificationStatus.MATCH else status
                ),
                report=report,
                readback_read=readback,
                expected=expected,
                confirmation_digest=confirmation_digest,
            )
        return self._outcome(
            kind,
            MutationStatus.PERFORMED,
            None,
            f"{len(results)} calls; read-back {status.value}",
            planned=tuple(planned),
            call_results=tuple(results),
            readback=status,
            report=report,
            readback_read=readback,
            expected=expected,
            confirmation_digest=confirmation_digest,
        )

    # -- candidate markers --
    def add_candidate_markers(self, handoff: CandidateHandoff) -> MutationOutcome:
        """Write the handoff's pending candidate markers onto the live anchor items."""
        kind = MutationKind.ADD_CANDIDATE_MARKERS
        if not isinstance(handoff, CandidateHandoff):
            raise TypeError("A CandidateHandoff is required")
        gated = self._gate(kind, (_C.MARKER_ADD_ITEM,))
        if gated is not None:
            return gated
        live = self._live_read(kind)
        if isinstance(live, MutationOutcome):
            return live
        if live.actual is None:
            raise AssertionError("live read carries an Actual")
        base = expected_from_actual(live.actual)
        if timeline_digest(strip_candidate_markers(handoff.timeline)) != timeline_digest(base):
            return self._outcome(
                kind,
                MutationStatus.REFUSED,
                PortIssueKind.STALE,
                "handoff was not built from the live timeline (stale or markers present)",
                readback_read=live,
            )
        try:
            anchors = [
                i
                for i in self._live_items()
                if (i.track_api, i.track_index) == ("video", ANCHOR_TRACK.ordinal)
            ]
        except (_Blocked, _Invalid) as exc:
            return self._outcome(kind, MutationStatus.REFUSED, PortIssueKind.UNKNOWN, str(exc))
        plan: list[tuple[PlannedOperation, _LiveItem, tuple[object, ...]]] = []
        for placed in handoff.candidates:
            target = placed.candidate.timeline_range
            item = next(
                (a for a in anchors if a.start <= target.start and target.end <= a.end), None
            )
            if item is None:
                return self._outcome(
                    kind,
                    MutationStatus.REFUSED,
                    PortIssueKind.UNRESOLVED,
                    f"{placed.candidate_id}: no live anchor item",
                )
            frame_id = placed.marker_range.start - item.left_offset
            color = _COLOR_TO_RESOLVE.get(MarkerColor.YELLOW, "Yellow")
            args: tuple[object, ...] = (
                frame_id,
                color,
                f"{placed.candidate_id} ?",
                placed.candidate.marker_note,
                placed.marker_range.duration,
                placed.candidate_id,
            )
            operation = PlannedOperation(
                OperationKind.ADD_MARKER, "Video 1", target.start, placed.candidate_id
            )
            plan.append((operation, item, args))
        results: list[object] = []
        failure: str | None = None
        for operation, item, args in plan:
            try:
                result = self._mutate(
                    item.obj, _K.TIMELINE_ITEM, "AddMarker", _C.MARKER_ADD_ITEM, *args
                )
            except _Blocked as blocked:
                results.append(None)
                failure = f"{operation.detail}: {blocked.diagnostic.code.value}"
                break
            results.append(result)
            if result is not True:
                failure = f"{operation.detail}: AddMarker returned {result!r}"
                break
        return self._finish(
            kind, "studio-t0-markers", handoff.timeline, [p[0] for p in plan], results, failure
        )

    def remove_candidate_markers(self, candidate_ids: Sequence[str]) -> MutationOutcome:
        """Delete candidate markers by the token stored as customData at add time."""
        kind = MutationKind.REMOVE_CANDIDATE_MARKERS
        tokens = frozenset(candidate_ids)
        gated = self._gate(kind, (_C.MARKER_DELETE_ITEM_BY_CUSTOM_DATA, _C.READ_ITEM_MARKERS))
        if gated is not None:
            return gated
        live = self._live_read(kind)
        if isinstance(live, MutationOutcome):
            return live
        if live.actual is None:
            raise AssertionError("live read carries an Actual")
        expected = strip_candidate_markers(expected_from_actual(live.actual), tokens)
        try:
            items = self._live_items()
            single = _Pass(self._profile)
            plan: list[tuple[PlannedOperation, _LiveItem, str]] = []
            for item in items:
                markers = single.markers(item.obj, "item") or ()
                for marker in markers:
                    token = (
                        None if marker.name is None else parse_candidate_marker_name(marker.name)[0]
                    )
                    if token in tokens:
                        if marker.custom_data != token:
                            return self._outcome(
                                kind,
                                MutationStatus.UNSUPPORTED,
                                PortIssueKind.UNSUPPORTED,
                                f"{token}: marker lacks our customData; delete by hand",
                            )
                        operation = PlannedOperation(
                            OperationKind.DELETE_MARKER,
                            f"{item.track_api} {item.track_index}",
                            item.start,
                            token,
                        )
                        plan.append((operation, item, token))
            if single.blocked:
                raise _Invalid("marker read UNKNOWN")
        except (_Blocked, _Invalid) as exc:
            return self._outcome(kind, MutationStatus.REFUSED, PortIssueKind.UNKNOWN, str(exc))
        results: list[object] = []
        failure: str | None = None
        for operation, item, token in plan:
            try:
                result = self._mutate(
                    item.obj,
                    _K.TIMELINE_ITEM,
                    "DeleteMarkerByCustomData",
                    _C.MARKER_DELETE_ITEM_BY_CUSTOM_DATA,
                    token,
                )
            except _Blocked as blocked:
                results.append(None)
                failure = f"{operation.detail}: {blocked.diagnostic.code.value}"
                break
            results.append(result)
            if result is not True:
                failure = f"{operation.detail}: DeleteMarkerByCustomData returned {result!r}"
                break
        return self._finish(
            kind, "studio-t0-markers", expected, [p[0] for p in plan], results, failure
        )

    # -- cuts in place --
    def plan_cuts_in_place(
        self,
        actual: ReimportedTimeline,
        cuts: Sequence[FrameRange],
        policies: Mapping[str, TrackCutPolicy],
    ) -> tuple[tuple[PlannedOperation, ...], tuple[str, ...]]:
        """(operations, unsupported reasons). Pure: no call is made.

        Only CUT_WITH_SOURCE tracks lose frames; SHIFT_WITH_RIPPLE tracks are only
        moved by the ripple; KEEP_IN_PLACE is not expressible in place. No track is
        ever deleted, merged or flattened, and nothing is rebuilt.
        """
        split = self._granted(_C.SPLIT_ITEM_AT_FRAME) is CapabilityGrant.GRANTED_TEST_ONLY
        selective = self._granted(_C.TRACK_SELECTIVE_RIPPLE) is CapabilityGrant.GRANTED_TEST_ONLY
        operations: list[PlannedOperation] = []
        reasons: list[str] = []
        for _, track in track_keys(actual):
            policy = policies.get(track.name, TrackCutPolicy.UNKNOWN)
            if policy is TrackCutPolicy.UNKNOWN:
                reasons.append(f"{track.name}: track policy UNKNOWN")
            elif policy is TrackCutPolicy.KEEP_IN_PLACE and cuts and not selective:
                reasons.append(
                    f"{track.name}: KEEP_IN_PLACE needs track-selective ripple "
                    "(TRACK_SELECTIVE_RIPPLE NOT_AVAILABLE)"
                )
        if reasons:
            return (), tuple(reasons)
        cut_tracks = ",".join(
            sorted(n for n, p in policies.items() if p is TrackCutPolicy.CUT_WITH_SOURCE)
        )
        for cut in cuts:
            spans: list[tuple[int, int]] = []
            needed: list[tuple[str, int]] = []
            conflict = False
            for key, track in track_keys(actual):
                if key.kind not in (HandoffTrackKind.VIDEO, HandoffTrackKind.AUDIO):
                    continue
                policy = policies[track.name]
                for start, clip in track.placements():
                    end = start + clip.duration
                    if not _overlaps(start, end, cut):
                        continue
                    if policy is not TrackCutPolicy.CUT_WITH_SOURCE:
                        reasons.append(
                            f"[{cut.start},{cut.end}): LAYER_CONFLICT on {track.name} "
                            f"({policy.value} item overlaps the cut; never cut)"
                        )
                        conflict = True
                        continue
                    if start < cut.start:
                        needed.append((track.name, cut.start))
                    if end > cut.end:
                        needed.append((track.name, cut.end))
                    spans.append((max(start, cut.start), min(end, cut.end)))
            if conflict:
                continue
            covered = cut.start
            for start, end in sorted(spans):
                if start > covered:
                    break
                covered = max(covered, end)
            if covered < cut.end:
                reasons.append(
                    f"[{cut.start},{cut.end}): not fully covered by CUT_WITH_SOURCE items "
                    "(gap frames cannot be deleted in place)"
                )
                continue
            if needed and not split:
                frames = ", ".join(f"{t}@{f}" for t, f in sorted(set(needed)))
                reasons.append(
                    f"[{cut.start},{cut.end}): needs a split at {frames}; no split API "
                    "(SPLIT_ITEM_AT_FRAME NOT_AVAILABLE)"
                )
                continue
            for track_name, frame in sorted(set(needed)):
                operations.append(
                    PlannedOperation(OperationKind.SPLIT_AT_FRAME, track_name, frame, "test-only")
                )
            operations.append(
                PlannedOperation(
                    OperationKind.DELETE_ITEMS_RIPPLE,
                    cut_tracks,
                    cut.start,
                    f"[{cut.start},{cut.end}) {cut.duration}f",
                )
            )
        return tuple(operations), tuple(reasons)

    def apply_confirmed_cuts(
        self,
        confirmation: ApplyConfirmation,
        *,
        confirmed_digest: str,
        track_policies: Mapping[str, TrackCutPolicy] | None = None,
    ) -> MutationOutcome:
        """Apply APPLY-001 confirmed cuts to the live timeline in place (never a rebuild).

        Raises ``apply_cuts.ApplyRefused`` unless ``confirmed_digest`` equals the
        confirmation digest. The Expected is APPLY-001's own result (same
        geometry as the file path) keeping the live timeline name.

        ``track_policies`` maps Actual track names (``Video 1``...) to a
        :class:`TrackCutPolicy`; ``None`` means today's APPLY-001 semantics (every
        track CUT_WITH_SOURCE). Until LAYER-001 lands APPLY-001's Expected cuts every
        track, so a non-CUT track overlapping a cut is reported as LAYER_CONFLICT
        (UNSUPPORTED in place) instead of silently diverging from the Expected.
        """
        kind = MutationKind.APPLY_CUTS_IN_PLACE
        applied = apply_approved_cuts(confirmation, confirmed_digest=confirmed_digest)
        digest = confirmation.confirmation_digest
        expected = replace(applied.timeline, name=confirmation.actual.name)
        gated = self._gate(kind, (_C.DELETE_ITEMS_RIPPLE, _C.RIPPLE_SPAN_SEMANTICS))
        if gated is not None:
            return replace(gated, confirmation_digest=digest, fallback=Fallback.FILE_PATH)
        live = self._live_read(kind)
        if isinstance(live, MutationOutcome):
            return replace(live, confirmation_digest=digest)
        if live.actual is None:
            raise AssertionError("live read carries an Actual")
        if timeline_digest(live.actual) != confirmation.actual_digest:
            return self._outcome(
                kind,
                MutationStatus.REFUSED,
                PortIssueKind.STALE,
                "live timeline differs from the confirmed Actual (stale); nothing mutated",
                readback_read=live,
                confirmation_digest=digest,
            )
        cuts = tuple(c.timeline_range for c in confirmation.approved_cuts)
        for cut in cuts:
            if any(lock.frame_range.overlaps(cut) for lock in confirmation.locks):
                return self._outcome(
                    kind,
                    MutationStatus.REFUSED,
                    PortIssueKind.CONFLICT,
                    "a cut overlaps a HARD_LOCK",
                    confirmation_digest=digest,
                )
        policies: Mapping[str, TrackCutPolicy] = MappingProxyType(
            {t.name: TrackCutPolicy.CUT_WITH_SOURCE for t in live.actual.tracks}
            if track_policies is None
            else dict(track_policies)
        )
        cut_tracks = {n for n, p in policies.items() if p is TrackCutPolicy.CUT_WITH_SOURCE}
        planned, reasons = self.plan_cuts_in_place(live.actual, cuts, policies)
        if reasons:
            return self._outcome(
                kind,
                MutationStatus.UNSUPPORTED,
                PortIssueKind.UNSUPPORTED,
                "in place unsupported; use the file path (APPLY-001 XML): " + "; ".join(reasons),
                planned=planned,
                expected=expected,
                confirmation_digest=digest,
                fallback=Fallback.FILE_PATH,
            )
        if any(p.kind is OperationKind.SPLIT_AT_FRAME for p in planned):
            gated = self._gate(kind, (_C.SPLIT_ITEM_AT_FRAME,))
            if gated is not None:
                return replace(gated, confirmation_digest=digest, fallback=Fallback.FILE_PATH)
        results: list[object] = []
        failure: str | None = None
        try:
            timeline = self._timeline_obj()
            origin = self._origin(timeline)
            # Last cut first: a ripple only moves material after the deleted span.
            for cut in reversed(cuts):
                splits = [
                    p
                    for p in planned
                    if p.kind is OperationKind.SPLIT_AT_FRAME and p.frame in (cut.start, cut.end)
                ]
                for split in sorted(splits, key=lambda p: (-p.frame, p.track)):
                    label, index = split.track.rsplit(" ", 1)
                    result = self._mutate(
                        timeline,
                        _K.TIMELINE,
                        TEST_ONLY_SPLIT_METHOD,
                        _C.SPLIT_ITEM_AT_FRAME,
                        label.lower(),
                        int(index),
                        origin + split.frame,
                    )
                    results.append(result)
                    if result is not True:
                        failure = f"split {split.track}@{split.frame} returned {result!r}"
                        break
                if failure is not None:
                    break
                inside = [
                    i.obj
                    for i in self._live_items()
                    if cut.start <= i.start
                    and i.end <= cut.end
                    and f"{i.track_api.capitalize()} {i.track_index}" in cut_tracks
                ]
                result = self._mutate(
                    timeline, _K.TIMELINE, "DeleteClips", _C.DELETE_ITEMS_RIPPLE, inside, True
                )
                results.append(result)
                if result is not True:
                    failure = f"DeleteClips [{cut.start},{cut.end}) returned {result!r}"
                    break
        except _Blocked as blocked:
            results.append(None)
            failure = f"{blocked.diagnostic.location}: {blocked.diagnostic.code.value}"
        except _Invalid as exc:
            if not results:
                return self._outcome(
                    kind,
                    MutationStatus.REFUSED,
                    PortIssueKind.UNKNOWN,
                    str(exc),
                    confirmation_digest=digest,
                )
            results.append(None)
            failure = str(exc)
        return self._finish(kind, "studio-t0-apply", expected, planned, results, failure, digest)


TrackGeometry = tuple[str, int, tuple[tuple[int, str, int, int], ...]]


def cut_geometry(timeline: HandoffTimeline | ReimportedTimeline) -> tuple[TrackGeometry, ...]:
    """Canonical applied-cut geometry: per track kind/ordinal, (start, media, source) runs."""
    result: list[TrackGeometry] = []
    for key, track in track_keys(timeline):
        placements = tuple(
            (start, clip.media.media_id, clip.source_range.start, clip.source_range.end)
            for start, clip in track.placements()
        )
        result.append((key.kind.value, key.ordinal, placements))
    return tuple(result)


def candidate_sets_equal(a: CandidateHandoff, b: CandidateHandoff) -> bool:
    """Same candidate ids, ranges, anchors and marker ranges (transport-independent)."""
    if len(a.candidates) != len(b.candidates):
        return False
    return all(
        x.candidate == y.candidate
        and x.anchor_track == y.anchor_track
        and x.marker_range == y.marker_range
        and x.media_id == y.media_id
        for x, y in zip(a.candidates, b.candidates, strict=True)
    )
