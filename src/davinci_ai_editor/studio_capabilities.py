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

STUDIO-T1 (tiered apply) adds the evidence for the four tiers: importing the
shared Expected as a NEW version timeline (``ImportTimelineFromFile`` and its
measured naming quirks), the structural grade read used for tier selection,
grade / Fusion transfer (``CopyGrades`` replaces wholesale and creates no
version; other layers and versions are NOT_AVAILABLE; keyframes UNVERIFIED),
the razor-assist playhead (``SetCurrentTimecode``) and the undocumented
split/trim surface of Blackmagic's own MCP server (UNVERIFIED). Additional
read-only sources: ``OSS_PYI`` (typed stubs) and three OSS reference notes.
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
OSS_PYI = "OSS davinci-resolve-mcp docs/reference/DaVinciResolveScript.pyi (typed stubs)"
OSS_API_COVERAGE = "OSS davinci-resolve-mcp docs/reference/api-coverage.md"
OSS_LUT_CONTROLS = "OSS davinci-resolve-mcp docs/reference/lut-file-controls.md"
OSS_TYPED_API_SEARCH = "OSS davinci-resolve-mcp docs/reference/typed-api-search.md"


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
    # STUDIO-T1 tiered apply
    NEW_VERSION_IMPORT = "NEW_VERSION_IMPORT"
    GRADE_READ = "GRADE_READ"
    GRADE_TRANSFER = "GRADE_TRANSFER"
    RAZOR_ASSIST = "RAZOR_ASSIST"
    NATIVE_MCP = "NATIVE_MCP"


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
    # STUDIO-T1 tier 1/2: import a new timeline version inside Resolve
    IMPORT_TIMELINE_FROM_FILE = "IMPORT_TIMELINE_FROM_FILE"
    IMPORT_NAME_AUTHORITY = "IMPORT_NAME_AUTHORITY"
    IMPORT_TRACK_NAMES_PRESERVED = "IMPORT_TRACK_NAMES_PRESERVED"
    IMPORT_MEDIA_RELINK_EXACT = "IMPORT_MEDIA_RELINK_EXACT"
    IMPORT_MARKER_COLOR_AND_CUSTOM_DATA = "IMPORT_MARKER_COLOR_AND_CUSTOM_DATA"
    LIST_PROJECT_TIMELINES = "LIST_PROJECT_TIMELINES"
    SET_CURRENT_TIMELINE = "SET_CURRENT_TIMELINE"
    MEDIA_POOL_ROOT_FOLDER = "MEDIA_POOL_ROOT_FOLDER"
    READ_TRACK_NAME = "READ_TRACK_NAME"
    SET_TRACK_NAME = "SET_TRACK_NAME"
    # STUDIO-T1 grade state read (tier selection)
    READ_GRADE_GRAPH = "READ_GRADE_GRAPH"
    READ_GRADE_VERSIONS = "READ_GRADE_VERSIONS"
    READ_FUSION_COMPS = "READ_FUSION_COMPS"
    READ_NODE_STACK_LAYERS = "READ_NODE_STACK_LAYERS"
    GRADE_ABSENCE_INFERENCE = "GRADE_ABSENCE_INFERENCE"
    # STUDIO-T1 tier 2: grade / Fusion transfer to the new items
    GRADE_COPY_GRADES = "GRADE_COPY_GRADES"
    GRADE_COPY_ACROSS_TIMELINES = "GRADE_COPY_ACROSS_TIMELINES"
    GRADE_COPY_ALL_LAYERS = "GRADE_COPY_ALL_LAYERS"
    GRADE_COPY_VERSIONS = "GRADE_COPY_VERSIONS"
    GRADE_COPY_KEYFRAMES = "GRADE_COPY_KEYFRAMES"
    GRADE_STRUCTURE_FINGERPRINT = "GRADE_STRUCTURE_FINGERPRINT"
    GRADE_APPLY_DRX = "GRADE_APPLY_DRX"
    GRADE_APPLY_FROM_STILL = "GRADE_APPLY_FROM_STILL"
    GRADE_EXPORT_LUT = "GRADE_EXPORT_LUT"
    GRADE_ADD_VERSION = "GRADE_ADD_VERSION"
    FUSION_COMP_EXPORT = "FUSION_COMP_EXPORT"
    FUSION_COMP_IMPORT = "FUSION_COMP_IMPORT"
    FUSION_COMP_ADD = "FUSION_COMP_ADD"
    FUSION_COMP_TIME_ALIGNMENT = "FUSION_COMP_TIME_ALIGNMENT"
    # STUDIO-T1 tier 4: razor assist (the editor presses blade)
    PLAYHEAD_SET_TIMECODE = "PLAYHEAD_SET_TIMECODE"
    PLAYHEAD_GET_TIMECODE = "PLAYHEAD_GET_TIMECODE"
    TIMECODE_STRING_FORMAT = "TIMECODE_STRING_FORMAT"
    READ_CURRENT_VIDEO_ITEM = "READ_CURRENT_VIDEO_ITEM"
    # STUDIO-T1 Blackmagic's own (21.1) MCP server
    NATIVE_MCP_SPLIT_TRIM_TOOLS = "NATIVE_MCP_SPLIT_TRIM_TOOLS"


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
        "T0 view: as part of a REBUILD it is still not preserving (only the current "
        "node-stack layer grade; Fusion, audio and other versions are not covered). The "
        "STUDIO-T1 tier-2 use and its measured traps are recorded as GRADE_COPY_GRADES.",
        False,
    ),
    CapabilityEntry(
        _C.DUPLICATE_TIMELINE,
        _A.CUT_REBUILD,
        "Timeline.DuplicateTimeline(name) -> Timeline",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, _truth("Timeline.DuplicateTimeline")),
        "OSS measured on Studio 21.1.0.14 (reconfirmed 2026-09-13): returns the copy but "
        "SILENTLY moves the project's current-timeline pointer to it, so later mutations land "
        "in the copy. Not used: tiers 1/2 import a NEW timeline and leave the original "
        "untouched as the backup. If ever used: capture GetCurrentTimeline() first and "
        "SetCurrentTimeline() back, checking the bool.",
        False,
    ),
    # ------------------------------------------- STUDIO-T1 tier 1/2: new version import
    CapabilityEntry(
        _C.IMPORT_TIMELINE_FROM_FILE,
        _A.NEW_VERSION_IMPORT,
        "MediaPool.ImportTimelineFromFile(filePath, {timelineName, importSourceClips, "
        "sourceClipsPath, sourceClipsFolders, interlaceProcessing}) -> Timeline",
        _S.DOCUMENTED_CLAIM,
        "README all versions; OSS measured on Studio 19.1.3.7 / 21.0.4.5",
        (
            OSS_README,
            OSS_PYI,
            _truth("MediaPool.ImportTimelineFromFile"),
            _truth("Timeline.Export / ImportTimelineFromFile (format fidelity)"),
        ),
        "Creates a NEW timeline from AAF/EDL/XML/FCPXML/DRT/ADL/OTIO. Returns None with no "
        "error when the requested timelineName already exists. FCP7 XML keeps the cut and the "
        "tracks frame-exact and relinks when media moved; the OSS-recommended repeatable loop "
        "is FCP7 XML + a unique name + importSourceClips=False + sourceClipsFolders=[root]. "
        "OTIO does not relink from the pool; DRT ignores importOptions. Tiers 1/2 use FCP7 XML.",
        True,
    ),
    CapabilityEntry(
        _C.IMPORT_NAME_AUTHORITY,
        _A.NEW_VERSION_IMPORT,
        "Which name the imported timeline gets, and whether a NEW timeline is returned",
        _S.UNVERIFIED,
        "OSS measured on Studio 21.0.4.5 (issue #171) and 19.1.3.7",
        (
            _truth(
                "MediaPool.ImportTimelineFromFile (internal sequence name overrides timelineName)"
            ),
            _truth("MediaPool.ImportTimelineFromFile"),
        ),
        "FCP7 XML IGNORES timelineName: the internal <sequence><name> wins, and when it "
        "matches an existing timeline the call returns that EXISTING timeline (no error). A "
        "repeated timelineName returns None. The transport writes the unique name INTO the "
        "file, refuses a name that already exists before calling, and afterwards requires a "
        "timeline id absent from the pre-import set carrying the requested name; anything "
        "else is REFUSED/UNVERIFIED, never success.",
        True,
    ),
    CapabilityEntry(
        _C.IMPORT_TRACK_NAMES_PRESERVED,
        _A.NEW_VERSION_IMPORT,
        "Track names / order after an FCP7 XML import",
        _S.UNVERIFIED,
        _ALL,
        (OSS_README, _truth("Timeline.Export / ImportTimelineFromFile (format fidelity)")),
        "The OSS reports that FCP7 XML keeps the cut and the tracks; custom track NAMES are "
        "not documented either way. The read-back compares track count/kind/order and "
        "GetTrackName per track; a difference is restored with SetTrackName only when "
        "granted, otherwise MISMATCH. Layers are never merged.",
        True,
    ),
    CapabilityEntry(
        _C.IMPORT_MEDIA_RELINK_EXACT,
        _A.NEW_VERSION_IMPORT,
        "Imported items link to the same media pool clips",
        _S.UNVERIFIED,
        "OSS measured on Studio 19.1.3.7",
        (
            _truth(
                "Timeline import MERGES pool media by a coarse identity - similar files can "
                "silently cross-link"
            ),
        ),
        "Pool media are merged by a coarse identity across imports and similar files can "
        "cross-link silently. The read-back compares media name and file path per item "
        "(VER-001); 'linked == total' is not trusted.",
        True,
    ),
    CapabilityEntry(
        _C.IMPORT_MARKER_COLOR_AND_CUSTOM_DATA,
        _A.NEW_VERSION_IMPORT,
        "Marker colour and customData through an FCP7 XML import",
        _S.NOT_AVAILABLE,
        _ALL,
        (OSS_README, REPO_READ_MAP),
        "FCP7 xmeml markers carry no colour and no customData (APPLY-001 limits). Remaining "
        "candidate markers on the new version keep their NAME only; the read-back compares "
        "markers without colour (documented format loss), and marker removal by customData "
        "is UNSUPPORTED on the imported version.",
        False,
    ),
    CapabilityEntry(
        _C.LIST_PROJECT_TIMELINES,
        _A.NEW_VERSION_IMPORT,
        "Project.GetTimelineCount() -> int; Project.GetTimelineByIndex(idx) -> Timeline",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Pre-import name/id set (collision refusal and the new-id check).",
        True,
    ),
    CapabilityEntry(
        _C.SET_CURRENT_TIMELINE,
        _A.NEW_VERSION_IMPORT,
        "Project.SetCurrentTimeline(timeline) -> bool",
        _S.DOCUMENTED_CLAIM,
        "README all versions; OSS measured on Studio 21.1.0.14",
        (OSS_README, _truth("Timeline.DuplicateTimeline")),
        "Opens the new version for the editor after a MATCH read-back; verified by the "
        "GetCurrentTimeline id. Optional: without the grant the editor opens it by hand.",
        True,
    ),
    CapabilityEntry(
        _C.MEDIA_POOL_ROOT_FOLDER,
        _A.NEW_VERSION_IMPORT,
        "Project.GetMediaPool() -> MediaPool; MediaPool.GetRootFolder() -> Folder",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, _truth("MediaPool.ImportTimelineFromFile")),
        "sourceClipsFolders=[root] with importSourceClips=False (no duplicated pool media).",
        True,
    ),
    CapabilityEntry(
        _C.READ_TRACK_NAME,
        _A.NEW_VERSION_IMPORT,
        "Timeline.GetTrackName(trackType, trackIndex) -> str",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Layer-preservation read-back on both timelines.",
        True,
    ),
    CapabilityEntry(
        _C.SET_TRACK_NAME,
        _A.NEW_VERSION_IMPORT,
        "Timeline.SetTrackName(trackType, trackIndex, name) -> bool",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Only on the NEW timeline, only to restore the original names; re-read afterwards.",
        True,
    ),
    # ------------------------------------------------------ STUDIO-T1 grade state read
    CapabilityEntry(
        _C.READ_GRADE_GRAPH,
        _A.GRADE_READ,
        "TimelineItem.GetNodeGraph(layerIdx) -> Graph; Graph.GetNumNodes(), "
        "GetNodeLabel(i), GetToolsInNode(i)",
        _S.DOCUMENTED_CLAIM,
        "README all versions; OSS: read side answers on the Edit page (19.1.3.7)",
        (
            OSS_README,
            _truth("TimelineItem.AddVersion / Graph.ApplyGradeFromDRX (page-dependent)"),
        ),
        "Structural only (node count, labels, tool lists), never grade values.",
        True,
    ),
    CapabilityEntry(
        _C.READ_GRADE_VERSIONS,
        _A.GRADE_READ,
        "TimelineItem.GetVersionNameList(versionType) -> [names]; GetCurrentVersion() -> "
        "{versionName, versionType}",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, _truth("TimelineItem.CopyGrades")),
        "More than one local version means GRADED, and the other versions are not "
        "transferable (GRADE_COPY_VERSIONS).",
        True,
    ),
    CapabilityEntry(
        _C.READ_FUSION_COMPS,
        _A.GRADE_READ,
        "TimelineItem.GetFusionCompCount() -> int; GetFusionCompNameList() -> [names]",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Any comp counts as work a re-import would lose (GRADED for tier selection).",
        True,
    ),
    CapabilityEntry(
        _C.READ_NODE_STACK_LAYERS,
        _A.GRADE_READ,
        "Project.GetSetting('nodeStackLayers') -> str",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Named in the GetNodeGraph bound. More than one layer makes CopyGrades partial "
        "(GRADE_COPY_ALL_LAYERS). Parsed strictly (digits only).",
        True,
    ),
    CapabilityEntry(
        _C.GRADE_ABSENCE_INFERENCE,
        _A.GRADE_READ,
        "'one node, no tools, one version, no comps' implies 'not graded'",
        _S.UNVERIFIED,
        _ALL,
        (OSS_README,),
        "Not documented: a primary correction inside the single default node may not show "
        "in GetToolsInNode. Without this grant the grade state is UNKNOWN (never UNGRADED), "
        "and the planner asks the user (NEEDS_USER_CHOICE) instead of picking tier 1.",
        True,
    ),
    # ------------------------------------------- STUDIO-T1 tier 2: grade / comp transfer
    CapabilityEntry(
        _C.GRADE_COPY_GRADES,
        _A.GRADE_TRANSFER,
        "TimelineItem.CopyGrades([tgtTimelineItems]) -> bool",
        _S.DOCUMENTED_CLAIM,
        "README all versions; OSS measured on Studio 21.1.0.14 (reconfirmed 2026-09-13)",
        (OSS_README, OSS_PYI, _truth("TimelineItem.CopyGrades")),
        "Copies the CURRENT node-stack layer grade to the same layer of each target. "
        "Measured: REPLACES the target grade wholesale (no merge), returns True, and creates "
        "NO version (GetVersionNameList unchanged), so an overwritten target grade cannot be "
        "recovered. Tier 2 targets only freshly imported items whose graph is checked to be "
        "the default before the call.",
        True,
    ),
    CapabilityEntry(
        _C.GRADE_COPY_ACROSS_TIMELINES,
        _A.GRADE_TRANSFER,
        "CopyGrades from an item on the backup timeline to items on the new timeline",
        _S.UNVERIFIED,
        _ALL,
        (OSS_README, _truth("TimelineItem.CopyGrades")),
        "The README does not say whether source and targets may sit on different timelines; "
        "the OSS measurement was within one timeline. Tier 2 requires this grant.",
        True,
    ),
    CapabilityEntry(
        _C.GRADE_COPY_ALL_LAYERS,
        _A.GRADE_TRANSFER,
        "(none) copy every node-stack layer / choose the current layer",
        _S.NOT_AVAILABLE,
        _ALL,
        (OSS_README,),
        "CopyGrades copies the current layer only, and no call selects the current layer. "
        "With nodeStackLayers > 1 the transfer cannot be complete, so tier 2 is not offered "
        "(tier 4 keeps the graded items in place).",
        False,
    ),
    CapabilityEntry(
        _C.GRADE_COPY_VERSIONS,
        _A.GRADE_TRANSFER,
        "(none) copy colour versions other than the current one",
        _S.NOT_AVAILABLE,
        "OSS measured on Studio 21.1.0.14",
        (OSS_README, _truth("TimelineItem.CopyGrades")),
        "CopyGrades copies the current grade and creates no version; other local/remote "
        "versions are not transferred. An item with more than one version blocks tier 2.",
        False,
    ),
    CapabilityEntry(
        _C.GRADE_COPY_KEYFRAMES,
        _A.GRADE_TRANSFER,
        "Whether CopyGrades carries node keyframes, and how they align on a later piece",
        _S.UNVERIFIED,
        _ALL,
        (OSS_README, _truth("TimelineItem.CopyGrades")),
        "Not documented. The OSS compared exported (static) LUTs, which cannot show "
        "keyframes. Tier-2 grade VALUES therefore stay UNVERIFIED even when the structural "
        "fingerprint matches.",
        False,
    ),
    CapabilityEntry(
        _C.GRADE_STRUCTURE_FINGERPRINT,
        _A.GRADE_TRANSFER,
        "Fingerprint = current-layer node count, labels, tools per node, Fusion comp names",
        _S.UNVERIFIED,
        _ALL,
        (OSS_README,),
        "Per-item read-back evidence for tier 2 (MATCH / MISMATCH / UNVERIFIED). Equal "
        "structure does not prove equal values; a value check needs a page-gated ExportLUT "
        "comparison (GRADE_EXPORT_LUT), left to TASK-020.",
        True,
    ),
    CapabilityEntry(
        _C.GRADE_APPLY_DRX,
        _A.GRADE_TRANSFER,
        "Graph.ApplyGradeFromDRX(path, gradeMode 0|1|2) -> bool",
        _S.DOCUMENTED_CLAIM,
        "README all versions; OSS measured on 19.1.3 / Studio 19.1.3.7",
        (
            OSS_README,
            _truth("Graph.ApplyGradeFromDRX (node layout preserved on same-structure apply)"),
            _truth("TimelineItem.AddVersion / Graph.ApplyGradeFromDRX (page-dependent)"),
        ),
        "gradeMode 1 = source-timecode aligned (the keyframe-preserving candidate for a later "
        "piece). Returns False on the Edit page with no signal and needs a .drx still "
        "(GrabStill + GalleryStillAlbum.ExportStills, Gallery panel visible). Not used in T1.",
        False,
    ),
    CapabilityEntry(
        _C.GRADE_APPLY_FROM_STILL,
        _A.GRADE_TRANSFER,
        "(none) TimelineItem.ApplyGradeFromStill",
        _S.NOT_AVAILABLE,
        "OSS measured on Studio 21.1.0.14",
        (_truth("TimelineItem.ApplyGradeFromStill"), OSS_PYI),
        "Does not exist (AttributeError); Graph.ApplyGradeFromDRX is the documented call.",
        False,
    ),
    CapabilityEntry(
        _C.GRADE_EXPORT_LUT,
        _A.GRADE_TRANSFER,
        "TimelineItem.ExportLUT(exportType, path) -> bool",
        _S.DOCUMENTED_CLAIM,
        "OSS measured on Studio 21.1.0.14 (reconfirmed 2026-09-13)",
        (OSS_README, _truth("TimelineItem.ExportLUT")),
        "Color page only (a bare False elsewhere, no file written). A static LUT: usable as "
        "a value-level read-back of a transferred grade, never as the transfer. Not used in T1.",
        False,
    ),
    CapabilityEntry(
        _C.GRADE_ADD_VERSION,
        _A.GRADE_TRANSFER,
        "TimelineItem.AddVersion(versionName, versionType) -> bool",
        _S.DOCUMENTED_CLAIM,
        "OSS measured on Studio 19.1.3.7",
        (
            OSS_README,
            _truth("TimelineItem.AddVersion / Graph.ApplyGradeFromDRX (page-dependent)"),
        ),
        "Color page only. Not needed in T1: the targets are fresh items with nothing to keep.",
        False,
    ),
    CapabilityEntry(
        _C.FUSION_COMP_EXPORT,
        _A.GRADE_TRANSFER,
        "TimelineItem.ExportFusionComp(path, compIndex) -> bool",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, OSS_PYI),
        "Exports comp N of the original item to a work file.",
        True,
    ),
    CapabilityEntry(
        _C.FUSION_COMP_IMPORT,
        _A.GRADE_TRANSFER,
        "TimelineItem.ImportFusionComp(path) -> fusionComp",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, OSS_PYI),
        "Creates and adds a new comp on each new piece; None is a failure.",
        True,
    ),
    CapabilityEntry(
        _C.FUSION_COMP_ADD,
        _A.GRADE_TRANSFER,
        "TimelineItem.AddFusionComp() -> fusionComp",
        _S.DOCUMENTED_CLAIM,
        "OSS measured on Studio 19.1.3.7 / 21.0.x",
        (OSS_README, _truth("TimelineItem.AddFusionComp / LoadFusionCompByName")),
        "An API-created comp renders only when MediaOut has a path from MediaIn, and values "
        "written under a comp lock read back but never render. Not used (import is used).",
        False,
    ),
    CapabilityEntry(
        _C.FUSION_COMP_TIME_ALIGNMENT,
        _A.GRADE_TRANSFER,
        "Comp animation timing on a piece that starts later in the source",
        _S.UNVERIFIED,
        _ALL,
        (OSS_README,),
        "Not documented whether an imported comp's keyframes follow source or item time; "
        "comp transfer values stay UNVERIFIED.",
        False,
    ),
    # ------------------------------------------------ STUDIO-T1 tier 4: razor assist
    CapabilityEntry(
        _C.PLAYHEAD_SET_TIMECODE,
        _A.RAZOR_ASSIST,
        "Timeline.SetCurrentTimecode(timecode) -> bool",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README, OSS_PYI),
        "Moves the playhead on the Cut, Edit, Color, Fairlight and Deliver pages. Read back "
        "with GetCurrentTimecode; a mismatch stops the assist (no retry).",
        True,
    ),
    CapabilityEntry(
        _C.PLAYHEAD_GET_TIMECODE,
        _A.RAZOR_ASSIST,
        "Timeline.GetCurrentTimecode() -> str",
        _S.DOCUMENTED_CLAIM,
        _ALL,
        (OSS_README,),
        "Playhead read-back after SetCurrentTimecode.",
        True,
    ),
    CapabilityEntry(
        _C.TIMECODE_STRING_FORMAT,
        _A.RAZOR_ASSIST,
        "Timecode string accepted by SetCurrentTimecode ('HH:MM:SS:FF'; drop-frame ';')",
        _S.UNVERIFIED,
        _ALL,
        (OSS_README,),
        "The string format is not specified. The transport emits non-drop 'HH:MM:SS:FF' for "
        "integer and 23.976 rates and refuses 29.97/59.94 (drop-frame setting unknown).",
        True,
    ),
    CapabilityEntry(
        _C.READ_CURRENT_VIDEO_ITEM,
        _A.RAZOR_ASSIST,
        "Timeline.GetCurrentVideoItem() -> TimelineItem",
        _S.DOCUMENTED_CLAIM,
        "README all versions; OSS observed it on the Color page (19.1.3.7)",
        (
            OSS_README,
            OSS_PYI,
            _truth("Timeline.GetCurrentClipThumbnailImage (foreground only)"),
        ),
        "Which track's item is 'current' is not documented. Not used for any decision; the "
        "post-razor timeline read is the only evidence.",
        False,
    ),
    # ------------------------------------------------- native MCP (Blackmagic's own)
    CapabilityEntry(
        _C.NATIVE_MCP_SPLIT_TRIM_TOOLS,
        _A.NATIVE_MCP,
        "Blackmagic's own (21.1) MCP server: split / trim / razor tools",
        _S.UNVERIFIED,
        "21.1 (as referenced by the OSS)",
        (OSS_API_COVERAGE, OSS_LUT_CONTROLS, OSS_TYPED_API_SEARCH, OSS_CHANGELOG_21_1),
        "The OSS references Blackmagic's own MCP only for list_luts / generate_lut / "
        "delete_lut and search_scripting_api. No source in hand lists a split or trim tool "
        "or documents the server's edition (Studio-only) status, and the 21.1 scripting "
        "changelog adds no split call. Check on a real Studio (TASK-020) before relying on it.",
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
