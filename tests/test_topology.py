from dataclasses import FrozenInstanceError, replace

import pytest

from davinci_ai_editor.domain import (
    Clip,
    ClipId,
    FrameRange,
    MediaId,
    Relationship,
    RelationshipGraph,
    RelationshipId,
    RelationshipMember,
    RelationshipType,
    TimelineId,
    TimelineObjectId,
    TimelineSnapshot,
    TimelineVersion,
    Track,
    TrackId,
    TrackType,
)
from davinci_ai_editor.topology import (
    ExpectedTopologyChange,
    ObjectIdentityBinding,
    ObjectMembership,
    ObjectTrackMove,
    StateOrigin,
    TimelineTopologySnapshot,
    TopologyDiff,
    TrackOrderChange,
    TrackTopology,
    TrackTypeChange,
    diff_topology,
    validate_topology,
)

V1, V2, A1, S1 = map(TrackId, ("V1", "V2", "A1", "S1"))
ONE = TimelineObjectId(V1, ClipId("repeat"))
TWO = TimelineObjectId(V2, ClipId("repeat"))
AUDIO = TimelineObjectId(A1, ClipId("audio"))
SUB = TimelineObjectId(S1, ClipId("sub"))


def clip(name, start=0):
    return Clip(
        ClipId(name), MediaId("same-media"), FrameRange(start, start + 10), FrameRange(100, 110)
    )


def snapshot(linked=False):
    snap = TimelineSnapshot(
        TimelineId("main"),
        TimelineVersion(7),
        (
            Track(V1, (clip("repeat"),), TrackType.VIDEO),
            Track(V2, (clip("repeat"),), TrackType.VIDEO),
            Track(A1, (clip("audio"),), TrackType.AUDIO),
            Track(S1, (clip("sub"),), TrackType.SUBTITLE),
        ),
    )
    if linked:
        rel = Relationship(
            RelationshipId("av"),
            RelationshipType.AV_LINK,
            (RelationshipMember(ONE), RelationshipMember(AUDIO)),
        )
        snap = replace(snap, relationship_graph=RelationshipGraph(snap.object_ids, (rel,)))
    return snap


def topology():
    return TimelineTopologySnapshot.from_snapshot(snapshot())


def expected(base, changes=None):
    return ExpectedTopologyChange(
        base.timeline_id, base.version, changes if changes is not None else TopologyDiff()
    )


def test_multi_layer_projection_preserves_identity_type_order_membership_and_graph():
    snap = snapshot(linked=True)
    base = TimelineTopologySnapshot.from_snapshot(snap)
    assert base.tracks == (
        TrackTopology(V1, TrackType.VIDEO, 0),
        TrackTopology(V2, TrackType.VIDEO, 1),
        TrackTopology(A1, TrackType.AUDIO, 2),
        TrackTopology(S1, TrackType.SUBTITLE, 3),
    )
    assert base.objects == (
        ObjectMembership(ONE, V1),
        ObjectMembership(TWO, V2),
        ObjectMembership(AUDIO, A1),
        ObjectMembership(SUB, S1),
    )
    assert base.relationship_graph == snap.relationship_graph
    assert validate_topology(base, base, expected(base)) == TopologyDiff()
    assert snap == snapshot(linked=True)
    assert len({item.object_id for item in base.objects}) == 4


def test_track_addition_requires_exact_expected_order_displacements():
    base = topology()
    added = TrackTopology(TrackId("V3"), TrackType.VIDEO, 1)
    tracks = (base.tracks[0], added) + tuple(replace(t, order=t.order + 1) for t in base.tracks[1:])
    after = replace(base, tracks=tracks)
    wanted = TopologyDiff(
        added_tracks=(added,),
        track_order_changes=(
            TrackOrderChange(V2, 1, 2),
            TrackOrderChange(A1, 2, 3),
            TrackOrderChange(S1, 3, 4),
        ),
    )
    assert diff_topology(base, after) == wanted
    with pytest.raises(ValueError, match="unexpected"):
        validate_topology(base, after, expected(base))
    with pytest.raises(ValueError, match="unexpected"):
        validate_topology(base, after, expected(base, TopologyDiff(added_tracks=(added,))))
    assert validate_topology(base, after, expected(base, wanted)) == wanted


def test_existing_track_removal_and_object_removal_are_detected():
    base = topology()
    after = replace(
        base, tracks=base.tracks[:-1], objects=base.objects[:-1], relationship_graph=None
    )
    wanted = TopologyDiff(removed_tracks=(base.tracks[-1],), removed_objects=(base.objects[-1],))
    assert diff_topology(base, after) == wanted
    with pytest.raises(ValueError, match="unexpected"):
        validate_topology(base, after, expected(base))
    assert validate_topology(base, after, expected(base, wanted)) == wanted


def test_track_type_change_is_not_silent():
    base = topology()
    after = replace(
        base, tracks=(replace(base.tracks[0], track_type=TrackType.AUDIO),) + base.tracks[1:]
    )
    change = TopologyDiff(
        track_type_changes=(TrackTypeChange(V1, TrackType.VIDEO, TrackType.AUDIO),)
    )
    assert diff_topology(base, after) == change
    with pytest.raises(ValueError, match="unexpected"):
        validate_topology(base, after, expected(base))
    assert validate_topology(base, after, expected(base, change)) == change


def test_track_reorder_keeps_identity_but_needs_explicit_approval():
    base = topology()
    after = replace(
        base,
        tracks=(replace(base.tracks[1], order=0), replace(base.tracks[0], order=1))
        + base.tracks[2:],
    )
    change = TopologyDiff(
        track_order_changes=(TrackOrderChange(V1, 0, 1), TrackOrderChange(V2, 1, 0))
    )
    assert diff_topology(base, after) == change
    assert {t.track_id for t in after.tracks} == {t.track_id for t in base.tracks}
    with pytest.raises(ValueError, match="unexpected"):
        validate_topology(base, after, expected(base))
    validate_topology(base, after, expected(base, change))


def test_object_move_uses_identity_not_same_media_or_track_index():
    base = topology()
    after = replace(base, objects=(ObjectMembership(ONE, A1),) + base.objects[1:])
    change = TopologyDiff(object_moves=(ObjectTrackMove(ONE, V1, A1),))
    assert diff_topology(base, after) == change
    assert after.objects[1] == base.objects[1]
    with pytest.raises(ValueError, match="unexpected"):
        validate_topology(base, after, expected(base))
    assert validate_topology(base, after, expected(base, change)) == change


def test_explicit_cross_track_binding_preserves_relationship_references_without_execution():
    before_snap = snapshot(linked=True)
    moved = TimelineObjectId(A1, ClipId("moved-repeat"))
    tracks = (
        replace(before_snap.tracks[0], clips=()),
        before_snap.tracks[1],
        replace(before_snap.tracks[2], clips=(clip("audio"), clip("moved-repeat", 10))),
        before_snap.tracks[3],
    )
    unlinked = TimelineSnapshot(before_snap.timeline_id, before_snap.version, tracks)
    rel = Relationship(
        RelationshipId("av"),
        RelationshipType.AV_LINK,
        (RelationshipMember(moved), RelationshipMember(AUDIO)),
    )
    after_snap = replace(
        unlinked, relationship_graph=RelationshipGraph(unlinked.object_ids, (rel,))
    )
    before = TimelineTopologySnapshot.from_snapshot(before_snap)
    unmapped = TimelineTopologySnapshot.from_snapshot(after_snap)
    assert diff_topology(before, unmapped).object_moves == ()
    assert diff_topology(before, unmapped).removed_objects == (ObjectMembership(ONE, V1),)
    after = TimelineTopologySnapshot.from_snapshot(
        after_snap, identity_bindings=(ObjectIdentityBinding(moved, ONE),)
    )
    # Registry iteration order follows the projected snapshot; object identity and
    # relationship records, rather than registry enumeration order, must be preserved.
    assert set(after.relationship_graph.object_ids) == set(before.relationship_graph.object_ids)
    assert after.relationship_graph.relationships == before.relationship_graph.relationships
    change = TopologyDiff(object_moves=(ObjectTrackMove(ONE, V1, A1),))
    validate_topology(before, after, expected(before, change))
    assert before_snap == snapshot(linked=True)
    assert after_snap.relationship_graph == RelationshipGraph(unlinked.object_ids, (rel,))


@pytest.mark.parametrize("bad", ["unknown", "duplicate-current", "collision"])
def test_bad_bindings_reject_instead_of_guessing(bad):
    bindings = {
        "unknown": (ObjectIdentityBinding(TimelineObjectId(V1, ClipId("missing")), ONE),),
        "duplicate-current": (ObjectIdentityBinding(ONE, ONE), ObjectIdentityBinding(ONE, TWO)),
        "collision": (ObjectIdentityBinding(ONE, TWO),),
    }[bad]
    with pytest.raises(ValueError, match="binding"):
        TimelineTopologySnapshot.from_snapshot(snapshot(), identity_bindings=bindings)


@pytest.mark.parametrize("origin", [StateOrigin.PREVIEW, StateOrigin.RENDER, StateOrigin.FLATTENED])
def test_output_artifact_cannot_replace_editable_state_even_with_same_topology(origin):
    base = topology()
    artifact = replace(base, origin=origin)
    assert diff_topology(base, artifact) == TopologyDiff()
    with pytest.raises(ValueError, match="editable"):
        validate_topology(base, artifact, expected(base))
    with pytest.raises(ValueError, match="editable"):
        validate_topology(artifact, base, expected(artifact))


@pytest.mark.parametrize(
    "origin", [StateOrigin.RENDER, StateOrigin.FLATTENED, StateOrigin.NATIVE_EDITABLE]
)
def test_many_layers_to_single_replacement_rejects_even_if_fully_expected(origin):
    base = topology()
    replacement = TimelineObjectId(V1, ClipId("rendered-composite"))
    after = replace(
        base,
        tracks=base.tracks[:1],
        objects=(ObjectMembership(replacement, V1),),
        relationship_graph=None,
        origin=origin,
    )
    changes = diff_topology(base, after)
    with pytest.raises(ValueError, match="editable|flatten"):
        validate_topology(base, after, expected(base, changes))


def test_approved_layer_deletion_retains_individual_native_object():
    base = topology()
    after = replace(base, tracks=base.tracks[:1], objects=base.objects[:1], relationship_graph=None)
    wanted = TopologyDiff(removed_tracks=base.tracks[1:], removed_objects=base.objects[1:])
    assert validate_topology(base, after, expected(base, wanted)) == wanted


def test_expected_change_is_not_an_extra_change_whitelist():
    base = topology()
    move = ObjectTrackMove(ONE, V1, V2)
    with pytest.raises(ValueError, match="unexpected"):
        validate_topology(base, base, expected(base, TopologyDiff(object_moves=(move,))))
    after = replace(
        base, objects=(ObjectMembership(ONE, V2), ObjectMembership(TWO, A1)) + base.objects[2:]
    )
    with pytest.raises(ValueError, match="unexpected"):
        validate_topology(base, after, expected(base, TopologyDiff(object_moves=(move,))))


def test_new_object_membership_is_detected():
    base = topology()
    new = ObjectMembership(TimelineObjectId(V1, ClipId("new")), V1)
    after = replace(base, objects=base.objects + (new,), relationship_graph=None)
    change = TopologyDiff(added_objects=(new,))
    assert diff_topology(base, after) == change
    with pytest.raises(ValueError, match="unexpected"):
        validate_topology(base, after, expected(base))
    validate_topology(base, after, expected(base, change))


@pytest.mark.parametrize("bad", ["expected-version", "expected-timeline", "result-timeline"])
def test_wrong_comparison_context_rejects(bad):
    base = topology()
    after = base
    approval = expected(base)
    if bad == "expected-version":
        approval = replace(approval, base_version=TimelineVersion(999))
    elif bad == "expected-timeline":
        approval = replace(approval, timeline_id=TimelineId("other"))
    else:
        after = replace(base, timeline_id=TimelineId("other"))
    with pytest.raises(ValueError):
        validate_topology(base, after, approval)


def test_topology_rejects_dangling_membership_duplicate_identity_and_wrong_registry():
    base = topology()
    for objects in (
        (replace(base.objects[0], track_id=TrackId("absent")),) + base.objects[1:],
        base.objects + (base.objects[0],),
    ):
        with pytest.raises(ValueError):
            replace(base, objects=objects)
    with pytest.raises(ValueError, match="registry"):
        replace(base, relationship_graph=RelationshipGraph())
    with pytest.raises(ValueError):
        replace(base, tracks=base.tracks + (replace(base.tracks[0], order=4),))
    with pytest.raises(ValueError):
        replace(base, tracks=(replace(base.tracks[0], order=1),) + base.tracks[1:])


def test_relationship_changes_are_not_implicitly_approved_by_topology():
    snap = snapshot(linked=True)
    base = TimelineTopologySnapshot.from_snapshot(snap)
    after = replace(base, relationship_graph=RelationshipGraph(snap.object_ids))
    assert diff_topology(base, after) == TopologyDiff()
    with pytest.raises(ValueError, match="relationship"):
        validate_topology(base, after, expected(base))


def test_topology_and_expected_diff_are_deeply_immutable():
    base = topology()
    tracks, objects = list(base.tracks), list(base.objects)
    copied = replace(base, tracks=tracks, objects=objects)
    moves = [ObjectTrackMove(ONE, V1, V2)]
    delta = TopologyDiff(object_moves=moves)
    approval = expected(base, delta)
    tracks.clear()
    objects.clear()
    moves.clear()
    assert copied == base
    assert len(approval.changes.object_moves) == 1
    for obj, field, value in (
        (copied, "tracks", ()),
        (copied.objects[0], "track_id", A1),
        (copied.tracks[0], "order", 4),
        (approval, "changes", TopologyDiff()),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, field, value)


def test_comparison_is_pure_and_does_not_increment_version():
    base = topology()
    after = replace(base, objects=(ObjectMembership(ONE, V2),) + base.objects[1:])
    change = TopologyDiff(object_moves=(ObjectTrackMove(ONE, V1, V2),))
    validate_topology(base, after, expected(base, change))
    assert base == topology()
    assert base.version == after.version == TimelineVersion(7)


@pytest.mark.parametrize("order", [-1, True, 1.5])
def test_track_index_must_be_nonnegative_integer(order):
    with pytest.raises(ValueError):
        TrackTopology(V1, TrackType.VIDEO, order)


def test_diff_rejects_duplicate_entries():
    move = ObjectTrackMove(ONE, V1, V2)
    with pytest.raises(ValueError):
        TopologyDiff(object_moves=(move, move))


def test_empty_topology_is_valid_and_track_identity_change_is_not_reorder():
    empty = TimelineSnapshot(TimelineId("empty"), TimelineVersion(1), ())
    projected = TimelineTopologySnapshot.from_snapshot(empty)
    assert validate_topology(projected, projected, expected(projected)) == TopologyDiff()
    base = topology()
    new_id = TrackId("renamed-identity")
    after = replace(
        base,
        tracks=(replace(base.tracks[0], track_id=new_id),) + base.tracks[1:],
        objects=(ObjectMembership(ONE, new_id),) + base.objects[1:],
    )
    changes = diff_topology(base, after)
    assert changes.removed_tracks == (base.tracks[0],)
    assert changes.added_tracks == (TrackTopology(new_id, TrackType.VIDEO, 0),)
    assert changes.track_order_changes == ()
    assert changes.object_moves == (ObjectTrackMove(ONE, V1, new_id),)
    with pytest.raises(ValueError, match="unexpected"):
        validate_topology(base, after, expected(base))
