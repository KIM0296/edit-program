"""Immutable timeline domain values. Ranges are integer, half-open [start, end)."""

from dataclasses import dataclass, replace
from enum import Enum
from typing import Literal, NewType

TimelineId = NewType("TimelineId", str)
TimelineVersion = NewType("TimelineVersion", int)
TrackId = NewType("TrackId", str)
ClipId = NewType("ClipId", str)
MediaId = NewType("MediaId", str)
RelationshipId = NewType("RelationshipId", str)


class TrackType(str, Enum):
    UNKNOWN = "UNKNOWN"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    SUBTITLE = "SUBTITLE"
    OTHER = "OTHER"


class RelationshipType(str, Enum):
    AV_LINK = "AV_LINK"
    SYNC_GROUP = "SYNC_GROUP"
    SUBTITLE_FOLLOWS_DIALOGUE = "SUBTITLE_FOLLOWS_DIALOGUE"
    ANCHOR = "ANCHOR"


class RelationshipPolicy(str, Enum):
    """Per-member descriptive metadata; no movement or execution is implied."""

    FOLLOW = "FOLLOW"
    STAY = "STAY"
    RECALCULATE = "RECALCULATE"
    REVIEW = "REVIEW"


@dataclass(frozen=True)
class TimelineObjectId:
    """Snapshot-local fake placement lineage, NEVER a Resolve persistent ID.

    Fragments of a split placement share this ID. Distinct placements require
    distinct IDs even if their media/source ranges match. See ADR-012 / OPEN-001.
    """

    track_id: TrackId
    clip_id: ClipId

    def __post_init__(self) -> None:
        if not isinstance(self.track_id, str) or not self.track_id.strip():
            raise ValueError("Object track identity must be nonempty")
        if not isinstance(self.clip_id, str) or not self.clip_id.strip():
            raise ValueError("Object placement identity must be nonempty")


@dataclass(frozen=True)
class RelationshipMember:
    object_id: TimelineObjectId
    policy: RelationshipPolicy = RelationshipPolicy.REVIEW

    def __post_init__(self) -> None:
        if not isinstance(self.object_id, TimelineObjectId):
            raise TypeError("Relationship member requires a fake object identity")
        if not isinstance(self.policy, RelationshipPolicy):
            raise TypeError("Unknown relationship policy")


@dataclass(frozen=True)
class Relationship:
    """Unbound value descriptor. Graph/snapshot binding validates object existence.

    Member order does not imply direction, timing alignment or common displacement.
    Type-specific roles and execution semantics are deferred under OPEN-005.
    """

    relationship_id: RelationshipId
    relationship_type: RelationshipType
    members: tuple[RelationshipMember, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "members", tuple(self.members))
        if not isinstance(self.relationship_id, str) or not self.relationship_id.strip():
            raise ValueError("Relationship ID must be nonempty")
        if not isinstance(self.relationship_type, RelationshipType):
            raise TypeError("Unknown relationship type")
        if len(self.members) < 2:
            raise ValueError("Relationship requires at least two members")
        ids = [member.object_id for member in self.members]
        if len(set(ids)) != len(ids):
            raise ValueError("Relationship members must reference distinct objects")


@dataclass(frozen=True)
class RelationshipGraph:
    """Immutable bound relationships; registry is rechecked against snapshot objects."""

    object_ids: tuple[TimelineObjectId, ...] = ()
    relationships: tuple[Relationship, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "object_ids", tuple(self.object_ids))
        object.__setattr__(self, "relationships", tuple(self.relationships))
        known = set(self.object_ids)
        if len(known) != len(self.object_ids):
            raise ValueError("Duplicate object ID in relationship graph")
        ids = [rel.relationship_id for rel in self.relationships]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate relationship ID in graph")
        if any(
            member.object_id not in known for rel in self.relationships for member in rel.members
        ):
            raise ValueError("Relationship references an unknown object")

    def with_relationship(self, relationship: Relationship) -> "RelationshipGraph":
        """Bind a descriptor without changing this graph; dangling members reject."""
        return replace(self, relationships=self.relationships + (relationship,))

    def related_to(self, object_id: TimelineObjectId) -> tuple[Relationship, ...]:
        if object_id not in self.object_ids:
            raise ValueError("Cannot query an unknown object")
        return tuple(
            rel
            for rel in self.relationships
            if any(member.object_id == object_id for member in rel.members)
        )


@dataclass(frozen=True)
class FrameRange:
    start: int
    end: int

    def __post_init__(self) -> None:
        if type(self.start) is not int or type(self.end) is not int:
            raise ValueError("Frame boundaries must be integers")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("Expected nonempty, nonnegative [start, end)")

    @property
    def duration(self) -> int:
        return self.end - self.start

    def contains(self, other: "FrameRange") -> bool:
        return self.start <= other.start and other.end <= self.end

    def overlaps(self, other: "FrameRange") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class Clip:
    # Fake-only placement lineage. Split fragments keep this ID (ADR-012).
    clip_id: ClipId
    media_id: MediaId
    timeline_range: FrameRange
    source_range: FrameRange

    def __post_init__(self) -> None:
        if self.timeline_range.duration != self.source_range.duration:
            raise ValueError("Only 1:1 source mapping is supported by the fake")


@dataclass(frozen=True)
class Track:
    track_id: TrackId
    clips: tuple[Clip, ...] = ()
    track_type: TrackType = TrackType.UNKNOWN

    def __post_init__(self) -> None:
        object.__setattr__(self, "clips", tuple(self.clips))
        if not isinstance(self.track_type, TrackType):
            raise TypeError("Unknown track type")
        if any(
            a.timeline_range.end > b.timeline_range.start
            for a, b in zip(self.clips, self.clips[1:])
        ):
            raise ValueError("Clips must be ordered and nonoverlapping")


@dataclass(frozen=True)
class StableTarget:
    timeline_id: TimelineId
    timeline_version: TimelineVersion
    track_id: TrackId
    clip_id: ClipId
    media_id: MediaId
    timeline_range: FrameRange
    source_range: FrameRange
    coordinate_space: Literal["TIMELINE"] = "TIMELINE"


@dataclass(frozen=True)
class ProtectedRange:
    track_id: TrackId
    frame_range: FrameRange
    policy: str = "HARD_LOCK"

    def __post_init__(self) -> None:
        if self.policy != "HARD_LOCK":
            raise ValueError("Only HARD_LOCK protection is supported")


@dataclass(frozen=True)
class RippleDisplacement:
    """Explicit allowed movement of surviving content in base-snapshot coordinates."""

    track_id: TrackId
    original_range: FrameRange
    delta_frames: int

    def __post_init__(self) -> None:
        if type(self.delta_frames) is not int or self.delta_frames >= 0:
            raise ValueError("Ripple DELETE displacement must be a negative integer")


@dataclass(frozen=True)
class TimelineSnapshot:
    timeline_id: TimelineId
    version: TimelineVersion
    tracks: tuple[Track, ...]
    protected_ranges: tuple[ProtectedRange, ...] = ()
    relationship_graph: RelationshipGraph | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracks", tuple(self.tracks))
        object.__setattr__(self, "protected_ranges", tuple(self.protected_ranges))
        track_ids = {t.track_id for t in self.tracks}
        if len(track_ids) != len(self.tracks):
            raise ValueError("Duplicate track ID in snapshot")
        lineages: dict[TimelineObjectId, list[Clip]] = {}
        for track in self.tracks:
            for clip in track.clips:
                key = TimelineObjectId(track.track_id, clip.clip_id)
                previous = lineages.setdefault(key, [])
                if any(
                    clip.media_id != other.media_id
                    or clip.source_range.overlaps(other.source_range)
                    for other in previous
                ):
                    raise ValueError("Ambiguous fake placement lineage")
                previous.append(clip)
        if self.relationship_graph is None:
            object.__setattr__(self, "relationship_graph", RelationshipGraph(self.object_ids))
        elif set(self.relationship_graph.object_ids) != set(self.object_ids):
            raise ValueError("Relationship graph registry does not match snapshot objects")
        if any(p.track_id not in track_ids for p in self.protected_ranges):
            raise ValueError("Protected range must reference a known track")

    @property
    def object_ids(self) -> tuple[TimelineObjectId, ...]:
        return tuple(
            dict.fromkeys(
                TimelineObjectId(track.track_id, clip.clip_id)
                for track in self.tracks
                for clip in track.clips
            )
        )

    @property
    def duration(self) -> int:
        return max((c.timeline_range.end for t in self.tracks for c in t.clips), default=0)

    def resolve(self, track_id: TrackId, interval: FrameRange) -> StableTarget:
        matches = [
            c
            for t in self.tracks
            if t.track_id == track_id
            for c in t.clips
            if c.timeline_range.contains(interval)
        ]
        if len(matches) != 1:
            raise ValueError("Target must lie in exactly one clip fragment on the given track")
        clip = matches[0]
        start = clip.source_range.start + interval.start - clip.timeline_range.start
        return StableTarget(
            self.timeline_id,
            self.version,
            track_id,
            clip.clip_id,
            clip.media_id,
            interval,
            FrameRange(start, start + interval.duration),
        )


@dataclass(frozen=True)
class EditCommand:
    target: StableTarget
    action: str = "DELETE"
    ripple: bool = True


@dataclass(frozen=True)
class EditPlan:
    timeline_id: TimelineId
    base_version: TimelineVersion
    commands: tuple[EditCommand, ...]
    approved_ripple_displacements: tuple[RippleDisplacement, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "commands", tuple(self.commands))
        object.__setattr__(
            self, "approved_ripple_displacements", tuple(self.approved_ripple_displacements)
        )
