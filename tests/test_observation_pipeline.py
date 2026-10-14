"""TEST_ONLY_SUPPORT supplied reads/features; no native or media qualification."""

import ast
import inspect
from dataclasses import FrozenInstanceError, replace

import pytest

from davinci_ai_editor import evidence as e
from davinci_ai_editor import native_snapshot as n
from davinci_ai_editor import observation_pipeline as p
from davinci_ai_editor import pause
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
    MappingStatus,
    NativeSnapshotRef,
    PlacementTemporalBinding,
    SourceFrameRange,
    TimelineFrameRange,
)

REF = NativeSnapshotRef(TimelineId("timeline"), TimelineVersion(4), "state")
OID = TimelineObjectId(TrackId("audio"), ClipId("semantic-placement"))
PRODUCER = e.ProducerRef(e.ProducerKind.RULE, "TEST_ONLY_SUPPORT", "1", "v1")


def identity(ref: str) -> n.IdentityRef:
    return n.IdentityRef(ref, n.IdentityScope.SNAPSHOT_LOCAL, n.IdentityBasis.SNAPSHOT_ASSIGNED)


def inputs() -> tuple[n.NativeTimelineSnapshot, p.ObservationPlacementLink, p.AnalysisCoverage]:
    placement = n.NativePlacementSnapshot(
        "capture",
        identity("native-placement"),
        "audio",
        identity("media"),
        TimelineFrameRange(FrameRange(100, 300)),
        SourceFrameRange(FrameRange(0, 200)),
        FrameRate(24, 1),
        FrameRate(24, 1),
        MappingKind.IDENTITY_1X,
    )
    native = n.NativeTimelineSnapshot(
        "capture",
        identity("timeline"),
        REF.timeline_version,
        REF.state_token,
        FrameRate(24, 1),
        (
            n.NativeTrackSnapshot(
                "capture", identity("audio"), TrackType.AUDIO, ("native-placement",)
            ),
        ),
        (placement,),
        n.AdapterProvenance("TEST_ONLY_SUPPORT", "1", "v1"),
        n.CapabilityManifest(
            tuple(
                n.AdapterCapability(k, n.CapabilityState.SUPPORTED)
                for k in n.PAUSE_ANALYSIS.required_capabilities
            )
        ),
        n.CaptureConsistency.CONSISTENT,
        n.SnapshotCompleteness.COMPLETE_FOR_DECLARED_CAPABILITIES,
        "TEST_ONLY_SUPPORT-consistency",
    )
    binding = (
        PlacementTemporalBinding(
            "mapping",
            REF,
            OID,
            MediaId("media"),
            placement.timeline_range,
            placement.source_range,
            FrameRate(24, 1),
            FrameRate(24, 1),
            MappingKind.IDENTITY_1X,
        )
        if placement.timeline_range is not None and placement.source_range is not None
        else None
    )
    assert binding is not None
    link = p.ObservationPlacementLink("link", placement, binding, PRODUCER, ("capture",))
    coverage = p.AnalysisCoverage(
        "coverage",
        REF,
        "link",
        OID,
        placement.object_ref,
        FrameRange(100, 300),
        (PRODUCER,),
        ("mode", "band", "boundary", "conflict"),
        p.CoverageStatus.ANALYZED,
    )
    return native, link, coverage


def bundle(start: int = 120) -> e.EvidenceBundle:
    binding = e.EvidenceBinding(
        REF.timeline_id, REF.timeline_version, OID, FrameRange(start, start + 40)
    )
    records = tuple(
        e.EvidenceRecord(
            name,
            binding,
            PRODUCER,
            kind,
            e.EvidenceAssertion.PRESENT,
            e.EvidenceStrength.STRONG,
            payload,
        )
        for name, kind, payload in (
            ("mode", e.EvidenceKind.CONTENT_MODE, pause.ContentMode.SPOKEN_CONTENT),
            ("band", e.EvidenceKind.RELATIVE_PAUSE_BAND, pause.RelativePauseBand.LONG),
            (
                "boundary",
                e.EvidenceKind.TRANSCRIPT_BOUNDARY,
                pause.PauseBoundaryKind.SENTENCE_BOUNDARY,
            ),
        )
    )
    return e.EvidenceBundle(
        f"subject-{start}",
        REF.timeline_id,
        REF.timeline_version,
        OID,
        binding.observed_range,
        records,
        "v1",
    )


def run(
    native: n.NativeTimelineSnapshot | None = None,
    link: p.ObservationPlacementLink | None = None,
    coverage: p.AnalysisCoverage | None = None,
    *,
    current: NativeSnapshotRef = REF,
    subjects: tuple[e.EvidenceBundle, ...] | None = None,
) -> p.NativePausePreparation:
    initial_native, initial_link, initial_coverage = inputs()
    return p.prepare_pause_candidates_from_native(
        native or initial_native,
        current,
        links=(link or initial_link,),
        coverage=coverage or initial_coverage,
        bundles=(bundle(),) if subjects is None else subjects,
    )


def test_ready_composes_exact_existing_contracts() -> None:
    native, link, coverage = inputs()
    raw = bundle()
    result = run(native, link, coverage, subjects=(raw,))
    assert result.readiness.status == n.ReadinessStatus.READY
    assert result.readiness.profile is n.PAUSE_ANALYSIS
    assert result.readiness.snapshot is native
    assert result.links[0] is link and result.coverage is coverage
    subject = result.subjects[0]
    assert subject.bundle is raw
    assert (
        subject.preparation is not None and subject.preparation.status == e.PreparationStatus.READY
    )
    assert subject.candidate is not None and subject.candidate.observation is subject.observation
    assert subject.candidate == pause.classify_pause(subject.observation)
    assert result.projection is not None
    clip = result.projection.tracks[0].clips[0]
    assert clip.media_id == link.binding.media_id
    assert clip.source_range == link.binding.source_range.frames
    assert result.projection.version == REF.timeline_version
    assert subject.mappings[0].source_range == SourceFrameRange(FrameRange(20, 60))
    assert link.placement.object_ref.scope == n.IdentityScope.SNAPSHOT_LOCAL
    assert not hasattr(result, "authorization") and not hasattr(subject.candidate, "apply")


@pytest.mark.parametrize("case", ["stale", "unverified", "partial", "unsupported", "unstable"])
def test_native_gate(case: str) -> None:
    native, _, _ = inputs()
    current = REF
    if case == "stale":
        current = replace(REF, state_token="human-edit")
    elif case == "unverified":
        native = replace(native, capture_consistency=n.CaptureConsistency.UNVERIFIED)
    elif case == "partial":
        native = replace(native, completeness=n.SnapshotCompleteness.PARTIAL)
    elif case == "unsupported":
        native = replace(
            native,
            adapter_provenance=replace(
                native.adapter_provenance, snapshot_contract_version="future"
            ),
        )
    else:
        native = replace(native, capture_consistency=n.CaptureConsistency.UNSTABLE)
    result = run(native, current=current)
    assert result.readiness.status != n.ReadinessStatus.READY
    assert result.subjects[0].candidate is None
    assert result.subjects[0].preparation is None
    if case == "stale":
        assert result.coverage_status == p.CoverageStatus.STALE


@pytest.mark.parametrize(
    "field", ["media", "source", "timeline", "track", "rate", "source-rate", "snapshot", "kind"]
)
def test_link_must_agree_on_every_bound_fact(field: str) -> None:
    _, link, _ = inputs()
    b = link.binding
    altered = {
        "media": replace(b, media_id=MediaId("wrong")),
        "source": replace(b, source_range=SourceFrameRange(FrameRange(1, 201))),
        "timeline": replace(b, timeline_range=TimelineFrameRange(FrameRange(101, 301))),
        "track": replace(b, object_id=TimelineObjectId(TrackId("wrong"), OID.clip_id)),
        "rate": replace(b, timeline_rate=FrameRate(30, 1)),
        "source-rate": replace(b, source_rate=FrameRate(30, 1)),
        "snapshot": replace(b, snapshot_ref=replace(REF, state_token="old")),
        "kind": replace(b, mapping_kind=MappingKind.REVERSE),
    }[field]
    result = run(link=replace(link, binding=altered))
    assert result.subjects[0].candidate is None
    assert p.ObservationDiagnostic.LINK_MISMATCH in result.diagnostics


def test_repeated_media_requires_explicit_link_never_first_match() -> None:
    native, link, coverage = inputs()
    second = replace(
        link.placement,
        object_ref=identity("second-placement"),
        timeline_range=TimelineFrameRange(FrameRange(400, 600)),
    )
    native = replace(
        native,
        placements=(second, link.placement),
        tracks=(
            replace(native.tracks[0], placement_refs=("second-placement", "native-placement")),
        ),
    )
    assert run(native).subjects[0].candidate is not None
    no_link = p.prepare_pause_candidates_from_native(
        native, REF, links=(), coverage=coverage, bundles=(bundle(),)
    )
    assert no_link.subjects[0].candidate is None
    ambiguous = p.prepare_pause_candidates_from_native(
        native,
        REF,
        links=(link, replace(link, link_ref="alternative", placement=second)),
        coverage=coverage,
        bundles=(bundle(),),
    )
    assert p.ObservationDiagnostic.LINK_AMBIGUOUS in ambiguous.diagnostics
    assert ambiguous.subjects[0].candidate is None


def test_name_or_locator_is_not_placement_membership() -> None:
    _, link, _ = inputs()
    wrong = replace(link.placement, object_ref=identity("same-display-name.mp4"))
    assert run(link=replace(link, placement=wrong)).subjects[0].candidate is None
    with pytest.raises(ValueError):
        n.IdentityRef("name.mp4", n.IdentityScope.SNAPSHOT_LOCAL, n.IdentityBasis.FILENAME_ONLY)


@pytest.mark.parametrize(
    "kind", [MappingKind.VARIABLE_RETIME, MappingKind.REVERSE, MappingKind.UNKNOWN]
)
def test_unsupported_native_retime_does_not_prepare(kind: MappingKind) -> None:
    native, link, _ = inputs()
    placement = replace(link.placement, retime_kind=kind)
    native = replace(native, placements=(placement,))
    link = replace(link, placement=placement, binding=replace(link.binding, mapping_kind=kind))
    assert run(native, link).subjects[0].candidate is None


def test_non_integral_mapping_and_non_1x_projection_stop() -> None:
    native, link, _ = inputs()
    placement = replace(
        link.placement,
        source_range=SourceFrameRange(FrameRange(0, 101)),
        retime_kind=MappingKind.AFFINE_FORWARD,
    )
    native = replace(native, placements=(placement,))
    link = replace(
        link,
        placement=placement,
        binding=replace(
            link.binding,
            source_range=SourceFrameRange(FrameRange(0, 101)),
            mapping_kind=MappingKind.AFFINE_FORWARD,
        ),
    )
    result = run(native, link)
    assert any(m.status == MappingStatus.NON_INTEGRAL for m in result.subjects[0].mappings)
    assert result.subjects[0].candidate is None
    assert result.projection is None


@pytest.mark.parametrize("field", ["timeline", "version", "placement", "context", "contract"])
def test_bad_bundle_binding_or_version_cannot_produce_candidate(field: str) -> None:
    raw = bundle()
    # Empty records isolate outer binding; mixed records are rejected by EvidenceBundle itself.
    raw = replace(raw, evidence=())
    if field == "timeline":
        raw = replace(raw, timeline_id=TimelineId("wrong"))
    elif field == "version":
        raw = replace(raw, base_version=TimelineVersion(1))
    elif field == "placement":
        raw = replace(raw, target_object_id=TimelineObjectId(OID.track_id, ClipId("other")))
    elif field == "context":
        raw = replace(raw, context_range=FrameRange(0, 1000))
    else:
        raw = replace(raw, evidence_contract_version="v999")
    assert run(subjects=(raw,)).subjects[0].candidate is None


def test_existing_bundle_rejects_mixed_placement_and_outside_evidence() -> None:
    raw = bundle()
    r = raw.evidence[0]
    with pytest.raises(ValueError, match="Mixed"):
        replace(
            raw,
            evidence=(
                replace(
                    r,
                    binding=replace(
                        r.binding, object_id=TimelineObjectId(OID.track_id, ClipId("other"))
                    ),
                ),
            ),
        )
    with pytest.raises(ValueError, match="outside"):
        replace(
            raw,
            evidence=(replace(r, binding=replace(r.binding, observed_range=FrameRange(0, 10))),),
        )


@pytest.mark.parametrize("conflict", [False, True])
def test_unresolved_preparation_is_not_editorial_review(conflict: bool) -> None:
    raw = bundle()
    if conflict:
        boundary = next(r for r in raw.evidence if r.kind == e.EvidenceKind.TRANSCRIPT_BOUNDARY)
        raw = replace(
            raw,
            evidence=raw.evidence
            + (
                replace(
                    boundary, evidence_id="conflict", payload=pause.PauseBoundaryKind.WITHIN_PHRASE
                ),
            ),
        )
    else:
        raw = replace(raw, evidence=())
    subject = run(subjects=(raw,)).subjects[0]
    assert subject.preparation is not None
    assert subject.preparation.status == e.PreparationStatus.REVIEW_REQUIRED
    assert subject.observation is None and subject.candidate is None


@pytest.mark.parametrize("status", list(p.CoverageStatus))
def test_zero_subjects_preserve_each_coverage_meaning(status: p.CoverageStatus) -> None:
    _, _, coverage = inputs()
    result = run(coverage=replace(coverage, status=status), subjects=())
    assert result.coverage_status == status
    assert result.subjects == ()
    assert bool(result.diagnostics) == (
        status not in (p.CoverageStatus.ANALYZED, p.CoverageStatus.PARTIALLY_ANALYZED)
    )


def test_missing_coverage_is_not_analyzed() -> None:
    native, link, _ = inputs()
    result = p.prepare_pause_candidates_from_native(
        native, REF, links=(link,), coverage=None, bundles=()
    )
    assert result.coverage_status is None
    assert p.ObservationDiagnostic.COVERAGE_MISSING in result.diagnostics


def test_partial_multi_subjects_no_decision_count_or_authority() -> None:
    _, _, coverage = inputs()
    result = run(
        coverage=replace(coverage, status=p.CoverageStatus.PARTIALLY_ANALYZED),
        subjects=(bundle(120), bundle(180), bundle(240)),
    )
    assert result.coverage_status == p.CoverageStatus.PARTIALLY_ANALYZED
    assert len(result.subjects) == 3
    assert all(s.candidate is not None for s in result.subjects)
    assert not hasattr(result, "decision_count")


def test_human_change_rechecks_without_rebasing_old_evidence() -> None:
    native, link, coverage = inputs()
    original = run(native, link, coverage)
    changed = run(native, link, coverage, current=replace(REF, state_token="human-changed"))
    assert original.subjects[0].candidate is not None
    assert changed.coverage_status == p.CoverageStatus.STALE
    assert changed.subjects[0].candidate is None
    assert changed.links[0] is link and changed.coverage is coverage
    field = "status"
    with pytest.raises(FrozenInstanceError):
        setattr(coverage, field, p.CoverageStatus.ANALYZED)


def test_exact_affine_equal_span_uses_existing_mapping_without_rounding() -> None:
    native, link, _ = inputs()
    placement = replace(link.placement, retime_kind=MappingKind.AFFINE_FORWARD)
    native = replace(native, placements=(placement,))
    link = replace(
        link,
        placement=placement,
        binding=replace(link.binding, mapping_kind=MappingKind.AFFINE_FORWARD),
    )
    subject = run(native, link).subjects[0]
    assert subject.candidate is not None
    assert all(m.status == MappingStatus.EXACT for m in subject.mappings)


def test_exact_non_1x_affine_does_not_invent_domain_clip_geometry() -> None:
    native, link, _ = inputs()
    source = SourceFrameRange(FrameRange(0, 400))
    placement = replace(link.placement, retime_kind=MappingKind.AFFINE_FORWARD, source_range=source)
    native = replace(native, placements=(placement,))
    link = replace(
        link,
        placement=placement,
        binding=replace(link.binding, mapping_kind=MappingKind.AFFINE_FORWARD, source_range=source),
    )
    result = run(native, link)
    subject = result.subjects[0]
    assert all(m.status == MappingStatus.EXACT for m in subject.mappings)
    assert p.ObservationDiagnostic.PROJECTION_UNSUPPORTED in subject.diagnostics
    assert subject.candidate is None and result.projection is None


@pytest.mark.parametrize("case", ["producer", "source", "coverage-link", "coverage-native"])
def test_provenance_and_coverage_correlation_required(case: str) -> None:
    _, _, coverage = inputs()
    if case == "producer":
        coverage = replace(coverage, producers=(replace(PRODUCER, producer_name="other"),))
    elif case == "source":
        coverage = replace(coverage, source_refs=("missing",))
    elif case == "coverage-link":
        coverage = replace(coverage, link_ref="wrong")
    else:
        coverage = replace(coverage, native_object=identity("other"))
    assert run(coverage=coverage).subjects[0].candidate is None


def test_no_native_authority_classifier_or_timeline_reimplementation() -> None:
    tree = ast.parse(inspect.getsource(p))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports == {
        "dataclasses",
        "enum",
        "domain",
        "evidence",
        "native_snapshot",
        "pause",
        "temporal_mapping",
    }
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert classes == {
        "ObservationPlacementLink",
        "CoverageStatus",
        "AnalysisCoverage",
        "ObservationDiagnostic",
        "PreparedPauseSubject",
        "NativePausePreparation",
    }
