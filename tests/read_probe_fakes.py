"""Deterministic native fakes, not production identity or runtime evidence."""

from davinci_ai_editor.probe_evidence import RuntimeProfile
from davinci_ai_editor.resolve_probe.adapter import InstalledSurface, ReadOnlyProbeAdapter
from davinci_ai_editor.resolve_probe.fixtures import (
    ASSET_HASHES,
    AssetBinding,
    FixtureInput,
    placement_roles,
)
from davinci_ai_editor.resolve_probe.model import Context, ReadProfile, RunBinding
from davinci_ai_editor.resolve_probe.surface import READS
from davinci_ai_editor.resolve_probe.values import freeze


class Native:
    def __init__(self, methods, calls):
        self.methods = methods
        self.calls = calls

    def __getattr__(self, name):
        if name not in self.methods:
            raise AttributeError(name)

        def read(*args):
            self.calls.append((name, args))
            value = self.methods[name]
            return value(*args) if callable(value) else value

        return read


def fixture_runtime(context=Context.F0, *, extra=False, reverse=False):
    calls = []
    runtime = RuntimeProfile(
        "21.1.1",
        "10",
        "Windows",
        "task020",
        "v1",
        "read-only-v1",
        "task020-v1",
        "v1",
        "not-produced",
        "ADR-033/038-v1",
    )
    profile = ReadProfile(
        runtime,
        "DaVinci Resolve",
        (21, 1, 1, 10, ""),
        "21.1.1.10",
        "AMD64",
        "test-revision",
        "a" * 64,
    )
    binding = RunBinding(
        "run-test",
        profile,
        "env",
        "registry",
        1,
        "project-id",
        freeze({"DbType": "Disk", "DbName": "Probe"}),
        "operator-session",
    )
    assets = tuple(
        AssetBinding(role, role + "-media", digest, binding.package_digest, "external-hash-proof")
        for role, digest in ASSET_HASHES.items()
    )
    fixture = FixtureInput(
        context,
        "timeline-id",
        "fixture-1",
        assets,
        "empirical-half-open-ref",
        (("timelineFrameRate", freeze("24")),),
    )
    tracks = {}
    for role in placement_roles(fixture):
        media = Native(
            {
                "GetUniqueId": role.asset_role + "-media",
                "GetMediaId": role.asset_role + "-native",
                "GetClipProperty": {"FPS": "24", "Frames": "720"},
            },
            calls,
        )
        item = Native(
            {
                "GetUniqueId": role.role,
                "GetType": role.track_type,
                "GetStart": lambda subframe=False, r=role: 86400 + r.timeline_offset.start,
                "GetEnd": lambda subframe=False, r=role: 86400 + r.timeline_offset.end,
                "GetDuration": lambda subframe=False, r=role: r.timeline_offset.duration,
                "GetSourceStartFrame": role.source_range.start,
                "GetSourceEndFrame": role.source_range.end,
                "GetTrackTypeAndIndex": [role.track_type, role.track_index],
                "GetMediaPoolItem": media,
                "GetLinkedItems": [],
                "GetClipEnabled": True,
                "GetMarkers": {},
            },
            calls,
        )
        tracks.setdefault((role.track_type, role.track_index), []).append(item)
    if context == Context.F0:
        for video, audio in zip(tracks[("video", 1)], tracks[("audio", 1)], strict=True):
            video.methods["GetLinkedItems"] = [audio]
            audio.methods["GetLinkedItems"] = [video]
    if extra:
        tracks[("video", 1)].append(tracks[("video", 1)][0])
    if reverse:
        for items in tracks.values():
            items.reverse()
    timeline = Native(
        {
            "GetUniqueId": "timeline-id",
            "GetName": "diagnostic-name",
            "GetStartFrame": 86400,
            "GetEndFrame": 86400 + max(r.timeline_offset.end for r in placement_roles(fixture)),
            "GetStartTimecode": "01:00:00:00",
            "GetSettings": {"timelineFrameRate": "24"},
            "GetMarkers": {},
            "GetTrackCount": lambda kind: (
                2
                if context == Context.F2 and kind != "subtitle"
                else 1
                if kind != "subtitle"
                else 0
            ),
            "GetTrackName": lambda kind, index: f"{kind}/{index}",
            "GetTrackSubType": lambda kind, index: "stereo" if kind == "audio" else "",
            "GetIsTrackEnabled": lambda kind, index: not (context == Context.F2 and index == 2),
            "GetIsTrackLocked": lambda kind, index: context == Context.F2 and kind == "audio",
            "GetItemListInTrack": lambda kind, index: tracks.get((kind, index), []),
        },
        calls,
    )
    project = Native(
        {
            "GetUniqueId": "project-id",
            "GetName": "Probe",
            "GetSettings": {"timelineFrameRate": "24"},
            "GetCurrentTimeline": timeline,
        },
        calls,
    )
    manager = Native(
        {"GetCurrentDatabase": {"DbType": "Disk", "DbName": "Probe"}, "GetCurrentProject": project},
        calls,
    )
    resolve = Native(
        {
            "GetProductName": "DaVinci Resolve",
            "GetVersion": [21, 1, 1, 10, ""],
            "GetVersionString": "21.1.1.10",
            "GetProjectManager": manager,
        },
        calls,
    )
    installed = InstalledSurface("a" * 64, tuple((r.owner, r.method) for r in READS))
    adapter = ReadOnlyProbeAdapter(lambda: resolve, installed)
    return adapter, binding, fixture, calls, resolve, project, timeline, tracks
