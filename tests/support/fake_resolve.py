"""Deterministic FAKE Resolve object graph for STUDIO-T0/T1 (TEST_ONLY_SUPPORT).

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

STUDIO-T1 additions (all modelled on the DOCUMENTED claims and the OSS-measured
quirks recorded in ``studio_capabilities``, never on verified behaviour):

- ``MediaPool.ImportTimelineFromFile`` reads our own FCP7 XML with the repo's
  reader and builds a NEW timeline: the file's internal sequence name wins over
  ``timelineName``; an existing name returns that EXISTING timeline; markers
  lose colour and customData; track names reset to defaults unless
  ``import_keeps_track_names``; new items carry no grade; pool media are reused
  by name (importSourceClips=False).
- Grades are structural (:class:`FakeGrade`: node layers, versions) and Fusion
  comps are name -> content. ``CopyGrades`` copies the CURRENT (first) layer to
  each target, replacing it, and creates no version.
- ``SetCurrentTimecode`` / ``GetCurrentTimecode`` move and read a playhead;
  ``_blade`` simulates the editor's razor (a UI action, not an API).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from davinci_ai_editor.handoff_model import HandoffClip, HandoffTrackKind, TimelineStructure
from davinci_ai_editor.xmeml_reader import read_xmeml

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
_TC_BASE = {"23.976": 24, "24": 24, "25": 25, "30": 30, "50": 50, "60": 60}

Node = tuple[str, tuple[str, ...]]  # (label, tools)


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
    # STUDIO-T1 knobs
    import_result_none: bool = False
    import_returns_existing: bool = False  # simulate the FCP7 "returns existing" quirk
    import_keeps_track_names: bool = False
    import_extra_shift: int = 0  # imported geometry error (frames, from the 2nd item on)
    copy_grades_result: bool | None = None  # force a return value and do nothing
    copy_grades_partial: bool = False  # only the first target receives the grade
    node_stack_layers: str = "1"
    playhead_offset: int = 0  # playhead lands this many frames off
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


@dataclass
class FakeGrade:
    """Structural grade: node layers (first = current), colour versions."""

    layers: tuple[tuple[Node, ...], ...] = ((("", ()),),)
    versions: tuple[str, ...] = ("Version 1",)
    current_version: str = "Version 1"


GRADED = FakeGrade(layers=((("Primary", ("Primaries",)), ("Skin", ("Qualifier", "Window"))),))


class FakeGraph(_FakeObject):
    KIND = "Graph"

    def __init__(self, behavior: FakeBehavior, nodes: tuple[Node, ...]) -> None:
        super().__init__(behavior)
        self._nodes = nodes

    def GetNumNodes(self) -> int:
        return len(self._nodes)

    def GetNodeLabel(self, index: int) -> str:
        return self._nodes[index - 1][0]

    def GetToolsInNode(self, index: int) -> list[str]:
        return list(self._nodes[index - 1][1])


class FakeFusionComp(_FakeObject):
    KIND = "FusionComp"

    def __init__(self, behavior: FakeBehavior, name: str) -> None:
        super().__init__(behavior)
        self._name = name


class FakeFolder(_FakeObject):
    KIND = "Folder"


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
        self._grade = FakeGrade()
        self._comps: dict[str, str] = {}

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

    # grade / Fusion (STUDIO-T1) ---------------------------------------------
    def GetNodeGraph(self, layer: int = 1) -> FakeGraph | None:
        if not 1 <= layer <= len(self._grade.layers):
            return None
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        return FakeGraph(behavior, self._grade.layers[layer - 1])

    def GetVersionNameList(self, version_type: int) -> list[str]:
        return list(self._grade.versions) if version_type == 0 else []

    def GetCurrentVersion(self) -> dict[str, Any]:
        return {"versionName": self._grade.current_version, "versionType": 0}

    def GetFusionCompCount(self) -> int:
        return len(self._comps)

    def GetFusionCompNameList(self) -> list[str]:
        return list(self._comps)

    def ExportFusionComp(self, path: str, index: int) -> bool:
        names = list(self._comps)
        if not 1 <= index <= len(names):
            return False
        name = names[index - 1]
        Path(path).write_text(f"{name}\n{self._comps[name]}", encoding="utf-8")
        return True

    def ImportFusionComp(self, path: str) -> FakeFusionComp | None:
        try:
            name, content = Path(path).read_text(encoding="utf-8").split("\n", 1)
        except (OSError, ValueError):
            return None
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        unique = name
        serial = 1
        while unique in self._comps:
            serial += 1
            unique = f"{name} {serial}"
        self._comps[unique] = content
        return FakeFusionComp(behavior, unique)

    def CopyGrades(self, targets: list["FakeTimelineItem"]) -> bool:
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        if behavior.copy_grades_result is not None:
            return behavior.copy_grades_result
        chosen = targets[:1] if behavior.copy_grades_partial else targets
        for target in chosen:
            current = self._grade.layers[0]
            target._grade = FakeGrade(
                layers=(current, *target._grade.layers[1:]),
                versions=target._grade.versions,  # no version is created or copied
                current_version=target._grade.current_version,
            )
        return True

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
        self._track_names = {
            "video": [f"Video {n}" for n in range(1, len(video) + 1)],
            "audio": [f"Audio {n}" for n in range(1, len(audio) + 1)],
        }
        self._playhead = start_frame

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

    def GetTrackName(self, track_type: str, index: int) -> str:
        names = self._track_names.get(track_type, [])
        return names[index - 1] if 1 <= index <= len(names) else ""

    def SetTrackName(self, track_type: str, index: int, name: str) -> bool:
        names = self._track_names.get(track_type, [])
        if not 1 <= index <= len(names):
            return False
        names[index - 1] = name
        return True

    # playhead (STUDIO-T1 razor assist) ---------------------------------------
    def SetCurrentTimecode(self, timecode: str) -> bool:
        base = _TC_BASE.get(self._rate)
        parts = timecode.split(":")
        if base is None or len(parts) != 4 or not all(p.isdigit() for p in parts):
            return False
        hours, minutes, seconds, frames = (int(p) for p in parts)
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        self._playhead = ((hours * 60 + minutes) * 60 + seconds) * base + frames
        self._playhead += behavior.playhead_offset
        return True

    def GetCurrentTimecode(self) -> str:
        base = _TC_BASE[self._rate]
        seconds, frames = divmod(self._playhead, base)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

    def GetCurrentVideoItem(self) -> FakeTimelineItem | None:
        for track in reversed(self._tracks["video"]):
            for item in track:
                if item._start <= self._playhead < item._end:
                    return item
        return None

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

    def _split(self, track_type: str, index: int, frame: int) -> bool:
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
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
                right._grade = FakeGrade(
                    item._grade.layers, item._grade.versions, item._grade.current_version
                )
                right._comps = dict(item._comps)
                for key, info in list(item._markers.items()):
                    if key >= offset:
                        del item._markers[key]
                        right._markers[key - offset] = info
                item._end = frame
                track.insert(position + 1, right)
                return True
        return False

    def AieTestOnlySplitAt(self, track_type: str, index: int, frame: int) -> bool:
        """NOT a Resolve API. Present only when ``FakeBehavior.split_enabled``."""
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        if not behavior.split_enabled:
            raise AttributeError("AieTestOnlySplitAt")
        return self._split(track_type, index, frame)

    # test-only helpers (simulated editor actions; not allowlisted) ----------
    def _item(self, track_type: str, index: int, position: int) -> FakeTimelineItem:
        return self._tracks[track_type][index - 1][position]

    def _blade(self, track_type: str, index: int) -> bool:
        """The editor presses blade at the playhead on one track (a UI action)."""
        return self._split(track_type, index, self._playhead)

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


class FakeMediaPool(_FakeObject):
    KIND = "MediaPool"

    def __init__(self, behavior: FakeBehavior, project: "FakeProject") -> None:
        super().__init__(behavior)
        self._project = project
        self._root = FakeFolder(behavior)

    def GetRootFolder(self) -> FakeFolder:
        return self._root

    def ImportTimelineFromFile(
        self, path: str, options: dict[str, Any] | None = None
    ) -> FakeTimeline | None:
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        project = self._project
        if behavior.import_result_none:
            return None
        if behavior.import_returns_existing:
            return project._timelines[0]
        result = read_xmeml(Path(path).read_text(encoding="utf-8"))
        if result.timeline is None:
            return None
        name = result.timeline.name  # FCP7: the internal sequence name wins
        for existing in project._timelines:
            if existing._name == name:
                return existing  # documented quirk: the EXISTING timeline is returned
        timeline = project._build(result.timeline, colours=False)
        if behavior.import_extra_shift:
            for tracks in timeline._tracks.values():
                for track in tracks:
                    for item in track[1:]:
                        item._start += behavior.import_extra_shift
                        item._end += behavior.import_extra_shift
        project._timelines.append(timeline)
        return timeline


class FakeProject(_FakeObject):
    KIND = "Project"

    def __init__(self, behavior: FakeBehavior) -> None:
        super().__init__(behavior)
        self._timelines: list[FakeTimeline] = []
        self._current: FakeTimeline | None = None
        self._media: dict[str, FakeMediaPoolItem] = {}
        self._serial = 0
        self._pool = FakeMediaPool(behavior, self)

    def GetCurrentTimeline(self) -> FakeTimeline | None:
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        return None if behavior.no_current_timeline else self._current

    def GetTimelineCount(self) -> int:
        return len(self._timelines)

    def GetTimelineByIndex(self, index: int) -> FakeTimeline | None:
        return self._timelines[index - 1] if 1 <= index <= len(self._timelines) else None

    def SetCurrentTimeline(self, timeline: FakeTimeline) -> bool:
        if timeline not in self._timelines:
            return False
        self._current = timeline
        return True

    def GetMediaPool(self) -> FakeMediaPool:
        return self._pool

    def GetSetting(self, key: str) -> str:
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        return {"nodeStackLayers": behavior.node_stack_layers}.get(key, "")

    @property
    def timeline(self) -> FakeTimeline:
        """The ORIGINAL timeline (first built); not necessarily the current one."""
        return self._timelines[0]

    @property
    def current(self) -> FakeTimeline | None:
        return self._current

    def _build(self, timeline: TimelineStructure, *, colours: bool = True) -> FakeTimeline:
        behavior: FakeBehavior = object.__getattribute__(self, "_behavior")
        video: list[list[FakeTimelineItem]] = []
        audio: list[list[FakeTimelineItem]] = []
        for track in timeline.tracks:
            items: list[FakeTimelineItem] = []
            for start, clip in track.placements():
                ref = clip.media
                pool = self._media.get(ref.media_id)
                if pool is None:
                    frames = None if ref.available_range is None else ref.available_range.end
                    pool = FakeMediaPoolItem(
                        behavior,
                        ref.media_id,
                        ref.target_path,
                        frames,
                        ref.media_start_frame,
                        f"mpi-{len(self._media) + 1}",
                    )
                    self._media[ref.media_id] = pool
                self._serial += 1
                absolute = timeline.start_frame + start
                item = FakeTimelineItem(
                    behavior,
                    clip.name,
                    pool,
                    absolute,
                    absolute + clip.duration,
                    clip.source_range.start,
                    f"ti-{self._serial}",
                    clip.enabled,
                )
                _copy_markers(item, clip, colours)
                items.append(item)
            if track.kind is HandoffTrackKind.VIDEO:
                video.append(items)
            elif track.kind is HandoffTrackKind.AUDIO:
                audio.append(items)
            else:
                raise ValueError("Fake supports VIDEO and AUDIO tracks only")
        rate = _RATE_STRINGS[(timeline.rate.numerator, timeline.rate.denominator)]
        uid = f"fake-timeline-{len(self._timelines) + 1}"
        built = FakeTimeline(behavior, timeline.name, timeline.start_frame, rate, video, audio, uid)
        if behavior.import_keeps_track_names and self._timelines:
            for kind, names in self._timelines[0]._track_names.items():
                built._track_names[kind] = list(names)
        return built


def fake_project_from_handoff(
    timeline: TimelineStructure, behavior: FakeBehavior | None = None
) -> FakeProject:
    """Build the fake graph from a HandoffTimeline (markers included, colours mapped)."""
    behavior = FakeBehavior() if behavior is None else behavior
    project = FakeProject(behavior)
    built = project._build(timeline)
    project._timelines.append(built)
    project._current = built
    return project


def _copy_markers(item: FakeTimelineItem, clip: HandoffClip, colours: bool) -> None:
    for marker in clip.markers:
        offset = marker.frame_range.start - clip.source_range.start
        item._markers[float(offset)] = {
            "color": _COLOR_NAMES.get(marker.color.value, "Blue") if colours else "Blue",
            "duration": float(marker.frame_range.duration),
            "note": marker.note,
            "name": marker.name,
            "customData": "",
        }
