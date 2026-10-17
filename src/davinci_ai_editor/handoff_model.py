"""HANDOFF-001 neutral model for file-based NLE handoff artifacts.

A handoff value describes an *Expected* timeline. It is an artifact only: it
never proves the Actual NLE state, and importing a written file into Resolve
(``ImportTimelineFromFile``) is a native mutation that stays HOLD / manual user
action. Every value therefore carries ``artifact_kind`` =
``EXPECTED_TIMELINE_ARTIFACT`` and ``authorizes_import`` = ``False``.

Coordinates:
- Timeline item placement is sequential (clips and explicit gaps), frame 0 is
  the timeline start; ``start_frame`` is the declared global start label.
- ``source_range`` / ``available_range`` / clip marker ranges are
  media-relative frames (0 = first media frame) at the timeline rate.
  ``media_start_frame`` is the media's absolute start frame, or ``None`` when
  UNKNOWN; UNKNOWN is never replaced by 0.
- Mixed-rate media is out of scope: all frames are at the timeline rate.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal
from urllib.parse import unquote, urlsplit

from .domain import FrameRange, TimelineSnapshot, TrackType
from .temporal_mapping import FrameRate
from .timecode import is_smpte_rate

ARTIFACT_KIND: Literal["EXPECTED_TIMELINE_ARTIFACT"] = "EXPECTED_TIMELINE_ARTIFACT"
EVIDENCE_CLASS: Literal["FILE_ROUNDTRIP"] = "FILE_ROUNDTRIP"
# INT-002 (STUDIO-T1 request): non-file evidence class for a getter-only Studio API
# read. Never native evidence; today only produced from the in-repo fake object graph,
# so its qualification is TEST_ONLY_SUPPORT.
STUDIO_EVIDENCE_CLASS: Literal["STUDIO_API_READ"] = "STUDIO_API_READ"
EvidenceClass = Literal["FILE_ROUNDTRIP", "STUDIO_API_READ"]
EVIDENCE_CLASSES: frozenset[str] = frozenset({EVIDENCE_CLASS, STUDIO_EVIDENCE_CLASS})
EVIDENCE_QUALIFICATION: dict[str, str] = {
    EVIDENCE_CLASS: "FILE_ROUNDTRIP",
    STUDIO_EVIDENCE_CLASS: "TEST_ONLY_SUPPORT",
}


class HandoffTrackKind(str, Enum):
    UNKNOWN = "UNKNOWN"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"


class MarkerColor(str, Enum):
    """OTIO Marker.2 string colors plus UNKNOWN (writers refuse UNKNOWN)."""

    UNKNOWN = "UNKNOWN"
    PINK = "PINK"
    RED = "RED"
    ORANGE = "ORANGE"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    CYAN = "CYAN"
    BLUE = "BLUE"
    PURPLE = "PURPLE"
    MAGENTA = "MAGENTA"
    BLACK = "BLACK"
    WHITE = "WHITE"


class HandoffSeverity(str, Enum):
    UNKNOWN = "UNKNOWN"
    REFUSAL = "REFUSAL"
    WARNING = "WARNING"


class HandoffDiagnosticCode(str, Enum):
    UNKNOWN = "UNKNOWN"
    # writer refusals
    MEDIA_START_UNKNOWN = "MEDIA_START_UNKNOWN"
    UNKNOWN_TRACK_KIND = "UNKNOWN_TRACK_KIND"
    UNKNOWN_MARKER_COLOR = "UNKNOWN_MARKER_COLOR"
    MISSING_MEDIA_PATH = "MISSING_MEDIA_PATH"
    UNSUPPORTED_PATH = "UNSUPPORTED_PATH"
    MARKER_NOT_REPRESENTED = "MARKER_NOT_REPRESENTED"
    # subtitles
    EMPTY_TEXT = "EMPTY_TEXT"
    ARROW_IN_TEXT = "ARROW_IN_TEXT"
    MALFORMED_BLOCK = "MALFORMED_BLOCK"
    BAD_INDEX = "BAD_INDEX"
    BAD_TIMESTAMP = "BAD_TIMESTAMP"
    NONPOSITIVE_DURATION = "NONPOSITIVE_DURATION"
    # readers
    MALFORMED_DOCUMENT = "MALFORMED_DOCUMENT"
    UNKNOWN_SCHEMA = "UNKNOWN_SCHEMA"
    UNKNOWN_RATE = "UNKNOWN_RATE"
    RATE_MISMATCH = "RATE_MISMATCH"
    NON_INTEGRAL_TIME = "NON_INTEGRAL_TIME"
    UNSUPPORTED_FEATURE = "UNSUPPORTED_FEATURE"
    MISSING_MEDIA_ID = "MISSING_MEDIA_ID"
    INVALID_VALUE = "INVALID_VALUE"
    # LAYER-001: a layer item (or track state) the target format cannot carry
    LAYER_LOSS_RISK = "LAYER_LOSS_RISK"
    LINK_NOT_PRESERVED = "LINK_NOT_PRESERVED"


@dataclass(frozen=True)
class HandoffDiagnostic:
    code: HandoffDiagnosticCode
    severity: HandoffSeverity
    location: str
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, HandoffDiagnosticCode):
            raise TypeError("Unknown diagnostic code")
        if not isinstance(self.severity, HandoffSeverity):
            raise TypeError("Unknown diagnostic severity")
        if not isinstance(self.location, str) or not isinstance(self.message, str):
            raise TypeError("Diagnostic location and message must be strings")


def refusal(code: HandoffDiagnosticCode, location: str, message: str) -> HandoffDiagnostic:
    return HandoffDiagnostic(code, HandoffSeverity.REFUSAL, location, message)


def warning(code: HandoffDiagnosticCode, location: str, message: str) -> HandoffDiagnostic:
    return HandoffDiagnostic(code, HandoffSeverity.WARNING, location, message)


def has_refusal(diagnostics: tuple[HandoffDiagnostic, ...]) -> bool:
    return any(d.severity is not HandoffSeverity.WARNING for d in diagnostics)


def _nonempty(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")


def _optional_nonempty(value: object, label: str) -> None:
    if value is not None:
        _nonempty(value, label)


def _artifact_guard(artifact_kind: object, authorizes_import: object) -> None:
    if artifact_kind != ARTIFACT_KIND:
        raise ValueError("Handoff values are EXPECTED_TIMELINE_ARTIFACT only")
    if authorizes_import is not False:
        raise ValueError("Handoff artifacts never authorize import")


@dataclass(frozen=True)
class HandoffMediaRef:
    media_id: str
    target_path: str | None
    available_range: FrameRange | None = None
    media_start_frame: int | None = None

    def __post_init__(self) -> None:
        _nonempty(self.media_id, "Media ID")
        if self.target_path is not None:
            _nonempty(self.target_path, "Target path")
        if self.available_range is not None and not isinstance(self.available_range, FrameRange):
            raise TypeError("Available range must be a FrameRange")
        if self.media_start_frame is not None and (
            type(self.media_start_frame) is not int or self.media_start_frame < 0
        ):
            raise ValueError("Media start frame must be a nonnegative int or None (UNKNOWN)")

    @property
    def is_missing(self) -> bool:
        return self.target_path is None


@dataclass(frozen=True)
class HandoffMarker:
    frame_range: FrameRange
    name: str
    color: MarkerColor = MarkerColor.UNKNOWN
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.frame_range, FrameRange):
            raise TypeError("Marker requires a FrameRange")
        if not isinstance(self.name, str) or not isinstance(self.note, str):
            raise TypeError("Marker name and note must be strings")
        if not isinstance(self.color, MarkerColor):
            raise TypeError("Unknown marker color type")


@dataclass(frozen=True)
class HandoffClip:
    name: str
    media: HandoffMediaRef
    source_range: FrameRange
    enabled: bool = True
    markers: tuple[HandoffMarker, ...] = ()
    # LAYER-001 follow-up: FCP7 <sourcetrack> as "<mediatype>:<trackindex>" (e.g. "audio:2"
    # for the right channel of a stereo file), None when the file carries none.
    source_track: str | None = None
    # FCP7 <link> group read from the file (relationship evidence, not identity).
    link_group: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "markers", tuple(self.markers))
        _nonempty(self.name, "Clip name")
        _optional_nonempty(self.source_track, "Source track")
        _optional_nonempty(self.link_group, "Link group")
        if not isinstance(self.media, HandoffMediaRef):
            raise TypeError("Clip requires a HandoffMediaRef")
        if not isinstance(self.source_range, FrameRange):
            raise TypeError("Clip source range must be a FrameRange")
        if type(self.enabled) is not bool:
            raise TypeError("Clip enabled must be a bool")
        if any(not isinstance(m, HandoffMarker) for m in self.markers):
            raise TypeError("Clip markers must be HandoffMarker values")
        available = self.media.available_range
        if available is not None and not available.contains(self.source_range):
            raise ValueError("Clip source range lies outside the media available range")
        if any(not self.source_range.contains(m.frame_range) for m in self.markers):
            raise ValueError("Clip marker must lie within the clip source range")

    @property
    def duration(self) -> int:
        return self.source_range.duration


@dataclass(frozen=True)
class HandoffGap:
    duration: int

    def __post_init__(self) -> None:
        if type(self.duration) is not int or self.duration <= 0:
            raise ValueError("Gap duration must be a positive int")


HandoffItem = HandoffClip | HandoffGap


class LayerItemKind(str, Enum):
    """LAYER-001: what a pass-through (not modelled) track item is."""

    UNKNOWN = "UNKNOWN"
    GENERATOR = "GENERATOR"
    TRANSITION = "TRANSITION"
    NESTED_SEQUENCE = "NESTED_SEQUENCE"
    EFFECT_CLIP = "EFFECT_CLIP"  # clipitem carrying <filter> effects
    RETIMED_CLIP = "RETIMED_CLIP"  # speed change / time remap
    UNMODELLED_CLIP = "UNMODELLED_CLIP"  # any other clipitem the model cannot place
    UNKNOWN_ELEMENT = "UNKNOWN_ELEMENT"


PASSTHROUGH_FORMAT_XMEML: Literal["XMEML"] = "XMEML"


@dataclass(frozen=True)
class PassthroughItem:
    """LAYER-001: a track item the model does not understand, preserved verbatim.

    ``raw_xml`` is the original element subtree (canonical serialization by the
    xmeml reader: whitespace-only text removed, ``id`` attributes and ``<link>``
    children normalized, file references inlined). It is re-emitted as is; only
    the root's timeline ``start``/``end`` (and, for a 1:1 cut, ``in``/``out``)
    are ever rewritten.

    ``timeline_range`` is the item's extent in timeline frames, or ``None`` when
    it cannot be determined (UNKNOWN; such an item is never moved or cut).
    ``source_range`` is set only when the item is a plain 1:1 clipitem that can
    be cut like a modelled clip (e.g. a clipitem whose only unmodelled children
    are ``<filter>`` effects); ``media_id`` is set whenever the item names a file.
    """

    kind: LayerItemKind
    label: str
    timeline_range: FrameRange | None
    raw_xml: str
    media_id: str | None = None
    source_range: FrameRange | None = None
    has_filters: bool = False
    # FCP7 <link> group (relationship evidence, not identity); the writer re-maps it.
    link_group: str | None = field(default=None, compare=False)
    source_format: Literal["XMEML"] = PASSTHROUGH_FORMAT_XMEML

    def __post_init__(self) -> None:
        if not isinstance(self.kind, LayerItemKind):
            raise TypeError("Pass-through item requires a LayerItemKind")
        if not isinstance(self.label, str):
            raise TypeError("Pass-through label must be a string")
        _nonempty(self.raw_xml, "Pass-through raw XML")
        if self.timeline_range is not None and not isinstance(self.timeline_range, FrameRange):
            raise TypeError("Pass-through extent must be a FrameRange or None")
        if self.media_id is not None:
            _nonempty(self.media_id, "Pass-through media ID")
        if self.source_range is not None:
            if not isinstance(self.source_range, FrameRange):
                raise TypeError("Pass-through source range must be a FrameRange")
            if (
                self.media_id is None
                or self.timeline_range is None
                or self.timeline_range.duration != self.source_range.duration
            ):
                raise ValueError("A cuttable pass-through item needs media and a 1:1 extent")
        if type(self.has_filters) is not bool:
            raise TypeError("has_filters must be a bool")
        _optional_nonempty(self.link_group, "Link group")
        if self.source_format != PASSTHROUGH_FORMAT_XMEML:
            raise ValueError("Only xmeml pass-through items exist")

    @property
    def cuttable(self) -> bool:
        return self.source_range is not None


@dataclass(frozen=True)
class SequenceMarker:
    """LAYER-001: a sequence-level (timeline) marker, kept verbatim.

    ``frame_range`` is in timeline frames (a point marker is one frame);
    ``raw_xml`` is the canonical ``<marker>`` subtree. Only its ``in``/``out``
    are ever rewritten (ripple shift / move to a cut point).
    """

    frame_range: FrameRange
    name: str
    raw_xml: str

    def __post_init__(self) -> None:
        if not isinstance(self.frame_range, FrameRange):
            raise TypeError("Sequence marker requires a FrameRange")
        if not isinstance(self.name, str):
            raise TypeError("Sequence marker name must be a string")
        _nonempty(self.raw_xml, "Sequence marker raw XML")


@dataclass(frozen=True)
class HandoffTrack:
    """A track (layer). LAYER-001: tracks are never merged, dropped or reordered.

    ``passthrough`` holds items the model does not understand (absolute
    timeline positions, never overlapping modelled clips). ``enabled`` /
    ``locked`` are the track flags as read; ``attributes`` and ``extra_xml``
    keep other track-level XML (attributes, settings children) verbatim.
    """

    name: str
    kind: HandoffTrackKind
    items: tuple[HandoffItem, ...] = ()
    passthrough: tuple[PassthroughItem, ...] = ()
    enabled: bool = True
    locked: bool = False
    attributes: tuple[tuple[str, str], ...] = ()
    extra_xml: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "passthrough", tuple(self.passthrough))
        object.__setattr__(self, "attributes", tuple(tuple(a) for a in self.attributes))
        object.__setattr__(self, "extra_xml", tuple(self.extra_xml))
        _nonempty(self.name, "Track name")
        if not isinstance(self.kind, HandoffTrackKind):
            raise TypeError("Unknown track kind type")
        if any(not isinstance(i, (HandoffClip, HandoffGap)) for i in self.items):
            raise TypeError("Track items must be HandoffClip or HandoffGap")
        if any(not isinstance(p, PassthroughItem) for p in self.passthrough):
            raise TypeError("Pass-through items must be PassthroughItem values")
        if type(self.enabled) is not bool or type(self.locked) is not bool:
            raise TypeError("Track flags must be bools")
        for pair in self.attributes:
            if len(pair) != 2 or not all(isinstance(v, str) for v in pair):
                raise TypeError("Track attributes must be (name, value) string pairs")
        if any(not isinstance(x, str) or not x.strip() for x in self.extra_xml):
            raise TypeError("Track extra XML must be nonempty strings")
        spans = [FrameRange(start, start + clip.duration) for start, clip in self.placements()]
        for item in self.passthrough:
            extent = item.timeline_range
            if extent is not None and any(extent.overlaps(span) for span in spans):
                raise ValueError("A pass-through item must not overlap a modelled clip")

    @property
    def duration(self) -> int:
        ends = [p.timeline_range.end for p in self.passthrough if p.timeline_range is not None]
        return max([sum(item.duration for item in self.items), *ends])

    @property
    def has_layer_state(self) -> bool:
        """True when the track carries anything beyond modelled clips and gaps."""
        return bool(
            self.passthrough or not self.enabled or self.locked or self.attributes or self.extra_xml
        )

    def placements(self) -> tuple[tuple[int, HandoffClip], ...]:
        """(timeline start frame relative to timeline start, clip) in order."""
        cursor = 0
        result: list[tuple[int, HandoffClip]] = []
        for item in self.items:
            if isinstance(item, HandoffClip):
                result.append((cursor, item))
            cursor += item.duration
        return tuple(result)


def _check_sequence_markers(timeline: "HandoffTimeline | ReimportedTimeline") -> None:
    markers = tuple(timeline.markers)
    object.__setattr__(timeline, "markers", markers)
    if any(not isinstance(m, SequenceMarker) for m in markers):
        raise TypeError("Sequence markers must be SequenceMarker values")


@dataclass(frozen=True)
class HandoffTimeline:
    name: str
    rate: FrameRate
    start_frame: int
    tracks: tuple[HandoffTrack, ...]
    markers: tuple[SequenceMarker, ...] = ()
    artifact_kind: Literal["EXPECTED_TIMELINE_ARTIFACT"] = ARTIFACT_KIND
    authorizes_import: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracks", tuple(self.tracks))
        _check_sequence_markers(self)
        _nonempty(self.name, "Timeline name")
        if not isinstance(self.rate, FrameRate) or not is_smpte_rate(self.rate):
            raise ValueError("Timeline rate must be a whitelisted SMPTE FrameRate")
        if type(self.start_frame) is not int or self.start_frame < 0:
            raise ValueError("Timeline start frame must be a nonnegative int")
        if any(not isinstance(t, HandoffTrack) for t in self.tracks):
            raise TypeError("Timeline tracks must be HandoffTrack values")
        _artifact_guard(self.artifact_kind, self.authorizes_import)

    @property
    def duration(self) -> int:
        return max((t.duration for t in self.tracks), default=0)


@dataclass(frozen=True)
class ReimportedTimeline:
    """Actual side: a timeline re-read from a file an NLE exported (RT-001 decision 1).

    Distinct from the Expected :class:`HandoffTimeline`: it carries the evidence
    class ``FILE_ROUNDTRIP`` (never native evidence, never VERIFIED_LIVE; INT-002:
    ``STUDIO_API_READ`` when it came from a getter-only Studio read, TEST_ONLY_SUPPORT) and no
    ``EXPECTED_TIMELINE_ARTIFACT`` constant, so a re-read file can never be passed
    where an Expected plan is required. Tracks reuse the structural
    :class:`HandoffTrack` values.

    ``unpreserved`` (LAYER-001): descriptions of content the file carried that
    this model cannot preserve when a new file is written (e.g. a malformed
    sequence-level marker). Applying cuts to such a timeline refuses with
    ``LAYER_LOSS_RISK``. Well-formed sequence markers are kept in ``markers``.

    ``path_identified_media_ids``: media IDs that the file did not carry as our
    metadata (e.g. an OTIO export whose ``metadata["davinci_ai_editor"]`` was
    dropped by the NLE) and were therefore derived from the target path. Clips
    with these IDs are matched by path + source range with WEAK identity only.
    """

    name: str
    rate: FrameRate
    start_frame: int
    tracks: tuple[HandoffTrack, ...]
    path_identified_media_ids: tuple[str, ...] = ()
    unpreserved: tuple[str, ...] = ()
    markers: tuple[SequenceMarker, ...] = ()
    evidence_class: EvidenceClass = EVIDENCE_CLASS
    native_evidence: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracks", tuple(self.tracks))
        _check_sequence_markers(self)
        object.__setattr__(
            self, "path_identified_media_ids", tuple(sorted(set(self.path_identified_media_ids)))
        )
        object.__setattr__(self, "unpreserved", tuple(self.unpreserved))
        if any(not isinstance(u, str) or not u.strip() for u in self.unpreserved):
            raise TypeError("Unpreserved content descriptions must be nonempty strings")
        _nonempty(self.name, "Timeline name")
        if not isinstance(self.rate, FrameRate) or not is_smpte_rate(self.rate):
            raise ValueError("Timeline rate must be a whitelisted SMPTE FrameRate")
        if type(self.start_frame) is not int or self.start_frame < 0:
            raise ValueError("Timeline start frame must be a nonnegative int")
        if any(not isinstance(t, HandoffTrack) for t in self.tracks):
            raise TypeError("Timeline tracks must be HandoffTrack values")
        for media_id in self.path_identified_media_ids:
            _nonempty(media_id, "Path-identified media ID")
        if self.evidence_class not in EVIDENCE_CLASSES or self.native_evidence is not False:
            raise ValueError(
                "A re-imported timeline is FILE_ROUNDTRIP or STUDIO_API_READ evidence, never native"
            )

    @property
    def duration(self) -> int:
        return max((t.duration for t in self.tracks), default=0)


TimelineStructure = HandoffTimeline | ReimportedTimeline


@dataclass(frozen=True)
class HandoffSubtitleCue:
    frame_range: FrameRange
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.frame_range, FrameRange):
            raise TypeError("Subtitle cue requires a FrameRange")
        if not isinstance(self.text, str):
            raise TypeError("Subtitle text must be a string")


_TRACK_KIND = {
    TrackType.VIDEO: HandoffTrackKind.VIDEO,
    TrackType.AUDIO: HandoffTrackKind.AUDIO,
    TrackType.UNKNOWN: HandoffTrackKind.UNKNOWN,
}


def handoff_from_snapshot(
    snapshot: TimelineSnapshot,
    media: Mapping[str, HandoffMediaRef],
    rate: FrameRate,
    name: str,
    start_frame: int = 0,
) -> HandoffTimeline:
    """Describe a snapshot as an Expected-timeline artifact (no Actual claim).

    Gaps are derived from clip timeline ranges in order. Missing media mapping,
    or SUBTITLE/OTHER tracks (not representable as clip tracks), reject.
    UNKNOWN track type stays UNKNOWN (writers refuse it).
    """
    if not isinstance(snapshot, TimelineSnapshot):
        raise TypeError("A TimelineSnapshot is required")
    tracks: list[HandoffTrack] = []
    for track in snapshot.tracks:
        kind = _TRACK_KIND.get(track.track_type)
        if kind is None:
            raise ValueError(f"Track {track.track_id} type {track.track_type.value} unsupported")
        items: list[HandoffItem] = []
        cursor = 0
        for clip in track.clips:
            ref = media.get(clip.media_id)
            if ref is None:
                raise ValueError(f"No media reference supplied for {clip.media_id}")
            if ref.media_id != clip.media_id:
                raise ValueError("Media reference ID does not match the clip media ID")
            if clip.timeline_range.start > cursor:
                items.append(HandoffGap(clip.timeline_range.start - cursor))
            items.append(HandoffClip(clip.clip_id, ref, clip.source_range))
            cursor = clip.timeline_range.end
        tracks.append(HandoffTrack(track.track_id, kind, tuple(items)))
    return HandoffTimeline(name, rate, start_frame, tuple(tracks))


# --- path / URL helpers (shared by writers) ---------------------------------

_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
_URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+:")


def is_windows_absolute(path: str) -> bool:
    return bool(_WINDOWS_ABSOLUTE.match(path))


def has_url_scheme(path: str) -> bool:
    """True for ``scheme:`` URLs; single-letter Windows drives are not schemes."""
    return not is_windows_absolute(path) and bool(_URL_SCHEME.match(path))


def path_to_file_url(path: str) -> str | None:
    """Absolute path -> ``file://`` URL; existing URL unchanged; relative -> None."""
    if has_url_scheme(path):
        return path
    if is_windows_absolute(path):
        return PureWindowsPath(path).as_uri()
    if path.startswith("/"):
        return PurePosixPath(path).as_uri()
    return None


def file_url_to_path(url: str) -> str:
    """Inverse of :func:`path_to_file_url` for ``file:`` URLs (forward slashes)."""
    parts = urlsplit(url)
    if parts.scheme.lower() != "file":
        return url
    path = unquote(parts.path)
    if re.match(r"^/[A-Za-z]:/", path):
        path = path[1:]
    if parts.netloc:
        path = f"//{parts.netloc}{path}"
    return path
