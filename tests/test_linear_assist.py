"""TEST_ONLY_SUPPORT: supplied display facts, never native qualification or UI work."""

import ast
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest
from test_orchestration import prepared
from test_reference_style import intent

from davinci_ai_editor import authority as a
from davinci_ai_editor import linear_assist as u
from davinci_ai_editor import reference_style as style
from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.evidence import ProducerKind, ProducerRef
from davinci_ai_editor.pause import Confidence, PauseAction
from davinci_ai_editor.temporal_mapping import TimelineFrameRange

PRODUCER = ProducerRef(ProducerKind.HUMAN_SUPPLIED, "TEST_ONLY_SUPPORT", "1", "1")
BASIS = ("TEST_ONLY_SUPPORT supplied evidence",)


def presentation(action: PauseAction = PauseAction.TIGHTEN) -> u.CandidatePresentation:
    value = prepared()
    candidate = value.inputs.authority_candidate
    return u.CandidatePresentation(
        "display-1",
        "proposal-revision-1",
        replace(
            value.editorial_candidate,
            action=action,
            suggested_retained_frames=(
                value.editorial_candidate.suggested_retained_frames
                if action == PauseAction.TIGHTEN
                else None
            ),
        ),
        value.expected_diff.base_snapshot,
        u.ScopePresentation(
            "change-scope",
            ("accepted-cuts",),
            ("this-pause",),
            (),
            BASIS,
            value.expected_diff.inputs.scope,
        ),
        authority=a.CandidateWorkState(candidate, a.WorkingAuthority(candidate.base)),
        location=TimelineFrameRange(FrameRange(100, 120)),
        location_basis_refs=BASIS,
        snapshot_is_current=True,
        currentness_basis_refs=BASIS,
        expected_diff=value.expected_diff,
        safety=value.safety,
        geometry=value.geometry,
        actions=tuple(u.ActionAvailability(action, True, BASIS) for action in u.PresentationAction),
    )


def position(source: u.CandidatePresentation, frame: int = 90) -> u.PositionWindow:
    return u.PositionWindow(source.snapshot, frame, TimelineFrameRange(FrameRange(80, 200)), BASIS)


def projected(source: u.CandidatePresentation) -> u.ProjectedCandidate:
    return u.project_upcoming((source,), position(source)).candidates[0]


@pytest.mark.parametrize("mode", tuple(u.AssistMode))
def test_keep_is_silent_unless_show_more(mode: u.AssistMode) -> None:
    source = presentation(PauseAction.KEEP)
    assert not u.project_upcoming((source,), position(source), mode=mode).candidates[0].visible
    assert (
        u.project_upcoming((source,), position(source), mode=mode, show_more=True)
        .candidates[0]
        .visible
    )


def test_review_no_response_preserves_without_rewriting_or_decision() -> None:
    source = presentation(PauseAction.REVIEW)
    result = projected(source)
    assert result.source is source
    assert result.source.candidate.action == PauseAction.REVIEW
    assert result.no_response_behavior == "PRESERVE_CURRENT_STATE"
    assert source.authority is not None
    assert source.authority.candidate.approval == a.ApprovalState.NOT_APPROVED
    assert source.authority.candidate.selection == a.SelectionState.UNSELECTED
    assert u.project_upcoming((source,), position(source)).counts.explicit_human_decisions is None


def test_all_five_counts_are_independent_supplied_measurements() -> None:
    source = presentation()
    counts = u.AssistCounts(70, 9, 2, 1, 0, BASIS)
    result = u.project_upcoming((source,), position(source), counts=counts)
    assert result.counts is counts
    assert tuple(
        getattr(counts, name)
        for name in (
            "internal_observations",
            "visible_recommendations",
            "attention_requests",
            "explicit_human_decisions",
            "executed_changes",
        )
    ) == (70, 9, 2, 1, 0)


@pytest.mark.parametrize("classification", tuple(u.ReviewClassification))
def test_review_assessment_is_retained_without_interruption_or_authority(
    classification: u.ReviewClassification,
) -> None:
    assessment = u.ReviewAssessment(classification, PRODUCER, BASIS, ("supplied-basis",))
    source = replace(presentation(PauseAction.REVIEW), review=assessment)
    result = u.project_upcoming((source,), position(source))
    assert result.candidates[0].source.review is assessment
    assert result.counts.attention_requests is None
    assert result.candidates[0].no_response_behavior == "PRESERVE_CURRENT_STATE"
    assert (
        len({u.ReviewClassification.NOT_EVALUATABLE, u.ReviewClassification.LOW_REVIEW_NEED}) == 2
    )


def test_missing_facts_remain_missing_and_snapshot_equality_is_not_currentness() -> None:
    original = presentation()
    source = u.CandidatePresentation(
        "minimal", "r1", original.candidate, original.snapshot, u.ScopePresentation("scope")
    )
    result = projected(source)
    assert result.current is None and result.relation == u.PositionRelation.UNKNOWN
    assert all(
        fact is None
        for fact in (
            source.location,
            source.geometry,
            source.review,
            source.proposal_summary,
            source.reason,
            source.uncertainty,
            source.safety,
            source.expected_diff,
        )
    )
    assert not result.actions
    assert "SCOPE_CONFLICT_UNASSESSED" in result.inactive_reasons


def test_mode_switch_preserves_exact_objects_and_revision() -> None:
    source = presentation()
    linear = u.project_upcoming((source,), position(source))
    queue = u.project_upcoming((source,), position(source), mode=u.AssistMode.REVIEW_QUEUE)
    for result in (linear, queue):
        retained = result.candidates[0].source
        assert retained is source
        for name in (
            "candidate",
            "snapshot",
            "scope",
            "authority",
            "expected_diff",
            "safety",
            "geometry",
        ):
            assert getattr(retained, name) is getattr(source, name)
        assert retained.candidate_revision_ref == "proposal-revision-1"


@pytest.mark.parametrize("stale_authority", [True, False])
def test_stale_is_explainable_but_never_current_or_actionable(stale_authority: bool) -> None:
    source = presentation()
    if stale_authority:
        assert source.authority is not None
        source = replace(
            source,
            authority=replace(
                source.authority,
                candidate=replace(source.authority.candidate, validity=a.CandidateValidity.STALE),
            ),
        )
    else:
        source = replace(source, snapshot_is_current=False)
    result = projected(source)
    assert result.visible and result.current is False and result.inactive_reasons
    assert all(
        action.available is False
        for action in result.actions
        if action.supplied.action != u.PresentationAction.DEFER_REVIEW
    )


@pytest.mark.parametrize(
    "frame,relation",
    [
        (90, u.PositionRelation.AHEAD),
        (100, u.PositionRelation.AT_CONTEXT),
        (119, u.PositionRelation.AT_CONTEXT),
        (120, u.PositionRelation.PASSED),
    ],
)
def test_supplied_half_open_position_relation(frame: int, relation: u.PositionRelation) -> None:
    source = presentation()
    supplied = position(source, frame)
    result = u.project_upcoming((source,), supplied)
    assert result.position is supplied and result.position.position_frame == frame
    assert result.candidates[0].relation == relation


def test_late_candidate_does_not_rewind_and_is_available_in_queue() -> None:
    source = presentation()
    supplied = position(source, 150)
    linear = u.project_upcoming((source,), supplied)
    queue = u.project_upcoming((source,), supplied, mode=u.AssistMode.REVIEW_QUEUE)
    assert not linear.candidates[0].visible and queue.candidates[0].visible
    assert queue.candidates[0].relation == u.PositionRelation.PASSED
    assert linear.position is queue.position is supplied
    assert not any("seek" in field.name or "rewind" in field.name for field in fields(linear))


def test_no_window_or_position_is_invented() -> None:
    source = presentation()
    for supplied in (
        u.PositionWindow(),
        replace(position(source), window=None),
        replace(position(source), position_frame=None),
    ):
        result = u.project_upcoming((source,), supplied)
        assert result.candidates[0].relation == u.PositionRelation.UNKNOWN
        assert not result.candidates[0].visible
        assert result.position is supplied


def test_window_has_no_default_time_distance_threshold() -> None:
    source = presentation()
    supplied = replace(position(source), window=TimelineFrameRange(FrameRange(0, 100)))
    result = u.project_upcoming((source,), supplied)
    assert result.candidates[0].relation == u.PositionRelation.OUTSIDE_WINDOW
    assert not result.candidates[0].visible


def test_snapshot_mismatch_is_inactive_not_guessed_mapping() -> None:
    source = presentation()
    supplied = replace(position(source), snapshot=replace(source.snapshot, state_token="other"))
    result = u.project_upcoming((source,), supplied, show_more=True).candidates[0]
    assert result.current is False and result.relation == u.PositionRelation.UNKNOWN
    assert "POSITION_SNAPSHOT_MISMATCH" in result.inactive_reasons


def test_missing_geometry_is_not_derived_from_candidate_or_expected_diff() -> None:
    source = replace(presentation(), geometry=None)
    result = projected(source)
    assert result.source.geometry is None
    assert "DIFF_GEOMETRY_NOT_RETAINED" in result.inactive_reasons
    assert (
        next(
            action
            for action in result.actions
            if action.supplied.action == u.PresentationAction.REQUEST_APPLY
        ).available
        is False
    )


@pytest.mark.parametrize("conflicts", [None, ("accepted-cut-overlap",)])
def test_scope_conflict_or_unassessed_scope_is_surfaced(conflicts: tuple[str, ...] | None) -> None:
    source = presentation()
    scope = replace(source.scope, conflict_refs=conflicts)
    source = replace(source, scope=scope)
    result = projected(source)
    assert result.source.scope is scope
    assert any("SCOPE_CONFLICT" in reason for reason in result.inactive_reasons)
    assert scope.accepted_scope_refs == ("accepted-cuts",)
    assert scope.reopened_scope_refs == ("this-pause",)


def test_style_cannot_expand_modification_or_reopened_scope() -> None:
    source = presentation()
    context = style.compose_style(intent())
    original_scope = source.scope
    result = projected(replace(source, style=context))
    assert result.source.style is context
    assert result.source.scope is original_scope
    assert result.source.scope.modification_scope_ref == "change-scope"
    assert result.source.scope.reopened_scope_refs == ("this-pause",)
    assert "STYLE_MODIFICATION_SCOPE_MISMATCH" in result.inactive_reasons


def test_matching_style_is_retained_without_learning_or_reopening() -> None:
    source = presentation()
    context = style.compose_style(replace(intent(), modification_scope_ref="change-scope"))
    result = projected(replace(source, style=context))
    assert result.source.style is context
    assert not result.inactive_reasons


def test_action_availability_never_grants_selection_approval_execution_or_verification() -> None:
    source = presentation()
    before = source.authority
    result = projected(source)
    assert not result.inactive_reasons
    assert all(action.available is True for action in result.actions)
    assert source.authority is before and before is not None
    assert before.candidate.selection == a.SelectionState.UNSELECTED
    assert before.candidate.approval == a.ApprovalState.NOT_APPROVED
    assert before.candidate.application == a.ApplicationState.NOT_APPLIED
    assert before.candidate.verification == a.VerificationState.NOT_VERIFIED


@pytest.mark.parametrize("available", [None, False])
def test_projection_never_upgrades_external_action_availability(available: bool | None) -> None:
    source = replace(
        presentation(),
        actions=(u.ActionAvailability(u.PresentationAction.REQUEST_APPLY, available, BASIS),),
    )
    assert projected(source).actions[0].available is available


def test_defer_hide_and_batch_display_do_not_create_domain_events() -> None:
    first = presentation(PauseAction.REVIEW)
    second = replace(first, presentation_ref="display-2", candidate_revision_ref="revision-2")
    result = u.project_upcoming(
        (first, second),
        position(first),
        deferred_refs=(first.presentation_ref,),
        hidden_refs=(second.presentation_ref,),
    )
    assert not any(entry.visible for entry in result.candidates)
    queue = u.project_upcoming(
        (first, second),
        position(first),
        mode=u.AssistMode.REVIEW_QUEUE,
        deferred_refs=(first.presentation_ref,),
    )
    assert all(entry.visible for entry in queue.candidates)
    assert queue.counts.explicit_human_decisions is queue.counts.executed_changes is None
    assert queue.candidates[0].source is first and queue.candidates[1].source is second
    assert all(entry.source.candidate.action == PauseAction.REVIEW for entry in queue.candidates)
    assert first.authority is second.authority


def test_review_required_does_not_override_user_visibility_choice() -> None:
    source = replace(
        presentation(PauseAction.REVIEW),
        review=u.ReviewAssessment(u.ReviewClassification.REVIEW_REQUIRED, PRODUCER, BASIS, BASIS),
    )
    result = u.project_upcoming((source,), position(source), hidden_refs=(source.presentation_ref,))
    assert not result.candidates[0].visible


def test_records_are_frozen_and_cannot_hold_mutable_reference_collections() -> None:
    source = presentation()
    with pytest.raises(FrozenInstanceError):
        attribute = "candidate"
        setattr(source, attribute, None)
    with pytest.raises(TypeError):
        u.ScopePresentation("scope", accepted_scope_refs=["mutable"])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        replace(source, actions=list(source.actions))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        u.project_upcoming([source], position(source))  # type: ignore[arg-type]


def test_known_facts_require_basis_and_unknown_is_not_false() -> None:
    with pytest.raises(ValueError):
        u.ActionAvailability(u.PresentationAction.REQUEST_APPLY, True)
    with pytest.raises(ValueError):
        u.AssistCounts(explicit_human_decisions=0)
    with pytest.raises(ValueError):
        u.ScopePresentation("scope", conflict_refs=())
    with pytest.raises(ValueError):
        u.ReviewAssessment(u.ReviewClassification.NOT_EVALUATABLE, PRODUCER, (), BASIS)
    with pytest.raises(ValueError):
        u.PositionWindow(position_frame=10)
    with pytest.raises(ValueError):
        replace(presentation(), location_basis_refs=())
    assert u.ActionAvailability(u.PresentationAction.SELECT_PROPOSAL).available is None


def test_duplicate_display_ids_and_action_descriptions_are_rejected() -> None:
    source = presentation()
    with pytest.raises(ValueError):
        u.project_upcoming((source, source), position(source))
    with pytest.raises(ValueError):
        replace(source, actions=(source.actions[0], source.actions[0]))


def test_high_confidence_remove_does_not_imply_mutation() -> None:
    source = presentation()
    remove = replace(
        source.candidate,
        action=PauseAction.REMOVE,
        confidence=Confidence.HIGH,
        suggested_retained_frames=None,
    )
    source = replace(source, candidate=remove, expected_diff=None, safety=None, geometry=None)
    result = projected(source)
    assert result.source.candidate is remove
    assert result.no_response_behavior == "PRESERVE_CURRENT_STATE"
    assert source.authority is not None
    assert source.authority.candidate.approval == a.ApprovalState.NOT_APPROVED
    assert (
        next(
            action
            for action in result.actions
            if action.supplied.action == u.PresentationAction.REQUEST_APPLY
        ).available
        is False
    )


@pytest.mark.parametrize("missing", ["authority", "expected_diff", "safety", "geometry"])
def test_incomplete_apply_context_cannot_be_advertised_as_available(missing: str) -> None:
    original = presentation()
    variants = {
        "authority": replace(original, authority=None),
        "expected_diff": replace(original, expected_diff=None),
        "safety": replace(original, safety=None),
        "geometry": replace(original, geometry=None),
    }
    source = variants[missing]
    action = next(
        action
        for action in projected(source).actions
        if action.supplied.action == u.PresentationAction.REQUEST_APPLY
    )
    assert action.available is False and "EXTERNAL_APPLY_CONTEXT_MISSING" in action.inactive_reasons


def test_reconstructed_equal_diff_is_not_exact_retained_safety_input() -> None:
    source = presentation()
    assert source.expected_diff is not None
    copied = replace(source.expected_diff)
    assert copied == source.expected_diff and copied is not source.expected_diff
    result = projected(replace(source, expected_diff=copied))
    assert "SAFETY_DIFF_NOT_RETAINED" in result.inactive_reasons


def test_projection_result_collections_are_immutable_and_cannot_upgrade_availability() -> None:
    source = presentation()
    result = u.project_upcoming((source,), position(source))
    with pytest.raises(TypeError):
        replace(result, candidates=list(result.candidates))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        replace(result.candidates[0], actions=[])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        u.ProjectedAction(u.ActionAvailability(u.PresentationAction.REQUEST_APPLY), True, ())


def test_production_ast_has_no_state_machine_event_producer_or_execution_path() -> None:
    tree = ast.parse(Path(u.__file__).read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports == {
        "dataclasses",
        "enum",
        "typing",
        "authority",
        "evidence",
        "expected_diff",
        "pause",
        "pause_planning",
        "reference_style",
        "safety_preflight",
        "temporal_mapping",
    }
    enums = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(isinstance(base, ast.Name) and base.id == "Enum" for base in node.bases)
    }
    assert enums == {"AssistMode", "ReviewClassification", "PresentationAction", "PositionRelation"}
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not calls.intersection(
        {
            "Candidate",
            "PauseCandidate",
            "CandidateWorkState",
            "FeedbackEvent",
            "ApproveCandidate",
            "transition",
            "classify_pause",
            "evaluate_safety",
            "ActualDiff",
            "Transaction",
            "compose_style",
            "execute_next",
            "finalize_edit",
            "admit_execution",
        }
    )
    assert not any(isinstance(node, (ast.AsyncFunctionDef, ast.While)) for node in ast.walk(tree))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name not in enums:
            assert any(
                isinstance(decorator, ast.Call)
                and any(
                    k.arg == "frozen"
                    and isinstance(k.value, ast.Constant)
                    and k.value.value is True
                    for k in decorator.keywords
                )
                for decorator in node.decorator_list
            )
