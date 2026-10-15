"""Installed 21.1 candidate reads, fixed at review time; not capability claims."""

from dataclasses import dataclass
from typing import cast

from .values import contains_opaque, freeze


@dataclass(frozen=True)
class ReadSpec:
    key: str
    owner: str
    method: str
    case_id: str
    shape: str


READS = (
    ReadSpec("product", "Resolve", "GetProductName", "RV-001", "identity"),
    ReadSpec("version", "Resolve", "GetVersion", "RV-002", "version"),
    ReadSpec("version_string", "Resolve", "GetVersionString", "RV-003", "identity"),
    ReadSpec("manager", "Resolve", "GetProjectManager", "ROOT", "object"),
    ReadSpec("library", "ProjectManager", "GetCurrentDatabase", "RV-004", "library"),
    ReadSpec("project", "ProjectManager", "GetCurrentProject", "RV-005", "object"),
    ReadSpec("project_id", "Project", "GetUniqueId", "RV-006", "identity"),
    ReadSpec("project_name", "Project", "GetName", "RV-007", "string"),
    ReadSpec("project_settings", "Project", "GetSettings", "RV-008", "map"),
    ReadSpec("timeline", "Project", "GetCurrentTimeline", "RV-009", "object"),
    ReadSpec("timeline_id", "Timeline", "GetUniqueId", "RV-010", "identity"),
    ReadSpec("timeline_name", "Timeline", "GetName", "RV-011", "string"),
    ReadSpec("timeline_start", "Timeline", "GetStartFrame", "RV-012", "integer"),
    ReadSpec("timeline_end", "Timeline", "GetEndFrame", "RV-013", "integer"),
    ReadSpec("timecode", "Timeline", "GetStartTimecode", "RV-014", "string"),
    ReadSpec("timeline_settings", "Timeline", "GetSettings", "RV-015", "map"),
    ReadSpec("track_count", "Timeline", "GetTrackCount", "RV-016", "count"),
    ReadSpec("track_name", "Timeline", "GetTrackName", "RV-017", "string"),
    ReadSpec("track_subtype", "Timeline", "GetTrackSubType", "RV-018", "string"),
    ReadSpec("track_enabled", "Timeline", "GetIsTrackEnabled", "RV-019", "boolean"),
    ReadSpec("track_locked", "Timeline", "GetIsTrackLocked", "RV-020", "boolean"),
    ReadSpec("items", "Timeline", "GetItemListInTrack", "RV-021", "objects"),
    ReadSpec("item_id", "TimelineItem", "GetUniqueId", "RV-022", "identity"),
    ReadSpec("item_type", "TimelineItem", "GetType", "RV-023", "item_type"),
    ReadSpec("start", "TimelineItem", "GetStart", "RV-024", "integer"),
    ReadSpec("end", "TimelineItem", "GetEnd", "RV-025", "integer"),
    ReadSpec("duration", "TimelineItem", "GetDuration", "RV-026", "integer"),
    ReadSpec("source_start", "TimelineItem", "GetSourceStartFrame", "RV-027", "integer"),
    ReadSpec("source_end", "TimelineItem", "GetSourceEndFrame", "RV-028", "integer"),
    ReadSpec("membership", "TimelineItem", "GetTrackTypeAndIndex", "RV-029", "membership"),
    ReadSpec("media", "TimelineItem", "GetMediaPoolItem", "RV-030", "object_or_none"),
    ReadSpec("media_unique", "MediaPoolItem", "GetUniqueId", "RV-031", "identity"),
    ReadSpec("media_id", "MediaPoolItem", "GetMediaId", "RV-032", "identity"),
    ReadSpec("properties", "MediaPoolItem", "GetClipProperty", "RV-033", "map"),
    ReadSpec("links", "TimelineItem", "GetLinkedItems", "RV-034", "objects"),
    ReadSpec("clip_enabled", "TimelineItem", "GetClipEnabled", "RV-035", "boolean"),
    ReadSpec("timeline_markers", "Timeline", "GetMarkers", "RV-036", "markers"),
    ReadSpec("item_markers", "TimelineItem", "GetMarkers", "RV-037", "markers"),
    ReadSpec("subtitle_name", "TimelineItem", "GetName", "RV-040", "string"),
)


def spec(key: str) -> ReadSpec:
    return next(r for r in READS if r.key == key)


def native_object(value: object) -> bool:
    return value is not None and type(value) not in (
        str,
        int,
        bool,
        float,
        list,
        tuple,
        dict,
        bytes,
    )


def shape_valid(shape: str, value: object) -> bool:
    if shape == "identity":
        return type(value) is str and bool(value.strip())
    if shape == "string":
        return type(value) is str
    if shape == "integer":
        return type(value) is int
    if shape == "count":
        return type(value) is int and value >= 0
    if shape == "boolean":
        return type(value) is bool
    if shape == "version":
        return (
            type(value) in (tuple, list)
            and len(cast(list[object], value)) == 5
            and all(type(v) is int for v in cast(list[object], value)[:4])
            and type(cast(list[object], value)[4]) is str
        )
    if shape == "library":
        return (
            type(value) is dict
            and all(
                type(cast(dict[str, object], value).get(k)) is str
                and bool(cast(dict[str, object], value).get(k))
                for k in ("DbType", "DbName")
            )
            and (
                "IpAddress" not in cast(dict[str, object], value)
                or type(cast(dict[str, object], value)["IpAddress"]) is str
            )
        )
    if shape == "map":
        return type(value) is dict and not contains_opaque(freeze(value))
    if shape == "membership":
        return (
            type(value) is list
            and len(cast(list[object], value)) == 2
            and cast(list[object], value)[0] in ("video", "audio", "subtitle")
            and type(cast(list[object], value)[1]) is int
            and cast(int, cast(list[object], value)[1]) >= 1
        )
    if shape == "item_type":
        return type(value) is str and value in ("video", "audio", "generator", "transition")
    if shape == "object":
        return native_object(value)
    if shape == "object_or_none":
        return value is None or native_object(value)
    if shape == "objects":
        return type(value) is list and all(native_object(v) for v in cast(list[object], value))
    if shape == "markers":
        if type(value) is not dict:
            return False
        for k, v in cast(dict[object, object], value).items():
            # Fractional/float keys need a separately approved exact representation.
            if type(k) is not int or type(v) is not dict:
                return False
            d = cast(dict[str, object], v)
            if type(d.get("duration")) is not int or any(
                type(d.get(n)) is not str for n in ("color", "name", "note")
            ):
                return False
            if "customData" in d and type(d["customData"]) is not str:
                return False
        return not contains_opaque(freeze(value))
    raise ValueError("Unknown fixed shape")
