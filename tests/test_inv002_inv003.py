from dataclasses import replace

import pytest

from davinci_ai_editor.domain import (
    Clip,
    ClipId,
    EditCommand,
    EditPlan,
    FrameRange,
    MediaId,
    ProtectedRange,
    RippleDisplacement,
    TimelineId,
    Track,
    TrackId,
)
from davinci_ai_editor.fake_timeline import FakeTimeline
from davinci_ai_editor.safety import propose_ripple_displacements

V1 = TrackId("V1")


def timeline(protections=()):
    return FakeTimeline(
        TimelineId("main"),
        Track(
            V1,
            (
                Clip(ClipId("a"), MediaId("shared"), FrameRange(0, 40), FrameRange(100, 140)),
                Clip(ClipId("b"), MediaId("other"), FrameRange(50, 90), FrameRange(200, 240)),
                Clip(ClipId("c"), MediaId("shared"), FrameRange(90, 130), FrameRange(100, 140)),
            ),
        ),
        protected_ranges=protections,
    )


def plan_for(fake, intervals):
    snap = fake.snapshot()
    commands = tuple(EditCommand(snap.resolve(V1, r)) for r in intervals)
    # Explicit caller inclusion, never automatic approval by apply().
    return EditPlan(
        snap.timeline_id, snap.version, commands, propose_ripple_displacements(snap, commands)
    )


def frames(snapshot):
    return [
        (c.clip_id, c.media_id, c.source_range.start + offset, c.timeline_range.start + offset)
        for c in snapshot.tracks[0].clips
        for offset in range(c.source_range.duration)
    ]


@pytest.mark.parametrize("reverse", [False, True])
def test_inv002_exact_independent_frame_oracle(reverse):
    fake = timeline()
    before = fake.snapshot()
    intervals = [FrameRange(10, 20), FrameRange(60, 65), FrameRange(110, 120)]
    plan = plan_for(fake, tuple(reversed(intervals)) if reverse else intervals)
    fake.apply(plan)
    expected = []
    for clip, media, source, position in frames(before):
        if any(r.start <= position < r.end for r in intervals):
            continue
        delta = sum(r.duration for r in intervals if r.end <= position)
        expected.append((clip, media, source, position - delta))
    assert frames(fake.snapshot()) == expected
    assert fake.snapshot().duration == 105
    assert fake.snapshot().version == before.version + 1


def test_manifest_matches_hand_calculated_displacements():
    fake = timeline()
    plan = plan_for(fake, [FrameRange(10, 20), FrameRange(60, 65)])
    assert plan.approved_ripple_displacements == (
        RippleDisplacement(V1, FrameRange(20, 40), -10),
        RippleDisplacement(V1, FrameRange(50, 60), -10),
        RippleDisplacement(V1, FrameRange(65, 90), -15),
        RippleDisplacement(V1, FrameRange(90, 130), -15),
    )


@pytest.mark.parametrize("bad", ["missing", "delta", "extra", "range", "track", "duplicate"])
def test_bad_displacement_rejected_before_any_delete(monkeypatch, bad):
    fake = timeline()
    before = fake.snapshot()
    plan = plan_for(fake, [FrameRange(10, 20)])
    approved = plan.approved_ripple_displacements
    if bad == "missing":
        approved = ()
    elif bad == "delta":
        approved = (replace(approved[0], delta_frames=-9),) + approved[1:]
    elif bad == "extra":
        approved += (RippleDisplacement(V1, FrameRange(0, 10), -1),)
    elif bad == "range":
        approved = (replace(approved[0], original_range=FrameRange(21, 40)),) + approved[1:]
    elif bad == "track":
        approved = (replace(approved[0], track_id=TrackId("wrong")),) + approved[1:]
    else:
        approved += approved[:1]
    monkeypatch.setattr(
        FakeTimeline,
        "_delete",
        staticmethod(lambda *args: pytest.fail("delete called before preflight rejection")),
    )
    with pytest.raises(ValueError, match="displacement"):
        fake.apply(replace(plan, approved_ripple_displacements=approved))
    assert fake.snapshot() == before


@pytest.mark.parametrize(
    "interval",
    [
        FrameRange(12, 18),
        FrameRange(5, 15),
        FrameRange(15, 25),
        FrameRange(5, 25),
        FrameRange(10, 20),
        FrameRange(0, 5),
        FrameRange(0, 10),
    ],
)
def test_hard_lock_rejects_direct_and_ripple_before_mutation(monkeypatch, interval):
    fake = timeline((ProtectedRange(V1, FrameRange(10, 20)),))
    before = fake.snapshot()
    plan = plan_for(fake, [interval])
    monkeypatch.setattr(
        FakeTimeline,
        "_delete",
        staticmethod(lambda *args: pytest.fail("HARD_LOCK must reject before the first delete")),
    )
    with pytest.raises(ValueError, match="HARD_LOCK"):
        fake.apply(plan)
    assert fake.snapshot() == before


@pytest.mark.parametrize("interval", [FrameRange(20, 25), FrameRange(60, 65)])
def test_hard_lock_end_boundary_and_later_edits_are_allowed(interval):
    protected = ProtectedRange(V1, FrameRange(10, 20))
    fake = timeline((protected,))
    before = fake.snapshot()
    fake.apply(plan_for(fake, [interval]))
    assert fake.snapshot().protected_ranges == (protected,)
    assert [f for f in frames(fake.snapshot()) if 10 <= f[3] < 20] == [
        f for f in frames(before) if 10 <= f[3] < 20
    ]
    assert fake.snapshot().version == before.version + 1


@pytest.mark.parametrize("reverse", [False, True])
def test_late_violation_and_multiple_protections_reject_entire_plan(monkeypatch, reverse):
    fake = timeline(
        (ProtectedRange(V1, FrameRange(10, 20)), ProtectedRange(V1, FrameRange(70, 80)))
    )
    before = fake.snapshot()
    intervals = [FrameRange(110, 120), FrameRange(60, 65)]
    if reverse:
        intervals.reverse()
    plan = plan_for(fake, intervals)
    monkeypatch.setattr(
        FakeTimeline,
        "_delete",
        staticmethod(lambda *args: pytest.fail("a later violation must block the first command")),
    )
    with pytest.raises(ValueError, match="HARD_LOCK"):
        fake.apply(plan)
    assert fake.snapshot() == before


def test_hard_lock_in_gap_still_blocks_earlier_ripple():
    fake = timeline((ProtectedRange(V1, FrameRange(42, 48)),))
    before = fake.snapshot()
    with pytest.raises(ValueError, match="HARD_LOCK"):
        fake.apply(plan_for(fake, [FrameRange(10, 20)]))
    assert fake.snapshot() == before


@pytest.mark.parametrize("corruption", ["media", "source", "order", "position", "missing", "extra"])
def test_inv002_corrupted_candidate_never_published(monkeypatch, corruption):
    fake = timeline()
    before = fake.snapshot()
    plan = plan_for(fake, [FrameRange(120, 130)])
    original = FakeTimeline._delete

    def corrupt(track, index, interval):
        result = original(track, index, interval)
        clips = list(result.clips)
        if corruption == "media":
            clips[0] = replace(clips[0], media_id=MediaId("wrong"))
        elif corruption == "source":
            clips[0] = replace(clips[0], source_range=FrameRange(101, 141))
        elif corruption == "order":
            clips[0], clips[1] = (
                replace(clips[1], timeline_range=clips[0].timeline_range),
                replace(clips[0], timeline_range=clips[1].timeline_range),
            )
        elif corruption == "position":
            clips[0] = replace(clips[0], timeline_range=FrameRange(1, 41))
        elif corruption == "missing":
            clips.pop(0)
        else:
            clips.append(
                Clip(ClipId("extra"), MediaId("x"), FrameRange(140, 150), FrameRange(0, 10))
            )
        return replace(result, clips=tuple(clips))

    monkeypatch.setattr(FakeTimeline, "_delete", staticmethod(corrupt))
    with pytest.raises(ValueError, match="INV-002"):
        fake.apply(plan)
    assert fake.snapshot() == before


def test_repeated_plan_uses_new_snapshot_and_preserves_old_snapshot():
    fake = timeline((ProtectedRange(V1, FrameRange(0, 5)),))
    original = fake.snapshot()
    fake.apply(plan_for(fake, [FrameRange(10, 20)]))
    first = fake.snapshot()
    fake.apply(plan_for(fake, [FrameRange(50, 55)]))
    assert fake.snapshot().version == original.version + 2
    assert first.version == original.version + 1
    assert original.duration == 130
    assert fake.snapshot().protected_ranges == original.protected_ranges


def test_protection_must_reference_known_track():
    with pytest.raises(ValueError, match="track"):
        timeline((ProtectedRange(TrackId("wrong"), FrameRange(10, 20)),))


def test_non_hard_lock_policy_is_not_supported():
    with pytest.raises(ValueError, match="HARD_LOCK"):
        ProtectedRange(V1, FrameRange(0, 10), policy="SOFT")
