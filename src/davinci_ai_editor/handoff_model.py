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
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal
from urllib.parse import unquote, urlsplit

from .domain import FrameRange, TimelineSnapshot, TrackType
from .temporal_mapping import FrameRate
from .timecode import is_smpte_rate

ARTIFACT_KIND: Literal["EXPECTED_TIMELINE_ARTIFACT"] = "EXPECTED_TIMELINE_ARTIFACT"
EVIDENCE_CLASS: Literal["FILE_ROUNDTRIP"] = "FILE_ROUNDTRIP"


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "markers", tuple(self.markers))
        _nonempty(self.name, "Clip name")
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


@dataclass(frozen=True)
class HandoffTrack:
    name: str
    kind: HandoffTrackKind
    items: tuple[HandoffItem, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        _nonempty(self.name, "Track name")
        if not isinstance(self.kind, HandoffTrackKind):
            raise TypeError("Unknown track kind type")
        if any(not isinstance(i, (HandoffClip, HandoffGap)) for i in self.items):
            raise TypeError("Track items must be HandoffClip or HandoffGap")

    @property
    def duration(self) -> int:
        return sum(item.duration for item in self.items)

    def placements(self) -> tuple[tuple[int, HandoffClip], ...]:
        """(timeline start frame relative to timeline start, clip) in order."""
        cursor = 0
        result: list[tuple[int, HandoffClip]] = []
        for item in self.items:
            if isinstance(item, HandoffClip):
                result.append((cursor, item))
            cursor += item.duration
        return tuple(result)


@dataclass(frozen=True)
class HandoffTimeline:
    name: str
    rate: FrameRate
    start_frame: int
    tracks: tuple[HandoffTrack, ...]
    artifact_kind: Literal["EXPECTED_TIMELINE_ARTIFACT"] = ARTIFACT_KIND
    authorizes_import: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracks", tuple(self.tracks))
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
    class ``FILE_ROUNDTRIP`` (never native evidence, never VERIFIED_LIVE) and no
    ``EXPECTED_TIMELINE_ARTIFACT`` constant, so a re-read file can never be passed
    where an Expected plan is required. Tracks reuse the structural
    :class:`HandoffTrack` values.

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
    evidence_class: Literal["FILE_ROUNDTRIP"] = EVIDENCE_CLASS
    native_evidence: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracks", tuple(self.tracks))
        object.__setattr__(
            self, "path_identified_media_ids", tuple(sorted(set(self.path_identified_media_ids)))
        )
        _nonempty(self.name, "Timeline name")
        if not isinstance(self.rate, FrameRate) or not is_smpte_rate(self.rate):
            raise ValueError("Timeline rate must be a whitelisted SMPTE FrameRate")
        if type(self.start_frame) is not int or self.start_frame < 0:
            raise ValueError("Timeline start frame must be a nonnegative int")
        if any(not isinstance(t, HandoffTrack) for t in self.tracks):
            raise TypeError("Timeline tracks must be HandoffTrack values")
        for media_id in self.path_identified_media_ids:
            _nonempty(media_id, "Path-identified media ID")
        if self.evidence_class != EVIDENCE_CLASS or self.native_evidence is not False:
            raise ValueError("A re-imported timeline is FILE_ROUNDTRIP evidence, never native")

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
