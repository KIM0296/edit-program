"""ADR-028 structural validation of supplied IR/evidence; no native execution or probing."""

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias, TypeVar

from .domain import TimelineObjectId
from .expected_diff import ExpectedDiff, PlacementState, RangeRemovalEffect, TemporalDisplacement
from .native_snapshot import IdentityScope, ObservedValue
from .safety_preflight import PreflightStatus, SafetyPreflightResult, SafetyVerdict
from .temporal_mapping import NativeSnapshotRef
from .transaction import ArtifactBinding, ExecutionAuthorization, RollbackCapability

T = TypeVar("T")
SemanticEffect: TypeAlias = RangeRemovalEffect | TemporalDisplacement


def _typed(value: object, kind: type[object]) -> None:
    if not isinstance(value, kind):
        raise TypeError(f"Expected {kind.__name__}")


def _text(value: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError("Nonempty opaque reference/version required")


def _optional(value: str | None) -> None:
    if value is not None:
        _text(value)


def _tuple(values: tuple[T, ...], kind: type[T]) -> tuple[T, ...]:
    result = tuple(values)
    for value in result:
        _typed(value, kind)
    return result


def _refs(values: tuple[str, ...]) -> tuple[str, ...]:
    result = tuple(values)
    for value in result:
        _text(value)
    return result


def _effects(values: tuple[SemanticEffect, ...]) -> tuple[SemanticEffect, ...]:
    result = tuple(values)
    for value in result:
        if not isinstance(value, (RangeRemovalEffect, TemporalDisplacement)):
            raise TypeError("Only Pause v1 effects")
    return tuple(sorted(result, key=repr))


class ExecutionOpKind(str, Enum):
    REMOVE_RANGE = "REMOVE_RANGE"
    TRANSLATE_PLACEMENT = "TRANSLATE_PLACEMENT"


class TargetResolutionStatus(str, Enum):
    VERIFIED = "VERIFIED"
    STALE = "STALE"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"
    UNSUPPORTED = "UNSUPPORTED"


class NativeCapabilityStatus(str, Enum):
    SUPPORTED_VERIFIED = "SUPPORTED_VERIFIED"
    SUPPORTED_UNVERIFIED = "SUPPORTED_UNVERIFIED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class EffectModelStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTING = "CONFLICTING"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class ExecutionIRValidationStatus(str, Enum):
    READY_FOR_EXECUTION = "READY_FOR_EXECUTION"
    STALE = "STALE"
    INVALID = "INVALID"
    UNSUPPORTED = "UNSUPPORTED"
    INCOMPLETE = "INCOMPLETE"


class ExecutionIRValidationReason(str, Enum):
    ARTIFACT_BINDING = "ARTIFACT_BINDING"
    SAFETY_NOT_PASS = "SAFETY_NOT_PASS"
    AUTHORIZATION_NOT_CURRENT = "AUTHORIZATION_NOT_CURRENT"
    LOGICAL_COVERAGE = "LOGICAL_COVERAGE"
    REALIZATION_COVERAGE = "REALIZATION_COVERAGE"
    TARGET_BINDING = "TARGET_BINDING"
    TARGET_RESOLUTION = "TARGET_RESOLUTION"
    IDENTITY_SCOPE = "IDENTITY_SCOPE"
    IDENTITY_PROOF = "IDENTITY_PROOF"
    CAPABILITY = "CAPABILITY"
    EFFECT_MODEL = "EFFECT_MODEL"
    EFFECT_EQUALITY = "EFFECT_EQUALITY"
    SCOPE_CONTAINMENT = "SCOPE_CONTAINMENT"
    FRAGMENT_REBINDING = "FRAGMENT_REBINDING"
    RECONCILIATION = "RECONCILIATION"
    POST_READ = "POST_READ"
    RUNTIME_PROFILE = "RUNTIME_PROFILE"
    CONTRACT_VERSION = "CONTRACT_VERSION"


@dataclass(frozen=True)
class RuntimeProfile:
    adapter_name: str
    adapter_version: str
    resolve_version: str
    platform: str
    session_ref: str

    def __post_init__(self) -> None:
        for v in (
            self.adapter_name,
            self.adapter_version,
            self.resolve_version,
            self.platform,
            self.session_ref,
        ):
            _text(v)


@dataclass(frozen=True)
class RemoveRangeOp:
    op_ref: str
    target_ref: str
    effect: RangeRemovalEffect

    def __post_init__(self) -> None:
        _text(self.op_ref)
        _text(self.target_ref)
        _typed(self.effect, RangeRemovalEffect)

    @property
    def kind(self) -> ExecutionOpKind:
        return ExecutionOpKind.REMOVE_RANGE


@dataclass(frozen=True)
class TranslatePlacementOp:
    op_ref: str
    target_ref: str
    effect: TemporalDisplacement

    def __post_init__(self) -> None:
        _text(self.op_ref)
        _text(self.target_ref)
        _typed(self.effect, TemporalDisplacement)

    @property
    def kind(self) -> ExecutionOpKind:
        return ExecutionOpKind.TRANSLATE_PLACEMENT


ExecutionOp: TypeAlias = RemoveRangeOp | TranslatePlacementOp


@dataclass(frozen=True)
class ExecutionTargetBinding:
    target_ref: str
    binding: ArtifactBinding
    before: PlacementState
    identity_scope: IdentityScope
    resolution: TargetResolutionStatus
    session_ref: str
    native_locator_ref: str | None = None
    identity_proof_ref: str | None = None
    locator_proof_ref: str | None = None
    mutation_stability_ref: str | None = None
    postflight_correspondence_ref: str | None = None
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        for v in (self.target_ref, self.session_ref, self.contract_version):
            _text(v)
        _typed(self.binding, ArtifactBinding)
        _typed(self.before, PlacementState)
        _typed(self.identity_scope, IdentityScope)
        _typed(self.resolution, TargetResolutionStatus)
        for optional_ref in (
            self.native_locator_ref,
            self.identity_proof_ref,
            self.locator_proof_ref,
            self.mutation_stability_ref,
            self.postflight_correspondence_ref,
        ):
            _optional(optional_ref)


@dataclass(frozen=True)
class ExecutionIR:
    ir_ref: str
    authorization: ExecutionAuthorization
    ops: tuple[ExecutionOp, ...]
    targets: tuple[ExecutionTargetBinding, ...]
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        _text(self.ir_ref)
        _text(self.contract_version)
        _typed(self.authorization, ExecutionAuthorization)
        ops = tuple(self.ops)
        for op in ops:
            if not isinstance(op, (RemoveRangeOp, TranslatePlacementOp)):
                raise TypeError("Bounded IR only")
        object.__setattr__(self, "ops", tuple(sorted(ops, key=lambda o: o.op_ref)))
        object.__setattr__(
            self,
            "targets",
            tuple(sorted(_tuple(self.targets, ExecutionTargetBinding), key=lambda t: t.target_ref)),
        )


@dataclass(frozen=True)
class PrimitiveCapability:
    primitive_kind: str
    status: NativeCapabilityStatus

    def __post_init__(self) -> None:
        _text(self.primitive_kind)
        _typed(self.status, NativeCapabilityStatus)


@dataclass(frozen=True)
class ExecutorCapabilityManifest:
    profile: RuntimeProfile
    primitives: tuple[PrimitiveCapability, ...]
    target_identity: NativeCapabilityStatus
    post_read: NativeCapabilityStatus
    reconciliation: NativeCapabilityStatus
    rollback_capability: RollbackCapability = RollbackCapability.UNKNOWN
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        _typed(self.profile, RuntimeProfile)
        _text(self.contract_version)
        for v in (self.target_identity, self.post_read, self.reconciliation):
            _typed(v, NativeCapabilityStatus)
        _typed(self.rollback_capability, RollbackCapability)
        values = _tuple(self.primitives, PrimitiveCapability)
        if len({p.primitive_kind for p in values}) != len(values):
            raise ValueError("Duplicate primitive capability")
        object.__setattr__(
            self, "primitives", tuple(sorted(values, key=lambda p: p.primitive_kind))
        )


@dataclass(frozen=True)
class NativeEffectModel:
    effect_model_ref: str
    binding: ArtifactBinding
    profile: RuntimeProfile
    status: EffectModelStatus
    step_refs: tuple[str, ...]
    primitive_kinds: tuple[str, ...]
    op_refs: tuple[str, ...]
    predicted_effects: tuple[SemanticEffect, ...]
    possible_subjects: tuple[TimelineObjectId, ...]
    evidence_refs: tuple[str, ...]
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        _text(self.effect_model_ref)
        _text(self.contract_version)
        _typed(self.binding, ArtifactBinding)
        _typed(self.profile, RuntimeProfile)
        _typed(self.status, EffectModelStatus)
        for f in ("step_refs", "primitive_kinds", "op_refs", "evidence_refs"):
            object.__setattr__(self, f, _refs(getattr(self, f)))
        object.__setattr__(self, "predicted_effects", _effects(self.predicted_effects))
        object.__setattr__(
            self,
            "possible_subjects",
            tuple(sorted(_tuple(self.possible_subjects, TimelineObjectId), key=repr)),
        )


@dataclass(frozen=True)
class ReconciliationSpec:
    reconciliation_ref: str
    binding: ArtifactBinding
    profile: RuntimeProfile
    step_ref: str
    status: EffectModelStatus
    observable_subjects: tuple[PlacementState, ...]
    applied_state_ref: str | None
    not_applied_state_ref: str | None
    read_evidence_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        for v in (self.reconciliation_ref, self.step_ref, self.contract_version):
            _text(v)
        _typed(self.binding, ArtifactBinding)
        _typed(self.profile, RuntimeProfile)
        _typed(self.status, EffectModelStatus)
        for optional_ref in (self.applied_state_ref, self.not_applied_state_ref):
            _optional(optional_ref)
        for f in ("read_evidence_refs", "evidence_refs"):
            object.__setattr__(self, f, _refs(getattr(self, f)))
        object.__setattr__(
            self,
            "observable_subjects",
            tuple(sorted(_tuple(self.observable_subjects, PlacementState), key=repr)),
        )


@dataclass(frozen=True)
class NativeExecutionStep:
    step_ref: str
    primitive_kind: str
    target_refs: tuple[str, ...]
    reconciliation: ReconciliationSpec | None
    post_read: NativeCapabilityStatus

    def __post_init__(self) -> None:
        _text(self.step_ref)
        _text(self.primitive_kind)
        object.__setattr__(self, "target_refs", tuple(sorted(_refs(self.target_refs))))
        if self.reconciliation is not None:
            _typed(self.reconciliation, ReconciliationSpec)
        _typed(self.post_read, NativeCapabilityStatus)


class FragmentPath(str, Enum):
    COMPOUND_PRIMITIVE = "COMPOUND_PRIMITIVE"
    INTERMEDIATE_REBINDING = "INTERMEDIATE_REBINDING"


@dataclass(frozen=True)
class FragmentEvidence:
    evidence_ref: str
    binding: ArtifactBinding
    profile: RuntimeProfile
    realization_ref: str
    step_refs: tuple[str, ...]
    status: EffectModelStatus
    path: FragmentPath
    evidence_refs: tuple[str, ...]
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        for v in (self.evidence_ref, self.realization_ref, self.contract_version):
            _text(v)
        _typed(self.binding, ArtifactBinding)
        _typed(self.profile, RuntimeProfile)
        _typed(self.status, EffectModelStatus)
        _typed(self.path, FragmentPath)
        object.__setattr__(self, "step_refs", _refs(self.step_refs))
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs))


@dataclass(frozen=True)
class LoweringRealization:
    realization_ref: str
    op_refs: tuple[str, ...]
    step_refs: tuple[str, ...]
    effect_model: NativeEffectModel
    produces_fragments: bool = False
    fragment_evidence: FragmentEvidence | None = None

    def __post_init__(self) -> None:
        _text(self.realization_ref)
        object.__setattr__(self, "op_refs", tuple(sorted(_refs(self.op_refs))))
        object.__setattr__(self, "step_refs", _refs(self.step_refs))
        _typed(self.effect_model, NativeEffectModel)
        if type(self.produces_fragments) is not bool:
            raise TypeError("Explicit fragment fact required")
        if self.fragment_evidence is not None:
            _typed(self.fragment_evidence, FragmentEvidence)


@dataclass(frozen=True)
class NativeLoweringPlan:
    lowering_ref: str
    execution_ir_ref: str
    binding: ArtifactBinding
    profile: RuntimeProfile
    steps: tuple[NativeExecutionStep, ...]
    realizations: tuple[LoweringRealization, ...]
    contract_version: str = "v1"

    def __post_init__(self) -> None:
        for v in (self.lowering_ref, self.execution_ir_ref, self.contract_version):
            _text(v)
        _typed(self.binding, ArtifactBinding)
        _typed(self.profile, RuntimeProfile)
        object.__setattr__(self, "steps", _tuple(self.steps, NativeExecutionStep))
        object.__setattr__(
            self,
            "realizations",
            tuple(
                sorted(
                    _tuple(self.realizations, LoweringRealization), key=lambda r: r.realization_ref
                )
            ),
        )


@dataclass(frozen=True)
class ExecutionIRValidationInput:
    expected_diff: ExpectedDiff
    safety_result_ref: str
    safety: SafetyPreflightResult
    execution_ir: ExecutionIR
    lowering: NativeLoweringPlan
    manifest: ExecutorCapabilityManifest
    current_snapshot: NativeSnapshotRef
    current_profile: RuntimeProfile
    authorization_current: ObservedValue

    def __post_init__(self) -> None:
        _typed(self.expected_diff, ExpectedDiff)
        _text(self.safety_result_ref)
        _typed(self.safety, SafetyPreflightResult)
        _typed(self.execution_ir, ExecutionIR)
        _typed(self.lowering, NativeLoweringPlan)
        _typed(self.manifest, ExecutorCapabilityManifest)
        _typed(self.current_snapshot, NativeSnapshotRef)
        _typed(self.current_profile, RuntimeProfile)
        _typed(self.authorization_current, ObservedValue)


@dataclass(frozen=True)
class ValidationFinding:
    status: ExecutionIRValidationStatus
    reason: ExecutionIRValidationReason
    subject_ref: str

    def __post_init__(self) -> None:
        _typed(self.status, ExecutionIRValidationStatus)
        _typed(self.reason, ExecutionIRValidationReason)
        _text(self.subject_ref)
        if self.status == ExecutionIRValidationStatus.READY_FOR_EXECUTION:
            raise ValueError("Finding must block readiness")


def _findings(v: ExecutionIRValidationInput) -> tuple[ValidationFinding, ...]:
    S, R = ExecutionIRValidationStatus, ExecutionIRValidationReason
    findings: list[ValidationFinding] = []

    def add(
        status: ExecutionIRValidationStatus, reason: ExecutionIRValidationReason, ref: str
    ) -> None:
        findings.append(ValidationFinding(status, reason, ref))

    diff, logical, plan, manifest = v.expected_diff, v.execution_ir, v.lowering, v.manifest
    binding = ArtifactBinding(diff.expected_diff_ref, v.safety_result_ref, diff.base_snapshot)

    def bound(b: ArtifactBinding, profile: RuntimeProfile | None, ref: str) -> None:
        if b.base_snapshot != binding.base_snapshot:
            add(S.STALE, R.ARTIFACT_BINDING, ref)
        elif b != binding:
            add(S.INVALID, R.ARTIFACT_BINDING, ref)
        if profile is not None and profile != v.current_profile:
            add(S.STALE, R.RUNTIME_PROFILE, ref)

    def version(value: str, ref: str) -> None:
        if value != "v1":
            add(S.UNSUPPORTED, R.CONTRACT_VERSION, ref)

    def capability(
        value: NativeCapabilityStatus, reason: ExecutionIRValidationReason, ref: str
    ) -> None:
        if value != NativeCapabilityStatus.SUPPORTED_VERIFIED:
            add(
                S.UNSUPPORTED if value == NativeCapabilityStatus.UNSUPPORTED else S.INCOMPLETE,
                reason,
                ref,
            )

    def model_status(
        value: EffectModelStatus, reason: ExecutionIRValidationReason, ref: str
    ) -> None:
        statuses = {
            EffectModelStatus.STALE: S.STALE,
            EffectModelStatus.CONFLICTING: S.INVALID,
            EffectModelStatus.UNKNOWN: S.INCOMPLETE,
            EffectModelStatus.UNVERIFIED: S.INCOMPLETE,
        }
        if value in statuses:
            add(statuses[value], reason, ref)

    auth = logical.authorization
    bound(auth.binding, None, auth.authorization_ref)
    bound(plan.binding, plan.profile, plan.lowering_ref)
    if (
        v.current_snapshot != diff.base_snapshot
        or v.safety.inputs.current_snapshot != diff.base_snapshot
    ):
        add(S.STALE, R.ARTIFACT_BINDING, logical.ir_ref)
    if v.authorization_current != ObservedValue.TRUE:
        add(
            S.STALE if v.authorization_current == ObservedValue.FALSE else S.INCOMPLETE,
            R.AUTHORIZATION_NOT_CURRENT,
            auth.authorization_ref,
        )
    if v.safety.inputs.compilation.expected_diff != diff:
        add(S.INVALID, R.ARTIFACT_BINDING, v.safety_result_ref)
    if v.safety.status == PreflightStatus.STALE:
        add(S.STALE, R.SAFETY_NOT_PASS, v.safety_result_ref)
    elif v.safety.status == PreflightStatus.UNSUPPORTED:
        add(S.UNSUPPORTED, R.SAFETY_NOT_PASS, v.safety_result_ref)
    elif v.safety.status != PreflightStatus.EVALUATED:
        add(S.INCOMPLETE, R.SAFETY_NOT_PASS, v.safety_result_ref)
    elif v.safety.verdict != SafetyVerdict.PASS:
        add(S.INVALID, R.SAFETY_NOT_PASS, v.safety_result_ref)
    for value, ref in (
        (logical.contract_version, logical.ir_ref),
        (auth.contract_version, auth.authorization_ref),
        (plan.contract_version, plan.lowering_ref),
        (manifest.contract_version, "manifest"),
    ):
        version(value, ref)
    if plan.execution_ir_ref != logical.ir_ref:
        add(S.INVALID, R.ARTIFACT_BINDING, plan.lowering_ref)
    approved = Counter((*diff.primary_changes, *diff.displacements))
    if Counter(o.effect for o in logical.ops) != approved:
        add(S.INVALID, R.LOGICAL_COVERAGE, logical.ir_ref)
    ops = {o.op_ref: o for o in logical.ops}
    targets = {t.target_ref: t for t in logical.targets}
    steps = {s.step_ref: s for s in plan.steps}
    if len(ops) != len(logical.ops) or len(targets) != len(logical.targets):
        add(S.INVALID, R.LOGICAL_COVERAGE, logical.ir_ref)
    if set(targets) != {o.target_ref for o in logical.ops}:
        add(S.INVALID, R.TARGET_BINDING, logical.ir_ref)
    if len(steps) != len(plan.steps) or len({r.realization_ref for r in plan.realizations}) != len(
        plan.realizations
    ):
        add(S.INVALID, R.REALIZATION_COVERAGE, plan.lowering_ref)
    if Counter(x for r in plan.realizations for x in r.op_refs) != Counter(ops.keys()):
        add(S.INVALID, R.REALIZATION_COVERAGE, plan.lowering_ref)
    if Counter(x for r in plan.realizations for x in r.step_refs) != Counter(steps.keys()):
        add(S.INVALID, R.REALIZATION_COVERAGE, plan.lowering_ref)
    for op in logical.ops:
        t = targets.get(op.target_ref)
        if t is None or t.before != op.effect.before:
            add(S.INVALID, R.TARGET_BINDING, op.op_ref)
    for t in logical.targets:
        bound(t.binding, None, t.target_ref)
        version(t.contract_version, t.target_ref)
        if t.session_ref != v.current_profile.session_ref:
            add(S.STALE, R.RUNTIME_PROFILE, t.target_ref)
        if t.resolution != TargetResolutionStatus.VERIFIED:
            status = {
                TargetResolutionStatus.STALE: S.STALE,
                TargetResolutionStatus.UNSUPPORTED: S.UNSUPPORTED,
            }.get(t.resolution, S.INCOMPLETE)
            add(status, R.TARGET_RESOLUTION, t.target_ref)
        if t.identity_scope == IdentityScope.SNAPSHOT_LOCAL:
            add(S.UNSUPPORTED, R.IDENTITY_SCOPE, t.target_ref)
        elif t.identity_scope == IdentityScope.UNKNOWN:
            add(S.INCOMPLETE, R.IDENTITY_SCOPE, t.target_ref)
        if not all((t.native_locator_ref, t.identity_proof_ref, t.locator_proof_ref)):
            add(S.INCOMPLETE, R.IDENTITY_PROOF, t.target_ref)
        if t.identity_scope == IdentityScope.SESSION_LOCAL_VERIFIED and not all(
            (t.mutation_stability_ref, t.postflight_correspondence_ref)
        ):
            add(S.INCOMPLETE, R.IDENTITY_PROOF, t.target_ref)
    capability(manifest.target_identity, R.CAPABILITY, "manifest")
    capability(manifest.reconciliation, R.RECONCILIATION, "manifest")
    capability(manifest.post_read, R.POST_READ, "manifest")
    caps = {p.primitive_kind: p.status for p in manifest.primitives}
    scope = {p.object_id: p for p in diff.inputs.scope.objects}
    predictions: list[SemanticEffect] = []
    for r in plan.realizations:
        m = r.effect_model
        bound(m.binding, m.profile, m.effect_model_ref)
        version(m.contract_version, m.effect_model_ref)
        model_status(m.status, R.EFFECT_MODEL, m.effect_model_ref)
        if not m.evidence_refs:
            add(S.INCOMPLETE, R.EFFECT_MODEL, m.effect_model_ref)
        selected = [ops[x] for x in r.op_refs if x in ops]
        selected_steps = [steps[x] for x in r.step_refs if x in steps]
        if (
            not r.op_refs
            or not r.step_refs
            or m.step_refs != r.step_refs
            or Counter(m.op_refs) != Counter(r.op_refs)
            or m.primitive_kinds != tuple(s.primitive_kind for s in selected_steps)
        ):
            add(S.INVALID, R.REALIZATION_COVERAGE, r.realization_ref)
        # Sequence order is evidence, not an optimization choice.
        if tuple(s.step_ref for s in plan.steps if s.step_ref in r.step_refs) != r.step_refs:
            add(S.INVALID, R.REALIZATION_COVERAGE, r.realization_ref)
        if Counter(m.predicted_effects) != Counter(o.effect for o in selected):
            add(S.INVALID, R.EFFECT_EQUALITY, m.effect_model_ref)
        predictions.extend(m.predicted_effects)
        possible = set(m.possible_subjects)
        if not {e.before.object_id for e in m.predicted_effects} <= possible:
            add(S.INCOMPLETE, R.SCOPE_CONTAINMENT, m.effect_model_ref)
        if not possible <= scope.keys():
            add(S.UNSUPPORTED, R.SCOPE_CONTAINMENT, m.effect_model_ref)
        expected_targets = {o.target_ref for o in selected}
        if {x for s in selected_steps for x in s.target_refs} != expected_targets:
            add(S.INVALID, R.TARGET_BINDING, r.realization_ref)
        if r.produces_fragments or len(r.step_refs) > 1:
            p = r.fragment_evidence
            if p is None:
                add(S.UNSUPPORTED, R.FRAGMENT_REBINDING, r.realization_ref)
            else:
                bound(p.binding, p.profile, p.evidence_ref)
                version(p.contract_version, p.evidence_ref)
                if p.status != EffectModelStatus.VERIFIED or not p.evidence_refs:
                    add(S.UNSUPPORTED, R.FRAGMENT_REBINDING, p.evidence_ref)
                if p.status == EffectModelStatus.STALE:
                    add(S.STALE, R.FRAGMENT_REBINDING, p.evidence_ref)
                if (
                    p.realization_ref != r.realization_ref
                    or p.step_refs != r.step_refs
                    or (p.path == FragmentPath.COMPOUND_PRIMITIVE and len(r.step_refs) != 1)
                ):
                    add(S.INVALID, R.FRAGMENT_REBINDING, p.evidence_ref)
        for s in selected_steps:
            recon = s.reconciliation
            if recon is not None:
                subjects = {p.object_id: p for p in recon.observable_subjects}
                if not possible <= subjects.keys():
                    add(S.INCOMPLETE, R.RECONCILIATION, s.step_ref)
    if Counter(predictions) != approved:
        add(S.INVALID, R.EFFECT_EQUALITY, plan.lowering_ref)
    for s in plan.steps:
        capability(
            caps.get(s.primitive_kind, NativeCapabilityStatus.UNKNOWN), R.CAPABILITY, s.step_ref
        )
        capability(s.post_read, R.POST_READ, s.step_ref)
        if (
            not s.target_refs
            or len(set(s.target_refs)) != len(s.target_refs)
            or not set(s.target_refs) <= targets.keys()
        ):
            add(S.INVALID, R.TARGET_BINDING, s.step_ref)
        recon = s.reconciliation
        if recon is None:
            add(S.INCOMPLETE, R.RECONCILIATION, s.step_ref)
        else:
            bound(recon.binding, recon.profile, recon.reconciliation_ref)
            version(recon.contract_version, recon.reconciliation_ref)
            model_status(recon.status, R.RECONCILIATION, recon.reconciliation_ref)
            if recon.step_ref != s.step_ref:
                add(S.INVALID, R.RECONCILIATION, s.step_ref)
            if not all(
                (
                    recon.applied_state_ref,
                    recon.not_applied_state_ref,
                    recon.read_evidence_refs,
                    recon.evidence_refs,
                )
            ):
                add(S.INCOMPLETE, R.RECONCILIATION, s.step_ref)
            elif recon.applied_state_ref == recon.not_applied_state_ref:
                add(S.INVALID, R.RECONCILIATION, s.step_ref)
            if len({p.object_id for p in recon.observable_subjects}) != len(
                recon.observable_subjects
            ):
                add(S.INVALID, R.RECONCILIATION, s.step_ref)
            for observed in recon.observable_subjects:
                if scope.get(observed.object_id) != observed:
                    add(S.INVALID, R.RECONCILIATION, s.step_ref)
    if manifest.profile != v.current_profile:
        add(S.STALE, R.RUNTIME_PROFILE, "manifest")
    return tuple(dict.fromkeys(findings))


def _status(findings: tuple[ValidationFinding, ...]) -> ExecutionIRValidationStatus:
    S = ExecutionIRValidationStatus
    for status in (S.STALE, S.INVALID, S.UNSUPPORTED, S.INCOMPLETE):
        if any(f.status == status for f in findings):
            return status
    return S.READY_FOR_EXECUTION


@dataclass(frozen=True)
class ExecutionIRValidationResult:
    inputs: ExecutionIRValidationInput
    status: ExecutionIRValidationStatus
    findings: tuple[ValidationFinding, ...]

    def __post_init__(self) -> None:
        _typed(self.inputs, ExecutionIRValidationInput)
        _typed(self.status, ExecutionIRValidationStatus)
        findings = _tuple(self.findings, ValidationFinding)
        if findings != _findings(self.inputs) or self.status != _status(findings):
            raise ValueError("Result must reflect exact validation; cannot forge readiness")
        object.__setattr__(self, "findings", findings)


def validate_execution_ir(inputs: ExecutionIRValidationInput) -> ExecutionIRValidationResult:
    """Validate only supplied artifacts. Never compile, discover, repair or execute."""
    _typed(inputs, ExecutionIRValidationInput)
    findings = _findings(inputs)
    return ExecutionIRValidationResult(inputs, _status(findings), findings)
