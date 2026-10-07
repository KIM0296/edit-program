"""ADR-029/030 immutable observations and pure qualification; no probe runtime."""

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from .domain import FrameRange
from .execution_ir import EffectModelStatus, NativeCapabilityStatus
from .native_snapshot import IdentityScope

T = TypeVar("T")


def _typed(value: object, kind: type[object]) -> None:
    if not isinstance(value, kind):
        raise TypeError(f"Expected {kind.__name__}")


def _text(value: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError("Nonempty reference/version required")


def _optional(value: str | None) -> None:
    if value is not None:
        _text(value)


def _bool(value: bool) -> None:
    if type(value) is not bool:
        raise TypeError("Explicit boolean required")


def _values(values: tuple[T, ...], kind: type[T]) -> tuple[T, ...]:
    result = tuple(values)
    for value in result:
        _typed(value, kind)
    return tuple(sorted(result, key=repr))


def _refs(values: tuple[str, ...]) -> tuple[str, ...]:
    result = tuple(values)
    for value in result:
        _text(value)
    _unique(result)
    return tuple(sorted(result))


def _unique(values: tuple[str, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError("Duplicate evidence/instance identity")


class ScopeCompleteness(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class EvidenceStatus(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    INCOMPLETE = "INCOMPLETE"
    CONFLICTING = "CONFLICTING"
    INVALID = "INVALID"


class ReconciliationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    AMBIGUOUS = "AMBIGUOUS"
    UNVERIFIED = "UNVERIFIED"
    STALE = "STALE"


class FragmentEvidenceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class PostReadStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class ProbePrimitive(str, Enum):
    """Probe vocabulary, never ExecutionOpKind or an executable command."""

    TRANSLATE_PLACEMENT = "TRANSLATE_PLACEMENT"
    REMOVE_RANGE = "REMOVE_RANGE"
    COMPOUND_RIPPLE = "COMPOUND_RIPPLE"


class ProbeFixtureClass(str, Enum):
    ISOLATED_PLACEMENT = "ISOLATED_PLACEMENT"
    ADJACENT_PLACEMENTS = "ADJACENT_PLACEMENTS"
    PRE_EXISTING_GAP = "PRE_EXISTING_GAP"
    REPEATED_MEDIA = "REPEATED_MEDIA"
    MIDDLE_REMOVAL = "MIDDLE_REMOVAL"
    NEAR_LEADING_BOUNDARY = "NEAR_LEADING_BOUNDARY"
    NEAR_TRAILING_BOUNDARY = "NEAR_TRAILING_BOUNDARY"
    EXISTING_DOWNSTREAM_GAP = "EXISTING_DOWNSTREAM_GAP"
    SIMPLE_CONTIGUOUS_SINGLE_TRACK = "SIMPLE_CONTIGUOUS_SINGLE_TRACK"
    EXISTING_GAPS = "EXISTING_GAPS"
    MULTIPLE_DOWNSTREAM = "MULTIPLE_DOWNSTREAM"
    LARGE_DOWNSTREAM_SET = "LARGE_DOWNSTREAM_SET"
    EXPLICIT_MULTI_TRACK = "EXPLICIT_MULTI_TRACK"
    LINKED_AV = "LINKED_AV"
    INTENTIONAL_JL = "INTENTIONAL_JL"
    MARKERS_SUBTITLES = "MARKERS_SUBTITLES"
    TRACK_CONTROL_VARIATION = "TRACK_CONTROL_VARIATION"


class ChallengeClass(str, Enum):
    LINKED_AV = "LINKED_AV"
    INTENTIONAL_JL = "INTENTIONAL_JL"
    MARKERS_SUBTITLES = "MARKERS_SUBTITLES"
    TRANSITION_EFFECT_KEYFRAME = "TRANSITION_EFFECT_KEYFRAME"
    TRACK_CONTROL_VARIATION = "TRACK_CONTROL_VARIATION"


class SubjectKind(str, Enum):
    PLACEMENT = "PLACEMENT"
    TRACK = "TRACK"
    TOPOLOGY = "TOPOLOGY"
    MARKER = "MARKER"
    SUBTITLE = "SUBTITLE"
    TRANSITION = "TRANSITION"
    EFFECT = "EFFECT"
    KEYFRAME = "KEYFRAME"
    RELATIONSHIP = "RELATIONSHIP"


@dataclass(frozen=True)
class RuntimeProfile:
    resolve_version: str
    resolve_build: str
    platform: str
    adapter_name: str
    adapter_version: str
    invocation_contract: str
    observation_contract: str
    evidence_contract: str
    model_contract: str
    verification_policy_version: str
    profile_contract: str = "v1"

    def __post_init__(self) -> None:
        for value in (
            self.resolve_version,
            self.resolve_build,
            self.platform,
            self.adapter_name,
            self.adapter_version,
            self.invocation_contract,
            self.observation_contract,
            self.evidence_contract,
            self.model_contract,
            self.verification_policy_version,
            self.profile_contract,
        ):
            _text(value)


@dataclass(frozen=True)
class SubjectState:
    """Aligned observed values; structure refs are opaque, never inferred semantics."""

    subject_ref: str
    kind: SubjectKind
    timeline_range: FrameRange | None = None
    source_range: FrameRange | None = None
    media_ref: str | None = None
    track_ref: str | None = None
    structure_ref: str | None = None

    def __post_init__(self) -> None:
        _text(self.subject_ref)
        _typed(self.kind, SubjectKind)
        for value in (self.timeline_range, self.source_range):
            if value is not None:
                _typed(value, FrameRange)
        for ref in (self.media_ref, self.track_ref, self.structure_ref):
            _optional(ref)


def _states(values: tuple[SubjectState, ...]) -> tuple[SubjectState, ...]:
    values = _values(values, SubjectState)
    _unique(tuple(v.subject_ref for v in values))
    return values


@dataclass(frozen=True)
class ObservedChange:
    subject_ref: str
    before: SubjectState | None
    after: SubjectState | None

    def __post_init__(self) -> None:
        _text(self.subject_ref)
        if self.before == self.after:
            raise ValueError("Change requires different observations")
        for value in (self.before, self.after):
            if value is not None:
                _typed(value, SubjectState)
                if value.subject_ref != self.subject_ref:
                    raise ValueError("Subject binding mismatch")


def observed_changes(
    before: tuple[SubjectState, ...], after: tuple[SubjectState, ...]
) -> tuple[ObservedChange, ...]:
    b = {s.subject_ref: s for s in _states(before)}
    a = {s.subject_ref: s for s in _states(after)}
    return tuple(
        ObservedChange(ref, b.get(ref), a.get(ref))
        for ref in sorted(b.keys() | a.keys())
        if b.get(ref) != a.get(ref)
    )


@dataclass(frozen=True)
class ProbeObservationScope:
    scope_ref: str
    subject_refs: tuple[str, ...]
    kinds: tuple[SubjectKind, ...]
    completeness: ScopeCompleteness

    def __post_init__(self) -> None:
        _text(self.scope_ref)
        object.__setattr__(self, "subject_refs", _refs(self.subject_refs))
        object.__setattr__(self, "kinds", _values(self.kinds, SubjectKind))
        if len(set(self.kinds)) != len(self.kinds):
            raise ValueError("Duplicate category")
        _typed(self.completeness, ScopeCompleteness)


@dataclass(frozen=True)
class ChallengeDeclaration:
    kind: ChallengeClass
    applicable: bool

    def __post_init__(self) -> None:
        _typed(self.kind, ChallengeClass)
        _bool(self.applicable)


@dataclass(frozen=True)
class ApplicabilityDomain:
    domain_ref: str
    version: str
    conditions: tuple[str, ...]
    challenges: tuple[ChallengeDeclaration, ...]

    def __post_init__(self) -> None:
        _text(self.domain_ref)
        _text(self.version)
        object.__setattr__(self, "conditions", _refs(self.conditions))
        if not self.conditions:
            raise ValueError("Explicit domain conditions required")
        declarations = _values(self.challenges, ChallengeDeclaration)
        if len(declarations) != 5 or {d.kind for d in declarations} != set(ChallengeClass):
            raise ValueError("All five applicability declarations required")
        object.__setattr__(self, "challenges", declarations)


@dataclass(frozen=True)
class ProbeFixture:
    fixture_ref: str
    fixture_version: str
    fixture_class: ProbeFixtureClass
    project_ref: str
    registry_ref: str | None
    disposable: bool
    isolated: bool
    production: bool
    canonical_state: tuple[SubjectState, ...]
    authoritative: bool = False

    def __post_init__(self) -> None:
        for ref in (self.fixture_ref, self.fixture_version, self.project_ref):
            _text(ref)
        _optional(self.registry_ref)
        _typed(self.fixture_class, ProbeFixtureClass)
        for flag in (self.disposable, self.isolated, self.production, self.authoritative):
            _bool(flag)
        object.__setattr__(self, "canonical_state", _states(self.canonical_state))


@dataclass(frozen=True)
class NativeInvocationSpec:
    primitive: ProbePrimitive
    contract_version: str
    target_refs: tuple[str, ...]
    removed_range: FrameRange | None = None
    delta_frames: int | None = None
    produces_fragments: bool = False

    def __post_init__(self) -> None:
        _typed(self.primitive, ProbePrimitive)
        _text(self.contract_version)
        object.__setattr__(self, "target_refs", _refs(self.target_refs))
        if self.removed_range is not None:
            _typed(self.removed_range, FrameRange)
        if self.delta_frames is not None and type(self.delta_frames) is not int:
            raise TypeError("Integer delta required")
        _bool(self.produces_fragments)
        if not self.target_refs:
            raise ValueError("Explicit targets required")
        if self.primitive == ProbePrimitive.TRANSLATE_PLACEMENT:
            if self.delta_frames is None or self.removed_range is not None:
                raise ValueError("Translation requires explicit delta only")
        elif self.removed_range is None or self.delta_frames is not None:
            raise ValueError("Removal probe requires explicit range; no inferred displacement")


@dataclass(frozen=True)
class ProbeHypothesis:
    effects: tuple[ObservedChange, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "effects", _values(self.effects, ObservedChange))


@dataclass(frozen=True)
class ProbeCase:
    case_ref: str
    domain: ApplicabilityDomain
    fixture: ProbeFixture
    fixture_version: str
    invocation: NativeInvocationSpec
    hypothesis: ProbeHypothesis
    challenge: ChallengeClass | None = None

    def __post_init__(self) -> None:
        _text(self.case_ref)
        _text(self.fixture_version)
        _typed(self.domain, ApplicabilityDomain)
        _typed(self.fixture, ProbeFixture)
        _typed(self.invocation, NativeInvocationSpec)
        _typed(self.hypothesis, ProbeHypothesis)
        if self.challenge is not None:
            _typed(self.challenge, ChallengeClass)


@dataclass(frozen=True)
class NativeEffectEvidence:
    evidence_ref: str
    profile: RuntimeProfile
    pre_snapshot_ref: str
    post_snapshot_ref: str
    before: tuple[SubjectState, ...]
    after: tuple[SubjectState, ...]
    scope: ProbeObservationScope
    harness_version: str
    status: EvidenceStatus = EvidenceStatus.VALID

    def __post_init__(self) -> None:
        for ref in (
            self.evidence_ref,
            self.pre_snapshot_ref,
            self.post_snapshot_ref,
            self.harness_version,
        ):
            _text(ref)
        _typed(self.profile, RuntimeProfile)
        _typed(self.scope, ProbeObservationScope)
        _typed(self.status, EvidenceStatus)
        object.__setattr__(self, "before", _states(self.before))
        object.__setattr__(self, "after", _states(self.after))

    @property
    def observed_effects(self) -> tuple[ObservedChange, ...]:
        return observed_changes(self.before, self.after)


@dataclass(frozen=True)
class EvidenceBinding:
    profile: RuntimeProfile
    support_run_refs: tuple[str, ...]
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        _typed(self.profile, RuntimeProfile)
        _text(self.contract_version)
        object.__setattr__(self, "support_run_refs", _refs(self.support_run_refs))


@dataclass(frozen=True)
class PostReadEvidence:
    evidence_ref: str
    binding: EvidenceBinding
    status: PostReadStatus
    independent: bool
    scope: ProbeObservationScope
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.evidence_ref)
        _typed(self.binding, EvidenceBinding)
        _typed(self.status, PostReadStatus)
        _bool(self.independent)
        _typed(self.scope, ProbeObservationScope)
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs))


@dataclass(frozen=True)
class ReconciliationEvidence:
    evidence_ref: str
    binding: EvidenceBinding
    status: ReconciliationStatus
    applied_signature: tuple[SubjectState, ...]
    not_applied_signature: tuple[SubjectState, ...]
    ambiguous_signatures: tuple[str, ...]
    post_read_ref: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.evidence_ref)
        _text(self.post_read_ref)
        _typed(self.binding, EvidenceBinding)
        _typed(self.status, ReconciliationStatus)
        for field in ("applied_signature", "not_applied_signature"):
            object.__setattr__(self, field, _states(getattr(self, field)))
        for field in ("ambiguous_signatures", "evidence_refs"):
            object.__setattr__(self, field, _refs(getattr(self, field)))


class IdentityBoundary(str, Enum):
    SAME_SESSION = "SAME_SESSION"
    RELOAD = "RELOAD"
    CROSS_SESSION = "CROSS_SESSION"


@dataclass(frozen=True)
class IdentityCorrespondence:
    subject_ref: str
    pre_locator_ref: str
    post_locator_ref: str
    boundary: IdentityBoundary
    verified: bool
    evidence_ref: str

    def __post_init__(self) -> None:
        for ref in (
            self.subject_ref,
            self.pre_locator_ref,
            self.post_locator_ref,
            self.evidence_ref,
        ):
            _text(ref)
        _typed(self.boundary, IdentityBoundary)
        _bool(self.verified)


@dataclass(frozen=True)
class IdentityCapabilityEvidence:
    evidence_ref: str
    binding: EvidenceBinding
    claimed_scope: IdentityScope
    session_ref: str | None
    correspondences: tuple[IdentityCorrespondence, ...]

    def __post_init__(self) -> None:
        _text(self.evidence_ref)
        _typed(self.binding, EvidenceBinding)
        _typed(self.claimed_scope, IdentityScope)
        _optional(self.session_ref)
        object.__setattr__(
            self, "correspondences", _values(self.correspondences, IdentityCorrespondence)
        )


class FragmentBindingMethod(str, Enum):
    EXPLICIT_CORRESPONDENCE = "EXPLICIT_CORRESPONDENCE"
    RETURNED_ORDER = "RETURNED_ORDER"
    FILENAME = "FILENAME"
    POSITION = "POSITION"


@dataclass(frozen=True)
class FragmentCorrespondence:
    source_subject_ref: str
    fragment_ref: str
    evidence_ref: str
    method: FragmentBindingMethod

    def __post_init__(self) -> None:
        for ref in (self.source_subject_ref, self.fragment_ref, self.evidence_ref):
            _text(ref)
        _typed(self.method, FragmentBindingMethod)


@dataclass(frozen=True)
class FragmentCorrespondenceEvidence:
    evidence_ref: str
    binding: EvidenceBinding
    status: FragmentEvidenceStatus
    correspondences: tuple[FragmentCorrespondence, ...]

    def __post_init__(self) -> None:
        _text(self.evidence_ref)
        _typed(self.binding, EvidenceBinding)
        _typed(self.status, FragmentEvidenceStatus)
        object.__setattr__(
            self, "correspondences", _values(self.correspondences, FragmentCorrespondence)
        )


class ProbeRunStatus(str, Enum):
    PASS_OBSERVED = "PASS_OBSERVED"
    FAIL_OBSERVED = "FAIL_OBSERVED"
    INCONCLUSIVE = "INCONCLUSIVE"
    STALE = "STALE"
    INVALID_FIXTURE = "INVALID_FIXTURE"
    CONTAINMENT_FAILURE = "CONTAINMENT_FAILURE"


@dataclass(frozen=True)
class ProbeRunResult:
    run_ref: str
    instance_ref: str
    case: ProbeCase
    status: ProbeRunStatus
    effect: NativeEffectEvidence | None
    post_read: PostReadEvidence | None
    reconciliation: ReconciliationEvidence | None
    identity: IdentityCapabilityEvidence | None
    fragment: FragmentCorrespondenceEvidence | None = None
    native_success: bool | None = None
    containment_failure: bool = False
    ambiguous_target: bool = False

    def __post_init__(self) -> None:
        _text(self.run_ref)
        _text(self.instance_ref)
        _typed(self.case, ProbeCase)
        _typed(self.status, ProbeRunStatus)
        for value, kind in (
            (self.effect, NativeEffectEvidence),
            (self.post_read, PostReadEvidence),
            (self.reconciliation, ReconciliationEvidence),
            (self.identity, IdentityCapabilityEvidence),
            (self.fragment, FragmentCorrespondenceEvidence),
        ):
            if value is not None:
                _typed(value, kind)
        if self.native_success is not None:
            _bool(self.native_success)
        _bool(self.containment_failure)
        _bool(self.ambiguous_target)


@dataclass(frozen=True)
class CapabilityVerificationPolicy:
    primitive: ProbePrimitive
    version: str = "v1"

    def __post_init__(self) -> None:
        _typed(self.primitive, ProbePrimitive)
        _text(self.version)

    @property
    def positive_classes(self) -> tuple[ProbeFixtureClass, ...]:
        F = ProbeFixtureClass
        return {
            ProbePrimitive.TRANSLATE_PLACEMENT: (
                F.ISOLATED_PLACEMENT,
                F.ADJACENT_PLACEMENTS,
                F.PRE_EXISTING_GAP,
                F.REPEATED_MEDIA,
            ),
            ProbePrimitive.REMOVE_RANGE: (
                F.MIDDLE_REMOVAL,
                F.NEAR_LEADING_BOUNDARY,
                F.NEAR_TRAILING_BOUNDARY,
                F.ADJACENT_PLACEMENTS,
                F.EXISTING_DOWNSTREAM_GAP,
                F.REPEATED_MEDIA,
            ),
            ProbePrimitive.COMPOUND_RIPPLE: (
                F.SIMPLE_CONTIGUOUS_SINGLE_TRACK,
                F.EXISTING_GAPS,
                F.MULTIPLE_DOWNSTREAM,
                F.LARGE_DOWNSTREAM_SET,
                F.EXPLICIT_MULTI_TRACK,
                F.REPEATED_MEDIA,
                F.LINKED_AV,
                F.INTENTIONAL_JL,
                F.MARKERS_SUBTITLES,
                F.TRACK_CONTROL_VARIATION,
            ),
        }[self.primitive]

    @property
    def runs_per_positive_class(self) -> int:
        return 5

    @property
    def minimum_positive_runs(self) -> int:
        return len(self.positive_classes) * 5

    @property
    def runs_per_challenge_class(self) -> int:
        return 3

    @property
    def allowed_conflicts(self) -> int:
        return 0

    @property
    def allowed_side_effects(self) -> int:
        return 0

    @property
    def allowed_containment_failures(self) -> int:
        return 0

    @property
    def allowed_ambiguous_targets(self) -> int:
        return 0

    @property
    def production_editor_manual_probe_work(self) -> int:
        return 0

    @property
    def full_suite_per_edit(self) -> bool:
        return False


@dataclass(frozen=True)
class ProbeCorpus:
    domain: ApplicabilityDomain
    profile: RuntimeProfile
    primitive: ProbePrimitive
    runs: tuple[ProbeRunResult, ...]

    def __post_init__(self) -> None:
        _typed(self.domain, ApplicabilityDomain)
        _typed(self.profile, RuntimeProfile)
        _typed(self.primitive, ProbePrimitive)
        runs = tuple(sorted(_values(self.runs, ProbeRunResult), key=lambda r: r.run_ref))
        _unique(tuple(r.run_ref for r in runs))
        _unique(tuple(r.instance_ref for r in runs))
        _unique(tuple(r.effect.evidence_ref for r in runs if r.effect is not None))
        captures = tuple(
            ref
            for r in runs
            if r.effect is not None
            for ref in (r.effect.pre_snapshot_ref, r.effect.post_snapshot_ref)
        )
        _unique(captures)
        object.__setattr__(self, "runs", runs)

    def append(self, run: ProbeRunResult) -> "ProbeCorpus":
        _typed(run, ProbeRunResult)
        return ProbeCorpus(self.domain, self.profile, self.primitive, (*self.runs, run))


@dataclass(frozen=True)
class AvailabilityEvidence:
    evidence_ref: str
    profile: RuntimeProfile
    available: bool
    supporting_ref: str

    def __post_init__(self) -> None:
        _text(self.evidence_ref)
        _text(self.supporting_ref)
        _typed(self.profile, RuntimeProfile)
        _bool(self.available)


@dataclass(frozen=True)
class ProbeDerivationInput:
    model_ref: str
    corpus: ProbeCorpus
    policy: CapabilityVerificationPolicy
    current_profile: RuntimeProfile
    current_session: str
    availability: AvailabilityEvidence | None = None

    def __post_init__(self) -> None:
        _text(self.model_ref)
        _typed(self.corpus, ProbeCorpus)
        _typed(self.policy, CapabilityVerificationPolicy)
        _typed(self.current_profile, RuntimeProfile)
        _text(self.current_session)
        if self.availability is not None:
            _typed(self.availability, AvailabilityEvidence)


class QualificationReason(str, Enum):
    OUTSIDE_DOMAIN = "OUTSIDE_DOMAIN"
    DOMAIN_MISMATCH = "DOMAIN_MISMATCH"
    PROFILE_STALE = "PROFILE_STALE"
    INVALID_FIXTURE = "INVALID_FIXTURE"
    DIRTY_FIXTURE = "DIRTY_FIXTURE"
    INVOCATION_MISMATCH = "INVOCATION_MISMATCH"
    OBSERVATION_MISSING = "OBSERVATION_MISSING"
    OBSERVATION_INCOMPLETE = "OBSERVATION_INCOMPLETE"
    EVIDENCE_INVALID = "EVIDENCE_INVALID"
    SEMANTIC_CONFLICT = "SEMANTIC_CONFLICT"
    UNEXPECTED_EFFECT = "UNEXPECTED_EFFECT"
    CONTAINMENT_FAILURE = "CONTAINMENT_FAILURE"
    AMBIGUOUS_TARGET = "AMBIGUOUS_TARGET"
    RUN_NOT_PASS = "RUN_NOT_PASS"
    POST_READ_UNVERIFIED = "POST_READ_UNVERIFIED"
    RECONCILIATION_UNVERIFIED = "RECONCILIATION_UNVERIFIED"
    IDENTITY_UNVERIFIED = "IDENTITY_UNVERIFIED"
    IDENTITY_STALE = "IDENTITY_STALE"
    FRAGMENT_UNVERIFIED = "FRAGMENT_UNVERIFIED"
    UNSUPPORTED_POLICY = "UNSUPPORTED_POLICY"
    FIXTURE_COVERAGE = "FIXTURE_COVERAGE"
    CHALLENGE_COVERAGE = "CHALLENGE_COVERAGE"
    AVAILABILITY_CONFLICT = "AVAILABILITY_CONFLICT"


@dataclass(frozen=True)
class RunQualification:
    run_ref: str
    reasons: tuple[QualificationReason, ...]
    qualified: bool
    outside_domain: bool
    post_read_status: PostReadStatus
    reconciliation_status: ReconciliationStatus
    identity_status: EvidenceStatus
    fragment_status: FragmentEvidenceStatus

    def __post_init__(self) -> None:
        _text(self.run_ref)
        object.__setattr__(self, "reasons", _values(self.reasons, QualificationReason))
        _bool(self.qualified)
        _bool(self.outside_domain)
        _typed(self.post_read_status, PostReadStatus)
        _typed(self.reconciliation_status, ReconciliationStatus)
        _typed(self.identity_status, EvidenceStatus)
        _typed(self.fragment_status, FragmentEvidenceStatus)
        if self.qualified != (not self.reasons and not self.outside_domain):
            raise ValueError("Qualification must preserve blockers")


def _binding_current(
    binding: EvidenceBinding, run: ProbeRunResult, v: ProbeDerivationInput
) -> bool:
    known = {r.run_ref for r in v.corpus.runs}
    return (
        binding.profile == v.current_profile
        and binding.contract_version == v.current_profile.evidence_contract
        and run.run_ref in binding.support_run_refs
        and set(binding.support_run_refs) <= known
    )


def _post_read(run: ProbeRunResult, v: ProbeDerivationInput) -> PostReadStatus:
    e, raw = run.post_read, run.effect
    if e is None:
        return PostReadStatus.UNKNOWN
    if e.binding.profile != v.current_profile or e.status == PostReadStatus.STALE:
        return PostReadStatus.STALE
    if (
        raw is None
        or e.status != PostReadStatus.VERIFIED
        or not _binding_current(e.binding, run, v)
        or not e.independent
        or not e.evidence_refs
        or e.scope.completeness != ScopeCompleteness.COMPLETE
        or not set(raw.scope.subject_refs) <= set(e.scope.subject_refs)
        or not set(raw.scope.kinds) <= set(e.scope.kinds)
    ):
        return PostReadStatus.UNVERIFIED
    return PostReadStatus.VERIFIED


def _reconciliation(
    run: ProbeRunResult, v: ProbeDerivationInput, post: PostReadStatus
) -> ReconciliationStatus:
    e, raw = run.reconciliation, run.effect
    if e is None:
        return ReconciliationStatus.UNVERIFIED
    if e.binding.profile != v.current_profile or e.status == ReconciliationStatus.STALE:
        return ReconciliationStatus.STALE
    if (
        e.status == ReconciliationStatus.AMBIGUOUS
        or e.ambiguous_signatures
        or e.applied_signature == e.not_applied_signature
    ):
        return ReconciliationStatus.AMBIGUOUS
    if (
        e.status != ReconciliationStatus.VERIFIED
        or raw is None
        or not _binding_current(e.binding, run, v)
        or post != PostReadStatus.VERIFIED
        or run.post_read is None
        or e.post_read_ref != run.post_read.evidence_ref
        or not e.evidence_refs
        or e.applied_signature != raw.after
        or e.not_applied_signature != raw.before
    ):
        return ReconciliationStatus.UNVERIFIED
    return ReconciliationStatus.VERIFIED


def _identity(run: ProbeRunResult, v: ProbeDerivationInput) -> EvidenceStatus:
    e = run.identity
    if e is None:
        return EvidenceStatus.INCOMPLETE
    if e.binding.profile != v.current_profile:
        return EvidenceStatus.STALE
    if (
        e.claimed_scope == IdentityScope.SESSION_LOCAL_VERIFIED
        and e.session_ref is not None
        and e.session_ref != v.current_session
    ):
        return EvidenceStatus.STALE
    if not _binding_current(e.binding, run, v):
        return EvidenceStatus.INCOMPLETE
    if e.claimed_scope not in (
        IdentityScope.PERSISTENT_VERIFIED,
        IdentityScope.SESSION_LOCAL_VERIFIED,
    ):
        return EvidenceStatus.INCOMPLETE
    if e.claimed_scope == IdentityScope.SESSION_LOCAL_VERIFIED and e.session_ref is None:
        return EvidenceStatus.INCOMPLETE
    subjects = set(run.case.invocation.target_refs)
    if run.effect is not None:
        subjects.update(c.subject_ref for c in run.effect.observed_effects)
    if not subjects or not e.correspondences or any(not c.verified for c in e.correspondences):
        return EvidenceStatus.INCOMPLETE
    proven = {
        c.subject_ref
        for c in e.correspondences
        if c.verified
        and (
            e.claimed_scope == IdentityScope.SESSION_LOCAL_VERIFIED
            or c.boundary in (IdentityBoundary.RELOAD, IdentityBoundary.CROSS_SESSION)
        )
    }
    return EvidenceStatus.VALID if subjects <= proven else EvidenceStatus.INCOMPLETE


def _fragments(run: ProbeRunResult, v: ProbeDerivationInput) -> FragmentEvidenceStatus:
    e = run.fragment
    if e is None:
        return FragmentEvidenceStatus.UNKNOWN
    if not _binding_current(e.binding, run, v):
        return FragmentEvidenceStatus.UNKNOWN
    if e.status != FragmentEvidenceStatus.VERIFIED:
        return e.status
    if not e.correspondences:
        return FragmentEvidenceStatus.UNKNOWN
    if any(c.method != FragmentBindingMethod.EXPLICIT_CORRESPONDENCE for c in e.correspondences):
        return FragmentEvidenceStatus.UNSUPPORTED
    if len({c.fragment_ref for c in e.correspondences}) != len(e.correspondences):
        return FragmentEvidenceStatus.AMBIGUOUS
    if not set(run.case.invocation.target_refs) <= {
        c.source_subject_ref for c in e.correspondences
    }:
        return FragmentEvidenceStatus.UNKNOWN
    return FragmentEvidenceStatus.VERIFIED


def qualify_run(run: ProbeRunResult, v: ProbeDerivationInput) -> RunQualification:
    _typed(run, ProbeRunResult)
    _typed(v, ProbeDerivationInput)
    R = QualificationReason
    reasons: set[QualificationReason] = set()
    case, fixture, raw = run.case, run.case.fixture, run.effect
    outside = (
        case.domain == v.corpus.domain
        and case.challenge is not None
        and not next(d.applicable for d in case.domain.challenges if d.kind == case.challenge)
    )
    if outside:
        reasons.add(R.OUTSIDE_DOMAIN)
    if case.domain != v.corpus.domain:
        reasons.add(R.DOMAIN_MISMATCH)
    if case.challenge is None and fixture.fixture_class not in v.policy.positive_classes:
        reasons.add(R.FIXTURE_COVERAGE)
    if v.corpus.profile != v.current_profile:
        reasons.add(R.PROFILE_STALE)
    if (
        case.invocation.primitive != v.corpus.primitive
        or case.invocation.contract_version != v.current_profile.invocation_contract
        or not case.invocation.target_refs
    ):
        reasons.add(R.INVOCATION_MISMATCH)
    if (
        fixture.production
        or fixture.authoritative
        or not fixture.disposable
        or not fixture.isolated
        or fixture.registry_ref is None
        or fixture.fixture_version != case.fixture_version
        or not fixture.canonical_state
    ):
        reasons.add(R.INVALID_FIXTURE)
    if run.status != ProbeRunStatus.PASS_OBSERVED:
        reasons.add(R.RUN_NOT_PASS)
    if run.status == ProbeRunStatus.STALE:
        reasons.add(R.PROFILE_STALE)
    if run.status == ProbeRunStatus.INVALID_FIXTURE:
        reasons.add(R.INVALID_FIXTURE)
    if run.ambiguous_target:
        reasons.add(R.AMBIGUOUS_TARGET)
    if run.containment_failure or run.status == ProbeRunStatus.CONTAINMENT_FAILURE:
        reasons.add(R.CONTAINMENT_FAILURE)
    if raw is None:
        reasons.add(R.OBSERVATION_MISSING)
    else:
        if raw.profile != v.current_profile or raw.status == EvidenceStatus.STALE:
            reasons.add(R.PROFILE_STALE)
        if raw.before != fixture.canonical_state:
            reasons.add(R.DIRTY_FIXTURE)
        if raw.status == EvidenceStatus.CONFLICTING:
            reasons.add(R.SEMANTIC_CONFLICT)
        elif raw.status not in (EvidenceStatus.VALID, EvidenceStatus.STALE):
            reasons.add(R.EVIDENCE_INVALID)
        subjects = {s.subject_ref for s in (*raw.before, *raw.after)}
        if (
            raw.scope.completeness != ScopeCompleteness.COMPLETE
            or subjects != set(raw.scope.subject_refs)
            or not {s.kind for s in (*raw.before, *raw.after)} <= set(raw.scope.kinds)
            or raw.pre_snapshot_ref == raw.post_snapshot_ref
        ):
            reasons.add(R.OBSERVATION_INCOMPLETE)
        if not subjects <= set(raw.scope.subject_refs):
            reasons.add(R.CONTAINMENT_FAILURE)
        if not set(case.invocation.target_refs) <= {s.subject_ref for s in raw.before}:
            reasons.add(R.AMBIGUOUS_TARGET)
        if Counter(raw.observed_effects) != Counter(case.hypothesis.effects):
            reasons.add(R.UNEXPECTED_EFFECT)
    post = _post_read(run, v)
    recon = _reconciliation(run, v, post)
    identity = _identity(run, v)
    fragment = _fragments(run, v)
    if post != PostReadStatus.VERIFIED:
        reasons.add(R.POST_READ_UNVERIFIED)
    if recon != ReconciliationStatus.VERIFIED:
        reasons.add(R.RECONCILIATION_UNVERIFIED)
    if identity != EvidenceStatus.VALID:
        reasons.add(R.IDENTITY_UNVERIFIED)
    if identity == EvidenceStatus.STALE:
        reasons.add(R.IDENTITY_STALE)
    if post == PostReadStatus.STALE or recon == ReconciliationStatus.STALE:
        reasons.add(R.PROFILE_STALE)
    if case.invocation.produces_fragments and fragment != FragmentEvidenceStatus.VERIFIED:
        reasons.add(R.FRAGMENT_UNVERIFIED)
    if run.fragment is not None and run.fragment.binding.profile != v.current_profile:
        reasons.add(R.PROFILE_STALE)
    return RunQualification(
        run.run_ref,
        tuple(sorted(reasons, key=lambda r: r.value)),
        not reasons,
        outside,
        post,
        recon,
        identity,
        fragment,
    )


@dataclass(frozen=True)
class CoverageCount:
    class_ref: str
    required: int
    qualified: int

    def __post_init__(self) -> None:
        _text(self.class_ref)
        if type(self.required) is not int or type(self.qualified) is not int:
            raise TypeError("Integer counts required")
        if self.required < 0 or self.qualified < 0:
            raise ValueError("Nonnegative counts required")


def _derive(
    v: ProbeDerivationInput,
) -> tuple[
    EffectModelStatus,
    NativeCapabilityStatus,
    tuple[RunQualification, ...],
    tuple[CoverageCount, ...],
    tuple[QualificationReason, ...],
]:
    R = QualificationReason
    runs = tuple(qualify_run(r, v) for r in v.corpus.runs)
    by_ref = {r.run_ref: r for r in v.corpus.runs}
    inside = tuple(r for r in runs if not r.outside_domain)
    reasons = {reason for r in inside for reason in r.reasons}
    if v.corpus.profile != v.current_profile:
        reasons.add(R.PROFILE_STALE)
    if (
        v.policy.version != "v1"
        or v.policy.primitive != v.corpus.primitive
        or v.current_profile.verification_policy_version != v.policy.version
        or any(
            version != "v1"
            for version in (
                v.current_profile.evidence_contract,
                v.current_profile.model_contract,
                v.current_profile.profile_contract,
            )
        )
    ):
        reasons.add(R.UNSUPPORTED_POLICY)
    positive = Counter(
        by_ref[r.run_ref].case.fixture.fixture_class
        for r in inside
        if r.qualified and by_ref[r.run_ref].case.challenge is None
    )
    challenges = Counter(
        by_ref[r.run_ref].case.challenge
        for r in inside
        if r.qualified and by_ref[r.run_ref].case.challenge is not None
    )
    counts = tuple(
        CoverageCount("positive:" + c.value, 5, positive[c]) for c in v.policy.positive_classes
    ) + tuple(
        CoverageCount("challenge:" + d.kind.value, 3, challenges[d.kind])
        for d in v.corpus.domain.challenges
        if d.applicable
    )
    if any(c.qualified < c.required for c in counts if c.class_ref.startswith("positive:")):
        reasons.add(R.FIXTURE_COVERAGE)
    if any(c.qualified < c.required for c in counts if c.class_ref.startswith("challenge:")):
        reasons.add(R.CHALLENGE_COVERAGE)
    observed_sets = set()
    for q in inside:
        raw = by_ref[q.run_ref].effect
        if raw is not None and not {
            R.INVALID_FIXTURE,
            R.DIRTY_FIXTURE,
            R.PROFILE_STALE,
            R.DOMAIN_MISMATCH,
            R.OBSERVATION_INCOMPLETE,
        } & set(q.reasons):
            observed_sets.add(raw.observed_effects)
    if len(observed_sets) > 1 or R.UNEXPECTED_EFFECT in reasons:
        reasons.add(R.SEMANTIC_CONFLICT)
    available = v.availability
    if available is not None:
        if available.profile != v.current_profile:
            reasons.add(R.PROFILE_STALE)
        elif not available.available and inside:
            reasons.add(R.AVAILABILITY_CONFLICT)
    if R.PROFILE_STALE in reasons or R.IDENTITY_STALE in reasons:
        status = EffectModelStatus.STALE
    elif R.SEMANTIC_CONFLICT in reasons:
        status = EffectModelStatus.CONFLICTING
    elif not inside:
        status = EffectModelStatus.UNKNOWN
    elif reasons:
        status = EffectModelStatus.UNVERIFIED
    else:
        status = EffectModelStatus.VERIFIED
    if available is not None and available.profile == v.current_profile and not available.available:
        capability = NativeCapabilityStatus.UNSUPPORTED
    elif status == EffectModelStatus.VERIFIED:
        capability = NativeCapabilityStatus.SUPPORTED_VERIFIED
    elif inside or (
        available is not None and available.profile == v.current_profile and available.available
    ):
        capability = NativeCapabilityStatus.SUPPORTED_UNVERIFIED
    else:
        capability = NativeCapabilityStatus.UNKNOWN
    return status, capability, runs, counts, tuple(sorted(reasons, key=lambda r: r.value))


@dataclass(frozen=True)
class NativeEffectModel:
    """Derived artifact retains its raw corpus; not a production executor manifest."""

    inputs: ProbeDerivationInput
    model_status: EffectModelStatus
    capability_status: NativeCapabilityStatus
    runs: tuple[RunQualification, ...]
    coverage: tuple[CoverageCount, ...]
    reasons: tuple[QualificationReason, ...]

    def __post_init__(self) -> None:
        _typed(self.inputs, ProbeDerivationInput)
        _typed(self.model_status, EffectModelStatus)
        _typed(self.capability_status, NativeCapabilityStatus)
        runs = tuple(self.runs)
        coverage = tuple(self.coverage)
        reasons = tuple(self.reasons)
        if (self.model_status, self.capability_status, runs, coverage, reasons) != _derive(
            self.inputs
        ):
            raise ValueError("Derived status must match complete evidence")
        object.__setattr__(self, "runs", runs)
        object.__setattr__(self, "coverage", coverage)
        object.__setattr__(self, "reasons", reasons)

    @property
    def positive_count(self) -> int:
        return sum(c.qualified for c in self.coverage if c.class_ref.startswith("positive:"))

    @property
    def challenge_count(self) -> int:
        return sum(c.qualified for c in self.coverage if c.class_ref.startswith("challenge:"))

    @property
    def outside_domain_run_refs(self) -> tuple[str, ...]:
        return tuple(r.run_ref for r in self.runs if r.outside_domain)

    @property
    def outside_domain_status(self) -> NativeCapabilityStatus:
        return NativeCapabilityStatus.UNSUPPORTED

    @property
    def observed_effect_sets(self) -> tuple[tuple[ObservedChange, ...], ...]:
        return tuple(
            r.effect.observed_effects for r in self.inputs.corpus.runs if r.effect is not None
        )

    @property
    def verified_effects(self) -> tuple[ObservedChange, ...] | None:
        if self.model_status != EffectModelStatus.VERIFIED:
            return None
        qualified = {r.run_ref for r in self.runs if r.qualified}
        effects = {
            r.effect.observed_effects
            for r in self.inputs.corpus.runs
            if r.run_ref in qualified and r.effect is not None
        }
        # The derivation already requires one exact agreeing set; no ranked selection.
        return next(iter(effects)) if len(effects) == 1 else None


def derive_capability(inputs: ProbeDerivationInput) -> NativeEffectModel:
    _typed(inputs, ProbeDerivationInput)
    return NativeEffectModel(inputs, *_derive(inputs))
