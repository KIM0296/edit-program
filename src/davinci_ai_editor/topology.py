"""Pure fake topology projection and INV-019 validation, never an edit executor.

Comparison identity and current track membership are separate. Explicit origin
bindings handle TASK-003's track-qualified IDs without guessing persistent identity.
Provenance is declared fake data, not evidence of native Resolve editability.
"""

from dataclasses import dataclass, field, fields, replace
from enum import Enum

from .domain import (
    RelationshipGraph,
    TimelineId,
    TimelineObjectId,
    TimelineSnapshot,
    TimelineVersion,
    TrackId,
    TrackType,
)


class StateOrigin(str, Enum):
    NATIVE_EDITABLE = "NATIVE_EDITABLE"
    PREVIEW = "PREVIEW"
    RENDER = "RENDER"
    FLATTENED = "FLATTENED"


@dataclass(frozen=True)
class TrackTopology:
    track_id: TrackId
    track_type: TrackType
    order: int

    def __post_init__(self) -> None:
        if not isinstance(self.track_id, str) or not self.track_id.strip():
            raise ValueError("Track identity must be nonempty")
        if not isinstance(self.track_type, TrackType):
            raise TypeError("Unknown track type")
        if type(self.order) is not int or self.order < 0:
            raise ValueError("Track order must be a nonnegative integer")


@dataclass(frozen=True)
class ObjectMembership:
    """object_id is an original comparison identity, track_id is current membership."""

    object_id: TimelineObjectId
    track_id: TrackId

    def __post_init__(self) -> None:
        if not isinstance(self.object_id, TimelineObjectId):
            raise TypeError("Membership requires an object identity")
        if not isinstance(self.track_id, str) or not self.track_id.strip():
            raise ValueError("Membership track must be nonempty")


@dataclass(frozen=True)
class ObjectIdentityBinding:
    current_id: TimelineObjectId
    original_id: TimelineObjectId


@dataclass(frozen=True)
class TimelineTopologySnapshot:
    timeline_id: TimelineId
    version: TimelineVersion
    tracks: tuple[TrackTopology, ...]
    objects: tuple[ObjectMembership, ...]
    relationship_graph: RelationshipGraph | None = None
    origin: StateOrigin = StateOrigin.NATIVE_EDITABLE

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracks", tuple(self.tracks))
        object.__setattr__(self, "objects", tuple(self.objects))
        if not isinstance(self.origin, StateOrigin):
            raise TypeError("Unknown state origin")
        track_ids = {track.track_id for track in self.tracks}
        if len(track_ids) != len(self.tracks):
            raise ValueError("Duplicate track identity")
        if tuple(t.order for t in self.tracks) != tuple(range(len(self.tracks))):
            raise ValueError("Track order must match contiguous snapshot tuple indices")
        ids = tuple(item.object_id for item in self.objects)
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate comparison object identity")
        if any(item.track_id not in track_ids for item in self.objects):
            raise ValueError("Object membership references an unknown track")
        if self.relationship_graph is None:
            object.__setattr__(self, "relationship_graph", RelationshipGraph(ids))
        elif set(self.relationship_graph.object_ids) != set(ids):
            raise ValueError("Relationship registry does not match topology objects")

    @classmethod
    def from_snapshot(
        cls,
        snapshot: TimelineSnapshot,
        *,
        identity_bindings: tuple[ObjectIdentityBinding, ...] = (),
        origin: StateOrigin = StateOrigin.NATIVE_EDITABLE,
    ) -> "TimelineTopologySnapshot":
        """Project without mutation. A binding is explicit caller evidence, not inference.

        No binding means current composite IDs stay distinct, even for identical media.
        Native status is a fake declaration; a production adapter must verify it (OPEN-007).
        """
        actual_ids = snapshot.object_ids
        supplied = {b.current_id: b.original_id for b in identity_bindings}
        if len(supplied) != len(identity_bindings) or not set(supplied).issubset(actual_ids):
            raise ValueError("Invalid or duplicate current object identity binding")
        mapping = {oid: supplied.get(oid, oid) for oid in actual_ids}
        if len(set(mapping.values())) != len(actual_ids):
            raise ValueError("Object identity binding must be one-to-one")
        objects = tuple(ObjectMembership(mapping[oid], oid.track_id) for oid in actual_ids)
        source_graph = snapshot.relationship_graph
        assert source_graph is not None  # TimelineSnapshot always installs a validated graph.
        graph = RelationshipGraph(
            tuple(mapping[oid] for oid in source_graph.object_ids),
            tuple(
                replace(
                    rel,
                    members=tuple(
                        replace(member, object_id=mapping[member.object_id])
                        for member in rel.members
                    ),
                )
                for rel in source_graph.relationships
            ),
        )
        return cls(
            snapshot.timeline_id,
            snapshot.version,
            tuple(
                TrackTopology(track.track_id, track.track_type, index)
                for index, track in enumerate(snapshot.tracks)
            ),
            objects,
            graph,
            origin,
        )


@dataclass(frozen=True)
class TrackTypeChange:
    track_id: TrackId
    before: TrackType
    after: TrackType


@dataclass(frozen=True)
class TrackOrderChange:
    track_id: TrackId
    before: int
    after: int


@dataclass(frozen=True)
class ObjectTrackMove:
    object_id: TimelineObjectId
    before: TrackId
    after: TrackId


@dataclass(frozen=True)
class TopologyDiff:
    added_tracks: tuple[TrackTopology, ...] = ()
    removed_tracks: tuple[TrackTopology, ...] = ()
    track_type_changes: tuple[TrackTypeChange, ...] = ()
    track_order_changes: tuple[TrackOrderChange, ...] = ()
    added_objects: tuple[ObjectMembership, ...] = ()
    removed_objects: tuple[ObjectMembership, ...] = ()
    object_moves: tuple[ObjectTrackMove, ...] = ()

    def __post_init__(self) -> None:
        # Canonical tuples make expected/actual comparison independent of input list order.
        for descriptor in fields(self):
            entries = tuple(getattr(self, descriptor.name))
            if len(set(entries)) != len(entries):
                raise ValueError("Duplicate topology diff entry")
            object.__setattr__(self, descriptor.name, tuple(sorted(entries, key=repr)))


@dataclass(frozen=True)
class ExpectedTopologyChange:
    timeline_id: TimelineId
    base_version: TimelineVersion
    changes: TopologyDiff = field(default_factory=TopologyDiff)


def diff_topology(
    before: TimelineTopologySnapshot, after: TimelineTopologySnapshot
) -> TopologyDiff:
    """Describe identity/type/order/membership differences; no inference or execution."""
    if before.timeline_id != after.timeline_id:
        raise ValueError("Cannot compare different timeline identities")
    old_tracks = {t.track_id: t for t in before.tracks}
    new_tracks = {t.track_id: t for t in after.tracks}
    common_tracks = old_tracks.keys() & new_tracks.keys()
    old_objects = {o.object_id: o for o in before.objects}
    new_objects = {o.object_id: o for o in after.objects}
    return TopologyDiff(
        added_tracks=tuple(new_tracks[k] for k in new_tracks.keys() - old_tracks.keys()),
        removed_tracks=tuple(old_tracks[k] for k in old_tracks.keys() - new_tracks.keys()),
        track_type_changes=tuple(
            TrackTypeChange(k, old_tracks[k].track_type, new_tracks[k].track_type)
            for k in common_tracks
            if old_tracks[k].track_type != new_tracks[k].track_type
        ),
        track_order_changes=tuple(
            TrackOrderChange(k, old_tracks[k].order, new_tracks[k].order)
            for k in common_tracks
            if old_tracks[k].order != new_tracks[k].order
        ),
        added_objects=tuple(new_objects[k] for k in new_objects.keys() - old_objects.keys()),
        removed_objects=tuple(old_objects[k] for k in old_objects.keys() - new_objects.keys()),
        object_moves=tuple(
            ObjectTrackMove(k, old_objects[k].track_id, new_objects[k].track_id)
            for k in old_objects.keys() & new_objects.keys()
            if old_objects[k].track_id != new_objects[k].track_id
        ),
    )


def validate_topology(
    before: TimelineTopologySnapshot,
    after: TimelineTopologySnapshot,
    expected: ExpectedTopologyChange,
) -> TopologyDiff:
    """Enforce exact expectations and scoped preserve-editability checks (INV-019).

    Expected changes do not authorize rendered replacements or relation propagation.
    Success certifies only supplied topology/provenance, not full native editability.
    """
    if (
        before.origin is not StateOrigin.NATIVE_EDITABLE
        or after.origin is not StateOrigin.NATIVE_EDITABLE
    ):
        raise ValueError(
            "Preserve editable state: preview/render/flattened artifacts cannot replace it"
        )
    if expected.timeline_id != before.timeline_id or expected.base_version != before.version:
        raise ValueError("Expected topology change does not match the base timeline/version")
    actual = diff_topology(before, after)
    old_ids = {item.object_id for item in before.objects}
    new_ids = {item.object_id for item in after.objects}
    if (
        len({item.track_id for item in before.objects}) > 1
        and len(after.objects) == 1
        and not old_ids.intersection(new_ids)
    ):
        raise ValueError("REVIEW: possible flatten of editable layers into one replacement")
    assert before.relationship_graph is not None and after.relationship_graph is not None
    if before.relationship_graph.relationships != after.relationship_graph.relationships:
        raise ValueError("REVIEW: relationship changes require separate lifecycle semantics")
    if actual != expected.changes:
        raise ValueError("INV-019: unexpected or missing expected topology change")
    return actual
