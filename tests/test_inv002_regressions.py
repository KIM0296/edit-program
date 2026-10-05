from dataclasses import replace

import pytest

from davinci_ai_editor.domain import (
    Clip,
    ClipId,
    EditCommand,
    EditPlan,
    FrameRange,
    MediaId,
    TimelineId,
    Track,
    TrackId,
)
from davinci_ai_editor.fake_timeline import FakeTimeline


def test_inv002_missing_displacement_approval_rejected_before_delete(monkeypatch):
    fake = FakeTimeline(
        TimelineId("main"),
        Track(
            TrackId("V1"),
            (Clip(ClipId("c"), MediaId("m"), FrameRange(0, 100), FrameRange(1000, 1100)),),
        ),
    )
    before = fake.snapshot()
    target = before.resolve(TrackId("V1"), FrameRange(10, 20))
    plan = EditPlan(before.timeline_id, before.version, (EditCommand(target),))
    original = FakeTimeline._delete
    calls = []

    def spy(track, index, interval):
        calls.append(interval)
        return original(track, index, interval)

    monkeypatch.setattr(FakeTimeline, "_delete", staticmethod(spy))
    with pytest.raises(ValueError, match="displacement"):
        fake.apply(plan)
    assert calls == []
    assert fake.snapshot() == before


def test_inv002_unrequested_media_corruption_is_not_published(monkeypatch):
    fake = FakeTimeline(
        TimelineId("main"),
        Track(
            TrackId("V1"),
            (Clip(ClipId("c"), MediaId("m"), FrameRange(0, 100), FrameRange(1000, 1100)),),
        ),
    )
    before = fake.snapshot()
    # Tail deletion needs no displacement approval, but must preserve preceding media.
    target = before.resolve(TrackId("V1"), FrameRange(90, 100))
    plan = EditPlan(before.timeline_id, before.version, (EditCommand(target),))
    original = FakeTimeline._delete

    def corrupt(track, index, interval):
        result = original(track, index, interval)
        return replace(result, clips=(replace(result.clips[0], media_id=MediaId("wrong")),))

    monkeypatch.setattr(FakeTimeline, "_delete", staticmethod(corrupt))
    with pytest.raises(ValueError, match="INV-002"):
        fake.apply(plan)
    assert fake.snapshot() == before
