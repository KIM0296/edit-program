"""STUDIO-T1: four-tier Studio apply on the FAKE Resolve graph (TEST_ONLY_SUPPORT).

Same shared fixture as STUDIO-T0 (``test_studio_parity``): an interview pre-cut
at its pauses on V1 + linked A1 and a B-roll layer on V2, start 86400 at 25 fps.
AIE-0001 / AIE-0002 sit on whole pause items (aligned); AIE-0003 (filler,
[30, 40)) falls inside clip A (mid-item). No Resolve, no media, no rendering.
"""

from dataclasses import replace
from pathlib import Path

import pytest
from support import fake_resolve as fr
from test_studio_parity import Studio, file_path, fixture, profile

from davinci_ai_editor.apply_cuts import ApplyConfirmation, ApplyRefused
from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.handoff_model import HandoffClip, HandoffTimeline
from davinci_ai_editor.layer_policy import TrackPolicyOverride
from davinci_ai_editor.native_snapshot import CaptureConsistency
from davinci_ai_editor.roundtrip_diff import timeline_digest
from davinci_ai_editor.roundtrip_verification import VerificationStatus
from davinci_ai_editor.runtime_ports import PortIssueKind
from davinci_ai_editor.studio_apply_planner import (
    ApplyTier,
    GradeState,
    PlanStatus,
    StudioApplyPlan,
    UserAction,
    UserChoice,
)
from davinci_ai_editor.studio_capabilities import (
    CapabilityGrant,
    CapabilityStatus,
    StudioCapability,
    StudioCapabilityProfile,
    capability_entry,
    documented_profile,
)
from davinci_ai_editor.studio_razor import (
    SplitChangeKind,
    classify_split_change,
    timecode_for_frame,
)
from davinci_ai_editor.studio_tiered_apply import (
    TIERED_MUTATION_METHODS,
    TIERED_READ_METHODS,
    TieredApplyOutcome,
    TieredApplyPort,
)
from davinci_ai_editor.studio_transport import (
    MutationStatus,
    StudioEvidence,
    TrackCutPolicy,
    cut_geometry,
    studio_verification,
)
from davinci_ai_editor.temporal_mapping import FrameRate

MID = {"AIE-0001": "OK", "AIE-0003": "OK"}  # one aligned cut + one mid-item cut
G = CapabilityGrant
C = StudioCapability
IMPORT = "MediaPool.ImportTimelineFromFile"


def t1_profile(**overrides: CapabilityGrant) -> StudioCapabilityProfile:
    base = profile()
    grants = dict(base.grants)
    for name, grant in overrides.items():
        grants[StudioCapability(name)] = grant
    return StudioCapabilityProfile(grants, base.item_marker_basis)


class T1:
    def __init__(
        self,
        work: Path,
        prof: StudioCapabilityProfile | None = None,
        behavior: fr.FakeBehavior | None = None,
        timeline: HandoffTimeline | None = None,
    ) -> None:
        self.studio = Studio(t1_profile() if prof is None else prof, behavior, timeline)
        self.port = TieredApplyPort(self.studio.project, self.studio.read_port, work_dir=work)

    @property
    def behavior(self) -> fr.FakeBehavior:
        return self.studio.behavior

    @property
    def project(self) -> fr.FakeProject:
        return self.studio.project

    def confirm(
        self,
        decisions: dict[str, str],
        overrides: tuple[TrackPolicyOverride, ...] = (),
    ) -> ApplyConfirmation:
        handoff = self.studio.handoff()
        self.studio.decide(decisions)
        _, confirmation = self.studio.confirm(handoff, overrides)
        return confirmation

    def grade_clip_a(self, *, comp: bool = True, versions: int = 1) -> None:
        item = self.project.timeline._item("video", 1, 0)  # clip A [0, 100)
        names = tuple(f"Version {n}" for n in range(1, versions + 1))
        item._grade = replace(fr.GRADED, versions=names)
        if comp:
            item._comps = {"Comp 1": "MediaIn1 -> Blur1 -> MediaOut1"}

    def execute(self, plan: StudioApplyPlan, confirmation: ApplyConfirmation) -> TieredApplyOutcome:
        return self.port.execute(
            plan,
            confirmation,
            confirmed_digest=confirmation.confirmation_digest,
            confirmed_plan_digest=plan.plan_digest,
        )


# --- tier selection --------------------------------------------------------------------


def test_all_aligned_cuts_choose_tier_3_in_place(tmp_path: Path) -> None:
    t1 = T1(tmp_path)
    confirmation = t1.confirm({"AIE-0001": "OK", "AIE-0002": "OK"})
    plan = t1.port.plan(confirmation)
    assert plan.status is PlanStatus.READY
    assert plan.tier is ApplyTier.TIER_3_DELETE_ALIGNED_IN_PLACE
    assert plan.user_action is UserAction.CONFIRM_ON_EDIT_PAGE
    assert all(c.aligned for c in plan.cuts) and plan.new_timeline_name is None
    outcome = t1.execute(plan, confirmation)
    assert outcome.status is MutationStatus.PERFORMED, outcome.detail
    assert outcome.readback is VerificationStatus.MATCH
    assert outcome.layers is VerificationStatus.MATCH
    assert t1.behavior.count("Timeline.DeleteClips") == 2 and t1.behavior.count(IMPORT) == 0


def test_mid_item_cut_ungraded_is_tier_1_confirm_only_and_matches_file_path(
    tmp_path: Path,
) -> None:
    t1 = T1(tmp_path)
    confirmation = t1.confirm(MID)
    plan = t1.port.plan(confirmation)
    assert plan.grade_state is GradeState.UNGRADED
    assert plan.tier is ApplyTier.TIER_1_IMPORT_NEW_VERSION
    assert plan.user_action is UserAction.CONFIRM_ONLY and plan.confirm_only_promised
    assert [c.aligned for c in plan.cuts] == [False, True]  # [30,40) mid-item, [100,120) whole
    assert plan.new_timeline_name == "Interview AIE v2"
    assert plan.backup_timeline_name == "Interview"
    assert "[확인] 버튼만 누르세요" in plan.summary
    outcome = t1.execute(plan, confirmation)
    assert outcome.status is MutationStatus.PERFORMED, outcome.detail
    assert outcome.geometry is VerificationStatus.MATCH
    assert outcome.layers is VerificationStatus.MATCH
    assert outcome.readback is VerificationStatus.MATCH
    assert outcome.current_timeline_switched and outcome.grades is None
    assert outcome.format_losses == ("MARKER_COLOR", "MARKER_CUSTOM_DATA")
    assert t1.behavior.count(IMPORT) == 1 and t1.behavior.count("Timeline.DeleteClips") == 0
    # the same core result as the file path (APPLY-001 Expected), imported inside Resolve
    _, _, _, applied_file = file_path(MID)
    assert outcome.readback_read is not None and outcome.readback_read.actual is not None
    new_actual = outcome.readback_read.actual
    assert cut_geometry(new_actual) == cut_geometry(applied_file.timeline)
    assert new_actual.name == "Interview AIE v2" and len(new_actual.tracks) == 3
    # the original is the untouched backup; the new version is now current
    original = t1.studio.read_port.read(t1.project.timeline)
    assert original.actual is not None
    assert timeline_digest(original.actual) == confirmation.actual_digest
    assert t1.project.current is not None and t1.project.current._name == "Interview AIE v2"


def test_unknown_grade_state_needs_user_choice_never_tier_1(tmp_path: Path) -> None:
    t1 = T1(tmp_path, t1_profile(GRADE_ABSENCE_INFERENCE=G.UNKNOWN))
    confirmation = t1.confirm(MID)
    plan = t1.port.plan(confirmation)
    assert plan.grade_state is GradeState.UNKNOWN
    assert plan.status is PlanStatus.NEEDS_USER_CHOICE and plan.tier is ApplyTier.UNKNOWN
    assert plan.options == (UserChoice.ACCEPT_GRADE_LOSS, UserChoice.USE_RAZOR_ASSIST)
    assert plan.user_action is UserAction.CHOOSE_OPTION and not plan.confirm_only_promised
    assert "ACCEPT_GRADE_LOSS" in plan.summary and "USE_RAZOR_ASSIST" in plan.summary
    refused = t1.execute(plan, confirmation)
    assert refused.status is MutationStatus.REFUSED and not refused.mutated
    assert t1.behavior.count(IMPORT) == 0
    loss = t1.port.plan(confirmation, user_choice=UserChoice.ACCEPT_GRADE_LOSS)
    assert loss.tier is ApplyTier.TIER_1_IMPORT_NEW_VERSION
    razor = t1.port.plan(confirmation, user_choice=UserChoice.USE_RAZOR_ASSIST)
    assert razor.tier is ApplyTier.TIER_4_RAZOR_ASSIST
    # an unreadable grade graph is UNKNOWN as well (never UNGRADED)
    blind = T1(tmp_path, t1_profile(READ_GRADE_GRAPH=G.UNKNOWN))
    assert blind.port.read_grade_state().state is GradeState.UNKNOWN


def test_graded_and_transferable_is_tier_2_with_per_item_match(tmp_path: Path) -> None:
    t1 = T1(tmp_path)
    t1.grade_clip_a()
    confirmation = t1.confirm(MID)
    plan = t1.port.plan(confirmation)
    assert plan.grade_state is GradeState.GRADED
    assert plan.tier is ApplyTier.TIER_2_IMPORT_WITH_GRADE_TRANSFER
    assert plan.user_action is UserAction.CONFIRM_THEN_REVIEW_GRADES
    assert not plan.confirm_only_promised  # customer-safe: confirm-only is tier 1 only
    assert plan.transfer_items == ("Video 1@0",)
    outcome = t1.execute(plan, confirmation)
    assert outcome.status is MutationStatus.PERFORMED, outcome.detail
    assert outcome.grades is not None
    assert outcome.grades.structure is VerificationStatus.MATCH
    assert outcome.grades.values is VerificationStatus.UNVERIFIED  # keyframes / values unproven
    [item] = outcome.grades.items
    assert item.original == "Video 1@0" and item.targets == ("Video 1@0", "Video 1@30")
    assert outcome.readback is VerificationStatus.MATCH
    assert t1.behavior.count("TimelineItem.CopyGrades") == 1
    assert t1.behavior.count("TimelineItem.ExportFusionComp") == 1
    assert t1.behavior.count("TimelineItem.ImportFusionComp") == 2


def test_partial_grade_transfer_is_mismatch_listing_items(tmp_path: Path) -> None:
    t1 = T1(tmp_path, behavior=fr.FakeBehavior(copy_grades_partial=True))
    t1.grade_clip_a(comp=False)
    confirmation = t1.confirm(MID)
    plan = t1.port.plan(confirmation)
    assert plan.tier is ApplyTier.TIER_2_IMPORT_WITH_GRADE_TRANSFER
    outcome = t1.execute(plan, confirmation)
    assert outcome.status is MutationStatus.PERFORMED
    assert outcome.grades is not None and outcome.grades.structure is VerificationStatus.MISMATCH
    assert outcome.grades.mismatched == ("Video 1@0",)
    assert "Video 1@30" in outcome.grades.items[0].detail
    assert outcome.readback is VerificationStatus.MISMATCH
    assert not outcome.current_timeline_switched  # a broken version is not opened
    assert t1.behavior.count("TimelineItem.CopyGrades") == 1  # no retry


def test_graded_but_untransferable_falls_back_to_tier_4(tmp_path: Path) -> None:
    t1 = T1(tmp_path)
    t1.grade_clip_a(versions=2)  # other colour versions cannot be copied
    confirmation = t1.confirm(MID)
    plan = t1.port.plan(confirmation)
    assert plan.tier is ApplyTier.TIER_4_RAZOR_ASSIST
    assert plan.user_action is UserAction.RAZOR_THEN_CONFIRM
    assert any("GRADE_COPY_VERSIONS NOT_AVAILABLE" in r for r in plan.reasons)
    assert [(s.timecode, s.tracks) for s in plan.razor_steps] == [
        ("00:57:37:05", ("Audio 1", "Video 1")),
        ("00:57:37:15", ("Audio 1", "Video 1")),
    ]
    assert "00:57:37:05" in plan.summary
    # no razor capability either: the user may still accept grade loss (tier 1)
    t1b = T1(tmp_path, t1_profile(PLAYHEAD_SET_TIMECODE=G.UNKNOWN))
    t1b.grade_clip_a(versions=2)
    choice = t1b.port.plan(t1b.confirm(MID))
    assert choice.status is PlanStatus.NEEDS_USER_CHOICE
    assert choice.options == (UserChoice.ACCEPT_GRADE_LOSS,)


# --- tier 4: razor assist ---------------------------------------------------------------


def _razor_plan(t1: T1) -> tuple[ApplyConfirmation, StudioApplyPlan]:
    confirmation = t1.confirm(MID)
    plan = t1.port.plan(confirmation, user_choice=UserChoice.USE_RAZOR_ASSIST)
    assert plan.tier is ApplyTier.TIER_4_RAZOR_ASSIST
    return confirmation, plan


def _blade_listed(t1: T1, plan: StudioApplyPlan) -> None:
    for step in plan.razor_steps:
        moved = t1.port.razor_goto(plan, step.index)
        assert moved.status is MutationStatus.PERFORMED
        assert moved.readback is VerificationStatus.MATCH
        for track in step.tracks:
            label, index = track.split(" ")
            assert t1.project.timeline._blade(label.lower(), int(index))


def test_razor_assist_neutral_split_then_tier_3_delete(tmp_path: Path) -> None:
    t1 = T1(tmp_path)
    t1.grade_clip_a(comp=False)
    confirmation, plan = _razor_plan(t1)
    _blade_listed(t1, plan)
    outcome = t1.execute(plan, confirmation)
    assert outcome.split is not None and outcome.split.kind is SplitChangeKind.NEUTRAL_SPLIT
    assert outcome.split.hard_lock is False  # not a human edit
    assert outcome.status is MutationStatus.PERFORMED, outcome.detail
    assert outcome.readback is VerificationStatus.MATCH
    assert t1.behavior.count("Timeline.DeleteClips") == 2 and t1.behavior.count(IMPORT) == 0
    _, _, _, applied_file = file_path(MID)
    assert outcome.readback_read is not None and outcome.readback_read.actual is not None
    assert cut_geometry(outcome.readback_read.actual) == cut_geometry(applied_file.timeline)
    # in place: the graded items survive with their grade
    for item in t1.project.timeline._tracks["video"][0][:2]:
        assert item._grade.layers == fr.GRADED.layers


def test_razor_assist_human_edit_or_incomplete_is_refused(tmp_path: Path) -> None:
    t1 = T1(tmp_path)
    confirmation, plan = _razor_plan(t1)
    t1.port.razor_goto(plan, 1)
    assert t1.project.timeline._blade("video", 1)  # V1 only: A1 still whole
    incomplete = t1.execute(plan, confirmation)
    assert incomplete.status is MutationStatus.REFUSED and not incomplete.mutated
    assert incomplete.split is not None
    assert incomplete.split.kind is SplitChangeKind.INCOMPLETE_SPLIT
    assert ("Audio 1", 30) in incomplete.split.missing
    # a blade at an unlisted frame is a real human edit (HARD_LOCK path), never applied
    t1.project.timeline._playhead = 86400 + 60
    assert t1.project.timeline._blade("audio", 1)
    human = t1.execute(plan, confirmation)
    assert human.split is not None and human.split.kind is SplitChangeKind.HUMAN_EDIT
    assert human.split.hard_lock is True and human.status is MutationStatus.REFUSED
    assert "unlisted frame" in human.detail
    assert t1.behavior.count("Timeline.DeleteClips") == 0


def test_razor_playhead_readback_mismatch_is_reported(tmp_path: Path) -> None:
    t1 = T1(tmp_path, behavior=fr.FakeBehavior(playhead_offset=1))
    _, plan = _razor_plan(t1)
    moved = t1.port.razor_goto(plan, 1)
    assert moved.status is MutationStatus.PERFORMED
    assert moved.readback is VerificationStatus.MISMATCH
    assert t1.behavior.count("Timeline.SetCurrentTimecode") == 1  # no retry


def test_neutral_split_classifier_is_pure_and_strict() -> None:
    timeline = fixture()
    before = Studio(timeline=timeline).read_port.read().actual
    assert before is not None
    planned = {"Video 1": frozenset({30})}
    assert classify_split_change(before, before, {}).kind is SplitChangeKind.NO_CHANGE
    assert classify_split_change(before, before, planned).kind is (SplitChangeKind.INCOMPLETE_SPLIT)
    split = Studio(timeline=timeline)
    split.project.timeline._playhead = 86400 + 30
    split.project.timeline._blade("video", 1)
    after = split.read_port.read().actual
    assert after is not None
    assert classify_split_change(before, after, planned).kind is SplitChangeKind.NEUTRAL_SPLIT
    assert classify_split_change(before, after, {}).kind is SplitChangeKind.HUMAN_EDIT
    assert timecode_for_frame(86430, FrameRate(25, 1)) == "00:57:37:05"
    assert timecode_for_frame(86430, FrameRate(30000, 1001)) is None  # drop-frame unknown


# --- tier 1 import quirks and layers ---------------------------------------------------


def test_name_collision_is_refused_before_any_import(tmp_path: Path) -> None:
    t1 = T1(tmp_path)
    confirmation = t1.confirm(MID)
    plan = t1.port.plan(confirmation)
    assert plan.new_timeline_name == "Interview AIE v2"
    clash = t1.project._build(replace(fixture(), name="Interview AIE v2"))
    t1.project._timelines.append(clash)
    outcome = t1.execute(plan, confirmation)
    assert outcome.status is MutationStatus.REFUSED and outcome.issue is PortIssueKind.CONFLICT
    assert "NAME_COLLISION" in outcome.detail and not outcome.mutated
    assert t1.behavior.count(IMPORT) == 0
    # planning again picks the next free version name
    assert t1.port.plan(confirmation).new_timeline_name == "Interview AIE v3"


@pytest.mark.parametrize(
    ("behavior", "needle"),
    [
        (fr.FakeBehavior(import_returns_existing=True), "IMPORT_RETURNED_EXISTING"),
        (fr.FakeBehavior(import_result_none=True), "returned None"),
    ],
)
def test_import_quirks_are_failed_unverified_without_retry(
    tmp_path: Path, behavior: fr.FakeBehavior, needle: str
) -> None:
    t1 = T1(tmp_path, behavior=behavior)
    confirmation = t1.confirm(MID)
    plan = t1.port.plan(confirmation)
    outcome = t1.execute(plan, confirmation)
    assert outcome.status is MutationStatus.FAILED and needle in outcome.detail
    assert outcome.readback is VerificationStatus.UNVERIFIED and outcome.retried is False
    assert "not retried" in outcome.detail
    assert t1.behavior.count(IMPORT) == 1
    assert t1.project.current is t1.project.timeline  # nothing switched


def test_layers_preserved_and_track_names_restored_on_import(tmp_path: Path) -> None:
    names = {"video": ["Interview", "B-roll"], "audio": ["Dialogue"]}
    t1 = T1(tmp_path)
    t1.project.timeline._track_names = {k: list(v) for k, v in names.items()}
    confirmation = t1.confirm(MID)
    outcome = t1.execute(t1.port.plan(confirmation), confirmation)
    assert outcome.layers is VerificationStatus.MATCH and outcome.readback is (
        VerificationStatus.MATCH
    )
    assert t1.behavior.count("Timeline.SetTrackName") == 3
    assert t1.project.current is not None and t1.project.current._track_names == names
    assert outcome.readback_read is not None and outcome.readback_read.actual is not None
    kinds = [(t.kind.value, t.name) for t in outcome.readback_read.actual.tracks]
    assert kinds == [("VIDEO", "Video 1"), ("VIDEO", "Video 2"), ("AUDIO", "Audio 1")]
    # without SetTrackName the loss is reported (MISMATCH), and the version is not opened
    t2 = T1(tmp_path, t1_profile(SET_TRACK_NAME=G.UNKNOWN))
    t2.project.timeline._track_names = {k: list(v) for k, v in names.items()}
    confirmation2 = t2.confirm(MID)
    lost = t2.execute(t2.port.plan(confirmation2), confirmation2)
    assert lost.layers is VerificationStatus.MISMATCH and lost.readback is (
        VerificationStatus.MISMATCH
    )
    assert "Video 1='Interview'" in lost.detail and not lost.current_timeline_switched


def test_imported_geometry_error_is_mismatch_and_not_opened(tmp_path: Path) -> None:
    t1 = T1(tmp_path, behavior=fr.FakeBehavior(import_extra_shift=1))
    confirmation = t1.confirm(MID)
    outcome = t1.execute(t1.port.plan(confirmation), confirmation)
    assert outcome.status is MutationStatus.PERFORMED
    assert outcome.geometry is VerificationStatus.MISMATCH
    assert outcome.readback is VerificationStatus.MISMATCH
    assert not outcome.current_timeline_switched


# --- bindings, policy, determinism, evidence ----------------------------------------------


def test_plan_and_confirmation_digests_and_staleness_are_enforced(tmp_path: Path) -> None:
    t1 = T1(tmp_path)
    confirmation = t1.confirm(MID)
    plan = t1.port.plan(confirmation)
    with pytest.raises(ApplyRefused):
        t1.port.execute(
            plan, confirmation, confirmed_digest="0" * 64, confirmed_plan_digest=plan.plan_digest
        )
    with pytest.raises(ApplyRefused):
        t1.port.execute(
            plan,
            confirmation,
            confirmed_digest=confirmation.confirmation_digest,
            confirmed_plan_digest=confirmation.confirmation_digest,
        )
    t1.project.timeline._trim_end("video", 2, 0, 5)  # the editor changes the timeline
    stale = t1.execute(plan, confirmation)
    assert stale.status is MutationStatus.REFUSED and stale.issue is PortIssueKind.STALE
    assert t1.behavior.count(IMPORT) == 0
    assert t1.port.plan(confirmation).status is PlanStatus.REFUSED


def test_keep_in_place_is_imported_as_a_version_never_in_place(tmp_path: Path) -> None:
    """INT-002: the LAYER-001 Expected expresses KEEP_IN_PLACE, so the import tier
    carries it (same geometry as the file path); the in-place tiers cannot."""
    keep = (TrackPolicyOverride("Video 2", TrackCutPolicy.KEEP_IN_PLACE),)
    t1 = T1(tmp_path)
    confirmation = t1.confirm({"AIE-0001": "OK", "AIE-0002": "OK"}, keep)  # all aligned
    plan = t1.port.plan(confirmation)
    # tier 3 would be chosen for aligned cuts, but KEEP is not expressible in place
    assert plan.status is PlanStatus.READY
    assert plan.tier is ApplyTier.TIER_1_IMPORT_NEW_VERSION
    assert ("AIE-0001", "Video 2", TrackCutPolicy.KEEP_IN_PLACE) in plan.track_policies
    assert "Video 2 [VIDEO:2] KEEP_IN_PLACE (override) -> UNCHANGED" in plan.summary
    outcome = t1.execute(plan, confirmation)
    assert outcome.status is MutationStatus.PERFORMED, outcome.detail
    assert outcome.readback is VerificationStatus.MATCH
    assert t1.behavior.count("Timeline.DeleteClips") == 0
    _, _, _, applied_file = file_path({"AIE-0001": "OK", "AIE-0002": "OK"}, overrides=keep)
    assert outcome.readback_read is not None and outcome.readback_read.actual is not None
    assert cut_geometry(outcome.readback_read.actual) == cut_geometry(applied_file.timeline)
    assert cut_geometry(applied_file.timeline)[1] == ("VIDEO", 2, ((300, "broll.mov", 0, 50),))
    # with the import tier unavailable there is no Studio route: file path
    blocked = T1(tmp_path / "b", t1_profile(IMPORT_TIMELINE_FROM_FILE=G.ABSENT))
    (tmp_path / "b").mkdir()
    plan_b = blocked.port.plan(blocked.confirm({"AIE-0001": "OK", "AIE-0002": "OK"}, keep))
    assert plan_b.status is PlanStatus.UNSUPPORTED
    assert any("TRACK_SELECTIVE_RIPPLE" in r for r in plan_b.reasons)


def test_plans_and_results_are_deterministic(tmp_path: Path) -> None:
    runs = []
    for n in range(2):
        t1 = T1(tmp_path / str(n))
        (tmp_path / str(n)).mkdir()
        t1.grade_clip_a()
        confirmation = t1.confirm(MID)
        plan = t1.port.plan(confirmation)
        outcome = t1.execute(plan, confirmation)
        assert outcome.readback_read is not None and outcome.readback_read.actual is not None
        runs.append((plan.plan_digest, plan.summary, cut_geometry(outcome.readback_read.actual)))
    assert runs[0] == runs[1]


def test_studio_reads_carry_their_own_evidence_label(tmp_path: Path) -> None:
    t1 = T1(tmp_path)
    read = t1.studio.read_port.read()
    assert read.consistency is CaptureConsistency.CONSISTENT
    assert read.evidence_label == "STUDIO_API_READ" and read.native_evidence is False
    assert read.evidence == StudioEvidence()
    # INT-002: the core types carry the Studio class themselves (nothing superseded)
    assert read.evidence.core_evidence_class == "STUDIO_API_READ"
    assert read.evidence.core_label_superseded is False
    assert read.actual is not None and read.actual.evidence_class == "STUDIO_API_READ"
    assert read.artifact_ref.evidence_class == "STUDIO_API_READ"
    assert read.evidence.qualification == "TEST_ONLY_SUPPORT"
    assert t1.port.read_grade_state().evidence_label == "STUDIO_API_READ"
    confirmation = t1.confirm(MID)
    plan = t1.port.plan(confirmation)
    assert plan.evidence_label == "STUDIO_API_READ" and plan.authorizes_apply is False
    outcome = t1.execute(plan, confirmation)
    assert outcome.evidence_label == "STUDIO_API_READ" and outcome.native_evidence is False
    wrapped = studio_verification(outcome.report)
    assert wrapped.status is outcome.geometry and wrapped.evidence.domain == "STUDIO_API_READ"
    assert studio_verification(None).status is VerificationStatus.UNVERIFIED


# --- capability evidence and hygiene ----------------------------------------------------


def test_t1_capability_findings_are_recorded_with_sources() -> None:
    def entry(capability: StudioCapability) -> tuple[CapabilityStatus, str, str]:
        e = capability_entry(capability)
        return e.status, e.notes, " ".join(e.sources)

    status, notes, sources = entry(C.GRADE_COPY_GRADES)
    assert status is CapabilityStatus.DOCUMENTED_CLAIM
    assert "REPLACES" in notes and "NO version" in notes and "TimelineItem.CopyGrades" in sources
    status, notes, sources = entry(C.IMPORT_NAME_AUTHORITY)
    assert status is CapabilityStatus.UNVERIFIED and "EXISTING" in notes
    assert "internal sequence name overrides timelineName" in sources
    for absent in (
        C.GRADE_COPY_ALL_LAYERS,
        C.GRADE_COPY_VERSIONS,
        C.GRADE_APPLY_FROM_STILL,
        C.IMPORT_MARKER_COLOR_AND_CUSTOM_DATA,
    ):
        assert capability_entry(absent).status is CapabilityStatus.NOT_AVAILABLE
    for unverified in (
        C.GRADE_ABSENCE_INFERENCE,
        C.GRADE_COPY_KEYFRAMES,
        C.GRADE_COPY_ACROSS_TIMELINES,
        C.NATIVE_MCP_SPLIT_TRIM_TOOLS,
        C.TIMECODE_STRING_FORMAT,
    ):
        assert capability_entry(unverified).status is CapabilityStatus.UNVERIFIED
    assert capability_entry(C.SPLIT_ITEM_AT_FRAME).status is CapabilityStatus.NOT_AVAILABLE
    assert "current-timeline pointer" in capability_entry(C.DUPLICATE_TIMELINE).notes
    assert G.GRANTED_TEST_ONLY not in documented_profile().grants.values()


def test_tiered_allowlist_has_no_rebuild_track_or_native_calls() -> None:
    names = {
        m
        for methods in (*TIERED_READ_METHODS.values(), *TIERED_MUTATION_METHODS.values())
        for m in methods
    }
    forbidden = {
        "AppendToTimeline",
        "CreateTimelineFromClips",
        "DeleteTrack",
        "SetTrackLock",
        "DeleteTimelines",
        "DuplicateTimeline",
        "DeleteClips",
        "AddTrack",
    }
    assert not names & forbidden
    root = Path(__file__).resolve().parents[1] / "src" / "davinci_ai_editor"
    for module in ("studio_tiered_apply", "studio_apply_planner", "studio_razor"):
        source = (root / f"{module}.py").read_text(encoding="utf-8")
        assert "hasattr(" not in source
        assert "import DaVinciResolveScript" not in source


def test_imported_markers_keep_names_only(tmp_path: Path) -> None:
    t1 = T1(tmp_path)
    confirmation = t1.confirm(MID)
    outcome = t1.execute(t1.port.plan(confirmation), confirmation)
    assert outcome.readback_read is not None and outcome.readback_read.actual is not None
    markers = [
        m
        for t in outcome.readback_read.actual.tracks
        for i in t.items
        if isinstance(i, HandoffClip)
        for m in i.markers
    ]
    assert {m.name for m in markers} == {"AIE-0002 ?", "AIE-0004 ?"}
    assert outcome.expected is not None
    assert outcome.expected.duration == fixture().duration - 30
    assert FrameRange(30, 40) in [c.timeline_range for c in confirmation.approved_cuts]
