"""Immutable runtime evidence axes. No support is inferred at construction."""

import re
from dataclasses import dataclass
from enum import Enum

from ..probe_evidence import RuntimeProfile
from .values import NativeValue

APPROVED_PACKAGE_DIGEST = "17b5b007df4f328a414505e68b395bab4f466b72a207e93a4f006595cbc375de"


def text(value: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError("Nonempty reference required")


def positive(value: int) -> None:
    if type(value) is not int or value < 1:
        raise ValueError("Positive exact integer required")


class RuntimeResult(str, Enum):
    SUPPORTED_STABLE = "SUPPORTED_STABLE"
    SUPPORTED_UNSTABLE = "SUPPORTED_UNSTABLE"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class FixtureResult(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    INCOMPLETE = "INCOMPLETE"
    UNSTABLE = "UNSTABLE"
    UNSUPPORTED_REQUIRED_FIELD = "UNSUPPORTED_REQUIRED_FIELD"
    ABORTED = "ABORTED"
    STALE = "STALE"


class Context(str, Enum):
    F0 = "F0_BASIC"
    F1 = "F1_REPEATED_MEDIA"
    F2 = "F2_TRACK_STATE"
    F3 = "F3_MARKER_SUBTITLE"
    F4_A = "F4_IDENTITY_BOUNDARY/timeline-A"
    F4_B = "F4_IDENTITY_BOUNDARY/timeline-B"


@dataclass(frozen=True)
class ReadProfile:
    runtime: RuntimeProfile
    product: str
    version: tuple[int | str, ...]
    version_string: str
    architecture: str
    adapter_revision: str
    stub_sha256: str
    normalization_version: str = "task020-order-only-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.runtime, RuntimeProfile):
            raise TypeError("RuntimeProfile required")
        object.__setattr__(self, "version", tuple(self.version))
        if (
            len(self.version) != 5
            or any(type(v) is not int for v in self.version[:4])
            or type(self.version[4]) is not str
        ):
            raise ValueError("Exact Resolve version tuple required")
        for v in (
            self.product,
            self.version_string,
            self.architecture,
            self.adapter_revision,
            self.stub_sha256,
            self.normalization_version,
        ):
            text(v)
        if re.fullmatch("[0-9a-f]{64}", self.stub_sha256) is None:
            raise ValueError("Installed stub digest required")


@dataclass(frozen=True)
class RunBinding:
    validation_run_id: str
    profile: ReadProfile
    environment_ref: str
    registry_ref: str
    project_generation: int
    project_id: str
    library: NativeValue
    operator_session: str
    package_digest: str = APPROVED_PACKAGE_DIGEST
    catalog_version: str = "v1"
    runtime_policy: str = "ADR-033/038-v1"

    def __post_init__(self) -> None:
        positive(self.project_generation)
        for value in (
            self.validation_run_id,
            self.environment_ref,
            self.registry_ref,
            self.project_id,
            self.operator_session,
            self.catalog_version,
            self.runtime_policy,
        ):
            text(value)
        if not isinstance(self.profile, ReadProfile) or not isinstance(self.library, NativeValue):
            raise TypeError("Typed profile/library required")
        if self.package_digest != APPROVED_PACKAGE_DIGEST:
            raise ValueError("Approved canonical package required")
        if self.catalog_version != "v1" or self.runtime_policy != "ADR-033/038-v1":
            raise ValueError("Unsupported qualification contract")


@dataclass(frozen=True)
class ReadObservation:
    case_id: str
    subject: str
    method: str
    args: NativeValue
    raw: NativeValue | None
    valid: bool
    semantic_value: NativeValue | None
    error: str | None = None
    documented_absent: bool = False

    def __post_init__(self) -> None:
        for value in (self.case_id, self.subject, self.method):
            text(value)
        if type(self.valid) is not bool or type(self.documented_absent) is not bool:
            raise TypeError("Explicit observation flags required")
        if not isinstance(self.args, NativeValue) or (
            self.raw is not None and not isinstance(self.raw, NativeValue)
        ):
            raise TypeError("Typed raw evidence required")
        if self.semantic_value is not None and not isinstance(self.semantic_value, NativeValue):
            raise TypeError("Immutable typed semantic value required")
        if self.error is not None:
            text(self.error)
        if self.valid != (self.semantic_value is not None):
            raise ValueError("Invalid observation cannot contain an authoritative normalized value")
        if self.valid and (self.error is not None or self.documented_absent or self.raw is None):
            raise ValueError("Failed/absent read cannot be valid")

    @property
    def key(self) -> tuple[str, str]:
        return self.subject, self.case_id


@dataclass(frozen=True)
class ProbeSnapshot:
    binding: RunBinding
    context: Context
    timeline_id: str
    sequence: int
    reads: tuple[ReadObservation, ...]
    start_fence: tuple[ReadObservation, ...]
    end_fence: tuple[ReadObservation, ...]
    findings: tuple[str, ...] = ()
    operator_interference: bool = False

    def __post_init__(self) -> None:
        positive(self.sequence)
        text(self.timeline_id)
        if not isinstance(self.binding, RunBinding) or not isinstance(self.context, Context):
            raise TypeError("Bound snapshot required")
        if type(self.operator_interference) is not bool:
            raise TypeError("Explicit operator state required")
        for attr in ("reads", "start_fence", "end_fence"):
            values = tuple(getattr(self, attr))
            if any(not isinstance(v, ReadObservation) for v in values):
                raise TypeError("Typed observations required")
            object.__setattr__(self, attr, values)
        object.__setattr__(self, "findings", tuple(self.findings))
        for finding in self.findings:
            text(finding)

    @property
    def semantic_fields(self) -> tuple[tuple[str, str, NativeValue | None], ...]:
        return tuple(
            sorted(
                ((r.subject, r.case_id, r.semantic_value) for r in self.reads),
                key=lambda row: (row[0], row[1], repr(row[2])),
            )
        )

    @property
    def consistent(self) -> bool:
        def values(
            reads: tuple[ReadObservation, ...],
        ) -> tuple[tuple[str, str, NativeValue | None], ...]:
            return tuple((r.subject, r.case_id, r.semantic_value) for r in reads)

        return (
            bool(self.start_fence)
            and all(r.valid for r in (*self.start_fence, *self.end_fence))
            and values(self.start_fence) == values(self.end_fence)
        )

    @property
    def complete(self) -> bool:
        # Structural completeness only; per-field stability is derived after S1.
        mandatory = {f"RV-{n:03d}" for n in range(1, 17)}
        return (
            mandatory <= {r.case_id for r in self.reads}
            and not self.findings
            and all(r.valid for r in self.reads)
            and self.consistent
        )

    def field(self, subject: str, case_id: str) -> NativeValue | None:
        matches = [r for r in self.reads if r.subject == subject and r.case_id == case_id]
        return matches[0].semantic_value if len(matches) == 1 else None
