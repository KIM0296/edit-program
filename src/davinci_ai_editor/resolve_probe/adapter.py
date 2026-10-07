"""Fixed Resolve read boundary with independently reacquired root fences."""

import ast
from collections.abc import Callable
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from typing import cast

from .model import Context, ProbeSnapshot, ReadObservation, RunBinding
from .surface import READS, ReadSpec, shape_valid, spec
from .values import freeze, semantic


@dataclass(frozen=True)
class InstalledSurface:
    stub_sha256: str
    methods: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "methods", tuple(sorted(tuple(p) for p in self.methods)))
        if len(self.stub_sha256) != 64:
            raise ValueError("Exact stub hash required")


def inspect_stub(path: Path) -> InstalledSurface:
    raw = path.read_bytes()
    tree = ast.parse(raw.decode("utf-8-sig"))
    allowed = {(r.owner, r.method) for r in READS}
    methods = tuple(
        (cls.name, node.name)
        for cls in tree.body
        if isinstance(cls, ast.ClassDef)
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and (cls.name, node.name) in allowed
    )
    return InstalledSurface(sha256(raw).hexdigest(), methods)


class ReadOnlyProbeAdapter:
    """Only discovery and capture are public; no arbitrary native command entry point."""

    def __init__(self, root_factory: Callable[[], object | None], installed: InstalledSurface):
        self._root_factory = root_factory
        self._installed = installed

    def _read(
        self, target: object | None, read: ReadSpec, subject: str, *args: object
    ) -> tuple[object | None, ReadObservation]:
        if read not in READS:
            raise ValueError("Unreviewed native read")
        if (read.owner, read.method) not in self._installed.methods:
            return None, ReadObservation(
                read.case_id, subject, read.method, freeze(args), None, False, None, None, True
            )
        try:
            if target is None:
                raise RuntimeError("OBJECT_UNAVAILABLE")
            method = getattr(target, read.method)
            if not callable(method):
                raise TypeError("AMBIGUOUS_NONCALLABLE_SURFACE")
            raw = cast(Callable[..., object], method)(*args)
            valid = shape_valid(read.shape, raw)
            observation = ReadObservation(
                read.case_id,
                subject,
                read.method,
                freeze(args),
                freeze(raw),
                valid,
                semantic(freeze(raw)) if valid else None,
            )
            return raw, observation
        except Exception as error:  # noqa: BLE001 - preserve ambiguous native bridge errors
            return None, ReadObservation(
                read.case_id,
                subject,
                read.method,
                freeze(args),
                None,
                False,
                None,
                type(error).__name__ + ": " + str(error),
            )

    def _root(self) -> object | None:
        return self._root_factory()

    def discover_runtime(self) -> tuple[ReadObservation, ...]:
        """Nonqualifying discovery, not a support verdict."""
        try:
            root = self._root()
        except Exception as error:  # noqa: BLE001 - preserve ambiguous native bridge errors
            return (
                ReadObservation(
                    "ROOT",
                    "resolve",
                    "scriptapp",
                    freeze(("Resolve",)),
                    None,
                    False,
                    None,
                    type(error).__name__ + ": " + str(error),
                ),
            )
        return tuple(
            self._read(root, spec(key), "resolve")[1]
            for key in ("product", "version", "version_string")
        )

    def _fence(self) -> tuple[object | None, object | None, tuple[ReadObservation, ...]]:
        reads: list[ReadObservation] = []
        try:
            root = self._root()
        except Exception as error:  # noqa: BLE001 - preserve ambiguous native bridge errors
            return (
                None,
                None,
                (
                    ReadObservation(
                        "ROOT",
                        "resolve",
                        "scriptapp",
                        freeze(("Resolve",)),
                        None,
                        False,
                        None,
                        type(error).__name__ + ": " + str(error),
                    ),
                ),
            )

        def read(target: object | None, key: str, subject: str, *args: object) -> object | None:
            raw, observation = self._read(target, spec(key), subject, *args)
            reads.append(observation)
            return raw

        for key in ("product", "version", "version_string"):
            read(root, key, "resolve")
        manager = read(root, "manager", "resolve")
        read(manager, "library", "project-manager")
        project = read(manager, "project", "project-manager")
        read(project, "project_id", "project")
        read(project, "project_name", "project")
        read(project, "project_settings", "project")
        timeline = read(project, "timeline", "project")
        for key in (
            "timeline_id",
            "timeline_name",
            "timeline_start",
            "timeline_end",
            "timecode",
            "timeline_settings",
            "timeline_markers",
        ):
            read(timeline, key, "timeline")
        for track_type in ("video", "audio", "subtitle"):
            read(timeline, "track_count", "tracks/" + track_type, track_type)
        return project, timeline, tuple(reads)

    def capture(
        self,
        binding: RunBinding,
        context: Context,
        timeline_id: str,
        sequence: int,
        *,
        operator_interference: bool = False,
    ) -> ProbeSnapshot:
        _, timeline, start = self._fence()
        reads = list(start)
        findings: list[str] = []
        if binding.profile.stub_sha256 != self._installed.stub_sha256:
            findings.append("STALE_INSTALLED_SURFACE")

        def get(target: object | None, key: str, subject: str, *args: object) -> object | None:
            raw, observation = self._read(target, spec(key), subject, *args)
            reads.append(observation)
            return raw

        # Gate body reads on exact root/profile/project/library/current timeline observations.
        checks = (
            ("resolve", "RV-001", freeze(binding.profile.product)),
            ("resolve", "RV-002", freeze(list(binding.profile.version))),
            ("resolve", "RV-003", freeze(binding.profile.version_string)),
            ("project-manager", "RV-004", semantic(binding.library)),
            ("project", "RV-006", freeze(binding.project_id)),
            ("timeline", "RV-010", freeze(timeline_id)),
        )
        for subject, case, expected in checks:
            obs = [r for r in start if r.key == (subject, case)]
            if not obs or not obs[0].valid:
                findings.append("UNVERIFIED_CONTEXT:" + case)
            elif obs[0].semantic_value != expected:
                # Version container type is preserved; tuple/list mismatch is not silently fixed.
                findings.append("STALE_CONTEXT:" + case)
        if not findings:
            identities: list[str] = []
            for track_type in ("video", "audio", "subtitle"):
                count_obs = next(r for r in start if r.key == ("tracks/" + track_type, "RV-016"))
                if not count_obs.valid or count_obs.raw is None:
                    findings.append("INCOMPLETE_TRACK_ENUMERATION:" + track_type)
                    continue
                count = count_obs.raw.scalar
                assert type(count) is int
                if count > 10000:
                    findings.append("UNSUPPORTED_ENUMERATION_BOUND")
                    continue
                for index in range(1, count + 1):
                    subject = f"track/{track_type}/{index}"
                    for key in ("track_name", "track_subtype", "track_enabled", "track_locked"):
                        get(timeline, key, subject, track_type, index)
                    items = get(timeline, "items", subject, track_type, index)
                    enumeration_index = len(reads) - 1
                    enum = reads[enumeration_index]
                    if not enum.valid or not isinstance(items, list):
                        findings.append("INCOMPLETE_ITEM_ENUMERATION:" + subject)
                        continue
                    member_ids: list[str] = []
                    for ordinal, item in enumerate(items):
                        item_id, id_obs = self._read(item, spec("item_id"), "pending")
                        item_subject = (
                            "item/" + item_id
                            if type(item_id) is str and item_id.strip()
                            else f"unresolved/{subject}/{ordinal}"
                        )
                        reads.append(replace(id_obs, subject=item_subject))
                        if id_obs.valid:
                            assert isinstance(item_id, str)
                            member_ids.append(item_id)
                            identities.append(item_id)
                        else:
                            findings.append("UNKNOWN_PLACEMENT_ID")
                        if track_type != "subtitle":
                            get(item, "item_type", item_subject)
                        for key in ("start", "end", "duration"):
                            get(item, key, item_subject, False)
                        get(item, "membership", item_subject)
                        get(item, "clip_enabled", item_subject)
                        get(item, "item_markers", item_subject)
                        if track_type == "subtitle":
                            get(item, "subtitle_name", item_subject)
                            # Exact timing values remain RV-024/025/026; no subtitle coercion.
                            continue
                        for key in ("source_start", "source_end"):
                            get(item, key, item_subject)
                        media = get(item, "media", item_subject)
                        media_index = len(reads) - 1
                        if media is None:
                            findings.append("MISSING_MEDIA_BINDING:" + item_subject)
                        else:
                            media_id = get(media, "media_unique", item_subject)
                            get(media, "media_id", item_subject)
                            get(media, "properties", item_subject)
                            observation = reads[media_index]
                            valid = observation.valid and type(media_id) is str and bool(media_id)
                            reads[media_index] = replace(
                                observation,
                                valid=valid,
                                semantic_value=freeze(media_id) if valid else None,
                            )
                        links = get(item, "links", item_subject)
                        link_index = len(reads) - 1
                        link_ids: list[str] = []
                        if isinstance(links, list) and reads[link_index].valid:
                            for link in links:
                                linked_id, linked_obs = self._read(
                                    link, spec("item_id"), "linked-of/" + item_subject
                                )
                                # Retain independent linked-ID raw reads (also unordered).
                                reads.append(linked_obs)
                                if linked_obs.valid and isinstance(linked_id, str):
                                    link_ids.append(linked_id)
                            valid = len(link_ids) == len(links) and len(set(link_ids)) == len(
                                link_ids
                            )
                            reads[link_index] = replace(
                                reads[link_index],
                                valid=valid,
                                semantic_value=freeze(sorted(link_ids)) if valid else None,
                            )
                    valid = len(member_ids) == len(items) and len(set(member_ids)) == len(
                        member_ids
                    )
                    reads[enumeration_index] = replace(
                        enum,
                        valid=valid,
                        semantic_value=freeze(sorted(member_ids)) if valid else None,
                    )
            if len(set(identities)) != len(identities):
                findings.append("AMBIGUOUS_DUPLICATE_PLACEMENT_ID")
        _, _, end = self._fence()
        if operator_interference:
            findings.append("OPERATOR_INTERFERENCE")
        # Tier C missing state is explicit metadata, never false/absence.
        return ProbeSnapshot(
            binding,
            context,
            timeline_id,
            sequence,
            tuple(reads),
            start,
            end,
            tuple(findings),
            operator_interference,
        )
