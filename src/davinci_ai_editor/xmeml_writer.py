"""HANDOFF-001 deterministic FCP7 XML (xmeml v5) writer via xml.etree.

Element layout adapted from timeline (Chat Octopus) src/xmeml/writer.ts, MIT
License, see licenses/timeline-LICENSE.txt. Ported to Python/xml.etree with
exact integer frames; unsupported content is refused, never dropped.

Scope limits (explicit): no ``<format>``/``samplecharacteristics`` (frame size
and audio sample rate are UNKNOWN to the model), no links between A/V
clipitems, no marker colors (xmeml v5 markers have none; reported as warnings).
The written file is an Expected artifact only; importing it is a native
mutation (HOLD / manual user action) and nothing here authorizes it.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Literal

from .handoff_model import (
    ARTIFACT_KIND,
    HandoffClip,
    HandoffDiagnostic,
    HandoffDiagnosticCode,
    HandoffMediaRef,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
    has_refusal,
    path_to_file_url,
    refusal,
    warning,
)
from .temporal_mapping import FrameRate
from .timecode import default_mode, frames_to_timecode, is_ntsc, nominal_fps, supports_drop_frame

XML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'


@dataclass(frozen=True)
class XmemlWriteResult:
    text: str | None
    diagnostics: tuple[HandoffDiagnostic, ...]
    artifact_kind: Literal["EXPECTED_TIMELINE_ARTIFACT"] = ARTIFACT_KIND
    authorizes_import: Literal[False] = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.artifact_kind != ARTIFACT_KIND or self.authorizes_import is not False:
            raise ValueError("xmeml results are artifacts that never authorize import")
        if (self.text is None) != has_refusal(self.diagnostics):
            raise ValueError("A refused write has no text; a written file has no refusal")

    @property
    def refused(self) -> bool:
        return self.text is None


def _leaf(parent: ET.Element, tag: str, text: str) -> ET.Element:
    element = ET.SubElement(parent, tag)
    element.text = text
    return element


def _rate(parent: ET.Element, rate: FrameRate) -> None:
    element = ET.SubElement(parent, "rate")
    _leaf(element, "timebase", str(nominal_fps(rate)))
    _leaf(element, "ntsc", "TRUE" if is_ntsc(rate) else "FALSE")


def _timecode(parent: ET.Element, frame: int, rate: FrameRate) -> None:
    element = ET.SubElement(parent, "timecode")
    _rate(element, rate)
    _leaf(element, "string", frames_to_timecode(frame, rate, default_mode(rate)))
    _leaf(element, "frame", str(frame))
    _leaf(element, "displayformat", "DF" if supports_drop_frame(rate) else "NDF")


def _preflight(timeline: HandoffTimeline) -> list[HandoffDiagnostic]:
    diagnostics: list[HandoffDiagnostic] = []
    for t_index, track in enumerate(timeline.tracks):
        location = f"tracks[{t_index}]"
        if track.kind is HandoffTrackKind.UNKNOWN:
            diagnostics.append(
                refusal(HandoffDiagnosticCode.UNKNOWN_TRACK_KIND, location, "Track kind UNKNOWN")
            )
        for i_index, item in enumerate(track.items):
            if not isinstance(item, HandoffClip):
                continue
            item_location = f"{location}.items[{i_index}]"
            path = item.media.target_path
            if path is None:
                diagnostics.append(
                    refusal(
                        HandoffDiagnosticCode.MISSING_MEDIA_PATH,
                        item_location,
                        "xmeml has no missing-reference form; clip is not dropped",
                    )
                )
            elif path_to_file_url(path) is None:
                diagnostics.append(
                    refusal(
                        HandoffDiagnosticCode.UNSUPPORTED_PATH,
                        item_location,
                        "Relative media path cannot be written as pathurl",
                    )
                )
            for m_index, marker in enumerate(item.markers):
                diagnostics.append(
                    warning(
                        HandoffDiagnosticCode.MARKER_NOT_REPRESENTED,
                        f"{item_location}.markers[{m_index}]",
                        f"Marker color {marker.color.value} is not representable in xmeml v5",
                    )
                )
    return diagnostics


class _Builder:
    def __init__(self, timeline: HandoffTimeline) -> None:
        self.timeline = timeline
        self.rate = timeline.rate
        self.file_ids: dict[str, str] = {}
        self.clip_counter = 0

    def file(self, parent: ET.Element, media: HandoffMediaRef) -> None:
        existing = self.file_ids.get(media.media_id)
        if existing is not None:
            ET.SubElement(parent, "file", {"id": existing})
            return
        file_id = f"file-{len(self.file_ids) + 1}"
        self.file_ids[media.media_id] = file_id
        element = ET.SubElement(parent, "file", {"id": file_id})
        _leaf(element, "name", media.media_id)
        url = None if media.target_path is None else path_to_file_url(media.target_path)
        if url is None:
            raise AssertionError("pathurl must be validated by preflight")
        _leaf(element, "pathurl", url)
        _rate(element, self.rate)
        if media.available_range is not None:
            _leaf(element, "duration", str(media.available_range.end))
        if media.media_start_frame is not None:
            _timecode(element, media.media_start_frame, self.rate)

    def clipitem(self, parent: ET.Element, start: int, clip: HandoffClip) -> None:
        self.clip_counter += 1
        element = ET.SubElement(parent, "clipitem", {"id": f"clipitem-{self.clip_counter}"})
        _leaf(element, "name", clip.name)
        _leaf(element, "enabled", "TRUE" if clip.enabled else "FALSE")
        _leaf(element, "duration", str(clip.duration))
        _leaf(element, "start", str(start))
        _leaf(element, "end", str(start + clip.duration))
        _leaf(element, "in", str(clip.source_range.start))
        _leaf(element, "out", str(clip.source_range.end))
        self.file(element, clip.media)
        for marker in clip.markers:
            marker_element = ET.SubElement(element, "marker")
            _leaf(marker_element, "name", marker.name)
            _leaf(marker_element, "comment", marker.note)
            _leaf(marker_element, "in", str(marker.frame_range.start))
            _leaf(marker_element, "out", str(marker.frame_range.end))

    def track(self, parent: ET.Element, track: HandoffTrack) -> None:
        element = ET.SubElement(parent, "track")
        for start, clip in track.placements():
            self.clipitem(element, start, clip)

    def build(self) -> ET.Element:
        root = ET.Element("xmeml", {"version": "5"})
        sequence = ET.SubElement(root, "sequence", {"id": "sequence-1"})
        duration = self.timeline.duration
        _leaf(sequence, "name", self.timeline.name)
        _leaf(sequence, "duration", str(duration))
        _rate(sequence, self.rate)
        _leaf(sequence, "in", "0")
        _leaf(sequence, "out", str(duration))
        _timecode(sequence, self.timeline.start_frame, self.rate)
        media = ET.SubElement(sequence, "media")
        video = ET.SubElement(media, "video")
        for track in self.timeline.tracks:
            if track.kind is HandoffTrackKind.VIDEO:
                self.track(video, track)
        audio = ET.SubElement(media, "audio")
        for track in self.timeline.tracks:
            if track.kind is HandoffTrackKind.AUDIO:
                self.track(audio, track)
        return root


def write_xmeml(timeline: HandoffTimeline) -> XmemlWriteResult:
    """Deterministic xmeml v5 text (2-space indent, LF, trailing newline)."""
    if not isinstance(timeline, HandoffTimeline):
        raise TypeError("A HandoffTimeline is required")
    diagnostics = _preflight(timeline)
    if has_refusal(tuple(diagnostics)):
        return XmemlWriteResult(None, tuple(diagnostics))
    root = _Builder(timeline).build()
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    return XmemlWriteResult(XML_HEADER + body + "\n", tuple(diagnostics))
