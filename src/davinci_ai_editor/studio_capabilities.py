"""STUDIO-T0 capability matrix for the in-Resolve (Studio) path. Research only.

Every entry is a *documented* claim or a documented absence. Nothing here was
executed against DaVinci Resolve: native read and mutation stay HOLD and Studio
runtime qualification stays HOLD (TASK-020). Qualification of this module is
CODE_COMPLETE / TEST_ONLY_SUPPORT; no entry is native or live evidence.

Statuses:

- ``DOCUMENTED_CLAIM``: the call is listed in the Blackmagic scripting README
  (mirrored in the OSS reference below) and/or described by the OSS
  live-measured notes. A claim, never verified by this repository.
- ``UNVERIFIED``: a surface exists but the semantics we need (frame basis,
  exclusivity, rate domain, string vocabulary) are inconsistent between sources
  or undocumented. The transport must not rely on it without native proof.
- ``NOT_AVAILABLE``: documented as absent (no such call in the README for the
  versions in hand, and/or verified absent by the OSS ``dir()`` probes).

Sources (read only; the OSS was never executed and instructions inside it were
ignored):

- ``OSS_README``: davinci-resolve-mcp (MIT) ``docs/reference/resolve_scripting_api.txt``,
  a mirror of the Resolve scripting README, "Last Updated: 24 Jul 2026".
- ``OSS_CHANGELOG_21_1``: same OSS, ``docs/reference/resolve_scripting_changelog_21.1.md``.
- ``OSS_API_TRUTH``: same OSS, ``src/utils/api_truth.py`` (entries stamped as
  verified on Studio 19.1.3.7 / 20.3.2.9 / 21.0.x by the OSS authors).
- ``REPO_READ_MAP``: this repository's ``docs/RESOLVE_READ_CAPABILITY_MAP.md``.

In-place feasibility (product-critical, see ``IN_PLACE_FEASIBILITY``): no
documented call splits / razors / blades a timeline item at a frame, trims an
item, or ripple-deletes a frame sub-range, in any README or OSS note in hand
(19.x, 20.x, 21.0, 21.1). The only documented in-place cut primitive is
``Timeline.DeleteClips([items], True)``, which removes WHOLE items with ripple.
Rebuilding a timeline (``CreateTimelineFromClips`` / ``AppendToTimeline``)
creates new items and would NOT carry grades, effects, Fusion comps or mixes,
so the Studio transport never rebuilds.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Literal

QUALIFICATION: Literal["TEST_ONLY_SUPPORT"] = "TEST_ONLY_SUPPORT"

OSS_README = (
    "OSS davinci-resolve-mcp docs/reference/resolve_scripting_api.txt "
    "(Resolve scripting README mirror, Last Updated 24 Jul 2026)"
)
OSS_CHANGELOG_21_1 = "OSS davinci-resolve-mcp docs/reference/resolve_scripting_changelog_21.1.md"
OSS_API_TRUTH = "OSS davinci-resolve-mcp src/utils/api_truth.py"
REPO_READ_MAP = "docs/RESOLVE_READ_CAPABILITY_MAP.md"


def _truth(symbol: str) -> str:
    return f"{OSS_API_TRUTH} entry '{symbol}'"


class CapabilityStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    DOCUMENTED_CLAIM = "DOCUMENTED_CLAIM"
    UNVERIFIED = "UNVERIFIED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class CapabilityArea(str, Enum):
    UNKNOWN = "UNKNOWN"
    TIMELINE_READ = "TIMELINE_READ"
    MARKER_MUTATION = "MARKER_MUTATION"
    CUT_IN_PLACE = "CUT_IN_PLACE"
    CUT_REBUILD = "CUT_REBUILD"
    DETECTION = "DETECTION"


class StudioCapability(str, Enum):
    UNKNOWN = "UNKNOWN"
    # (a) timeline read
    READ_CURRENT_TIMELINE = "READ_CURRENT_TIMELINE"
    READ_TIMELINE_NAME = "READ_TIMELINE_NAME"
    READ_TIMELINE_START_FRAME = "READ_TIMELINE_START_FRAME"
    READ_TIMELINE_END_FRAME_EXCLUSIVE = "READ_TIMELINE_END_FRAME_EXCLUSIVE"
    READ_FRAME_RATE = "READ_FRAME_RATE"
    READ_TRACK_COUNT = "READ_TRACK_COUNT"
    READ_TRACK_ITEMS = "READ_TRACK_ITEMS"
    READ_ITEM_START = "READ_ITEM_START"
    READ_ITEM_END_EXCLUSIVE = "READ_ITEM_END_EXCLUSIVE"
    READ_ITEM_LEFT_OFFSET = "READ_ITEM_LEFT_OFFSET"
    READ_ITEM_SOURCE_START_FRAME = "READ_ITEM_SOURCE_START_FRAME"
    READ_ITEM_SOURCE_END_FRAME = "READ_ITEM_SOURCE_END_FRAME"
    READ_ITEM_NAME = "READ_ITEM_NAME"
    READ_ITEM_ENABLED = "READ_ITEM_ENABLED"
    READ_ITEM_UNIQUE_ID = "READ_ITEM_UNIQUE_ID"
    READ_ITEM_MEDIA_POOL_ITEM = "READ_ITEM_MEDIA_POOL_ITEM"
    READ_MEDIA_NAME = "READ_MEDIA_NAME"
    READ_MEDIA_PATH = "READ_MEDIA_PATH"
    READ_MEDIA_FRAMES_AND_START = "READ_MEDIA_FRAMES_AND_START"
    READ_ITEM_MARKERS = "READ_ITEM_MARKERS"
    ITEM_MARKER_FRAME_BASIS = "ITEM_MARKER_FRAME_BASIS"
    READ_TIMELINE_MARKERS = "READ_TIMELINE_MARKERS"
    READ_ITEM_LINKED = "READ_ITEM_LINKED"
    # (b) markers
    MARKER_ADD_ITEM = "MARKER_ADD_ITEM"
    MARKER_DELETE_ITEM_BY_CUSTOM_DATA = "MARKER_DELETE_ITEM_BY_CUSTOM_DATA"
    MARKER_DELETE_ITEM_AT_FRAME = "MARKER_DELETE_ITEM_AT_FRAME"
    MARKER_UPDATE_CUSTOM_DATA = "MARKER_UPDATE_CUSTOM_DATA"
    MARKER_UPDATE_NAME_COLOR_NOTE = "MARKER_UPDATE_NAME_COLOR_NOTE"
    # (c) cuts in place
    SPLIT_ITEM_AT_FRAME = "SPLIT_ITEM_AT_FRAME"
    TRIM_ITEM = "TRIM_ITEM"
    DELETE_SUBRANGE_RIPPLE = "DELETE_SUBRANGE_RIPPLE"
    DELETE_ITEMS_RIPPLE = "DELETE_ITEMS_RIPPLE"
    RIPPLE_SPAN_SEMANTICS = "RIPPLE_SPAN_SEMANTICS"
    DETECT_SCENE_CUTS = "DETECT_SCENE_CUTS"
    TRACK_SELECTIVE_RIPPLE = "TRACK_SELECTIVE_RIPPLE"
    TRACK_LOCK_READ = "TRACK_LOCK_READ"
    TRACK_LOCK_SET = "TRACK_LOCK_SET"
    TRACK_LOCK_EXCLUDES_RIPPLE = "TRACK_LOCK_EXCLUDES_RIPPLE"
    DELETE_TRACK = "DELETE_TRACK"
    # (c) cuts by rebuilding (never used by the transport)
    REBUILD_CREATE_TIMELINE_FROM_CLIPS = "REBUILD_CREATE_TIMELINE_FROM_CLIPS"
    REBUILD_APPEND_TO_TIMELINE = "REBUILD_APPEND_TO_TIMELINE"
    REBUILD_COPY_GRADES = "REBUILD_COPY_GRADES"
    DUPLICATE_TIMELINE = "DUPLICATE_TIMELINE"
    # detection
    HASATTR_DETECTION = "HASATTR_DETECTION"


@dataclass(frozen=True)
class CapabilityEntry:
    capability: StudioCapability
    area: CapabilityArea
    api_surface: str
    status: CapabilityStatus
    versions: str
    sources: tuple[str, ...]
    notes: str
    used_by_transport: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))
        if not isinstance(self.capability, StudioCapability) or not isinstance(
            self.area, CapabilityArea
        ):
            raise TypeError("Typed capability and area required")
        if not isinstance(self.status, CapabilityStatus):
            raise TypeError("Typed capability status required")
        if self.capability is StudioCapability.UNKNOWN or self.area is CapabilityArea.UNKNOWN:
            raise ValueError("Matrix entries name a concrete capability and area")
        if not self.sources or any(not isinstance(s, str) or not s.strip() for s in self.sources):
            raise ValueError("Every capability entry cites at least one source")
        if type(self.used_by_transport) is not bool:
            raise TypeError("used_by_transport must be a bool")


_A = CapabilityArea
_C = StudioCapability
_S = CapabilityStatus
_ALL = "19.x / 20.x / 21.0 / 21.1 (README in hand)"

STUDIO_CAPABILITY_MATRIX: tuple[CapabilityEntry, ...] = (
    # ---------------------------------------------------------------- (a) read
    CapabilityEntry(
        _C.READ_CURRENT_TIMELINE,
        _A.TIMELINE_READ,
        "Project.GetCurrentTimeline() -> Timeline",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "May return None when no timeline is open; None stays None (read UNVERIFIED).",
        True,
    ),
    CapabilityEntry(
        _C.READ_TIMELINE_NAME,
        _A.TIMELINE_READ,
        "Timeline.GetName() -> str",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "Descriptive only, never identity.",
        True,
    ),
    CapabilityEntry(
        _C.READ_TIMELINE_START_FRAME,
        _A.TIMELINE_READ,
        "Timeline.GetStartFrame() -> int",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (
            OSS_README,
            REPO_READ_MAP,
            _truth("MediaPool.AppendToTimeline clipInfo recordFrame (timeline-absolute origin)"),
        ),
        "Absolute frame (01:00:00:00 -> 86400 at 24 fps). TimelineItem.GetStart/GetEnd are "
        "absolute too, so timeline-relative = GetStart() - GetStartFrame().",
        True,
    ),
    CapabilityEntry(
        _C.READ_TIMELINE_END_FRAME_EXCLUSIVE,
        _A.TIMELINE_READ,
        "Timeline.GetEndFrame() -> int",
        _S.DOCUMENTED_CLAIM,
        "measured on Studio 19.1.3.7 by the OSS",
        (OSS_README, _truth("Timeline.GetEndFrame (exclusive bound)")),
        "EXCLUSIVE (one past the last frame). Used only as a cross-check against the last "
        "item end; disagreement makes the read UNVERIFIED.",
        True,
    ),
    CapabilityEntry(
        _C.READ_FRAME_RATE,
        _A.TIMELINE_READ,
        "Timeline.GetSetting('timelineFrameRate') -> str",
        _S.UNVERIFIED,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "Getter documented; the exact string vocabulary ('23.976' vs '23.98', drop-frame "
        "spelling) is not. The transport maps an explicit whitelist; anything else is UNKNOWN.",
        True,
    ),
    CapabilityEntry(
        _C.READ_TRACK_COUNT,
        _A.TIMELINE_READ,
        "Timeline.GetTrackCount('video'|'audio') -> int",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "Track index is a locator, not persistent identity.",
        True,
    ),
    CapabilityEntry(
        _C.READ_TRACK_ITEMS,
        _A.TIMELINE_READ,
        "Timeline.GetItemListInTrack(trackType, index) -> [TimelineItem]",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "List order is not documented; the transport orders by GetStart().",
        True,
    ),
    CapabilityEntry(
        _C.READ_ITEM_START,
        _A.TIMELINE_READ,
        "TimelineItem.GetStart(subframe_precision=False) -> int",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "Absolute timeline frame.",
        True,
    ),
    CapabilityEntry(
        _C.READ_ITEM_END_EXCLUSIVE,
        _A.TIMELINE_READ,
        "TimelineItem.GetEnd(subframe_precision=False) -> int",
        _S.DOCUMENTED_CLAIM,
        "measured on Studio 19.1.3.7 by the OSS",
        (OSS_README, _truth("Timeline.GetEndFrame (exclusive bound)")),
        "EXCLUSIVE: an item occupies [GetStart(), GetEnd()).",
        True,
    ),
    CapabilityEntry(
        _C.READ_ITEM_LEFT_OFFSET,
        _A.TIMELINE_READ,
        "TimelineItem.GetLeftOffset(subframe_precision=False) -> int",
        _S.DOCUMENTED_CLAIM,
        "measured on 21.0 by the OSS",
        (OSS_README, _truth("TimelineItem.GetSourceStartFrame")),
        "Media-relative source start; exact at 100% speed. WARPED by speed (position/speed) "
        "and on audio items advances at the timeline rate. The transport assumes 100% speed "
        "and same-rate media (retime/mixed rate are out of scope, as in HANDOFF-001).",
        True,
    ),
    CapabilityEntry(
        _C.READ_ITEM_SOURCE_START_FRAME,
        _A.TIMELINE_READ,
        "TimelineItem.GetSourceStartFrame() -> int",
        _S.UNVERIFIED,
        "measured on 21.0 by the OSS",
        (OSS_README, _truth("TimelineItem.GetSourceStartFrame"), REPO_READ_MAP),
        "Reads one frame off on some items. Recorded as a diagnostic cross-check only.",
        True,
    ),
    CapabilityEntry(
        _C.READ_ITEM_SOURCE_END_FRAME,
        _A.TIMELINE_READ,
        "TimelineItem.GetSourceEndFrame() -> int",
        _S.UNVERIFIED,
        "measured on Studio 19.1.3.7 by the OSS",
        (
            OSS_README,
            _truth(
                "TimelineItem.GetSourceStartFrame on an AUDIO item (media-rate frames; "
                "a WAV freezes the PROJECT rate at import)"
            ),
        ),
        "EXCLUSIVE when source rate == timeline rate, INCLUSIVE when they differ. Not used; "
        "source end = left offset + record duration.",
        False,
    ),
    CapabilityEntry(
        _C.READ_ITEM_NAME,
        _A.TIMELINE_READ,
        "TimelineItem.GetName() -> str",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Descriptive only.",
        True,
    ),
    CapabilityEntry(
        _C.READ_ITEM_ENABLED,
        _A.TIMELINE_READ,
        "TimelineItem.GetClipEnabled() -> bool",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "Non-bool is UNKNOWN, never coerced.",
        True,
    ),
    CapabilityEntry(
        _C.READ_ITEM_UNIQUE_ID,
        _A.TIMELINE_READ,
        "TimelineItem.GetUniqueId() -> str",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "Readable; lifetime across split/delete/reload is unverified (OPEN-001/006/012). "
        "Recorded in the raw read only; never used as identity.",
        True,
    ),
    CapabilityEntry(
        _C.READ_ITEM_MEDIA_POOL_ITEM,
        _A.TIMELINE_READ,
        "TimelineItem.GetMediaPoolItem() -> MediaPoolItem | None",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "'if one exists': generators/titles have none; the read is then UNVERIFIED.",
        True,
    ),
    CapabilityEntry(
        _C.READ_MEDIA_NAME,
        _A.TIMELINE_READ,
        "MediaPoolItem.GetName() -> str",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Used as the media display name, the same identity basis as FCP7 xmeml "
        "(DISPLAY_NAME + path, WEAK at best).",
        True,
    ),
    CapabilityEntry(
        _C.READ_MEDIA_PATH,
        _A.TIMELINE_READ,
        "MediaPoolItem.GetClipProperty('File Path') -> str",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "Getter documented; key spelling must be qualified natively. Empty/None = UNKNOWN.",
        True,
    ),
    CapabilityEntry(
        _C.READ_MEDIA_FRAMES_AND_START,
        _A.TIMELINE_READ,
        "MediaPoolItem.GetClipProperty('Frames' | 'Start') -> str",
        _S.UNVERIFIED,
        "observed on Studio 19.1.3.7 by the OSS",
        (OSS_README, _truth("Timeline.GetEndFrame (exclusive bound)")),
        "String values; 'Frames' observed as a count and 'End' as inclusive. Parsed strictly "
        "(digits only); otherwise UNKNOWN (None) and never defaulted to 0.",
        True,
    ),
    CapabilityEntry(
        _C.READ_ITEM_MARKERS,
        _A.TIMELINE_READ,
        "TimelineItem.GetMarkers() -> {frameId: {color, duration, note, name, customData}}",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "frameId and duration are floats in the README example (96.0); only integral values "
        "are accepted.",
        True,
    ),
    CapabilityEntry(
        _C.ITEM_MARKER_FRAME_BASIS,
        _A.TIMELINE_READ,
        "TimelineItem marker frameId basis",
        _S.UNVERIFIED,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "README says 'clip offset 96'. Whether that offset counts from the item's visible "
        "start (left edge) or from the media start is not stated. The transport only reads "
        "item markers when a profile grants the ITEM_START_RELATIVE interpretation.",
        True,
    ),
    CapabilityEntry(
        _C.READ_TIMELINE_MARKERS,
        _A.TIMELINE_READ,
        "Timeline.GetMarkers() -> {frameId: {...}}",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (
            OSS_README,
            _truth("MediaPool.AppendToTimeline clipInfo recordFrame (timeline-absolute origin)"),
        ),
        "Timeline marker frameIds are timeline-relative (frame 0 = first frame). Counted in "
        "the raw read; not modelled (as sequence markers in the xmeml reader).",
        True,
    ),
    CapabilityEntry(
        _C.READ_ITEM_LINKED,
        _A.TIMELINE_READ,
        "TimelineItem.GetLinkedItems() -> [TimelineItem]",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "Descriptive relation only; not read in T0.",
        False,
    ),
    # ------------------------------------------------------------- (b) markers
    CapabilityEntry(
        _C.MARKER_ADD_ITEM,
        _A.MARKER_MUTATION,
        "TimelineItem.AddMarker(frameId, color, name, note, duration, customData) -> bool",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Candidate markers go on the anchor item (Video 1), mirroring the file path. "
        "customData carries the candidate token.",
        True,
    ),
    CapabilityEntry(
        _C.MARKER_DELETE_ITEM_BY_CUSTOM_DATA,
        _A.MARKER_MUTATION,
        "TimelineItem.DeleteMarkerByCustomData(customData) -> bool",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Deletes the first matching marker only.",
        True,
    ),
    CapabilityEntry(
        _C.MARKER_DELETE_ITEM_AT_FRAME,
        _A.MARKER_MUTATION,
        "TimelineItem.DeleteMarkerAtFrame(frameNum) -> bool",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Not used in T0 (custom data is the safer key).",
        False,
    ),
    CapabilityEntry(
        _C.MARKER_UPDATE_CUSTOM_DATA,
        _A.MARKER_MUTATION,
        "TimelineItem.UpdateMarkerCustomData(frameId, customData) -> bool",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Updates customData only.",
        False,
    ),
    CapabilityEntry(
        _C.MARKER_UPDATE_NAME_COLOR_NOTE,
        _A.MARKER_MUTATION,
        "(none) marker name/color/note setter",
        _S.NOT_AVAILABLE,
        _ALL,
        (OSS_README,),
        "No marker rename/recolor API is documented: an update is delete + add. The editor "
        "renames markers in the UI (the approval channel); the transport never renames.",
        False,
    ),
    # --------------------------------------------------------- (c) in place
    CapabilityEntry(
        _C.SPLIT_ITEM_AT_FRAME,
        _A.CUT_IN_PLACE,
        "(none) razor / blade / split a TimelineItem at a frame",
        _S.NOT_AVAILABLE,
        _ALL,
        (
            _truth("Razor / blade / split a timeline item"),
            OSS_README,
            OSS_CHANGELOG_21_1,
        ),
        "Verified absent on Timeline and TimelineItem (dir(), 21.0.0) by the OSS; no split "
        "call in the README Timeline/TimelineItem sections (Jul 2026) nor in the 21.1 "
        "changelog. No 19.x/20.x source documents one either. In-place apply of a cut that "
        "falls inside an item is therefore UNSUPPORTED (routed to the file path).",
        True,
    ),
    CapabilityEntry(
        _C.TRIM_ITEM,
        _A.CUT_IN_PLACE,
        "(none) TimelineItem SetStart / SetEnd / SetLeftOffset / SetRightOffset",
        _S.NOT_AVAILABLE,
        "verified via dir() on 21.0.0 by the OSS",
        (_truth("TimelineItem trim / move / re-time (no position setters)"), OSS_README),
        "Getters only: no trim, slip, slide, roll or move.",
        False,
    ),
    CapabilityEntry(
        _C.DELETE_SUBRANGE_RIPPLE,
        _A.CUT_IN_PLACE,
        "(none) ripple-delete a frame range / marked in-out range",
        _S.NOT_AVAILABLE,
        _ALL,
        (OSS_README, _truth("Insert / Overwrite / Replace / Fit-to-Fill edit modes")),
        "Timeline.SetMarkInOut exists but no call deletes the marked range; no edit-mode API.",
        False,
    ),
    CapabilityEntry(
        _C.DELETE_ITEMS_RIPPLE,
        _A.CUT_IN_PLACE,
        "Timeline.DeleteClips([timelineItems], ripple=True) -> bool",
        _S.DOCUMENTED_CLAIM,
        "README all versions; OSS measured on Studio 21.0",
        (
            OSS_README,
            _truth("Timeline.DeleteClips (requires the Edit page; flaky first attempt)"),
            _truth("Timeline.DeleteClips (linked audio not deleted)"),
        ),
        "Deletes WHOLE items. Requires the Edit page (False otherwise); a False return is "
        "advisory; linked audio is NOT deleted implicitly (pass video and audio items "
        "together). The transport calls it once per cut, never retries, and verifies by "
        "read-back.",
        True,
    ),
    CapabilityEntry(
        _C.RIPPLE_SPAN_SEMANTICS,
        _A.CUT_IN_PLACE,
        "DeleteClips ripple: which tracks shift, by how much",
        _S.UNVERIFIED,
        _ALL,
        (OSS_README,),
        "README says only 'performing ripple delete'. Whether all tracks shift by the "
        "deleted span (sync-preserving) is not documented. The fake models span ripple across "
        "all tracks; post-mutation read-back is the only acceptance signal.",
        True,
    ),
    CapabilityEntry(
        _C.TRACK_SELECTIVE_RIPPLE,
        _A.CUT_IN_PLACE,
        "(none) ripple/shift items on chosen tracks only",
        _S.NOT_AVAILABLE,
        _ALL,
        (OSS_README, _truth("Insert / Overwrite / Replace / Fit-to-Fill edit modes")),
        "DeleteClips takes items and a ripple flag only: no track list, no auto-track-selector "
        "or sync-lock parameter, and no call moves an item (TRIM_ITEM). A per-track policy "
        "KEEP_IN_PLACE (later items on that track must not move) therefore cannot be expressed "
        "in place; the transport returns UNSUPPORTED (file path) for it. SHIFT_WITH_RIPPLE is "
        "only what DeleteClips' (UNVERIFIED) span ripple does to the other tracks.",
        True,
    ),
    CapabilityEntry(
        _C.TRACK_LOCK_READ,
        _A.CUT_IN_PLACE,
        "Timeline.GetIsTrackLocked(trackType, index) -> bool",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "Readable lock state; input for native qualification, not read in T0.",
        False,
    ),
    CapabilityEntry(
        _C.TRACK_LOCK_SET,
        _A.CUT_IN_PLACE,
        "Timeline.SetTrackLock(trackType, index, bool) -> bool",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Documented setter. Not allowlisted in T0: the transport never changes track state.",
        False,
    ),
    CapabilityEntry(
        _C.TRACK_LOCK_EXCLUDES_RIPPLE,
        _A.CUT_IN_PLACE,
        "Effect of a locked track on DeleteClips(ripple=True)",
        _S.UNVERIFIED,
        _ALL,
        (
            OSS_README,
            _truth("Timeline.DeleteClips (requires the Edit page; flaky first attempt)"),
        ),
        "Not documented whether a locked track is skipped by the ripple shift (as in the UI) "
        "or makes the call fail; the OSS only records that lock state was clear during its "
        "DeleteClips measurement. Must be probed natively before any lock-based KEEP_IN_PLACE.",
        False,
    ),
    CapabilityEntry(
        _C.DELETE_TRACK,
        _A.CUT_IN_PLACE,
        "Timeline.DeleteTrack(trackType, index) -> bool",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Never used: tracks/layers are never deleted, merged or flattened before final render.",
        False,
    ),
    CapabilityEntry(
        _C.DETECT_SCENE_CUTS,
        _A.CUT_IN_PLACE,
        "Timeline.DetectSceneCuts() -> bool",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Cuts at detected scene changes only; cannot target a chosen frame. Not usable for "
        "applying approved cuts.",
        False,
    ),
    # --------------------------------------------------------- (c) rebuild
    CapabilityEntry(
        _C.REBUILD_CREATE_TIMELINE_FROM_CLIPS,
        _A.CUT_REBUILD,
        "MediaPool.CreateTimelineFromClips(name, [clipInfo]) -> Timeline",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, _truth("MediaPool.CreateTimelineFromClips")),
        "Builds a NEW timeline (clipInfo has no track field). Grades, effects, Fusion comps, "
        "mixes of the current timeline are not carried. Never used by the transport.",
        False,
    ),
    CapabilityEntry(
        _C.REBUILD_APPEND_TO_TIMELINE,
        _A.CUT_REBUILD,
        "MediaPool.AppendToTimeline([{mediaPoolItem, startFrame, endFrame, recordFrame, "
        "trackIndex, mediaType}]) -> [TimelineItem]",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (
            OSS_README,
            _truth("MediaPool.AppendToTimeline clipInfo endFrame (exclusive bound)"),
            _truth("MediaPool.AppendToTimeline (overlapping records — earlier item wins)"),
        ),
        "Creates NEW items (endFrame exclusive, recordFrame absolute, overlapping records "
        "silently dropped). New items carry no grade/effect. Never used by the transport.",
        False,
    ),
    CapabilityEntry(
        _C.REBUILD_COPY_GRADES,
        _A.CUT_REBUILD,
        "TimelineItem.CopyGrades([targets]) -> bool",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Copies only the current node-stack layer grade; effects, Fusion, audio and "
        "keyframes are not covered, so a rebuild plus CopyGrades is still not preserving.",
        False,
    ),
    CapabilityEntry(
        _C.DUPLICATE_TIMELINE,
        _A.CUT_REBUILD,
        "Timeline.DuplicateTimeline(name) -> Timeline",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Candidate pre-mutation backup for native qualification; not used in T0.",
        False,
    ),
    # --------------------------------------------------------------- detection
    CapabilityEntry(
        _C.HASATTR_DETECTION,
        _A.DETECTION,
        "hasattr()/getattr() capability probing on Resolve objects",
        _S.NOT_AVAILABLE,
        "measured on Studio 19.1.3.7 / 21.0.x by the OSS",
        (_truth("hasattr() / getattr() on Resolve API objects (attribute fabrication)"),),
        "hasattr() is constant True on Resolve objects. The transport uses an explicit "
        "allowlisted method table and declared capability grants instead.",
        False,
    ),
)

_BY_CAPABILITY: Mapping[StudioCapability, CapabilityEntry] = MappingProxyType(
    {entry.capability: entry for entry in STUDIO_CAPABILITY_MATRIX}
)
if len(_BY_CAPABILITY) != len(STUDIO_CAPABILITY_MATRIX):
    raise AssertionError("Duplicate capability entry")


def capability_entry(capability: StudioCapability) -> CapabilityEntry:
    if not isinstance(capability, StudioCapability):
        raise TypeError("Typed capability required")
    entry = _BY_CAPABILITY.get(capability)
    if entry is None:
        raise KeyError(capability.value)
    return entry


IN_PLACE_FEASIBILITY = (
    "No documented Resolve scripting call (19.x/20.x/21.0/21.1 sources in hand) splits a "
    "timeline item at a frame, trims an item, or ripple-deletes a frame sub-range "
    "(SPLIT_ITEM_AT_FRAME, TRIM_ITEM, DELETE_SUBRANGE_RIPPLE = NOT_AVAILABLE). The only "
    "documented in-place cut primitive is Timeline.DeleteClips([items], True), which removes "
    "WHOLE items with ripple (DOCUMENTED_CLAIM; ripple span semantics UNVERIFIED). In-place "
    "apply is therefore possible only when every approved cut coincides with item boundaries "
    "on every affected track; any other cut is UNSUPPORTED in place and routed to the file "
    "path (APPLY-001 FCP7 XML). Rebuilding with CreateTimelineFromClips/AppendToTimeline would "
    "drop grades, effects, Fusion comps and mixes, so the transport never rebuilds."
)


# --- runtime grants (what one transport instance may call) ---------------------------


class CapabilityGrant(str, Enum):
    """Per-runtime permission to use a capability. No NATIVE grant exists (HOLD)."""

    UNKNOWN = "UNKNOWN"
    ABSENT = "ABSENT"
    GRANTED_TEST_ONLY = "GRANTED_TEST_ONLY"


class ItemMarkerBasis(str, Enum):
    UNKNOWN = "UNKNOWN"
    ITEM_START_RELATIVE = "ITEM_START_RELATIVE"


@dataclass(frozen=True)
class StudioCapabilityProfile:
    """Declared grants for one transport instance (fake object graph only).

    A grant is a declaration, never discovered with ``hasattr``. Missing entries
    are UNKNOWN. ``GRANTED_TEST_ONLY`` is the only positive grant: native grants
    require TASK-020 qualification and do not exist in this code base.
    """

    grants: Mapping[StudioCapability, CapabilityGrant] = field(
        default_factory=lambda: MappingProxyType({})
    )
    item_marker_basis: ItemMarkerBasis = ItemMarkerBasis.UNKNOWN
    qualification: Literal["TEST_ONLY_SUPPORT"] = QUALIFICATION

    def __post_init__(self) -> None:
        grants = dict(self.grants)
        for key, value in grants.items():
            if not isinstance(key, StudioCapability) or not isinstance(value, CapabilityGrant):
                raise TypeError("Typed capability grants required")
        if not isinstance(self.item_marker_basis, ItemMarkerBasis):
            raise TypeError("Typed item marker basis required")
        if self.qualification != QUALIFICATION:
            raise ValueError("Studio profiles are TEST_ONLY_SUPPORT (native HOLD)")
        object.__setattr__(self, "grants", MappingProxyType(grants))

    def grant(self, capability: StudioCapability) -> CapabilityGrant:
        if not isinstance(capability, StudioCapability):
            raise TypeError("Typed capability required")
        return self.grants.get(capability, CapabilityGrant.UNKNOWN)


def documented_profile() -> StudioCapabilityProfile:
    """Grants implied by the research alone: NOT_AVAILABLE -> ABSENT, all else UNKNOWN.

    Nothing is granted: documentation is not qualification. A transport built on
    this profile refuses every read and mutation (UNVERIFIED / UNSUPPORTED).
    """
    return StudioCapabilityProfile(
        {
            entry.capability: CapabilityGrant.ABSENT
            for entry in STUDIO_CAPABILITY_MATRIX
            if entry.status is CapabilityStatus.NOT_AVAILABLE
        }
    )
