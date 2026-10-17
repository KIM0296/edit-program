"""STUDIO-T1 tier 4 "razor assist": playhead steps and NEUTRAL_SPLIT classification.

Qualification: CODE_COMPLETE / TEST_ONLY_SUPPORT. Pure functions, no Resolve
access. Resolve's scripting API cannot split an item at a frame
(``studio_capabilities.SPLIT_ITEM_AT_FRAME`` = NOT_AVAILABLE). In tier 4 the
transport only moves the playhead to each listed frame
(``Timeline.SetCurrentTimecode``); the EDITOR presses blade. Afterwards the
live timeline is re-read and compared with the confirmed Actual:

- ``NEUTRAL_SPLIT``: every change divides one item into source-contiguous
  pieces (same media, name, enabled state, no gap, the union of the pieces'
  markers equal to the original's) and every split frame is one we listed.
  Nothing else changed. This is not a human edit and creates no HARD_LOCK;
  merging the pieces back reproduces the confirmed Actual exactly.
- ``INCOMPLETE_SPLIT``: only neutral splits, but some listed frames are not
  split yet (the editor is not done). Nothing is applied.
- ``HUMAN_EDIT``: anything else (a split at an unlisted frame, a trim, a move,
  a marker change, a renamed or disabled piece). The cut is not applied; the
  normal RT-001 flow (HARD_LOCK on human edits) decides on the next run.
- ``NO_CHANGE``: identical timelines (nothing listed and nothing split).

INT-002: the split geometry rule is the core one
(``roundtrip_diff.contiguous_split_frames``), shared with RT-001's
``NEUTRAL_SPLIT`` (``diff_roundtrip(..., expected_splits=...)``) so the file path
and Studio agree on what an editor razor at listed frames is.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from .handoff_model import HandoffClip, HandoffMarker, HandoffTrack, ReimportedTimeline
from .roundtrip_diff import contiguous_split_frames
from .studio_capabilities import QUALIFICATION
from .temporal_mapping import FrameRate

SplitPlan = Mapping[str, frozenset[int]]  # track name -> timeline-relative split frames


def nominal_timecode_base(rate: FrameRate) -> int | None:
    """Frames per timecode second for non-drop timecode, or None (drop-frame unknown)."""
    if rate.denominator == 1 and rate.numerator > 0:
        return rate.numerator
    if (rate.numerator, rate.denominator) in ((24000, 1001), (48000, 1001)):
        return rate.numerator // 1000  # 23.976 / 47.952 use non-drop 24 / 48 counting
    return None  # 29.97 / 59.94: drop-frame or not is a project setting we cannot read


def timecode_for_frame(absolute_frame: int, rate: FrameRate) -> str | None:
    """Non-drop ``HH:MM:SS:FF`` for an absolute timeline frame, or None when unknown."""
    base = nominal_timecode_base(rate)
    if base is None or type(absolute_frame) is not int or absolute_frame < 0:
        return None
    frames = absolute_frame % base
    seconds_total = absolute_frame // base
    hours, rest = divmod(seconds_total, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours > 23:
        return None
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


@dataclass(frozen=True)
class RazorStep:
    """One playhead stop. The editor blades ``tracks`` (and only those) at this frame."""

    index: int
    frame: int  # timeline-relative
    absolute_frame: int
    timecode: str
    tracks: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracks", tuple(self.tracks))
        if not self.tracks or self.index < 1:
            raise ValueError("A razor step names at least one track and a 1-based index")


def razor_steps(plan: SplitPlan, start_frame: int, rate: FrameRate) -> tuple[RazorStep, ...] | None:
    """Group split frames into playhead stops (ascending). None if a timecode is unknown."""
    by_frame: dict[int, set[str]] = {}
    for track, frames in plan.items():
        for frame in frames:
            by_frame.setdefault(frame, set()).add(track)
    steps: list[RazorStep] = []
    for number, frame in enumerate(sorted(by_frame), start=1):
        timecode = timecode_for_frame(start_frame + frame, rate)
        if timecode is None:
            return None
        steps.append(
            RazorStep(number, frame, start_frame + frame, timecode, tuple(sorted(by_frame[frame])))
        )
    return tuple(steps)


class SplitChangeKind(str, Enum):
    UNKNOWN = "UNKNOWN"
    NO_CHANGE = "NO_CHANGE"
    NEUTRAL_SPLIT = "NEUTRAL_SPLIT"
    INCOMPLETE_SPLIT = "INCOMPLETE_SPLIT"
    HUMAN_EDIT = "HUMAN_EDIT"


@dataclass(frozen=True)
class SplitClassification:
    kind: SplitChangeKind
    found: tuple[tuple[str, int], ...]
    missing: tuple[tuple[str, int], ...]
    reasons: tuple[str, ...]
    qualification: Literal["TEST_ONLY_SUPPORT"] = QUALIFICATION

    def __post_init__(self) -> None:
        for name in ("found", "missing", "reasons"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not isinstance(self.kind, SplitChangeKind):
            raise TypeError("Typed split change kind required")
        if self.kind is SplitChangeKind.NEUTRAL_SPLIT and (self.missing or self.reasons):
            raise ValueError("NEUTRAL_SPLIT has every listed split and nothing else")

    @property
    def hard_lock(self) -> bool:
        """Only a real human edit locks; a neutral (listed, source-contiguous) split never."""
        return self.kind is SplitChangeKind.HUMAN_EDIT


class _Human(Exception):
    pass


def _marker_key(marker: HandoffMarker) -> tuple[int, int, str, str, str]:
    return (
        marker.frame_range.start,
        marker.frame_range.end,
        marker.name,
        marker.note,
        marker.color.value,
    )


def _same_piece(piece: HandoffClip, original: HandoffClip) -> bool:
    return (
        piece.media == original.media
        and piece.enabled == original.enabled
        and piece.name == original.name
    )


def _track_splits(before: HandoffTrack, after: HandoffTrack, planned: frozenset[int]) -> list[int]:
    if (before.name, before.kind) != (after.name, after.kind):
        raise _Human(f"{after.name}: track identity changed")
    pieces: Sequence[tuple[int, HandoffClip]] = tuple(after.placements())
    found: list[int] = []
    cursor = 0
    for start, original in before.placements():
        end = start + original.duration
        group: list[tuple[int, HandoffClip]] = []
        while cursor < len(pieces) and pieces[cursor][0] < end:
            group.append(pieces[cursor])
            cursor += 1

        def same(piece: HandoffClip, original: HandoffClip = original) -> bool:
            return _same_piece(piece, original)

        frames = contiguous_split_frames(start, original, group, same)
        if isinstance(frames, str):
            raise _Human(f"{before.name}@{start}: {frames}")
        for frame in frames:
            if frame not in planned:
                raise _Human(f"{before.name}@{frame}: split at an unlisted frame")
        found.extend(frames)
        markers = sorted(_marker_key(m) for _, piece in group for m in piece.markers)
        if markers != sorted(_marker_key(m) for m in original.markers):
            raise _Human(f"{before.name}@{start}: markers changed across the split")
    if cursor != len(pieces):
        raise _Human(f"{before.name}: extra items")
    return found


def classify_split_change(
    before: ReimportedTimeline, after: ReimportedTimeline, planned: SplitPlan
) -> SplitClassification:
    """Compare the confirmed Actual with the post-razor live Actual (pure)."""
    if not isinstance(before, ReimportedTimeline) or not isinstance(after, ReimportedTimeline):
        raise TypeError("Both sides are ReimportedTimeline reads")
    listed = {(track, frame) for track, frames in planned.items() for frame in frames}
    try:
        if (before.name, before.rate, before.start_frame) != (
            after.name,
            after.rate,
            after.start_frame,
        ):
            raise _Human("timeline header changed")
        if len(before.tracks) != len(after.tracks):
            raise _Human("track count changed")
        found: list[tuple[str, int]] = []
        for left, right in zip(before.tracks, after.tracks, strict=True):
            frames = planned.get(left.name, frozenset())
            found.extend((left.name, f) for f in _track_splits(left, right, frames))
    except _Human as human:
        return SplitClassification(
            SplitChangeKind.HUMAN_EDIT, (), tuple(sorted(listed)), (str(human),)
        )
    missing = tuple(sorted(listed - set(found)))
    found_sorted = tuple(sorted(found))
    if not found_sorted and not missing:
        return SplitClassification(SplitChangeKind.NO_CHANGE, (), (), ())
    if missing:
        return SplitClassification(SplitChangeKind.INCOMPLETE_SPLIT, found_sorted, missing, ())
    return SplitClassification(SplitChangeKind.NEUTRAL_SPLIT, found_sorted, (), ())
