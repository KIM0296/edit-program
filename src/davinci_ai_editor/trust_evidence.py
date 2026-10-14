"""Content correlation and retained reads. No native authenticity/qualification claim."""

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Literal

from .domain import TimelineObjectId
from .native_snapshot import IdentityScope, NativePlacementSnapshot, NativeTimelineSnapshot
from .temporal_mapping import NativeSnapshotRef

CANONICALIZATION = "semantic-json-v1"


def _value(value: object) -> object:
    if isinstance(value, Enum):
        return {"enum": type(value).__name__, "value": value.value}
    if value is None or type(value) in (str, int, bool):
        return value
    if isinstance(value, str):  # existing str NewTypes
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "type": type(value).__name__,
            "fields": {f.name: _value(getattr(value, f.name)) for f in fields(value)},
        }
    if isinstance(value, (tuple, list)):
        return [_value(item) for item in value]
    if isinstance(value, dict) and all(type(key) is str for key in value):
        return {key: _value(item) for key, item in value.items()}
    raise TypeError("Canonical semantic content requires typed exact values; no float/set/opaque")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        _value(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


@dataclass(frozen=True)
class PreparedArtifactRevision:
    namespace: str
    artifact_id: str
    revision_id: str
    schema_version: str
    canonicalization_version: str
    digest_algorithm: str
    content_digest: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(v, str) and v.strip()
            for v in (
                self.namespace,
                self.artifact_id,
                self.revision_id,
            )
        ):
            raise ValueError("Explicit artifact/revision identity required")
        if (self.schema_version, self.canonicalization_version, self.digest_algorithm) != (
            "prepared-semantic-v1",
            CANONICALIZATION,
            "sha256",
        ):
            raise ValueError("Unsupported artifact contract")
        if len(self.content_digest) != 64 or any(
            c not in "0123456789abcdef" for c in self.content_digest
        ):
            raise ValueError("Canonical SHA-256 hex required")
        if self.revision_id != self.content_digest:
            raise ValueError("Content-addressed revision ID cannot be reused for changed content")

    def matches(self, content: object) -> bool:
        return hashlib.sha256(canonical_bytes(content)).hexdigest() == self.content_digest


def artifact_revision(
    namespace: str, artifact_id: str, content: object
) -> PreparedArtifactRevision:
    digest = hashlib.sha256(canonical_bytes(content)).hexdigest()
    # Content-addressed revision: changing semantic content necessarily changes revision.
    return PreparedArtifactRevision(
        namespace, artifact_id, digest, "prepared-semantic-v1", CANONICALIZATION, "sha256", digest
    )


class ObservationCompleteness(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class IndependentReadEvidence:
    """Retained capture, not a command receipt. Order is producer-supplied, not a clock proof."""

    snapshot: NativeSnapshotRef
    capture: NativeTimelineSnapshot
    phase: Literal["PRE", "POST"]
    sequence: int
    scope_refs: tuple[str, ...]
    completeness: ObservationCompleteness
    source_captures: tuple[NativeTimelineSnapshot, ...]
    limitations: tuple[str, ...]
    transaction_ref: str | None = None
    after_sequence: int | None = None
    evidence_domain: Literal["PRODUCER_ASSERTION", "TEST_ONLY_SUPPORT"] = "PRODUCER_ASSERTION"
    order_domain_ref: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capture, NativeTimelineSnapshot):
            raise TypeError("An actual read capture is required, not command acknowledgment")
        if not isinstance(self.snapshot, NativeSnapshotRef) or not isinstance(
            self.completeness, ObservationCompleteness
        ):
            raise TypeError("Typed snapshot/completeness required")
        if self.phase not in ("PRE", "POST") or type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("Explicit observation phase/order required")
        if self.evidence_domain not in ("PRODUCER_ASSERTION", "TEST_ONLY_SUPPORT"):
            raise ValueError("Invalid evidence domain")
        for name in ("scope_refs", "source_captures", "limitations"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if any(not isinstance(capture, NativeTimelineSnapshot) for capture in self.source_captures):
            raise TypeError("Read evidence must retain source captures, not receipt strings")
        if any(
            not isinstance(ref, str) or not ref.strip()
            for ref in (*self.scope_refs, *self.limitations)
        ):
            raise ValueError("Explicit scope/limitation text required")

    def bound(self) -> bool:
        return (
            self.capture.timeline_ref.ref == self.snapshot.timeline_id
            and self.capture.timeline_version == self.snapshot.timeline_version
            and self.capture.state_token == self.snapshot.state_token
            and bool(self.source_captures)
            and self.capture in self.source_captures
            and bool(self.scope_refs)
        )


@dataclass(frozen=True)
class TargetCorrespondence:
    """Evidence for semantic -> execution -> result, including staging lineage.

    Native identities must resolve within retained captures. Similar names or
    geometry alone never create this record. Producers own authenticity.
    """

    artifact_revision: PreparedArtifactRevision
    semantic_object: TimelineObjectId
    semantic_snapshot: NativeSnapshotRef
    target_ref: str
    semantic_read: IndependentReadEvidence
    execution_read: IndependentReadEvidence
    semantic_placement: NativePlacementSnapshot
    execution_placement: NativePlacementSnapshot
    lineage_captures: tuple[NativeTimelineSnapshot, ...]
    result_placements: tuple[NativePlacementSnapshot, ...] = ()
    result_read: IndependentReadEvidence | None = None
    result_sources: tuple[NativePlacementSnapshot, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_revision, PreparedArtifactRevision):
            raise TypeError("Approved revision required")
        if not self.target_ref.strip():
            raise ValueError("Execution target reference required")
        object.__setattr__(self, "lineage_captures", tuple(self.lineage_captures))
        object.__setattr__(self, "result_placements", tuple(self.result_placements))
        object.__setattr__(self, "result_sources", tuple(self.result_sources))

    def admission_bound(self) -> bool:
        return (
            self.semantic_read.bound()
            and self.execution_read.bound()
            and self.semantic_read.evidence_domain == self.execution_read.evidence_domain
            and self.semantic_read.phase == self.execution_read.phase == "PRE"
            and self.semantic_read.snapshot == self.semantic_snapshot
            and self.semantic_placement in self.semantic_read.capture.placements
            and self.execution_placement in self.execution_read.capture.placements
            and self.semantic_read.capture in self.lineage_captures
            and self.execution_read.capture in self.lineage_captures
            and self.semantic_read.completeness == ObservationCompleteness.COMPLETE
            and self.execution_read.completeness == ObservationCompleteness.COMPLETE
            and self.semantic_placement.object_ref.scope
            in (IdentityScope.SESSION_LOCAL_VERIFIED, IdentityScope.PERSISTENT_VERIFIED)
            and self.execution_placement.object_ref.scope
            in (IdentityScope.SESSION_LOCAL_VERIFIED, IdentityScope.PERSISTENT_VERIFIED)
        )
