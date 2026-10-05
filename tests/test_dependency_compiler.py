from dataclasses import FrozenInstanceError, replace
from itertools import permutations

import pytest

from davinci_ai_editor.dependency import (
    CompilationStatus as Status,
)
from davinci_ai_editor.dependency import (
    DependencyReason as Reason,
)
from davinci_ai_editor.dependency import (
    EditActionType as Action,
)
from davinci_ai_editor.dependency import (
    PrimaryEditIntent,
    compile_dependencies,
)
from davinci_ai_editor.domain import (
    Clip,
    ClipId,
    FrameRange,
    MediaId,
    Relationship,
    RelationshipGraph,
    RelationshipId,
    RelationshipMember,
    TimelineId,
    TimelineObjectId,
    TimelineSnapshot,
    TimelineVersion,
    Track,
    TrackId,
    TrackType,
)
from davinci_ai_editor.domain import (
    RelationshipPolicy as Policy,
)
from davinci_ai_editor.domain import (
    RelationshipRole as Role,
)
from davinci_ai_editor.domain import (
    RelationshipType as Kind,
)
from davinci_ai_editor.topology import StateOrigin, TimelineTopologySnapshot


def oid(name):
    return TimelineObjectId(TrackId(name), ClipId("placement"))


A, B, C, X, UNRELATED = map(oid, ("A", "B", "C", "X", "unrelated"))


def relation(name, driver=A, dependent=B, policy=Policy.FOLLOW, kind=Kind.ANCHOR):
    return Relationship(
        RelationshipId(name),
        kind,
        (
            RelationshipMember(driver, Policy.REVIEW, Role.DRIVER),
            RelationshipMember(dependent, policy, Role.DEPENDENT),
        ),
    )


def snapshot(relations=(), objects=(A, B, C, X, UNRELATED)):
    # Same media and placement name on different tracks must never alias.
    tracks = tuple(
        Track(
            obj.track_id,
            (
                Clip(
                    obj.clip_id,
                    MediaId("shared"),
                    FrameRange(i * 2, 30 + i * 2),
                    FrameRange(100, 130),
                ),
            ),
            TrackType.AUDIO if obj == B else TrackType.VIDEO,
        )
        for i, obj in enumerate(objects)
    )
    return TimelineSnapshot(
        TimelineId("base"),
        TimelineVersion(8),
        tracks,
        relationship_graph=RelationshipGraph(objects, relations),
    )


def intent(snap, action=Action.DELETE, target=A, interval=None):
    return PrimaryEditIntent(
        snap.timeline_id, snap.version, target, action, interval or FrameRange(10, 15)
    )


def compile(snap, action=Action.DELETE, target=A):
    return compile_dependencies(
        snap, TimelineTopologySnapshot.from_snapshot(snap), intent(snap, action, target)
    )


def reasons(plan):
    return {r.code for r in plan.review_reasons}


def test_av_partial_delete_and_j_l_cut_are_review_only():
    snap = snapshot((relation("av", kind=Kind.AV_LINK),))
    before = repr(snap)
    plan = compile(snap)
    assert plan.status == Status.REVIEW_REQUIRED
    assert Reason.SYNC_SEMANTICS_UNRESOLVED in reasons(plan)
    assert len(plan.actions) == 1
    assert plan.actions[0].object_id == B
    assert plan.actions[0].disposition == Policy.REVIEW
    assert plan.actions[0].fragments[0].timeline_range == FrameRange(2, 32)
    assert repr(snap) == before
    assert not hasattr(plan.actions[0], "command")
    assert not hasattr(plan.actions[0], "new_range")


@pytest.mark.parametrize("action", [Action.DELETE, Action.TRIM])
def test_subtitle_response_is_recalculate_never_delete(action):
    snap = snapshot((relation("sub", kind=Kind.SUBTITLE_FOLLOWS_DIALOGUE),))
    plan = compile(snap, action)
    assert plan.status == Status.REVIEW_REQUIRED
    assert plan.actions[0].disposition == Policy.RECALCULATE
    assert plan.actions[0].reason == Reason.SUBTITLE_RECALCULATION_REQUIRED
    assert plan.actions[0].trigger_action == action


def test_anchor_delete_never_cascades():
    plan = compile(snapshot((relation("anchor"),)))
    assert plan.status == Status.REVIEW_REQUIRED
    assert plan.actions[0].disposition == Policy.REVIEW
    assert Reason.ANCHOR_SEMANTICS_UNRESOLVED in reasons(plan)


def test_conflict_keeps_both_requirements_without_priority():
    plan = compile(snapshot((relation("follow"), relation("stay", policy=Policy.STAY))))
    assert plan.status == Status.REVIEW_REQUIRED
    assert len(plan.conflicts) == 1
    assert plan.conflicts[0].object_id == B
    assert set(plan.conflicts[0].requirements) == {
        (RelationshipId("follow"), Policy.FOLLOW),
        (RelationshipId("stay"), Policy.STAY),
    }
    assert len(plan.actions) == 2
    assert Reason.CONFLICT in reasons(plan)


def test_equal_policies_are_not_a_conflict():
    plan = compile(snapshot((relation("one"), relation("two"))))
    assert not plan.conflicts
    assert len(plan.actions) == 2


def test_cycle_is_finite_and_identifies_only_scc_not_downstream_tail():
    snap = snapshot(
        (relation("ab"), relation("bc", B, C), relation("ca", C, A), relation("cx", C, X))
    )
    plan = compile(snap)
    assert plan.status == Status.REVIEW_REQUIRED
    assert len(plan.cycles) == 1
    assert plan.cycles[0].object_ids == (A, B, C)
    assert len(plan.actions) == 6
    assert Reason.CYCLE in reasons(plan)


def test_diamond_has_no_directed_cycle():
    plan = compile(
        snapshot((relation("ab"), relation("ac", A, C), relation("bx", B, X), relation("cx", C, X)))
    )
    assert not plan.cycles
    assert set(plan.closure) == {A, B, C, X}


def test_disconnected_cycle_and_shared_media_do_not_enter_plan():
    snap = snapshot((relation("ab"), relation("cx", C, X), relation("xc", X, C)))
    plan = compile(snap)
    assert plan.closure == (A, B)
    assert {a.object_id for a in plan.actions} == {B}
    assert not plan.cycles


def test_peer_context_is_not_an_artificial_directed_cycle():
    rel = Relationship(
        RelationshipId("peers"),
        Kind.AV_LINK,
        (RelationshipMember(A, role=Role.PEER), RelationshipMember(B, role=Role.PEER)),
    )
    plan = compile(snapshot((rel,)))
    assert plan.status == Status.REVIEW_REQUIRED
    assert not plan.cycles


def test_unspecified_roles_fail_closed_and_tuple_order_cannot_assign_driver():
    rel = Relationship(
        RelationshipId("legacy"),
        Kind.SUBTITLE_FOLLOWS_DIALOGUE,
        (RelationshipMember(A), RelationshipMember(B)),
    )
    plan = compile(snapshot((rel,)))
    assert Reason.ROLE_SEMANTICS_UNRESOLVED in reasons(plan)
    assert plan.actions[0].disposition == Policy.REVIEW


@pytest.mark.parametrize("action", list(Action))
def test_each_primary_action_has_distinct_review_dispatch(action):
    plan = compile(snapshot((relation("anchor"),)), action)
    expected = Status.UNSUPPORTED if action == Action.RETIME else Status.REVIEW_REQUIRED
    assert plan.status == expected
    assert plan.actions[0].trigger_action == action
    assert getattr(Reason, action.value + "_SEMANTICS_UNRESOLVED") in reasons(plan)


@pytest.mark.parametrize("action", [Action.MOVE, Action.RIPPLE, Action.TRIM, Action.DELETE])
def test_dependency_free_safe_means_only_continue_planning(action):
    plan = compile(snapshot(), action)
    assert plan.status == Status.SAFE_TO_CONTINUE
    assert plan.closure == (A,)
    assert not plan.actions and not plan.review_reasons


def test_retime_without_relationships_still_unsupported():
    assert compile(snapshot(), Action.RETIME).status == Status.UNSUPPORTED


def test_split_never_clones_relationships():
    snap = snapshot((relation("ab"),))
    plan = compile(snap, Action.SPLIT)
    assert plan.status == Status.REVIEW_REQUIRED
    assert len(plan.actions) == 1
    assert Reason.FRAGMENT_REBINDING_REQUIRED in reasons(plan)
    assert len(snap.relationship_graph.relationships) == 1


def test_fragment_candidates_are_evidence_not_multiple_actions():
    snap = snapshot((relation("ab"),))
    original = snap.tracks[1]
    fragments = (
        Clip(B.clip_id, MediaId("shared"), FrameRange(2, 8), FrameRange(100, 106)),
        Clip(B.clip_id, MediaId("shared"), FrameRange(20, 26), FrameRange(120, 126)),
    )
    snap = replace(
        snap, tracks=(snap.tracks[0], replace(original, clips=fragments)) + snap.tracks[2:]
    )
    plan = compile(snap)
    assert len(plan.actions) == 1
    assert len(plan.actions[0].fragments) == 2
    assert Reason.AMBIGUOUS_FRAGMENT in reasons(plan)
    assert plan.actions[0].disposition == Policy.REVIEW


def test_primary_range_must_bind_one_concrete_fragment():
    snap = snapshot()
    parts = (
        Clip(A.clip_id, MediaId("shared"), FrameRange(0, 10), FrameRange(100, 110)),
        Clip(A.clip_id, MediaId("shared"), FrameRange(20, 30), FrameRange(120, 130)),
    )
    snap = replace(snap, tracks=(replace(snap.tracks[0], clips=parts),) + snap.tracks[1:])
    topo = TimelineTopologySnapshot.from_snapshot(snap)
    bad = compile_dependencies(snap, topo, intent(snap, interval=FrameRange(5, 25)))
    good = compile_dependencies(snap, topo, intent(snap, interval=FrameRange(2, 5)))
    assert bad.status == Status.REVIEW_REQUIRED and not bad.actions
    assert Reason.INVALID_TARGET in reasons(bad)
    assert good.status == Status.SAFE_TO_CONTINUE


@pytest.mark.parametrize(
    "field,value",
    [
        ("timeline_id", TimelineId("other")),
        ("base_version", TimelineVersion(999)),
        ("object_id", oid("missing")),
    ],
)
def test_stale_or_missing_target_never_compiles_actions(field, value):
    snap = snapshot((relation("ab"),))
    plan = compile_dependencies(
        snap, TimelineTopologySnapshot.from_snapshot(snap), replace(intent(snap), **{field: value})
    )
    assert plan.status == Status.REVIEW_REQUIRED and not plan.actions


@pytest.mark.parametrize("origin", [StateOrigin.PREVIEW, StateOrigin.RENDER, StateOrigin.FLATTENED])
def test_noneditable_topology_rejected(origin):
    snap = snapshot((relation("ab"),))
    topo = TimelineTopologySnapshot.from_snapshot(snap, origin=origin)
    plan = compile_dependencies(snap, topo, intent(snap))
    assert Reason.INVALID_BASE in reasons(plan)
    assert not plan.actions


def test_topology_graph_type_order_membership_and_version_must_match_base():
    snap = snapshot((relation("ab"),))
    topo = TimelineTopologySnapshot.from_snapshot(snap)
    variants = [
        replace(topo, version=TimelineVersion(9)),
        replace(topo, relationship_graph=RelationshipGraph(snap.object_ids)),
        replace(
            topo, tracks=(replace(topo.tracks[0], track_type=TrackType.SUBTITLE),) + topo.tracks[1:]
        ),
        replace(
            topo, tracks=tuple(replace(t, order=i) for i, t in enumerate(reversed(topo.tracks)))
        ),
        replace(topo, objects=(replace(topo.objects[0], track_id=B.track_id),) + topo.objects[1:]),
    ]
    for changed in variants:
        plan = compile_dependencies(snap, changed, intent(snap))
        assert Reason.INVALID_BASE in reasons(plan)
        assert not plan.actions


def test_canonical_results_ignore_members_relationships_registry_order():
    rels = (relation("ab"), relation("bc", B, C))
    base = snapshot(rels)
    expected = compile(base)
    for order in permutations(rels):
        changed = replace(
            base,
            relationship_graph=RelationshipGraph(
                tuple(reversed(base.object_ids)),
                tuple(replace(r, members=tuple(reversed(r.members))) for r in order),
            ),
        )
        assert compile(changed) == expected
        # Topology may independently serialize graph members in another order.
        assert (
            compile_dependencies(
                changed, TimelineTopologySnapshot.from_snapshot(base), intent(changed)
            )
            == expected
        )
    assert compile(base) == expected


def test_inputs_and_outputs_are_immutable_and_roles_validate():
    snap = snapshot((relation("ab"),))
    topo = TimelineTopologySnapshot.from_snapshot(snap)
    before = (repr(snap), repr(topo))
    plan = compile_dependencies(snap, topo, intent(snap))
    assert (repr(snap), repr(topo)) == before
    with pytest.raises(FrozenInstanceError):
        plan.status = Status.SAFE_TO_CONTINUE
    with pytest.raises(FrozenInstanceError):
        plan.actions[0].disposition = Policy.FOLLOW
    with pytest.raises(TypeError):
        RelationshipMember(A, role="DRIVER")
    with pytest.raises(TypeError):
        replace(intent(snap), action="DELETE")


def test_long_chain_uses_finite_nonrecursive_closure():
    ids = tuple(oid(f"n{i:04}") for i in range(1100))
    rels = tuple(relation(f"r{i:04}", ids[i], ids[i + 1]) for i in range(len(ids) - 1))
    plan = compile(snapshot(rels, ids), target=ids[0])
    assert len(plan.closure) == len(ids)
    assert not plan.cycles
    assert len(plan.actions) == 2 * len(rels) - 1


@pytest.mark.parametrize("kind", [Kind.AV_LINK, Kind.SYNC_GROUP])
@pytest.mark.parametrize("policy", [Policy.FOLLOW, Policy.STAY, Policy.RECALCULATE])
def test_sync_context_never_auto_resolves_even_with_explicit_policy(kind, policy):
    plan = compile(snapshot((relation("sync", kind=kind, policy=policy),)), Action.MOVE)
    assert plan.status == Status.REVIEW_REQUIRED
    assert plan.actions[0].disposition == Policy.REVIEW
    assert Reason.SYNC_SEMANTICS_UNRESOLVED in reasons(plan)


def test_upstream_context_is_assessed_without_claiming_reverse_execution():
    plan = compile(snapshot((relation("ab"), relation("bc", B, C))), target=C)
    assert plan.closure == (A, B, C)
    assert {a.object_id for a in plan.actions} == {A, B}
    assert plan.status == Status.REVIEW_REQUIRED
    assert all(a.disposition == Policy.REVIEW for a in plan.actions)


def test_multiple_independent_cycles_have_canonical_evidence():
    rels = (
        relation("ab"),
        relation("ba", B, A),
        relation("bc", B, C),
        relation("cx", C, X),
        relation("xc", X, C),
    )
    plan = compile(snapshot(rels))
    assert tuple(c.object_ids for c in plan.cycles) == ((A, B), (C, X))
    assert compile(snapshot(tuple(reversed(rels)))) == plan


def test_role_projection_preserves_roles_and_old_fake_execution_still_rejects_relations():
    from davinci_ai_editor.domain import EditCommand, EditPlan
    from davinci_ai_editor.safety import preflight

    snap = snapshot((relation("ab"),))
    assert (
        TimelineTopologySnapshot.from_snapshot(snap).relationship_graph == snap.relationship_graph
    )
    target = snap.resolve(A.track_id, FrameRange(10, 15))
    with pytest.raises(ValueError, match="relationship"):
        preflight(snap, EditPlan(snap.timeline_id, snap.version, (EditCommand(target),)))
