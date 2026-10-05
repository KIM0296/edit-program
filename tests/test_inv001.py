from dataclasses import FrozenInstanceError, replace

import pytest

from davinci_ai_editor.domain import (
    Clip,
    ClipId,
    EditCommand,
    EditPlan,
    FrameRange,
    MediaId,
    TimelineId,
    TimelineVersion,
    Track,
    TrackId,
)
from davinci_ai_editor.fake_timeline import FakeTimeline
from davinci_ai_editor.safety import propose_ripple_displacements


def timeline() -> FakeTimeline:
    return FakeTimeline(
        TimelineId("main"),
        Track(
            TrackId("V1"),
            (
                Clip(
                    ClipId("clip"), MediaId("media"), FrameRange(0, 3600), FrameRange(10000, 13600)
                ),
            ),
        ),
    )


def original_frames(fake: FakeTimeline) -> list[int]:
    return [
        f
        for c in fake.snapshot().tracks[0].clips
        for f in range(c.source_range.start, c.source_range.end)
    ]


@pytest.mark.parametrize("reverse", [False, True])
def test_inv001_stable_targets_and_exact_remaining_content(reverse: bool) -> None:
    fake = timeline()
    before = fake.snapshot()
    ranges = [FrameRange(900, 960), FrameRange(2700, 2760)]
    if reverse:
        ranges.reverse()
    targets = tuple(before.resolve(TrackId("V1"), r) for r in ranges)
    assert fake.snapshot() == before  # All targets resolved before mutation.
    plan = EditPlan(before.timeline_id, before.version, tuple(EditCommand(t) for t in targets))
    plan = replace(
        plan, approved_ripple_displacements=propose_ripple_displacements(before, plan.commands)
    )
    actual_positions = fake.apply(plan)
    assert (
        actual_positions == tuple(ranges)
        if reverse
        else actual_positions == (FrameRange(900, 960), FrameRange(2640, 2700))
    )
    assert targets[-1].timeline_version == before.version
    assert fake.snapshot().duration == before.duration - 120
    expected = [f for f in range(10000, 13600) if not (10900 <= f < 10960 or 12700 <= f < 12760)]
    assert original_frames(fake) == expected  # Ordered identity diff, not duration alone.
    assert fake.snapshot().version == TimelineVersion(before.version + 1)
    assert before.tracks[0].clips[0].timeline_range == FrameRange(0, 3600)


def test_duplicate_media_placements_do_not_confuse_clip_identity() -> None:
    fake = FakeTimeline(
        TimelineId("main"),
        Track(
            TrackId("V1"),
            (
                Clip(ClipId("a"), MediaId("shared"), FrameRange(0, 60), FrameRange(0, 60)),
                Clip(ClipId("b"), MediaId("shared"), FrameRange(60, 120), FrameRange(0, 60)),
            ),
        ),
    )
    snap = fake.snapshot()
    targets = tuple(snap.resolve(TrackId("V1"), r) for r in (FrameRange(0, 60), FrameRange(70, 80)))
    assert fake.apply(
        EditPlan(
            snap.timeline_id,
            snap.version,
            tuple(EditCommand(t) for t in targets),
            propose_ripple_displacements(snap, tuple(EditCommand(t) for t in targets)),
        )
    ) == (FrameRange(0, 60), FrameRange(10, 20))
    assert [
        (c.clip_id, c.source_range, c.timeline_range) for c in fake.snapshot().tracks[0].clips
    ] == [
        ("b", FrameRange(0, 10), FrameRange(0, 10)),
        ("b", FrameRange(20, 60), FrameRange(10, 50)),
    ]


@pytest.mark.parametrize("bounds", [(0, 0), (-1, 2), (3, 2), (True, 2), (0, 1.5)])
def test_invalid_frame_range(bounds: tuple[int, int]) -> None:
    with pytest.raises(ValueError):
        FrameRange(*bounds)


def test_snapshot_is_immutable() -> None:
    snap = timeline().snapshot()
    with pytest.raises(FrozenInstanceError):
        snap.version = 99  # type: ignore[misc,assignment]


@pytest.mark.parametrize("interval", [FrameRange(3590, 3610), FrameRange(3600, 3601)])
def test_unresolved_range_does_not_mutate(interval: FrameRange) -> None:
    fake = timeline()
    before = fake.snapshot()
    with pytest.raises(ValueError):
        before.resolve(TrackId("V1"), interval)
    assert fake.snapshot() == before


@pytest.mark.parametrize("bad", ["version", "timeline", "media", "overlap", "action"])
def test_invalid_plan_rejected_before_mutation(bad: str) -> None:
    fake = timeline()
    snap = fake.snapshot()
    target = snap.resolve(TrackId("V1"), FrameRange(900, 960))
    plan = EditPlan(snap.timeline_id, snap.version, (EditCommand(target),))
    if bad == "version":
        plan = replace(plan, base_version=TimelineVersion(999))
    elif bad == "timeline":
        plan = replace(plan, timeline_id=TimelineId("other"))
    elif bad == "media":
        plan = replace(plan, commands=(EditCommand(replace(target, media_id=MediaId("x"))),))
    elif bad == "overlap":
        plan = replace(plan, commands=plan.commands * 2)
    else:
        plan = replace(plan, commands=(replace(plan.commands[0], action="MOVE"),))
    with pytest.raises(ValueError):
        fake.apply(plan)
    assert fake.snapshot() == snap


@pytest.mark.parametrize(
    "ranges",
    [
        (FrameRange(0, 10), FrameRange(10, 20)),
        (FrameRange(10, 20), FrameRange(0, 10)),
        (FrameRange(3590, 3600),),
        (FrameRange(0, 3600),),
    ],
)
def test_boundaries_preserve_exact_source_content(ranges: tuple[FrameRange, ...]) -> None:
    fake = timeline()
    snap = fake.snapshot()
    plan = EditPlan(
        snap.timeline_id,
        snap.version,
        tuple(EditCommand(snap.resolve(TrackId("V1"), r)) for r in ranges),
    )
    plan = replace(
        plan, approved_ripple_displacements=propose_ripple_displacements(snap, plan.commands)
    )
    fake.apply(plan)
    expected = [f + 10000 for f in range(3600) if not any(r.start <= f < r.end for r in ranges)]
    assert original_frames(fake) == expected
    assert fake.snapshot().duration == len(expected)


def test_later_invalid_command_prevents_earlier_delete() -> None:
    fake = timeline()
    snap = fake.snapshot()
    a = snap.resolve(TrackId("V1"), FrameRange(900, 960))
    b = snap.resolve(TrackId("V1"), FrameRange(2700, 2760))
    plan = EditPlan(
        snap.timeline_id,
        snap.version,
        (EditCommand(a), EditCommand(replace(b, clip_id=ClipId("missing")))),
    )
    with pytest.raises(ValueError):
        fake.apply(plan)
    assert fake.snapshot() == snap


def test_old_snapshot_cannot_be_applied_as_new_plan() -> None:
    fake = timeline()
    snap = fake.snapshot()
    a = snap.resolve(TrackId("V1"), FrameRange(900, 960))
    b = snap.resolve(TrackId("V1"), FrameRange(2700, 2760))
    fake.apply(
        EditPlan(
            snap.timeline_id,
            snap.version,
            (EditCommand(a),),
            propose_ripple_displacements(snap, (EditCommand(a),)),
        )
    )
    after = fake.snapshot()
    with pytest.raises(ValueError):
        fake.apply(EditPlan(snap.timeline_id, snap.version, (EditCommand(b),)))
    assert fake.snapshot() == after


def test_empty_timeline_and_plan() -> None:
    fake = FakeTimeline(TimelineId("empty"), Track(TrackId("V1")))
    snap = fake.snapshot()
    assert snap.duration == 0
    assert fake.apply(EditPlan(snap.timeline_id, snap.version, ())) == ()
    assert fake.snapshot() == snap
    with pytest.raises(ValueError):
        snap.resolve(TrackId("V1"), FrameRange(0, 1))


def test_gap_and_cross_clip_requests_are_explicitly_unsupported() -> None:
    fake = FakeTimeline(
        TimelineId("main"),
        Track(
            TrackId("V1"),
            (
                Clip(ClipId("a"), MediaId("m"), FrameRange(0, 10), FrameRange(0, 10)),
                Clip(ClipId("b"), MediaId("m"), FrameRange(20, 30), FrameRange(0, 10)),
            ),
        ),
    )
    snap = fake.snapshot()
    for interval in (FrameRange(10, 20), FrameRange(5, 25)):
        with pytest.raises(ValueError):
            snap.resolve(TrackId("V1"), interval)
    with pytest.raises(ValueError):
        snap.resolve(TrackId("missing"), FrameRange(0, 1))
    assert fake.snapshot() == snap
