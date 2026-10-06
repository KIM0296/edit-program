"""ADR-022 immutable observations and feature input readiness, never Resolve authority."""

from dataclasses import dataclass
from enum import Enum

from .domain import TrackType
from .temporal_mapping import (
    FrameRate,
    MappingKind,
    NativeSnapshotRef,
    SourceFrameRange,
    TimelineFrameRange,
)


class IdentityScope(str, Enum):
    PERSISTENT_VERIFIED = "PERSISTENT_VERIFIED"
    SESSION_LOCAL_VERIFIED = "SESSION_LOCAL_VERIFIED"
    SNAPSHOT_LOCAL = "SNAPSHOT_LOCAL"
    UNKNOWN = "UNKNOWN"


class IdentityBasis(str, Enum):
    NATIVE = "NATIVE"
    ADAPTER_VERIFIED = "ADAPTER_VERIFIED"
    SNAPSHOT_ASSIGNED = "SNAPSHOT_ASSIGNED"
    UNKNOWN = "UNKNOWN"
    FILENAME_ONLY = "FILENAME_ONLY"


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Opaque references/versions must be nonempty strings")


def _optional_text(value: str | None) -> None:
    if value is not None:
        _text(value)


@dataclass(frozen=True)
class IdentityRef:
    """Caller-declared categorical evidence, not a runtime verification result."""

    ref: str
    scope: IdentityScope
    basis: IdentityBasis

    def __post_init__(self) -> None:
        _text(self.ref)
        if not isinstance(self.scope, IdentityScope) or not isinstance(self.basis, IdentityBasis):
            raise TypeError("Identity scope and basis must be categorical")
        if self.basis == IdentityBasis.FILENAME_ONLY:
            raise ValueError("Filename-only identity is not authoritative")
        if self.basis == IdentityBasis.UNKNOWN and self.scope != IdentityScope.UNKNOWN:
            raise ValueError("Unknown basis cannot claim verified identity")
        if self.basis == IdentityBasis.SNAPSHOT_ASSIGNED and self.scope not in (
            IdentityScope.SNAPSHOT_LOCAL,
            IdentityScope.UNKNOWN,
        ):
            raise ValueError("Snapshot-assigned refs cannot claim longer lifetime")


class CapabilityState(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class CapabilityKind(str, Enum):
    TIMELINE_IDENTITY = "TIMELINE_IDENTITY"
    TRACK_IDENTITY = "TRACK_IDENTITY"
    TRACK_TYPE = "TRACK_TYPE"
    PLACEMENT_IDENTITY = "PLACEMENT_IDENTITY"
    MEDIA_IDENTITY = "MEDIA_IDENTITY"
    TIMELINE_RANGE = "TIMELINE_RANGE"
    SOURCE_RANGE = "SOURCE_RANGE"
    FRAME_RATE = "FRAME_RATE"
    RETIME = "RETIME"
    FRESHNESS = "FRESHNESS"
    CAPTURE_CONSISTENCY = "CAPTURE_CONSISTENCY"
    EFFECTS = "EFFECTS"
    TRANSITIONS = "TRANSITIONS"
    KEYFRAMES = "KEYFRAMES"
    COMPOUND = "COMPOUND"
    MULTICAM = "MULTICAM"
    NESTED = "NESTED"
    GENERATOR = "GENERATOR"
    LINKED_AV = "LINKED_AV"
    SYNC_RELATIONSHIP = "SYNC_RELATIONSHIP"
    TRACK_LOCK = "TRACK_LOCK"
    TRACK_MUTE = "TRACK_MUTE"
    TRACK_ENABLE = "TRACK_ENABLE"
    TRACK_SOLO = "TRACK_SOLO"
    TRACK_AUTOSELECT = "TRACK_AUTOSELECT"


_TRACK_FLAGS = frozenset(
    (
        CapabilityKind.TRACK_LOCK,
        CapabilityKind.TRACK_MUTE,
        CapabilityKind.TRACK_ENABLE,
        CapabilityKind.TRACK_SOLO,
        CapabilityKind.TRACK_AUTOSELECT,
    )
)
_PLACEMENT_FLAGS = frozenset(
    (
        CapabilityKind.EFFECTS,
        CapabilityKind.TRANSITIONS,
        CapabilityKind.KEYFRAMES,
        CapabilityKind.COMPOUND,
        CapabilityKind.MULTICAM,
        CapabilityKind.NESTED,
        CapabilityKind.GENERATOR,
        CapabilityKind.LINKED_AV,
        CapabilityKind.SYNC_RELATIONSHIP,
    )
)


@dataclass(frozen=True)
class AdapterCapability:
    kind: CapabilityKind
    state: CapabilityState

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CapabilityKind) or not isinstance(self.state, CapabilityState):
            raise TypeError("Capability requires typed kind/state")


@dataclass(frozen=True)
class CapabilityManifest:
    entries: tuple[AdapterCapability, ...]

    def __post_init__(self) -> None:
        entries = tuple(self.entries)
        if any(not isinstance(e, AdapterCapability) for e in entries):
            raise TypeError("Manifest requires typed entries")
        if len({e.kind for e in entries}) != len(entries):
            raise ValueError("Duplicate capability declaration")
        object.__setattr__(self, "entries", tuple(sorted(entries, key=lambda e: e.kind.value)))

    def state(self, kind: CapabilityKind) -> CapabilityState:
        if not isinstance(kind, CapabilityKind):
            raise TypeError("Capability lookup requires typed kind")
        return next((e.state for e in self.entries if e.kind == kind), CapabilityState.UNKNOWN)


class ObservedValue(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ObservedFlag:
    kind: CapabilityKind
    value: ObservedValue

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CapabilityKind) or not isinstance(self.value, ObservedValue):
            raise TypeError("Observation requires typed kind/value")
        if self.kind not in _TRACK_FLAGS | _PLACEMENT_FLAGS:
            raise ValueError("This capability has a dedicated typed observation")


def _flags(
    values: tuple[ObservedFlag, ...], allowed: frozenset[CapabilityKind]
) -> tuple[ObservedFlag, ...]:
    flags = tuple(values)
    if any(not isinstance(f, ObservedFlag) for f in flags):
        raise TypeError("Observed flags must be typed")
    if any(f.kind not in allowed for f in flags) or len({f.kind for f in flags}) != len(flags):
        raise ValueError("Invalid/duplicate flag for this native object")
    return tuple(sorted(flags, key=lambda f: f.kind.value))


class CaptureConsistency(str, Enum):
    CONSISTENT = "CONSISTENT"
    UNSTABLE = "UNSTABLE"
    UNVERIFIED = "UNVERIFIED"


class SnapshotCompleteness(str, Enum):
    COMPLETE_FOR_DECLARED_CAPABILITIES = "COMPLETE_FOR_DECLARED_CAPABILITIES"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class AdapterProvenance:
    adapter_name: str
    adapter_version: str
    snapshot_contract_version: str
    resolve_version: str | None = None
    platform: str | None = None

    def __post_init__(self) -> None:
        for value in (self.adapter_name, self.adapter_version, self.snapshot_contract_version):
            _text(value)
        _optional_text(self.resolve_version)
        _optional_text(self.platform)


@dataclass(frozen=True)
class NativeTrackSnapshot:
    capture_id: str
    track_ref: IdentityRef
    track_type: TrackType
    placement_refs: tuple[str, ...]
    native_index: int | None = None
    display_name: str | None = None
    observations: tuple[ObservedFlag, ...] = ()

    def __post_init__(self) -> None:
        _text(self.capture_id)
        if not isinstance(self.track_ref, IdentityRef) or not isinstance(
            self.track_type, TrackType
        ):
            raise TypeError("Track requires typed identity/type")
        refs = tuple(self.placement_refs)
        for ref in refs:
            _text(ref)
        if len(set(refs)) != len(refs):
            raise ValueError("Duplicate membership")
        if self.native_index is not None and (
            type(self.native_index) is not int or self.native_index < 0
        ):
            raise ValueError("Descriptive index must be a nonnegative integer")
        if self.display_name is not None and not isinstance(self.display_name, str):
            raise TypeError("Display name is descriptive text only")
        object.__setattr__(self, "placement_refs", tuple(sorted(refs)))
        object.__setattr__(self, "observations", _flags(self.observations, _TRACK_FLAGS))


@dataclass(frozen=True)
class NativePlacementSnapshot:
    capture_id: str
    object_ref: IdentityRef
    track_ref: str
    media_ref: IdentityRef
    timeline_range: TimelineFrameRange | None
    source_range: SourceFrameRange | None
    timeline_rate: FrameRate | None
    source_rate: FrameRate | None
    retime_kind: MappingKind
    observations: tuple[ObservedFlag, ...] = ()

    def __post_init__(self) -> None:
        _text(self.capture_id)
        _text(self.track_ref)
        if not isinstance(self.object_ref, IdentityRef) or not isinstance(
            self.media_ref, IdentityRef
        ):
            raise TypeError("Placement and media identity must be distinct typed references")
        for value, expected in (
            (self.timeline_range, TimelineFrameRange),
            (self.source_range, SourceFrameRange),
            (self.timeline_rate, FrameRate),
            (self.source_rate, FrameRate),
        ):
            if value is not None and not isinstance(value, expected):
                raise TypeError("Native ranges/rates must be typed or explicitly missing")
        if not isinstance(self.retime_kind, MappingKind):
            raise TypeError("Retime observation must use ADR-021 vocabulary")
        object.__setattr__(self, "observations", _flags(self.observations, _PLACEMENT_FLAGS))


@dataclass(frozen=True)
class NativeTimelineSnapshot:
    capture_id: str
    timeline_ref: IdentityRef
    timeline_version: int
    state_token: str | None
    timeline_rate: FrameRate | None
    tracks: tuple[NativeTrackSnapshot, ...]
    placements: tuple[NativePlacementSnapshot, ...]
    adapter_provenance: AdapterProvenance
    capabilities: CapabilityManifest
    capture_consistency: CaptureConsistency
    completeness: SnapshotCompleteness
    consistency_evidence_ref: str | None = None

    def __post_init__(self) -> None:
        _text(self.capture_id)
        _optional_text(self.state_token)
        _optional_text(self.consistency_evidence_ref)
        if type(self.timeline_version) is not int or self.timeline_version < 0:
            raise ValueError("Timeline version must be a nonnegative integer")
        for value, expected in (
            (self.timeline_ref, IdentityRef),
            (self.adapter_provenance, AdapterProvenance),
            (self.capabilities, CapabilityManifest),
            (self.capture_consistency, CaptureConsistency),
            (self.completeness, SnapshotCompleteness),
        ):
            if not isinstance(value, expected):
                raise TypeError("Snapshot metadata must be typed")
        if self.timeline_rate is not None and not isinstance(self.timeline_rate, FrameRate):
            raise TypeError("Timeline rate must be exact or absent")
        tracks, placements = tuple(self.tracks), tuple(self.placements)
        if any(not isinstance(t, NativeTrackSnapshot) for t in tracks) or any(
            not isinstance(p, NativePlacementSnapshot) for p in placements
        ):
            raise TypeError("Snapshot members must be typed")
        if len({t.track_ref.ref for t in tracks}) != len(tracks) or len(
            {p.object_ref.ref for p in placements}
        ) != len(placements):
            raise ValueError("Duplicate track/placement identity")
        if any(t.capture_id != self.capture_id for t in tracks) or any(
            p.capture_id != self.capture_id for p in placements
        ):
            raise ValueError("Mixed captures cannot masquerade as one snapshot")
        if self.timeline_rate is not None and any(
            p.timeline_rate is not None and p.timeline_rate != self.timeline_rate
            for p in placements
        ):
            raise ValueError("Placement timeline rate disagrees with captured timeline")
        track_refs = {t.track_ref.ref for t in tracks}
        if any(p.track_ref not in track_refs for p in placements):
            raise ValueError("Unknown placement track")
        for track in tracks:
            if set(track.placement_refs) != {
                p.object_ref.ref for p in placements if p.track_ref == track.track_ref.ref
            }:
                raise ValueError("Track membership disagrees with captured placements")
        if (
            self.capture_consistency == CaptureConsistency.CONSISTENT
            and self.consistency_evidence_ref is None
        ):
            raise ValueError("CONSISTENT needs supplied capture evidence")
        object.__setattr__(self, "tracks", tracks)
        object.__setattr__(self, "placements", placements)
        for kind, present, known in _field_states(self):
            state = self.capabilities.state(kind)
            if state != CapabilityState.SUPPORTED and known:
                raise ValueError(
                    "Unsupported/unknown capability cannot supply known observed value"
                )
            if (
                state == CapabilityState.SUPPORTED
                and not present
                and self.completeness == SnapshotCompleteness.COMPLETE_FOR_DECLARED_CAPABILITIES
            ):
                raise ValueError("Missing supported field requires PARTIAL capture")


def _field_states(
    snapshot: NativeTimelineSnapshot,
) -> tuple[tuple[CapabilityKind, bool, bool], ...]:
    """Structural presence and observed knowledge are deliberately separate."""
    fields = [
        (
            CapabilityKind.TIMELINE_IDENTITY,
            True,
            snapshot.timeline_ref.scope != IdentityScope.UNKNOWN,
        ),
        (
            CapabilityKind.FRAME_RATE,
            snapshot.timeline_rate is not None,
            snapshot.timeline_rate is not None,
        ),
        (
            CapabilityKind.FRESHNESS,
            snapshot.state_token is not None,
            snapshot.state_token is not None,
        ),
        (
            CapabilityKind.CAPTURE_CONSISTENCY,
            True,
            snapshot.capture_consistency != CaptureConsistency.UNVERIFIED,
        ),
    ]
    for track in snapshot.tracks:
        fields.append((CapabilityKind.TRACK_TYPE, True, track.track_type != TrackType.UNKNOWN))
        fields.append(
            (CapabilityKind.TRACK_IDENTITY, True, track.track_ref.scope != IdentityScope.UNKNOWN)
        )
        for kind in _TRACK_FLAGS:
            flag = next((f for f in track.observations if f.kind == kind), None)
            fields.append(
                (kind, flag is not None, flag is not None and flag.value != ObservedValue.UNKNOWN)
            )
    for placement in snapshot.placements:
        fields.extend(
            (
                (
                    CapabilityKind.PLACEMENT_IDENTITY,
                    True,
                    placement.object_ref.scope != IdentityScope.UNKNOWN,
                ),
                (
                    CapabilityKind.MEDIA_IDENTITY,
                    True,
                    placement.media_ref.scope != IdentityScope.UNKNOWN,
                ),
                (
                    CapabilityKind.TIMELINE_RANGE,
                    placement.timeline_range is not None,
                    placement.timeline_range is not None,
                ),
                (
                    CapabilityKind.SOURCE_RANGE,
                    placement.source_range is not None,
                    placement.source_range is not None,
                ),
                (
                    CapabilityKind.FRAME_RATE,
                    placement.timeline_rate is not None,
                    placement.timeline_rate is not None,
                ),
                (
                    CapabilityKind.FRAME_RATE,
                    placement.source_rate is not None,
                    placement.source_rate is not None,
                ),
                (CapabilityKind.RETIME, True, placement.retime_kind != MappingKind.UNKNOWN),
            )
        )
        for kind in _PLACEMENT_FLAGS:
            flag = next((f for f in placement.observations if f.kind == kind), None)
            fields.append(
                (kind, flag is not None, flag is not None and flag.value != ObservedValue.UNKNOWN)
            )
    return tuple(fields)


@dataclass(frozen=True)
class FeatureRequirementProfile:
    profile_id: str
    profile_version: str
    required_capabilities: tuple[CapabilityKind, ...]
    allowed_identity_scopes: tuple[IdentityScope, ...]
    require_complete: bool = True
    require_consistent_capture: bool = True
    require_freshness: bool = True
    allowed_retime_kinds: tuple[MappingKind, ...] = (
        MappingKind.IDENTITY_1X,
        MappingKind.AFFINE_FORWARD,
    )

    def __post_init__(self) -> None:
        _text(self.profile_id)
        _text(self.profile_version)
        for name, expected in (
            ("required_capabilities", CapabilityKind),
            ("allowed_identity_scopes", IdentityScope),
            ("allowed_retime_kinds", MappingKind),
        ):
            values = tuple(getattr(self, name))
            if any(not isinstance(v, expected) for v in values):
                raise TypeError("Profile requirements must be typed")
            object.__setattr__(self, name, tuple(sorted(set(values), key=lambda v: v.value)))
        if any(
            type(v) is not bool
            for v in (
                self.require_complete,
                self.require_consistent_capture,
                self.require_freshness,
            )
        ):
            raise TypeError("Profile requirement switches must be bool")


PAUSE_ANALYSIS = FeatureRequirementProfile(
    "PAUSE_ANALYSIS",
    "v1",
    (
        CapabilityKind.TIMELINE_IDENTITY,
        CapabilityKind.TRACK_IDENTITY,
        CapabilityKind.TRACK_TYPE,
        CapabilityKind.PLACEMENT_IDENTITY,
        CapabilityKind.MEDIA_IDENTITY,
        CapabilityKind.TIMELINE_RANGE,
        CapabilityKind.SOURCE_RANGE,
        CapabilityKind.FRAME_RATE,
        CapabilityKind.RETIME,
        CapabilityKind.FRESHNESS,
        CapabilityKind.CAPTURE_CONSISTENCY,
    ),
    (
        IdentityScope.PERSISTENT_VERIFIED,
        IdentityScope.SESSION_LOCAL_VERIFIED,
        IdentityScope.SNAPSHOT_LOCAL,
    ),
)


class ReadinessStatus(str, Enum):
    READY = "READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    STALE = "STALE"
    UNSUPPORTED = "UNSUPPORTED"
    UNVERIFIED = "UNVERIFIED"


class ReadinessReason(str, Enum):
    SUFFICIENT_INPUT = "SUFFICIENT_INPUT"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    UNSUPPORTED_CONTRACT = "UNSUPPORTED_CONTRACT"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    UNKNOWN_OBSERVATION = "UNKNOWN_OBSERVATION"
    PARTIAL_CAPTURE = "PARTIAL_CAPTURE"
    UNSTABLE_CAPTURE = "UNSTABLE_CAPTURE"
    UNVERIFIED_CAPTURE = "UNVERIFIED_CAPTURE"
    MISSING_FRESHNESS = "MISSING_FRESHNESS"
    INSUFFICIENT_IDENTITY = "INSUFFICIENT_IDENTITY"
    UNSUPPORTED_RETIME = "UNSUPPORTED_RETIME"
    NO_PLACEMENTS = "NO_PLACEMENTS"


@dataclass(frozen=True)
class ReadinessIssue:
    reason: ReadinessReason
    subject_ref: str
    capability: CapabilityKind | None = None

    def __post_init__(self) -> None:
        _text(self.subject_ref)
        if not isinstance(self.reason, ReadinessReason):
            raise TypeError("Readiness reason must be typed")
        if self.capability is not None and not isinstance(self.capability, CapabilityKind):
            raise TypeError("Issue capability must be typed")


@dataclass(frozen=True)
class ReadinessResult:
    snapshot: NativeTimelineSnapshot
    profile: FeatureRequirementProfile
    current_snapshot: NativeSnapshotRef | None
    status: ReadinessStatus
    issues: tuple[ReadinessIssue, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, NativeTimelineSnapshot) or not isinstance(
            self.profile, FeatureRequirementProfile
        ):
            raise TypeError("Readiness retains typed snapshot and profile")
        if self.current_snapshot is not None and not isinstance(
            self.current_snapshot, NativeSnapshotRef
        ):
            raise TypeError("Current snapshot reference must be typed")
        if not isinstance(self.status, ReadinessStatus):
            raise TypeError("Readiness status must be typed")
        issues = tuple(self.issues)
        if not issues or any(not isinstance(i, ReadinessIssue) for i in issues):
            raise ValueError("Readiness requires typed issues")
        if (self.status == ReadinessStatus.READY) != all(
            i.reason == ReadinessReason.SUFFICIENT_INPUT for i in issues
        ):
            raise ValueError("Only READY can have exclusively sufficient-input diagnostics")
        object.__setattr__(
            self,
            "issues",
            tuple(
                sorted(
                    set(issues),
                    key=lambda i: (
                        i.reason.value,
                        i.subject_ref,
                        i.capability.value if i.capability else "",
                    ),
                )
            ),
        )


def evaluate_readiness(
    snapshot: NativeTimelineSnapshot,
    profile: FeatureRequirementProfile,
    current_snapshot: NativeSnapshotRef | None = None,
) -> ReadinessResult:
    """Assess supplied analysis requirements only; no mapping or native API call."""
    if not isinstance(snapshot, NativeTimelineSnapshot) or not isinstance(
        profile, FeatureRequirementProfile
    ):
        raise TypeError("Readiness requires immutable snapshot/profile")
    if current_snapshot is not None and not isinstance(current_snapshot, NativeSnapshotRef):
        raise TypeError("Current snapshot reference must be typed")
    issues: list[ReadinessIssue] = []
    statuses: set[ReadinessStatus] = set()
    subject = snapshot.timeline_ref.ref

    def issue(
        status: ReadinessStatus,
        reason: ReadinessReason,
        ref: str = subject,
        capability: CapabilityKind | None = None,
    ) -> None:
        statuses.add(status)
        issues.append(ReadinessIssue(reason, ref, capability))

    if snapshot.adapter_provenance.snapshot_contract_version != "v1":
        issue(ReadinessStatus.UNSUPPORTED, ReadinessReason.UNSUPPORTED_CONTRACT)
    if current_snapshot is not None and (
        current_snapshot.timeline_id != subject
        or current_snapshot.timeline_version != snapshot.timeline_version
        or (
            snapshot.state_token is not None
            and current_snapshot.state_token != snapshot.state_token
        )
    ):
        issue(ReadinessStatus.STALE, ReadinessReason.SNAPSHOT_MISMATCH)
    if profile.require_freshness and (snapshot.state_token is None or current_snapshot is None):
        issue(ReadinessStatus.UNVERIFIED, ReadinessReason.MISSING_FRESHNESS)
    if profile.require_complete and snapshot.completeness == SnapshotCompleteness.PARTIAL:
        issue(ReadinessStatus.REVIEW_REQUIRED, ReadinessReason.PARTIAL_CAPTURE)
    if snapshot.capture_consistency == CaptureConsistency.UNSTABLE:
        issue(ReadinessStatus.REVIEW_REQUIRED, ReadinessReason.UNSTABLE_CAPTURE)
    elif (
        profile.require_consistent_capture
        and snapshot.capture_consistency == CaptureConsistency.UNVERIFIED
    ):
        issue(ReadinessStatus.UNVERIFIED, ReadinessReason.UNVERIFIED_CAPTURE)
    if not snapshot.placements:
        issue(ReadinessStatus.REVIEW_REQUIRED, ReadinessReason.NO_PLACEMENTS)
    identities = (
        (snapshot.timeline_ref,)
        + tuple(t.track_ref for t in snapshot.tracks)
        + tuple(identity for p in snapshot.placements for identity in (p.object_ref, p.media_ref))
    )
    for identity in identities:
        if identity.scope not in profile.allowed_identity_scopes:
            issue(
                ReadinessStatus.REVIEW_REQUIRED, ReadinessReason.INSUFFICIENT_IDENTITY, identity.ref
            )
    for kind in profile.required_capabilities:
        state = snapshot.capabilities.state(kind)
        if state == CapabilityState.UNSUPPORTED:
            issue(
                ReadinessStatus.UNSUPPORTED, ReadinessReason.UNSUPPORTED_CAPABILITY, capability=kind
            )
        elif state == CapabilityState.UNKNOWN:
            issue(ReadinessStatus.UNVERIFIED, ReadinessReason.UNKNOWN_CAPABILITY, capability=kind)
        if any(k == kind and not known for k, _, known in _field_states(snapshot)):
            issue(ReadinessStatus.UNVERIFIED, ReadinessReason.UNKNOWN_OBSERVATION, capability=kind)
    if CapabilityKind.RETIME in profile.required_capabilities:
        for placement in snapshot.placements:
            if (
                placement.retime_kind != MappingKind.UNKNOWN
                and placement.retime_kind not in profile.allowed_retime_kinds
            ):
                issue(
                    ReadinessStatus.UNSUPPORTED,
                    ReadinessReason.UNSUPPORTED_RETIME,
                    placement.object_ref.ref,
                )
    status = next(
        (
            s
            for s in (
                ReadinessStatus.STALE,
                ReadinessStatus.UNSUPPORTED,
                ReadinessStatus.REVIEW_REQUIRED,
                ReadinessStatus.UNVERIFIED,
            )
            if s in statuses
        ),
        ReadinessStatus.READY,
    )
    if not issues:
        issues.append(ReadinessIssue(ReadinessReason.SUFFICIENT_INPUT, subject))
    return ReadinessResult(snapshot, profile, current_snapshot, status, tuple(issues))
