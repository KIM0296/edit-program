from dataclasses import FrozenInstanceError, replace

import pytest

from davinci_ai_editor.authority import (
    ActivateTimeline,
    ApplicationRecord,
    ApplicationState,
    ApprovalState,
    ApproveCandidate,
    Candidate,
    CandidateBase,
    CandidateId,
    CandidateLineage,
    CandidateResultRef,
    CandidateValidity,
    CandidateWorkState,
    ObserveHumanVersion,
    PromoteCandidate,
    PromotionState,
    RecordApplication,
    RecordVerification,
    SelectCandidate,
    SelectionState,
    SetWorkPhase,
    TransitionReason,
    VerificationState,
    WorkingAuthority,
    WorkPhase,
    apply_eligibility,
    branch_candidate,
    transition,
)
from davinci_ai_editor.domain import TimelineId, TimelineVersion

BASE = CandidateBase(TimelineId("main"), TimelineVersion(42))
RESULT = CandidateResultRef(
    "fake-result-B", CandidateBase(TimelineId("result-B"), TimelineVersion(1))
)


def state():
    return CandidateWorkState(
        Candidate(CandidateId("B"), BASE), WorkingAuthority(BASE), TimelineId("main")
    )


def approved():
    return transition(state(), ApproveCandidate()).state


def record(s=None, result=RESULT):
    s = s or approved()
    return ApplicationRecord(s.candidate.candidate_id, s.candidate.base, result)


def applied():
    s = approved()
    return transition(s, RecordApplication(record(s))).state


def verified():
    s = applied()
    return transition(s, RecordVerification(s.candidate.application_record, True)).state


def assert_reject(s, event, reason=None):
    result = transition(s, event)
    assert not result.accepted
    assert result.state == s
    if reason is not None:
        assert result.reason == reason
    return result


def test_selection_changes_only_selection_not_approval_or_authority():
    s = state()
    result = transition(s, SelectCandidate())
    assert result.accepted
    assert result.state.candidate == replace(s.candidate, selection=SelectionState.SELECTED)
    assert result.state.authority == s.authority
    assert result.state.active_timeline_id == s.active_timeline_id
    assert not apply_eligibility(result.state).eligible


def test_approval_never_applies_verifies_promotes_or_switches_authority():
    s = state()
    result = transition(s, ApproveCandidate())
    assert result.accepted
    assert result.state.candidate == replace(s.candidate, approval=ApprovalState.APPROVED)
    assert result.state.authority == s.authority
    assert result.state.active_timeline_id == s.active_timeline_id
    assert apply_eligibility(result.state).eligible
    assert result.state.candidate.selection == SelectionState.UNSELECTED


def test_stale_after_approval_preserves_original_base_and_approval():
    s = approved()
    now = CandidateBase(BASE.timeline_id, TimelineVersion(45))
    result = transition(s, ObserveHumanVersion(now))
    assert result.accepted
    assert result.state.authority.reference == now
    assert result.state.candidate.base == BASE
    assert result.state.candidate.validity == CandidateValidity.STALE
    assert result.state.candidate.approval == ApprovalState.APPROVED
    assert not apply_eligibility(result.state).eligible
    assert_reject(result.state, RecordApplication(record(s)), TransitionReason.STALE)


def test_constructor_mismatch_is_stale_including_different_timeline_same_version():
    for current in (
        CandidateBase(BASE.timeline_id, TimelineVersion(45)),
        CandidateBase(TimelineId("other"), BASE.timeline_version),
        CandidateBase(BASE.timeline_id, TimelineVersion(40)),
    ):
        s = replace(approved(), authority=WorkingAuthority(current))
        assert s.candidate.base == BASE
        assert s.candidate.validity == CandidateValidity.STALE
        assert not apply_eligibility(s).eligible


def test_human_edit_does_not_rebase_or_silently_resurrect_old_candidate():
    s = transition(approved(), ObserveHumanVersion(replace(BASE, timeline_version=45))).state
    assert_reject(s, ObserveHumanVersion(BASE), TransitionReason.OLDER_OBSERVATION)
    # Even a caller round-tripping context back to the old base cannot refresh stale state.
    reverted = replace(s, authority=WorkingAuthority(BASE))
    assert reverted.candidate.validity == CandidateValidity.STALE
    assert not apply_eligibility(reverted).eligible
    for phase in WorkPhase:
        reverted = transition(reverted, SetWorkPhase(phase)).state
        assert reverted.candidate.base == BASE
        assert reverted.candidate.validity == CandidateValidity.STALE


@pytest.mark.parametrize("factory", [state, approved, applied])
def test_created_approved_and_unverified_states_cannot_promote(factory):
    assert_reject(factory(), PromoteCandidate(RESULT.reference))


def test_selected_candidate_cannot_promote():
    assert_reject(transition(state(), SelectCandidate()).state, PromoteCandidate(RESULT.reference))


def test_verified_promotion_changes_only_explicit_working_authority_and_history():
    s = verified()
    before = repr(s)
    result = transition(s, PromoteCandidate(RESULT.reference))
    assert result.accepted
    assert result.state.authority == WorkingAuthority(RESULT.reference, CandidateId("B"), RESULT)
    assert result.state.active_timeline_id == s.active_timeline_id
    assert result.state.candidate.base == BASE
    assert result.state.candidate.promotion == PromotionState.PROMOTED
    assert result.state.candidate.application == ApplicationState.APPLIED
    assert result.state.candidate.verification == VerificationState.VERIFIED
    assert not apply_eligibility(result.state).eligible
    assert repr(s) == before
    assert_reject(result.state, PromoteCandidate(RESULT.reference))


def test_candidate_branching_does_not_copy_authority_or_approval():
    s = approved()
    child = branch_candidate(s.candidate, CandidateId("B2"))
    assert child.base == BASE
    assert child.lineage.ancestors == (CandidateId("B"),)
    assert child.approval == ApprovalState.NOT_APPROVED
    assert child.selection == SelectionState.UNSELECTED
    assert child.application == ApplicationState.NOT_APPLIED
    assert child.verification == VerificationState.NOT_VERIFIED
    assert child.promotion == PromotionState.NOT_PROMOTED
    child_state = replace(s, candidate=child)
    assert child_state.authority == s.authority
    assert child_state.active_timeline_id == s.active_timeline_id
    grandchild = branch_candidate(child, CandidateId("B3"))
    assert grandchild.lineage.ancestors == (CandidateId("B"), CandidateId("B2"))
    for duplicate in ("B", "B2"):
        with pytest.raises(ValueError):
            branch_candidate(child, CandidateId(duplicate))


def test_stale_parent_branch_cannot_be_a_refresh():
    s = transition(state(), ObserveHumanVersion(replace(BASE, timeline_version=45))).state
    child = branch_candidate(s.candidate, CandidateId("B2"))
    assert child.base == BASE and child.validity == CandidateValidity.STALE
    assert not apply_eligibility(replace(s, candidate=child)).eligible


def test_active_timeline_switch_and_selection_never_change_authority():
    s = state()
    for name in ("candidate-preview", "another-human-timeline", "main"):
        switched = transition(s, ActivateTimeline(TimelineId(name))).state
        assert switched.authority == s.authority
        assert switched.candidate == s.candidate
        assert switched.active_timeline_id == name
        s = switched
    assert_reject(
        s,
        ObserveHumanVersion(CandidateBase(TimelineId("preview"), TimelineVersion(45))),
        TransitionReason.WRONG_AUTHORITY,
    )


def test_same_version_observation_is_noop_and_phase_is_not_approval():
    s = transition(state(), SetWorkPhase(WorkPhase.READY)).state
    assert s.candidate.approval == ApprovalState.NOT_APPROVED
    assert transition(s, ObserveHumanVersion(BASE)).state == s
    assert not apply_eligibility(s).eligible


def test_human_change_after_verification_blocks_promotion_without_erasing_history():
    s = transition(verified(), ObserveHumanVersion(replace(BASE, timeline_version=43))).state
    assert s.candidate.verification == VerificationState.VERIFIED
    assert s.candidate.application == ApplicationState.APPLIED
    assert_reject(s, PromoteCandidate(RESULT.reference), TransitionReason.STALE)


def test_result_change_between_verification_and_promotion_blocks_authority_switch():
    s = verified()
    assert_reject(
        s,
        PromoteCandidate(replace(RESULT.reference, timeline_version=2)),
        TransitionReason.RESULT_MISMATCH,
    )
    assert_reject(s, PromoteCandidate(BASE), TransitionReason.RESULT_MISMATCH)


def test_same_timeline_supplied_result_can_promote_without_executing_or_incrementing():
    s = approved()
    supplied = CandidateResultRef("fake-in-place", replace(BASE, timeline_version=43))
    evidence = record(s, supplied)
    s = transition(s, RecordApplication(evidence)).state
    assert s.authority.reference == BASE
    s = transition(s, RecordVerification(evidence, True)).state
    out = transition(s, PromoteCandidate(supplied.reference))
    assert out.accepted
    assert out.state.authority.reference.timeline_version == 43
    assert out.state.candidate.base.timeline_version == 42


@pytest.mark.parametrize(
    "change",
    [
        {"candidate_id": CandidateId("other")},
        {"base": CandidateBase(TimelineId("other"), TimelineVersion(42))},
        {"base": CandidateBase(TimelineId("main"), TimelineVersion(41))},
    ],
)
def test_application_evidence_must_bind_exact_candidate_and_base(change):
    s = approved()
    assert_reject(
        s, RecordApplication(replace(record(s), **change)), TransitionReason.EVIDENCE_MISMATCH
    )


def test_application_without_approval_or_replay_rejected():
    assert_reject(state(), RecordApplication(record()), TransitionReason.NOT_APPROVED)
    assert_reject(applied(), RecordApplication(record()), TransitionReason.ALREADY_APPLIED)


def test_verification_requires_applied_exact_result_evidence():
    evidence = record()
    assert_reject(approved(), RecordVerification(evidence, True), TransitionReason.NOT_APPLIED)
    changed = replace(evidence, result=replace(RESULT, result_id="other-result"))
    assert_reject(applied(), RecordVerification(changed, True), TransitionReason.EVIDENCE_MISMATCH)
    changed = replace(
        evidence, result=replace(RESULT, reference=replace(RESULT.reference, timeline_version=2))
    )
    assert_reject(applied(), RecordVerification(changed, True), TransitionReason.EVIDENCE_MISMATCH)


def test_failed_verification_cannot_promote_or_be_silently_overwritten():
    s = applied()
    event = RecordVerification(s.candidate.application_record, False)
    s = transition(s, event).state
    assert s.candidate.verification == VerificationState.FAILED
    assert_reject(s, PromoteCandidate(RESULT.reference), TransitionReason.NOT_VERIFIED)
    assert_reject(
        s,
        RecordVerification(s.candidate.application_record, True),
        TransitionReason.ALREADY_VERIFIED,
    )


def test_approval_and_verification_cannot_clear_stale():
    s = transition(state(), ObserveHumanVersion(replace(BASE, timeline_version=45))).state
    assert_reject(s, ApproveCandidate(), TransitionReason.STALE)
    s = transition(applied(), ObserveHumanVersion(replace(BASE, timeline_version=45))).state
    assert_reject(
        s, RecordVerification(s.candidate.application_record, True), TransitionReason.STALE
    )


def test_every_transition_is_deterministic_immutable_and_does_not_call_executor(monkeypatch):
    from davinci_ai_editor.fake_timeline import FakeTimeline

    def forbidden(*args, **kwargs):
        raise AssertionError("No timeline execution may be called")

    monkeypatch.setattr(FakeTimeline, "apply", forbidden)
    s = state()
    events = (
        SelectCandidate(),
        SetWorkPhase(WorkPhase.READY),
        ApproveCandidate(),
        RecordApplication(record()),
        RecordVerification(record(), True),
        PromoteCandidate(RESULT.reference),
    )
    for event in events:
        before = repr(s)
        result = transition(s, event)
        assert result == transition(s, event)
        assert repr(s) == before
        assert result.accepted
        with pytest.raises(FrozenInstanceError):
            result.accepted = False
        with pytest.raises(FrozenInstanceError):
            result.state.candidate.base = BASE
        with pytest.raises(FrozenInstanceError):
            result.state.authority.reference = BASE
        s = result.state


def test_lineage_defensively_freezes_and_rejects_duplicate_ancestors():
    ancestors = [CandidateId("A")]
    lineage = CandidateLineage(ancestors)
    ancestors.append(CandidateId("C"))
    assert lineage.ancestors == (CandidateId("A"),)
    with pytest.raises(ValueError):
        CandidateLineage((CandidateId("A"), CandidateId("A")))
    with pytest.raises(ValueError):
        Candidate(CandidateId("A"), BASE, lineage)


@pytest.mark.parametrize("version", [-1, True, 42.0, "42"])
def test_base_rejects_invalid_version(version):
    with pytest.raises((TypeError, ValueError)):
        CandidateBase(TimelineId("main"), version)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("approval", "APPROVED"),
        ("validity", "FRESH"),
        ("application", "APPLIED"),
        ("verification", "VERIFIED"),
        ("promotion", "PROMOTED"),
        ("selection", "SELECTED"),
        ("work_phase", "READY"),
    ],
)
def test_plain_strings_cannot_bypass_typed_axes(field, bad):
    with pytest.raises(TypeError):
        replace(state().candidate, **{field: bad})


def test_inconsistent_axis_combinations_rejected_at_construction():
    for changes in (
        {"application": ApplicationState.APPLIED},
        {"verification": VerificationState.VERIFIED},
        {"promotion": PromotionState.PROMOTED},
        {"application_record": record()},
    ):
        with pytest.raises(ValueError):
            replace(state().candidate, **changes)
    with pytest.raises(ValueError):
        WorkingAuthority(BASE, CandidateId("B"), RESULT)
    with pytest.raises(TypeError):
        RecordVerification(record(), "true")


def test_unknown_event_fails_closed():
    assert_reject(state(), object(), TransitionReason.UNSUPPORTED_EVENT)


def test_selection_after_approval_does_not_revoke_or_change_other_axes():
    s = approved()
    out = transition(s, SelectCandidate()).state
    assert out.candidate == replace(s.candidate, selection=SelectionState.SELECTED)
    assert out.authority == s.authority


def test_branch_of_applied_parent_is_source_exploration_not_applied_result():
    s = verified()
    child = branch_candidate(s.candidate, CandidateId("B2"))
    assert child.base == BASE
    assert child.application_record is None
    assert child.application == ApplicationState.NOT_APPLIED
    assert child.verification == VerificationState.NOT_VERIFIED
    assert child.approval == ApprovalState.NOT_APPROVED
    assert s.candidate.verification == VerificationState.VERIFIED


def test_next_candidate_uses_explicit_promoted_authority_and_later_human_edit_wins():
    promoted = transition(verified(), PromoteCandidate(RESULT.reference)).state
    next_candidate = Candidate(CandidateId("next"), promoted.authority.reference)
    s = replace(promoted, candidate=next_candidate)
    assert s.candidate.validity == CandidateValidity.FRESH
    later = replace(RESULT.reference, timeline_version=9)
    s = transition(s, ObserveHumanVersion(later)).state
    assert s.authority.reference == later
    assert s.authority.promoted_result == RESULT  # Historical provenance, not latest content.
    assert s.candidate.base == RESULT.reference
    assert s.candidate.validity == CandidateValidity.STALE
    assert_reject(s, ApproveCandidate(), TransitionReason.STALE)


def test_same_timeline_result_cannot_roll_version_back():
    with pytest.raises(ValueError):
        record(result=CandidateResultRef("old", replace(BASE, timeline_version=41)))


@pytest.mark.parametrize(
    "constructor",
    [
        lambda: Candidate(CandidateId(""), BASE),
        lambda: CandidateBase(TimelineId(" "), TimelineVersion(42)),
        lambda: CandidateResultRef("", RESULT.reference),
        lambda: ActivateTimeline(TimelineId("")),
        lambda: SetWorkPhase("READY"),
        lambda: ObserveHumanVersion("v45"),
        lambda: RecordApplication("applied"),
        lambda: PromoteCandidate("verified"),
    ],
)
def test_invalid_event_and_identity_values_rejected(constructor):
    with pytest.raises((TypeError, ValueError)):
        constructor()


def test_rejected_transition_and_nested_evidence_are_frozen_and_repeatable():
    s = applied()
    event = PromoteCandidate(RESULT.reference)
    rejection = transition(s, event)
    assert rejection == transition(s, event)
    assert not rejection.accepted
    with pytest.raises(FrozenInstanceError):
        rejection.reason = TransitionReason.ACCEPTED
    with pytest.raises(FrozenInstanceError):
        s.candidate.application_record.result.result_id = "changed"
    with pytest.raises(FrozenInstanceError):
        event.result_observation = BASE
