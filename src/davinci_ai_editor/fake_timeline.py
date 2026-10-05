"""In-memory, one-track ripple simulation for INV-001 only.

This is not a validated transaction or a Resolve adapter. Unsupported scope raises
ValueError. All requests are checked against the base snapshot before mutation.
"""

from dataclasses import replace

from .domain import (
    Clip,
    EditPlan,
    FrameRange,
    StableTarget,
    TimelineId,
    TimelineSnapshot,
    TimelineVersion,
    Track,
)


class FakeTimeline:
    def __init__(self, timeline_id: TimelineId, track: Track) -> None:
        if len({c.clip_id for c in track.clips}) != len(track.clips):
            raise ValueError("Initial placements must have distinct clip IDs")
        self._snapshot = TimelineSnapshot(timeline_id, TimelineVersion(1), (track,))

    def snapshot(self) -> TimelineSnapshot:
        return self._snapshot

    def apply(self, plan: EditPlan) -> tuple[FrameRange, ...]:
        """Apply in command order, returning the actual positions used for each delete.

        Targets retain command-time coordinates. Only clip lineage/source intervals
        are used to locate them during execution; current-time resolve is never called.
        Version advances once for a nonempty plan. No production rollback is implied.
        """
        base = self._snapshot
        if plan.timeline_id != base.timeline_id or plan.base_version != base.version:
            raise ValueError("Plan does not match current timeline snapshot")
        seen: list[FrameRange] = []
        for command in plan.commands:
            if command.action != "DELETE" or command.ripple is not True:
                raise ValueError("Fake supports ripple DELETE only")
            target = command.target
            if target != base.resolve(target.track_id, target.timeline_range):
                raise ValueError("Target does not match the base snapshot")
            if any(target.timeline_range.overlaps(r) for r in seen):
                raise ValueError("Overlapping targets are unsupported")
            seen.append(target.timeline_range)

        if not plan.commands:
            return ()
        track = base.tracks[0]
        positions: list[FrameRange] = []
        for command in plan.commands:
            index, interval = self._locate(track, command.target)
            positions.append(interval)
            track = self._delete(track, index, interval)
        self._snapshot = replace(base, version=TimelineVersion(base.version + 1), tracks=(track,))
        return tuple(positions)

    @staticmethod
    def _locate(track: Track, target: StableTarget) -> tuple[int, FrameRange]:
        matches = [
            (i, c)
            for i, c in enumerate(track.clips)
            if track.track_id == target.track_id
            and c.clip_id == target.clip_id
            and c.media_id == target.media_id
            and c.source_range.contains(target.source_range)
        ]
        if len(matches) != 1:
            raise ValueError("Stable target no longer resolves to one fragment")
        index, clip = matches[0]
        start = clip.timeline_range.start + target.source_range.start - clip.source_range.start
        return index, FrameRange(start, start + target.source_range.duration)

    @staticmethod
    def _delete(track: Track, index: int, interval: FrameRange) -> Track:
        clips: list[Clip] = []
        for i, clip in enumerate(track.clips):
            if i < index:
                clips.append(clip)
            elif i > index:
                clips.append(
                    replace(
                        clip,
                        timeline_range=FrameRange(
                            clip.timeline_range.start - interval.duration,
                            clip.timeline_range.end - interval.duration,
                        ),
                    )
                )
            else:
                source_start = clip.source_range.start + interval.start - clip.timeline_range.start
                if clip.timeline_range.start < interval.start:
                    clips.append(
                        replace(
                            clip,
                            timeline_range=FrameRange(clip.timeline_range.start, interval.start),
                            source_range=FrameRange(clip.source_range.start, source_start),
                        )
                    )
                if interval.end < clip.timeline_range.end:
                    clips.append(
                        replace(
                            clip,
                            timeline_range=FrameRange(
                                interval.start, clip.timeline_range.end - interval.duration
                            ),
                            source_range=FrameRange(
                                source_start + interval.duration, clip.source_range.end
                            ),
                        )
                    )
        return replace(track, clips=tuple(clips))
