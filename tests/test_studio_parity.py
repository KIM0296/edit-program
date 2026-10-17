"""STUDIO-T0: file transport vs Studio transport (FAKE Resolve) on one shared fixture.

TEST_ONLY_SUPPORT. No Resolve, no media, no rendering. File-path editor actions
are text edits of our own xmeml; Studio editor actions are direct edits of the
fake object graph (``tests/support/fake_resolve.py``).
"""

from dataclasses import replace
from pathlib import Path

import pytest
from support import fake_resolve as fr

from davinci_ai_editor.apply_cuts import (
    AppliedTimeline,
    ApplyConfirmation,
    ApplyRefused,
    SkipReason,
    actual_binding_digest,
    apply_approved_cuts,
    build_apply_confirmation,
)
from davinci_ai_editor.candidate_markers import (
    CandidateHandoff,
    CutCandidate,
    attach_candidate_markers,
    read_marker_selections,
)
from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.handoff_model import (
    HandoffClip,
    HandoffGap,
    HandoffMediaRef,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
    MarkerColor,
    ReimportedTimeline,
)
from davinci_ai_editor.layer_policy import TrackPolicyOverride
from davinci_ai_editor.native_snapshot import CaptureConsistency
from davinci_ai_editor.roundtrip_diff import (
    RoundTripFormat,
    diff_xmeml_roundtrip,
    roundtrip_artifact_ref,
)
from davinci_ai_editor.roundtrip_verification import (
    ActualProvenance,
    VerificationStatus,
    verify_roundtrip,
)
from davinci_ai_editor.runtime_ports import PortIssueKind
from davinci_ai_editor.studio_apply_planner import ApplyTier, PlanStatus
from davinci_ai_editor.studio_capabilities import (
    STUDIO_CAPABILITY_MATRIX,
    CapabilityGrant,
    CapabilityStatus,
    ItemMarkerBasis,
    StudioCapability,
    StudioCapabilityProfile,
    capability_entry,
    documented_profile,
)
from davinci_ai_editor.studio_tiered_apply import TieredApplyPort
from davinci_ai_editor.studio_transport import (
    MUTATION_METHODS,
    READ_METHODS,
    Fallback,
    MutationStatus,
    ResolveMutationPort,
    ResolveReadPort,
    StudioDiagnosticCode,
    StudioReadResult,
    TrackCutPolicy,
    candidate_sets_equal,
    cut_geometry,
    diff_studio_read,
    expected_from_actual,
)
from davinci_ai_editor.temporal_mapping import FrameRate
from davinci_ai_editor.trust_evidence import PreparedArtifactRevision, artifact_revision
from davinci_ai_editor.xmeml_reader import read_xmeml
from davinci_ai_editor.xmeml_writer import write_xmeml

RATE = FrameRate(25, 1)
START = 86400  # 01:00:00:00 at 25 fps: exercises absolute GetStart -> relative frames
INTERVIEW = HandoffMediaRef("interview.mov", "C:/media/interview.mov", FrameRange(0, 1000), 0)
BROLL = HandoffMediaRef("broll.mov", "C:/media/broll.mov", FrameRange(0, 1000), 0)

CANDIDATES = (
    CutCandidate("AIE-0001", FrameRange(100, 120), "long pause"),
    CutCandidate("AIE-0002", FrameRange(250, 262), "breath"),
    CutCandidate("AIE-0003", FrameRange(30, 40), "filler um"),
    CutCandidate("AIE-0004", FrameRange(300, 310), "repeat"),
)
DECISIONS = {"AIE-0001": "OK", "AIE-0002": "승인", "AIE-0003": "X"}  # AIE-0004 stays pending


def _interview_track(name: str, kind: HandoffTrackKind, suffix: str) -> HandoffTrack:
    spans = (("A", 0, 100), ("P1", 100, 120), ("B", 120, 250), ("P2", 250, 262), ("C", 262, 400))
    return HandoffTrack(
        name,
        kind,
        tuple(HandoffClip(n + suffix, INTERVIEW, FrameRange(s, e)) for n, s, e in spans),
    )


def fixture() -> HandoffTimeline:
    """Interview pre-cut at the pauses (V1 + linked A1) and a B-roll layer on V2."""
    v2 = HandoffTrack(
        "Video 2",
        HandoffTrackKind.VIDEO,
        (HandoffGap(300), HandoffClip("Broll", BROLL, FrameRange(0, 50))),
    )
    return HandoffTimeline(
        "Interview",
        RATE,
        START,
        (
            _interview_track("Video 1", HandoffTrackKind.VIDEO, ""),
            v2,
            _interview_track("Audio 1", HandoffTrackKind.AUDIO, ".a"),
        ),
    )


def profile(*, split: bool = False, **overrides: CapabilityGrant) -> StudioCapabilityProfile:
    grants = {
        entry.capability: CapabilityGrant.GRANTED_TEST_ONLY
        for entry in STUDIO_CAPABILITY_MATRIX
        if entry.used_by_transport and entry.status is not CapabilityStatus.NOT_AVAILABLE
    }
    if split:
        grants[StudioCapability.SPLIT_ITEM_AT_FRAME] = CapabilityGrant.GRANTED_TEST_ONLY
    for name, grant in overrides.items():
        grants[StudioCapability(name)] = grant
    return StudioCapabilityProfile(grants, ItemMarkerBasis.ITEM_START_RELATIVE)


# --- (A) file transport -------------------------------------------------------------


def _rename_xml(text: str, decisions: dict[str, str]) -> str:
    for token, word in decisions.items():
        needle = f"<name>{token} ?</name>"
        assert text.count(needle) == 1
        text = text.replace(needle, f"<name>{token} {word}</name>")
    return text


def _written(timeline: HandoffTimeline) -> str:
    text = write_xmeml(timeline).text
    assert text is not None
    return text


def file_path(
    decisions: dict[str, str] = DECISIONS,
    *,
    timeline: HandoffTimeline | None = None,
    overrides: tuple[TrackPolicyOverride, ...] = (),
) -> tuple[CandidateHandoff, ReimportedTimeline, ApplyConfirmation, AppliedTimeline]:
    handoff = attach_candidate_markers(fixture() if timeline is None else timeline, CANDIDATES)
    exported = _rename_xml(_written(handoff.timeline), decisions)
    result = read_xmeml(exported)
    assert result.timeline is not None and result.complete, result.diagnostics
    diff = diff_xmeml_roundtrip(
        handoff.timeline,
        result,
        artifact_ref=roundtrip_artifact_ref("export.xml", exported, RoundTripFormat.XMEML),
    )
    selection = read_marker_selections(result.timeline, handoff.candidates)
    confirmation = build_apply_confirmation(
        selection, handoff.timeline, diff, track_overrides=overrides
    )
    applied = apply_approved_cuts(confirmation, confirmed_digest=confirmation.confirmation_digest)
    return handoff, result.timeline, confirmation, applied


def file_verification(applied: AppliedTimeline) -> VerificationStatus:
    text = _written(applied.timeline).replace("clipitem-", "item-")
    diff = diff_xmeml_roundtrip(
        applied.timeline,
        read_xmeml(text),
        artifact_ref=roundtrip_artifact_ref("reexport.xml", text, RoundTripFormat.XMEML),
    )
    report = verify_roundtrip(
        applied.revision, applied.timeline, diff, provenance=ActualProvenance.IMMEDIATE_REEXPORT
    )
    return report.status


# --- (B) Studio transport on the fake ----------------------------------------------


class Studio:
    def __init__(
        self,
        prof: StudioCapabilityProfile | None = None,
        behavior: fr.FakeBehavior | None = None,
        timeline: HandoffTimeline | None = None,
    ) -> None:
        self.behavior = fr.FakeBehavior() if behavior is None else behavior
        self.project = fr.fake_project_from_handoff(
            fixture() if timeline is None else timeline, self.behavior
        )
        self.read_port = ResolveReadPort(self.project, profile() if prof is None else prof)
        self.mutation = ResolveMutationPort(self.project, self.read_port)

    def handoff(self, candidates: tuple[CutCandidate, ...] = CANDIDATES) -> CandidateHandoff:
        base = self.read_port.read()
        assert base.actual is not None, base.diagnostics
        handoff = attach_candidate_markers(expected_from_actual(base.actual), candidates)
        outcome = self.mutation.add_candidate_markers(handoff)
        assert outcome.status is MutationStatus.PERFORMED, outcome.detail
        assert outcome.readback is VerificationStatus.MATCH
        return handoff

    def decide(self, decisions: dict[str, str] = DECISIONS) -> None:
        for token, word in decisions.items():  # simulated marker renames in the Resolve UI
            self.project.timeline._rename_marker(token, f"{token} {word}")

    def confirm(
        self,
        handoff: CandidateHandoff,
        overrides: tuple[TrackPolicyOverride, ...] = (),
    ) -> tuple[StudioReadResult, ApplyConfirmation]:
        live = self.read_port.read()
        assert live.actual is not None, live.diagnostics
        diff = diff_studio_read(handoff.timeline, live)
        selection = read_marker_selections(live.actual, handoff.candidates)
        return live, build_apply_confirmation(
            selection, handoff.timeline, diff, track_overrides=overrides
        )


def _decisions(confirmation: ApplyConfirmation) -> tuple[object, ...]:
    return (
        tuple((c.candidate_id, c.timeline_range, c.reason) for c in confirmation.approved_cuts),
        tuple((s.candidate_id, s.reason) for s in confirmation.skipped),
    )


def _uncoloured(actual: ReimportedTimeline) -> ReimportedTimeline:
    """FCP7 xmeml carries no marker colour: normalize the live colours to UNKNOWN.

    INT-002: also restate the transport label (STUDIO_API_READ -> FILE_ROUNDTRIP) so
    the content of the two reads can be compared directly.
    """
    tracks = tuple(
        replace(
            t,
            items=tuple(
                replace(i, markers=tuple(replace(m, color=MarkerColor.UNKNOWN) for m in i.markers))
                if isinstance(i, HandoffClip)
                else i
                for i in t.items
            ),
        )
        for t in actual.tracks
    )
    return replace(actual, tracks=tracks, evidence_class="FILE_ROUNDTRIP")


def track_effects_of(confirmation: ApplyConfirmation) -> tuple[tuple[str, str, int, int], ...]:
    return tuple(
        (e.track_name, e.effect.value, e.cut_frames, e.shift_frames)
        for e in confirmation.track_effects
    )


# --- parity -------------------------------------------------------------------------


def test_file_and_studio_transports_reach_the_same_core_result() -> None:
    handoff_a, actual_a, conf_a, applied_a = file_path()
    studio = Studio()
    handoff_b = studio.handoff()
    studio.decide()
    live, conf_b = studio.confirm(handoff_b)
    assert live.consistency is CaptureConsistency.CONSISTENT
    assert live.evidence_domain == "TEST_ONLY_SUPPORT" and live.native_evidence is False
    # INT-002: the Studio read is STUDIO_API_READ end to end, the file read FILE_ROUNDTRIP
    assert live.actual is not None and live.actual.evidence_class == "STUDIO_API_READ"
    assert actual_a.evidence_class == "FILE_ROUNDTRIP"
    # identical candidate sets and identical Expected (same expected digest)
    assert candidate_sets_equal(handoff_a, handoff_b)
    assert handoff_a.timeline == handoff_b.timeline
    assert conf_a.expected_digest == conf_b.expected_digest
    # identical approved cut set and skip reasons
    assert _decisions(conf_a) == _decisions(conf_b)
    assert [c.timeline_range for c in conf_b.approved_cuts] == [
        FrameRange(100, 120),
        FrameRange(250, 262),
    ]
    assert {s.candidate_id: s.reason for s in conf_b.skipped} == {
        "AIE-0003": SkipReason.REJECTED,
        "AIE-0004": SkipReason.PENDING,
    }
    # LAYER-001: the confirmation digest binds the RESOLVED candidate status and the
    # Actual with marker colours neutralized, so both transports give ONE digest even
    # though FCP7 xmeml carries no marker colour and the live read does.
    assert live.actual is not None
    assert _uncoloured(live.actual) == actual_a
    assert conf_a.candidate_statuses == conf_b.candidate_statuses
    assert actual_binding_digest(live.actual) == actual_binding_digest(actual_a)
    assert conf_a.confirmation_digest == conf_b.confirmation_digest
    # identical per-track policy and effect (LAYER-001): dialogue cut, B-roll shifted
    assert track_effects_of(conf_a) == track_effects_of(conf_b)
    assert track_effects_of(conf_b) == (
        ("Video 1", "CUT", 32, 0),
        ("Video 2", "SHIFTED", 0, 32),
        ("Audio 1", "CUT", 32, 0),
    )
    # apply: file path -> new Expected file; Studio -> in place on the fake
    outcome = studio.mutation.apply_confirmed_cuts(
        conf_b, confirmed_digest=conf_b.confirmation_digest
    )
    assert outcome.status is MutationStatus.PERFORMED, outcome.detail
    assert outcome.readback is VerificationStatus.MATCH
    assert outcome.retried is False and outcome.native_evidence is False
    assert outcome.confirmation_digest == conf_b.confirmation_digest
    assert studio.behavior.count("Timeline.DeleteClips") == 2
    applied_b = apply_approved_cuts(conf_b, confirmed_digest=conf_b.confirmation_digest)
    assert outcome.readback_read is not None and outcome.readback_read.actual is not None
    readback = outcome.readback_read.actual
    assert cut_geometry(applied_a.timeline) == cut_geometry(applied_b.timeline)
    assert cut_geometry(applied_a.timeline) == cut_geometry(readback)
    video1, video2, audio1 = cut_geometry(readback)
    assert video2 == ("VIDEO", 2, ((268, "broll.mov", 0, 50),))  # shifted by 32, never cut
    assert video1 == (
        "VIDEO",
        1,
        (
            (0, "interview.mov", 0, 100),
            (100, "interview.mov", 120, 250),
            (230, "interview.mov", 262, 400),
        ),
    )
    assert audio1 == ("AUDIO", 1, video1[2])  # linked A/V cut at identical frames
    assert readback.name == "Interview"  # in place: the timeline is not replaced
    assert len(readback.tracks) == 3  # no track deleted, merged or flattened
    # VER-001 MATCH on both transports
    assert file_verification(applied_a) is VerificationStatus.MATCH
    assert outcome.report is not None and outcome.report.status is VerificationStatus.MATCH
    assert outcome.report.evidence_class == "STUDIO_API_READ"
    assert outcome.report.evidence_domain == "TEST_ONLY_SUPPORT"
    assert outcome.report.native_evidence is False


def test_mid_item_cut_without_split_is_unsupported_and_never_rebuilt() -> None:
    decisions = {"AIE-0003": "OK"}
    studio = Studio()
    handoff = studio.handoff()
    studio.decide(decisions)
    before, confirmation = studio.confirm(handoff)
    assert [c.timeline_range for c in confirmation.approved_cuts] == [FrameRange(30, 40)]
    outcome = studio.mutation.apply_confirmed_cuts(
        confirmation, confirmed_digest=confirmation.confirmation_digest
    )
    assert outcome.status is MutationStatus.UNSUPPORTED
    assert outcome.issue is PortIssueKind.UNSUPPORTED
    assert outcome.fallback is Fallback.FILE_PATH
    assert "SPLIT_ITEM_AT_FRAME NOT_AVAILABLE" in outcome.detail
    assert outcome.readback is VerificationStatus.UNVERIFIED and not outcome.mutated
    assert studio.behavior.count("Timeline.DeleteClips") == 0
    after = studio.read_port.read()
    assert after.actual == before.actual  # untouched
    # the documented fallback (file path) still produces the cut
    _, _, conf_a, applied_a = file_path(decisions)
    assert [c.timeline_range for c in conf_a.approved_cuts] == [FrameRange(30, 40)]
    assert applied_a.timeline.duration == fixture().duration - 10


def test_split_capability_flag_reaches_file_path_geometry() -> None:
    decisions = {"AIE-0001": "OK", "AIE-0003": "OK"}
    studio = Studio(profile(split=True), fr.FakeBehavior(split_enabled=True))
    handoff = studio.handoff()
    studio.decide(decisions)
    _, confirmation = studio.confirm(handoff)
    outcome = studio.mutation.apply_confirmed_cuts(
        confirmation, confirmed_digest=confirmation.confirmation_digest
    )
    assert outcome.status is MutationStatus.PERFORMED, outcome.detail
    assert outcome.readback is VerificationStatus.MATCH
    _, _, _, applied_a = file_path(decisions)
    assert outcome.readback_read is not None and outcome.readback_read.actual is not None
    assert cut_geometry(outcome.readback_read.actual) == cut_geometry(applied_a.timeline)


def test_absent_or_unknown_ripple_capability_refuses_before_any_call() -> None:
    for grant, status in (
        (CapabilityGrant.ABSENT, MutationStatus.UNSUPPORTED),
        (CapabilityGrant.UNKNOWN, MutationStatus.REFUSED),
    ):
        studio = Studio(profile(DELETE_ITEMS_RIPPLE=grant))
        handoff = studio.handoff()
        studio.decide()
        _, confirmation = studio.confirm(handoff)
        outcome = studio.mutation.apply_confirmed_cuts(
            confirmation, confirmed_digest=confirmation.confirmation_digest
        )
        assert outcome.status is status and outcome.fallback is Fallback.FILE_PATH
        assert studio.behavior.count("Timeline.DeleteClips") == 0


# --- reads: None / unstable / unavailable -> UNVERIFIED -----------------------------


@pytest.mark.parametrize(
    ("behavior", "code", "consistency"),
    [
        (
            fr.FakeBehavior(none_methods={"TimelineItem.GetLeftOffset"}),
            StudioDiagnosticCode.NULL_VALUE,
            CaptureConsistency.UNVERIFIED,
        ),
        (
            fr.FakeBehavior(missing_methods={"TimelineItem.GetEnd"}),
            StudioDiagnosticCode.METHOD_UNAVAILABLE,
            CaptureConsistency.UNVERIFIED,
        ),
        (
            fr.FakeBehavior(unstable_methods={"TimelineItem.GetStart"}),
            StudioDiagnosticCode.UNSTABLE_READ,
            CaptureConsistency.UNSTABLE,
        ),
        (
            fr.FakeBehavior(inclusive_item_end=True),
            StudioDiagnosticCode.END_FRAME_INCONSISTENT,
            CaptureConsistency.UNVERIFIED,
        ),
        (
            fr.FakeBehavior(no_current_timeline=True),
            StudioDiagnosticCode.NO_CURRENT_TIMELINE,
            CaptureConsistency.UNVERIFIED,
        ),
    ],
)
def test_bad_reads_are_never_an_actual(
    behavior: fr.FakeBehavior, code: StudioDiagnosticCode, consistency: CaptureConsistency
) -> None:
    studio = Studio(behavior=behavior)
    result = studio.read_port.read()
    assert result.consistency is consistency and result.actual is None
    assert code in {d.code for d in result.diagnostics}
    expected = expected_from_actual(fr_actual())
    report = verify_roundtrip(
        _revision(expected),
        expected,
        diff_studio_read(expected, result),
        provenance=ActualProvenance.IMMEDIATE_REEXPORT,
    )
    assert report.status is VerificationStatus.UNVERIFIED


def fr_actual() -> ReimportedTimeline:
    timeline = fixture()
    return ReimportedTimeline(timeline.name, timeline.rate, timeline.start_frame, timeline.tracks)


def _revision(expected: HandoffTimeline) -> PreparedArtifactRevision:
    return artifact_revision("test", expected.name, expected)


def test_marker_basis_and_documented_profile_stay_unverified() -> None:
    no_basis = StudioCapabilityProfile(profile().grants, ItemMarkerBasis.UNKNOWN)
    result = Studio(no_basis).read_port.read()
    assert result.consistency is CaptureConsistency.UNVERIFIED
    assert StudioDiagnosticCode.MARKER_BASIS_UNKNOWN in {d.code for d in result.diagnostics}
    documented = Studio(documented_profile()).read_port.read()
    assert documented.consistency is CaptureConsistency.UNVERIFIED
    assert documented.diagnostics[0].code is StudioDiagnosticCode.CAPABILITY_UNKNOWN


def test_unstable_live_read_refuses_mutation_without_calls() -> None:
    studio = Studio()
    handoff = studio.handoff()
    studio.decide()
    _, confirmation = studio.confirm(handoff)
    studio.behavior.unstable_methods.add("TimelineItem.GetStart")
    outcome = studio.mutation.apply_confirmed_cuts(
        confirmation, confirmed_digest=confirmation.confirmation_digest
    )
    assert outcome.status is MutationStatus.REFUSED and outcome.issue is PortIssueKind.UNKNOWN
    assert outcome.readback is VerificationStatus.UNVERIFIED
    assert studio.behavior.count("Timeline.DeleteClips") == 0


# --- approval binding ---------------------------------------------------------------


def test_wrong_digest_and_foreign_confirmation_are_refused() -> None:
    studio = Studio()
    handoff = studio.handoff()
    studio.decide()
    _, confirmation = studio.confirm(handoff)
    with pytest.raises(ApplyRefused):
        studio.mutation.apply_confirmed_cuts(confirmation, confirmed_digest="0" * 64)
    _, _, conf_file, _ = file_path()
    # LAYER-001: same decision on the same content -> one transport-neutral digest ...
    assert conf_file.confirmation_digest == confirmation.confirmation_digest
    assert conf_file.actual_digest != confirmation.actual_digest
    # ... but a file-path confirmation (another Actual) still cannot drive the live timeline
    outcome = studio.mutation.apply_confirmed_cuts(
        conf_file, confirmed_digest=conf_file.confirmation_digest
    )
    assert outcome.status is MutationStatus.REFUSED and outcome.issue is PortIssueKind.STALE
    assert studio.behavior.count("Timeline.DeleteClips") == 0


def test_stale_marker_handoff_is_refused() -> None:
    studio = Studio()
    handoff = studio.handoff()
    outcome = studio.mutation.add_candidate_markers(handoff)  # markers already present
    assert outcome.status is MutationStatus.REFUSED and outcome.issue is PortIssueKind.STALE
    assert studio.behavior.count("TimelineItem.AddMarker") == len(CANDIDATES)


# --- post-mutation verification, no retry -------------------------------------------


def test_post_mutation_mismatch_is_reported_without_retry() -> None:
    # the fake ripples one frame short: a 1-frame gap the Expected does not have
    studio = Studio(behavior=fr.FakeBehavior(ripple_extra_shift=-1))
    handoff = studio.handoff()
    studio.decide()
    _, confirmation = studio.confirm(handoff)
    outcome = studio.mutation.apply_confirmed_cuts(
        confirmation, confirmed_digest=confirmation.confirmation_digest
    )
    assert outcome.status is MutationStatus.PERFORMED
    assert outcome.readback is VerificationStatus.MISMATCH
    assert studio.behavior.count("Timeline.DeleteClips") == 2  # one per cut, no retry


def test_failed_delete_stops_without_retry() -> None:
    studio = Studio()
    handoff = studio.handoff()
    studio.decide()
    _, confirmation = studio.confirm(handoff)
    studio.behavior.delete_clips_result = False  # e.g. UI not on the Edit page
    outcome = studio.mutation.apply_confirmed_cuts(
        confirmation, confirmed_digest=confirmation.confirmation_digest
    )
    assert outcome.status is MutationStatus.FAILED and outcome.retried is False
    assert outcome.readback is not VerificationStatus.MATCH
    assert studio.behavior.count("Timeline.DeleteClips") == 1
    assert "not retried" in outcome.detail


# --- HARD_LOCK and per-track policy ---------------------------------------------------


def test_hard_lock_from_a_human_edit_is_respected() -> None:
    studio = Studio()
    handoff = studio.handoff()
    studio.decide()
    pause = studio.project.timeline._item("video", 1, 1)  # P1, carries AIE-0001
    pause._markers[2.0] = {
        "color": "Blue",
        "duration": 1.0,
        "note": "keep",
        "name": "editor note",
        "customData": "",
    }
    _, confirmation = studio.confirm(handoff)
    assert {s.candidate_id: s.reason for s in confirmation.skipped}["AIE-0001"] is (
        SkipReason.HUMAN_EDIT_LOCKED
    )
    assert [c.candidate_id for c in confirmation.approved_cuts] == ["AIE-0002"]
    outcome = studio.mutation.apply_confirmed_cuts(
        confirmation, confirmed_digest=confirmation.confirmation_digest
    )
    assert outcome.readback is VerificationStatus.MATCH
    assert outcome.readback_read is not None and outcome.readback_read.actual is not None
    video1 = cut_geometry(outcome.readback_read.actual)[0]
    assert (100, "interview.mov", 100, 120) in video1[2]  # the locked pause survives


def test_per_track_policies_come_from_the_confirmation() -> None:
    """INT-002: the in-place path applies the confirmed LAYER-001 policies only."""
    overrides = (TrackPolicyOverride("Video 2", TrackCutPolicy.KEEP_IN_PLACE),)
    studio = Studio()
    handoff = studio.handoff()
    studio.decide()
    _, keep_conf = studio.confirm(handoff, overrides)
    assert {a.track_name: a.policy for a in keep_conf.approved_cuts[0].track_policies} == {
        "Video 1": TrackCutPolicy.CUT_WITH_SOURCE,
        "Video 2": TrackCutPolicy.KEEP_IN_PLACE,
        "Audio 1": TrackCutPolicy.CUT_WITH_SOURCE,
    }
    keep = studio.mutation.apply_confirmed_cuts(
        keep_conf, confirmed_digest=keep_conf.confirmation_digest
    )
    # KEEP_IN_PLACE stays UNSUPPORTED in place (no track-selective ripple, STUDIO-T0)
    assert keep.status is MutationStatus.UNSUPPORTED and "TRACK_SELECTIVE_RIPPLE" in keep.detail
    assert keep.fallback is Fallback.FILE_PATH and not keep.mutated
    assert studio.behavior.count("Timeline.DeleteClips") == 0
    # the file path expresses the same confirmed KEEP (same digest), B-roll untouched
    _, _, conf_file, applied_file = file_path(overrides=overrides)
    assert conf_file.confirmation_digest == keep_conf.confirmation_digest
    assert cut_geometry(applied_file.timeline)[1] == ("VIDEO", 2, ((300, "broll.mov", 0, 50),))
    assert any(w.code.value == "SYNC_SHIFT" for w in conf_file.layer_warnings)
    # SHIFT_WITH_RIPPLE (the default for V2) is applied in place by the span ripple
    _, shift_conf = studio.confirm(handoff)
    shifted = studio.mutation.apply_confirmed_cuts(
        shift_conf, confirmed_digest=shift_conf.confirmation_digest
    )
    assert shifted.status is MutationStatus.PERFORMED
    assert shifted.readback is VerificationStatus.MATCH
    assert shifted.readback_read is not None and shifted.readback_read.actual is not None
    broll = cut_geometry(shifted.readback_read.actual)[1]
    assert broll == ("VIDEO", 2, ((268, "broll.mov", 0, 50),))  # moved by 32, never cut


def test_planner_refuses_unknown_policy_and_shift_conflict_defensively() -> None:
    """A confirmation never approves these; the in-place planner re-checks anyway."""
    studio = Studio()
    handoff = studio.handoff()
    studio.decide()
    live, confirmation = studio.confirm(handoff)
    assert live.actual is not None
    cut = confirmation.approved_cuts[0]
    unknown = replace(cut, track_policies=cut.track_policies[:1])
    _, reasons = studio.mutation.plan_cuts_in_place(live.actual, (unknown,))
    assert any("policy UNKNOWN" in r for r in reasons)
    shift_v1 = replace(
        cut,
        track_policies=tuple(
            replace(a, policy=TrackCutPolicy.SHIFT_WITH_RIPPLE) for a in cut.track_policies
        ),
    )
    _, reasons = studio.mutation.plan_cuts_in_place(live.actual, (shift_v1,))
    assert any("LAYER_CONFLICT" in r for r in reasons)


# --- marker removal ------------------------------------------------------------------


def test_remove_candidate_markers_verifies_by_read_back() -> None:
    studio = Studio()
    studio.handoff()
    outcome = studio.mutation.remove_candidate_markers(["AIE-0003", "AIE-0004"])
    assert outcome.status is MutationStatus.PERFORMED
    assert outcome.readback is VerificationStatus.MATCH
    assert outcome.readback_read is not None and outcome.readback_read.actual is not None
    names = {
        m.name
        for t in outcome.readback_read.actual.tracks
        for i in t.items
        if isinstance(i, HandoffClip)
        for m in i.markers
    }
    assert names == {"AIE-0001 ?", "AIE-0002 ?"}


# --- capability matrix and transport hygiene ----------------------------------------


def test_capability_matrix_answers_the_in_place_question() -> None:
    def status(capability: StudioCapability) -> CapabilityStatus:
        return capability_entry(capability).status

    assert status(StudioCapability.SPLIT_ITEM_AT_FRAME) is CapabilityStatus.NOT_AVAILABLE
    assert status(StudioCapability.TRIM_ITEM) is CapabilityStatus.NOT_AVAILABLE
    assert status(StudioCapability.DELETE_SUBRANGE_RIPPLE) is CapabilityStatus.NOT_AVAILABLE
    assert status(StudioCapability.TRACK_SELECTIVE_RIPPLE) is CapabilityStatus.NOT_AVAILABLE
    assert status(StudioCapability.DELETE_ITEMS_RIPPLE) is CapabilityStatus.DOCUMENTED_CLAIM
    assert status(StudioCapability.RIPPLE_SPAN_SEMANTICS) is CapabilityStatus.UNVERIFIED
    assert status(StudioCapability.TRACK_LOCK_EXCLUDES_RIPPLE) is CapabilityStatus.UNVERIFIED
    assert status(StudioCapability.ITEM_MARKER_FRAME_BASIS) is CapabilityStatus.UNVERIFIED
    assert status(StudioCapability.HASATTR_DETECTION) is CapabilityStatus.NOT_AVAILABLE
    for entry in STUDIO_CAPABILITY_MATRIX:
        assert entry.sources
        if entry.area.value == "CUT_REBUILD":
            assert entry.used_by_transport is False
    granted = documented_profile().grants.values()
    assert CapabilityGrant.GRANTED_TEST_ONLY not in granted


def test_transport_allowlist_has_no_rebuild_track_or_native_calls() -> None:
    names = {m for methods in (*READ_METHODS.values(), *MUTATION_METHODS.values()) for m in methods}
    forbidden = {
        "AppendToTimeline",
        "CreateTimelineFromClips",
        "DeleteTrack",
        "SetTrackLock",
        "ImportTimelineFromFile",
        "CreateEmptyTimeline",
    }
    assert not names & forbidden
    source = (
        Path(__file__).resolve().parents[1] / "src" / "davinci_ai_editor" / "studio_transport.py"
    ).read_text(encoding="utf-8")
    assert "hasattr(" not in source
    assert "import DaVinciResolveScript" not in source


# --- INT-002: parity against the LAYER-001 apply semantics (music bed) ---------------

MUSIC = HandoffMediaRef("music.wav", "C:/media/music.wav", FrameRange(0, 1000), 0)


def music_fixture() -> HandoffTimeline:
    base = fixture()
    music = HandoffTrack(
        "Audio 2", HandoffTrackKind.AUDIO, (HandoffClip("Music", MUSIC, FrameRange(0, 400)),)
    )
    return replace(base, tracks=(*base.tracks, music))


MUSIC_CUT = (TrackPolicyOverride("Audio 2", TrackCutPolicy.CUT_WITH_SOURCE),)


def test_music_bed_conflicts_identically_on_both_transports() -> None:
    _, _, conf_a, _ = file_path(timeline=music_fixture())
    studio = Studio(timeline=music_fixture())
    handoff = studio.handoff()
    studio.decide()
    _, conf_b = studio.confirm(handoff)
    assert conf_a.confirmation_digest == conf_b.confirmation_digest
    assert not conf_b.approved_cuts
    reasons = {s.candidate_id: s.reason for s in conf_b.skipped}
    assert reasons["AIE-0001"] is SkipReason.LAYER_CONFLICT
    assert reasons["AIE-0002"] is SkipReason.LAYER_CONFLICT
    assert [e.effect.value for e in conf_b.track_effects][3] == "CONFLICT"


def test_music_override_parity_import_tier_and_test_only_split(tmp_path: Path) -> None:
    _, _, conf_a, applied_a = file_path(timeline=music_fixture(), overrides=MUSIC_CUT)
    assert [e.effect.value for e in conf_a.track_effects] == ["CUT", "SHIFTED", "CUT", "CUT"]
    assert file_verification(applied_a) is VerificationStatus.MATCH
    # in place without a split API: the music item spans the cut -> UNSUPPORTED (file path)
    studio = Studio(timeline=music_fixture())
    handoff = studio.handoff()
    studio.decide()
    _, conf_b = studio.confirm(handoff, MUSIC_CUT)
    assert conf_b.confirmation_digest == conf_a.confirmation_digest
    no_split = studio.mutation.apply_confirmed_cuts(
        conf_b, confirmed_digest=conf_b.confirmation_digest
    )
    assert no_split.status is MutationStatus.UNSUPPORTED and "Audio 2@100" in no_split.detail
    # tier 1 (import a new version) carries the same LAYER-001 Expected
    port = TieredApplyPort(studio.project, studio.read_port, work_dir=tmp_path)
    plan = port.plan(conf_b)
    assert plan.status is PlanStatus.READY and plan.tier is ApplyTier.TIER_1_IMPORT_NEW_VERSION
    outcome = port.execute(
        plan,
        conf_b,
        confirmed_digest=conf_b.confirmation_digest,
        confirmed_plan_digest=plan.plan_digest,
    )
    assert outcome.status is MutationStatus.PERFORMED, outcome.detail
    assert outcome.readback is VerificationStatus.MATCH
    assert outcome.readback_read is not None and outcome.readback_read.actual is not None
    assert cut_geometry(outcome.readback_read.actual) == cut_geometry(applied_a.timeline)
    # the test-only split flag reaches the same geometry in place
    split = Studio(profile(split=True), fr.FakeBehavior(split_enabled=True), music_fixture())
    handoff_s = split.handoff()
    split.decide()
    _, conf_s = split.confirm(handoff_s, MUSIC_CUT)
    in_place = split.mutation.apply_confirmed_cuts(
        conf_s, confirmed_digest=conf_s.confirmation_digest
    )
    assert in_place.status is MutationStatus.PERFORMED, in_place.detail
    assert in_place.readback is VerificationStatus.MATCH
    assert in_place.report is not None and in_place.report.evidence_class == "STUDIO_API_READ"
    assert in_place.readback_read is not None and in_place.readback_read.actual is not None
    geometry = cut_geometry(in_place.readback_read.actual)
    assert geometry == cut_geometry(applied_a.timeline)
    assert geometry[3] == (
        "AUDIO",
        2,
        ((0, "music.wav", 0, 100), (100, "music.wav", 120, 250), (230, "music.wav", 262, 400)),
    )
