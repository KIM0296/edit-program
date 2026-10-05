"""Scoped INV-002/003 checks for the single-track ripple-DELETE fake.

Compute expected survivors from the immutable base, independently of the sequential
mutation algorithm. This is not a transaction/rollback or general postflight engine.
"""

from dataclasses import replace

from .domain import (
    Clip,
    EditCommand,
    EditPlan,
    FrameRange,
    RippleDisplacement,
    TimelineSnapshot,
    Track,
)


def _expected_layout(
    base: TimelineSnapshot, commands: tuple[EditCommand, ...]
) -> tuple[Track, tuple[RippleDisplacement, ...]]:
    if len(base.tracks) != 1:
        raise ValueError("Only one-track fake plans are supported")
    cuts: list[FrameRange] = []
    for command in commands:
        if command.action != "DELETE" or command.ripple is not True:
            raise ValueError("Fake supports ripple DELETE only")
        target = command.target
        if target != base.resolve(target.track_id, target.timeline_range):
            raise ValueError("Target does not match the base snapshot")
        if any(target.timeline_range.overlaps(r) for r in cuts):
            raise ValueError("Overlapping targets are unsupported")
        cuts.append(target.timeline_range)
    cuts.sort(key=lambda r: r.start)
    track = base.tracks[0]
    survivors: list[Clip] = []
    displacements: list[RippleDisplacement] = []
    for clip in track.clips:
        intervals: list[FrameRange] = []
        cursor = clip.timeline_range.start
        for cut in cuts:
            if not cut.overlaps(clip.timeline_range):
                continue
            if cursor < cut.start:
                intervals.append(FrameRange(cursor, cut.start))
            cursor = cut.end
        if cursor < clip.timeline_range.end:
            intervals.append(FrameRange(cursor, clip.timeline_range.end))
        for interval in intervals:
            delta = -sum(cut.duration for cut in cuts if cut.end <= interval.start)
            source = clip.source_range.start + interval.start - clip.timeline_range.start
            survivors.append(
                replace(
                    clip,
                    source_range=FrameRange(source, source + interval.duration),
                    timeline_range=FrameRange(interval.start + delta, interval.end + delta),
                )
            )
            if delta:
                displacements.append(RippleDisplacement(track.track_id, interval, delta))
    return replace(track, clips=tuple(survivors)), tuple(displacements)


def propose_ripple_displacements(
    base: TimelineSnapshot, commands: tuple[EditCommand, ...]
) -> tuple[RippleDisplacement, ...]:
    """Return a proposal; only the caller can explicitly include it in an EditPlan.

    This does not approve the plan or bypass HARD_LOCK validation.
    """
    return _expected_layout(base, commands)[1]


def preflight(base: TimelineSnapshot, plan: EditPlan) -> Track:
    """Reject before the fake invokes any delete; return the exact expected track."""
    if plan.timeline_id != base.timeline_id or plan.base_version != base.version:
        raise ValueError("Plan does not match current timeline snapshot")
    if plan.commands and base.relationship_graph and base.relationship_graph.relationships:
        raise ValueError("REVIEW: relationship-aware editing is not implemented")
    expected, displacements = _expected_layout(base, plan.commands)
    for protection in base.protected_ranges:
        for command in plan.commands:
            target = command.target
            if target.track_id != protection.track_id:
                continue
            direct = target.timeline_range.overlaps(protection.frame_range)
            shifts = target.timeline_range.end <= protection.frame_range.start
            if direct or shifts:
                raise ValueError("HARD_LOCK violation: direct edit or ripple position change")
    approved = plan.approved_ripple_displacements
    if len(approved) != len(displacements) or set(approved) != set(displacements):
        raise ValueError("Unapproved or mismatched ripple displacement")
    return expected


def verify_unrequested_content(expected: Track, actual: Track) -> None:
    """Check ordered identity, source intervals and approved absolute positions."""
    if actual != expected:
        raise ValueError("INV-002 violation: unexpected content or timeline displacement")
