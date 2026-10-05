"""Pure ADR-013 impact compiler. Outputs are evidence, NEVER executable edit commands."""

from collections import defaultdict, deque
from dataclasses import dataclass, replace
from enum import Enum

from .domain import (
    FrameRange,
    MediaId,
    Relationship,
    RelationshipGraph,
    RelationshipId,
    RelationshipMember,
    RelationshipPolicy,
    RelationshipRole,
    RelationshipType,
    TimelineId,
    TimelineObjectId,
    TimelineSnapshot,
    TimelineVersion,
)
from .topology import StateOrigin, TimelineTopologySnapshot


class EditActionType(str, Enum):
    MOVE = "MOVE"
    RIPPLE = "RIPPLE"
    TRIM = "TRIM"
    DELETE = "DELETE"
    SPLIT = "SPLIT"
    RETIME = "RETIME"


class CompilationStatus(str, Enum):
    SAFE_TO_CONTINUE = "SAFE_TO_CONTINUE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"


class DependencyReason(str, Enum):
    INVALID_BASE = "INVALID_BASE"
    INVALID_TARGET = "INVALID_TARGET"
    ROLE_SEMANTICS_UNRESOLVED = "ROLE_SEMANTICS_UNRESOLVED"
    SYNC_SEMANTICS_UNRESOLVED = "SYNC_SEMANTICS_UNRESOLVED"
    ANCHOR_SEMANTICS_UNRESOLVED = "ANCHOR_SEMANTICS_UNRESOLVED"
    SUBTITLE_RECALCULATION_REQUIRED = "SUBTITLE_RECALCULATION_REQUIRED"
    AMBIGUOUS_FRAGMENT = "AMBIGUOUS_FRAGMENT"
    FRAGMENT_REBINDING_REQUIRED = "FRAGMENT_REBINDING_REQUIRED"
    MOVE_SEMANTICS_UNRESOLVED = "MOVE_SEMANTICS_UNRESOLVED"
    RIPPLE_SEMANTICS_UNRESOLVED = "RIPPLE_SEMANTICS_UNRESOLVED"
    TRIM_SEMANTICS_UNRESOLVED = "TRIM_SEMANTICS_UNRESOLVED"
    DELETE_SEMANTICS_UNRESOLVED = "DELETE_SEMANTICS_UNRESOLVED"
    SPLIT_SEMANTICS_UNRESOLVED = "SPLIT_SEMANTICS_UNRESOLVED"
    RETIME_SEMANTICS_UNRESOLVED = "RETIME_SEMANTICS_UNRESOLVED"
    CONFLICT = "CONFLICT"
    CYCLE = "CYCLE"


@dataclass(frozen=True)
class PrimaryEditIntent:
    timeline_id: TimelineId
    base_version: TimelineVersion
    object_id: TimelineObjectId
    action: EditActionType
    timeline_range: FrameRange

    def __post_init__(self) -> None:
        if not isinstance(self.action, EditActionType):
            raise TypeError("Primary action requires EditActionType")
        if not isinstance(self.object_id, TimelineObjectId):
            raise TypeError("Primary intent requires fake object identity")
        if not isinstance(self.timeline_range, FrameRange):
            raise TypeError("Primary intent requires a half-open frame range")


@dataclass(frozen=True)
class ConcreteFragment:
    object_id: TimelineObjectId
    media_id: MediaId
    timeline_range: FrameRange
    source_range: FrameRange


@dataclass(frozen=True)
class ReviewReason:
    code: DependencyReason
    object_id: TimelineObjectId | None = None
    relationship_id: RelationshipId | None = None


@dataclass(frozen=True)
class DependencyAction:
    """An impact candidate. trigger_action is NOT an action to apply to object_id."""

    object_id: TimelineObjectId
    trigger_action: EditActionType
    disposition: RelationshipPolicy
    original_policy: RelationshipPolicy
    relationship_id: RelationshipId
    reason: DependencyReason
    fragments: tuple[ConcreteFragment, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fragments", tuple(self.fragments))


@dataclass(frozen=True)
class Conflict:
    object_id: TimelineObjectId
    requirements: tuple[tuple[RelationshipId, RelationshipPolicy], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "requirements", tuple(tuple(r) for r in self.requirements))


@dataclass(frozen=True)
class Cycle:
    object_ids: tuple[TimelineObjectId, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "object_ids", tuple(self.object_ids))


@dataclass(frozen=True)
class CompiledDependencyPlan:
    primary: PrimaryEditIntent
    status: CompilationStatus
    closure: tuple[TimelineObjectId, ...] = ()
    actions: tuple[DependencyAction, ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    cycles: tuple[Cycle, ...] = ()
    review_reasons: tuple[ReviewReason, ...] = ()

    def __post_init__(self) -> None:
        for field in ("closure", "actions", "conflicts", "cycles", "review_reasons"):
            object.__setattr__(self, field, tuple(getattr(self, field)))


def _key(obj: TimelineObjectId) -> tuple[str, str]:
    return obj.track_id, obj.clip_id


def _canonical_graph(graph: RelationshipGraph | None) -> RelationshipGraph | None:
    if graph is None:
        return None
    return RelationshipGraph(
        tuple(sorted(graph.object_ids, key=_key)),
        tuple(
            replace(r, members=tuple(sorted(r.members, key=lambda m: _key(m.object_id))))
            for r in sorted(graph.relationships, key=lambda r: r.relationship_id)
        ),
    )


def _canonical_topology(topology: TimelineTopologySnapshot) -> TimelineTopologySnapshot:
    return replace(
        topology,
        objects=tuple(sorted(topology.objects, key=lambda m: _key(m.object_id))),
        relationship_graph=_canonical_graph(topology.relationship_graph),
    )


def _closure(
    graph: RelationshipGraph, root: TimelineObjectId
) -> tuple[tuple[TimelineObjectId, ...], tuple[Relationship, ...]]:
    # Incidence closure is conservative context assessment, not execution propagation.
    index: dict[TimelineObjectId, list[Relationship]] = defaultdict(list)
    for rel in graph.relationships:
        for member in rel.members:
            index[member.object_id].append(rel)
    visited = {root}
    reached: dict[RelationshipId, Relationship] = {}
    queue = deque([root])
    while queue:
        for rel in index[queue.popleft()]:
            if rel.relationship_id in reached:
                continue
            reached[rel.relationship_id] = rel
            for member in rel.members:
                if member.object_id not in visited:
                    visited.add(member.object_id)
                    queue.append(member.object_id)
    return (tuple(sorted(visited, key=_key)), tuple(reached[rid] for rid in sorted(reached)))


def _cycles(
    objects: tuple[TimelineObjectId, ...], relations: tuple[Relationship, ...]
) -> tuple[Cycle, ...]:
    # Iterative Kosaraju: exact SCCs, no recursion limit or side effects on timeline.
    edges: dict[TimelineObjectId, set[TimelineObjectId]] = {o: set() for o in objects}
    reverse: dict[TimelineObjectId, set[TimelineObjectId]] = {o: set() for o in objects}
    for rel in relations:
        drivers = [m.object_id for m in rel.members if m.role == RelationshipRole.DRIVER]
        dependents = [m.object_id for m in rel.members if m.role == RelationshipRole.DEPENDENT]
        for driver in drivers:
            for dependent in dependents:
                edges[driver].add(dependent)
                reverse[dependent].add(driver)
    seen: set[TimelineObjectId] = set()
    finished: list[TimelineObjectId] = []
    for root in objects:
        stack = [(root, False)]
        while stack:
            node, exiting = stack.pop()
            if exiting:
                finished.append(node)
            elif node not in seen:
                seen.add(node)
                stack.append((node, True))
                stack.extend(
                    (n, False) for n in sorted(edges[node], key=_key, reverse=True) if n not in seen
                )
    seen.clear()
    result = []
    for root in reversed(finished):
        if root in seen:
            continue
        component = set()
        pending = [root]
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            component.add(node)
            pending.extend(reverse[node] - seen)
        if len(component) > 1:
            result.append(Cycle(tuple(sorted(component, key=_key))))
    return tuple(sorted(result, key=lambda c: tuple(_key(o) for o in c.object_ids)))


_ACTION_REASON = {
    EditActionType.MOVE: DependencyReason.MOVE_SEMANTICS_UNRESOLVED,
    EditActionType.RIPPLE: DependencyReason.RIPPLE_SEMANTICS_UNRESOLVED,
    EditActionType.TRIM: DependencyReason.TRIM_SEMANTICS_UNRESOLVED,
    EditActionType.DELETE: DependencyReason.DELETE_SEMANTICS_UNRESOLVED,
    EditActionType.SPLIT: DependencyReason.SPLIT_SEMANTICS_UNRESOLVED,
    EditActionType.RETIME: DependencyReason.RETIME_SEMANTICS_UNRESOLVED,
}


def _response(
    rel: Relationship, member: RelationshipMember, action: EditActionType
) -> tuple[RelationshipPolicy, DependencyReason]:
    # Explicit per-action restrictions, never a universal FOLLOW executor.
    review = RelationshipPolicy.REVIEW
    if action in (EditActionType.SPLIT, EditActionType.RETIME):
        return review, _ACTION_REASON[action]
    if rel.relationship_type in (RelationshipType.AV_LINK, RelationshipType.SYNC_GROUP):
        return review, DependencyReason.SYNC_SEMANTICS_UNRESOLVED
    if any(m.role is None for m in rel.members):
        return review, DependencyReason.ROLE_SEMANTICS_UNRESOLVED
    if (
        action in (EditActionType.DELETE, EditActionType.TRIM)
        and rel.relationship_type == RelationshipType.SUBTITLE_FOLLOWS_DIALOGUE
        and member.role == RelationshipRole.DEPENDENT
        and any(m.role == RelationshipRole.DRIVER for m in rel.members)
    ):
        return RelationshipPolicy.RECALCULATE, DependencyReason.SUBTITLE_RECALCULATION_REQUIRED
    disposition = (
        member.policy
        if member.policy in (RelationshipPolicy.STAY, RelationshipPolicy.RECALCULATE)
        else review
    )
    reason = (
        DependencyReason.ANCHOR_SEMANTICS_UNRESOLVED
        if rel.relationship_type == RelationshipType.ANCHOR
        else _ACTION_REASON[action]
    )
    return disposition, reason


def compile_dependencies(
    snapshot: TimelineSnapshot, topology: TimelineTopologySnapshot, intent: PrimaryEditIntent
) -> CompiledDependencyPlan:
    """Compile immutable diagnostic evidence; SAFE_TO_CONTINUE is not edit authorization."""
    reasons: set[ReviewReason] = set()
    unsupported = intent.action == EditActionType.RETIME
    if unsupported:
        reasons.add(ReviewReason(DependencyReason.RETIME_SEMANTICS_UNRESOLVED))

    def result(
        closure: tuple[TimelineObjectId, ...] = (),
        actions: tuple[DependencyAction, ...] = (),
        conflicts: tuple[Conflict, ...] = (),
        cycles: tuple[Cycle, ...] = (),
    ) -> CompiledDependencyPlan:
        status = (
            CompilationStatus.UNSUPPORTED
            if unsupported
            else CompilationStatus.REVIEW_REQUIRED
            if reasons
            else CompilationStatus.SAFE_TO_CONTINUE
        )
        return CompiledDependencyPlan(
            intent,
            status,
            closure,
            actions,
            conflicts,
            cycles,
            tuple(
                sorted(
                    reasons,
                    key=lambda r: (
                        r.code.value,
                        _key(r.object_id) if r.object_id else ("", ""),
                        r.relationship_id or "",
                    ),
                )
            ),
        )

    if (
        intent.timeline_id != snapshot.timeline_id
        or intent.base_version != snapshot.version
        or topology.origin != StateOrigin.NATIVE_EDITABLE
        or _canonical_topology(topology)
        != _canonical_topology(TimelineTopologySnapshot.from_snapshot(snapshot))
    ):
        reasons.add(ReviewReason(DependencyReason.INVALID_BASE))
        return result()
    fragments: dict[TimelineObjectId, list[ConcreteFragment]] = defaultdict(list)
    for track in snapshot.tracks:
        for clip in track.clips:
            obj = TimelineObjectId(track.track_id, clip.clip_id)
            fragments[obj].append(
                ConcreteFragment(obj, clip.media_id, clip.timeline_range, clip.source_range)
            )
    primary = [
        f
        for f in fragments.get(intent.object_id, ())
        if f.timeline_range.contains(intent.timeline_range)
    ]
    if len(primary) != 1:
        reasons.add(ReviewReason(DependencyReason.INVALID_TARGET, intent.object_id))
        return result()
    graph = snapshot.relationship_graph
    assert graph is not None  # Snapshot construction always binds its graph.
    closure, relations = _closure(graph, intent.object_id)
    if intent.action == EditActionType.SPLIT:
        reasons.add(ReviewReason(DependencyReason.FRAGMENT_REBINDING_REQUIRED, intent.object_id))
        reasons.add(ReviewReason(_ACTION_REASON[intent.action]))
    actions = []
    requirements: dict[TimelineObjectId, list[tuple[RelationshipId, RelationshipPolicy]]]
    requirements = defaultdict(list)
    for rel in relations:
        reasons.add(
            ReviewReason(_ACTION_REASON[intent.action], relationship_id=rel.relationship_id)
        )
        if any(m.role is None for m in rel.members):
            reasons.add(
                ReviewReason(
                    DependencyReason.ROLE_SEMANTICS_UNRESOLVED, relationship_id=rel.relationship_id
                )
            )
        for member in sorted(rel.members, key=lambda m: _key(m.object_id)):
            # Include primary requirements in conflict evidence, never in dependent actions.
            requirements[member.object_id].append((rel.relationship_id, member.policy))
            if member.object_id == intent.object_id:
                continue
            disposition, reason = _response(rel, member, intent.action)
            bound = tuple(fragments[member.object_id])
            reasons.add(ReviewReason(reason, member.object_id, rel.relationship_id))
            if len(bound) != 1:
                disposition = RelationshipPolicy.REVIEW
                reason = DependencyReason.AMBIGUOUS_FRAGMENT
                reasons.add(ReviewReason(reason, member.object_id, rel.relationship_id))
            actions.append(
                DependencyAction(
                    member.object_id,
                    intent.action,
                    disposition,
                    member.policy,
                    rel.relationship_id,
                    reason,
                    bound,
                )
            )
    conflicts = tuple(
        Conflict(obj, tuple(sorted(req)))
        for obj, req in sorted(requirements.items(), key=lambda pair: _key(pair[0]))
        if len({policy for _, policy in req}) > 1
    )
    for conflict in conflicts:
        reasons.add(ReviewReason(DependencyReason.CONFLICT, conflict.object_id))
    cycles = _cycles(closure, relations)
    for cycle in cycles:
        for obj in cycle.object_ids:
            reasons.add(ReviewReason(DependencyReason.CYCLE, obj))
    return result(closure, tuple(actions), conflicts, cycles)
