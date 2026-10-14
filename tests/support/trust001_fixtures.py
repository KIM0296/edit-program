"""TEST_ONLY_SUPPORT independent synthetic captures; never native qualification."""

from dataclasses import replace

from davinci_ai_editor import expected_diff as d
from davinci_ai_editor import native_snapshot as n
from davinci_ai_editor import pause_planning as planning
from davinci_ai_editor.domain import (
    ClipId,
    FrameRange,
    MediaId,
    TimelineId,
    TimelineObjectId,
    TimelineVersion,
    TrackId,
    TrackType,
)
from davinci_ai_editor.temporal_mapping import (
    FrameRate,
    MappingKind,
    NativeSnapshotRef,
    SourceFrameRange,
    TimelineFrameRange,
)
from davinci_ai_editor.trust_evidence import (
    IndependentReadEvidence,
    PreparedArtifactRevision,
    TargetCorrespondence,
)
from davinci_ai_editor.trust_evidence import (
    ObservationCompleteness as C,
)


def identity(value: str) -> n.IdentityRef:
    return n.IdentityRef(
        value, n.IdentityScope.SESSION_LOCAL_VERIFIED, n.IdentityBasis.ADAPTER_VERIFIED
    )


def capture(
    states: tuple[d.PlacementState, ...], snapshot: NativeSnapshotRef, acquisition: str
) -> n.NativeTimelineSnapshot:
    placements = tuple(
        n.NativePlacementSnapshot(
            acquisition,
            identity(state.object_id.clip_id),
            state.track_id,
            identity(state.media_id),
            TimelineFrameRange(state.timeline_range),
            SourceFrameRange(state.source_range),
            FrameRate(24, 1),
            FrameRate(24, 1),
            state.retime,
        )
        for state in states
    )
    tracks = tuple(
        n.NativeTrackSnapshot(
            acquisition,
            identity(track),
            TrackType.VIDEO,
            tuple(p.object_ref.ref for p in placements if p.track_ref == track),
        )
        for track in sorted({state.track_id for state in states})
    )
    return n.NativeTimelineSnapshot(
        acquisition,
        identity(snapshot.timeline_id),
        snapshot.timeline_version,
        snapshot.state_token,
        FrameRate(24, 1),
        tracks,
        placements,
        n.AdapterProvenance("TEST_ONLY_SUPPORT", "1", "v1"),
        n.CapabilityManifest(
            tuple(
                n.AdapterCapability(k, n.CapabilityState.SUPPORTED)
                for k in (
                    n.CapabilityKind.FRAME_RATE,
                    n.CapabilityKind.TIMELINE_IDENTITY,
                    n.CapabilityKind.TRACK_IDENTITY,
                    n.CapabilityKind.TRACK_TYPE,
                    n.CapabilityKind.PLACEMENT_IDENTITY,
                    n.CapabilityKind.MEDIA_IDENTITY,
                    n.CapabilityKind.TIMELINE_RANGE,
                    n.CapabilityKind.SOURCE_RANGE,
                    n.CapabilityKind.RETIME,
                    n.CapabilityKind.FRESHNESS,
                    n.CapabilityKind.CAPTURE_CONSISTENCY,
                )
            )
        ),
        n.CaptureConsistency.CONSISTENT,
        n.SnapshotCompleteness.COMPLETE_FOR_DECLARED_CAPABILITIES,
        "test-consistency",
    )


def read(
    states: tuple[d.PlacementState, ...],
    snapshot: NativeSnapshotRef,
    acquisition: str,
    *,
    post: bool = False,
    transaction_ref: str = "test-transaction",
) -> IndependentReadEvidence:
    recorded = capture(states, snapshot, acquisition)
    return IndependentReadEvidence(
        snapshot,
        recorded,
        "POST" if post else "PRE",
        20 if post else 0,
        ("whole-test-timeline",),
        C.COMPLETE,
        (recorded,),
        ("TEST_ONLY_SUPPORT",),
        transaction_ref if post else None,
        5 if post else None,
        "TEST_ONLY_SUPPORT",
        "test-read-order",
    )


def target(
    revision: PreparedArtifactRevision,
    state: d.PlacementState,
    snapshot: NativeSnapshotRef,
    target_ref: str,
    states: tuple[d.PlacementState, ...] = (),
) -> TargetCorrespondence:
    pre = read(states or (state,), snapshot, "pre-read")
    placement = next(
        p for p in pre.capture.placements if p.object_ref.ref == state.object_id.clip_id
    )
    return TargetCorrespondence(
        revision,
        state.object_id,
        snapshot,
        target_ref,
        pre,
        pre,
        placement,
        placement,
        (pre.capture,),
    )


def nonprimary_links(
    revision: PreparedArtifactRevision,
    observations: tuple[d.ActualObjectObservation, ...],
    pre: IndependentReadEvidence,
    post: IndependentReadEvidence,
) -> tuple[TargetCorrespondence, ...]:
    """Fixture's explicit ID assignment table only, not production identity discovery."""
    links = []
    for obs in observations:
        before = next(
            p for p in pre.capture.placements if p.object_ref.ref == obs.object_id.clip_id
        )
        after = tuple(
            p for p in post.capture.placements if p.object_ref.ref == obs.object_id.clip_id
        )
        links.append(
            TargetCorrespondence(
                revision,
                obs.object_id,
                pre.snapshot,
                "fixture-other",
                pre,
                pre,
                before,
                before,
                (pre.capture,),
                after,
                post,
                tuple(before for _ in after),
            )
        )
    return tuple(links)


def observed_actual(
    metadata: d.ActualDiff,
    revision: PreparedArtifactRevision,
    before_states: tuple[d.PlacementState, ...],
    after_states: tuple[d.PlacementState, ...],
    correspondence: TargetCorrespondence,
    change_ref: str,
    *,
    transaction_ref: str = "test-transaction",
) -> d.ActualDiff:
    """Measure supplied simulator state; metadata contributes correlation only.

    No expected effect or expected after state is an input. Primary state is read
    from these independent state stores, not metadata.primary_changes.
    """
    pre = read(before_states, metadata.base_snapshot, "pre-read")
    post = read(
        after_states,
        metadata.post_snapshot,
        "post-read",
        post=True,
        transaction_ref=transaction_ref,
    )
    before = next(
        state for state in before_states if state.object_id == correspondence.semantic_object
    )
    pre_placement = next(
        p for p in pre.capture.placements if p.object_ref.ref == before.object_id.clip_id
    )
    results = tuple(
        p for p in post.capture.placements if p.object_ref.ref == before.object_id.clip_id
    )
    corr = replace(
        correspondence,
        execution_read=pre,
        semantic_read=pre,
        execution_placement=pre_placement,
        semantic_placement=pre_placement,
        lineage_captures=(pre.capture,),
        result_placements=results,
        result_read=post,
        result_sources=tuple(pre_placement for _ in results),
    )
    primary = d.PrimaryResultObservation(
        change_ref, revision, before, pre_placement, results, corr, pre, post, C.COMPLETE
    )
    return replace(
        metadata,
        contract_version="v2",
        artifact_revision=revision,
        execution_pre_snapshot=pre.snapshot,
        primary_results=(primary,),
        completeness=C.COMPLETE,
        pre_read=pre,
        post_read=post,
        object_correspondences=nonprimary_links(revision, metadata.observations, pre, post),
    )


def zero_result(actual: d.ActualDiff) -> d.ActualDiff:
    """TEST_ONLY_SUPPORT complete observed loss, not absence of observation."""
    original = actual.primary_results[0]
    assert original.correspondence is not None
    states = tuple(obs.after for obs in actual.observations if obs.after is not None)
    post = read(states, actual.post_snapshot, "zero-result-read", post=True)
    corr = replace(
        original.correspondence, result_read=post, result_placements=(), result_sources=()
    )
    result = replace(original, post_read=post, post_placements=(), correspondence=corr)
    assert actual.artifact_revision is not None and actual.pre_read is not None
    return replace(
        actual,
        primary_results=(result,),
        post_read=post,
        object_correspondences=nonprimary_links(
            actual.artifact_revision, actual.observations, actual.pre_read, post
        ),
    )


def split_input() -> tuple[d.DiffCompilationInput, tuple[d.PlacementState, ...], NativeSnapshotRef]:
    """Independent declared expected plan and literal fixture pre-state. No post-state generator."""
    base = NativeSnapshotRef(TimelineId("main"), TimelineVersion(42), "base-state")
    post = NativeSnapshotRef(TimelineId("main"), TimelineVersion(43), "post-state")

    def state(
        track: str, item: str, media: str, start: int, end: int, source: int
    ) -> d.PlacementState:
        return d.PlacementState(
            TimelineObjectId(TrackId(track), ClipId(item)),
            MediaId(media),
            TrackId(track),
            FrameRange(start, end),
            FrameRange(source, source + end - start),
            MappingKind.IDENTITY_1X,
        )

    primary = state("audio", "dialogue", "media", 0, 200, 0)
    first = state("audio", "a", "repeated-media", 200, 260, 10)
    second = state("video", "b", "repeated-media", 210, 290, 10)
    untouched = state("audio", "unlisted", "media", 300, 400, 0)
    states = (primary, first, second, untouched)
    binding = planning.PlanningBinding("candidate", base, primary.object_id, FrameRange(100, 160))
    cut = FrameRange(110, 150)
    geometry = planning.PauseCutGeometry(
        "geometry", binding, (cut,), 20, planning.GeometryProvenance("caller", "v1"), "v1"
    )
    proposal = planning.PauseEditProposal(
        "proposal",
        binding,
        planning.TemporalEditIntent.SHORTEN_GAP,
        geometry,
        cut,
        "target",
        "snapshot",
        "dependency",
    )
    diff_binding = d.DiffBinding("proposal", binding, "geometry", cut)
    assessment = d.DisplacementParticipationAssessment(
        "assessment",
        diff_binding,
        d.ParticipationStatus.RESOLVED,
        (
            d.DisplacementParticipant(first, -40, first.track_id),
            d.DisplacementParticipant(second, -40, second.track_id),
        ),
        True,
    )
    scope = d.PreservationScope("scope", diff_binding, states)
    return (
        d.DiffCompilationInput(
            "diff", proposal, assessment, scope, base, d.CompilerProvenance("pure-diff", "v1")
        ),
        states,
        post,
    )
