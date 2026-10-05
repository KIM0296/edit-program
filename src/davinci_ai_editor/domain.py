"""Immutable timeline domain values. Ranges are integer, half-open [start, end)."""

from dataclasses import dataclass
from typing import Literal, NewType

TimelineId = NewType("TimelineId", str)
TimelineVersion = NewType("TimelineVersion", int)
TrackId = NewType("TrackId", str)
ClipId = NewType("ClipId", str)
MediaId = NewType("MediaId", str)


@dataclass(frozen=True)
class FrameRange:
    start: int
    end: int

    def __post_init__(self) -> None:
        if type(self.start) is not int or type(self.end) is not int:
            raise ValueError("Frame boundaries must be integers")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("Expected nonempty, nonnegative [start, end)")

    @property
    def duration(self) -> int:
        return self.end - self.start

    def contains(self, other: "FrameRange") -> bool:
        return self.start <= other.start and other.end <= self.end

    def overlaps(self, other: "FrameRange") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class Clip:
    # Fake-only placement lineage. Split fragments keep this ID (ADR-012).
    clip_id: ClipId
    media_id: MediaId
    timeline_range: FrameRange
    source_range: FrameRange

    def __post_init__(self) -> None:
        if self.timeline_range.duration != self.source_range.duration:
            raise ValueError("Only 1:1 source mapping is supported by the fake")


@dataclass(frozen=True)
class Track:
    track_id: TrackId
    clips: tuple[Clip, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "clips", tuple(self.clips))
        if any(
            a.timeline_range.end > b.timeline_range.start
            for a, b in zip(self.clips, self.clips[1:])
        ):
            raise ValueError("Clips must be ordered and nonoverlapping")


@dataclass(frozen=True)
class StableTarget:
    timeline_id: TimelineId
    timeline_version: TimelineVersion
    track_id: TrackId
    clip_id: ClipId
    media_id: MediaId
    timeline_range: FrameRange
    source_range: FrameRange
    coordinate_space: Literal["TIMELINE"] = "TIMELINE"


@dataclass(frozen=True)
class ProtectedRange:
    track_id: TrackId
    frame_range: FrameRange
    policy: str = "HARD_LOCK"

    def __post_init__(self) -> None:
        if self.policy != "HARD_LOCK":
            raise ValueError("Only HARD_LOCK protection is supported")


@dataclass(frozen=True)
class RippleDisplacement:
    """Explicit allowed movement of surviving content in base-snapshot coordinates."""

    track_id: TrackId
    original_range: FrameRange
    delta_frames: int

    def __post_init__(self) -> None:
        if type(self.delta_frames) is not int or self.delta_frames >= 0:
            raise ValueError("Ripple DELETE displacement must be a negative integer")


@dataclass(frozen=True)
class TimelineSnapshot:
    timeline_id: TimelineId
    version: TimelineVersion
    tracks: tuple[Track, ...]
    protected_ranges: tuple[ProtectedRange, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracks", tuple(self.tracks))
        object.__setattr__(self, "protected_ranges", tuple(self.protected_ranges))
        track_ids = {t.track_id for t in self.tracks}
        if any(p.track_id not in track_ids for p in self.protected_ranges):
            raise ValueError("Protected range must reference a known track")

    @property
    def duration(self) -> int:
        return max((c.timeline_range.end for t in self.tracks for c in t.clips), default=0)

    def resolve(self, track_id: TrackId, interval: FrameRange) -> StableTarget:
        matches = [
            c
            for t in self.tracks
            if t.track_id == track_id
            for c in t.clips
            if c.timeline_range.contains(interval)
        ]
        if len(matches) != 1:
            raise ValueError("Target must lie in exactly one clip fragment on the given track")
        clip = matches[0]
        start = clip.source_range.start + interval.start - clip.timeline_range.start
        return StableTarget(
            self.timeline_id,
            self.version,
            track_id,
            clip.clip_id,
            clip.media_id,
            interval,
            FrameRange(start, start + interval.duration),
        )


@dataclass(frozen=True)
class EditCommand:
    target: StableTarget
    action: str = "DELETE"
    ripple: bool = True


@dataclass(frozen=True)
class EditPlan:
    timeline_id: TimelineId
    base_version: TimelineVersion
    commands: tuple[EditCommand, ...]
    approved_ripple_displacements: tuple[RippleDisplacement, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "commands", tuple(self.commands))
        object.__setattr__(
            self, "approved_ripple_displacements", tuple(self.approved_ripple_displacements)
        )
