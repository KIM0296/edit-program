"""Deterministic FAKE Resolve object graph for STUDIO-T0 (TEST_ONLY_SUPPORT).

Not DaVinci Resolve and not a model of its verified behaviour: it implements the
getter/mutator *names* the Studio transport allowlists, with the semantics the
capability matrix documents (absolute GetStart/GetEnd, exclusive ends,
item-start-relative marker frameIds, whole-item DeleteClips with span ripple on
every track). Everything is configurable through :class:`FakeBehavior` so tests
can produce None getters, unstable reads, inclusive ends, missing methods, a
failing DeleteClips and a post-mutation geometry error.

``AieTestOnlySplitAt`` is NOT a Resolve API (no split API exists; see
``studio_capabilities.SPLIT_ITEM_AT_FRAME``). It exists only so the transport's
capability-flag path can be tested, and only when ``FakeBehavior.split_enabled``.
"""

from dataclasses import dataclass, field
from typing import Any

from davinci_ai_editor.handoff_model import HandoffClip, HandoffTimeline, HandoffTrackKind

_COLOR_NAMES = {
    "RED": "Red",
    "GREEN": "Green",
    "BLUE": "Blue",
    "CYAN": "Cyan",
    "YELLOW": "Yellow",
    "PINK": "Pink",
    "PURPLE": "Purple",
}
_RATE_STRINGS = {
    (24000, 1001): "23.976",
    (24, 1): "24",
    (25, 1): "25",
    (30000, 1001): "29.97",
    (30, 1): "30",
    (50, 1): "50",
    (60000, 1001): "59.94",
    (60, 1): "60",
}


@dataclass
class FakeBehavior:
    """Mutable test knobs. Keys are ``"<Kind>.<Method>"`` (e.g. ``"TimelineItem.GetEnd"``)."""

    none_methods: set[str] = field(default_factory=set)
    missing_methods: set[str] = field(default_factory=set)
    unstable_methods: set[str] = field(default_factory=set)
    inclusive_item_end: bool = False
    delete_clips_result: bool | None = None  # force a return value and do nothing
    ripple_extra_shift: int = 0  # post-mutation geometry error (frames)
    split_enabled: bool = False
    no_current_timeline: bool = False
    calls: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)
    _seen: dict[tuple[int, str], int] = field(default_factory=dict)

    def count(self, key: str) -> int:
        return sum(1 for name, _ in self.calls if name == key)


class _FakeObject:
    KIND = "Object"

    def __init__(self, behavior: FakeBehavior) -> None:
        self._behavior = behavior

    def __getattribute__(self, name: str) -> Any:
        attr = object.__getattribute__(self, name)
        if name.startswith("_") or not name[:1].isupper() or name == "KIND":
            return attr
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        key = f"{object.__getattribute__(self, 'KIND')}.{name}"
        if key in behavior.missing_methods:
            raise AttributeError(name)

        def call(*args: Any) -> Any:
            behavior.calls.append((key, args))
            if key in behavior.none_methods:
                return None
            value = attr(*args)
            if key in behavior.unstable_methods and type(value) is int:
                # the n-th call of this getter on this object drifts by n frames
                seen = (id(self), key)
                drift = behavior._seen.get(seen, 0)
                behavior._seen[seen] = drift + 1
                return value + drift
            return value

        return call


class FakeMediaPoolItem(_FakeObject):
    KIND = "MediaPoolItem"

    def __init__(
        self,
        behavior: FakeBehavior,
        name: str,
        path: str | None,
        frames: int | None,
        start: int | None,
        uid: str,
    ) -> None:
        super().__init__(behavior)
        self._name = name
        self._path = path
        self._frames = frames
        self._start = start
        self._uid = uid

    def GetName(self) -> str:
        return self._name

    def GetUniqueId(self) -> str:
        return self._uid

    def GetClipProperty(self, key: str) -> str:
        values = {
            "File Path": self._path or "",
            "Frames": "" if self._frames is None else str(self._frames),
            "Start": "" if self._start is None else str(self._start),
            "File Name": self._name,
        }
        return values.get(key, "")


class FakeTimelineItem(_FakeObject):
    KIND = "TimelineItem"

    def __init__(
        self,
        behavior: FakeBehavior,
        name: str,
        media: FakeMediaPoolItem | None,
        start: int,
        end: int,
        left_offset: int,
        uid: str,
        enabled: bool = True,
    ) -> None:
        super().__init__(behavior)
        self._name = name
        self._media = media
        self._start = start
        self._end = end
        self._left = left_offset
        self._uid = uid
        self._enabled = enabled
        self._markers: dict[float, dict[str, Any]] = {}

    # getters -------------------------------------------------------------
    def GetName(self) -> str:
        return self._name

    def GetStart(self, subframe: bool = False) -> int:
        return self._start

    def GetEnd(self, subframe: bool = False) -> int:
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        return self._end - 1 if behavior.inclusive_item_end else self._end

    def GetDuration(self, subframe: bool = False) -> int:
        return self._end - self._start

    def GetLeftOffset(self, subframe: bool = False) -> int:
        return self._left

    def GetSourceStartFrame(self) -> int:
        return self._left

    def GetMediaPoolItem(self) -> FakeMediaPoolItem | None:
        return self._media

    def GetClipEnabled(self) -> bool:
        return self._enabled

    def GetUniqueId(self) -> str:
        return self._uid

    def GetMarkers(self) -> dict[float, dict[str, Any]]:
        return {frame: dict(info) for frame, info in self._markers.items()}

    # mutators ------------------------------------------------------------
    def AddMarker(
        self,
        frame_id: int,
        color: str,
        name: str,
        note: str,
        duration: int,
        custom_data: str = "",
    ) -> bool:
        key = float(frame_id)
        if key in self._markers or frame_id < 0 or frame_id + duration > self._end - self._start:
            return False
        self._markers[key] = {
            "color": color,
            "duration": float(duration),
            "note": note,
            "name": name,
            "customData": custom_data,
        }
        return True

    def DeleteMarkerByCustomData(self, custom_data: str) -> bool:
        for frame, info in sorted(self._markers.items()):
            if info["customData"] == custom_data:
                del self._markers[frame]
                return True
        return False

    def DeleteMarkerAtFrame(self, frame: int) -> bool:
        return self._markers.pop(float(frame), None) is not None

    # test-only (simulated editor actions in the Resolve UI; not allowlisted) ----
    def _rename_marker(self, custom_data: str, new_name: str) -> None:
        for info in self._markers.values():
            if info["customData"] == custom_data:
                info["name"] = new_name
                return
        raise KeyError(custom_data)

    def _set_marker_color(self, custom_data: str, color: str) -> None:
        for info in self._markers.values():
            if info["customData"] == custom_data:
                info["color"] = color
                return
        raise KeyError(custom_data)


class FakeTimeline(_FakeObject):
    KIND = "Timeline"

    def __init__(
        self,
        behavior: FakeBehavior,
        name: str,
        start_frame: int,
        rate: str,
        video: list[list[FakeTimelineItem]],
        audio: list[list[FakeTimelineItem]],
        uid: str = "fake-timeline-1",
    ) -> None:
        super().__init__(behavior)
        self._name = name
        self._start_frame = start_frame
        self._rate = rate
        self._tracks = {"video": video, "audio": audio}
        self._uid = uid
        self._markers: dict[float, dict[str, Any]] = {}

    def GetName(self) -> str:
        return self._name

    def GetUniqueId(self) -> str:
        return self._uid

    def GetStartFrame(self) -> int:
        return self._start_frame

    def GetEndFrame(self) -> int:
        ends = [i._end for tracks in self._tracks.values() for t in tracks for i in t]
        return max(ends, default=self._start_frame)

    def GetSetting(self, key: str) -> str:
        return {"timelineFrameRate": self._rate}.get(key, "")

    def GetTrackCount(self, track_type: str) -> int:
        return len(self._tracks.get(track_type, []))

    def GetItemListInTrack(self, track_type: str, index: int) -> list[FakeTimelineItem]:
        tracks = self._tracks.get(track_type, [])
        if not 1 <= index <= len(tracks):
            return []
        return list(tracks[index - 1])

    def GetMarkers(self) -> dict[float, dict[str, Any]]:
        return dict(self._markers)

    def DeleteClips(self, items: list[FakeTimelineItem], ripple: bool = False) -> bool:
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        if behavior.delete_clips_result is not None:
            return behavior.delete_clips_result
        targets = {id(i) for i in items}
        present = {id(i) for tracks in self._tracks.values() for t in tracks for i in t}
        if not targets or not targets <= present:
            return False
        spans = sorted({(i._start, i._end) for i in items})
        merged: list[list[int]] = []
        for start, end in spans:
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        if ripple:
            # span ripple on every track: refuse if a non-target item overlaps a span
            for tracks in self._tracks.values():
                for track in tracks:
                    for item in track:
                        if id(item) in targets:
                            continue
                        if any(item._start < e and s < item._end for s, e in merged):
                            return False
        for tracks in self._tracks.values():
            for index, track in enumerate(tracks):
                kept = [i for i in track if id(i) not in targets]
                if ripple:
                    for item in kept:
                        shift = sum(e - s for s, e in merged if e <= item._start)
                        if shift:
                            shift += behavior.ripple_extra_shift
                        item._start -= shift
                        item._end -= shift
                tracks[index] = kept
        return True

    def AieTestOnlySplitAt(self, track_type: str, index: int, frame: int) -> bool:
        """NOT a Resolve API. Present only when ``FakeBehavior.split_enabled``."""
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        if not behavior.split_enabled:
            raise AttributeError("AieTestOnlySplitAt")
        tracks = self._tracks.get(track_type, [])
        if not 1 <= index <= len(tracks):
            return False
        track = tracks[index - 1]
        for position, item in enumerate(track):
            if item._start < frame < item._end:
                offset = frame - item._start
                right = FakeTimelineItem(
                    behavior,
                    item._name,
                    item._media,
                    frame,
                    item._end,
                    item._left + offset,
                    f"{item._uid}+{offset}",
                    item._enabled,
                )
                for key, info in list(item._markers.items()):
                    if key >= offset:
                        del item._markers[key]
                        right._markers[key - offset] = info
                item._end = frame
                track.insert(position + 1, right)
                return True
        return False

    # test-only helpers (simulated editor actions; not allowlisted) ----------
    def _item(self, track_type: str, index: int, position: int) -> FakeTimelineItem:
        return self._tracks[track_type][index - 1][position]

    def _find_marker_item(self, custom_data: str) -> FakeTimelineItem:
        for tracks in self._tracks.values():
            for track in tracks:
                for item in track:
                    if any(m["customData"] == custom_data for m in item._markers.values()):
                        return item
        raise KeyError(custom_data)

    def _rename_marker(self, custom_data: str, new_name: str) -> None:
        self._find_marker_item(custom_data)._rename_marker(custom_data, new_name)

    def _trim_end(self, track_type: str, index: int, position: int, frames: int) -> None:
        """Non-ripple tail trim by the editor (leaves a gap)."""
        item = self._item(track_type, index, position)
        item._end -= frames


class FakeProject(_FakeObject):
    KIND = "Project"

    def __init__(self, behavior: FakeBehavior, timeline: FakeTimeline) -> None:
        super().__init__(behavior)
        self._timeline = timeline

    def GetCurrentTimeline(self) -> FakeTimeline | None:
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        return None if behavior.no_current_timeline else self._timeline

    @property
    def timeline(self) -> FakeTimeline:
        return self._timeline


def fake_project_from_handoff(
    timeline: HandoffTimeline, behavior: FakeBehavior | None = None
) -> FakeProject:
    """Build the fake graph from a HandoffTimeline (markers included, colours mapped)."""
    behavior = FakeBehavior() if behavior is None else behavior
    media: dict[str, FakeMediaPoolItem] = {}
    video: list[list[FakeTimelineItem]] = []
    audio: list[list[FakeTimelineItem]] = []
    serial = 0
    for track in timeline.tracks:
        items: list[FakeTimelineItem] = []
        for start, clip in track.placements():
            ref = clip.media
            pool = media.get(ref.media_id)
            if pool is None:
                frames = None if ref.available_range is None else ref.available_range.end
                pool = FakeMediaPoolItem(
                    behavior,
                    ref.media_id,
                    ref.target_path,
                    frames,
                    ref.media_start_frame,
                    f"mpi-{len(media) + 1}",
                )
                media[ref.media_id] = pool
            serial += 1
            absolute = timeline.start_frame + start
            item = FakeTimelineItem(
                behavior,
                clip.name,
                pool,
                absolute,
                absolute + clip.duration,
                clip.source_range.start,
                f"ti-{serial}",
                clip.enabled,
            )
            _copy_markers(item, clip)
            items.append(item)
        if track.kind is HandoffTrackKind.VIDEO:
            video.append(items)
        elif track.kind is HandoffTrackKind.AUDIO:
            audio.append(items)
        else:
            raise ValueError("Fake supports VIDEO and AUDIO tracks only")
    rate = _RATE_STRINGS[(timeline.rate.numerator, timeline.rate.denominator)]
    fake = FakeTimeline(behavior, timeline.name, timeline.start_frame, rate, video, audio)
    return FakeProject(behavior, fake)


def _copy_markers(item: FakeTimelineItem, clip: HandoffClip) -> None:
    for marker in clip.markers:
        offset = marker.frame_range.start - clip.source_range.start
        item._markers[float(offset)] = {
            "color": _COLOR_NAMES.get(marker.color.value, "Blue"),
            "duration": float(marker.frame_range.duration),
            "note": marker.note,
            "name": marker.name,
            "customData": "",
        }
