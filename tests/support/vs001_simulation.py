"""Test-only VS-001 interpreter and synthetic evidence; never native capability proof."""

from collections import Counter
from dataclasses import dataclass, field, replace
from itertools import pairwise
from typing import Literal

from davinci_ai_editor import authority as a
from davinci_ai_editor import execution_ir as ir
from davinci_ai_editor import expected_diff as d
from davinci_ai_editor import safety_preflight as s
from davinci_ai_editor import transaction as t
from davinci_ai_editor.domain import FrameRange, TimelineObjectId, TrackType
from davinci_ai_editor.native_snapshot import ObservedValue as V
from davinci_ai_editor.temporal_mapping import MappingKind, NativeSnapshotRef


@dataclass(frozen=True)
class SimulationState:
    snapshot: NativeSnapshotRef
    objects: tuple[d.PlacementState, ...]
    tracks: tuple[tuple[str, TrackType], ...]

    def __post_init__(self) -> None:
        objects, tracks = tuple(self.objects), tuple(self.tracks)
        if not isinstance(self.snapshot, NativeSnapshotRef):
            raise TypeError("Typed snapshot required")
        if any(not isinstance(o, d.PlacementState) for o in objects):
            raise TypeError("Typed placements required")
        if len({o.object_id for o in objects}) != len(objects):
            raise ValueError("Ambiguous duplicate object IDs")
        if len({track for track, _ in tracks}) != len(tracks):
            raise ValueError("Duplicate tracks")
        if any(not name or not isinstance(kind, TrackType) for name, kind in tracks):
            raise ValueError("Explicit typed track inventory required")
        if any(o.track_id not in dict(tracks) or o.object_id.track_id != o.track_id for o in objects):
            raise ValueError("Object/track binding mismatch")
        # Raw post state can retain overlap/retime damage for diagnosis; admission is stricter.
        object.__setattr__(self, "objects", tuple(sorted(objects, key=lambda o: repr(o.object_id))))
        object.__setattr__(self, "tracks", tuple(sorted(tracks)))


@dataclass(frozen=True)
class Request:
    base: SimulationState
    diff: d.ExpectedDiff
    safety: s.SafetyPreflightResult
    safety_ref: str
    logical: ir.ExecutionIR
    candidate: a.CandidateWorkState
    approval_ref: str


@dataclass(frozen=True)
class OperationRecord:
    op_ref: str
    kind: ir.ExecutionOpKind
    target_ref: str
    object_id: TimelineObjectId
    attempted: bool = False
    result: Literal["NOT_ATTEMPTED", "EVALUATED", "ERROR"] = "NOT_ATTEMPTED"
    before: d.PlacementState | None = None
    after: d.PlacementState | None = None


@dataclass(frozen=True)
class Receipt:
    receipt_ref: str
    binding: t.ArtifactBinding
    ir_ref: str
    authorization_ref: str
    base: SimulationState
    post_snapshot: NativeSnapshotRef | None
    operations: tuple[OperationRecord, ...]
    outcome: str
    published: bool
    failure_stage: str | None
    diagnostics: tuple[str, ...]
    evidence_domain: Literal["SIMULATION"] = field(default="SIMULATION", init=False)


@dataclass(frozen=True)
class Run:
    state: SimulationState
    receipt: Receipt


@dataclass(frozen=True)
class Correlations:
    expected_diff_ref: str
    primary_id: TimelineObjectId
    primary_op_ref: str
    change_id: str
    proposal_ref: str
    geometry_ref: str
    scope_ids: tuple[TimelineObjectId, ...]
    operation_refs: tuple[tuple[str, ir.ExecutionOpKind, str, TimelineObjectId], ...]


@dataclass(frozen=True)
class Evidence:
    actual: d.ActualDiff | None
    complete: bool
    diagnostics: tuple[str, ...]
    evidence_domain: Literal["SIMULATION"] = field(default="SIMULATION", init=False)


def correlations(request: Request) -> Correlations:
    removal = next(op for op in request.logical.ops if isinstance(op, ir.RemoveRangeOp))
    effect = removal.effect
    return Correlations(request.diff.expected_diff_ref, effect.before.object_id, removal.op_ref,
                        effect.change_id, effect.proposal_ref, effect.geometry_ref,
                        tuple(o.object_id for o in request.base.objects),
                        tuple((op.op_ref, op.kind, op.target_ref, op.effect.before.object_id)
                              for op in request.logical.ops))


def _binding(request: Request) -> t.ArtifactBinding:
    return t.ArtifactBinding(request.diff.expected_diff_ref, request.safety_ref,
                             request.diff.base_snapshot)


def _admit(request: Request, current: SimulationState, post: NativeSnapshotRef) -> None:
    logical, diff, safety = request.logical, request.diff, request.safety
    if current != request.base or current.snapshot != diff.base_snapshot:
        raise ValueError("STALE_BASE")
    eligibility = a.apply_eligibility(request.candidate)
    if not eligibility.eligible:
        raise ValueError(eligibility.reason.value)
    candidate = request.candidate.candidate
    pb = diff.inputs.proposal.binding
    if (candidate.candidate_id != pb.candidate_ref or candidate.base != a.CandidateBase(
            current.snapshot.timeline_id, current.snapshot.timeline_version)):
        raise ValueError("CANDIDATE_BINDING")
    if (safety.status != s.PreflightStatus.EVALUATED or safety.verdict != s.SafetyVerdict.PASS
            or safety.inputs.compilation.expected_diff != diff
            or safety.inputs.current_snapshot != current.snapshot
            or s.preflight(safety.inputs) != safety):
        raise ValueError("SAFETY_NOT_BOUND_PASS")
    if (logical.authorization.binding != _binding(request)
            or logical.authorization.approval_ref != request.approval_ref
            or not request.approval_ref or logical.contract_version != "v1"
            or logical.authorization.contract_version != "v1"):
        raise ValueError("AUTHORIZATION_BINDING")
    if (post.timeline_id != current.snapshot.timeline_id
            or post.timeline_version != current.snapshot.timeline_version + 1
            or post.state_token == current.snapshot.state_token):
        raise ValueError("POST_BINDING")
    if set(current.objects) != set(diff.inputs.scope.objects):
        raise ValueError("SCOPE_BINDING")
    if any(o.retime != MappingKind.IDENTITY_1X or o.timeline_range.duration != o.source_range.duration
           for o in current.objects):
        raise ValueError("UNSUPPORTED_SHAPE")
    if len({op.op_ref for op in logical.ops}) != len(logical.ops):
        raise ValueError("DUPLICATE_OP")
    if len({target.target_ref for target in logical.targets}) != len(logical.targets):
        raise ValueError("DUPLICATE_TARGET")
    targets = {target.target_ref: target for target in logical.targets}
    if set(targets) != {op.target_ref for op in logical.ops}:
        raise ValueError("TARGET_COVERAGE")
    if Counter(op.effect for op in logical.ops) != Counter((*diff.primary_changes, *diff.displacements)):
        raise ValueError("EFFECT_COVERAGE")
    if (sum(isinstance(op, ir.RemoveRangeOp) for op in logical.ops) != 1
            or sum(isinstance(op, ir.TranslatePlacementOp) for op in logical.ops) > 1
            or len({op.effect.before.object_id for op in logical.ops}) != len(logical.ops)):
        raise ValueError("UNSUPPORTED_SHAPE")
    objects = {o.object_id: o for o in current.objects}
    predicted = dict(objects)
    for op in logical.ops:
        target = targets.get(op.target_ref)
        before = objects.get(op.effect.before.object_id)
        if (target is None or target.binding != _binding(request)
                or target.before != before or before != op.effect.before
                or target.contract_version != "v1"):
            raise ValueError("TARGET_BINDING")
        assert before is not None
        if isinstance(op, ir.RemoveRangeOp):
            cut = op.effect.removed_timeline_range
            if not before.timeline_range.start < cut.start < cut.end == before.timeline_range.end:
                raise ValueError("UNSUPPORTED_SHAPE")
            predicted[before.object_id] = replace(
                before, timeline_range=FrameRange(before.timeline_range.start, cut.start),
                source_range=FrameRange(before.source_range.start,
                                        before.source_range.end - cut.duration))
        else:
            delta = op.effect.delta_frames
            translated = replace(before, timeline_range=FrameRange(
                before.timeline_range.start + delta, before.timeline_range.end + delta))
            if translated != op.effect.after:
                raise ValueError("TRANSLATION_MISMATCH")
            predicted[before.object_id] = translated
    for states in (objects, predicted):
        for track, _ in current.tracks:
            ranges = sorted((o.timeline_range for o in states.values() if o.track_id == track),
                            key=lambda r: r.start)
            if any(left.end > right.start for left, right in pairwise(ranges)):
                raise ValueError("OVERLAPPING_PLACEMENTS")


def _evaluate(op: ir.ExecutionOp, before: d.PlacementState) -> d.PlacementState:
    if isinstance(op, ir.RemoveRangeOp):
        duration = op.effect.removed_timeline_range.duration
        return replace(before, timeline_range=FrameRange(before.timeline_range.start,
                                                        before.timeline_range.end - duration),
                       source_range=FrameRange(before.source_range.start,
                                               before.source_range.end - duration))
    return replace(before, timeline_range=FrameRange(
        before.timeline_range.start + op.effect.delta_frames,
        before.timeline_range.end + op.effect.delta_frames))


def execute(request: Request, current: SimulationState, post: NativeSnapshotRef) -> Run:
    records = [OperationRecord(op.op_ref, op.kind, op.target_ref, op.effect.before.object_id)
               for op in request.logical.ops]

    def result(state: SimulationState, outcome: str, stage: str | None, *diagnostics: str) -> Run:
        published = outcome == "COMPLETED"
        return Run(state, Receipt("simulation:receipt", _binding(request), request.logical.ir_ref,
                   request.logical.authorization.authorization_ref, current,
                   post if published else None, tuple(records), outcome, published, stage,
                   tuple(diagnostics)))

    try:
        _admit(request, current, post)
    except ValueError as error:
        reason = str(error)
        outcome = "REJECTED_STALE" if reason in ("STALE_BASE", "STALE") else "REJECTED_INPUT"
        return result(current, outcome, "ADMISSION", reason)
    draft = {o.object_id: o for o in current.objects}
    for index, op in enumerate(request.logical.ops):
        before = draft[op.effect.before.object_id]
        try:
            after = _evaluate(op, before)
            if after.object_id != before.object_id:
                raise ValueError("TARGET_ID_CHANGED")
            draft[before.object_id] = after
            records[index] = replace(records[index], attempted=True, result="EVALUATED",
                                     before=before, after=after)
        except Exception as error:  # noqa: BLE001 - discard the private draft on any interpreter failure.
            records[index] = replace(records[index], attempted=True, result="ERROR", before=before)
            return result(current, "ERROR_NO_PUBLICATION", "EVALUATION", type(error).__name__)
    try:
        state = SimulationState(post, tuple(draft.values()), current.tracks)
    except (TypeError, ValueError) as error:
        return result(current, "ERROR_NO_PUBLICATION", "PUBLICATION", type(error).__name__)
    return result(state, "COMPLETED", None)


def derive_actual(base: SimulationState, post: SimulationState, receipt: Receipt,
                  refs: Correlations) -> Evidence:
    """Observe state differences, not the planned effect; no ExpectedDiff input/helper reuse."""
    if (receipt.evidence_domain != "SIMULATION" or not receipt.published
            or receipt.outcome != "COMPLETED" or receipt.base != base
            or receipt.post_snapshot != post.snapshot
            or receipt.binding.base_snapshot != base.snapshot
            or receipt.binding.expected_diff_ref != refs.expected_diff_ref):
        return Evidence(None, False, ("MISSING_PUBLICATION_CORRESPONDENCE",))
    before = {o.object_id: o for o in base.objects}
    after = {o.object_id: o for o in post.objects}
    problems: list[str] = []
    records = receipt.operations
    if (set(refs.scope_ids) != set(before) or len(set(refs.scope_ids)) != len(refs.scope_ids)
            or len({r.op_ref for r in records}) != len(records)
            or len({r.object_id for r in records}) != len(records)):
        problems.append("SCOPE_OR_RECEIPT_AMBIGUOUS")
    if tuple((r.op_ref, r.kind, r.target_ref, r.object_id) for r in records) != refs.operation_refs:
        problems.append("OPERATION_CORRESPONDENCE_MISSING")
    removal_records = [r for r in records if r.kind == ir.ExecutionOpKind.REMOVE_RANGE]
    if (len(removal_records) != 1 or removal_records[0].op_ref != refs.primary_op_ref
            or removal_records[0].object_id != refs.primary_id):
        problems.append("PRIMARY_RECEIPT_MISSING")
    for record in records:
        if (not record.attempted or record.result != "EVALUATED"
                or record.before != before.get(record.object_id)
                or record.after != after.get(record.object_id)):
            problems.append("RECEIPT_STATE_MISMATCH")
    if (post.snapshot.timeline_id != base.snapshot.timeline_id
            or post.snapshot.timeline_version != base.snapshot.timeline_version + 1
            or post.snapshot.state_token == base.snapshot.state_token):
        problems.append("POST_RELATION_MISSING")
    primary = before.get(refs.primary_id)
    remaining = after.get(refs.primary_id)
    changes: tuple[d.RangeRemovalEffect, ...] = ()
    if primary is None or remaining is None:
        problems.append("PRIMARY_CORRESPONDENCE_MISSING")
    elif primary != remaining:
        lost = primary.timeline_range.end - remaining.timeline_range.end
        if (lost <= 0 or remaining.timeline_range.start != primary.timeline_range.start
                or remaining.source_range.start != primary.source_range.start
                or primary.source_range.end - remaining.source_range.end != lost
                or replace(remaining, timeline_range=primary.timeline_range,
                           source_range=primary.source_range) != primary
                or primary.retime != MappingKind.IDENTITY_1X):
            problems.append("PRIMARY_CHANGE_UNREPRESENTABLE")
        else:
            changes = (d.RangeRemovalEffect(refs.change_id, refs.proposal_ref, primary,
                       FrameRange(remaining.timeline_range.end, primary.timeline_range.end),
                       refs.geometry_ref),)
    observations = tuple(d.ActualObjectObservation(oid, before.get(oid), after.get(oid))
                         for oid in sorted(before.keys() | after.keys(), key=repr)
                         if oid != refs.primary_id)
    topology: tuple[str, ...] = () if base.tracks == post.tracks else ("simulation:observed-track-inventory-change",)
    if any(before[oid].track_id != after[oid].track_id for oid in before.keys() & after.keys()):
        topology += ("simulation:observed-membership-change",)
    complete = not problems
    actual = d.ActualDiff(
        "simulation:actual", refs.expected_diff_ref, base.snapshot, post.snapshot, changes,
        observations, d.PostRelationStatus.VERIFIED if complete else d.PostRelationStatus.UNVERIFIED,
        "simulation:base-post-evidence" if complete else None,
        "simulation:identity-evidence" if complete else None, topology,
    )
    return Evidence(actual, complete, tuple(problems))


def _current(request: Request, state: SimulationState) -> t.CurrentAuthorityFacts:
    return t.CurrentAuthorityFacts(_binding(request), request.logical.authorization.authorization_ref,
                                   state.snapshot, V.TRUE, V.TRUE, False)


def _advance(tx: t.Transaction, kind: t.TransactionEventKind,
             payload: t.EventPayload = None) -> t.Transaction:
    return t.transition(tx, t.TransactionEvent(tx.definition.transaction_ref,
                        tx.journal.events[-1].sequence_no + 1, kind, payload))


def finish_transaction(request: Request, run: Run, evidence: Evidence,
                       current: SimulationState) -> t.Transaction:
    """Explicit synthetic receipt -> existing lifecycle facts; no execution performed here."""
    E = t.TransactionEventKind
    definition = t.TransactionDefinition("simulation:transaction", _binding(request),
                                         request.logical.authorization, ("simulation:batch",))
    tx = _advance(t.prepare_transaction(definition), E.PRECOMMIT_STARTED)
    if (run.receipt.binding != definition.binding
            or run.receipt.authorization_ref != definition.authorization.authorization_ref
            or run.receipt.ir_ref != request.logical.ir_ref):
        raise ValueError("Receipt artifact mismatch")
    if run.receipt.published:
        _admit(request, run.receipt.base, run.state.snapshot)
    stale = run.receipt.outcome == "REJECTED_STALE"
    admitted = run.receipt.failure_stage != "ADMISSION"
    facts = t.PrecommitFacts(definition.binding, definition.authorization.authorization_ref,
                            run.receipt.base.snapshot, request.safety.status, request.safety.verdict,
                            V.FALSE if stale else V.TRUE, V.FALSE if stale else V.TRUE,
                            V.TRUE if admitted else V.UNKNOWN, V.TRUE if admitted else V.UNKNOWN,
                            False)
    ready = t.validate_precommit(definition, facts).status == t.PrecommitStatus.READY
    tx = _advance(tx, E.PRECOMMIT_PASSED if ready else E.PRECOMMIT_FAILED, facts)
    if not ready:
        return tx
    tx = _advance(tx, E.STEP_STARTED, "simulation:batch")
    if not run.receipt.published or run.receipt.outcome != "COMPLETED":
        tx = _advance(tx, E.STEP_FAILED, t.ExecutionStepResult(
            "simulation:batch", t.ExecutionStepStatus.FAILED, run.receipt.receipt_ref, False))
        return _advance(tx, E.TRANSACTION_TERMINATED, t.TransactionOutcome.FAILED_BEFORE_MUTATION)
    if (run.receipt.base != request.base or run.receipt.post_snapshot != run.state.snapshot
            or not run.receipt.operations
            or any(r.result != "EVALUATED" or not r.attempted for r in run.receipt.operations)):
        raise ValueError("Incomplete receipt")
    tx = _advance(tx, E.STEP_SUCCEEDED, t.ExecutionStepResult(
        "simulation:batch", t.ExecutionStepStatus.SUCCEEDED, run.receipt.receipt_ref, True))
    tx = _advance(tx, E.POSTFLIGHT_STARTED)
    independently_derived = derive_actual(request.base, run.state, run.receipt, correlations(request))
    if independently_derived != evidence:
        raise ValueError("Evidence does not belong to actual run")
    status = (d.verify_diff(request.diff, evidence.actual, current.snapshot).status
              if evidence.actual is not None else d.DiffVerificationStatus.UNVERIFIED)
    if current != run.state:
        status = d.DiffVerificationStatus.STALE
    kinds = {d.DiffVerificationStatus.MATCH: E.POSTFLIGHT_MATCHED,
             d.DiffVerificationStatus.MISMATCH: E.POSTFLIGHT_MISMATCH,
             d.DiffVerificationStatus.UNVERIFIED: E.POSTFLIGHT_UNVERIFIED,
             d.DiffVerificationStatus.STALE: E.POSTFLIGHT_STALE}
    tx = _advance(tx, kinds[status], t.PostflightEvidence(
        "simulation:verification", definition.binding, status, run.state.snapshot,
        _current(request, current)))
    outcome = (t.TransactionOutcome.VERIFIED_COMMITTED if status == d.DiffVerificationStatus.MATCH
               else t.TransactionOutcome.FAILED_POSTFLIGHT_UNRECOVERED)
    return _advance(tx, E.TRANSACTION_TERMINATED, outcome)


def promote(request: Request, tx: t.Transaction, run: Run, evidence: Evidence,
            current: SimulationState) -> a.CandidateWorkState:
    if (not evidence.complete or evidence.actual is None or current != run.state
            or evidence != derive_actual(request.base, run.state, run.receipt, correlations(request))
            or tx != finish_transaction(request, run, evidence, current)
            or t.promotion_eligibility(tx, _current(request, current)) != t.PromotionEligibility.ELIGIBLE
            or not a.apply_eligibility(request.candidate).eligible):
        raise ValueError("Promotion requires exact committed simulation evidence")
    record = a.ApplicationRecord(request.candidate.candidate.candidate_id,
                                 request.candidate.candidate.base,
                                 a.CandidateResultRef("simulation:result", a.CandidateBase(
                                     run.state.snapshot.timeline_id, run.state.snapshot.timeline_version)))
    work = request.candidate
    for event in (a.RecordApplication(record), a.RecordVerification(record, True),
                  a.PromoteCandidate(record.result.reference)):
        transition = a.transition(work, event)
        if not transition.accepted:
            raise ValueError(transition.reason.value)
        work = transition.state
    return work
