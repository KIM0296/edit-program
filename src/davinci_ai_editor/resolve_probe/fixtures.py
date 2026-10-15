"""ADR-034 static fixture comparison; no materialization or native coordinate conversion."""

from dataclasses import dataclass
from enum import Enum

from ..domain import FrameRange
from ..native_snapshot import CapabilityKind
from .model import Context, FixtureResult, ProbeSnapshot, text
from .values import NativeValue, freeze, semantic


class RoleStatus(str, Enum):
    UNIQUE = "UNIQUE"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class PlacementRole:
    role: str
    track_type: str
    track_index: int
    asset_role: str
    timeline_offset: FrameRange
    source_range: FrameRange

    def __post_init__(self) -> None:
        text(self.role)
        if (
            self.track_type not in ("video", "audio")
            or type(self.track_index) is not int
            or self.track_index < 1
        ):
            raise ValueError("Exact declared track required")


@dataclass(frozen=True)
class AssetBinding:
    asset_role: str
    media_unique_id: str
    asset_sha256: str
    package_digest: str
    evidence_ref: str

    def __post_init__(self) -> None:
        from .model import APPROVED_PACKAGE_DIGEST

        for v in (self.asset_role, self.media_unique_id, self.asset_sha256, self.evidence_ref):
            text(v)
        if self.package_digest != APPROVED_PACKAGE_DIGEST or len(self.asset_sha256) != 64:
            raise ValueError("Approved asset provenance required")


@dataclass(frozen=True)
class FixtureInput:
    context: Context
    timeline_id: str
    fixture_instance: str
    assets: tuple[AssetBinding, ...]
    coordinate_evidence_ref: str | None
    required_project_settings: tuple[tuple[str, NativeValue], ...]
    include_optional_audio: bool = True
    item_marker_host_id: str | None = None
    required_risks: tuple[CapabilityKind, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_risks", tuple(self.required_risks))
        if any(not isinstance(v, CapabilityKind) for v in self.required_risks):
            raise TypeError("Typed required capability axis")
        if not isinstance(self.context, Context):
            raise TypeError("Catalog context required")
        text(self.timeline_id)
        text(self.fixture_instance)
        object.__setattr__(self, "assets", tuple(self.assets))
        object.__setattr__(
            self,
            "required_project_settings",
            tuple(tuple(p) for p in self.required_project_settings),
        )
        if any(not isinstance(a, AssetBinding) for a in self.assets):
            raise TypeError("Typed asset binding required")
        if len({a.asset_role for a in self.assets}) != len(self.assets):
            raise ValueError("Duplicate asset role")
        for key, value in self.required_project_settings:
            text(key)
            if not isinstance(value, NativeValue):
                raise TypeError("Typed setting expectation required")
        if len({k for k, _ in self.required_project_settings}) != len(
            self.required_project_settings
        ):
            raise ValueError("Duplicate setting expectation")
        if self.coordinate_evidence_ref is not None:
            text(self.coordinate_evidence_ref)
        if self.item_marker_host_id is not None:
            text(self.item_marker_host_id)
        if type(self.include_optional_audio) is not bool:
            raise TypeError("Explicit audio variant required")


@dataclass(frozen=True)
class FixtureRoleBinding:
    role: str
    matches: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.role)
        for match in self.matches:
            text(match)
        object.__setattr__(self, "matches", tuple(sorted(self.matches)))

    @property
    def status(self) -> RoleStatus:
        return (
            RoleStatus.UNRESOLVED
            if not self.matches
            else RoleStatus.UNIQUE
            if len(self.matches) == 1
            else RoleStatus.AMBIGUOUS
        )


@dataclass(frozen=True)
class FixtureAssessment:
    status: FixtureResult
    roles: tuple[FixtureRoleBinding, ...]
    findings: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, FixtureResult):
            raise TypeError("Typed fixture result required")
        object.__setattr__(self, "roles", tuple(self.roles))
        object.__setattr__(self, "findings", tuple(self.findings))
        for finding in self.findings:
            text(finding)
        if any(not isinstance(r, FixtureRoleBinding) for r in self.roles):
            raise TypeError("Typed role binding required")


ASSET_HASHES = {
    "ASSET_ALPHA": "67910939447e396ef0ce17d79d4303d223f20ca61b81337b034dfa8121d4d323",
    "ASSET_BETA": "fdbf8c87dfd1c1dcdf6e702e3da99565eef9e7c64a2cfeded60b5100843de13a",
    "ASSET_GAMMA": "ec0fea668d05116d6429fcf8c982bd07aad3f64164cbcabffa5c8e59258a1f93",
    "ASSET_REPEAT": "2b76b4102e1b8de3f838b1fb19a0d9dd4181be85e1ec9af7c2624f950c00488f",
    "ASSET_VIDEO_ONLY": "51109edb40573bcf98c1373dae2e049c81da99db44186841779075624d650137",
    "ASSET_AUDIO_ONLY": "f82f9cdeb70e7ef34f7bfb07158708549593e56bb73a1add6a5d5155c1692e9b",
}


def placement_roles(fixture: FixtureInput) -> tuple[PlacementRole, ...]:
    context = fixture.context
    rows: tuple[tuple[str, str, int, int, int, int], ...]
    if context == Context.F0:
        rows = (
            ("F0_A", "ALPHA", 100, 200, 24, 124),
            ("F0_B", "BETA", 240, 340, 48, 148),
            ("F0_C", "GAMMA", 400, 500, 72, 172),
        )
    elif context == Context.F1:
        rows = (
            ("F1_R1", "REPEAT", 100, 200, 120, 220),
            ("F1_R2", "REPEAT", 260, 360, 120, 220),
            ("F1_R3", "REPEAT", 420, 520, 240, 340),
        )
    elif context == Context.F3:
        rows = (("F3_HOST", "ALPHA", 100, 340, 0, 240),)
    elif context in (Context.F4_A, Context.F4_B):
        role = "F4_ITEM_A" if context == Context.F4_A else "F4_ITEM_B"
        rows = ((role, "REPEAT", 100, 200, 120, 220),)
    else:
        return tuple(
            PlacementRole(role, kind, index, "ASSET_" + asset, FrameRange(a, b), FrameRange(c, d))
            for role, kind, index, asset, a, b, c, d in (
                ("F2_V1", "video", 1, "VIDEO_ONLY", 100, 180, 40, 120),
                ("F2_V2", "video", 2, "VIDEO_ONLY", 220, 300, 160, 240),
                ("F2_A1", "audio", 1, "AUDIO_ONLY", 100, 180, 40, 120),
                ("F2_A2", "audio", 2, "AUDIO_ONLY", 220, 300, 160, 240),
            )
        )
    kinds = (
        ("video", "audio")
        if fixture.include_optional_audio or context == Context.F0
        else ("video",)
    )
    return tuple(
        PlacementRole(
            role + "/" + kind, kind, 1, "ASSET_" + asset, FrameRange(a, b), FrameRange(c, d)
        )
        for role, asset, a, b, c, d in rows
        for kind in kinds
    )


def scalar(snapshot: ProbeSnapshot, subject: str, case: str) -> object:
    value = snapshot.field(subject, case)
    return value.scalar if value is not None else None


def map_get(value: NativeValue | None, key: str) -> NativeValue | None:
    if value is None or value.type_name != "builtins.dict":
        return None
    return next((v for k, v in value.entries if k == freeze(key)), None)


def assess_fixture(snapshot: ProbeSnapshot, fixture: FixtureInput) -> FixtureAssessment:
    if snapshot.context != fixture.context or snapshot.timeline_id != fixture.timeline_id:
        return FixtureAssessment(FixtureResult.STALE, (), ("CONTEXT_MISMATCH",))
    if any(s.startswith("STALE") for s in snapshot.findings):
        return FixtureAssessment(FixtureResult.STALE, (), snapshot.findings)
    missing: list[str] = ["UNVERIFIED_REQUIRED_RISK:" + k.value for k in fixture.required_risks]
    wrong: list[str] = []
    if not snapshot.complete:
        missing.append("INCOMPLETE_CAPTURE")
    if not fixture.coordinate_evidence_ref:
        missing.append("NATIVE_COORDINATE_CONVENTION_UNPROVEN")
    if not fixture.required_project_settings:
        missing.append("REQUIRED_PROJECT_SETTINGS_UNDECLARED")
    for key, expected in fixture.required_project_settings:
        actual = map_get(snapshot.field("project", "RV-008"), key)
        if actual is None:
            missing.append("MISSING_PROJECT_SETTING:" + key)
        elif actual != expected:
            wrong.append("PROJECT_SETTING_MISMATCH:" + key)
    t0 = scalar(snapshot, "timeline", "RV-012")
    if type(t0) is not int:
        return FixtureAssessment(FixtureResult.INCOMPLETE, (), ("UNKNOWN_TIMELINE_START",))

    # Compare catalog offsets against native values; never alter the captured coordinates.
    def expect(subject: str, case: str, expected: object) -> None:
        actual = snapshot.field(subject, case)
        if actual is None:
            missing.append("MISSING:" + subject + ":" + case)
        elif actual != semantic(freeze(expected)):
            wrong.append("MISMATCH:" + subject + ":" + case)

    expect("timeline", "RV-013", t0 + max(r.timeline_offset.end for r in placement_roles(fixture)))
    expect("timeline", "RV-014", "01:00:00:00")
    rate = map_get(snapshot.field("timeline", "RV-015"), "timelineFrameRate")
    if rate is None:
        missing.append("MISSING_TIMELINE_RATE")
    elif rate != freeze("24"):
        wrong.append("TIMELINE_RATE_MISMATCH")
    counts = (
        (2, 2, 0)
        if fixture.context == Context.F2
        else (1, 1, 1 if fixture.context == Context.F3 else 0)
    )
    for kind, count in zip(("video", "audio", "subtitle"), counts, strict=True):
        expect("tracks/" + kind, "RV-016", count)
        for index in range(1, count + 1):
            enabled = not (fixture.context == Context.F2 and index == 2)
            locked = fixture.context == Context.F2 and kind == "audio"
            expect(f"track/{kind}/{index}", "RV-019", enabled)
            expect(f"track/{kind}/{index}", "RV-020", locked)
    subjects = sorted(
        {
            r.subject
            for r in snapshot.reads
            if r.case_id == "RV-022" and r.subject.startswith("item/")
        }
    )
    assets = {a.asset_role: a for a in fixture.assets}
    roles: list[FixtureRoleBinding] = []
    for role in placement_roles(fixture):
        asset = assets.get(role.asset_role)
        if asset is None:
            missing.append("MISSING_ASSET_PROVENANCE:" + role.asset_role)
            roles.append(FixtureRoleBinding(role.role, ()))
            continue
        if ASSET_HASHES.get(asset.asset_role) != asset.asset_sha256:
            wrong.append("WRONG_ASSET_HASH:" + role.asset_role)
        matches = tuple(
            s
            for s in subjects
            if snapshot.field(s, "RV-029") == freeze([role.track_type, role.track_index])
            and scalar(snapshot, s, "RV-031") == asset.media_unique_id
            and scalar(snapshot, s, "RV-024") == t0 + role.timeline_offset.start
            and scalar(snapshot, s, "RV-025") == t0 + role.timeline_offset.end
            and scalar(snapshot, s, "RV-026") == role.timeline_offset.duration
            and scalar(snapshot, s, "RV-027") == role.source_range.start
            and scalar(snapshot, s, "RV-028") == role.source_range.end
        )
        binding = FixtureRoleBinding(role.role, matches)
        roles.append(binding)
        if binding.status != RoleStatus.UNIQUE:
            # Known missing/wrong placements vs unreadable geometry remain distinct.
            if all(
                snapshot.field(s, case) is not None
                for s in subjects
                for case in ("RV-024", "RV-025", "RV-026", "RV-029")
            ):
                wrong.append("ROLE_" + binding.status.value + ":" + role.role)
            else:
                missing.append("ROLE_UNKNOWN:" + role.role)
    used = [s for role in roles for s in role.matches]
    if len(used) != len(set(used)):
        wrong.append("ROLE_NOT_ONE_TO_ONE")
    subtitles = [s for s in subjects if snapshot.field(s, "RV-029") == freeze(["subtitle", 1])]
    if fixture.context == Context.F3:
        expected_subtitles = ((160, 220, "PROBE ALPHA 01"), (260, 320, "PROBE BETA 02"))
        for a, b, label in expected_subtitles:
            found = [
                s
                for s in subtitles
                if scalar(snapshot, s, "RV-024") == t0 + a
                and scalar(snapshot, s, "RV-025") == t0 + b
                and scalar(snapshot, s, "RV-026") == b - a
                and scalar(snapshot, s, "RV-040") == label
            ]
            if len(found) != 1:
                wrong.append("SUBTITLE_MISMATCH:" + label)
        if len(subtitles) != 2:
            wrong.append("SUBTITLE_INVENTORY_MISMATCH")
        expect(
            "timeline",
            "RV-036",
            {
                120: {
                    "duration": 12,
                    "color": "Blue",
                    "name": "TL_MARK_A",
                    "note": "probe timeline marker",
                    "customData": "probe:tl:a",
                }
            },
        )
        # The catalog does not identify which A/V member owns the item marker.
        # Require an explicit external binding instead of choosing video or audio.
        host = "item/" + fixture.item_marker_host_id if fixture.item_marker_host_id else None
        if host is None:
            missing.append("ITEM_MARKER_HOST_BINDING_REQUIRED")
        elif host not in used:
            wrong.append("ITEM_MARKER_HOST_MISMATCH")
        else:
            expect(
                host,
                "RV-037",
                {
                    40: {
                        "duration": 8,
                        "color": "Green",
                        "name": "ITEM_MARK_A",
                        "note": "probe item marker",
                        "customData": "probe:item:a",
                    }
                },
            )
        for other in subjects:
            if host is not None and other != host:
                expect(other, "RV-037", {})
    else:
        expect("timeline", "RV-036", {})
        for subject in subjects:
            expect(subject, "RV-037", {})
    for subject in used:
        expect(subject, "RV-035", True)
        links = snapshot.field(subject, "RV-034")
        if links is not None and any(
            child.type_name != "builtins.str" or "item/" + str(child.scalar) not in subjects
            for child in links.children
        ):
            wrong.append("UNDECLARED_LINK_TARGET:" + subject)
    if fixture.context == Context.F0:
        by_role = {r.role: r for r in roles}
        for label in ("F0_A", "F0_B", "F0_C"):
            video = by_role[label + "/video"]
            audio = by_role[label + "/audio"]
            if video.status == audio.status == RoleStatus.UNIQUE:
                expect(video.matches[0], "RV-034", [audio.matches[0].removeprefix("item/")])
                expect(audio.matches[0], "RV-034", [video.matches[0].removeprefix("item/")])
    if set(subjects) != set(used) | set(subtitles):
        wrong.append("UNDECLARED_OR_UNRESOLVED_PLACEMENT")
    if snapshot.operator_interference:
        return FixtureAssessment(FixtureResult.ABORTED, tuple(roles), ("OPERATOR_INTERFERENCE",))
    if wrong:
        return FixtureAssessment(FixtureResult.MISMATCH, tuple(roles), tuple(wrong + missing))
    if missing:
        return FixtureAssessment(FixtureResult.INCOMPLETE, tuple(roles), tuple(missing))
    if not snapshot.consistent:
        return FixtureAssessment(FixtureResult.UNSTABLE, tuple(roles), ("CAPTURE_FENCE_DRIFT",))
    return FixtureAssessment(FixtureResult.MATCH, tuple(roles), ())
