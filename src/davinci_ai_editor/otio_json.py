"""HANDOFF-001 deterministic OpenTimelineIO JSON writer/reader for a narrow subset.

Schema names follow OpenTimelineIO (Apache-2.0, Copyright Contributors to the
OpenTimelineIO project; see licenses/OpenTimelineIO-LICENSE.txt and
licenses/OpenTimelineIO-NOTICE.txt). The object layout is adapted from
timeline (Chat Octopus) src/otio/writer.ts, MIT License, see
licenses/timeline-LICENSE.txt. No OpenTimelineIO code is imported or executed.

Subset: Timeline.1 / Stack.1 / Track.1 / Clip.2 / Gap.1 / ExternalReference.1 /
MissingReference.1 / Marker.2 / RationalTime.1 / TimeRange.1. Anything else is
reported as UNKNOWN and refused by the reader (never guessed).

``OtioProfile.RESOLVE_SHAPED`` applies third-party *claims* about what DaVinci
Resolve's OTIO import expects (bare filesystem path in ``target_url``, source
ranges absolute against the media start timecode, track names "Video N" /
"Audio N"). These claims are UNVERIFIED on our runtime. When the media start
frame is UNKNOWN the profile refuses instead of assuming 0.

The written file is an Expected artifact only. Importing it into Resolve is a
native mutation (HOLD / manual user action) and nothing here authorizes it.

Reading is the Actual side: ``read_otio`` returns a ``ReimportedTimeline``
(``FILE_ROUNDTRIP`` evidence). When an NLE export dropped our
``metadata["davinci_ai_editor"]`` from an ``ExternalReference``, the media is
identified by its target path instead (warning ``MISSING_MEDIA_ID``; the ID is
listed in ``path_identified_media_ids`` and diffs match it by path + source
range with WEAK identity). A ``MissingReference`` without our metadata has no
path and stays a refusal. FCP7 XML remains the default round-trip format.
"""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from .domain import FrameRange
from .handoff_model import (
    ARTIFACT_KIND,
    EVIDENCE_CLASS,
    HandoffClip,
    HandoffDiagnostic,
    HandoffDiagnosticCode,
    HandoffGap,
    HandoffItem,
    HandoffMarker,
    HandoffMediaRef,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
    MarkerColor,
    ReimportedTimeline,
    file_url_to_path,
    has_refusal,
    has_url_scheme,
    path_to_file_url,
    refusal,
    warning,
)
from .temporal_mapping import FrameRate
from .timecode import rate_as_float, snap_rate

METADATA_NAMESPACE = "davinci_ai_editor"
DEFAULT_MEDIA_KEY = "DEFAULT_MEDIA"

_KIND_TO_OTIO = {HandoffTrackKind.VIDEO: "Video", HandoffTrackKind.AUDIO: "Audio"}
_OTIO_TO_KIND = {value: key for key, value in _KIND_TO_OTIO.items()}

SUPPORTED_SCHEMAS = frozenset(
    {
        "Timeline.1",
        "Stack.1",
        "Track.1",
        "Clip.2",
        "Gap.1",
        "ExternalReference.1",
        "MissingReference.1",
        "Marker.2",
        "RationalTime.1",
        "TimeRange.1",
    }
)


class OtioProfile(str, Enum):
    UNKNOWN = "UNKNOWN"
    DEFAULT = "DEFAULT"
    RESOLVE_SHAPED = "RESOLVE_SHAPED"


@dataclass(frozen=True)
class OtioWriteResult:
    text: str | None
    profile: OtioProfile
    diagnostics: tuple[HandoffDiagnostic, ...]
    artifact_kind: Literal["EXPECTED_TIMELINE_ARTIFACT"] = ARTIFACT_KIND
    authorizes_import: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.artifact_kind != ARTIFACT_KIND or self.authorizes_import is not False:
            raise ValueError("OTIO results are artifacts that never authorize import")
        if (self.text is None) != has_refusal(self.diagnostics):
            raise ValueError("A refused write has no text; a written file has no refusal")

    @property
    def refused(self) -> bool:
        return self.text is None


@dataclass(frozen=True)
class OtioReadResult:
    timeline: ReimportedTimeline | None
    diagnostics: tuple[HandoffDiagnostic, ...]
    evidence_class: Literal["FILE_ROUNDTRIP"] = EVIDENCE_CLASS
    native_evidence: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.evidence_class != EVIDENCE_CLASS or self.native_evidence is not False:
            raise ValueError("A re-read OTIO file is FILE_ROUNDTRIP evidence, never native")
        if self.timeline is not None and has_refusal(self.diagnostics):
            raise ValueError("A refused read cannot carry a timeline")


# --- writer -------------------------------------------------------------------

JsonObject = dict[str, object]


def _rational_time(value: int, rate: FrameRate) -> JsonObject:
    return {"OTIO_SCHEMA": "RationalTime.1", "rate": rate_as_float(rate), "value": float(value)}


def _time_range(start: int, duration: int, rate: FrameRate) -> JsonObject:
    return {
        "OTIO_SCHEMA": "TimeRange.1",
        "duration": _rational_time(duration, rate),
        "start_time": _rational_time(start, rate),
    }


def _shifted(frame_range: FrameRange, offset: int, rate: FrameRate) -> JsonObject:
    return _time_range(frame_range.start + offset, frame_range.duration, rate)


class _Refused(Exception):
    def __init__(self, diagnostic: HandoffDiagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


class _Writer:
    def __init__(self, timeline: HandoffTimeline, profile: OtioProfile) -> None:
        self.timeline = timeline
        self.rate = timeline.rate
        self.profile = profile
        self.resolve = profile is OtioProfile.RESOLVE_SHAPED

    def offset(self, media: HandoffMediaRef, location: str) -> int:
        if not self.resolve:
            return 0
        if media.media_start_frame is None:
            raise _Refused(
                refusal(
                    HandoffDiagnosticCode.MEDIA_START_UNKNOWN,
                    location,
                    "Resolve-shaped absolute source ranges need a known media start; "
                    "UNKNOWN is not assumed to be 0",
                )
            )
        return media.media_start_frame

    def target_url(self, path: str, location: str) -> str:
        if self.resolve:
            if has_url_scheme(path):
                raise _Refused(
                    refusal(
                        HandoffDiagnosticCode.UNSUPPORTED_PATH,
                        location,
                        "Resolve-shaped profile requires a bare filesystem path, not a URL",
                    )
                )
            return path
        url = path_to_file_url(path)
        if url is None:
            raise _Refused(
                refusal(
                    HandoffDiagnosticCode.UNSUPPORTED_PATH,
                    location,
                    "Relative media path cannot be written as a file URL",
                )
            )
        return url

    def media_reference(self, media: HandoffMediaRef, location: str) -> JsonObject:
        offset = self.offset(media, location)
        metadata: JsonObject = {
            METADATA_NAMESPACE: {
                "media_id": media.media_id,
                "media_start_frame": media.media_start_frame,
            }
        }
        available = (
            None
            if media.available_range is None
            else _shifted(media.available_range, offset, self.rate)
        )
        if media.target_path is None:
            return {
                "OTIO_SCHEMA": "MissingReference.1",
                "available_range": available,
                "metadata": metadata,
                "name": media.media_id,
            }
        return {
            "OTIO_SCHEMA": "ExternalReference.1",
            "available_range": available,
            "metadata": metadata,
            "name": media.media_id,
            "target_url": self.target_url(media.target_path, location),
        }

    def marker(self, marker: HandoffMarker, offset: int, location: str) -> JsonObject:
        if marker.color is MarkerColor.UNKNOWN:
            raise _Refused(
                refusal(
                    HandoffDiagnosticCode.UNKNOWN_MARKER_COLOR,
                    location,
                    "Marker color is UNKNOWN; the writer does not pick one",
                )
            )
        return {
            "OTIO_SCHEMA": "Marker.2",
            "color": marker.color.value,
            "comment": marker.note,
            "marked_range": _shifted(marker.frame_range, offset, self.rate),
            "metadata": {},
            "name": marker.name,
        }

    def item(self, item: HandoffItem, location: str) -> JsonObject:
        if isinstance(item, HandoffGap):
            return {
                "OTIO_SCHEMA": "Gap.1",
                "effects": [],
                "enabled": True,
                "markers": [],
                "metadata": {},
                "name": "",
                "source_range": _time_range(0, item.duration, self.rate),
            }
        offset = self.offset(item.media, location)
        return {
            "OTIO_SCHEMA": "Clip.2",
            "active_media_reference_key": DEFAULT_MEDIA_KEY,
            "effects": [],
            "enabled": item.enabled,
            "markers": [
                self.marker(m, offset, f"{location}.markers[{i}]")
                for i, m in enumerate(item.markers)
            ],
            "media_references": {
                DEFAULT_MEDIA_KEY: self.media_reference(item.media, f"{location}.media")
            },
            "metadata": {},
            "name": item.name,
            "source_range": _shifted(item.source_range, offset, self.rate),
        }

    def track(self, track: HandoffTrack, name: str, location: str) -> JsonObject:
        kind = _KIND_TO_OTIO.get(track.kind)
        if kind is None:
            raise _Refused(
                refusal(
                    HandoffDiagnosticCode.UNKNOWN_TRACK_KIND,
                    location,
                    "Track kind is UNKNOWN; the writer does not choose Video or Audio",
                )
            )
        return {
            "OTIO_SCHEMA": "Track.1",
            "children": [
                self.item(item, f"{location}.items[{i}]") for i, item in enumerate(track.items)
            ],
            "effects": [],
            "enabled": True,
            "kind": kind,
            "markers": [],
            "metadata": {},
            "name": name,
            "source_range": None,
        }

    def track_names(self) -> list[str]:
        if not self.resolve:
            return [t.name for t in self.timeline.tracks]
        counters = {HandoffTrackKind.VIDEO: 0, HandoffTrackKind.AUDIO: 0}
        names: list[str] = []
        for track in self.timeline.tracks:
            if track.kind in counters:
                counters[track.kind] += 1
                names.append(f"{_KIND_TO_OTIO[track.kind]} {counters[track.kind]}")
            else:
                names.append(track.name)
        return names

    def document(self) -> JsonObject:
        names = self.track_names()
        return {
            "OTIO_SCHEMA": "Timeline.1",
            "global_start_time": _rational_time(self.timeline.start_frame, self.rate),
            "metadata": {
                METADATA_NAMESPACE: {
                    "artifact_kind": ARTIFACT_KIND,
                    "authorizes_import": False,
                    "profile": self.profile.value,
                    "rate": [self.rate.numerator, self.rate.denominator],
                }
            },
            "name": self.timeline.name,
            "tracks": {
                "OTIO_SCHEMA": "Stack.1",
                "children": [
                    self.track(t, names[i], f"tracks[{i}]")
                    for i, t in enumerate(self.timeline.tracks)
                ],
                "effects": [],
                "enabled": True,
                "markers": [],
                "metadata": {},
                "name": "tracks",
                "source_range": None,
            },
        }


def dumps_deterministic(document: JsonObject) -> str:
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_otio(
    timeline: HandoffTimeline, profile: OtioProfile = OtioProfile.DEFAULT
) -> OtioWriteResult:
    """Deterministic OTIO JSON (sorted keys, 2-space indent, LF, trailing newline)."""
    if not isinstance(timeline, HandoffTimeline):
        raise TypeError("A HandoffTimeline is required")
    if not isinstance(profile, OtioProfile) or profile is OtioProfile.UNKNOWN:
        raise ValueError("OTIO profile must be DEFAULT or RESOLVE_SHAPED")
    try:
        document = _Writer(timeline, profile).document()
    except _Refused as refused:
        return OtioWriteResult(None, profile, (refused.diagnostic,))
    return OtioWriteResult(dumps_deterministic(document), profile, ())


# --- reader -------------------------------------------------------------------


class _Reader:
    def __init__(self) -> None:
        self.diagnostics: list[HandoffDiagnostic] = []
        self.rate: FrameRate | None = None
        self.path_identified: set[str] = set()

    def fail(self, code: HandoffDiagnosticCode, location: str, message: str) -> _Refused:
        return _Refused(refusal(code, location, message))

    def obj(self, value: object, schema: str, location: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise self.fail(HandoffDiagnosticCode.MALFORMED_DOCUMENT, location, "Expected object")
        found = value.get("OTIO_SCHEMA")
        if not isinstance(found, str):
            raise self.fail(HandoffDiagnosticCode.UNKNOWN_SCHEMA, location, "No OTIO_SCHEMA")
        if found not in SUPPORTED_SCHEMAS:
            raise self.fail(
                HandoffDiagnosticCode.UNKNOWN_SCHEMA,
                location,
                f"Schema {found!r} is UNKNOWN to this reader",
            )
        if found != schema:
            raise self.fail(
                HandoffDiagnosticCode.UNKNOWN_SCHEMA,
                location,
                f"Expected {schema!r}, found {found!r}",
            )
        return value

    def string(self, container: dict[str, object], key: str, location: str) -> str:
        value = container.get(key, "")
        if not isinstance(value, str):
            raise self.fail(HandoffDiagnosticCode.INVALID_VALUE, location, f"{key} not a string")
        return value

    def no_effects(self, container: dict[str, object], location: str) -> None:
        effects = container.get("effects", [])
        if effects not in ([], None):
            raise self.fail(
                HandoffDiagnosticCode.UNSUPPORTED_FEATURE, location, "Effects are not supported"
            )

    def rational(self, value: object, location: str) -> int:
        data = self.obj(value, "RationalTime.1", location)
        raw_rate = data.get("rate")
        raw_value = data.get("value")
        if isinstance(raw_rate, bool) or not isinstance(raw_rate, (int, float)):
            raise self.fail(HandoffDiagnosticCode.INVALID_VALUE, location, "rate not numeric")
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise self.fail(HandoffDiagnosticCode.INVALID_VALUE, location, "value not numeric")
        rate = snap_rate(raw_rate)
        if rate is None:
            raise self.fail(
                HandoffDiagnosticCode.UNKNOWN_RATE,
                location,
                f"Rate {raw_rate!r} is not a whitelisted SMPTE rate (UNKNOWN)",
            )
        if self.rate is None:
            self.rate = rate
        elif rate != self.rate:
            raise self.fail(
                HandoffDiagnosticCode.RATE_MISMATCH, location, "Mixed rates are not supported"
            )
        if isinstance(raw_value, float) and not raw_value.is_integer():
            raise self.fail(
                HandoffDiagnosticCode.NON_INTEGRAL_TIME, location, "Time is not frame aligned"
            )
        return int(raw_value)

    def time_range(self, value: object, location: str) -> tuple[int, int]:
        data = self.obj(value, "TimeRange.1", location)
        start = self.rational(data.get("start_time"), f"{location}.start_time")
        duration = self.rational(data.get("duration"), f"{location}.duration")
        return start, duration

    def frame_range(self, value: object, offset: int, location: str) -> FrameRange:
        start, duration = self.time_range(value, location)
        try:
            return FrameRange(start - offset, start - offset + duration)
        except ValueError as exc:
            raise self.fail(HandoffDiagnosticCode.INVALID_VALUE, location, str(exc)) from exc

    def media(self, value: object, location: str, resolve: bool) -> tuple[HandoffMediaRef, int]:
        if not isinstance(value, dict):
            raise self.fail(HandoffDiagnosticCode.MALFORMED_DOCUMENT, location, "Expected object")
        schema = value.get("OTIO_SCHEMA")
        expected = "MissingReference.1" if schema == "MissingReference.1" else "ExternalReference.1"
        data = self.obj(value, expected, location)
        metadata = data.get("metadata")
        ours = metadata.get(METADATA_NAMESPACE) if isinstance(metadata, dict) else None
        media_id = ours.get("media_id") if isinstance(ours, dict) else None
        target: str | None = None
        if expected == "ExternalReference.1":
            url = self.string(data, "target_url", location)
            if not url:
                raise self.fail(HandoffDiagnosticCode.INVALID_VALUE, location, "Empty target_url")
            target = url if resolve else file_url_to_path(url)
        if not isinstance(media_id, str) or not media_id.strip():
            if target is None:
                raise self.fail(
                    HandoffDiagnosticCode.MISSING_MEDIA_ID, location, "No media_id; not guessed"
                )
            # The NLE dropped our metadata: identify by path (WEAK), never by a guess.
            media_id = target
            self.path_identified.add(target)
            self.diagnostics.append(
                warning(
                    HandoffDiagnosticCode.MISSING_MEDIA_ID,
                    location,
                    "No media_id metadata; media identified by target path (WEAK identity)",
                )
            )
        start = ours.get("media_start_frame") if isinstance(ours, dict) else None
        if start is not None and (type(start) is not int or start < 0):
            raise self.fail(HandoffDiagnosticCode.INVALID_VALUE, location, "Bad media start")
        offset = 0
        if resolve:
            if start is None:
                raise self.fail(
                    HandoffDiagnosticCode.MEDIA_START_UNKNOWN,
                    location,
                    "Resolve-shaped ranges cannot be made relative without a media start",
                )
            offset = start
        available_raw = data.get("available_range")
        available = (
            None
            if available_raw is None
            else self.frame_range(available_raw, offset, f"{location}.available_range")
        )
        return HandoffMediaRef(media_id, target, available, start), offset

    def marker(self, value: object, offset: int, location: str) -> HandoffMarker:
        data = self.obj(value, "Marker.2", location)
        raw_color = data.get("color")
        try:
            color = MarkerColor(raw_color.upper()) if isinstance(raw_color, str) else None
        except ValueError:
            color = None
        if color is None or color is MarkerColor.UNKNOWN:
            color = MarkerColor.UNKNOWN
            self.diagnostics.append(
                warning(
                    HandoffDiagnosticCode.UNKNOWN_MARKER_COLOR,
                    location,
                    f"Marker color {raw_color!r} is UNKNOWN",
                )
            )
        return HandoffMarker(
            self.frame_range(data.get("marked_range"), offset, f"{location}.marked_range"),
            self.string(data, "name", location),
            color,
            self.string(data, "comment", location),
        )

    def item(self, value: object, location: str, resolve: bool) -> HandoffItem:
        schema = value.get("OTIO_SCHEMA") if isinstance(value, dict) else None
        if schema == "Gap.1":
            data = self.obj(value, "Gap.1", location)
            self.no_effects(data, location)
            _, duration = self.time_range(data.get("source_range"), f"{location}.source_range")
            if duration <= 0:
                raise self.fail(HandoffDiagnosticCode.INVALID_VALUE, location, "Empty gap")
            return HandoffGap(duration)
        data = self.obj(value, "Clip.2", location)
        self.no_effects(data, location)
        key = data.get("active_media_reference_key")
        refs = data.get("media_references")
        if key != DEFAULT_MEDIA_KEY or not isinstance(refs, dict) or set(refs) != {key}:
            raise self.fail(
                HandoffDiagnosticCode.UNSUPPORTED_FEATURE,
                location,
                "Only a single DEFAULT_MEDIA reference is supported",
            )
        media, offset = self.media(refs[key], f"{location}.media", resolve)
        if data.get("source_range") is None:
            raise self.fail(
                HandoffDiagnosticCode.INVALID_VALUE, location, "Clip without explicit source_range"
            )
        source = self.frame_range(data.get("source_range"), offset, f"{location}.source_range")
        enabled = data.get("enabled", True)
        if type(enabled) is not bool:
            raise self.fail(HandoffDiagnosticCode.INVALID_VALUE, location, "enabled not bool")
        markers_raw = data.get("markers", [])
        if not isinstance(markers_raw, list):
            raise self.fail(HandoffDiagnosticCode.MALFORMED_DOCUMENT, location, "markers")
        markers = tuple(
            self.marker(m, offset, f"{location}.markers[{i}]") for i, m in enumerate(markers_raw)
        )
        name = self.string(data, "name", location)
        try:
            return HandoffClip(name, media, source, enabled, markers)
        except (TypeError, ValueError) as exc:
            raise self.fail(HandoffDiagnosticCode.INVALID_VALUE, location, str(exc)) from exc

    def track(self, value: object, location: str, resolve: bool) -> HandoffTrack:
        data = self.obj(value, "Track.1", location)
        self.no_effects(data, location)
        if data.get("source_range") is not None or data.get("markers", []) not in ([], None):
            raise self.fail(
                HandoffDiagnosticCode.UNSUPPORTED_FEATURE,
                location,
                "Track source_range/markers are not supported",
            )
        raw_kind = data.get("kind")
        kind = _OTIO_TO_KIND.get(raw_kind) if isinstance(raw_kind, str) else None
        if kind is None:
            kind = HandoffTrackKind.UNKNOWN
            self.diagnostics.append(
                warning(
                    HandoffDiagnosticCode.UNKNOWN_TRACK_KIND,
                    location,
                    f"Track kind {raw_kind!r} is UNKNOWN",
                )
            )
        children = data.get("children")
        if not isinstance(children, list):
            raise self.fail(HandoffDiagnosticCode.MALFORMED_DOCUMENT, location, "children")
        items = tuple(
            self.item(child, f"{location}.items[{i}]", resolve) for i, child in enumerate(children)
        )
        name = self.string(data, "name", location)
        if not name.strip():
            raise self.fail(HandoffDiagnosticCode.INVALID_VALUE, location, "Empty track name")
        return HandoffTrack(name, kind, items)

    def document(self, value: object) -> ReimportedTimeline:
        data = self.obj(value, "Timeline.1", "timeline")
        metadata = data.get("metadata")
        ours = metadata.get(METADATA_NAMESPACE) if isinstance(metadata, dict) else None
        raw_profile = ours.get("profile") if isinstance(ours, dict) else None
        if raw_profile is None:
            profile = OtioProfile.DEFAULT
        else:
            try:
                profile = OtioProfile(raw_profile)
            except ValueError:
                profile = OtioProfile.UNKNOWN
            if profile is OtioProfile.UNKNOWN:
                raise self.fail(
                    HandoffDiagnosticCode.UNKNOWN_SCHEMA,
                    "timeline.metadata",
                    f"Profile {raw_profile!r} is UNKNOWN",
                )
        resolve = profile is OtioProfile.RESOLVE_SHAPED
        start = self.rational(data.get("global_start_time"), "timeline.global_start_time")
        stack = self.obj(data.get("tracks"), "Stack.1", "timeline.tracks")
        self.no_effects(stack, "timeline.tracks")
        children = stack.get("children")
        if not isinstance(children, list):
            raise self.fail(HandoffDiagnosticCode.MALFORMED_DOCUMENT, "timeline.tracks", "children")
        tracks = tuple(
            self.track(child, f"tracks[{i}]", resolve) for i, child in enumerate(children)
        )
        if self.rate is None:
            raise self.fail(HandoffDiagnosticCode.UNKNOWN_RATE, "timeline", "No rate")
        name = self.string(data, "name", "timeline")
        try:
            return ReimportedTimeline(
                name, self.rate, start, tracks, tuple(sorted(self.path_identified))
            )
        except (TypeError, ValueError) as exc:
            raise self.fail(HandoffDiagnosticCode.INVALID_VALUE, "timeline", str(exc)) from exc


def read_otio(text: str) -> OtioReadResult:
    """Read the writer's subset back. Unknown schema/version/rate -> refusal, never guessed."""
    if not isinstance(text, str):
        raise TypeError("OTIO input must be a string")
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        return OtioReadResult(
            None,
            (
                refusal(
                    HandoffDiagnosticCode.MALFORMED_DOCUMENT, "document", f"Invalid JSON: {exc}"
                ),
            ),
        )
    reader = _Reader()
    try:
        timeline = reader.document(document)
    except _Refused as refused:
        return OtioReadResult(None, (*reader.diagnostics, refused.diagnostic))
    return OtioReadResult(timeline, tuple(reader.diagnostics))
