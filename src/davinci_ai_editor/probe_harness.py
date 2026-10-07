"""ADR-031/035 immutable fake control plane. No native callbacks or registry truth acquisition."""

from dataclasses import dataclass, replace
from enum import Enum
from typing import TypeVar

from .probe_evidence import (
    ApplicabilityDomain,
    CapabilityVerificationPolicy,
    NativeInvocationSpec,
    ProbeFixtureClass,
    ProbeObservationScope,
    RuntimeProfile,
    ScopeCompleteness,
    SubjectState,
)

T = TypeVar("T")


def _typed(value: object, kind: type[object]) -> None:
    if not isinstance(value, kind):
        raise TypeError(f"Expected {kind.__name__}")


def _text(value: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError("Nonempty opaque reference required")


def _positive(value: int) -> None:
    if type(value) is not int or value < 1:
        raise ValueError("Positive integer generation required")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _tuple(values: tuple[T, ...], kind: type[T]) -> tuple[T, ...]:
    result = tuple(values)
    for value in result:
        _typed(value, kind)
    return result


def _refs(values: tuple[str, ...]) -> tuple[str, ...]:
    result = tuple(values)
    for value in result:
        _text(value)
    _unique(result)
    return tuple(sorted(result))


def _unique(values: tuple[str, ...]) -> None:
    _require(len(set(values)) == len(values), "Duplicate identity")


def _states(values: tuple[SubjectState, ...]) -> tuple[SubjectState, ...]:
    result = _tuple(values, SubjectState)
    _unique(tuple(s.subject_ref for s in result))
    return tuple(sorted(result, key=lambda s: s.subject_ref))


class ProjectGenerationStatus(str, Enum):
    VERIFIED_CLEAN = "VERIFIED_CLEAN"
    REVERIFY_REQUIRED = "REVERIFY_REQUIRED"
    CONTAMINATED = "CONTAMINATED"
    RETIRED = "RETIRED"


class ProbeHarnessState(str, Enum):
    DISARMED = "DISARMED"
    ENVIRONMENT_VERIFIED = "ENVIRONMENT_VERIFIED"
    FIXTURE_VERIFIED = "FIXTURE_VERIFIED"
    ARMED_FOR_ONE_RUN = "ARMED_FOR_ONE_RUN"
    INVOCATION_ATTEMPTED = "INVOCATION_ATTEMPTED"
    OBSERVING = "OBSERVING"
    SEALED = "SEALED"
    QUARANTINED = "QUARANTINED"
    LOCKED_DOWN = "LOCKED_DOWN"


class ProbeRunMode(str, Enum):
    QUALIFYING = "QUALIFYING"
    EXPLORATORY = "EXPLORATORY"


class EnvironmentVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    STALE = "STALE"
    MISMATCH = "MISMATCH"
    INCOMPLETE = "INCOMPLETE"
    CONTAMINATED = "CONTAMINATED"


class FixtureLifecycleState(str, Enum):
    DEFINED = "DEFINED"
    MATERIALIZING = "MATERIALIZING"
    MATERIALIZED = "MATERIALIZED"
    VERIFYING = "VERIFYING"
    CLEAN_VERIFIED = "CLEAN_VERIFIED"
    LEASED_FOR_PROBE = "LEASED_FOR_PROBE"
    MUTATED = "MUTATED"
    OBSERVED = "OBSERVED"
    SEALED = "SEALED"
    DISCARDED = "DISCARDED"
    INVALID = "INVALID"
    DIRTY = "DIRTY"
    QUARANTINED = "QUARANTINED"
    ABORTED = "ABORTED"


class FixtureVerificationStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    INCOMPLETE = "INCOMPLETE"
    STALE = "STALE"


class ProbeRunState(str, Enum):
    PREPARING = "PREPARING"
    PRECHECKING = "PRECHECKING"
    ARMED = "ARMED"
    INVOKING = "INVOKING"
    OBSERVING = "OBSERVING"
    SEALED = "SEALED"
    TERMINAL = "TERMINAL"


class ProbeRunOutcome(str, Enum):
    NONE = "NONE"
    PASS_OBSERVED = "PASS_OBSERVED"
    FAIL_OBSERVED = "FAIL_OBSERVED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVALID_FIXTURE = "INVALID_FIXTURE"
    CONTAINMENT_FAILURE = "CONTAINMENT_FAILURE"
    ABORTED = "ABORTED"
    HARNESS_ERROR = "HARNESS_ERROR"


class ContainmentClass(str, Enum):
    CLEAN = "CLEAN"
    UNEXPECTED_FIXTURE_LOCAL = "UNEXPECTED_FIXTURE_LOCAL"
    PROJECT_LEVEL_CONTAMINATION = "PROJECT_LEVEL_CONTAMINATION"
    ENVIRONMENT_UNCERTAIN = "ENVIRONMENT_UNCERTAIN"


class NoFurtherMutationGate(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"


class NativeInvocationOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class GateFinding(str, Enum):
    LOCKED_DOWN = "LOCKED_DOWN"
    ENVIRONMENT_MISMATCH = "ENVIRONMENT_MISMATCH"
    GENERATION_INELIGIBLE = "GENERATION_INELIGIBLE"
    ENVIRONMENT_UNVERIFIED = "ENVIRONMENT_UNVERIFIED"
    FIXTURE_UNVERIFIED = "FIXTURE_UNVERIFIED"
    LEASE_INVALID = "LEASE_INVALID"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    PROFILE_CHANGED = "PROFILE_CHANGED"
    CASE_DOMAIN_CHANGED = "CASE_DOMAIN_CHANGED"
    SCOPE_CHANGED = "SCOPE_CHANGED"
    CONTAINMENT_CHANGED = "CONTAINMENT_CHANGED"
    INVOCATION_NOT_ALLOWED = "INVOCATION_NOT_ALLOWED"
    AUTHORIZATION_CONSUMED = "AUTHORIZATION_CONSUMED"
    MODE_NOT_ALLOWED = "MODE_NOT_ALLOWED"
    CONTRACT_UNSUPPORTED = "CONTRACT_UNSUPPORTED"
    OBSERVATION_MISMATCH = "OBSERVATION_MISMATCH"


@dataclass(frozen=True)
class RegisteredProbeEnvironment:
    environment_ref: str
    registry_ref: str
    registry_generation: int
    probe_project_ref: str
    project_generation: int
    fixture_catalog_ref: str
    fixture_catalog_version: str
    profile: RuntimeProfile
    harness_contract_version: str = "v1"
    disposable: bool = True
    isolated: bool = True
    production: bool = False
    authoritative: bool = False

    def __post_init__(self) -> None:
        for ref in (
            self.environment_ref,
            self.registry_ref,
            self.probe_project_ref,
            self.fixture_catalog_ref,
            self.fixture_catalog_version,
            self.harness_contract_version,
        ):
            _text(ref)
        _positive(self.registry_generation)
        _positive(self.project_generation)
        _typed(self.profile, RuntimeProfile)
        for flag in (self.disposable, self.isolated, self.production, self.authoritative):
            if type(flag) is not bool:
                raise TypeError("Explicit isolation classification required")
        _require(
            self.disposable and self.isolated and not self.production and not self.authoritative,
            "Working/production or non-isolated project cannot register for probes",
        )


ProbeEnvironmentBinding = RegisteredProbeEnvironment


@dataclass(frozen=True)
class EnvironmentFacts:
    registration: RegisteredProbeEnvironment
    project_ref: str
    timeline_ref: str
    profile: RuntimeProfile
    fingerprint_ref: str

    def __post_init__(self) -> None:
        _typed(self.registration, RegisteredProbeEnvironment)
        _typed(self.profile, RuntimeProfile)
        for ref in (self.project_ref, self.timeline_ref, self.fingerprint_ref):
            _text(ref)


@dataclass(frozen=True)
class EnvironmentVerification:
    verification_ref: str
    facts: EnvironmentFacts
    status: EnvironmentVerificationStatus
    independent_read_ref: str

    def __post_init__(self) -> None:
        _text(self.verification_ref)
        _text(self.independent_read_ref)
        _typed(self.facts, EnvironmentFacts)
        _typed(self.status, EnvironmentVerificationStatus)


@dataclass(frozen=True)
class FixtureAsset:
    asset_ref: str
    content_hash: str
    canonical_metadata_ref: str

    def __post_init__(self) -> None:
        for ref in (self.asset_ref, self.content_hash, self.canonical_metadata_ref):
            _text(ref)


@dataclass(frozen=True)
class FixtureAssetManifest:
    manifest_ref: str
    version: str
    assets: tuple[FixtureAsset, ...]

    def __post_init__(self) -> None:
        _text(self.manifest_ref)
        _text(self.version)
        assets = tuple(sorted(_tuple(self.assets, FixtureAsset), key=lambda a: a.asset_ref))
        _require(bool(assets), "Dedicated canonical assets required")
        _unique(tuple(a.asset_ref for a in assets))
        object.__setattr__(self, "assets", assets)


@dataclass(frozen=True)
class ProbeFixtureDefinition:
    fixture_ref: str
    version: str
    fixture_class: ProbeFixtureClass
    catalog_ref: str
    catalog_version: str
    assets: FixtureAssetManifest
    canonical_state: tuple[SubjectState, ...]

    def __post_init__(self) -> None:
        for ref in (self.fixture_ref, self.version, self.catalog_ref, self.catalog_version):
            _text(ref)
        _typed(self.fixture_class, ProbeFixtureClass)
        _typed(self.assets, FixtureAssetManifest)
        object.__setattr__(self, "canonical_state", _states(self.canonical_state))
        _require(bool(self.canonical_state), "Canonical state required")


@dataclass(frozen=True)
class FixtureSnapshot:
    registration: RegisteredProbeEnvironment
    instance_ref: str
    timeline_ref: str
    profile: RuntimeProfile
    snapshot_ref: str
    scope: ProbeObservationScope
    states: tuple[SubjectState, ...]

    def __post_init__(self) -> None:
        _typed(self.registration, RegisteredProbeEnvironment)
        _typed(self.profile, RuntimeProfile)
        for ref in (self.instance_ref, self.timeline_ref, self.snapshot_ref):
            _text(ref)
        _typed(self.scope, ProbeObservationScope)
        object.__setattr__(self, "states", _states(self.states))


@dataclass(frozen=True)
class FixtureVerificationResult:
    verification_ref: str
    instance_ref: str
    definition: ProbeFixtureDefinition
    snapshot: FixtureSnapshot
    status: FixtureVerificationStatus
    independent_read_ref: str

    def __post_init__(self) -> None:
        for ref in (self.verification_ref, self.instance_ref, self.independent_read_ref):
            _text(ref)
        _typed(self.definition, ProbeFixtureDefinition)
        _typed(self.snapshot, FixtureSnapshot)
        _typed(self.status, FixtureVerificationStatus)


@dataclass(frozen=True)
class ProbeFixtureInstance:
    instance_ref: str
    registration: RegisteredProbeEnvironment
    definition: ProbeFixtureDefinition
    timeline_ref: str
    materialization_generation: int
    state: FixtureLifecycleState = FixtureLifecycleState.DEFINED
    verification: FixtureVerificationResult | None = None

    def __post_init__(self) -> None:
        _text(self.instance_ref)
        _text(self.timeline_ref)
        _positive(self.materialization_generation)
        _typed(self.registration, RegisteredProbeEnvironment)
        _typed(self.definition, ProbeFixtureDefinition)
        _typed(self.state, FixtureLifecycleState)
        if self.verification is not None:
            _typed(self.verification, FixtureVerificationResult)
        if self.state in (
            FixtureLifecycleState.CLEAN_VERIFIED,
            FixtureLifecycleState.LEASED_FOR_PROBE,
        ):
            _require(
                self.verification is not None
                and self.verification.status == FixtureVerificationStatus.MATCH
                and self.verification.instance_ref == self.instance_ref
                and self.verification.definition == self.definition
                and self.verification.snapshot.instance_ref == self.instance_ref
                and self.verification.snapshot.registration == self.registration
                and self.verification.snapshot.timeline_ref == self.timeline_ref
                and self.verification.snapshot.profile == self.registration.profile
                and self.verification.snapshot.states == self.definition.canonical_state
                and self.verification.snapshot.scope.completeness == ScopeCompleteness.COMPLETE,
                "Clean fixture requires bound MATCH evidence",
            )


@dataclass(frozen=True)
class ContainmentEnvelope:
    envelope_ref: str
    fixture_subject_refs: tuple[str, ...]
    project_baseline_ref: str

    def __post_init__(self) -> None:
        _text(self.envelope_ref)
        _text(self.project_baseline_ref)
        object.__setattr__(self, "fixture_subject_refs", _refs(self.fixture_subject_refs))
        _require(bool(self.fixture_subject_refs), "Explicit containment subjects required")


@dataclass(frozen=True)
class HarnessProbeCase:
    case_ref: str
    definition: ProbeFixtureDefinition
    domain: ApplicabilityDomain
    invocation: NativeInvocationSpec
    scope: ProbeObservationScope
    envelope: ContainmentEnvelope
    mode: ProbeRunMode

    def __post_init__(self) -> None:
        _text(self.case_ref)
        _typed(self.definition, ProbeFixtureDefinition)
        _typed(self.domain, ApplicabilityDomain)
        _typed(self.invocation, NativeInvocationSpec)
        _typed(self.scope, ProbeObservationScope)
        _typed(self.envelope, ContainmentEnvelope)
        _typed(self.mode, ProbeRunMode)


@dataclass(frozen=True)
class ProbeRunBinding:
    run_ref: str
    registration: RegisteredProbeEnvironment
    fixture_instance_ref: str
    case: HarnessProbeCase
    pre_snapshot: FixtureSnapshot

    def __post_init__(self) -> None:
        _text(self.run_ref)
        _text(self.fixture_instance_ref)
        _typed(self.registration, RegisteredProbeEnvironment)
        _typed(self.case, HarnessProbeCase)
        _typed(self.pre_snapshot, FixtureSnapshot)


@dataclass(frozen=True)
class ProbeLease:
    lease_ref: str
    binding: ProbeRunBinding
    valid: bool = True

    def __post_init__(self) -> None:
        _text(self.lease_ref)
        _typed(self.binding, ProbeRunBinding)
        if type(self.valid) is not bool:
            raise TypeError("Explicit lease validity required")


@dataclass(frozen=True)
class PrimitiveAllowlist:
    allowlist_ref: str
    profile: RuntimeProfile
    invocations: tuple[NativeInvocationSpec, ...]
    modes: tuple[ProbeRunMode, ...]
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        _text(self.allowlist_ref)
        _text(self.contract_version)
        _typed(self.profile, RuntimeProfile)
        object.__setattr__(self, "invocations", _tuple(self.invocations, NativeInvocationSpec))
        object.__setattr__(self, "modes", _tuple(self.modes, ProbeRunMode))
        _require(
            len(set(self.invocations)) == len(self.invocations)
            and len(set(self.modes)) == len(self.modes),
            "Duplicate allowlist entry",
        )


@dataclass(frozen=True)
class ProbeRunAuthorization:
    authorization_ref: str
    lease: ProbeLease
    environment_verification: EnvironmentVerification
    fixture_verification: FixtureVerificationResult
    allowlist: PrimitiveAllowlist
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        _text(self.authorization_ref)
        _text(self.contract_version)
        _typed(self.lease, ProbeLease)
        _typed(self.environment_verification, EnvironmentVerification)
        _typed(self.fixture_verification, FixtureVerificationResult)
        _typed(self.allowlist, PrimitiveAllowlist)
        binding = self.lease.binding
        _require(
            self.lease.valid
            and self.fixture_verification.instance_ref == binding.fixture_instance_ref
            and self.fixture_verification.definition == binding.case.definition
            and self.fixture_verification.snapshot == binding.pre_snapshot
            and self.fixture_verification.status == FixtureVerificationStatus.MATCH
            and self.environment_verification.facts.registration == binding.registration
            and self.environment_verification.status == EnvironmentVerificationStatus.VERIFIED
            and self.allowlist.profile == binding.registration.profile,
            "Authorization requires exact clean fixture/environment/lease binding",
        )


@dataclass(frozen=True)
class CurrentInvocationFacts:
    binding: ProbeRunBinding
    environment: EnvironmentFacts
    allowlist: PrimitiveAllowlist
    lease_ref: str
    fixture_verification_ref: str

    def __post_init__(self) -> None:
        _typed(self.binding, ProbeRunBinding)
        _typed(self.environment, EnvironmentFacts)
        _typed(self.allowlist, PrimitiveAllowlist)
        _text(self.lease_ref)
        _text(self.fixture_verification_ref)


@dataclass(frozen=True)
class InvocationAttempt:
    attempt_ref: str
    authorization: ProbeRunAuthorization
    outcome: NativeInvocationOutcome | None = None
    metadata_ref: str | None = None

    def __post_init__(self) -> None:
        _text(self.attempt_ref)
        _typed(self.authorization, ProbeRunAuthorization)
        if self.outcome is not None:
            _typed(self.outcome, NativeInvocationOutcome)
        if self.metadata_ref is not None:
            _text(self.metadata_ref)
        _require(
            (self.outcome is None) == (self.metadata_ref is None), "Outcome requires raw metadata"
        )


@dataclass(frozen=True)
class PostObservation:
    observation_ref: str
    binding: ProbeRunBinding
    snapshot: FixtureSnapshot
    observed_diff_ref: str
    status: FixtureVerificationStatus

    def __post_init__(self) -> None:
        _text(self.observation_ref)
        _text(self.observed_diff_ref)
        _typed(self.binding, ProbeRunBinding)
        _typed(self.snapshot, FixtureSnapshot)
        _typed(self.status, FixtureVerificationStatus)


@dataclass(frozen=True)
class ContainmentResult:
    containment_ref: str
    binding: ProbeRunBinding
    classification: ContainmentClass
    observation_ref: str
    evidence_ref: str

    def __post_init__(self) -> None:
        for ref in (self.containment_ref, self.observation_ref, self.evidence_ref):
            _text(ref)
        _typed(self.binding, ProbeRunBinding)
        _typed(self.classification, ContainmentClass)


@dataclass(frozen=True)
class SealedProbeEvidence:
    evidence_ref: str
    binding: ProbeRunBinding
    lease: ProbeLease
    authorization: ProbeRunAuthorization | None
    authorization_consumed: bool
    attempt: InvocationAttempt | None
    observation: PostObservation | None
    containment: ContainmentResult | None
    effective_containment: ContainmentClass | None
    generation_after: ProjectGenerationStatus
    outcome: ProbeRunOutcome
    findings: tuple[GateFinding, ...]
    diagnostic_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.evidence_ref)
        _typed(self.binding, ProbeRunBinding)
        _typed(self.lease, ProbeLease)
        for value, kind in (
            (self.authorization, ProbeRunAuthorization),
            (self.attempt, InvocationAttempt),
            (self.observation, PostObservation),
            (self.containment, ContainmentResult),
            (self.effective_containment, ContainmentClass),
        ):
            if value is not None:
                _typed(value, kind)
        if type(self.authorization_consumed) is not bool:
            raise TypeError("Explicit consumption required")
        _typed(self.generation_after, ProjectGenerationStatus)
        _typed(self.outcome, ProbeRunOutcome)
        object.__setattr__(self, "findings", _tuple(self.findings, GateFinding))
        object.__setattr__(self, "diagnostic_refs", _refs(self.diagnostic_refs))
        _require(self.outcome != ProbeRunOutcome.NONE, "Cannot seal unfinished run")
        _require(
            self.authorization is None or self.authorization_consumed,
            "Seal cannot retain live authority",
        )

        _require(
            self.lease.binding == self.binding and not self.lease.valid,
            "Sealed lease must be consumed and bound",
        )
        if self.authorization is not None:
            _require(
                self.authorization.lease.binding == self.binding
                and self.authorization.lease.lease_ref == self.lease.lease_ref,
                "Authorization binding mismatch",
            )
        if self.attempt is not None:
            _require(
                self.attempt.authorization == self.authorization
                and self.attempt.outcome is not None,
                "Attempt must have bound acknowledgement or explicit uncertainty",
            )
        if self.outcome in (ProbeRunOutcome.PASS_OBSERVED, ProbeRunOutcome.FAIL_OBSERVED):
            _require(
                self.authorization is not None
                and self.attempt is not None
                and self.observation is not None
                and self.containment is not None
                and self.observation.binding == self.binding
                and self.containment.binding == self.binding,
                "Observed outcome requires complete bound evidence",
            )

    @property
    def eligible_for_qualification(self) -> bool:
        return (
            self.binding.case.mode == ProbeRunMode.QUALIFYING
            and self.outcome == ProbeRunOutcome.PASS_OBSERVED
            and self.attempt is not None
            and self.attempt.outcome == NativeInvocationOutcome.SUCCEEDED
            and self.containment is not None
            and self.containment.classification == ContainmentClass.CLEAN
            and self.generation_after == ProjectGenerationStatus.VERIFIED_CLEAN
            and not self.findings
            and self.effective_containment == ContainmentClass.CLEAN
            and self.observation is not None
            and self.observation.status == FixtureVerificationStatus.MATCH
            and self.observation.snapshot.scope == self.binding.case.scope
            and self.observation.snapshot.registration == self.binding.registration
            and self.observation.snapshot.profile == self.binding.registration.profile
            and self.observation.snapshot.instance_ref == self.binding.fixture_instance_ref
            and self.observation.snapshot.timeline_ref == self.binding.pre_snapshot.timeline_ref
            and self.observation.snapshot.snapshot_ref != self.binding.pre_snapshot.snapshot_ref
            and self.containment.observation_ref == self.observation.observation_ref
            and self.observation.snapshot.scope.completeness == ScopeCompleteness.COMPLETE
        )


@dataclass(frozen=True)
class ProbeRunRecord:
    binding: ProbeRunBinding
    lease_ref: str
    state: ProbeRunState = ProbeRunState.PRECHECKING
    outcome: ProbeRunOutcome = ProbeRunOutcome.NONE
    authorization: ProbeRunAuthorization | None = None
    authorization_consumed: bool = False
    attempt: InvocationAttempt | None = None
    observation: PostObservation | None = None
    containment: ContainmentResult | None = None
    effective_containment: ContainmentClass | None = None
    findings: tuple[GateFinding, ...] = ()
    diagnostic_refs: tuple[str, ...] = ()
    sealed_evidence: SealedProbeEvidence | None = None

    def __post_init__(self) -> None:
        _typed(self.binding, ProbeRunBinding)
        _text(self.lease_ref)
        _typed(self.state, ProbeRunState)
        _typed(self.outcome, ProbeRunOutcome)
        for value, kind in (
            (self.authorization, ProbeRunAuthorization),
            (self.attempt, InvocationAttempt),
            (self.observation, PostObservation),
            (self.containment, ContainmentResult),
            (self.effective_containment, ContainmentClass),
            (self.sealed_evidence, SealedProbeEvidence),
        ):
            if value is not None:
                _typed(value, kind)
        if type(self.authorization_consumed) is not bool:
            raise TypeError("Explicit consumption required")
        object.__setattr__(self, "findings", _tuple(self.findings, GateFinding))
        object.__setattr__(self, "diagnostic_refs", _refs(self.diagnostic_refs))
        if self.authorization is not None:
            _require(
                self.authorization.lease.binding == self.binding
                and self.authorization.lease.lease_ref == self.lease_ref,
                "Run authorization binding mismatch",
            )
        if self.attempt is not None:
            _require(
                self.authorization is not None
                and self.authorization_consumed
                and self.attempt.authorization == self.authorization,
                "Attempt requires consumed exact authorization",
            )
        if self.state == ProbeRunState.ARMED:
            _require(
                self.authorization is not None
                and not self.authorization_consumed
                and self.attempt is None,
                "Armed state requires unused authorization",
            )


@dataclass(frozen=True)
class GenerationArchive:
    registration: RegisteredProbeEnvironment
    status: ProjectGenerationStatus

    def __post_init__(self) -> None:
        _typed(self.registration, RegisteredProbeEnvironment)
        _typed(self.status, ProjectGenerationStatus)


@dataclass(frozen=True)
class Harness:
    registration: RegisteredProbeEnvironment
    generation_status: ProjectGenerationStatus = ProjectGenerationStatus.REVERIFY_REQUIRED
    verification: EnvironmentVerification | None = None
    fixtures: tuple[ProbeFixtureInstance, ...] = ()
    leases: tuple[ProbeLease, ...] = ()
    runs: tuple[ProbeRunRecord, ...] = ()
    environment_uncertain: bool = False
    verification_history: tuple[EnvironmentVerification, ...] = ()
    generation_history: tuple[GenerationArchive, ...] = ()

    def __post_init__(self) -> None:
        _typed(self.registration, RegisteredProbeEnvironment)
        _typed(self.generation_status, ProjectGenerationStatus)
        if self.verification is not None:
            _typed(self.verification, EnvironmentVerification)
        if type(self.environment_uncertain) is not bool:
            raise TypeError("Explicit uncertainty required")
        for field, kind in (
            ("fixtures", ProbeFixtureInstance),
            ("leases", ProbeLease),
            ("runs", ProbeRunRecord),
            ("verification_history", EnvironmentVerification),
            ("generation_history", GenerationArchive),
        ):
            object.__setattr__(self, field, _tuple(getattr(self, field), kind))
        _unique(tuple(f.instance_ref for f in self.fixtures))
        _unique(tuple(l.lease_ref for l in self.leases))
        _unique(tuple(r.binding.run_ref for r in self.runs))
        _unique(
            tuple(
                r.authorization.authorization_ref for r in self.runs if r.authorization is not None
            )
        )
        _unique(tuple(r.attempt.attempt_ref for r in self.runs if r.attempt is not None))
        _unique(
            tuple(
                r.sealed_evidence.evidence_ref for r in self.runs if r.sealed_evidence is not None
            )
        )
        active = [l.binding.fixture_instance_ref for l in self.leases if l.valid]
        _unique(tuple(active))

    def fixture(self, ref: str) -> ProbeFixtureInstance:
        return next(f for f in self.fixtures if f.instance_ref == ref)

    def run(self, ref: str) -> ProbeRunRecord:
        return next(r for r in self.runs if r.binding.run_ref == ref)

    def lease(self, ref: str) -> ProbeLease:
        return next(l for l in self.leases if l.lease_ref == ref)

    @property
    def no_further_mutation(self) -> NoFurtherMutationGate:
        if (
            self.environment_uncertain
            or self.generation_status != ProjectGenerationStatus.VERIFIED_CLEAN
            or self.verification is None
            or not _environment_match(self.registration, self.verification, self.verification.facts)
            or any(
                f.registration == self.registration and f.state == FixtureLifecycleState.QUARANTINED
                for f in self.fixtures
            )
        ):
            return NoFurtherMutationGate.BLOCKED
        return NoFurtherMutationGate.ALLOWED

    @property
    def state(self) -> ProbeHarnessState:
        if (
            self.environment_uncertain
            or self.generation_status == ProjectGenerationStatus.CONTAMINATED
        ):
            return ProbeHarnessState.LOCKED_DOWN
        if any(
            f.registration == self.registration and f.state == FixtureLifecycleState.QUARANTINED
            for f in self.fixtures
        ):
            return ProbeHarnessState.QUARANTINED
        current = [r for r in self.runs if r.binding.registration == self.registration]
        for phase, label in (
            (ProbeRunState.INVOKING, ProbeHarnessState.INVOCATION_ATTEMPTED),
            (ProbeRunState.OBSERVING, ProbeHarnessState.OBSERVING),
            (ProbeRunState.ARMED, ProbeHarnessState.ARMED_FOR_ONE_RUN),
        ):
            if any(r.state == phase for r in current):
                return label
        if any(r.state == ProbeRunState.SEALED for r in current):
            return ProbeHarnessState.SEALED
        if any(
            f.registration == self.registration and f.state == FixtureLifecycleState.CLEAN_VERIFIED
            for f in self.fixtures
        ):
            return ProbeHarnessState.FIXTURE_VERIFIED
        return (
            ProbeHarnessState.ENVIRONMENT_VERIFIED
            if self.no_further_mutation == NoFurtherMutationGate.ALLOWED
            else ProbeHarnessState.DISARMED
        )


def _environment_match(
    reg: RegisteredProbeEnvironment, proof: EnvironmentVerification, current: EnvironmentFacts
) -> bool:
    return (
        proof.status == EnvironmentVerificationStatus.VERIFIED
        and proof.facts == current
        and current.registration == reg
        and current.project_ref == reg.probe_project_ref
        and current.profile == reg.profile
        and reg.harness_contract_version == "v1"
    )


def _fixture_update(h: Harness, fixture: ProbeFixtureInstance) -> Harness:
    return replace(
        h,
        fixtures=tuple(
            fixture if f.instance_ref == fixture.instance_ref else f for f in h.fixtures
        ),
    )


def _run_update(h: Harness, run: ProbeRunRecord) -> Harness:
    return replace(
        h, runs=tuple(run if r.binding.run_ref == run.binding.run_ref else r for r in h.runs)
    )


def register_environment(registration: RegisteredProbeEnvironment) -> Harness:
    return Harness(registration)


def verify_environment(
    h: Harness, proof: EnvironmentVerification, current: EnvironmentFacts
) -> Harness:
    _require(
        h.generation_status
        not in (ProjectGenerationStatus.CONTAMINATED, ProjectGenerationStatus.RETIRED),
        "New generation required",
    )
    _require(
        not any(r.binding.registration == h.registration for r in h.runs),
        "Use independent re-verification after runs",
    )
    valid = _environment_match(h.registration, proof, current)
    status = (
        ProjectGenerationStatus.VERIFIED_CLEAN
        if valid
        else ProjectGenerationStatus.REVERIFY_REQUIRED
    )
    if proof.status == EnvironmentVerificationStatus.CONTAMINATED:
        status = ProjectGenerationStatus.CONTAMINATED
    return replace(
        h,
        generation_status=status,
        verification=proof if valid else None,
        verification_history=h.verification_history + (proof,),
    )


def define_fixture(
    h: Harness,
    instance_ref: str,
    definition: ProbeFixtureDefinition,
    timeline_ref: str,
    materialization_generation: int,
) -> Harness:
    _require(h.no_further_mutation == NoFurtherMutationGate.ALLOWED, "Environment not verified")
    _require(
        all(f.instance_ref != instance_ref for f in h.fixtures), "Instance identity already used"
    )
    _require(
        (definition.catalog_ref, definition.catalog_version)
        == (h.registration.fixture_catalog_ref, h.registration.fixture_catalog_version),
        "Catalog mismatch",
    )
    _require(
        not any(
            f.registration == h.registration
            and f.timeline_ref == timeline_ref
            and f.materialization_generation == materialization_generation
            for f in h.fixtures
        ),
        "Materialization identity already used; new instance generation required",
    )
    fixture = ProbeFixtureInstance(
        instance_ref, h.registration, definition, timeline_ref, materialization_generation
    )
    return replace(h, fixtures=h.fixtures + (fixture,))


def advance_fixture(h: Harness, instance_ref: str, state: FixtureLifecycleState) -> Harness:
    fixture = h.fixture(instance_ref)
    allowed = {
        FixtureLifecycleState.DEFINED: FixtureLifecycleState.MATERIALIZING,
        FixtureLifecycleState.MATERIALIZING: FixtureLifecycleState.MATERIALIZED,
        FixtureLifecycleState.MATERIALIZED: FixtureLifecycleState.VERIFYING,
        FixtureLifecycleState.ABORTED: FixtureLifecycleState.VERIFYING,
    }
    _require(
        allowed.get(fixture.state) == state and fixture.registration == h.registration,
        "Illegal fixture transition",
    )
    return _fixture_update(h, replace(fixture, state=state))


def verify_fixture(h: Harness, instance_ref: str, proof: FixtureVerificationResult) -> Harness:
    fixture = h.fixture(instance_ref)
    _require(fixture.state == FixtureLifecycleState.VERIFYING, "Fixture must be verifying")
    if fixture.verification is not None:
        _require(
            proof.verification_ref != fixture.verification.verification_ref
            and proof.independent_read_ref != fixture.verification.independent_read_ref,
            "Fresh verification required",
        )
    snapshot = proof.snapshot
    valid = (
        proof.instance_ref == fixture.instance_ref
        and proof.definition == fixture.definition
        and snapshot.instance_ref == fixture.instance_ref
        and snapshot.registration == h.registration == fixture.registration
        and snapshot.timeline_ref == fixture.timeline_ref
        and snapshot.profile == h.registration.profile
        and snapshot.states == fixture.definition.canonical_state
        and snapshot.scope.completeness == ScopeCompleteness.COMPLETE
    )
    state = FixtureLifecycleState.INVALID
    if valid:
        if proof.status == FixtureVerificationStatus.MATCH:
            state = FixtureLifecycleState.CLEAN_VERIFIED
        elif proof.status == FixtureVerificationStatus.MISMATCH:
            state = FixtureLifecycleState.DIRTY
    return _fixture_update(h, replace(fixture, state=state, verification=proof))


def lease_probe(h: Harness, lease_ref: str, binding: ProbeRunBinding) -> Harness:
    _require(h.no_further_mutation == NoFurtherMutationGate.ALLOWED, "Mutation gate blocked")
    _require(all(r.binding.run_ref != binding.run_ref for r in h.runs), "Run identity used")
    _require(all(l.lease_ref != lease_ref for l in h.leases), "Lease identity used")
    fixture = h.fixture(binding.fixture_instance_ref)
    proof = fixture.verification
    _require(
        fixture.state == FixtureLifecycleState.CLEAN_VERIFIED and proof is not None,
        "Clean fixture required",
    )
    assert proof is not None
    _require(
        binding.registration == fixture.registration == h.registration
        and binding.pre_snapshot == proof.snapshot
        and binding.case.definition == fixture.definition
        and binding.case.scope == proof.snapshot.scope
        and h.verification is not None
        and proof.snapshot.timeline_ref == h.verification.facts.timeline_ref
        and set(binding.case.invocation.target_refs)
        <= set(binding.case.envelope.fixture_subject_refs)
        and set(binding.case.envelope.fixture_subject_refs)
        == {s.subject_ref for s in proof.snapshot.states},
        "Lease binding mismatch",
    )
    _require(
        not any(
            l.valid and l.binding.fixture_instance_ref == fixture.instance_ref for l in h.leases
        ),
        "Fixture already leased",
    )
    lease = ProbeLease(lease_ref, binding)
    h = _fixture_update(h, replace(fixture, state=FixtureLifecycleState.LEASED_FOR_PROBE))
    return replace(
        h, leases=h.leases + (lease,), runs=h.runs + (ProbeRunRecord(binding, lease_ref),)
    )


def authorize_probe(
    h: Harness, run_ref: str, authorization_ref: str, allowlist: PrimitiveAllowlist
) -> Harness:
    run = h.run(run_ref)
    _require(
        run.state == ProbeRunState.PRECHECKING and run.authorization is None,
        "Run already authorized",
    )
    _require(
        all(
            r.authorization is None or r.authorization.authorization_ref != authorization_ref
            for r in h.runs
        ),
        "Authorization identity used",
    )
    _require(
        h.no_further_mutation == NoFurtherMutationGate.ALLOWED and h.lease(run.lease_ref).valid,
        "Environment or lease invalid",
    )
    _require(
        allowlist.profile == h.registration.profile
        and allowlist.contract_version == "v1"
        and run.binding.case.invocation in allowlist.invocations
        and run.binding.case.mode in allowlist.modes,
        "Invocation not allowlisted",
    )
    proof = h.fixture(run.binding.fixture_instance_ref).verification
    assert proof is not None and h.verification is not None
    authorization = ProbeRunAuthorization(
        authorization_ref, h.lease(run.lease_ref), h.verification, proof, allowlist
    )
    return _run_update(h, replace(run, state=ProbeRunState.ARMED, authorization=authorization))


def invalidate_lease(h: Harness, lease_ref: str) -> Harness:
    h.lease(lease_ref)
    return replace(
        h,
        leases=tuple(replace(l, valid=False) if l.lease_ref == lease_ref else l for l in h.leases),
    )


@dataclass(frozen=True)
class GateResult:
    harness: Harness
    submission: InvocationAttempt | None

    def __post_init__(self) -> None:
        _typed(self.harness, Harness)
        if self.submission is not None:
            _typed(self.submission, InvocationAttempt)
            _require(
                any(r.attempt == self.submission for r in self.harness.runs),
                "Submission must be recorded",
            )


def final_gate(
    h: Harness, run_ref: str, current: CurrentInvocationFacts, attempt_ref: str
) -> GateResult:
    run = h.run(run_ref)
    _require(
        run.state == ProbeRunState.ARMED
        and not run.authorization_consumed
        and run.authorization is not None,
        "Unused one-run authorization required",
    )
    auth = run.authorization
    assert auth is not None
    binding, actual = run.binding, current.binding
    fixture = h.fixture(binding.fixture_instance_ref)
    lease = h.lease(run.lease_ref)
    checks = (
        (h.no_further_mutation == NoFurtherMutationGate.ALLOWED, GateFinding.LOCKED_DOWN),
        (
            actual.registration == binding.registration == h.registration
            and current.environment.registration == h.registration,
            GateFinding.ENVIRONMENT_MISMATCH,
        ),
        (
            h.generation_status == ProjectGenerationStatus.VERIFIED_CLEAN,
            GateFinding.GENERATION_INELIGIBLE,
        ),
        (
            h.verification == auth.environment_verification
            and _environment_match(
                h.registration, auth.environment_verification, current.environment
            ),
            GateFinding.ENVIRONMENT_UNVERIFIED,
        ),
        (
            fixture.state == FixtureLifecycleState.LEASED_FOR_PROBE
            and fixture.verification == auth.fixture_verification
            and current.fixture_verification_ref == auth.fixture_verification.verification_ref
            and actual.fixture_instance_ref == fixture.instance_ref,
            GateFinding.FIXTURE_UNVERIFIED,
        ),
        (
            lease.valid
            and lease == auth.lease
            and current.lease_ref == lease.lease_ref
            and actual.run_ref == binding.run_ref,
            GateFinding.LEASE_INVALID,
        ),
        (actual.pre_snapshot == binding.pre_snapshot, GateFinding.SNAPSHOT_MISMATCH),
        (
            current.environment.profile
            == binding.registration.profile
            == current.allowlist.profile,
            GateFinding.PROFILE_CHANGED,
        ),
        (
            actual.case.case_ref == binding.case.case_ref
            and actual.case.domain == binding.case.domain
            and actual.case.definition == binding.case.definition,
            GateFinding.CASE_DOMAIN_CHANGED,
        ),
        (actual.case.scope == binding.case.scope, GateFinding.SCOPE_CHANGED),
        (actual.case.envelope == binding.case.envelope, GateFinding.CONTAINMENT_CHANGED),
        (
            current.allowlist == auth.allowlist
            and actual.case.invocation == binding.case.invocation
            and actual.case.invocation in current.allowlist.invocations,
            GateFinding.INVOCATION_NOT_ALLOWED,
        ),
        (not run.authorization_consumed, GateFinding.AUTHORIZATION_CONSUMED),
        (
            actual.case.mode == binding.case.mode and actual.case.mode in current.allowlist.modes,
            GateFinding.MODE_NOT_ALLOWED,
        ),
        (
            auth.contract_version
            == current.allowlist.contract_version
            == h.registration.harness_contract_version
            == "v1",
            GateFinding.CONTRACT_UNSUPPORTED,
        ),
    )
    findings = tuple(reason for valid, reason in checks if not valid)
    h = invalidate_lease(h, lease.lease_ref)
    if findings:
        h = _fixture_update(h, replace(fixture, state=FixtureLifecycleState.ABORTED))
        h = _run_update(
            h,
            replace(
                run,
                state=ProbeRunState.TERMINAL,
                outcome=ProbeRunOutcome.ABORTED,
                authorization_consumed=True,
                findings=findings,
            ),
        )
        return GateResult(h, None)
    attempt = InvocationAttempt(attempt_ref, auth)
    h = _fixture_update(h, replace(fixture, state=FixtureLifecycleState.MUTATED))
    h = _run_update(
        h, replace(run, state=ProbeRunState.INVOKING, authorization_consumed=True, attempt=attempt)
    )
    return GateResult(h, attempt)


def _uncertain(h: Harness, run: ProbeRunRecord) -> Harness:
    fixture = h.fixture(run.binding.fixture_instance_ref)
    h = _fixture_update(h, replace(fixture, state=FixtureLifecycleState.QUARANTINED))
    generation = (
        h.generation_status
        if h.generation_status == ProjectGenerationStatus.CONTAMINATED
        else ProjectGenerationStatus.REVERIFY_REQUIRED
    )
    return _run_update(
        replace(h, generation_status=generation, environment_uncertain=True),
        replace(
            run,
            state=ProbeRunState.OBSERVING,
            outcome=ProbeRunOutcome.INCONCLUSIVE,
            effective_containment=ContainmentClass.ENVIRONMENT_UNCERTAIN,
        ),
    )


def record_outcome(
    h: Harness, run_ref: str, outcome: NativeInvocationOutcome, metadata_ref: str
) -> Harness:
    run = h.run(run_ref)
    _require(
        run.state == ProbeRunState.INVOKING
        and run.attempt is not None
        and run.attempt.outcome is None,
        "Pending submission required",
    )
    assert run.attempt is not None
    run = replace(
        run,
        state=ProbeRunState.OBSERVING,
        attempt=replace(run.attempt, outcome=outcome, metadata_ref=metadata_ref),
    )
    if outcome in (NativeInvocationOutcome.TIMEOUT, NativeInvocationOutcome.OUTCOME_UNKNOWN):
        return _uncertain(h, run)
    return _run_update(h, run)


def observe_run(
    h: Harness, run_ref: str, observation: PostObservation, containment: ContainmentResult
) -> Harness:
    run = h.run(run_ref)
    _require(
        run.state == ProbeRunState.OBSERVING and run.observation is None,
        "One observation per submitted run",
    )
    binding, snapshot = run.binding, observation.snapshot
    pre = binding.pre_snapshot
    valid = (
        observation.binding == containment.binding == binding
        and containment.observation_ref == observation.observation_ref
        and snapshot.registration == binding.registration == h.registration
        and snapshot.instance_ref == pre.instance_ref
        and snapshot.timeline_ref == pre.timeline_ref
        and snapshot.profile == pre.profile
        and snapshot.scope == pre.scope
        and snapshot.scope.completeness == ScopeCompleteness.COMPLETE
        and snapshot.snapshot_ref != pre.snapshot_ref
        and observation.status
        in (FixtureVerificationStatus.MATCH, FixtureVerificationStatus.MISMATCH)
    )
    run = replace(run, observation=observation, containment=containment)
    if not valid or run.effective_containment == ContainmentClass.ENVIRONMENT_UNCERTAIN:
        return _uncertain(
            h, replace(run, findings=run.findings + (GateFinding.OBSERVATION_MISMATCH,))
        )
    classification = containment.classification
    if classification == ContainmentClass.ENVIRONMENT_UNCERTAIN:
        return _uncertain(h, run)
    fixture = h.fixture(binding.fixture_instance_ref)
    if classification == ContainmentClass.CLEAN:
        outcome = (
            ProbeRunOutcome.PASS_OBSERVED
            if observation.status == FixtureVerificationStatus.MATCH
            else ProbeRunOutcome.FAIL_OBSERVED
        )
        h = _fixture_update(h, replace(fixture, state=FixtureLifecycleState.OBSERVED))
    else:
        outcome = ProbeRunOutcome.CONTAINMENT_FAILURE
        h = _fixture_update(h, replace(fixture, state=FixtureLifecycleState.QUARANTINED))
        generation = (
            ProjectGenerationStatus.CONTAMINATED
            if classification == ContainmentClass.PROJECT_LEVEL_CONTAMINATION
            else ProjectGenerationStatus.REVERIFY_REQUIRED
        )
        if h.generation_status == ProjectGenerationStatus.CONTAMINATED:
            generation = h.generation_status
        h = replace(h, generation_status=generation)
    return _run_update(h, replace(run, outcome=outcome, effective_containment=classification))


def seal_run(h: Harness, run_ref: str, evidence_ref: str) -> Harness:
    run = h.run(run_ref)
    _require(
        run.sealed_evidence is None and run.outcome != ProbeRunOutcome.NONE,
        "Completed diagnostics required",
    )
    _require(
        run.authorization is None or run.authorization_consumed, "Cannot seal reusable authority"
    )
    if run.attempt is not None:
        _require(
            run.attempt.outcome is not None
            and (
                run.observation is not None
                or run.effective_containment == ContainmentClass.ENVIRONMENT_UNCERTAIN
            ),
            "Observation or uncertainty diagnostics required",
        )
    seal = SealedProbeEvidence(
        evidence_ref,
        run.binding,
        h.lease(run.lease_ref),
        run.authorization,
        run.authorization_consumed,
        run.attempt,
        run.observation,
        run.containment,
        run.effective_containment,
        h.generation_status,
        run.outcome,
        run.findings,
        run.diagnostic_refs,
    )
    fixture = h.fixture(run.binding.fixture_instance_ref)
    if fixture.state == FixtureLifecycleState.OBSERVED:
        h = _fixture_update(h, replace(fixture, state=FixtureLifecycleState.SEALED))
    return _run_update(h, replace(run, state=ProbeRunState.SEALED, sealed_evidence=seal))


def discard_fixture(h: Harness, instance_ref: str) -> Harness:
    fixture = h.fixture(instance_ref)
    _require(
        fixture.state
        in (
            FixtureLifecycleState.DIRTY,
            FixtureLifecycleState.INVALID,
            FixtureLifecycleState.ABORTED,
            FixtureLifecycleState.QUARANTINED,
            FixtureLifecycleState.SEALED,
        ),
        "Fixture not discardable",
    )
    affected = tuple(r for r in h.runs if r.binding.fixture_instance_ref == instance_ref)
    _require(
        all(r.attempt is None or r.sealed_evidence is not None for r in affected),
        "Seal submitted run before discard",
    )
    h = _fixture_update(h, replace(fixture, state=FixtureLifecycleState.DISCARDED))
    for run in affected:
        h = _run_update(h, replace(run, state=ProbeRunState.TERMINAL))
    return h


def crash(h: Harness, run_ref: str, diagnostic_ref: str) -> Harness:
    _text(diagnostic_ref)
    run = h.run(run_ref)
    _require(
        run.state
        in (
            ProbeRunState.PRECHECKING,
            ProbeRunState.ARMED,
            ProbeRunState.INVOKING,
            ProbeRunState.OBSERVING,
        ),
        "Run already terminated",
    )
    run = replace(run, diagnostic_refs=run.diagnostic_refs + (diagnostic_ref,))
    if run.attempt is not None:
        attempt = run.attempt
        if attempt.outcome is None:
            attempt = replace(
                attempt,
                outcome=NativeInvocationOutcome.OUTCOME_UNKNOWN,
                metadata_ref=diagnostic_ref,
            )
        return _uncertain(h, replace(run, attempt=attempt))
    h = invalidate_lease(h, run.lease_ref)
    fixture = h.fixture(run.binding.fixture_instance_ref)
    h = _fixture_update(h, replace(fixture, state=FixtureLifecycleState.ABORTED))
    return _run_update(
        h,
        replace(
            run,
            state=ProbeRunState.TERMINAL,
            outcome=ProbeRunOutcome.ABORTED,
            authorization_consumed=run.authorization is not None,
        ),
    )


def reverify_environment(
    h: Harness, proof: EnvironmentVerification, current: EnvironmentFacts
) -> Harness:
    _require(
        h.generation_status == ProjectGenerationStatus.REVERIFY_REQUIRED,
        "Generation is not re-verifiable",
    )
    _require(
        not any(
            f.registration == h.registration
            and f.state
            in (
                FixtureLifecycleState.QUARANTINED,
                FixtureLifecycleState.LEASED_FOR_PROBE,
                FixtureLifecycleState.MUTATED,
            )
            for f in h.fixtures
        ),
        "Discard affected fixtures first",
    )
    _require(
        all(
            proof.verification_ref != p.verification_ref
            and proof.independent_read_ref != p.independent_read_ref
            for p in h.verification_history
        ),
        "Fresh independent project observation required",
    )
    valid = _environment_match(h.registration, proof, current)
    return replace(
        h,
        verification=proof if valid else None,
        environment_uncertain=not valid,
        generation_status=ProjectGenerationStatus.VERIFIED_CLEAN
        if valid
        else ProjectGenerationStatus.CONTAMINATED,
        verification_history=h.verification_history + (proof,),
    )


def rebuild_environment(h: Harness, registration: RegisteredProbeEnvironment) -> Harness:
    _require(
        registration.environment_ref == h.registration.environment_ref
        and registration.registry_ref == h.registration.registry_ref
        and registration.project_generation > h.registration.project_generation,
        "New generation required",
    )
    _require(
        all(r.state in (ProbeRunState.SEALED, ProbeRunState.TERMINAL) for r in h.runs),
        "Finish or quarantine/seal outstanding runs first",
    )
    archive = GenerationArchive(
        h.registration,
        h.generation_status
        if h.generation_status == ProjectGenerationStatus.CONTAMINATED
        else ProjectGenerationStatus.RETIRED,
    )
    return replace(
        h,
        registration=registration,
        generation_status=ProjectGenerationStatus.REVERIFY_REQUIRED,
        verification=None,
        environment_uncertain=False,
        generation_history=h.generation_history + (archive,),
        leases=tuple(replace(l, valid=False) for l in h.leases),
    )


class SuitePurpose(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    RELEASE = "RELEASE"
    UPDATE = "UPDATE"
    DIAGNOSTIC = "DIAGNOSTIC"


@dataclass(frozen=True)
class ProbeSuite:
    suite_ref: str
    profile: RuntimeProfile
    policy: CapabilityVerificationPolicy
    purpose: SuitePurpose
    sealed_evidence: tuple[SealedProbeEvidence, ...]

    def __post_init__(self) -> None:
        _text(self.suite_ref)
        _typed(self.profile, RuntimeProfile)
        _typed(self.policy, CapabilityVerificationPolicy)
        _typed(self.purpose, SuitePurpose)
        evidence = _tuple(self.sealed_evidence, SealedProbeEvidence)
        _unique(tuple(e.evidence_ref for e in evidence))
        _unique(tuple(e.binding.run_ref for e in evidence))
        _require(
            all(e.binding.registration.profile == self.profile for e in evidence),
            "Suite profile mismatch",
        )
        _require(
            all(e.binding.case.invocation.primitive == self.policy.primitive for e in evidence),
            "Suite primitive mismatch",
        )
        object.__setattr__(
            self, "sealed_evidence", tuple(sorted(evidence, key=lambda e: e.evidence_ref))
        )

    @property
    def qualifying_evidence_refs(self) -> tuple[str, ...]:
        return tuple(e.evidence_ref for e in self.sealed_evidence if e.eligible_for_qualification)

    @property
    def production_editor_manual_probe_work(self) -> int:
        return 0


@dataclass(frozen=True)
class FakeProbeHarness:
    harness: Harness

    def __post_init__(self) -> None:
        _typed(self.harness, Harness)

    def submit(self, run_ref: str, current: CurrentInvocationFacts, attempt_ref: str) -> GateResult:
        """Record one logical submission; never invoke a callback or a native API."""
        return final_gate(self.harness, run_ref, current, attempt_ref)
