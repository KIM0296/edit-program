from dataclasses import FrozenInstanceError, replace

import pytest

from davinci_ai_editor.domain import (
    Clip,
    ClipId,
    EditCommand,
    EditPlan,
    FrameRange,
    MediaId,
    Relationship,
    RelationshipGraph,
    RelationshipId,
    RelationshipMember,
    RelationshipPolicy,
    RelationshipType,
    TimelineId,
    TimelineObjectId,
    TimelineSnapshot,
    TimelineVersion,
    Track,
    TrackId,
    TrackType,
)
from davinci_ai_editor.fake_timeline import FakeTimeline
from davinci_ai_editor.safety import propose_ripple_displacements

V1 = TrackId("V1")
A1 = TrackId("A1")
VIDEO = TimelineObjectId(V1, ClipId("video"))
AUDIO = TimelineObjectId(A1, ClipId("audio"))


def clip(name, start, end, source=100):
    return Clip(
        ClipId(name),
        MediaId("shared-media"),
        FrameRange(start, end),
        FrameRange(source, source + end - start),
    )


def relation(kind=RelationshipType.AV_LINK, ids=(VIDEO, AUDIO), name="r1"):
    return Relationship(RelationshipId(name), kind, tuple(RelationshipMember(i) for i in ids))


def av_snapshot(audio_start=10, audio_end=70):
    return TimelineSnapshot(
        TimelineId("main"),
        TimelineVersion(1),
        (
            Track(V1, (clip("video", 20, 80),), TrackType.VIDEO),
            Track(A1, (clip("audio", audio_start, audio_end, 500),), TrackType.AUDIO),
        ),
    )


@pytest.mark.parametrize("kind", list(RelationshipType))
def test_all_relation_types_bind_to_existing_objects(kind):
    snap = av_snapshot()
    graph = RelationshipGraph(snap.object_ids, (relation(kind),))
    linked = replace(snap, relationship_graph=graph)
    assert linked.relationship_graph == graph
    assert graph.related_to(VIDEO) == (relation(kind),)
    assert graph.related_to(AUDIO) == (relation(kind),)
    assert linked.tracks == snap.tracks
    assert linked.version == snap.version


@pytest.mark.parametrize("start,end", [(10, 70), (30, 90), (10, 90)])
def test_j_l_cut_independent_ranges_are_preserved(start, end):
    snap = av_snapshot(start, end)
    linked = replace(snap, relationship_graph=RelationshipGraph(snap.object_ids, (relation(),)))
    assert linked.tracks[0].clips[0].timeline_range == FrameRange(20, 80)
    assert linked.tracks[1].clips[0].timeline_range == FrameRange(start, end)
    assert linked.tracks == snap.tracks
    assert linked.duration == max(80, end)


@pytest.mark.parametrize("policy", list(RelationshipPolicy))
def test_member_policy_is_data_and_does_not_align_or_move(policy):
    snap = av_snapshot()
    rel = Relationship(
        RelationshipId("r"),
        RelationshipType.ANCHOR,
        (
            RelationshipMember(VIDEO, RelationshipPolicy.STAY),
            RelationshipMember(AUDIO, policy),
        ),
    )
    linked = replace(snap, relationship_graph=RelationshipGraph(snap.object_ids, (rel,)))
    assert linked.tracks == snap.tracks
    assert rel.members[0].policy is RelationshipPolicy.STAY
    assert rel.members[1].policy is policy
    assert RelationshipMember(VIDEO).policy is RelationshipPolicy.REVIEW


def test_nary_sync_group_and_same_media_placements_are_distinct():
    other = TimelineObjectId(V1, ClipId("video-repeat"))
    snap = TimelineSnapshot(
        TimelineId("main"),
        TimelineVersion(1),
        (
            Track(V1, (clip("video", 0, 30), clip("video-repeat", 30, 60)), TrackType.VIDEO),
            Track(A1, (clip("audio", 0, 30),), TrackType.AUDIO),
        ),
    )
    pair = relation(ids=(VIDEO, AUDIO))
    graph = RelationshipGraph(snap.object_ids, (pair,))
    assert graph.related_to(other) == ()
    group = relation(RelationshipType.SYNC_GROUP, (VIDEO, AUDIO, other), "sync")
    extended = graph.with_relationship(group)
    assert extended.related_to(other) == (group,)
    assert graph.related_to(other) == ()
    assert len(extended.relationships) == 2
    assert replace(snap, relationship_graph=extended).tracks == snap.tracks


def test_same_clip_id_on_distinct_tracks_is_not_same_object():
    snap = TimelineSnapshot(
        TimelineId("main"),
        TimelineVersion(1),
        (
            Track(V1, (clip("placement", 0, 30),)),
            Track(A1, (clip("placement", 0, 30),)),
        ),
    )
    assert len(set(snap.object_ids)) == 2


def test_dangling_graph_members_and_additions_are_rejected():
    missing = TimelineObjectId(A1, ClipId("missing"))
    invalid = relation(ids=(VIDEO, missing))
    graph = RelationshipGraph((VIDEO, AUDIO))
    with pytest.raises(ValueError, match="unknown object"):
        RelationshipGraph((VIDEO, AUDIO), (invalid,))
    with pytest.raises(ValueError, match="unknown object"):
        graph.with_relationship(invalid)
    assert graph.relationships == ()


def test_phantom_or_incomplete_registry_cannot_enter_snapshot():
    snap = av_snapshot()
    phantom = TimelineObjectId(V1, ClipId("phantom"))
    for graph in (
        RelationshipGraph((VIDEO,)),
        RelationshipGraph((VIDEO, AUDIO, phantom), (relation(ids=(VIDEO, phantom)),)),
    ):
        with pytest.raises(ValueError, match="registry"):
            replace(snap, relationship_graph=graph)


def test_duplicate_ids_and_duplicate_members_are_rejected():
    with pytest.raises(ValueError, match="object ID"):
        RelationshipGraph((VIDEO, VIDEO))
    with pytest.raises(ValueError, match="relationship ID"):
        RelationshipGraph((VIDEO, AUDIO), (relation(), relation()))
    with pytest.raises(ValueError, match="distinct"):
        relation(ids=(VIDEO, VIDEO))
    with pytest.raises(ValueError, match="two"):
        relation(ids=(VIDEO,))
    with pytest.raises(ValueError, match="track ID"):
        replace(av_snapshot(), tracks=(av_snapshot().tracks[0], av_snapshot().tracks[0]))


def test_references_revalidated_when_snapshot_objects_are_removed():
    snap = av_snapshot()
    linked = replace(snap, relationship_graph=RelationshipGraph(snap.object_ids, (relation(),)))
    with pytest.raises(ValueError, match="registry"):
        replace(linked, tracks=linked.tracks[:1])
    assert linked.tracks == snap.tracks


def test_deep_immutability_and_defensive_tuple_copies():
    ids = [VIDEO, AUDIO]
    members = [RelationshipMember(VIDEO), RelationshipMember(AUDIO)]
    rel = Relationship(RelationshipId("r"), RelationshipType.AV_LINK, members)
    relations = [rel]
    graph = RelationshipGraph(ids, relations)
    snap = replace(av_snapshot(), relationship_graph=graph)
    ids.clear()
    members.clear()
    relations.clear()
    assert graph.object_ids == (VIDEO, AUDIO)
    assert graph.relationships == (rel,)
    assert len(rel.members) == 2
    for obj, attr, value in (
        (graph, "relationships", ()),
        (rel, "members", ()),
        (rel.members[0], "policy", RelationshipPolicy.FOLLOW),
        (VIDEO, "clip_id", ClipId("changed")),
        (snap, "relationship_graph", None),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, attr, value)


def test_empty_graph_and_track_type_default():
    snap = TimelineSnapshot(TimelineId("empty"), TimelineVersion(1), ())
    assert snap.relationship_graph == RelationshipGraph()
    assert Track(V1).track_type is TrackType.UNKNOWN
    for kind in TrackType:
        assert Track(V1, track_type=kind).track_type is kind


def test_invalid_enum_values_and_blank_identity_rejected():
    with pytest.raises(TypeError):
        Track(V1, track_type="VIDEO")
    with pytest.raises(TypeError):
        RelationshipMember(VIDEO, "FOLLOW")
    with pytest.raises(TypeError):
        Relationship(RelationshipId("r"), "AV_LINK", relation().members)
    with pytest.raises(ValueError):
        relation(name="")
    with pytest.raises(ValueError):
        TimelineObjectId(V1, ClipId(""))


def test_legal_split_lineage_has_one_id_but_ambiguous_lineage_rejects():
    pieces = (clip("video", 0, 10, 100), clip("video", 10, 20, 120))
    snap = TimelineSnapshot(TimelineId("main"), TimelineVersion(1), (Track(V1, pieces),))
    assert snap.object_ids == (VIDEO,)
    for bad in (
        replace(pieces[1], source_range=FrameRange(100, 110)),
        replace(pieces[1], media_id=MediaId("different")),
    ):
        with pytest.raises(ValueError, match="lineage"):
            replace(snap, tracks=(Track(V1, (pieces[0], bad)),))


@pytest.mark.parametrize("policy", list(RelationshipPolicy))
def test_relation_bearing_plan_rejects_before_mutation(monkeypatch, policy):
    first = TimelineObjectId(V1, ClipId("first"))
    second = TimelineObjectId(V1, ClipId("second"))
    track = Track(V1, (clip("first", 0, 30), clip("second", 30, 60)))
    rel = Relationship(
        RelationshipId("r"),
        RelationshipType.ANCHOR,
        (
            RelationshipMember(first, policy),
            RelationshipMember(second),
        ),
    )
    fake = FakeTimeline(
        TimelineId("main"), track, relationship_graph=RelationshipGraph((first, second), (rel,))
    )
    before = fake.snapshot()
    commands = (EditCommand(before.resolve(V1, FrameRange(0, 10))),)
    plan = EditPlan(
        before.timeline_id, before.version, commands, propose_ripple_displacements(before, commands)
    )
    monkeypatch.setattr(
        FakeTimeline,
        "_delete",
        staticmethod(lambda *args: pytest.fail("relationship policies must not execute")),
    )
    with pytest.raises(ValueError, match="REVIEW"):
        fake.apply(plan)
    assert fake.snapshot() == before
    assert fake.apply(EditPlan(before.timeline_id, before.version, ())) == ()
    assert fake.snapshot() == before


def test_relation_free_delete_rebuilds_registry_without_mutating_old_snapshot():
    fake = FakeTimeline(TimelineId("main"), Track(V1, (clip("video", 0, 30),)))
    before = fake.snapshot()
    target = before.resolve(V1, FrameRange(0, 30))
    fake.apply(EditPlan(before.timeline_id, before.version, (EditCommand(target),)))
    assert before.object_ids == (VIDEO,)
    assert fake.snapshot().object_ids == ()
    assert fake.snapshot().relationship_graph == RelationshipGraph()
