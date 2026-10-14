"""TEST_ONLY_SUPPORT adversarial reads. No Resolve/native qualification."""

import copy
import hashlib
import json
from dataclasses import replace

import pytest
from support import trust001_fixtures as f
from test_orchestration import (
    approval_for,
    approved_state,
    authorized,
    completion,
    prepared,
    runtime_admission,
)

from davinci_ai_editor import execution_ir as ir
from davinci_ai_editor import expected_diff as d
from davinci_ai_editor import orchestration as o
from davinci_ai_editor.domain import (
    ClipId,
    FrameRange,
    MediaId,
    TimelineId,
    TimelineObjectId,
    TrackId,
)
from davinci_ai_editor.temporal_mapping import MappingKind, NativeSnapshotRef
from davinci_ai_editor.trust_evidence import (
    IndependentReadEvidence,
    PreparedArtifactRevision,
    TargetCorrespondence,
    artifact_revision,
    canonical_bytes,
)
from davinci_ai_editor.trust_evidence import (
    ObservationCompleteness as C,
)

INPUT, (PRIMARY, A, B, UNCHANGED), POST = f.split_input()


def sample() -> tuple[d.ExpectedDiff, d.ActualDiff, PreparedArtifactRevision]:
    diff = d.compile_expected_diff(INPUT).expected_diff
    assert diff is not None
    revision = artifact_revision("TEST_ONLY_SUPPORT", "edit", {"expected": diff})
    # These independently supplied fixture states are NOT calculated from ExpectedDiff.
    states = (PRIMARY, A, B, UNCHANGED)
    after = (
        replace(
            PRIMARY,
            object_id=TimelineObjectId(PRIMARY.track_id, ClipId("left")),
            timeline_range=FrameRange(0, 110),
            source_range=FrameRange(0, 110),
        ),
        replace(
            PRIMARY,
            object_id=TimelineObjectId(PRIMARY.track_id, ClipId("right")),
            timeline_range=FrameRange(110, 160),
            source_range=FrameRange(150, 200),
        ),
        replace(A, timeline_range=FrameRange(160, 220)),
        replace(B, timeline_range=FrameRange(170, 250)),
        UNCHANGED,
    )
    pre = f.read(states, diff.base_snapshot, "independent-pre")
    post = f.read(after, POST, "independent-post", post=True)
    primary = next(p for p in pre.capture.placements if p.object_ref.ref == "dialogue")
    results = tuple(p for p in post.capture.placements if p.object_ref.ref in ("left", "right"))
    corr = replace(
        f.target(revision, PRIMARY, diff.base_snapshot, "target"),
        semantic_read=pre,
        execution_read=pre,
        semantic_placement=primary,
        execution_placement=primary,
        lineage_captures=(pre.capture,),
        result_placements=results,
        result_read=post,
        result_sources=(primary, primary),
    )
    observation = d.PrimaryResultObservation(
        diff.primary_changes[0].change_id,
        revision,
        PRIMARY,
        primary,
        results,
        corr,
        pre,
        post,
        C.COMPLETE,
    )
    others = tuple(
        d.ActualObjectObservation(before.object_id, before, result)
        for before, result in zip((A, B, UNCHANGED), after[2:], strict=True)
    )
    actual = d.ActualDiff(
        "actual-read",
        diff.expected_diff_ref,
        diff.base_snapshot,
        POST,
        (),
        others,
        d.PostRelationStatus.VERIFIED,
        "read-relations",
        "read-identities",
        (),
        "v2",
        revision,
        pre.snapshot,
        (observation,),
        C.COMPLETE,
        pre,
        post,
        f.nonprimary_links(revision, others, pre, post),
    )
    return diff, actual, revision


def post_results(actual: d.ActualDiff, states: tuple[d.PlacementState, ...]) -> d.ActualDiff:
    """Fresh synthetic read after state-store mutation, not an expected-value copier."""
    old = actual.primary_results[0]
    assert old.correspondence is not None and actual.post_read is not None
    other_states = tuple(obs.after for obs in actual.observations if obs.after is not None)
    post = f.read((*states, *other_states), actual.post_snapshot, "changed-post-read", post=True)
    results = post.capture.placements[: len(states)]
    corr = replace(
        old.correspondence,
        result_placements=results,
        result_read=post,
        result_sources=tuple(old.execution_before for _ in results),
    )
    result = replace(old, post_placements=results, post_read=post, correspondence=corr)
    assert actual.artifact_revision is not None and actual.pre_read is not None
    return replace(
        actual,
        post_read=post,
        primary_results=(result,),
        object_correspondences=f.nonprimary_links(
            actual.artifact_revision, actual.observations, actual.pre_read, post
        ),
    )


def verify(
    actual: d.ActualDiff, expected: d.ExpectedDiff, revision: PreparedArtifactRevision
) -> d.DiffVerificationResult:
    return d.verify_diff(expected, actual, actual.post_snapshot, revision)


def test_fixed_canonical_vector_and_round_trip() -> None:
    canonical = b'{"a":1,"b":2}'
    assert canonical_bytes({"b": 2, "a": 1}) == canonical
    assert canonical_bytes(json.loads(canonical)) == canonical
    assert (
        hashlib.sha256(canonical).hexdigest()
        == "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    )
    assert (
        artifact_revision("test", "id", {"a": 1, "b": 2}).content_digest
        == hashlib.sha256(canonical).hexdigest()
    )


def test_prepared_manifest_fixed_vector_and_json_round_trip() -> None:
    value = prepared()
    assert value.artifact_revision is not None
    assert value.artifact_revision.content_digest == (
        "99803f99a7009482c83dc4608f4691bac0680b4c47e64435af27b8db30980343"
    )
    encoded = canonical_bytes(value.semantic_manifest())
    assert canonical_bytes(json.loads(encoded)) == encoded
    assert value.artifact_revision.matches(json.loads(encoded))


@pytest.mark.parametrize("bad", [1.5, {1, 2}, object()])
def test_unstable_canonical_values_rejected(bad: object) -> None:
    with pytest.raises(TypeError):
        canonical_bytes(bad)


def test_reconstructed_semantic_artifact_can_use_bound_approval() -> None:
    original = prepared()
    rebuilt = copy.deepcopy(original)
    assert rebuilt is not original and rebuilt.artifact_revision == original.artifact_revision
    assert (
        o.authorize_edit(rebuilt, approval_for(original), approved_state(original)).status
        == o.CompositionStatus.READY
    )


def test_revision_json_round_trip_and_same_id_changed_digest_rejected() -> None:
    from dataclasses import asdict

    revision = prepared().artifact_revision
    assert revision is not None
    rebuilt = PreparedArtifactRevision(**json.loads(json.dumps(asdict(revision))))
    assert rebuilt == revision and rebuilt is not revision
    with pytest.raises(ValueError, match="cannot be reused"):
        replace(revision, content_digest="0" * 64)


def test_admission_rejects_missing_target_correspondence() -> None:
    auth, work = authorized()
    runtime = runtime_admission(auth)
    validation = runtime.validation_inputs
    targets = tuple(
        replace(target, correspondence=None) for target in validation.execution_ir.targets
    )
    changed = replace(
        runtime,
        validation_inputs=replace(
            validation, execution_ir=replace(validation.execution_ir, targets=targets)
        ),
    )
    result = o.admit_execution(auth, changed, work)
    assert result.status == o.CompositionStatus.BLOCKED and result.transaction is None


def test_semantic_revision_propagates_through_existing_binding() -> None:
    auth, _ = authorized()
    runtime = runtime_admission(auth)
    revision = auth.prepared.artifact_revision
    assert revision is not None
    assert auth.bound_approval.artifact_revision == revision
    assert auth.authorization.binding.artifact_revision == revision
    assert runtime.transaction_definition.binding.artifact_revision == revision
    assert runtime.precommit_facts.binding.artifact_revision == revision
    assert all(
        target.binding.artifact_revision == revision
        for target in runtime.validation_inputs.execution_ir.targets
    )


@pytest.mark.parametrize("side", ["semantic", "execution"])
@pytest.mark.parametrize("field", ["media", "source", "timeline", "track", "retime", "object"])
def test_admission_rejects_different_strong_placement(side: str, field: str) -> None:
    auth, work = authorized()
    runtime = runtime_admission(auth)
    validation = runtime.validation_inputs
    target, *remaining = validation.execution_ir.targets
    correspondence = target.correspondence
    assert correspondence is not None
    before = target.before
    alternatives = {
        "media": replace(before, media_id=MediaId("other-media")),
        "source": replace(before, source_range=FrameRange(10000, 11000)),
        "timeline": replace(before, timeline_range=FrameRange(10000, 11000)),
        "track": replace(before, track_id=TrackId("other-track")),
        "retime": replace(before, retime=MappingKind.REVERSE),
        "object": replace(
            before, object_id=TimelineObjectId(before.track_id, ClipId("other-native-object"))
        ),
    }
    other = f.read((alternatives[field],), correspondence.semantic_snapshot, "other-pre-read")
    # Membership, strong identity, approved revision and target_ref all still pass.
    if side == "semantic":
        changed_correspondence = replace(
            correspondence,
            semantic_read=other,
            semantic_placement=other.capture.placements[0],
            lineage_captures=(other.capture, correspondence.execution_read.capture),
        )
    else:
        changed_correspondence = replace(
            correspondence,
            execution_read=other,
            execution_placement=other.capture.placements[0],
            lineage_captures=(correspondence.semantic_read.capture, other.capture),
        )
    assert changed_correspondence.admission_bound()
    changed = replace(
        validation,
        execution_ir=replace(
            validation.execution_ir,
            targets=(replace(target, correspondence=changed_correspondence), *remaining),
        ),
    )
    assert (
        ir.validate_execution_ir(changed).status
        != ir.ExecutionIRValidationStatus.READY_FOR_EXECUTION
    )
    result = o.admit_execution(auth, replace(runtime, validation_inputs=changed), work)
    assert result.status == o.CompositionStatus.BLOCKED
    assert result.transaction is None


@pytest.mark.parametrize(
    "case", ["exact", "source", "timeline", "track", "media", "retime", "no-lineage"]
)
def test_staging_prestate_requires_exact_semantics_and_lineage(case: str) -> None:
    auth, work = authorized()
    runtime = runtime_admission(auth)
    validation = runtime.validation_inputs
    target, *remaining = validation.execution_ir.targets
    c = target.correspondence
    assert c is not None
    before = target.before
    staging_state = replace(
        before, object_id=TimelineObjectId(before.track_id, ClipId("staging-object"))
    )
    if case == "source":
        staging_state = replace(staging_state, source_range=FrameRange(10000, 11000))
    elif case == "timeline":
        staging_state = replace(staging_state, timeline_range=FrameRange(10000, 11000))
    elif case == "track":
        staging_state = replace(staging_state, track_id=TrackId("other-track"))
    elif case == "media":
        staging_state = replace(staging_state, media_id=MediaId("other-media"))
    elif case == "retime":
        staging_state = replace(staging_state, retime=MappingKind.REVERSE)
    staging_snapshot = replace(c.semantic_snapshot, timeline_id=TimelineId("staging-timeline"))
    staging = f.read((staging_state,), staging_snapshot, "staging-pre-read")
    correspondence = replace(
        c,
        execution_read=staging,
        execution_placement=staging.capture.placements[0],
        lineage_captures=(c.semantic_read.capture,)
        if case == "no-lineage"
        else (c.semantic_read.capture, staging.capture),
    )
    changed = replace(
        validation,
        execution_ir=replace(
            validation.execution_ir,
            targets=(replace(target, correspondence=correspondence), *remaining),
        ),
    )
    ready = (
        ir.validate_execution_ir(changed).status
        == ir.ExecutionIRValidationStatus.READY_FOR_EXECUTION
    )
    result = o.admit_execution(auth, replace(runtime, validation_inputs=changed), work)
    assert ready == (case == "exact")
    if case == "exact":
        assert result.status == o.CompositionStatus.READY
        assert result.transaction is not None
    else:
        assert result.status == o.CompositionStatus.BLOCKED
        assert result.transaction is None


def test_equal_native_prestates_cannot_replace_approved_prestate() -> None:
    auth, work = authorized()
    runtime = runtime_admission(auth)
    validation = runtime.validation_inputs
    target, *remaining = validation.execution_ir.targets
    c = target.correspondence
    assert c is not None
    wrong = replace(target.before, source_range=FrameRange(10000, 11000))
    read = f.read((wrong,), c.semantic_snapshot, "equal-but-wrong-pre-read")
    c = replace(
        c,
        semantic_read=read,
        execution_read=read,
        semantic_placement=read.capture.placements[0],
        execution_placement=read.capture.placements[0],
        lineage_captures=(read.capture,),
    )
    assert c.admission_bound()
    changed = replace(
        validation,
        execution_ir=replace(
            validation.execution_ir,
            targets=(replace(target, correspondence=c), *remaining),
        ),
    )
    assert (
        ir.validate_execution_ir(changed).status
        != ir.ExecutionIRValidationStatus.READY_FOR_EXECUTION
    )
    result = o.admit_execution(auth, replace(runtime, validation_inputs=changed), work)
    assert result.status == o.CompositionStatus.BLOCKED
    assert result.transaction is None


def test_same_revision_tampered_geometry_fails_and_new_revision_differs() -> None:
    value = prepared()
    changed = replace(
        value, geometry=replace(value.geometry, removed_ranges=(FrameRange(347, 420),))
    )
    assert changed.artifact_revision == value.artifact_revision
    result = o.authorize_edit(changed, approval_for(value), approved_state(value))
    assert result.status == o.CompositionStatus.BLOCKED
    assert value.artifact_revision is not None
    assert not value.artifact_revision.matches(changed.semantic_manifest())
    revision = artifact_revision(
        "prepared-edit", value.inputs.authority_candidate.candidate_id, changed.semantic_manifest()
    )
    assert revision.revision_id != value.artifact_revision.revision_id


def test_same_name_new_revision_cannot_use_old_approval() -> None:
    value = prepared()
    new = o.prepare_edit(
        replace(value.inputs, compiler_provenance=d.CompilerProvenance("revision-2", "1"))
    ).prepared
    assert new is not None
    assert (
        new.inputs.authority_candidate.candidate_id == value.inputs.authority_candidate.candidate_id
    )
    assert o.authorize_edit(new, approval_for(value), approved_state(value)).authorized is None


def test_correct_split_match_without_expected_shaped_actual_effect() -> None:
    expected, actual, revision = sample()
    assert actual.primary_changes == ()
    assert verify(actual, expected, revision).status == d.DiffVerificationStatus.MATCH


def test_correct_single_match_from_simulator_read() -> None:
    auth, runtime, _ = completion()
    assert runtime.actual_diff is not None and auth.prepared.artifact_revision is not None
    assert len(runtime.actual_diff.primary_results[0].post_placements) == 1
    assert (
        verify(
            runtime.actual_diff, auth.prepared.expected_diff, auth.prepared.artifact_revision
        ).status
        == d.DiffVerificationStatus.MATCH
    )


@pytest.mark.parametrize(
    "case",
    ["no-mutation", "wrong-amount", "zero", "wrong-source", "overlap", "reversed", "missing"],
)
def test_primary_observed_mismatch(case: str) -> None:
    expected, actual, revision = sample()
    left = replace(
        PRIMARY,
        object_id=TimelineObjectId(PRIMARY.track_id, ClipId("left")),
        timeline_range=FrameRange(0, 110),
        source_range=FrameRange(0, 110),
    )
    right = replace(
        PRIMARY,
        object_id=TimelineObjectId(PRIMARY.track_id, ClipId("right")),
        timeline_range=FrameRange(110, 160),
        source_range=FrameRange(150, 200),
    )
    options = {
        "no-mutation": (PRIMARY,),
        "zero": (),
        "missing": (left,),
        "wrong-amount": (left, replace(right, source_range=FrameRange(149, 200))),
        "wrong-source": (left, replace(right, source_range=FrameRange(151, 201))),
        "overlap": (left, replace(right, timeline_range=FrameRange(109, 159))),
        "reversed": (right, left),
    }
    assert (
        verify(post_results(actual, options[case]), expected, revision).status
        == d.DiffVerificationStatus.MISMATCH
    )


def test_duplicate_result_fragment() -> None:
    expected, actual, revision = sample()
    original = actual.primary_results[0]
    assert original.correspondence is not None
    duplicates = (original.post_placements[0], original.post_placements[0])
    changed = replace(
        original,
        post_placements=duplicates,
        correspondence=replace(original.correspondence, result_placements=duplicates),
    )
    result = verify(replace(actual, primary_results=(changed,)), expected, revision)
    assert result.status == d.DiffVerificationStatus.MISMATCH


@pytest.mark.parametrize(
    "case",
    ["no-correspondence", "reused-acquisition", "partial-empty", "missing-read", "missing-primary"],
)
def test_uncertain_evidence_never_matches(case: str) -> None:
    expected, actual, revision = sample()
    primary = actual.primary_results[0]
    if case == "no-correspondence":
        actual = replace(actual, primary_results=(replace(primary, correspondence=None),))
    elif case == "reused-acquisition":
        actual = replace(actual, post_read=actual.pre_read)
    elif case == "partial-empty":
        actual = post_results(actual, ())
        actual = replace(actual, completeness=C.PARTIAL)
    elif case == "missing-read":
        actual = replace(actual, post_read=None)
    else:
        actual = replace(actual, primary_results=())
    assert verify(actual, expected, revision).status == d.DiffVerificationStatus.UNVERIFIED


def test_wrong_clip_origin_is_mismatch() -> None:
    expected, actual, revision = sample()
    primary = actual.primary_results[0]
    assert primary.correspondence is not None
    other = next(p for p in primary.pre_read.capture.placements if p.object_ref.ref == "a")
    corr = replace(primary.correspondence, result_sources=(other, other))
    assert (
        verify(
            replace(actual, primary_results=(replace(primary, correspondence=corr),)),
            expected,
            revision,
        ).status
        == d.DiffVerificationStatus.MISMATCH
    )


def test_command_receipt_is_not_read_evidence() -> None:
    _, actual, _ = sample()
    assert actual.post_read is not None
    with pytest.raises(TypeError):
        replace(actual.post_read, capture="command-success")  # type: ignore[arg-type]


def test_legacy_copied_expected_cannot_match_or_commit() -> None:
    auth, runtime, work = completion()
    assert runtime.actual_diff is not None
    legacy = replace(
        runtime.actual_diff,
        contract_version="v1",
        primary_results=(),
        primary_changes=auth.prepared.expected_diff.primary_changes,
    )
    assert (
        d.verify_diff(auth.prepared.expected_diff, legacy, runtime.current_post_snapshot).status
        == d.DiffVerificationStatus.UNVERIFIED
    )
    result = o.finalize_edit(auth, replace(runtime, actual_diff=legacy), work)
    assert (
        result.verification is not None
        and result.verification.status == d.DiffVerificationStatus.UNVERIFIED
    )
    assert not result.authority_transitions


def test_unexpected_ripple_mismatch() -> None:
    expected, actual, revision = sample()
    actual = replace(actual, topology_change_refs=("observed-extra-ripple",))
    assert verify(actual, expected, revision).status == d.DiffVerificationStatus.MISMATCH


def test_primary_observation_is_not_unexpected_by_definition() -> None:
    auth, runtime, _ = completion()
    actual = runtime.actual_diff
    assert actual is not None and auth.prepared.artifact_revision is not None
    primary = actual.primary_results[0]
    placement = primary.post_placements[0]
    assert placement.source_range is not None and placement.timeline_range is not None
    state = replace(
        primary.semantic_before,
        source_range=placement.source_range.frames,
        timeline_range=placement.timeline_range.frames,
    )
    duplicate = d.ActualObjectObservation(
        primary.semantic_before.object_id, primary.semantic_before, state
    )
    actual = replace(actual, observations=(*actual.observations, duplicate))
    assert (
        verify(actual, auth.prepared.expected_diff, auth.prepared.artifact_revision).status
        == d.DiffVerificationStatus.MATCH
    )


@pytest.mark.parametrize("proven", [False, True])
def test_staging_requires_explicit_original_to_staging_correspondence(proven: bool) -> None:
    expected, actual, revision = sample()
    original_pre, original_post = actual.pre_read, actual.post_read
    assert original_pre is not None and original_post is not None

    def staged(read: IndependentReadEvidence) -> IndependentReadEvidence:
        acquisition = "staging-" + read.capture.capture_id
        snapshot = NativeSnapshotRef(
            TimelineId("staging"),
            read.snapshot.timeline_version,
            "staging-" + read.snapshot.state_token,
        )
        capture = replace(
            read.capture,
            capture_id=acquisition,
            timeline_ref=f.identity("staging"),
            state_token=snapshot.state_token,
            tracks=tuple(replace(track, capture_id=acquisition) for track in read.capture.tracks),
            placements=tuple(replace(p, capture_id=acquisition) for p in read.capture.placements),
        )
        return replace(read, snapshot=snapshot, capture=capture, source_captures=(capture,))

    pre, post = staged(original_pre), staged(original_post)

    def translate(c: TargetCorrespondence) -> TargetCorrespondence:
        execution = next(
            p for p in pre.capture.placements if p.object_ref == c.execution_placement.object_ref
        )
        results = tuple(
            next(p for p in post.capture.placements if p.object_ref == old.object_ref)
            for old in c.result_placements
        )
        return replace(
            c,
            execution_read=pre,
            execution_placement=execution,
            lineage_captures=(original_pre.capture, pre.capture) if proven else (),
            result_read=post,
            result_placements=results,
            result_sources=tuple(execution for _ in results),
        )

    old = actual.primary_results[0]
    assert old.correspondence is not None
    corr = translate(old.correspondence)
    primary = replace(
        old,
        correspondence=corr,
        execution_before=corr.execution_placement,
        pre_read=pre,
        post_read=post,
        post_placements=corr.result_placements,
    )
    actual = replace(
        actual,
        execution_pre_snapshot=pre.snapshot,
        post_snapshot=post.snapshot,
        pre_read=pre,
        post_read=post,
        primary_results=(primary,),
        object_correspondences=tuple(translate(c) for c in actual.object_correspondences),
    )
    assert actual.base_snapshot.timeline_id != actual.post_snapshot.timeline_id
    result = verify(actual, expected, revision)
    assert result.status == (
        d.DiffVerificationStatus.MATCH if proven else d.DiffVerificationStatus.UNVERIFIED
    )


def test_failed_post_read_preserves_journal_and_has_no_retry() -> None:
    from test_runtime_integration import Harness, issue

    from davinci_ai_editor import runtime_integration as integration
    from davinci_ai_editor import runtime_ports as ports

    h = Harness()
    evidence = h.executed()
    h.faults["postflight"] = issue(ports.PortIssueKind.UNKNOWN)
    before_calls = len(h.trace)
    result = integration.finalize_postflight(
        evidence, "verify", observations=h, authority=h, lifecycle=h
    )
    assert result.evidence.transaction is evidence.transaction
    assert result.result is h.faults["postflight"]
    assert h.trace[before_calls:] == ["postflight"]
