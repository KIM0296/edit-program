from dataclasses import FrozenInstanceError, fields, replace
from fractions import Fraction
from itertools import permutations

import pytest

from davinci_ai_editor.evaluation import (
    ActivityKind,
    ActivityRecord,
    AdjudicationStatus,
    AIProposalSnapshot,
    Ambiguity,
    DecisionProducerRef,
    EmptyPayload,
    EvaluationCase,
    EvaluationRecord,
    FeedbackActor,
    FeedbackEvent,
    FeedbackEventType,
    FeedbackLog,
    FinalDecisionPayload,
    MeasurementSource,
    ProducerKind,
    ReferenceAnnotation,
    ReferenceAssessment,
    ReferenceJudgment,
    RunEvidence,
    RunFinalizedPayload,
    RunMode,
    SourceKind,
    WorkflowRun,
)
from davinci_ai_editor.evaluation_metrics import (
    CorrectionClass,
    TightenRange,
    derive_editorial_metrics,
    derive_net_time_saved,
    derive_timing_metrics,
    derive_user_final_outcome,
)
from davinci_ai_editor.pause import CandidateRouting, Confidence, PauseAction

PRODUCER = DecisionProducerRef(ProducerKind.RULE, "baseline", "1", "pause-v1", "features-v1")


def proposal(action=PauseAction.TIGHTEN, target=30, case_id="c", proposal_id="p"):
    return AIProposalSnapshot(
        proposal_id,
        case_id,
        action,
        Confidence.MEDIUM,
        ("reason",),
        100,
        target if action == PauseAction.TIGHTEN else None,
        CandidateRouting.BATCH_REVIEW,
        PRODUCER,
    )


def reference(action=PauseAction.TIGHTEN, case_id="c"):
    targets = (30, 20, 40) if action == PauseAction.TIGHTEN else (None, None, None)
    return ReferenceJudgment(
        case_id,
        "ref-v1",
        ReferenceAssessment(action, Confidence.HIGH, ("reference",), 100, *targets),
        Ambiguity.CLEAR,
        AdjudicationStatus.AGREED,
    )


def event(seq, kind, payload=None, case_id="c", proposal_id="p"):
    return FeedbackEvent(
        f"e{seq}",
        case_id,
        proposal_id,
        seq,
        FeedbackActor.EDITOR,
        kind,
        payload if payload is not None else EmptyPayload(),
    )


def final_events(action, target=None):
    return (
        event(1, FeedbackEventType.FINAL_DECISION_SET, FinalDecisionPayload(action, target)),
        event(2, FeedbackEventType.RUN_FINALIZED, RunFinalizedPayload("r")),
    )


def log(events=()):
    return FeedbackLog("c", "p", events)


def record(p=None, ref=None, feedback=None, source=SourceKind.BENCHMARK):
    p = p or proposal()
    case = EvaluationCase(p.case_id, source, "scope", "opaque-pause", "evaluation-v1")
    return EvaluationRecord(case, p, ref, (), feedback)


def run(mode=RunMode.AI_ASSISTED, run_id="r", scope="scope", durations=(10, 20, 30, 40, 50, 60)):
    workflow = WorkflowRun(run_id, scope, mode, PRODUCER, ("c",), tuple(ActivityKind))
    activities = tuple(
        ActivityRecord(
            f"{run_id}-{kind.value}", run_id, "c", kind, duration, MeasurementSource.INSTRUMENTED
        )
        for kind, duration in zip(ActivityKind, durations, strict=True)
    )
    return RunEvidence(workflow, activities)


def test_product_feedback_cannot_carry_or_mutate_benchmark_reference():
    ref = reference()
    with pytest.raises(ValueError):
        record(ref=ref, source=SourceKind.PRODUCT_FEEDBACK)
    benchmark = record(ref=ref)
    before = repr(benchmark)
    feedback = record(
        feedback=log(final_events(PauseAction.KEEP)), source=SourceKind.PRODUCT_FEEDBACK
    )
    derive_editorial_metrics((feedback,))
    assert repr(benchmark) == before
    annotation = ReferenceAnnotation("a", "c", "opaque-annotator", ref.assessment)
    with pytest.raises(ValueError):
        replace(feedback, annotations=(annotation,))


def test_proposal_refresh_requires_new_snapshot_and_batch_cannot_silently_pick_latest():
    original = proposal()
    new = replace(original, proposal_id="p2", suggested_retained_frames=25)
    assert original.suggested_retained_frames == 30
    assert new.proposal_id != original.proposal_id
    with pytest.raises(FrozenInstanceError):
        original.suggested_retained_frames = 20
    with pytest.raises(ValueError):
        derive_editorial_metrics((record(original), record(new)))


def test_event_order_is_sequence_not_input_order_and_append_is_immutable():
    events = (
        event(1, FeedbackEventType.PROPOSAL_ACCEPTED),
        event(
            2, FeedbackEventType.FINAL_DECISION_SET, FinalDecisionPayload(PauseAction.TIGHTEN, 20)
        ),
        event(3, FeedbackEventType.RUN_FINALIZED, RunFinalizedPayload("r")),
    )
    expected = derive_user_final_outcome(proposal(), log(events))
    for perm in permutations(events):
        assert derive_user_final_outcome(proposal(), log(perm)) == expected
    old = log(events[:1])
    new = old.append(events[1])
    assert old.events == events[:1] and new.events == events[:2]
    assert expected.final_retained_frames == 20


@pytest.mark.parametrize(
    "events",
    [
        (event(1, FeedbackEventType.REVIEW_OPENED), event(1, FeedbackEventType.REVIEW_OPENED)),
        (event(2, FeedbackEventType.REVIEW_OPENED),),
        (event(1, FeedbackEventType.REVIEW_OPENED), event(3, FeedbackEventType.REVIEW_OPENED)),
        (
            event(1, FeedbackEventType.RUN_FINALIZED, RunFinalizedPayload("r")),
            event(2, FeedbackEventType.REVIEW_OPENED),
        ),
    ],
)
def test_invalid_sequence_duplicate_or_after_finalize_rejected(events):
    with pytest.raises(ValueError):
        log(events)


def test_duplicate_ids_with_different_sequences_and_wrong_proposal_rejected():
    first = event(1, FeedbackEventType.REVIEW_OPENED)
    with pytest.raises(ValueError):
        log((first, replace(first, sequence_no=2)))
    with pytest.raises(ValueError):
        log((replace(first, proposal_id="other"),))
    with pytest.raises(ValueError):
        log((first,)).append(event(3, FeedbackEventType.REVIEW_OPENED))


@pytest.mark.parametrize(
    "action,target",
    [
        (PauseAction.TIGHTEN, None),
        (PauseAction.TIGHTEN, 0),
        (PauseAction.KEEP, 2),
        (PauseAction.REMOVE, 0),
        (PauseAction.REVIEW, 10),
    ],
)
def test_final_payload_shape_validation(action, target):
    with pytest.raises(ValueError):
        FinalDecisionPayload(action, target)


def test_payload_type_and_bound_target_validation():
    with pytest.raises(TypeError):
        event(1, FeedbackEventType.FINAL_DECISION_SET)
    with pytest.raises(TypeError):
        event(1, FeedbackEventType.REVIEW_OPENED, FinalDecisionPayload(PauseAction.KEEP, None))
    with pytest.raises(ValueError):
        derive_user_final_outcome(proposal(), log(final_events(PauseAction.TIGHTEN, 100)))


@pytest.mark.parametrize(
    "minimum,preferred,maximum", [(0, 20, 40), (20, 10, 40), (20, 50, 40), (20, 30, 100)]
)
def test_tighten_reference_invariant(minimum, preferred, maximum):
    with pytest.raises(ValueError):
        replace(
            reference().assessment,
            acceptable_min_frames=minimum,
            preferred_retained_frames=preferred,
            acceptable_max_frames=maximum,
        )


@pytest.mark.parametrize(
    "target,correction",
    [
        (20, CorrectionClass.TIGHTEN_MORE),
        (40, CorrectionClass.TIGHTEN_LESS),
        (30, CorrectionClass.NONE),
    ],
)
def test_tighten_correction_direction(target, correction):
    out = derive_user_final_outcome(proposal(), log(final_events(PauseAction.TIGHTEN, target)))
    assert out.correction == correction
    assert out.accepted_as_is == (target == 30)
    assert out.modified == (target != 30)


@pytest.mark.parametrize(
    "action,correction",
    [
        (PauseAction.KEEP, CorrectionClass.KEEP_INSTEAD),
        (PauseAction.REMOVE, CorrectionClass.REMOVE_INSTEAD),
        (PauseAction.REVIEW, CorrectionClass.OTHER_ACTION_CHANGE),
    ],
)
def test_action_corrections(action, correction):
    assert derive_user_final_outcome(proposal(), log(final_events(action))).correction == correction


def test_tighten_instead():
    out = derive_user_final_outcome(
        proposal(PauseAction.KEEP), log(final_events(PauseAction.TIGHTEN, 30))
    )
    assert out.correction == CorrectionClass.TIGHTEN_INSTEAD


def test_remove_to_keep_is_distinct_from_actual_restore():
    p = proposal(PauseAction.REMOVE)
    review = derive_user_final_outcome(p, log(final_events(PauseAction.KEEP)))
    restored = derive_user_final_outcome(
        p,
        log(
            (
                event(1, FeedbackEventType.REMOVED_PAUSE_RESTORED),
                event(2, FeedbackEventType.RUN_FINALIZED, RunFinalizedPayload("r")),
            )
        ),
    )
    assert review.correction == CorrectionClass.KEEP_INSTEAD
    assert not review.restored_removed_pause
    assert restored.correction == CorrectionClass.RESTORE_REMOVED_PAUSE
    assert restored.final_action == PauseAction.KEEP
    assert restored.restored_removed_pause
    with pytest.raises(ValueError):
        derive_user_final_outcome(
            proposal(), log((event(1, FeedbackEventType.REMOVED_PAUSE_RESTORED),))
        )


def test_accept_revert_never_accepted_as_is_or_guessed_keep():
    events = (
        event(1, FeedbackEventType.PROPOSAL_ACCEPTED),
        event(2, FeedbackEventType.PROPOSAL_REVERTED),
        event(3, FeedbackEventType.RUN_FINALIZED, RunFinalizedPayload("r")),
    )
    out = derive_user_final_outcome(proposal(), log(events))
    assert out.reverted and out.accepted_as_is is False
    assert out.final_action is None and out.correction is None
    reaccept = events[:2] + (
        event(3, FeedbackEventType.PROPOSAL_ACCEPTED),
        event(4, FeedbackEventType.RUN_FINALIZED, RunFinalizedPayload("r")),
    )
    assert derive_user_final_outcome(proposal(), log(reaccept)).accepted_as_is is False


def test_unfinalized_or_no_decision_outcomes_are_unknown():
    for events in (
        (),
        (event(1, FeedbackEventType.PROPOSAL_ACCEPTED),),
        (event(1, FeedbackEventType.RUN_FINALIZED, RunFinalizedPayload("r")),),
    ):
        out = derive_user_final_outcome(proposal(), log(events))
        assert out.final_action is None and out.accepted_as_is is None


def test_timing_formulas_keep_manual_completion_and_blocked_idle_separate():
    metrics = derive_timing_metrics(run())
    assert metrics.human_active_time_ms == 150
    assert metrics.mandatory_attention_time_ms == 110
    assert metrics.assisted_human_cost_ms == 210
    assert metrics.correction_debt_ms == 80
    assert metrics.metric_definition_version == "evaluation-metrics-v1"
    assert metrics.run_id == "r"
    assert "AI_COMPUTATION" not in ActivityKind.__members__


def test_missing_timing_is_not_zero_and_coverage_is_required():
    supplied = run(durations=(10, 20, None, 40, 50, 60))
    assert derive_timing_metrics(supplied).human_active_time_ms is None
    assert derive_timing_metrics(supplied).correction_debt_ms is None
    missing = replace(
        run(),
        activities=tuple(
            a for a in run().activities if a.activity_kind != ActivityKind.AI_BLOCKED_IDLE
        ),
    )
    assert derive_timing_metrics(missing).human_active_time_ms == 150
    assert derive_timing_metrics(missing).assisted_human_cost_ms is None
    partial = replace(run(), run=replace(run().run, complete_activity_kinds=()))
    assert derive_timing_metrics(partial).human_active_time_ms is None
    zeros = derive_timing_metrics(run(durations=(0, 0, 0, 0, 0, 0)))
    assert zeros.human_active_time_ms == 0 and zeros.assisted_human_cost_ms == 0


def test_activity_sum_order_and_manual_estimates_retained():
    evidence = run()
    extra = replace(
        next(a for a in evidence.activities if a.activity_kind == ActivityKind.INSTRUCTION),
        activity_id="extra",
        duration_ms=7,
        measurement_source=MeasurementSource.MANUAL_ESTIMATE,
    )
    new = replace(evidence, activities=evidence.activities + (extra,))
    assert derive_timing_metrics(new).human_active_time_ms == 157
    assert derive_timing_metrics(new) == derive_timing_metrics(
        replace(new, activities=tuple(reversed(new.activities)))
    )


def test_paired_savings_and_rate():
    manual = run(RunMode.MANUAL_BASELINE, "manual", durations=(100, 100, 100, 100, 100, 0))
    assisted = run()
    out = derive_net_time_saved(manual, assisted)
    assert out.net_time_saved_ms == 290
    assert out.net_time_saved_rate == Fraction(29, 50)
    assert derive_net_time_saved(None, assisted).net_time_saved_ms is None
    assert derive_net_time_saved(manual, None).net_time_saved_rate is None
    zeros = run(RunMode.MANUAL_BASELINE, "zero", durations=(0, 0, 0, 0, 0, 0))
    negative = derive_net_time_saved(zeros, assisted)
    assert negative.net_time_saved_ms == -210
    assert negative.net_time_saved_rate is None


def test_scope_mode_and_case_mismatches_cannot_be_paired():
    manual = run(RunMode.MANUAL_BASELINE, "manual")
    with pytest.raises(ValueError):
        derive_net_time_saved(manual, run(scope="different"))
    with pytest.raises(ValueError):
        derive_net_time_saved(run(), run())
    other = RunEvidence(replace(run().run, case_ids=("other",)), ())
    with pytest.raises(ValueError):
        derive_net_time_saved(manual, other)


def test_safety_denominator_review_load_and_reference_range():
    r1 = record(proposal(PauseAction.REMOVE), reference(PauseAction.KEEP))
    r2 = record(
        proposal(PauseAction.REVIEW, case_id="c2", proposal_id="p2"),
        reference(PauseAction.REVIEW, "c2"),
    )
    r3 = record(proposal(case_id="c3", proposal_id="p3"), reference(case_id="c3"))
    metrics = derive_editorial_metrics((r1, r2, r3))
    assert metrics.critical_false_removal_count == 1
    assert metrics.critical_false_removal_denominator == 2
    assert metrics.critical_false_removal_rate == Fraction(1, 2)
    assert metrics.review_load == Fraction(1, 3)
    assert metrics.cases[2].tighten_range == TightenRange.IN_RANGE
    assert metrics.decision_interruptions is None
    assert metrics.reference_case_count == 3
    assert derive_editorial_metrics((r3, r1, r2)) == metrics


@pytest.mark.parametrize(
    "target,expected",
    [
        (19, TightenRange.OUT_OF_RANGE),
        (20, TightenRange.IN_RANGE),
        (40, TightenRange.IN_RANGE),
        (41, TightenRange.OUT_OF_RANGE),
    ],
)
def test_tighten_inclusive_range(target, expected):
    metrics = derive_editorial_metrics((record(proposal(target=target), reference()),))
    assert metrics.cases[0].tighten_range == expected
    assert metrics.critical_false_removal_rate is None


def test_interruptions_count_attention_not_review_items_and_empty_log_means_zero():
    events = (
        event(1, FeedbackEventType.ATTENTION_REQUESTED),
        event(2, FeedbackEventType.REVIEW_OPENED),
        event(3, FeedbackEventType.REVIEW_OPENED),
        event(4, FeedbackEventType.PROPOSAL_ACCEPTED),
        event(5, FeedbackEventType.RUN_FINALIZED, RunFinalizedPayload("r")),
    )
    metrics = derive_editorial_metrics((record(feedback=log(events)),))
    assert metrics.decision_interruptions == 1
    assert metrics.accepted_as_is_count == 1
    assert metrics.accepted_as_is_rate == Fraction(1)
    assert derive_editorial_metrics((record(feedback=log()),)).decision_interruptions == 0
    assert derive_editorial_metrics((record(),)).decision_interruptions is None


def test_missing_references_and_empty_denominators_are_not_false_safety_passes():
    metrics = derive_editorial_metrics((record(),))
    assert metrics.reference_case_count == 0 and metrics.missing_reference_count == 1
    assert metrics.critical_false_removal_rate is None
    assert metrics.unknown_outcome_count == 1
    empty = derive_editorial_metrics(())
    assert empty.review_load is None and empty.accepted_as_is_rate is None


def test_binding_and_activity_duplicates_reject():
    with pytest.raises(ValueError):
        record(ref=replace(reference(), case_id="other"))
    with pytest.raises(ValueError):
        record(
            ref=replace(
                reference(), assessment=replace(reference().assessment, original_pause_frames=101)
            )
        )
    with pytest.raises(ValueError):
        replace(run(), activities=run().activities + (run().activities[0],))
    with pytest.raises(ValueError):
        replace(run(), activities=(replace(run().activities[0], case_id="unknown"),))


@pytest.mark.parametrize("bad", [-1, True, 1.2, "1"])
def test_invalid_duration_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        replace(run().activities[0], duration_ms=bad)


def test_immutable_raw_records_and_deterministic_pure_metrics(monkeypatch):
    from davinci_ai_editor import authority, pause, safety
    from davinci_ai_editor.fake_timeline import FakeTimeline

    def forbidden(*args, **kwargs):
        raise AssertionError("No intelligence/authority/execution in evaluation")

    monkeypatch.setattr(pause, "classify_pause", forbidden)
    monkeypatch.setattr(authority, "transition", forbidden)
    monkeypatch.setattr(safety, "preflight", forbidden)
    monkeypatch.setattr(FakeTimeline, "apply", forbidden)
    raw = record(ref=reference(), feedback=log(final_events(PauseAction.KEEP)))
    before = repr(raw)
    result = derive_editorial_metrics((raw,))
    assert result == derive_editorial_metrics((raw,))
    assert repr(raw) == before
    with pytest.raises(FrozenInstanceError):
        raw.case.source_kind = SourceKind.PRODUCT_FEEDBACK
    with pytest.raises(FrozenInstanceError):
        raw.reference.assessment.preferred_retained_frames = 10
    with pytest.raises(FrozenInstanceError):
        result.review_load = Fraction(1)
    assert derive_net_time_saved(run(RunMode.MANUAL_BASELINE, "manual"), run()) is not None


def test_core_schema_needs_no_private_media_or_training_consent():
    forbidden = {
        "video",
        "audio",
        "transcript",
        "project_filename",
        "media_filename",
        "user_name",
        "training_consent",
    }
    for cls in (EvaluationCase, AIProposalSnapshot, FeedbackEvent, ActivityRecord, WorkflowRun):
        assert not {f.name for f in fields(cls)} & forbidden
    assert record(source=SourceKind.PRODUCT_FEEDBACK).case.pause_subject_ref == "opaque-pause"


@pytest.mark.parametrize(
    "action,critical,denominator",
    [
        (PauseAction.KEEP, True, 1),
        (PauseAction.REVIEW, True, 1),
        (PauseAction.TIGHTEN, False, 0),
        (PauseAction.REMOVE, False, 0),
    ],
)
def test_critical_false_removal_exact_reference_definition(action, critical, denominator):
    result = derive_editorial_metrics((record(proposal(PauseAction.REMOVE), reference(action)),))
    assert result.cases[0].critical_false_removal is critical
    assert result.critical_false_removal_denominator == denominator
    assert result.critical_false_removal_rate == (Fraction(1) if denominator else None)


def test_product_feedback_is_excluded_from_reference_denominator():
    metrics = derive_editorial_metrics(
        (record(proposal(PauseAction.REMOVE), source=SourceKind.PRODUCT_FEEDBACK),)
    )
    assert metrics.critical_false_removal_rate is None
    assert metrics.reference_case_count == metrics.missing_reference_count == 0
    assert metrics.cases[0].critical_false_removal is None


def test_ambiguous_reference_preserved_without_inventing_adjudication_or_tolerance():
    ref = replace(
        reference(),
        ambiguity=Ambiguity.AMBIGUOUS,
        adjudication_status=AdjudicationStatus.SINGLE_ANNOTATOR,
    )
    metrics = derive_editorial_metrics((record(ref=ref),))
    assert metrics.cases[0].reference_ambiguity == Ambiguity.AMBIGUOUS
    assert metrics.cases[0].reference_version == "ref-v1"
    assert "NEAR_RANGE" not in TightenRange.__members__


def test_annotation_binding_and_defensive_copy():
    annotation = ReferenceAnnotation("a", "c", "opaque", reference().assessment)
    items = [annotation]
    raw = replace(record(ref=reference()), annotations=items)
    items.clear()
    assert raw.annotations == (annotation,)
    with pytest.raises(ValueError):
        replace(raw, annotations=(annotation, annotation))
    with pytest.raises(ValueError):
        replace(raw, annotations=(replace(annotation, case_id="wrong"),))


def test_duplicate_event_ids_across_distinct_proposals_rejected():
    first = record(feedback=log((event(1, FeedbackEventType.ATTENTION_REQUESTED),)))
    p2 = proposal(case_id="c2", proposal_id="p2")
    second_log = FeedbackLog(
        "c2",
        "p2",
        (event(1, FeedbackEventType.ATTENTION_REQUESTED, case_id="c2", proposal_id="p2"),),
    )
    with pytest.raises(ValueError):
        derive_editorial_metrics((first, record(p2, feedback=second_log)))


def test_activity_and_case_collections_defensively_frozen():
    cases = ["c"]
    workflow = replace(run().run, case_ids=cases)
    cases.clear()
    activities = list(run().activities)
    evidence = RunEvidence(workflow, activities)
    activities.clear()
    assert evidence.run.case_ids == ("c",) and len(evidence.activities) == 6
    supplied_events = list(final_events(PauseAction.KEEP))
    feedback = log(supplied_events)
    supplied_events.clear()
    assert len(feedback.events) == 2


def test_unknown_and_incomplete_runs_keep_savings_unknown():
    assert derive_net_time_saved(None, None).net_time_saved_ms is None
    manual = run(RunMode.MANUAL_BASELINE, "manual", durations=(10, 20, None, 40, 50, 0))
    result = derive_net_time_saved(manual, run())
    assert result.net_time_saved_ms is None and result.net_time_saved_rate is None
    assert result.source_activities


@pytest.mark.parametrize(
    "change",
    [
        {"sequence_no": True},
        {"sequence_no": 0},
        {"actor": "EDITOR"},
        {"event_type": "REVIEW_OPENED"},
    ],
)
def test_invalid_event_metadata(change):
    with pytest.raises((TypeError, ValueError)):
        replace(event(1, FeedbackEventType.REVIEW_OPENED), **change)


def test_versions_are_explicit_not_arbitrary_metric_labels():
    with pytest.raises(ValueError):
        replace(record().case, schema_version="evaluation-v999")
    with pytest.raises(ValueError):
        replace(PRODUCER, feature_contract_version="")
    with pytest.raises((TypeError, ValueError)):
        replace(derive_timing_metrics(run()), metric_definition_version="fake-v9")
    newer = replace(reference(), reference_version="ref-v2")
    assert derive_editorial_metrics((record(ref=newer),)).cases[0].reference_version == "ref-v2"


def test_refresh_and_reference_updates_are_explicit_values_not_feedback_side_effects():
    old = record(ref=reference())
    changed = replace(
        old,
        proposal=replace(old.proposal, proposal_id="p2"),
        reference=replace(old.reference, reference_version="ref-v2"),
    )
    assert old.proposal.proposal_id == "p" and old.reference.reference_version == "ref-v1"
    assert changed.proposal.proposal_id == "p2"


def test_zero_attention_and_correction_require_explicit_coverage_not_inferred_absence():
    evidence = RunEvidence(run().run, ())
    metrics = derive_timing_metrics(evidence)
    assert metrics.human_active_time_ms is None
    assert metrics.mandatory_attention_time_ms is None
    assert metrics.correction_debt_ms is None


def test_restore_then_later_equal_result_retains_strong_safety_signal():
    p = proposal(PauseAction.REMOVE)
    events = (
        event(1, FeedbackEventType.REMOVED_PAUSE_RESTORED),
        event(2, FeedbackEventType.PROPOSAL_ACCEPTED),
        event(3, FeedbackEventType.RUN_FINALIZED, RunFinalizedPayload("r")),
    )
    result = derive_user_final_outcome(p, log(events))
    assert result.final_action == PauseAction.REMOVE and result.accepted_as_is is False
    assert result.correction == CorrectionClass.RESTORE_REMOVED_PAUSE
