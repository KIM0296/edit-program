"""HANDOFF-001 deterministic FCP7 XML (xmeml v5) writer via xml.etree.

Element layout adapted from timeline (Chat Octopus) src/xmeml/writer.ts, MIT
License, see licenses/timeline-LICENSE.txt. Ported to Python/xml.etree with
exact integer frames; unsupported content is refused, never dropped.

Scope limits (explicit): no ``<format>``/``samplecharacteristics`` (frame size
and audio sample rate are UNKNOWN to the model), no marker colors (xmeml v5
markers have none; reported as warnings). Marker names and comments are
written (APPLY-001 candidate tokens travel in marker names).

A/V links (APPLY-001): a video clipitem and the audio clipitems that share its
media, timeline range and source range are written as one FCP7 link group:
every member carries one ``<link>`` per member (itself included) with
``linkclipref``, ``mediatype``, ``trackindex`` (1-based within the media kind)
and ``clipindex`` (1-based position in its track); audio links add
``groupindex`` 1. The link element layout is adapted from timeline (Chat
Octopus) src/xmeml/writer.ts ``writeLinkEntries``, MIT License, see
licenses/timeline-LICENSE.txt. Ambiguous groups (more than one matching video
clip) are not linked.

LAYER-001: every track is written in order with its flags (``enabled`` FALSE /
``locked`` TRUE when set), XML attributes and settings children; empty tracks
stay empty tracks. Pass-through items (generators, transitions, nested
sequences, clipitems with filters, ...) are re-emitted verbatim from their
stored subtree, interleaved with modelled clips by timeline start, with fresh
collision-free ids (``passthrough-N``; file definitions ``pt-file-N``). An item
whose stored timing disagrees with its extent is refused (``LAYER_LOSS_RISK``),
never written corrupted. Whether Resolve imports these items faithfully is
UNVERIFIED.
The written file is an Expected artifact only; importing it is a native
mutation (HOLD / manual user action) and nothing here authorizes it.
"""

import xml.etree.ElementTree as ET
from collections.abc import Iterator
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
    PassthroughItem,
    has_refusal,
    path_to_file_url,
    refusal,
    warning,
)
from .layer_xml import emit_raw, parse_raw, root_timing
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


def _passthrough_problem(item: PassthroughItem) -> str | None:
    """Why a pass-through item cannot be emitted faithfully, or ``None``."""
    try:
        start, end = root_timing(item.raw_xml)
    except (ValueError, ET.ParseError) as exc:
        return f"unparseable ({exc})"
    extent = item.timeline_range
    if extent is None:
        return None
    if start is not None and start != -1 and start != extent.start:
        return f"start {start} does not match extent {extent.start}"
    if end is not None and end != -1 and end != extent.end:
        return f"end {end} does not match extent {extent.end}"
    return None


def _preflight(timeline: HandoffTimeline) -> list[HandoffDiagnostic]:
    diagnostics: list[HandoffDiagnostic] = []
    for t_index, track in enumerate(timeline.tracks):
        location = f"tracks[{t_index}]"
        if track.kind is HandoffTrackKind.UNKNOWN:
            diagnostics.append(
                refusal(HandoffDiagnosticCode.UNKNOWN_TRACK_KIND, location, "Track kind UNKNOWN")
            )
        for p_index, pt_item in enumerate(track.passthrough):
            if pt_item.links_removed:
                diagnostics.append(
                    warning(
                        HandoffDiagnosticCode.LINK_NOT_PRESERVED,
                        f"{location}.passthrough[{p_index}]",
                        f"{pt_item.kind.value} {pt_item.label!r} is written without its "
                        f"{pt_item.links_removed} <link> reference(s); re-check its A/V link",
                    )
                )
            problem = _passthrough_problem(pt_item)
            if problem is not None:
                diagnostics.append(
                    refusal(
                        HandoffDiagnosticCode.LAYER_LOSS_RISK,
                        f"{location}.passthrough[{p_index}]",
                        f"Pass-through {pt_item.kind.value} {pt_item.label!r} cannot be written "
                        f"verbatim: {problem}",
                    )
                )
        for x_index, raw in enumerate(track.extra_xml):
            try:
                parse_raw(raw)
            except (ValueError, ET.ParseError) as exc:
                diagnostics.append(
                    refusal(
                        HandoffDiagnosticCode.LAYER_LOSS_RISK,
                        f"{location}.extra_xml[{x_index}]",
                        f"Track setting cannot be written verbatim: {exc}",
                    )
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


@dataclass(frozen=True)
class _LinkMember:
    clip_id: str
    media_type: str  # "video" | "audio"
    track_index: int  # 1-based within the media kind
    clip_index: int  # 1-based position of the clipitem in its track


_LinkKey = tuple[str, int, int, int, int]


def _ordered_tracks(timeline: HandoffTimeline) -> Iterator[tuple[str, int, HandoffTrack]]:
    """(media type, 1-based track index within kind, track) in document order."""
    for kind, media_type in ((HandoffTrackKind.VIDEO, "video"), (HandoffTrackKind.AUDIO, "audio")):
        index = 0
        for track in timeline.tracks:
            if track.kind is kind:
                index += 1
                yield media_type, index, track


_TrackEntry = tuple[int, HandoffClip | PassthroughItem]


def _track_entries(track: HandoffTrack) -> list[_TrackEntry]:
    """Modelled clips and pass-through items in document order (by timeline start).

    Pass-through items with an UNKNOWN extent keep their relative order at the end.
    """
    keyed: list[tuple[tuple[int, int, int, int], int, HandoffClip | PassthroughItem]] = []
    for order, (start, clip) in enumerate(track.placements()):
        keyed.append(((0, start, 0, order), start, clip))
    for order, item in enumerate(track.passthrough):
        extent = item.timeline_range
        start = 0 if extent is None else extent.start
        keyed.append(((0 if extent is not None else 1, start, 1, order), start, item))
    keyed.sort(key=lambda entry: entry[0])
    return [(start, value) for _, start, value in keyed]


def _link_groups(timeline: HandoffTimeline) -> dict[str, tuple[_LinkMember, ...]]:
    """clipitem id -> link group (same media, timeline range and source range).

    Clipitem ids are assigned in the same document order as :class:`_Builder`;
    ``clipindex`` counts every track item element (pass-through items included).
    """
    groups: dict[_LinkKey, list[_LinkMember]] = {}
    counter = 0
    for media_type, track_index, track in _ordered_tracks(timeline):
        for clip_index, (start, clip) in enumerate(_track_entries(track), start=1):
            if not isinstance(clip, HandoffClip):
                continue
            counter += 1
            key: _LinkKey = (
                clip.media.media_id,
                start,
                start + clip.duration,
                clip.source_range.start,
                clip.source_range.end,
            )
            member = _LinkMember(f"clipitem-{counter}", media_type, track_index, clip_index)
            groups.setdefault(key, []).append(member)
    result: dict[str, tuple[_LinkMember, ...]] = {}
    for members in groups.values():
        videos = [m for m in members if m.media_type == "video"]
        audios = [m for m in members if m.media_type == "audio"]
        if len(videos) != 1 or not audios:
            continue
        group = tuple(members)
        for member in group:
            result[member.clip_id] = group
    return result


class _Builder:
    def __init__(self, timeline: HandoffTimeline) -> None:
        self.timeline = timeline
        self.rate = timeline.rate
        self.file_ids: dict[str, str] = {}
        self.clip_counter = 0
        self.passthrough_counter = 0
        self.pt_file_ids: dict[str, str] = {}
        self.links = _link_groups(timeline)

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
        clip_id = f"clipitem-{self.clip_counter}"
        element = ET.SubElement(parent, "clipitem", {"id": clip_id})
        _leaf(element, "name", clip.name)
        _leaf(element, "enabled", "TRUE" if clip.enabled else "FALSE")
        _leaf(element, "duration", str(clip.duration))
        _leaf(element, "start", str(start))
        _leaf(element, "end", str(start + clip.duration))
        _leaf(element, "in", str(clip.source_range.start))
        _leaf(element, "out", str(clip.source_range.end))
        self.file(element, clip.media)
        for member in self.links.get(clip_id, ()):
            link = ET.SubElement(element, "link")
            _leaf(link, "linkclipref", member.clip_id)
            _leaf(link, "mediatype", member.media_type)
            _leaf(link, "trackindex", str(member.track_index))
            _leaf(link, "clipindex", str(member.clip_index))
            if member.media_type == "audio":
                _leaf(link, "groupindex", "1")
        for marker in clip.markers:
            marker_element = ET.SubElement(element, "marker")
            _leaf(marker_element, "name", marker.name)
            _leaf(marker_element, "comment", marker.note)
            _leaf(marker_element, "in", str(marker.frame_range.start))
            _leaf(marker_element, "out", str(marker.frame_range.end))

    def passthrough(self, parent: ET.Element, item: PassthroughItem) -> None:
        self.passthrough_counter += 1
        parent.append(
            emit_raw(item.raw_xml, f"passthrough-{self.passthrough_counter}", self.pt_file_ids)
        )

    def track(self, parent: ET.Element, track: HandoffTrack) -> None:
        element = ET.SubElement(parent, "track", dict(track.attributes))
        for start, entry in _track_entries(track):
            if isinstance(entry, HandoffClip):
                self.clipitem(element, start, entry)
            else:
                self.passthrough(element, entry)
        for raw in track.extra_xml:
            element.append(parse_raw(raw))
        if not track.enabled:
            _leaf(element, "enabled", "FALSE")
        if track.locked:
            _leaf(element, "locked", "TRUE")

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
