"""LAYER-001 raw xmeml subtree helpers for pass-through items (stdlib ``xml.etree`` only).

A pass-through item keeps the original element subtree of a track item the
model does not understand (generator / title, transition, nested sequence,
clipitem with filters, ...). The subtree is stored as a canonical string so it
can live inside frozen, digestible dataclasses:

- whitespace-only text and tails are removed;
- the root ``id`` attribute is removed and every other ``id`` inside the
  subtree is renamed ``n1``, ``n2``, ... in document order (``linkclipref``
  text inside the subtree follows the rename), so NLE renumbering on re-export
  does not change the canonical form;
- the root's direct ``<link>`` children are removed (they point at clipitem ids
  of the source document that a newly written file does not keep; the count is
  reported so the confirmation can ask the editor to re-check the link);
- ``<file id=…/>`` references are replaced by a copy of the file definition and
  file ids are removed (the writer assigns fresh, collision-free ids).

Only the root's direct ``start``/``end`` (and, for a 1:1 cut, ``in``/``out``/
``duration`` and the root's direct markers) are ever rewritten. Nothing else in
the subtree is touched, so effects, keyframes, generator parameters and nested
content are re-emitted verbatim.

Input to :func:`parse_raw` is always our own serialization (``ET.tostring``),
never untrusted text; it is still refused if it contains a DOCTYPE or entity
declaration.
"""

import copy
import xml.etree.ElementTree as ET
from collections.abc import Mapping

from .domain import FrameRange


def strip_whitespace(element: ET.Element) -> None:
    for node in element.iter():
        if node.text is not None and not node.text.strip():
            node.text = None
        if node.tail is not None and not node.tail.strip():
            node.tail = None


def serialize(element: ET.Element) -> str:
    return ET.tostring(element, encoding="unicode", short_empty_elements=True)


def parse_raw(raw: str) -> ET.Element:
    if "<!" in raw:
        raise ValueError("Pass-through XML must not contain declarations")
    return ET.fromstring(raw)


def canonical_subtree(
    element: ET.Element, file_definitions: Mapping[str, ET.Element]
) -> tuple[str, int]:
    """(canonical raw XML, number of root ``<link>`` children removed)."""
    root = copy.deepcopy(element)
    root.attrib.pop("id", None)
    links = [child for child in root if child.tag == "link"]
    for link in links:
        root.remove(link)
    for node in list(root.iter("file")):
        file_id = node.get("id")
        if len(node) == 0 and file_id is not None and file_id in file_definitions:
            definition = file_definitions[file_id]
            for child in definition:
                node.append(copy.deepcopy(child))
        node.attrib.pop("id", None)
    mapping: dict[str, str] = {}
    for node in root.iter():
        if node is root or node.tag == "file":
            continue
        old = node.get("id")
        if old is not None:
            mapping.setdefault(old, f"n{len(mapping) + 1}")
            node.set("id", mapping[old])
    for ref in root.iter("linkclipref"):
        text = (ref.text or "").strip()
        if text in mapping:
            ref.text = mapping[text]
    root.tail = None
    strip_whitespace(root)
    return serialize(root), len(links)


def child_int(element: ET.Element, tag: str) -> int | None:
    child = element.find(tag)
    if child is None:
        return None
    raw = (child.text or "").strip()
    try:
        return int(raw)
    except ValueError:
        return None


def _set_child_int(element: ET.Element, tag: str, value: int) -> None:
    child = element.find(tag)
    if child is not None:
        child.text = str(value)


def root_timing(raw: str) -> tuple[int | None, int | None]:
    """The root's direct ``start`` / ``end`` values (``-1`` kept as is)."""
    root = parse_raw(raw)
    return child_int(root, "start"), child_int(root, "end")


def shifted_raw(raw: str, delta: int) -> str:
    """Offset the root's timeline ``start``/``end`` by ``delta`` (``-1`` stays ``-1``)."""
    if delta == 0:
        return raw
    root = parse_raw(raw)
    for tag in ("start", "end"):
        value = child_int(root, tag)
        if value is not None and value != -1:
            _set_child_int(root, tag, value + delta)
    return serialize(root)


def raw_markers(raw: str) -> tuple[tuple[FrameRange, str], ...]:
    """The root's direct markers as (source-relative range, name); malformed ones skipped."""
    root = parse_raw(raw)
    result: list[tuple[FrameRange, str]] = []
    for marker in root.findall("marker"):
        start = child_int(marker, "in")
        end = child_int(marker, "out")
        if start is None or start < 0:
            continue
        if end is None or end == -1:
            end = start + 1
        if end <= start:
            continue
        result.append((FrameRange(start, end), (marker.findtext("name") or "").strip()))
    return tuple(result)


def has_unparsed_markers(raw: str) -> bool:
    root = parse_raw(raw)
    return len(root.findall("marker")) != len(raw_markers(raw))


def cut_piece_raw(raw: str, timeline_start: int, source: FrameRange) -> str:
    """One piece of a 1:1 clipitem: new timing, source in/out, markers inside the piece only."""
    root = parse_raw(raw)
    _set_child_int(root, "start", timeline_start)
    _set_child_int(root, "end", timeline_start + source.duration)
    _set_child_int(root, "in", source.start)
    _set_child_int(root, "out", source.end)
    _set_child_int(root, "duration", source.duration)
    for marker in root.findall("marker"):
        start = child_int(marker, "in")
        end = child_int(marker, "out")
        if start is None:
            root.remove(marker)
            continue
        if end is None or end == -1:
            end = start + 1
        if not (source.start <= start and end <= source.end):
            root.remove(marker)
    return serialize(root)


def content_key(raw: str, tags: tuple[str, ...] = ("start", "end")) -> str:
    """Canonical content ignoring only the root's direct timing children ``tags``."""
    root = parse_raw(raw)
    for tag in tags:
        child = root.find(tag)
        if child is not None:
            root.remove(child)
    return serialize(root)


def marker_raw_at(raw: str, frame_range: FrameRange) -> str:
    """A ``<marker>`` subtree moved to ``frame_range`` (timeline frames).

    ``in`` becomes the new start; ``out`` is rewritten only when the original
    carried a real out point (a point marker's ``-1`` / absent out is kept).
    """
    root = parse_raw(raw)
    _set_child_int(root, "in", frame_range.start)
    out = child_int(root, "out")
    if out is not None and out != -1:
        _set_child_int(root, "out", frame_range.end)
    return serialize(root)


def append_links(element: ET.Element, links: list[tuple[str, str, int, int]]) -> None:
    """Append FCP7 ``<link>`` children: (linkclipref, mediatype, trackindex, clipindex)."""
    for ref, media_type, track_index, clip_index in links:
        link = ET.SubElement(element, "link")
        for tag, text in (
            ("linkclipref", ref),
            ("mediatype", media_type),
            ("trackindex", str(track_index)),
            ("clipindex", str(clip_index)),
        ):
            ET.SubElement(link, tag).text = text
        if media_type == "audio":
            ET.SubElement(link, "groupindex").text = "1"


def emit_raw(raw: str, element_id: str, file_ids: dict[str, str]) -> ET.Element:
    """Element ready to insert into a written document, with collision-free ids.

    The root gets ``element_id``; nested ids are prefixed with it (``linkclipref``
    text follows); every file definition gets a stable ``pt-file-N`` id shared by
    identical definitions across the document (``file_ids`` is updated).
    """
    root = parse_raw(raw)
    root.set("id", element_id)
    mapping: dict[str, str] = {}
    for node in root.iter():
        if node is root or node.tag == "file":
            continue
        old = node.get("id")
        if old is not None:
            mapping[old] = f"{element_id}-{old}"
            node.set("id", mapping[old])
    for ref in root.iter("linkclipref"):
        text = (ref.text or "").strip()
        if text in mapping:
            ref.text = mapping[text]
    for node in root.iter("file"):
        node.attrib.pop("id", None)
        key = serialize(node)
        if key not in file_ids:
            file_ids[key] = f"pt-file-{len(file_ids) + 1}"
        node.set("id", file_ids[key])
    return root
