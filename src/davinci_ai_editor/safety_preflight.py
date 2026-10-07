"""ADR-026 pure, evidence-bound preflight. No authority, proof production or execution."""

from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from .domain import FrameRange, TimelineObjectId, TrackId
from .expected_diff import DiffCompilationResult, ExpectedDiffStatus, ParticipationStatus
from .native_snapshot import ObservedValue
from .pause_planning import PauseEditProposal
from .temporal_mapping import MappingKind, NativeSnapshotRef

T = TypeVar("T")


def _typed(value: object, kind: type[object]) -> None:
    if not isinstance(value, kind):
        raise TypeError(f"Expected {kind.__name__}")


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Nonempty opaque reference/version required")


def _values(values: tuple[T, ...], kind: type[T]) -> tuple[T, ...]:
    values = tuple(values)
    for value in values:
        _typed(value, kind)
    if len(set(values)) != len(values):
        raise ValueError("Duplicate evidence value")
    return tuple(sorted(values, key=repr))


def _refs(values: tuple[str, ...]) -> tuple[str, ...]:
    values = _values(values, str)
    for value in values:
        _text(value)
    return values


def _unique(values: tuple[object, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError("Duplicate identity or evidence subject")


class SafetyCheckKind(str, Enum):
    BASE_FRESHNESS = "BASE_FRESHNESS"
    EXPECTED_DIFF_INTEGRITY = "EXPECTED_DIFF_INTEGRITY"
    PROTECTION_CONTEXT = "PROTECTION_CONTEXT"
    PROTECTED_RANGE = "PROTECTED_RANGE"
    TRACK_LOCK = "TRACK_LOCK"
    RELATIONSHIP_INTEGRITY = "RELATIONSHIP_INTEGRITY"
    TEMPORAL_DEPENDENCY_COVERAGE = "TEMPORAL_DEPENDENCY_COVERAGE"
    RETIME_SUPPORT = "RETIME_SUPPORT"
    MEDIA_IDENTITY_PRESERVATION = "MEDIA_IDENTITY_PRESERVATION"
    SOURCE_RANGE_PRESERVATION = "SOURCE_RANGE_PRESERVATION"
    DURATION_PRESERVATION = "DURATION_PRESERVATION"
    TRACK_MEMBERSHIP_PRESERVATION = "TRACK_MEMBERSHIP_PRESERVATION"
    TOPOLOGY_PRESERVATION = "TOPOLOGY_PRESERVATION"
    TRANSITION_INTEGRITY = "TRANSITION_INTEGRITY"
    EFFECT_EDITABILITY = "EFFECT_EDITABILITY"
    KEYFRAME_EDITABILITY = "KEYFRAME_EDITABILITY"
    PRESERVATION_SCOPE = "PRESERVATION_SCOPE"


class PreflightStatus(str, Enum):
    STALE = "STALE"
    UNSUPPORTED = "UNSUPPORTED"
    INCOMPLETE = "INCOMPLETE"
    EVALUATED = "EVALUATED"


class SafetyVerdict(str, Enum):
    REJECT = "REJECT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    PASS = "PASS"


class SafetyCheckOutcome(str, Enum):
    REJECT = "REJECT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    PASS = "PASS"


class SafetyReason(str, Enum):
    CHECK_PASSED = "CHECK_PASSED"
    STALE_BASE = "STALE_BASE"
    MISBOUND_EVIDENCE = "MISBOUND_EVIDENCE"
    UNSUPPORTED_CONTRACT = "UNSUPPORTED_CONTRACT"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    EXPECTED_DIFF_NOT_READY = "EXPECTED_DIFF_NOT_READY"
    EXPECTED_DIFF_MISMATCH = "EXPECTED_DIFF_MISMATCH"
    PROTECTION_INCOMPLETE = "PROTECTION_INCOMPLETE"
    PROTECTED_PRIMARY = "PROTECTED_PRIMARY"
    PROTECTED_DISPLACEMENT = "PROTECTED_DISPLACEMENT"
    LOCK_UNKNOWN = "LOCK_UNKNOWN"
    TRACK_LOCKED = "TRACK_LOCKED"
    ASSESSMENT_UNRESOLVED = "ASSESSMENT_UNRESOLVED"
    RETIME_UNKNOWN = "RETIME_UNKNOWN"
    RETIME_UNSUPPORTED = "RETIME_UNSUPPORTED"
    FORWARD_NOT_EXACT = "FORWARD_NOT_EXACT"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    MEDIA_CHANGED = "MEDIA_CHANGED"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    DURATION_CHANGED = "DURATION_CHANGED"
    TRACK_CHANGED = "TRACK_CHANGED"
    TOPOLOGY_UNSUPPORTED = "TOPOLOGY_UNSUPPORTED"
    STRUCTURE_UNKNOWN = "STRUCTURE_UNKNOWN"
    PRESERVATION_UNPROVEN = "PRESERVATION_UNPROVEN"
    PROOF_INVALID = "PROOF_INVALID"
    EXPLICIT_VIOLATION = "EXPLICIT_VIOLATION"
    SCOPE_INCOMPLETE = "SCOPE_INCOMPLETE"


@dataclass(frozen=True)
class SafetyRequirementProfile:
    profile_id: str
    profile_version: str
    required_checks: tuple[SafetyCheckKind, ...]

    def __post_init__(self) -> None:
        _text(self.profile_id)
        _text(self.profile_version)
        checks = _values(self.required_checks, SafetyCheckKind)
        if set(checks) != set(SafetyCheckKind):
            raise ValueError("Pause v1 requires exactly all 17 checks")
        object.__setattr__(self, "required_checks", tuple(SafetyCheckKind))


PAUSE_DESTRUCTIVE_PREFLIGHT_V1 = SafetyRequirementProfile(
    "PAUSE_DESTRUCTIVE_PREFLIGHT_V1", "v1", tuple(SafetyCheckKind)
)


@dataclass(frozen=True)
class SafetySubject:
    object_id: TimelineObjectId
    frame_range: FrameRange

    def __post_init__(self) -> None:
        _typed(self.object_id, TimelineObjectId)
        _typed(self.frame_range, FrameRange)


@dataclass(frozen=True)
class ProtectedRangeRecord:
    record_ref: str
    track_id: TrackId
    frame_range: FrameRange | None = None
    object_id: TimelineObjectId | None = None
    policy: str = "HARD_LOCK"

    def __post_init__(self) -> None:
        _text(self.record_ref)
        _text(self.track_id)
        if self.policy != "HARD_LOCK":
            raise ValueError("Only HARD_LOCK is supported; no override")
        if self.frame_range is None and self.object_id is None:
            raise ValueError("Protection requires an explicit object or range")
        if self.frame_range is not None:
            _typed(self.frame_range, FrameRange)
        if self.object_id is not None:
            _typed(self.object_id, TimelineObjectId)
            if self.object_id.track_id != self.track_id:
                raise ValueError("Protected object must belong to the bound track")


@dataclass(frozen=True)
class ProtectionContext:
    context_ref: str
    snapshot: NativeSnapshotRef
    complete: bool
    records: tuple[ProtectedRangeRecord, ...]
    context_version: str

    def __post_init__(self) -> None:
        _text(self.context_ref)
        _text(self.context_version)
        _typed(self.snapshot, NativeSnapshotRef)
        if type(self.complete) is not bool:
            raise TypeError("Explicit protection completeness required")
        records = _values(self.records, ProtectedRangeRecord)
        _unique(tuple(r.record_ref for r in records))
        object.__setattr__(self, "records", records)


class PreservationProofKind(str, Enum):
    TRANSITION = "TRANSITION"
    EFFECT = "EFFECT"
    KEYFRAME = "KEYFRAME"


class ProofOutcome(str, Enum):
    PRESERVATION_PROVEN = "PRESERVATION_PROVEN"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class PreservationProof:
    proof_ref: str
    proof_kind: PreservationProofKind
    snapshot: NativeSnapshotRef
    expected_diff_ref: str
    subject: SafetySubject
    proof_contract_version: str
    outcome: ProofOutcome
    producer_name: str
    producer_version: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for value in (
            self.proof_ref,
            self.expected_diff_ref,
            self.proof_contract_version,
            self.producer_name,
            self.producer_version,
        ):
            _text(value)
        _typed(self.proof_kind, PreservationProofKind)
        _typed(self.snapshot, NativeSnapshotRef)
        _typed(self.subject, SafetySubject)
        _typed(self.outcome, ProofOutcome)
        refs = _refs(self.evidence_refs)
        if not refs:
            raise ValueError("Proof must retain supporting evidence references")
        object.__setattr__(self, "evidence_refs", refs)


class StructureState(str, Enum):
    KNOWN_ABSENT = "KNOWN_ABSENT"
    UNKNOWN = "UNKNOWN"
    KNOWN_PRESENT_WITHOUT_PROOF = "KNOWN_PRESENT_WITHOUT_PROOF"
    PRESERVATION_PROVEN = "PRESERVATION_PROVEN"
    EXPLICIT_VIOLATION = "EXPLICIT_VIOLATION"


@dataclass(frozen=True)
class StructureObservation:
    state: StructureState = StructureState.UNKNOWN
    proof_ref: str | None = None

    def __post_init__(self) -> None:
        _typed(self.state, StructureState)
        if self.proof_ref is not None:
            _text(self.proof_ref)
            if self.state not in (
                StructureState.KNOWN_PRESENT_WITHOUT_PROOF,
                StructureState.PRESERVATION_PROVEN,
            ):
                raise ValueError("Only known presence may reference preservation proof")


@dataclass(frozen=True)
class ObjectSafetyEvidence:
    subject: SafetySubject
    retime: MappingKind = MappingKind.UNKNOWN
    exact_forward: ObservedValue = ObservedValue.UNKNOWN
    transition: StructureObservation = StructureObservation()
    effect: StructureObservation = StructureObservation()
    keyframe: StructureObservation = StructureObservation()

    def __post_init__(self) -> None:
        _typed(self.subject, SafetySubject)
        _typed(self.retime, MappingKind)
        _typed(self.exact_forward, ObservedValue)
        for observation in (self.transition, self.effect, self.keyframe):
            _typed(observation, StructureObservation)


@dataclass(frozen=True)
class TrackLockEvidence:
    track_id: TrackId
    locked: ObservedValue

    def __post_init__(self) -> None:
        _text(self.track_id)
        _typed(self.locked, ObservedValue)


class AssessmentState(str, Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CurrentSafetyEvidence:
    evidence_ref: str
    expected_diff_ref: str
    snapshot: NativeSnapshotRef
    track_locks: tuple[TrackLockEvidence, ...] = ()
    objects: tuple[ObjectSafetyEvidence, ...] = ()
    relationship_status: AssessmentState = AssessmentState.UNKNOWN
    relationship_assessment_ref: str | None = None
    dependency_status: AssessmentState = AssessmentState.UNKNOWN
    dependency_assessment_ref: str | None = None
    known_impacted_ids: tuple[TimelineObjectId, ...] = ()
    known_dependent_ids: tuple[TimelineObjectId, ...] = ()

    def __post_init__(self) -> None:
        _text(self.evidence_ref)
        _text(self.expected_diff_ref)
        _typed(self.snapshot, NativeSnapshotRef)
        for state in (self.relationship_status, self.dependency_status):
            _typed(state, AssessmentState)
        for ref in (self.relationship_assessment_ref, self.dependency_assessment_ref):
            if ref is not None:
                _text(ref)
        locks, objects = (
            _values(self.track_locks, TrackLockEvidence),
            _values(self.objects, ObjectSafetyEvidence),
        )
        _unique(tuple(v.track_id for v in locks))
        _unique(tuple(v.subject for v in objects))
        object.__setattr__(self, "track_locks", locks)
        object.__setattr__(self, "objects", objects)
        for field in ("known_impacted_ids", "known_dependent_ids"):
            object.__setattr__(self, field, _values(getattr(self, field), TimelineObjectId))


@dataclass(frozen=True)
class SafetyPreflightInput:
    compilation: DiffCompilationResult
    proposal: PauseEditProposal
    current_snapshot: NativeSnapshotRef
    protection: ProtectionContext | None = None
    evidence: CurrentSafetyEvidence | None = None
    profile: SafetyRequirementProfile = PAUSE_DESTRUCTIVE_PREFLIGHT_V1
    proofs: tuple[PreservationProof, ...] = ()
    safety_contract_version: str = "v1"

    def __post_init__(self) -> None:
        _typed(self.compilation, DiffCompilationResult)
        _typed(self.proposal, PauseEditProposal)
        _typed(self.current_snapshot, NativeSnapshotRef)
        _typed(self.profile, SafetyRequirementProfile)
        if self.protection is not None:
            _typed(self.protection, ProtectionContext)
        if self.evidence is not None:
            _typed(self.evidence, CurrentSafetyEvidence)
        proofs = _values(self.proofs, PreservationProof)
        _unique(tuple(p.proof_ref for p in proofs))
        object.__setattr__(self, "proofs", proofs)
        _text(self.safety_contract_version)


@dataclass(frozen=True)
class SafetyFinding:
    status: PreflightStatus
    outcome: SafetyCheckOutcome | None
    reason: SafetyReason
    subjects: tuple[SafetySubject, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _typed(self.status, PreflightStatus)
        _typed(self.reason, SafetyReason)
        if self.outcome is not None:
            _typed(self.outcome, SafetyCheckOutcome)
        if (self.status == PreflightStatus.EVALUATED) != (self.outcome is not None):
            raise ValueError("Only evaluated findings carry a check outcome")
        object.__setattr__(self, "subjects", _values(self.subjects, SafetySubject))
        object.__setattr__(self, "evidence_refs", _refs(self.evidence_refs))


def _aggregate(
    findings: tuple[SafetyFinding, ...],
) -> tuple[PreflightStatus, SafetyCheckOutcome | None]:
    if not findings:
        raise ValueError("Empty findings cannot pass")
    for status in (PreflightStatus.STALE, PreflightStatus.UNSUPPORTED, PreflightStatus.INCOMPLETE):
        if any(f.status == status for f in findings):
            return status, None
    for outcome in (
        SafetyCheckOutcome.REJECT,
        SafetyCheckOutcome.REVIEW_REQUIRED,
        SafetyCheckOutcome.PASS,
    ):
        if any(f.outcome == outcome for f in findings):
            return PreflightStatus.EVALUATED, outcome
    raise ValueError("Evaluated findings must have outcomes")


@dataclass(frozen=True)
class SafetyCheckResult:
    kind: SafetyCheckKind
    findings: tuple[SafetyFinding, ...]

    def __post_init__(self) -> None:
        _typed(self.kind, SafetyCheckKind)
        findings = tuple(self.findings)
        for f in findings:
            _typed(f, SafetyFinding)
        if not findings:
            raise ValueError("Every check must report evidence or its absence")
        object.__setattr__(self, "findings", tuple(sorted(set(findings), key=repr)))

    @property
    def status(self) -> PreflightStatus:
        return _aggregate(self.findings)[0]

    @property
    def outcome(self) -> SafetyCheckOutcome | None:
        return _aggregate(self.findings)[1]

    @property
    def invariant_refs(self) -> tuple[str, ...]:
        K = SafetyCheckKind
        return {
            K.BASE_FRESHNESS: ("INV-012",),
            K.EXPECTED_DIFF_INTEGRITY: ("INV-016",),
            K.PROTECTION_CONTEXT: ("INV-003", "INV-017"),
            K.PROTECTED_RANGE: ("INV-003", "INV-017"),
            K.TRACK_LOCK: ("INV-017",),
            K.RELATIONSHIP_INTEGRITY: ("INV-004", "INV-006"),
            K.TEMPORAL_DEPENDENCY_COVERAGE: ("INV-018",),
            K.RETIME_SUPPORT: ("INV-007",),
            K.MEDIA_IDENTITY_PRESERVATION: ("INV-002", "INV-011"),
            K.SOURCE_RANGE_PRESERVATION: ("INV-002", "INV-011"),
            K.DURATION_PRESERVATION: ("INV-002",),
            K.TRACK_MEMBERSHIP_PRESERVATION: ("INV-019",),
            K.TOPOLOGY_PRESERVATION: ("INV-019",),
            K.TRANSITION_INTEGRITY: ("INV-009",),
            K.EFFECT_EDITABILITY: ("INV-010",),
            K.KEYFRAME_EDITABILITY: ("INV-010",),
            K.PRESERVATION_SCOPE: ("INV-002", "INV-016"),
        }[self.kind]


@dataclass(frozen=True)
class SafetyPreflightResult:
    inputs: SafetyPreflightInput
    checks: tuple[SafetyCheckResult, ...]
    status: PreflightStatus
    verdict: SafetyVerdict | None

    def __post_init__(self) -> None:
        _typed(self.inputs, SafetyPreflightInput)
        _typed(self.status, PreflightStatus)
        if self.verdict is not None:
            _typed(self.verdict, SafetyVerdict)
        checks = _values(self.checks, SafetyCheckResult)
        if len(checks) != 17 or {c.kind for c in checks} != set(
            self.inputs.profile.required_checks
        ):
            raise ValueError("Result requires exactly all 17 distinct mandatory checks")
        status, outcome = _aggregate(tuple(f for c in checks for f in c.findings))
        verdict = None if outcome is None else SafetyVerdict(outcome.value)
        if self.status != status or self.verdict != verdict:
            raise ValueError("Status/verdict must match all findings and mandatory precedence")
        object.__setattr__(self, "checks", checks)


def _overlaps(
    record: ProtectedRangeRecord, subject: SafetySubject, after: FrameRange | None = None
) -> bool:
    return (
        record.track_id == subject.object_id.track_id
        and (record.object_id is None or record.object_id == subject.object_id)
        and (
            record.frame_range is None
            or record.frame_range.overlaps(subject.frame_range)
            or (after is not None and record.frame_range.overlaps(after))
        )
    )


def preflight(inputs: SafetyPreflightInput) -> SafetyPreflightResult:
    """Evaluate all available facts; never synthesize missing safety or repair a plan."""
    _typed(inputs, SafetyPreflightInput)
    K, S, O, R = SafetyCheckKind, PreflightStatus, SafetyCheckOutcome, SafetyReason
    findings: dict[SafetyCheckKind, list[SafetyFinding]] = {k: [] for k in K}

    def emit(
        kind: SafetyCheckKind,
        status: PreflightStatus,
        outcome: SafetyCheckOutcome | None,
        reason: SafetyReason,
        subjects: tuple[SafetySubject, ...] = (),
        refs: tuple[str, ...] = (),
    ) -> None:
        findings[kind].append(
            SafetyFinding(status, outcome, reason, subjects, tuple(sorted(set(refs))))
        )

    def passed(
        kind: SafetyCheckKind, subjects: tuple[SafetySubject, ...] = (), refs: tuple[str, ...] = ()
    ) -> None:
        emit(kind, S.EVALUATED, O.PASS, R.CHECK_PASSED, subjects, refs)

    c, p, current = inputs.compilation, inputs.proposal, inputs.current_snapshot
    diff, evidence, protection = c.expected_diff, inputs.evidence, inputs.protection
    diff_ref = c.inputs.expected_diff_ref
    refs = (diff_ref, p.proposal_ref)
    snapshots = [
        p.binding.snapshot_ref,
        c.inputs.current_snapshot,
        c.inputs.proposal.binding.snapshot_ref,
        c.inputs.scope.binding.planning_binding.snapshot_ref,
        c.inputs.participation.binding.planning_binding.snapshot_ref,
    ]
    if diff is not None:
        snapshots.extend(
            (
                diff.base_snapshot,
                diff.inputs.current_snapshot,
                diff.inputs.scope.binding.planning_binding.snapshot_ref,
                diff.inputs.participation.binding.planning_binding.snapshot_ref,
            )
        )
    if protection is not None:
        snapshots.append(protection.snapshot)
    if evidence is not None:
        snapshots.append(evidence.snapshot)
    snapshots.extend(proof.snapshot for proof in inputs.proofs)
    if any(s != current for s in snapshots) or c.status == ExpectedDiffStatus.STALE:
        emit(K.BASE_FRESHNESS, S.STALE, None, R.STALE_BASE, refs=refs)
    else:
        passed(K.BASE_FRESHNESS, refs=refs)
    if evidence is not None and evidence.expected_diff_ref != diff_ref:
        emit(
            K.BASE_FRESHNESS, S.INCOMPLETE, None, R.MISBOUND_EVIDENCE, refs=(evidence.evidence_ref,)
        )
    if inputs.profile != PAUSE_DESTRUCTIVE_PREFLIGHT_V1 or inputs.safety_contract_version != "v1":
        emit(K.EXPECTED_DIFF_INTEGRITY, S.UNSUPPORTED, None, R.UNSUPPORTED_CONTRACT, refs=refs)
    ready = c.status == ExpectedDiffStatus.READY_FOR_PREFLIGHT and diff is not None
    if not ready:
        status = {
            ExpectedDiffStatus.STALE: S.STALE,
            ExpectedDiffStatus.UNSUPPORTED: S.UNSUPPORTED,
        }.get(c.status, S.INCOMPLETE)
        emit(K.EXPECTED_DIFF_INTEGRITY, status, None, R.EXPECTED_DIFF_NOT_READY, refs=refs)
    if diff is not None:
        geometry = p.geometry
        valid = (
            c.inputs.proposal == p
            and diff.inputs == c.inputs
            and geometry.binding == p.binding
            and geometry.removed_ranges == (p.affected_primary_range,)
            and p.binding.original_pause_range.contains(p.affected_primary_range)
            and geometry.retained_duration_frames
            == p.binding.original_pause_range.duration - p.affected_primary_range.duration
            and len(diff.primary_changes) == 1
        )
        for primary in diff.primary_changes:
            valid &= (
                primary.proposal_ref == p.proposal_ref
                and primary.geometry_ref == geometry.geometry_ref
                and primary.before.object_id == p.binding.object_id
                and primary.removed_timeline_range == p.affected_primary_range
                and primary.before.timeline_range.contains(p.binding.original_pause_range)
            )
        for bound in (diff.inputs.scope.binding, diff.inputs.participation.binding):
            valid &= (
                bound.proposal_ref == p.proposal_ref
                and bound.planning_binding == p.binding
                and bound.geometry_ref == p.geometry.geometry_ref
                and bound.primary_range == p.affected_primary_range
            )
        participants = {v.before.object_id: v for v in diff.inputs.participation.participants}
        move_ids = [m.before.object_id for m in diff.displacements]
        valid &= len(set(move_ids)) == len(move_ids) and set(move_ids) == set(participants)
        valid &= diff.inputs.participation.status == ParticipationStatus.RESOLVED
        valid &= diff.inputs.participation.uniform_consequence_verified
        for m in diff.displacements:
            participant = participants.get(m.before.object_id)
            valid &= (
                participant is not None
                and participant.before == m.before
                and participant.delta_frames == m.delta_frames
                and participant.after_track_id == m.after.track_id
            )
            valid &= (
                m.before.object_id == m.after.object_id
                and m.before.retime == m.after.retime
                and m.before.object_id != p.binding.object_id
                and m.before.timeline_range.start >= p.affected_primary_range.end
                and m.delta_frames == -p.affected_primary_range.duration
                and m.after.timeline_range.start - m.before.timeline_range.start == m.delta_frames
                and m.after.timeline_range.end - m.before.timeline_range.end == m.delta_frames
                and any(primary.change_id == m.source_change_id for primary in diff.primary_changes)
            )
        if not valid:
            emit(
                K.EXPECTED_DIFF_INTEGRITY,
                S.EVALUATED,
                O.REJECT,
                R.EXPECTED_DIFF_MISMATCH,
                refs=refs,
            )
        elif ready:
            passed(K.EXPECTED_DIFF_INTEGRITY, refs=refs)
        if (
            p.planning_contract_version != "v1"
            or geometry.geometry_contract_version != "v1"
            or diff.inputs.provenance.contract_version != "v1"
        ):
            emit(K.EXPECTED_DIFF_INTEGRITY, S.UNSUPPORTED, None, R.UNSUPPORTED_CONTRACT, refs=refs)

    subjects = {SafetySubject(p.binding.object_id, p.affected_primary_range)}
    if diff is not None:
        subjects.update(
            SafetySubject(m.before.object_id, m.before.timeline_range) for m in diff.displacements
        )
        subjects.update(
            SafetySubject(v.before.object_id, v.removed_timeline_range)
            for v in diff.primary_changes
        )
    subject_tuple = tuple(sorted(subjects, key=repr))
    if protection is None or not protection.complete:
        for kind in (K.PROTECTION_CONTEXT, K.PROTECTED_RANGE):
            emit(
                kind,
                S.INCOMPLETE,
                None,
                R.PROTECTION_INCOMPLETE,
                refs=() if protection is None else (protection.context_ref,),
            )
    else:
        passed(K.PROTECTION_CONTEXT, refs=(protection.context_ref,))
    if protection is not None:
        for record in protection.records:
            primary_subjects = {SafetySubject(p.binding.object_id, p.affected_primary_range)}
            if diff is not None:
                primary_subjects.update(
                    SafetySubject(v.before.object_id, v.removed_timeline_range)
                    for v in diff.primary_changes
                )
            for primary_subject in sorted(primary_subjects, key=repr):
                if _overlaps(record, primary_subject):
                    emit(
                        K.PROTECTED_RANGE,
                        S.EVALUATED,
                        O.REJECT,
                        R.PROTECTED_PRIMARY,
                        (primary_subject,),
                        (protection.context_ref, record.record_ref),
                    )
            if diff is not None:
                for m in diff.displacements:
                    subject = SafetySubject(m.before.object_id, m.before.timeline_range)
                    if m.before.timeline_range != m.after.timeline_range and _overlaps(
                        record, subject, m.after.timeline_range
                    ):
                        emit(
                            K.PROTECTED_RANGE,
                            S.EVALUATED,
                            O.REJECT,
                            R.PROTECTED_DISPLACEMENT,
                            (subject,),
                            (protection.context_ref, record.record_ref),
                        )
        if not findings[K.PROTECTED_RANGE]:
            passed(K.PROTECTED_RANGE, subject_tuple, (protection.context_ref,))

    evrefs = () if evidence is None else (evidence.evidence_ref,)
    locks = {} if evidence is None else {v.track_id: v.locked for v in evidence.track_locks}
    for track in sorted({s.object_id.track_id for s in subjects}):
        track_subjects = tuple(s for s in subject_tuple if s.object_id.track_id == track)
        state = locks.get(track, ObservedValue.UNKNOWN)
        if state == ObservedValue.UNKNOWN:
            emit(K.TRACK_LOCK, S.INCOMPLETE, None, R.LOCK_UNKNOWN, track_subjects, evrefs)
        elif state == ObservedValue.TRUE:
            emit(K.TRACK_LOCK, S.EVALUATED, O.REJECT, R.TRACK_LOCKED, track_subjects, evrefs)
        else:
            passed(K.TRACK_LOCK, track_subjects, evrefs)
    for kind, assessment_state, assessment_ref in (
        (
            K.RELATIONSHIP_INTEGRITY,
            AssessmentState.UNKNOWN if evidence is None else evidence.relationship_status,
            None if evidence is None else evidence.relationship_assessment_ref,
        ),
        (
            K.TEMPORAL_DEPENDENCY_COVERAGE,
            AssessmentState.UNKNOWN if evidence is None else evidence.dependency_status,
            None if evidence is None else evidence.dependency_assessment_ref,
        ),
    ):
        assessment_refs = evrefs if assessment_ref is None else (*evrefs, assessment_ref)
        if assessment_state != AssessmentState.RESOLVED or assessment_ref is None:
            emit(kind, S.INCOMPLETE, None, R.ASSESSMENT_UNRESOLVED, refs=assessment_refs)
        else:
            passed(kind, refs=assessment_refs)

    observations = {} if evidence is None else {v.subject: v for v in evidence.objects}
    proofs = {v.proof_ref: v for v in inputs.proofs}
    structures = (
        (K.TRANSITION_INTEGRITY, "transition", PreservationProofKind.TRANSITION),
        (K.EFFECT_EDITABILITY, "effect", PreservationProofKind.EFFECT),
        (K.KEYFRAME_EDITABILITY, "keyframe", PreservationProofKind.KEYFRAME),
    )
    for proof in inputs.proofs:
        kind = {
            PreservationProofKind.TRANSITION: K.TRANSITION_INTEGRITY,
            PreservationProofKind.EFFECT: K.EFFECT_EDITABILITY,
            PreservationProofKind.KEYFRAME: K.KEYFRAME_EDITABILITY,
        }[proof.proof_kind]
        if (
            proof.expected_diff_ref != diff_ref
            or proof.subject not in subjects
            or proof.snapshot != current
            or proof.proof_contract_version != "v1"
            or proof.outcome != ProofOutcome.PRESERVATION_PROVEN
        ):
            emit(
                kind,
                S.EVALUATED,
                O.REVIEW_REQUIRED,
                R.PROOF_INVALID,
                (proof.subject,),
                (proof.proof_ref, *proof.evidence_refs),
            )
    planned_retimes = (
        {}
        if diff is None
        else {
            SafetySubject(v.before.object_id, v.removed_timeline_range): v.before.retime
            for v in diff.primary_changes
        }
    )
    if diff is not None:
        planned_retimes.update(
            {
                SafetySubject(m.before.object_id, m.before.timeline_range): m.before.retime
                for m in diff.displacements
            }
        )
    for subject in subject_tuple:
        observation = observations.get(subject)
        retime = MappingKind.UNKNOWN if observation is None else observation.retime
        if retime == MappingKind.UNKNOWN:
            emit(K.RETIME_SUPPORT, S.INCOMPLETE, None, R.RETIME_UNKNOWN, (subject,), evrefs)
        elif retime not in (MappingKind.IDENTITY_1X, MappingKind.AFFINE_FORWARD):
            emit(K.RETIME_SUPPORT, S.UNSUPPORTED, None, R.RETIME_UNSUPPORTED, (subject,), evrefs)
        elif observation is None or observation.exact_forward != ObservedValue.TRUE:
            emit(K.RETIME_SUPPORT, S.INCOMPLETE, None, R.FORWARD_NOT_EXACT, (subject,), evrefs)
        else:
            passed(K.RETIME_SUPPORT, (subject,), evrefs)
        planned_retime = planned_retimes.get(subject, MappingKind.UNKNOWN)
        if planned_retime == MappingKind.UNKNOWN:
            emit(K.RETIME_SUPPORT, S.INCOMPLETE, None, R.RETIME_UNKNOWN, (subject,), refs)
        elif planned_retime not in (MappingKind.IDENTITY_1X, MappingKind.AFFINE_FORWARD):
            emit(K.RETIME_SUPPORT, S.UNSUPPORTED, None, R.RETIME_UNSUPPORTED, (subject,), refs)
        elif (
            retime in (MappingKind.IDENTITY_1X, MappingKind.AFFINE_FORWARD)
            and retime != planned_retime
        ):
            emit(K.RETIME_SUPPORT, S.INCOMPLETE, None, R.EVIDENCE_CONFLICT, (subject,), evrefs)
        for kind, field, proof_kind in structures:
            obs = StructureObservation() if observation is None else getattr(observation, field)
            if obs.state == StructureState.UNKNOWN:
                emit(kind, S.INCOMPLETE, None, R.STRUCTURE_UNKNOWN, (subject,), evrefs)
            elif obs.state == StructureState.KNOWN_ABSENT:
                passed(kind, (subject,), evrefs)
            elif obs.state == StructureState.EXPLICIT_VIOLATION:
                emit(kind, S.EVALUATED, O.REJECT, R.EXPLICIT_VIOLATION, (subject,), evrefs)
            else:
                selected_proof = None if obs.proof_ref is None else proofs.get(obs.proof_ref)
                valid_selected_proof = (
                    selected_proof is not None
                    and selected_proof.proof_kind == proof_kind
                    and selected_proof.subject == subject
                    and selected_proof.expected_diff_ref == diff_ref
                    and selected_proof.snapshot == current
                    and selected_proof.proof_contract_version == "v1"
                    and selected_proof.outcome == ProofOutcome.PRESERVATION_PROVEN
                )
                proof_refs = (
                    evrefs
                    if selected_proof is None
                    else (*evrefs, selected_proof.proof_ref, *selected_proof.evidence_refs)
                )
                if valid_selected_proof:
                    passed(kind, (subject,), proof_refs)
                else:
                    emit(
                        kind,
                        S.EVALUATED,
                        O.REVIEW_REQUIRED,
                        R.PRESERVATION_UNPROVEN if selected_proof is None else R.PROOF_INVALID,
                        (subject,),
                        proof_refs,
                    )

    preservation = (
        (K.MEDIA_IDENTITY_PRESERVATION, "media_id", R.MEDIA_CHANGED),
        (K.SOURCE_RANGE_PRESERVATION, "source_range", R.SOURCE_CHANGED),
        (K.DURATION_PRESERVATION, "duration", R.DURATION_CHANGED),
        (K.TRACK_MEMBERSHIP_PRESERVATION, "track_id", R.TRACK_CHANGED),
    )
    if diff is None:
        for kind, _, _ in preservation:
            emit(kind, S.INCOMPLETE, None, R.EXPECTED_DIFF_NOT_READY, refs=refs)
        emit(K.TOPOLOGY_PRESERVATION, S.INCOMPLETE, None, R.EXPECTED_DIFF_NOT_READY, refs=refs)
        emit(K.PRESERVATION_SCOPE, S.INCOMPLETE, None, R.EXPECTED_DIFF_NOT_READY, refs=refs)
    else:
        for kind, field, reason in preservation:
            for m in diff.displacements:
                before = (
                    m.before.timeline_range.duration
                    if field == "duration"
                    else getattr(m.before, field)
                )
                after = (
                    m.after.timeline_range.duration
                    if field == "duration"
                    else getattr(m.after, field)
                )
                subject = SafetySubject(m.before.object_id, m.before.timeline_range)
                if before != after:
                    emit(kind, S.EVALUATED, O.REJECT, reason, (subject,), refs)
                else:
                    passed(kind, (subject,), refs)
            if not diff.displacements:
                passed(kind, refs=refs)
        if diff.expected_topology_changes:
            emit(K.TOPOLOGY_PRESERVATION, S.UNSUPPORTED, None, R.TOPOLOGY_UNSUPPORTED, refs=refs)
        else:
            passed(K.TOPOLOGY_PRESERVATION, refs=refs)
        scope = {v.object_id: v for v in diff.inputs.scope.objects}
        affected = {s.object_id for s in subjects} | {m.after.object_id for m in diff.displacements}
        affected.update(diff.inputs.participation.known_impacted_ids)
        affected.update(diff.inputs.participation.protected_risk_ids)
        if evidence is not None:
            affected.update(evidence.known_impacted_ids)
            affected.update(evidence.known_dependent_ids)
        if not affected <= scope.keys():
            emit(K.PRESERVATION_SCOPE, S.INCOMPLETE, None, R.SCOPE_INCOMPLETE, subject_tuple, refs)
        else:
            passed(K.PRESERVATION_SCOPE, subject_tuple, refs)
        for placement in [v.before for v in diff.primary_changes] + [
            m.before for m in diff.displacements
        ]:
            if placement.object_id in scope and scope[placement.object_id] != placement:
                emit(
                    K.EXPECTED_DIFF_INTEGRITY,
                    S.EVALUATED,
                    O.REJECT,
                    R.EXPECTED_DIFF_MISMATCH,
                    (SafetySubject(placement.object_id, placement.timeline_range),),
                    refs,
                )
    checks = tuple(
        SafetyCheckResult(
            k, tuple(values) if values else (SafetyFinding(S.INCOMPLETE, None, R.MISSING_EVIDENCE),)
        )
        for k, values in findings.items()
    )
    status, outcome = _aggregate(tuple(f for c in checks for f in c.findings))
    return SafetyPreflightResult(
        inputs, checks, status, None if outcome is None else SafetyVerdict(outcome.value)
    )
