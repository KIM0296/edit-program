"""RT-001 strict FCP7 XML (xmeml v4/v5) reader for round-trip re-import.

Reads the subset HANDOFF-001 ``xmeml_writer`` produces plus common NLE-export
variations: ``sequence`` ``rate``/``timebase``/``ntsc``, sequence and file
``timecode``, ``media/video|audio/track/clipitem`` with
``start``/``end``/``in``/``out``, ``file`` definitions reused across clipitems
by ``<file id=…/>`` references (in any order), ``enabled`` and clip markers.

The idea of collecting ``file`` definitions by id across all clipitems before
resolving references is adapted from timeline (Chat Octopus)
``src/xmeml/reader.ts``, MIT License, see licenses/timeline-LICENSE.txt. Unlike
that reader, nothing is defaulted: a missing or non-whitelisted rate, a
missing sequence timecode, an undefined file reference or a conflicting file
definition is a refusal, never a guess.

Unsupported constructs (transitions, generators, nested sequences, speed
changes, filters, unknown clip/track children, transition-adjacent ``-1``
boundaries, overlapping clipitems, mixed-rate files) are reported as explicit
``UNSUPPORTED`` regions. The affected clips are *not* placed in the returned
model (their span becomes a gap) and the region is UNKNOWN; downstream diffing
must never classify content inside it.

LAYER-001: nothing on a track is dropped. Every track child that is not placed
as a modelled clip (the unsupported constructs above, every item of a disabled
or whole-UNKNOWN track, overlapped clipitems) is kept verbatim as a
``PassthroughItem`` on its ``HandoffTrack`` (canonical subtree, see
``layer_xml``), with its timeline extent when determinable. Track flags
(``enabled``/``locked``), track XML attributes and other track settings
children are kept on the track. Sequence-level markers, which the model cannot
carry, are listed in ``ReimportedTimeline.unpreserved``.

LAYER-001 follow-up: well-formed sequence-level markers are kept verbatim as
``ReimportedTimeline.markers`` (only a malformed one is ``unpreserved``);
``<link>`` groups among track items are read as ``link_group`` (canonical
``L1``, ``L2``, ... by document order); ``<sourcetrack>`` is read as
``HandoffClip.source_track`` (``audio:2``) and distinguishes the channels of
one stereo file.

Security: input is a ``str`` capped at ``max_chars``; any ``<!ENTITY``
declaration, DTD internal subset, external DOCTYPE identifier or DOCTYPE other
than the bare ``<!DOCTYPE xmeml>`` is refused before parsing (defusedxml-like
precautions implemented manually; stdlib only).

Evidence: a re-imported file is ``FILE_ROUNDTRIP`` evidence. It is never native
evidence and never VERIFIED_LIVE. The reader returns a ``ReimportedTimeline``
(Actual side), never the Expected ``HandoffTimeline``. FCP7 XML is the default
round-trip format (RT-001 decision 2).
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from .domain import FrameRange
from .handoff_model import (
    EVIDENCE_CLASS as _EVIDENCE_CLASS,
)
from .handoff_model import (
    HandoffClip,
    HandoffDiagnostic,
    HandoffDiagnosticCode,
    HandoffGap,
    HandoffItem,
    HandoffMarker,
    HandoffMediaRef,
    HandoffTrack,
    HandoffTrackKind,
    LayerItemKind,
    PassthroughItem,
    ReimportedTimeline,
    SequenceMarker,
    TimelineStructure,
    file_url_to_path,
    has_refusal,
    refusal,
    warning,
)
from .layer_xml import canonical_subtree, child_int, has_unparsed_markers, raw_markers
from .temporal_mapping import FrameRate
from .timecode import is_smpte_rate, parse_timecode

EVIDENCE_CLASS: Literal["FILE_ROUNDTRIP"] = _EVIDENCE_CLASS  # defined in handoff_model
DEFAULT_MAX_CHARS = 8 * 1024 * 1024
MAX_ELEMENTS = 200_000
SUPPORTED_VERSIONS = frozenset({"4", "5"})

_DOCTYPE_RE = re.compile(r"<!DOCTYPE", re.IGNORECASE)
_BARE_DOCTYPE_RE = re.compile(r"<!DOCTYPE\s+xmeml\s*>")
_ENTITY_RE = re.compile(r"<!ENTITY", re.IGNORECASE)
_INT_RE = re.compile(r"^-?\d+$")

# Clipitem children that carry no editorial timing we model and are ignored.
_BENIGN_CLIP_CHILDREN = frozenset(
    {
        "name",
        "enabled",
        "duration",
        "start",
        "end",
        "in",
        "out",
        "file",
        "marker",
        "rate",
        "masterclipid",
        "ismasterclip",
        "alphatype",
        "pixelaspectratio",
        "anamorphic",
        "link",
        "logginginfo",
        "colorinfo",
        "labels",
        "comments",
        "sourcetrack",
        "fielddominance",
        "compositemode",
        "itemhistory",
        "pproTicksIn",
        "pproTicksOut",
    }
)
_BENIGN_TRACK_CHILDREN = frozenset(
    {"enabled", "locked", "outputchannelindex", "MZ.TrackName", "TL.SQTrackShy"}
)
_TRACK_UNSUPPORTED = {
    "transitionitem": "TRANSITION",
    "generatoritem": "GENERATOR",
}


def _source_track(element: ET.Element) -> str | None:
    """FCP7 ``<sourcetrack>`` as ``mediatype:trackindex``; absent/malformed -> None."""
    source = element.find("sourcetrack")
    if source is None:
        return None
    media_type = (source.findtext("mediatype") or "").strip().lower()
    index = child_int(source, "trackindex")
    if media_type not in ("video", "audio") or index is None or index < 1:
        return None
    return f"{media_type}:{index}"


def _layer_kind(element: ET.Element) -> LayerItemKind:
    if element.tag == "generatoritem":
        return LayerItemKind.GENERATOR
    if element.tag == "transitionitem":
        return LayerItemKind.TRANSITION
    if element.tag != "clipitem":
        return LayerItemKind.UNKNOWN_ELEMENT
    if element.find("sequence") is not None:
        return LayerItemKind.NESTED_SEQUENCE
    filters = element.findall("filter")
    effects = {(f.findtext("effect/effectid") or "").strip().lower() for f in filters}
    if effects & {"timeremap", "speed"}:
        return LayerItemKind.RETIMED_CLIP
    values = [child_int(element, tag) for tag in ("start", "end", "in", "out")]
    start, end, source_in, source_out = values
    if (
        start is not None
        and end is not None
        and source_in is not None
        and source_out is not None
        and -1 not in values
        and source_out - source_in != end - start
    ):
        return LayerItemKind.RETIMED_CLIP
    if filters:
        return LayerItemKind.EFFECT_CLIP
    return LayerItemKind.UNMODELLED_CLIP


class UnsupportedConstruct(str, Enum):
    UNKNOWN = "UNKNOWN"
    TRANSITION = "TRANSITION"
    GENERATOR = "GENERATOR"
    NESTED_SEQUENCE = "NESTED_SEQUENCE"
    SPEED_CHANGE = "SPEED_CHANGE"
    FILTER = "FILTER"
    UNKNOWN_ELEMENT = "UNKNOWN_ELEMENT"
    TRANSITION_ADJACENT_BOUNDARY = "TRANSITION_ADJACENT_BOUNDARY"
    OVERLAPPING_CLIPS = "OVERLAPPING_CLIPS"
    MIXED_RATE = "MIXED_RATE"
    MISSING_FILE = "MISSING_FILE"
    MARKER_OUT_OF_RANGE = "MARKER_OUT_OF_RANGE"
    TRACK_DISABLED = "TRACK_DISABLED"
    INVALID_CLIP = "INVALID_CLIP"


@dataclass(frozen=True)
class TrackKey:
    """Track identity across Expected/Actual: kind + 1-based ordinal within the kind."""

    kind: HandoffTrackKind
    ordinal: int

    def __post_init__(self) -> None:
        if not isinstance(self.kind, HandoffTrackKind):
            raise TypeError("Track key requires a HandoffTrackKind")
        if type(self.ordinal) is not int or self.ordinal < 1:
            raise ValueError("Track ordinal must be a positive int")

    @property
    def label(self) -> str:
        return f"{self.kind.value}:{self.ordinal}"


def track_keys(timeline: TimelineStructure) -> tuple[tuple[TrackKey, HandoffTrack], ...]:
    counters: dict[HandoffTrackKind, int] = {}
    result: list[tuple[TrackKey, HandoffTrack]] = []
    for track in timeline.tracks:
        counters[track.kind] = counters.get(track.kind, 0) + 1
        result.append((TrackKey(track.kind, counters[track.kind]), track))
    return tuple(result)


@dataclass(frozen=True)
class UnknownRegion:
    """Actual-timeline region whose content is UNKNOWN. ``None`` range = whole track."""

    track: TrackKey
    frame_range: FrameRange | None
    construct: UnsupportedConstruct
    location: str
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.track, TrackKey):
            raise TypeError("Unknown region requires a TrackKey")
        if self.frame_range is not None and not isinstance(self.frame_range, FrameRange):
            raise TypeError("Unknown region range must be a FrameRange or None")
        if not isinstance(self.construct, UnsupportedConstruct):
            raise TypeError("Unknown construct type")
        if not isinstance(self.location, str) or not isinstance(self.message, str):
            raise TypeError("Location and message must be strings")


@dataclass(frozen=True)
class XmemlReadResult:
    timeline: ReimportedTimeline | None
    diagnostics: tuple[HandoffDiagnostic, ...]
    unknown_regions: tuple[UnknownRegion, ...] = ()
    evidence_class: Literal["FILE_ROUNDTRIP"] = EVIDENCE_CLASS

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        object.__setattr__(self, "unknown_regions", tuple(self.unknown_regions))
        if self.evidence_class != EVIDENCE_CLASS:
            raise ValueError("A re-imported xmeml file is FILE_ROUNDTRIP evidence only")
        if (self.timeline is None) != has_refusal(self.diagnostics):
            raise ValueError("A refused read has no timeline; a read timeline has no refusal")
        if self.timeline is None and self.unknown_regions:
            raise ValueError("A refused read carries no regions")
        if any(not isinstance(r, UnknownRegion) for r in self.unknown_regions):
            raise TypeError("Unknown regions must be UnknownRegion values")

    @property
    def refused(self) -> bool:
        return self.timeline is None

    @property
    def complete(self) -> bool:
        return self.timeline is not None and not self.unknown_regions


class _Refused(Exception):
    def __init__(self, diagnostic: HandoffDiagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


def _fail(code: HandoffDiagnosticCode, location: str, message: str) -> _Refused:
    return _Refused(refusal(code, location, message))


@dataclass(frozen=True)
class _FileDef:
    name: str | None
    path: str | None
    rate: FrameRate | None
    duration: int | None
    media_start: int | None


@dataclass(frozen=True)
class _Placed:
    start: int
    end: int
    clip: HandoffClip | None  # None = unsupported (region UNKNOWN, span becomes a gap)
    construct: UnsupportedConstruct | None = None


def _precheck(text: str, max_chars: int) -> None:
    if len(text) > max_chars:
        raise _fail(
            HandoffDiagnosticCode.INVALID_VALUE,
            "document",
            f"Input exceeds {max_chars} characters; refused before parsing",
        )
    if _ENTITY_RE.search(text):
        raise _fail(
            HandoffDiagnosticCode.UNSUPPORTED_FEATURE,
            "document",
            "ENTITY declarations are refused (entity expansion / XXE)",
        )
    doctypes = _DOCTYPE_RE.findall(text)
    if len(doctypes) > 1:
        raise _fail(HandoffDiagnosticCode.UNSUPPORTED_FEATURE, "document", "Multiple DOCTYPEs")
    if doctypes and not _BARE_DOCTYPE_RE.search(text):
        raise _fail(
            HandoffDiagnosticCode.UNSUPPORTED_FEATURE,
            "document",
            "Only the bare <!DOCTYPE xmeml> is accepted (no internal subset or external id)",
        )


def _int_text(element: ET.Element | None, location: str) -> int | None:
    if element is None:
        return None
    raw = (element.text or "").strip()
    if not _INT_RE.match(raw):
        raise _fail(HandoffDiagnosticCode.INVALID_VALUE, location, f"Not an integer: {raw!r}")
    return int(raw)


def _required_int(parent: ET.Element, tag: str, location: str) -> int:
    value = _int_text(parent.find(tag), f"{location}.{tag}")
    if value is None:
        raise _fail(HandoffDiagnosticCode.MALFORMED_DOCUMENT, location, f"Missing <{tag}>")
    return value


def _bool_text(element: ET.Element | None, location: str) -> bool | None:
    if element is None:
        return None
    raw = (element.text or "").strip().upper()
    if raw not in ("TRUE", "FALSE"):
        raise _fail(HandoffDiagnosticCode.INVALID_VALUE, location, f"Not TRUE/FALSE: {raw!r}")
    return raw == "TRUE"


def _rate(element: ET.Element | None, location: str) -> FrameRate | None:
    """``None`` = absent. Present but not whitelisted/incomplete -> refusal (UNKNOWN)."""
    if element is None:
        return None
    timebase = _int_text(element.find("timebase"), f"{location}.timebase")
    ntsc = _bool_text(element.find("ntsc"), f"{location}.ntsc")
    if timebase is None or ntsc is None or timebase <= 0:
        raise _fail(
            HandoffDiagnosticCode.UNKNOWN_RATE,
            location,
            "Rate needs timebase and ntsc; a missing ntsc flag is UNKNOWN, not defaulted",
        )
    rate = FrameRate(timebase * 1000, 1001) if ntsc else FrameRate(timebase, 1)
    if not is_smpte_rate(rate):
        raise _fail(HandoffDiagnosticCode.UNKNOWN_RATE, location, "Rate not whitelisted (UNKNOWN)")
    return rate


def _timecode_frame(element: ET.Element | None, rate: FrameRate, location: str) -> int | None:
    if element is None:
        return None
    tc_rate = _rate(element.find("rate"), f"{location}.rate")
    if tc_rate is not None and tc_rate != rate:
        raise _fail(HandoffDiagnosticCode.RATE_MISMATCH, location, "Timecode rate differs")
    frame = _int_text(element.find("frame"), f"{location}.frame")
    label = element.findtext("string")
    parsed: int | None = None
    if label is not None:
        try:
            parsed = parse_timecode(label.strip(), rate)[0]
        except ValueError as exc:
            raise _fail(HandoffDiagnosticCode.INVALID_VALUE, location, str(exc)) from exc
    if frame is not None and parsed is not None and frame != parsed:
        raise _fail(HandoffDiagnosticCode.INVALID_VALUE, location, "Timecode frame/string differ")
    value = frame if frame is not None else parsed
    if value is None or value < 0:
        raise _fail(HandoffDiagnosticCode.INVALID_VALUE, location, "Timecode without a value")
    return value


class _Reader:
    def __init__(self) -> None:
        self.diagnostics: list[HandoffDiagnostic] = []
        self.regions: list[UnknownRegion] = []
        self.files: dict[str, _FileDef] = {}
        self.file_elements: dict[str, ET.Element] = {}
        self.link_groups: dict[str, str] = {}
        self.rate: FrameRate = FrameRate(24, 1)

    # --- files --------------------------------------------------------------

    def file_def(self, element: ET.Element, location: str) -> _FileDef:
        url = element.findtext("pathurl")
        path = None if url is None or not url.strip() else file_url_to_path(url.strip())
        name = element.findtext("name")
        rate = _rate(element.find("rate"), f"{location}.rate")
        duration = _int_text(element.find("duration"), f"{location}.duration")
        media_start = _timecode_frame(
            element.find("timecode"), self.rate if rate is None else rate, f"{location}.timecode"
        )
        return _FileDef(
            None if name is None or not name.strip() else name.strip(),
            path,
            rate,
            duration,
            media_start,
        )

    def collect_files(self, sequence: ET.Element) -> None:
        for index, element in enumerate(sequence.iter("file")):
            file_id = element.get("id")
            if len(element) == 0:
                continue
            definition = self.file_def(element, f"file[{index}]")
            if file_id is None:
                continue
            previous = self.files.get(file_id)
            if previous is not None and previous != definition:
                raise _fail(
                    HandoffDiagnosticCode.MALFORMED_DOCUMENT,
                    f"file[{index}]",
                    f"Conflicting definitions for file id {file_id!r}",
                )
            self.files[file_id] = definition
            self.file_elements.setdefault(file_id, element)

    def collect_links(self, media: ET.Element) -> None:
        """FCP7 ``<link>`` groups among top-level track items -> canonical group names.

        Groups are the connected components of ``linkclipref`` references between
        existing item ids, named ``L1``, ``L2``, ... by document order; references
        to ids that do not exist are ignored and single-member groups get none.
        """
        items: list[ET.Element] = [
            child
            for section in ("video", "audio")
            for track in media.findall(f"{section}/track")
            for child in track
            if child.get("id")
        ]
        ids = [child.get("id") or "" for child in items]
        known = set(ids)
        parent = {item_id: item_id for item_id in ids}

        def find(item_id: str) -> str:
            while parent[item_id] != item_id:
                parent[item_id] = parent[parent[item_id]]
                item_id = parent[item_id]
            return item_id

        for item_id, child in zip(ids, items, strict=True):
            for ref in child.findall("link/linkclipref"):
                other = (ref.text or "").strip()
                if other in known and other != item_id:
                    parent[find(other)] = find(item_id)
        members: dict[str, list[str]] = {}
        for item_id in ids:
            members.setdefault(find(item_id), []).append(item_id)
        names: dict[str, str] = {}
        for item_id in ids:
            root = find(item_id)
            if len(members[root]) < 2:
                continue
            if root not in names:
                names[root] = f"L{len(names) + 1}"
            self.link_groups[item_id] = names[root]

    def resolve_file(self, element: ET.Element, location: str) -> _FileDef:
        file_id = element.get("id")
        if len(element) == 0:
            if file_id is None or file_id not in self.files:
                raise _fail(
                    HandoffDiagnosticCode.MALFORMED_DOCUMENT,
                    location,
                    f"File reference {file_id!r} has no definition",
                )
            return self.files[file_id]
        if file_id is not None:
            return self.files[file_id]
        return self.file_def(element, location)

    # --- regions ------------------------------------------------------------

    def unknown(
        self,
        key: TrackKey,
        frame_range: FrameRange | None,
        construct: UnsupportedConstruct,
        location: str,
        message: str,
    ) -> None:
        self.regions.append(UnknownRegion(key, frame_range, construct, location, message))
        self.diagnostics.append(
            warning(
                HandoffDiagnosticCode.UNSUPPORTED_FEATURE,
                location,
                f"UNSUPPORTED {construct.value}: {message}; region is UNKNOWN",
            )
        )

    @staticmethod
    def span(start: int | None, end: int | None) -> FrameRange | None:
        if start is None or end is None or start < 0 or end <= start:
            return None
        return FrameRange(start, end)

    # --- clipitems ----------------------------------------------------------

    def markers(
        self, element: ET.Element, source: FrameRange, location: str
    ) -> tuple[HandoffMarker, ...] | None:
        result: list[HandoffMarker] = []
        for index, marker in enumerate(element.findall("marker")):
            m_location = f"{location}.markers[{index}]"
            start = _required_int(marker, "in", m_location)
            end = _int_text(marker.find("out"), f"{m_location}.out")
            if end is None or end == -1:
                end = start + 1  # FCP7 point marker: out -1 / absent = one frame
            if start < 0 or end <= start:
                return None
            frame_range = FrameRange(start, end)
            if not source.contains(frame_range):
                return None
            result.append(
                HandoffMarker(
                    frame_range,
                    (marker.findtext("name") or "").strip(),
                    note=(marker.findtext("comment") or "").strip(),
                )
            )
        return tuple(result)

    def clipitem(self, element: ET.Element, key: TrackKey, location: str) -> _Placed | None:
        start = _int_text(element.find("start"), f"{location}.start")
        end = _int_text(element.find("end"), f"{location}.end")
        source_in = _int_text(element.find("in"), f"{location}.in")
        source_out = _int_text(element.find("out"), f"{location}.out")
        span = self.span(start, end)
        if start == -1 or end == -1 or span is None:
            self.unknown(
                key,
                None,
                UnsupportedConstruct.TRANSITION_ADJACENT_BOUNDARY,
                location,
                "Clip boundary is -1/missing (transition-determined); track position UNKNOWN",
            )
            return None
        unsupported: tuple[UnsupportedConstruct, str] | None = None
        for child in element:
            tag = child.tag
            if tag == "sequence":
                unsupported = (UnsupportedConstruct.NESTED_SEQUENCE, "Nested sequence")
            elif tag == "filter":
                effect = (child.findtext("effect/effectid") or "").strip().lower()
                if effect in ("timeremap", "speed"):
                    unsupported = (UnsupportedConstruct.SPEED_CHANGE, "Speed / time remap")
                else:
                    unsupported = (UnsupportedConstruct.FILTER, f"Filter {effect or '?'}")
            elif tag not in _BENIGN_CLIP_CHILDREN:
                unsupported = (UnsupportedConstruct.UNKNOWN_ELEMENT, f"Unknown <{tag}>")
            if unsupported is not None:
                break
        file_element = element.find("file")
        if unsupported is None and file_element is None:
            unsupported = (UnsupportedConstruct.MISSING_FILE, "Clipitem without a file")
        if unsupported is None and (source_in is None or source_out is None):
            unsupported = (UnsupportedConstruct.INVALID_CLIP, "Clipitem without in/out")
        if (
            unsupported is None
            and source_in is not None
            and source_out is not None
            and source_out - source_in != span.duration
        ):
            unsupported = (UnsupportedConstruct.SPEED_CHANGE, "Source and record durations differ")
        definition: _FileDef | None = None
        if unsupported is None and file_element is not None:
            definition = self.resolve_file(file_element, f"{location}.file")
            if definition.rate is not None and definition.rate != self.rate:
                unsupported = (UnsupportedConstruct.MIXED_RATE, "File rate differs from sequence")
            elif definition.path is None and definition.name is None:
                unsupported = (UnsupportedConstruct.MISSING_FILE, "File without name or pathurl")
        if unsupported is not None:
            self.unknown(key, span, unsupported[0], location, unsupported[1])
            return _Placed(span.start, span.end, None, unsupported[0])
        if definition is None or source_in is None or source_out is None:
            raise AssertionError("validated above")
        try:
            source = FrameRange(source_in, source_out)
        except ValueError:
            self.unknown(key, span, UnsupportedConstruct.INVALID_CLIP, location, "Bad in/out")
            return _Placed(span.start, span.end, None, UnsupportedConstruct.INVALID_CLIP)
        markers = self.markers(element, source, location)
        if markers is None:
            self.unknown(
                key,
                span,
                UnsupportedConstruct.MARKER_OUT_OF_RANGE,
                location,
                "Marker outside the clip source range or malformed; not dropped",
            )
            return _Placed(span.start, span.end, None, UnsupportedConstruct.MARKER_OUT_OF_RANGE)
        enabled_value = _bool_text(element.find("enabled"), f"{location}.enabled")
        if enabled_value is None:
            enabled_value = True
            self.diagnostics.append(
                warning(
                    HandoffDiagnosticCode.INVALID_VALUE,
                    f"{location}.enabled",
                    "No <enabled>; FCP7 DTD default TRUE applied",
                )
            )
        available = (
            None
            if definition.duration is None or definition.duration <= 0
            else FrameRange(0, definition.duration)
        )
        if available is not None and not available.contains(source):
            available = None
            self.diagnostics.append(
                warning(
                    HandoffDiagnosticCode.INVALID_VALUE,
                    f"{location}.file",
                    "File duration does not cover in/out; available range UNKNOWN",
                )
            )
        media_id = definition.name if definition.name is not None else definition.path
        if media_id is None:
            raise AssertionError("validated above")
        media = HandoffMediaRef(media_id, definition.path, available, definition.media_start)
        name = (element.findtext("name") or "").strip() or media_id
        clip = HandoffClip(
            name,
            media,
            source,
            enabled_value,
            markers,
            _source_track(element),
            self.link_groups.get(element.get("id") or ""),
        )
        return _Placed(span.start, span.end, clip)

    # --- tracks -------------------------------------------------------------

    def track(self, element: ET.Element, key: TrackKey, location: str) -> HandoffTrack:
        placed: list[_Placed] = []
        entries: list[tuple[ET.Element, _Placed | None]] = []
        extra: list[str] = []
        whole_unknown = False
        enabled = _bool_text(element.find("enabled"), f"{location}.enabled")
        locked = _bool_text(element.find("locked"), f"{location}.locked")
        if enabled is False:
            self.unknown(key, None, UnsupportedConstruct.TRACK_DISABLED, location, "Track disabled")
            whole_unknown = True
        for index, child in enumerate(element):
            c_location = f"{location}.{child.tag}[{index}]"
            if child.tag == "clipitem":
                result = self.clipitem(child, key, c_location)
                entries.append((child, result))
                if result is None:
                    whole_unknown = True
                else:
                    placed.append(result)
            elif child.tag in _TRACK_UNSUPPORTED:
                construct = UnsupportedConstruct(_TRACK_UNSUPPORTED[child.tag])
                start = _int_text(child.find("start"), f"{c_location}.start")
                end = _int_text(child.find("end"), f"{c_location}.end")
                span = self.span(start, end)
                self.unknown(key, span, construct, c_location, f"<{child.tag}>")
                if span is None:
                    whole_unknown = True
                    entries.append((child, None))
                else:
                    item = _Placed(span.start, span.end, None, construct)
                    placed.append(item)
                    entries.append((child, item))
            elif child.tag in ("enabled", "locked"):
                continue
            elif child.tag in _BENIGN_TRACK_CHILDREN:
                extra.append(canonical_subtree(child, {})[0])
            else:
                self.unknown(
                    key, None, UnsupportedConstruct.UNKNOWN_ELEMENT, c_location, "Unknown element"
                )
                whole_unknown = True
                entries.append((child, None))
        name = f"{'Video' if key.kind is HandoffTrackKind.VIDEO else 'Audio'} {key.ordinal}"
        items: tuple[HandoffItem, ...] = ()
        kept: set[int] = set()
        if not whole_unknown:
            items, kept = self.layout(placed, key, location)
        leftovers = [(child, p) for child, p in entries if p is None or id(p) not in kept]
        return HandoffTrack(
            name,
            key.kind,
            items,
            self.passthrough_items(leftovers, whole_unknown),
            enabled is not False,
            locked is True,
            tuple(sorted(element.attrib.items())),
            tuple(extra),
        )

    # --- LAYER-001 pass-through -------------------------------------------

    def passthrough_items(
        self, leftovers: list[tuple[ET.Element, _Placed | None]], whole_unknown: bool
    ) -> tuple[PassthroughItem, ...]:
        """Every track child not placed as a modelled clip, preserved verbatim."""
        extents = [self.extent(child) for child, _ in leftovers]
        result: list[PassthroughItem] = []
        for index, (child, placed) in enumerate(leftovers):
            extent = extents[index]
            raw = canonical_subtree(child, self.file_elements)[0]
            kind = _layer_kind(child)
            media_id = self.raw_media_id(child)
            overlapped = extent is None or any(
                other is None or other.overlaps(extent)
                for position, other in enumerate(extents)
                if position != index
            )
            source: FrameRange | None = None
            if (
                not whole_unknown
                and not overlapped
                and kind is LayerItemKind.EFFECT_CLIP
                and placed is not None
                and placed.construct is UnsupportedConstruct.FILTER
                and media_id is not None
            ):
                source = self.cuttable_source(child, raw)
            label = (child.findtext("name") or "").strip() or child.tag
            result.append(
                PassthroughItem(
                    kind,
                    label,
                    extent,
                    raw,
                    media_id,
                    source,
                    child.find("filter") is not None,
                    self.link_groups.get(child.get("id") or ""),
                )
            )
        return tuple(result)

    @staticmethod
    def extent(child: ET.Element) -> FrameRange | None:
        """Timeline extent; ``-1`` (transition-determined) edges derived from in/out."""
        start = child_int(child, "start")
        end = child_int(child, "end")
        source_in = child_int(child, "in")
        source_out = child_int(child, "out")
        length = (
            None
            if source_in is None or source_out is None or source_out <= source_in
            else source_out - source_in
        )
        if start == -1 and end is not None and end > 0 and length is not None:
            start = max(0, end - length)
        if end == -1 and start is not None and start >= 0 and length is not None:
            end = start + length
        if start is None or end is None or start < 0 or end <= start:
            return None
        return FrameRange(start, end)

    def raw_media_id(self, child: ET.Element) -> str | None:
        file_element = child.find("file")
        if child.tag != "clipitem" or file_element is None:
            return None
        try:
            definition = self.resolve_file(file_element, "passthrough.file")
        except _Refused:
            return None
        return definition.name if definition.name is not None else definition.path

    def cuttable_source(self, child: ET.Element, raw: str) -> FrameRange | None:
        """1:1 source range when the clipitem can be cut like a modelled clip."""
        for grandchild in child:
            if grandchild.tag == "filter":
                effect = (grandchild.findtext("effect/effectid") or "").strip().lower()
                if effect in ("timeremap", "speed"):
                    return None
            elif grandchild.tag not in _BENIGN_CLIP_CHILDREN:
                return None
        start, end = child_int(child, "start"), child_int(child, "end")
        source_in, source_out = child_int(child, "in"), child_int(child, "out")
        if start is None or end is None or source_in is None or source_out is None:
            return None
        if start < 0 or source_in < 0 or end <= start or source_out - source_in != end - start:
            return None
        file_element = child.find("file")
        if file_element is None:
            return None
        try:
            definition = self.resolve_file(file_element, "passthrough.file")
        except _Refused:
            return None
        if definition.rate is not None and definition.rate != self.rate:
            return None
        source = FrameRange(source_in, source_out)
        if has_unparsed_markers(raw) or any(
            not source.contains(frame_range) for frame_range, _ in raw_markers(raw)
        ):
            return None
        return source

    def layout(
        self, placed: list[_Placed], key: TrackKey, location: str
    ) -> tuple[tuple[HandoffItem, ...], set[int]]:
        """(items, ids of the placements kept as modelled clips)."""
        ordered = sorted(placed, key=lambda p: (p.start, p.end))
        # Overlapping placements cannot be represented; the overlapped content is UNKNOWN.
        resolved: list[_Placed] = []
        for item in ordered:
            if resolved and item.start < resolved[-1].end:
                previous = resolved.pop()
                merged = _Placed(previous.start, max(previous.end, item.end), None)
                if previous.clip is not None or item.clip is not None:
                    self.unknown(
                        key,
                        FrameRange(merged.start, merged.end),
                        UnsupportedConstruct.OVERLAPPING_CLIPS,
                        location,
                        "Overlapping placements on one track",
                    )
                resolved.append(merged)
            else:
                resolved.append(item)
        items: list[HandoffItem] = []
        cursor = 0
        for item in resolved:
            if item.start > cursor:
                items.append(HandoffGap(item.start - cursor))
            if item.clip is None:
                items.append(HandoffGap(item.end - item.start))
            else:
                items.append(item.clip)
            cursor = item.end
        # Trailing unsupported spans would be indistinguishable from nothing; drop the
        # trailing gaps (the region itself is recorded in ``unknown_regions`` and the
        # item is kept verbatim as a pass-through item).
        while items and isinstance(items[-1], HandoffGap):
            items.pop()
        return tuple(items), {id(p) for p in resolved if p.clip is not None}

    # --- document -----------------------------------------------------------

    def document(self, root: ET.Element) -> ReimportedTimeline:
        if root.tag != "xmeml":
            raise _fail(HandoffDiagnosticCode.MALFORMED_DOCUMENT, "document", "Root is not xmeml")
        version = root.get("version")
        if version not in SUPPORTED_VERSIONS:
            raise _fail(HandoffDiagnosticCode.UNKNOWN_SCHEMA, "xmeml", f"xmeml version {version!r}")
        children = list(root)
        sequences = [c for c in children if c.tag == "sequence"]
        others = [c.tag for c in children if c.tag != "sequence"]
        if others or len(sequences) != 1:
            raise _fail(
                HandoffDiagnosticCode.UNSUPPORTED_FEATURE,
                "xmeml",
                "Exactly one top-level <sequence> is supported (no project/bin/clip roots)",
            )
        sequence = sequences[0]
        rate = _rate(sequence.find("rate"), "sequence.rate")
        if rate is None:
            raise _fail(HandoffDiagnosticCode.UNKNOWN_RATE, "sequence", "No sequence rate")
        self.rate = rate
        start = _timecode_frame(sequence.find("timecode"), rate, "sequence.timecode")
        if start is None:
            raise _fail(
                HandoffDiagnosticCode.INVALID_VALUE,
                "sequence.timecode",
                "No sequence timecode; start frame UNKNOWN (not assumed 0)",
            )
        self.collect_files(sequence)
        media = sequence.find("media")
        if media is None:
            raise _fail(HandoffDiagnosticCode.MALFORMED_DOCUMENT, "sequence", "No <media>")
        self.collect_links(media)
        tracks: list[HandoffTrack] = []
        for section_tag, kind in (
            ("video", HandoffTrackKind.VIDEO),
            ("audio", HandoffTrackKind.AUDIO),
        ):
            section = media.find(section_tag)
            if section is None:
                continue
            for index, track in enumerate(section.findall("track")):
                key = TrackKey(kind, index + 1)
                tracks.append(self.track(track, key, f"{section_tag}.track[{index}]"))
        unpreserved: list[str] = []
        sequence_markers: list[SequenceMarker] = []
        for marker_index, marker in enumerate(sequence.findall("marker")):
            name = (marker.findtext("name") or "").strip()
            m_start = child_int(marker, "in")
            m_end = child_int(marker, "out")
            if m_end is None or m_end == -1:
                m_end = None if m_start is None else m_start + 1
            if m_start is None or m_end is None or m_start < 0 or m_end <= m_start:
                self.diagnostics.append(
                    warning(
                        HandoffDiagnosticCode.UNSUPPORTED_FEATURE,
                        f"sequence.markers[{marker_index}]",
                        "Malformed sequence-level marker; listed as unpreserved",
                    )
                )
                unpreserved.append(f"malformed sequence marker {name!r}")
                continue
            raw = canonical_subtree(marker, {})[0]
            sequence_markers.append(SequenceMarker(FrameRange(m_start, m_end), name, raw))
        raw_name = (sequence.findtext("name") or "").strip()
        if not raw_name:
            raw_name = "UNNAMED_SEQUENCE"
            self.diagnostics.append(
                warning(HandoffDiagnosticCode.INVALID_VALUE, "sequence.name", "No sequence name")
            )
        return ReimportedTimeline(
            raw_name,
            rate,
            start,
            tuple(tracks),
            unpreserved=tuple(unpreserved),
            markers=tuple(sequence_markers),
        )


def read_xmeml(text: str, *, max_chars: int = DEFAULT_MAX_CHARS) -> XmemlReadResult:
    """Strictly read a re-imported xmeml file. Refusals carry no timeline."""
    if not isinstance(text, str):
        raise TypeError("xmeml input must be a string")
    if type(max_chars) is not int or max_chars <= 0:
        raise ValueError("max_chars must be a positive int")
    reader = _Reader()
    try:
        _precheck(text, max_chars)
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise _fail(
                HandoffDiagnosticCode.MALFORMED_DOCUMENT, "document", f"Invalid XML: {exc}"
            ) from exc
        if sum(1 for _ in root.iter()) > MAX_ELEMENTS:
            raise _fail(HandoffDiagnosticCode.INVALID_VALUE, "document", "Too many elements")
        timeline = reader.document(root)
    except _Refused as refused:
        return XmemlReadResult(None, (*reader.diagnostics, refused.diagnostic))
    return XmemlReadResult(timeline, tuple(reader.diagnostics), tuple(reader.regions))
