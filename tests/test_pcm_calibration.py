"""TEST_ONLY_SUPPORT: invented metadata, labels and generated PCM, no real data."""

import ast
import inspect
import json
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from functools import cache
from itertools import permutations
from pathlib import Path
from struct import pack

import pytest
from test_observation_pipeline import REF, inputs

from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.pause_acoustic_producer import AcousticConfig, PcmInput
from davinci_ai_editor.temporal_mapping import FrameRate, SourceFrameRange
from tools import pcm_calibration as c

H = "a" * 64
J = "b" * 64
GOOD_COUNTS = c.Counts(tp=1500, tn=1500)


def acquisition() -> c.AcquisitionManifest:
    first = c.Extraction(
        "operator-a",
        "synthetic-tool",
        "v1",
        H,
        (("start", "0"), ("end", "1440000")),
        H,
        J,
        2880000,
        H,
    )
    return c.AcquisitionManifest(
        "synthetic-asset",
        "synthetic-session",
        "synthetic-permission",
        "2026-12-01T00:00:00+09:00",
        "synthetic-retention",
        "operator-a",
        "2026-10-01T12:00:00+09:00",
        2880044,
        H,
        "UNKNOWN",
        ("UNKNOWN",),
        "synthetic-container",
        "synthetic-header",
        "stream-0",
        ("mono",),
        0,
        48000,
        16,
        True,
        "LE",
        1440000,
        0,
        1440000,
        0,
        0,
        0,
        750,
        FrameRate(25, 1),
        "synthetic-origin",
        first,
        replace(first, operator_ref="reviewer-b"),
        "synthetic-review",
        "BYTE_IDENTICAL",
        "2026-09-01T00:00:00+09:00",
        "reviewer-b",
    )


def dataset() -> tuple[c.Session, ...]:
    return tuple(
        c.Session(
            f"synthetic-session-{i}",
            stratum,
            split,
            (f"take-{i}", f"lineage-{i}"),
            tuple(
                c.Window(
                    f"window-{i}-{j}",
                    c.digest(f"original-{i}"),
                    j * 1440000,
                    (j + 1) * 1440000,
                    48000,
                    0,
                )
                for j in range(4)
            ),
        )
        for i, (split, stratum) in enumerate((s, t) for s in c.Split for t in c.Stratum)
    )


def annotation(reviewer: str = "r1", regions: tuple[c.Region, ...] | None = None) -> c.Annotation:
    return c.Annotation(
        "window",
        H,
        reviewer,
        "v1",
        "rubric-v1",
        "blind-pre-detector",
        regions or (c.Region(0, 3840, c.Label.QUIET),),
    )


@cache
def freeze() -> c.Freeze:
    sessions = dataset()
    annotations = tuple(
        c.Annotation(
            w.window_ref,
            c.digest(w),
            reviewer,
            "v1",
            "rubric-v1",
            "blind",
            (c.Region(w.sample_start, w.sample_end, c.Label.QUIET),),
        )
        for session in sessions
        for w in session.windows
        for reviewer in ("r1", "r2")
    )
    return c.freeze_inputs("synthetic-experiment", sessions, annotations, "rubric-v1", "none", H, J)


def scores(
    config: AcousticConfig, split: c.Split, counts: c.Counts = GOOD_COUNTS
) -> c.ConfigEvaluation:
    frozen = freeze()
    selected = tuple(s for s in frozen.sessions if s.split == split)
    windows = {w.window_ref for s in selected for w in s.windows}
    return c.ConfigEvaluation(
        config,
        split,
        tuple(c.SessionScore(s.session_ref, s.stratum, s.split, counts) for s in selected),
        frozen,
        selected,
        tuple(a for a in frozen.annotations if a.window_ref in windows),
    )


def calibrated() -> c.CalibrationReport:
    return c.evaluate_calibration(freeze(), scores)


def holdout_use(report: c.CalibrationReport) -> c.HoldoutUse:
    assert report.selected is not None
    return c.HoldoutUse(
        "synthetic-access",
        c.digest(freeze()),
        freeze().experiment_ref,
        c.policy_digest(),
        report.selected.config_ref,
        freeze().holdout_lineages,
    )


def test_acquisition_synthetic_valid_unknown_processing_is_explicit() -> None:
    assert (
        c.validate_acquisition(acquisition(), experiment_use_at="2026-10-14T12:00:00+09:00") == ()
    )
    with pytest.raises(FrozenInstanceError):
        field_name = "selected_channel"
        setattr(acquisition(), field_name, 1)


@pytest.mark.parametrize(
    "bad,code",
    [
        (replace(acquisition(), permission_ref="UNKNOWN"), "PROVENANCE_QUARANTINE"),
        (replace(acquisition(), origin_correspondence_ref=""), "PROVENANCE_QUARANTINE"),
        (replace(acquisition(), acquired_at="2026-10-01T12:00:00"), "TIMEZONE_MISSING"),
        (replace(acquisition(), acquired_at="bad"), "TIMESTAMP_INVALID"),
        (
            replace(acquisition(), permission_expiry="2026-01-01T00:00:00+09:00"),
            "PERMISSION_EXPIRED_AT_ACQUISITION",
        ),
        (replace(acquisition(), selected_channel=1), "CHANNEL_UNCLEAR"),
        (replace(acquisition(), bit_depth=24), "PCM_FORMAT_UNSUPPORTED"),
        (replace(acquisition(), sample_start=1), "SAMPLE_ORIGIN_MISMATCH"),
        (replace(acquisition(), source_end=749), "BYTE_COUNT_MISMATCH"),
        (replace(acquisition(), independent_extraction=None), "INDEPENDENT_EXTRACTION_MISSING"),
        (
            replace(acquisition(), independent_extraction=acquisition().extraction),
            "INDEPENDENT_EXTRACTION_MISMATCH",
        ),
        (
            replace(
                acquisition(),
                extraction=replace(acquisition().extraction, original_reread_sha256=J),
            ),
            "ORIGINAL_CHANGED_OR_MISMATCHED",
        ),
        (
            replace(
                acquisition(),
                independent_extraction=replace(
                    acquisition().extraction, operator_ref="r2", output_sha256=H
                ),
            ),
            "INDEPENDENT_EXTRACTION_MISMATCH",
        ),
    ],
)
def test_acquisition_fail_closed(bad: c.AcquisitionManifest, code: str) -> None:
    assert code in {
        f.code for f in c.validate_acquisition(bad, experiment_use_at="2026-10-14T12:00:00+09:00")
    }


@pytest.mark.parametrize("fps,k", [(24, 2000), (25, 1920), (30, 1600)])
def test_exact_support_profiles(fps: int, k: int) -> None:
    assert c.samples_per_frame(48000, FrameRate(fps, 1)) == k


def test_nonintegral_profile_refused_no_rounding() -> None:
    with pytest.raises(c.Refusal, match="NON_INTEGRAL"):
        c.samples_per_frame(44100, FrameRate(24, 1))
    with pytest.raises(c.Refusal, match="INVALID_SAMPLE_RATE"):
        c.samples_per_frame(0, FrameRate(25, 1))


def test_exact_dataset_allocation_and_caps() -> None:
    assert c.validate_splits(dataset()) == ()
    assert c.validate_splits(dataset()[:-1])
    assert c.validate_splits(dataset() + (replace(dataset()[0], session_ref="extra"),))


@pytest.mark.parametrize("shared", ["take", "original", "derivative", "channel"])
def test_leakage_even_with_new_session_names(shared: str) -> None:
    sessions = list(dataset())
    first, other = sessions[0], sessions[4]
    if shared in ("take", "derivative"):
        sessions[4] = replace(other, lineage_refs=first.lineage_refs)
    else:
        sessions[4] = replace(
            other,
            windows=tuple(
                replace(
                    w,
                    original_sha256=first.windows[0].original_sha256,
                    selected_channel=1 if shared == "channel" else 0,
                )
                for w in other.windows
            ),
        )
    assert "SESSION_LEAKAGE" in {f.code for f in c.validate_splits(tuple(sessions))}


def test_overlap_not_independent_and_missing_lineage() -> None:
    s = dataset()[0]
    bad = replace(
        s,
        lineage_refs=(),
        windows=(s.windows[0], replace(s.windows[0], window_ref="copy", selected_channel=1)),
    )
    found = {f.code for f in c.validate_splits((bad,), complete=False)}
    assert {"OVERLAPPING_WINDOWS", "LINEAGE_UNDECLARED"} <= found


def test_truth_requires_whole_frame_agreement_and_retains_original_digests() -> None:
    first = annotation(
        regions=(c.Region(0, 1920, c.Label.QUIET), c.Region(1920, 3840, c.Label.ACTIVITY))
    )
    second = replace(first, reviewer_ref="r2")
    truth = c.derive_truth(first, second, 0, 3840, 48000, FrameRate(25, 1))
    assert truth.labels == (c.Label.QUIET, c.Label.ACTIVITY)
    assert truth.annotation_digests == (c.digest(first), c.digest(second))


def test_disagreement_and_boundary_crossing_are_ambiguous() -> None:
    boundary = annotation(
        "r2", (c.Region(0, 1000, c.Label.ACTIVITY), c.Region(1000, 3840, c.Label.ACTIVITY))
    )
    truth = c.derive_truth(annotation(), boundary, 0, 3840, 48000, FrameRate(25, 1))
    assert truth.labels == (c.Label.AMBIGUOUS, c.Label.AMBIGUOUS)
    assert (truth.boundary_frames, truth.disagreement_frames) == (1, 1)


def test_exclusions_remain_distinct_from_ambiguous_and_negative() -> None:
    truth = c.derive_truth(
        annotation(), annotation("r2"), 0, 3840, 48000, FrameRate(25, 1), exclusions=((0, 1),)
    )
    assert truth.labels == (c.Label.EXCLUDED, c.Label.QUIET)


@pytest.mark.parametrize(
    "bad",
    [
        annotation("r1"),
        replace(annotation("r2"), pcm_sha256=J),
        replace(annotation("r2"), blindness_ref=""),
        annotation("r2", (c.Region(1, 3840, c.Label.QUIET),)),
        annotation("r2", (c.Region(0, 3840, c.Label.EXCLUDED),)),
    ],
)
def test_invalid_annotation_refused(bad: c.Annotation) -> None:
    with pytest.raises(c.Refusal):
        c.derive_truth(annotation(), bad, 0, 3840, 48000, FrameRate(25, 1))


def test_frame_metrics_exact_denominators() -> None:
    counts = c.frame_counts(
        (
            c.Label.QUIET,
            c.Label.ACTIVITY,
            c.Label.QUIET,
            c.Label.ACTIVITY,
            c.Label.AMBIGUOUS,
            c.Label.EXCLUDED,
        ),
        (True, True, False, False, True, True),
    )
    assert counts == c.Counts(1, 1, 1, 1, 1, 1)
    assert counts.rates == c.Rates(*(Fraction(1, 2) for _ in range(4)))
    assert counts.ambiguous_percentage == 20
    assert counts.analyzed_seconds == Fraction(6, 25)
    assert c.Counts().rates == c.Rates(None, None, None, None)


def test_frame_vector_mismatch_and_negative_counts() -> None:
    with pytest.raises(c.Refusal):
        c.frame_counts((c.Label.QUIET,), ())
    with pytest.raises(c.Refusal):
        c.Counts(fp=-1)


def test_session_macro_differs_from_micro_and_strata_retained() -> None:
    rows = (
        c.SessionScore("a", c.Stratum.QUIET_INDOOR, c.Split.CALIBRATION, c.Counts(1, 1, 0, 1)),
        c.SessionScore("b", c.Stratum.BACKGROUND_NOISE, c.Split.CALIBRATION, c.Counts(9, 0, 1, 9)),
    )
    micro, macro, strata = c.aggregate(rows)
    assert micro.rates.precision == Fraction(10, 11)
    assert macro.precision == Fraction(3, 4)
    assert len(strata) == 4
    assert c.aggregate((replace(rows[0], counts=c.Counts()), rows[1]))[1].precision is None


def test_bootstrap_resamples_sessions_reproducibly_not_frames() -> None:
    rows = scores(c.calibration_grid()[0], c.Split.CALIBRATION).sessions
    assert c.bootstrap_sessions(rows) == c.bootstrap_sessions(tuple(reversed(rows)))
    assert dict(c.bootstrap_sessions(rows))["precision"] == c.Interval(
        Fraction(1), Fraction(1), 1000, 1000
    )
    empty = tuple(replace(r, counts=c.Counts()) for r in rows)
    assert dict(c.bootstrap_sessions(empty))["precision"] == c.Interval(None, None, 0, 1000)


def test_event_matching_split_tie_and_boundaries() -> None:
    result = c.match_events((c.Event("r", 0, 10),), (c.Event("p2", 5, 10), c.Event("p1", 0, 5)))
    assert (result.tp, result.fp, result.fn) == (1, 1, 0)
    assert result.matches == (("r", "p1"),)
    assert result.start_errors == (0,) and result.end_errors == (-5,)
    assert result.median_absolute_error == Fraction(5, 2)
    assert result.p95_absolute_error == result.max_absolute_error == 5
    assert (result.split_count, result.merge_count) == (1, 0)


def test_event_merge_empty_and_iou_below_half() -> None:
    assert (
        c.match_events(
            (c.Event("a", 0, 5), c.Event("b", 5, 10)), (c.Event("p", 0, 10),)
        ).merge_count
        == 1
    )
    result = c.match_events((c.Event("r", 0, 10),), (c.Event("p", 7, 17),))
    assert (result.tp, result.fp, result.fn) == (0, 1, 1)
    assert result.median_absolute_error is None
    assert c.match_events((), ()).max_absolute_error is None


def test_event_matches_maximum_weight_not_first_overlap() -> None:
    result = c.match_events((c.Event("r", 0, 10),), (c.Event("a", 0, 4), c.Event("b", 4, 10)))
    assert result.matches == (("r", "b"),)
    for perm in permutations((c.Event("a", 0, 4), c.Event("b", 4, 10))):
        assert c.match_events((c.Event("r", 0, 10),), perm) == result


def test_event_overlap_or_duplicate_is_refused() -> None:
    with pytest.raises(c.Refusal):
        c.match_events((c.Event("r", 0, 10), c.Event("r", 5, 15)), ())


def test_freeze_requires_full_valid_blind_dataset_and_is_order_independent() -> None:
    sessions = dataset()
    annotations = tuple(
        c.Annotation(
            w.window_ref,
            H,
            reviewer,
            "v1",
            "rubric",
            "blind",
            (c.Region(w.sample_start, w.sample_end, c.Label.AMBIGUOUS),),
        )
        for s in sessions
        for w in s.windows
        for reviewer in ("r1", "r2")
    )
    frozen = c.freeze_inputs("synthetic", sessions, annotations, "rubric", "none", H, J)
    assert frozen == c.freeze_inputs(
        "synthetic", tuple(reversed(sessions)), tuple(reversed(annotations)), "rubric", "none", H, J
    )
    with pytest.raises(c.Refusal):
        c.freeze_inputs("synthetic", sessions, annotations[:-1], "rubric", "none", H, J)


def test_all_40_configs_calibration_only_ties_preregistered() -> None:
    report = calibrated()
    assert len(report.evaluations) == 40
    assert {r.split for r in report.evaluations} == {c.Split.CALIBRATION}
    assert report.selected is not None
    assert (report.selected.mean_square_threshold, report.selected.minimum_silent_frames) == (0, 10)
    assert all(
        r.config.neighborhood_source_frames == 250 and r.config.minimum_neighbors == 3
        for r in report.evaluations
    )


def test_rejected_configs_retained_and_no_acceptable_config() -> None:
    report = c.evaluate_calibration(
        freeze(), lambda cfg, split: scores(cfg, split, c.Counts(0, 0, 1500, 1500))
    )
    assert report.selected is None and report.result == "NO_ACCEPTABLE_CONFIG"
    assert len(report.evaluations) == 40


def test_recall_selection_precedes_threshold_tie() -> None:
    def evaluate(cfg: AcousticConfig, split: c.Split) -> c.ConfigEvaluation:
        return scores(
            cfg,
            split,
            c.Counts(
                1500 if cfg.mean_square_threshold == 64 else 1200,
                0,
                0 if cfg.mean_square_threshold == 64 else 300,
                1500,
            ),
        )

    result = c.evaluate_calibration(freeze(), evaluate)
    assert result.selected is not None and result.selected.mean_square_threshold == 64


def test_changed_policy_and_wrong_evaluator_refused() -> None:
    with pytest.raises(c.Refusal, match="POLICY_CHANGED"):
        c.evaluate_calibration(replace(freeze(), policy_sha256=H), scores)
    with pytest.raises(c.Refusal, match="EVALUATOR_MISMATCH"):
        c.evaluate_calibration(freeze(), lambda cfg, split: scores(cfg, c.Split.VALIDATION))


@pytest.mark.parametrize(
    "counts,expected",
    [
        (c.Counts(1500, 0, 0, 1500), "VALIDATION_CRITERIA_MET"),
        (c.Counts(1199, 0, 301, 1500), "VALIDATION_FAIL"),
        (c.Counts(1500, 16, 0, 1484), "VALIDATION_FAIL"),
        (c.Counts(0, 0, 1500, 1500), "VALIDATION_FAIL"),
    ],
)
def test_validation_exact_gates(counts: c.Counts, expected: str) -> None:
    report = calibrated()
    assert report.selected is not None
    assert (
        c.evaluate_validation(report, scores(report.selected, c.Split.VALIDATION, counts))
        == expected
    )


def test_validation_wrong_config_or_incomplete_session_scores_refused() -> None:
    report = calibrated()
    with pytest.raises(c.Refusal, match="EXACT_SELECTED"):
        c.evaluate_validation(report, scores(c.calibration_grid()[0], c.Split.VALIDATION))
    assert report.selected is not None
    with pytest.raises(c.Refusal, match="COVERAGE_MISMATCH"):
        c.evaluate_validation(
            report, scores(report.selected, c.Split.VALIDATION, c.Counts(1, 0, 0, 1))
        )


def test_holdout_attempt_audit_rejects_reuse_even_changed_experiment() -> None:
    report = calibrated()
    assert report.selected is not None
    use = holdout_use(report)
    valid = scores(report.selected, c.Split.VALIDATION)
    assert c.audit_holdout_use(use, freeze(), report, valid, ()) == ()
    for prior in (use, replace(use, access_ref="other", experiment_ref="other")):
        assert "HOLDOUT_ALREADY_CONSUMED" in {
            f.code for f in c.audit_holdout_use(use, freeze(), report, valid, (prior,))
        }
    assert c.audit_holdout_use(replace(use, policy_sha256=H), freeze(), report, valid, ())
    assert c.audit_holdout_use(
        use,
        freeze(),
        report,
        scores(report.selected, c.Split.VALIDATION, c.Counts(1, 100, 1499, 1400)),
        (),
    )


@pytest.mark.parametrize(
    "counts,expected",
    [
        (c.Counts(1500, 0, 0, 1500), "HOLDOUT_CRITERIA_MET_NOT_QUALIFICATION"),
        (c.Counts(100, 0, 0, 2900), "INSUFFICIENT_EVIDENCE"),
        (c.Counts(1000, 0, 0, 1000, 1000), "INSUFFICIENT_EVIDENCE"),
        (c.Counts(1100, 0, 400, 1500), "HOLDOUT_FAIL"),
    ],
)
def test_holdout_gate_is_math_not_qualification(counts: c.Counts, expected: str) -> None:
    report = calibrated()
    assert report.selected is not None
    assert (
        c.evaluate_holdout(scores(report.selected, c.Split.HOLDOUT, counts), holdout_use(report))
        == expected
    )


def test_real_producer_reused_with_generated_pcm_and_synthetic_native_binding() -> None:
    native, link, _ = inputs()
    rate = FrameRate(25, 1)
    placement = replace(link.placement, source_rate=rate, timeline_rate=rate)
    native = replace(native, placements=(placement,), timeline_rate=rate)
    link = replace(
        link,
        placement=placement,
        binding=replace(link.binding, source_rate=rate, timeline_rate=rate),
    )
    pcm = PcmInput(
        pack("<h", 0) * 1920 * 2 + pack("<h", 1000) * 1920 * 2,
        "PCM16LE",
        48000,
        1,
        0,
        SourceFrameRange(FrameRange(0, 4)),
        "synthetic-buffer",
        link,
    )
    truth = (c.Label.QUIET, c.Label.QUIET, c.Label.ACTIVITY, c.Label.ACTIVITY)
    first = c.score_pcm_window(pcm, c.calibration_grid()[0], native, REF, truth)
    second = c.score_pcm_window(
        replace(pcm, data=bytes(pcm.data or b"")), c.calibration_grid()[0], native, REF, truth
    )
    assert first == second == c.Counts(tp=2, tn=2)
    with pytest.raises(c.Refusal):
        c.score_pcm_window(replace(pcm, data=None), c.calibration_grid()[0], native, REF, truth)


def test_reproduction_comparison_requires_independent_claim_and_matching_outputs() -> None:
    first = c.Reproduction("process-a", H, J, 0, "config", H, J, H)
    second = replace(first, process_ref="process-b")
    assert c.compare_reproduction(first, second) == ()
    assert c.compare_reproduction(first, first)
    assert c.compare_reproduction(first, replace(second, selected_channel=1))
    assert c.compare_reproduction(first, replace(second, metrics_sha256=H))


@pytest.mark.parametrize("gate", ["G1", "G2", "G3", "G4", "G5", "G6", "FAILURE_CASES"])
def test_receipt_serialization_is_synthetic_bounded_and_reproducible(gate: str) -> None:
    receipt = c.GateReceipt(
        gate,
        "synthetic-receipt",
        (("input", H),),
        (("precision", Fraction(1, 2)), ("empty", None)),
        (c.Finding("MISSING", "synthetic-input"),),
    )
    data = json.loads(c.receipt_json(receipt))
    assert data["receipt"]["qualification"] == "TEST_ONLY_SUPPORT"
    assert data["sha256"] == c.digest(receipt)
    assert c.receipt_json(receipt) == c.receipt_json(receipt)
    with pytest.raises(c.Refusal, match="PROMOTION_FORBIDDEN"):
        replace(receipt, qualification="PASS")


def test_receipt_exclusive_write_preserves_failed_attempt(tmp_path: Path) -> None:
    receipt = c.GateReceipt(
        "G5", "synthetic-failure", (), (), (c.Finding("VALIDATION_FAIL", "experiment"),)
    )
    path = tmp_path / "receipt.json"
    c.write_receipt(path, receipt)
    with pytest.raises(FileExistsError):
        c.write_receipt(path, replace(receipt, findings=()))
    assert path.read_text() == c.receipt_json(receipt)


def test_raw_pcm_and_noncanonical_payload_refused() -> None:
    with pytest.raises(c.Refusal):
        c.digest(b"raw audio")
    with pytest.raises(c.Refusal):
        c.digest(0.5)
    with pytest.raises(c.Refusal):
        c.GateReceipt("G2", "path/identity", (), (), ())


def test_architecture_no_media_read_native_network_or_production_modification() -> None:
    tree = ast.parse(inspect.getsource(c))
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(
        any(
            word in name
            for word in (
                "authority",
                "transaction",
                "execution_ir",
                "runtime",
                "requests",
                "http",
                "socket",
            )
        )
        for name in imports
    )
    calls = [node.func for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not any(isinstance(f, ast.Name) and f.id == "round" for f in calls)
    assert not any(
        isinstance(f, ast.Attribute) and f.attr in ("read_bytes", "read_text", "unlink")
        for f in calls
    )
    assert "classify_pause" not in inspect.getsource(c)


def test_acquisition_independent_review_must_be_explicit() -> None:
    bad = replace(acquisition(), independent_review_result="UNKNOWN")
    assert "INDEPENDENT_REVIEW_UNQUALIFIED" in {
        f.code for f in c.validate_acquisition(bad, experiment_use_at="2026-10-14T12:00:00+09:00")
    }


def test_validation_inclusive_thresholds_and_precision_failure() -> None:
    report = calibrated()
    assert report.selected is not None
    boundary = scores(report.selected, c.Split.VALIDATION, c.Counts(1200, 15, 300, 1485))
    assert c.evaluate_validation(report, boundary) == "VALIDATION_CRITERIA_MET"
    low_precision = scores(report.selected, c.Split.VALIDATION, c.Counts(10, 1, 0, 2989))
    assert c.evaluate_validation(report, low_precision) == "VALIDATION_FAIL"


def test_stratum_failure_cannot_hide_in_good_overall_result() -> None:
    report = calibrated()
    assert report.selected is not None
    result = scores(report.selected, c.Split.HOLDOUT)
    result = replace(
        result,
        sessions=(
            replace(result.sessions[0], counts=c.Counts(2750, 16, 0, 234)),
            *result.sessions[1:],
        ),
    )
    assert result.counts.rates.fpr is not None and result.counts.rates.fpr < Fraction(1, 100)
    assert c.evaluate_holdout(result, holdout_use(report)) == "HOLDOUT_FAIL"


def test_changed_rubric_or_exclusion_digest_invalidates_old_holdout_use() -> None:
    report = calibrated()
    assert report.selected is not None
    for changed in (replace(freeze(), rubric_sha256=J), replace(freeze(), exclusion_sha256=H)):
        issues = c.audit_holdout_use(
            holdout_use(report), changed, report, scores(report.selected, c.Split.VALIDATION), ()
        )
        assert "HOLDOUT_FREEZE_OR_POLICY_MISMATCH" in {i.code for i in issues}


def test_holdout_without_selected_config_is_bounded_refusal() -> None:
    report = replace(calibrated(), selected=None, result="NO_ACCEPTABLE_CONFIG")
    use = holdout_use(calibrated())
    issues = c.audit_holdout_use(
        use, freeze(), report, scores(c.calibration_grid()[0], c.Split.VALIDATION), ()
    )
    assert {i.code for i in issues} == {
        "HOLDOUT_FREEZE_OR_POLICY_MISMATCH",
        "HOLDOUT_BLOCKED_BY_VALIDATION",
    }


def test_annotation_origin_mismatch_is_not_rounded() -> None:
    with pytest.raises(c.Refusal, match="NON_ALIGNED"):
        c.derive_truth(
            annotation(), annotation("r2"), 0, 3840, 48000, FrameRate(25, 1), sample_origin=1
        )


def test_receipt_rejects_duplicate_keys_and_matches_schema_example() -> None:
    with pytest.raises(c.Refusal, match="DUPLICATE_KEY"):
        c.GateReceipt("G4", "synthetic", (), (("tp", 1), ("tp", 2)), ())
    folder = Path(__file__).parent / "fixtures" / "pcm_calibration"
    schema = json.loads((folder / "receipt.schema.json").read_text())
    example = json.loads((folder / "synthetic_receipt.json").read_text())
    receipt = c.GateReceipt(
        "G5",
        "synthetic-failure",
        (("input", H),),
        (("tp", 0), ("precision", None)),
        (c.Finding("NO_ACCEPTABLE_CONFIG", "synthetic-experiment"),),
    )
    assert example == json.loads(c.receipt_json(receipt))
    assert set(example) == set(schema["required"])
    assert set(example["receipt"]) == set(schema["properties"]["receipt"]["required"])


def test_independent_synthetic_metric_recomputation_not_report_copy() -> None:
    truth = (c.Label.QUIET, c.Label.ACTIVITY, c.Label.QUIET, c.Label.AMBIGUOUS)
    predicted = (True, True, False, True)
    original = c.frame_counts(truth, predicted)
    # Independent straight counting in the test, not a second call reading its report.
    reproduced = c.Counts(
        sum(t == c.Label.QUIET and p for t, p in zip(truth, predicted)),
        sum(t == c.Label.ACTIVITY and p for t, p in zip(truth, predicted)),
        sum(t == c.Label.QUIET and not p for t, p in zip(truth, predicted)),
        sum(t == c.Label.ACTIVITY and not p for t, p in zip(truth, predicted)),
        sum(t == c.Label.AMBIGUOUS for t in truth),
    )
    assert reproduced == original


@pytest.mark.parametrize(
    "used",
    [
        "2026-12-01T00:00:00+09:00",
        "2027-01-01T00:00:00+09:00",
        "2026-09-30T00:00:00+09:00",
        "2026-10-14T12:00:00",
        "UNKNOWN",
    ],
)
def test_permission_requires_valid_declared_experiment_time(used: str) -> None:
    assert c.validate_acquisition(acquisition(), experiment_use_at=used)


def test_permission_timezone_equivalence_and_not_yet_valid() -> None:
    assert not c.validate_acquisition(acquisition(), experiment_use_at="2026-10-14T03:00:00+00:00")
    bad = replace(acquisition(), permission_valid_from="2026-11-01T00:00:00+09:00")
    assert c.validate_acquisition(bad, experiment_use_at="2026-10-14T12:00:00+09:00")


@pytest.mark.parametrize("reviewer", ["operator-a", "different-reviewer", "UNKNOWN", ""])
def test_independent_review_identity_must_match_second_extractor(reviewer: str) -> None:
    bad = replace(acquisition(), independent_reviewer_ref=reviewer)
    issues = c.validate_acquisition(bad, experiment_use_at="2026-10-14T12:00:00+09:00")
    assert "INDEPENDENT_REVIEWER_MISMATCH" in {i.code for i in issues}


def test_freeze_rejects_reviewer_substitution_and_forged_digests() -> None:
    frozen = freeze()
    changed = (
        replace(frozen.annotations[0], reviewer_ref="third-reviewer"),
        *frozen.annotations[1:],
    )
    with pytest.raises(c.Refusal, match="INCONSISTENT_INDEPENDENT_REVIEWERS"):
        c.freeze_inputs("other", frozen.sessions, changed, frozen.rubric_ref, "none", H, J)
    with pytest.raises(c.Refusal, match="FREEZE_INPUT_DIGEST_MISMATCH"):
        replace(frozen, split_digest=H)
    with pytest.raises(c.Refusal, match="FREEZE_INPUT_DIGEST_MISMATCH"):
        replace(frozen, annotation_digest=J)


@pytest.mark.parametrize("split", list(c.Split))
@pytest.mark.parametrize(
    "tamper", ["foreign-session", "channel", "pcm", "annotation", "omission", "freeze"]
)
def test_every_evaluation_gate_checks_exact_frozen_inputs(split: c.Split, tamper: str) -> None:
    report = calibrated()
    assert report.selected is not None
    cfg = c.calibration_grid()[0] if split == c.Split.CALIBRATION else report.selected
    result = scores(cfg, split)
    if tamper == "foreign-session":
        result = replace(
            result,
            sessions=(
                replace(result.sessions[0], session_ref="foreign-session"),
                *result.sessions[1:],
            ),
        )
    elif tamper == "channel":
        session = result.input_sessions[0]
        changed = replace(
            session, windows=(replace(session.windows[0], selected_channel=1), *session.windows[1:])
        )
        result = replace(result, input_sessions=(changed, *result.input_sessions[1:]))
    elif tamper in ("pcm", "annotation"):
        first = result.input_annotations[0]
        changed_annotation = (
            replace(first, pcm_sha256=H) if tamper == "pcm" else replace(first, version="changed")
        )
        result = replace(
            result, input_annotations=(changed_annotation, *result.input_annotations[1:])
        )
    elif tamper == "omission":
        result = replace(result, input_sessions=result.input_sessions[:-1])
    else:
        result = replace(result, freeze=replace(freeze(), experiment_ref="other-experiment"))
    with pytest.raises(c.Refusal, match="FROZEN_INPUT_MISMATCH"):
        if split == c.Split.CALIBRATION:
            c.evaluate_calibration(
                freeze(), lambda config, requested: replace(result, config=config)
            )
        elif split == c.Split.VALIDATION:
            c.evaluate_validation(report, result)
        else:
            c.evaluate_holdout(result, holdout_use(report))


def test_freeze_roundtrip_ordering_remains_valid_not_object_identity() -> None:
    frozen = freeze()
    rebuilt = c.freeze_inputs(
        frozen.experiment_ref,
        tuple(reversed(frozen.sessions)),
        tuple(reversed(frozen.annotations)),
        frozen.rubric_ref,
        frozen.exclusion_ref,
        frozen.rubric_sha256,
        frozen.exclusion_sha256,
    )
    assert rebuilt is not frozen and c.digest(rebuilt) == c.digest(frozen)
    report = c.evaluate_calibration(rebuilt, scores)
    assert report.selected is not None
    result = replace(scores(report.selected, c.Split.VALIDATION), freeze=rebuilt)
    assert c.evaluate_validation(report, result) == "VALIDATION_CRITERIA_MET"


@pytest.mark.parametrize("field", ["independent_review_ref", "independent_reviewer_ref"])
@pytest.mark.parametrize("identity", ["recorder-only", "operator-a"])
def test_review_rejects_recorder_and_first_extractor_separately(field: str, identity: str) -> None:
    manifest = replace(acquisition(), recorder_ref="recorder-only")
    bad = (
        replace(manifest, independent_review_ref=identity)
        if field == "independent_review_ref"
        else replace(manifest, independent_reviewer_ref=identity)
    )
    assert "INDEPENDENT_REVIEWER_MISMATCH" in {
        f.code for f in c.validate_acquisition(bad, experiment_use_at="2026-10-14T12:00:00+09:00")
    }


@pytest.mark.parametrize("split", [c.Split.CALIBRATION, c.Split.HOLDOUT])
def test_unrelated_complete_dataset_with_perfect_scores_is_refused(split: c.Split) -> None:
    report = calibrated()
    assert report.selected is not None
    foreign_sessions = tuple(
        replace(
            s,
            session_ref="foreign-" + s.session_ref,
            lineage_refs=tuple("foreign-" + ref for ref in s.lineage_refs),
            windows=tuple(
                replace(w, window_ref="foreign-" + w.window_ref, original_sha256=c.digest(w))
                for w in s.windows
            ),
        )
        for s in freeze().sessions
    )
    foreign_annotations = tuple(
        replace(a, window_ref="foreign-" + a.window_ref, pcm_sha256=c.digest(a))
        for a in freeze().annotations
    )
    # Both reviewers must refer to the same foreign PCM; their identities remain distinct.
    foreign_annotations = tuple(
        replace(a, pcm_sha256=c.digest(a.window_ref)) for a in foreign_annotations
    )
    foreign = c.freeze_inputs(
        "foreign-experiment", foreign_sessions, foreign_annotations, "rubric-v1", "none", H, J
    )
    selected = tuple(s for s in foreign.sessions if s.split == split)
    windows = {w.window_ref for s in selected for w in s.windows}
    result = c.ConfigEvaluation(
        report.selected,
        split,
        tuple(c.SessionScore(s.session_ref, s.stratum, split, GOOD_COUNTS) for s in selected),
        foreign,
        selected,
        tuple(a for a in foreign.annotations if a.window_ref in windows),
    )
    with pytest.raises(c.Refusal, match="FROZEN_INPUT_MISMATCH|HOLDOUT_USE_MISMATCH"):
        if split == c.Split.CALIBRATION:
            c.evaluate_calibration(freeze(), lambda config, requested: replace(result, config=config))
        else:
            c.evaluate_holdout(result, holdout_use(report))


def test_validation_rejects_calibration_membership_even_with_relabelled_scores() -> None:
    report = calibrated()
    assert report.selected is not None
    calibration = scores(report.selected, c.Split.CALIBRATION)
    relabelled = replace(
        calibration,
        split=c.Split.VALIDATION,
        sessions=tuple(replace(s, split=c.Split.VALIDATION) for s in calibration.sessions),
    )
    with pytest.raises(c.Refusal, match="FROZEN_INPUT_MISMATCH"):
        c.evaluate_validation(report, relabelled)


@pytest.mark.parametrize("split", list(c.Split))
@pytest.mark.parametrize("changed", ["source-digest", "window-bounds"])
def test_same_session_ids_changed_window_content_is_refused(split: c.Split, changed: str) -> None:
    report = calibrated()
    assert report.selected is not None
    result = scores(report.selected, split)
    session = result.input_sessions[0]
    window = session.windows[0]
    altered = (
        replace(window, original_sha256=H)
        if changed == "source-digest"
        else replace(window, sample_start=window.sample_start + 1920, sample_end=window.sample_end + 1920)
    )
    result = replace(
        result,
        input_sessions=(
            replace(session, windows=(altered, *session.windows[1:])),
            *result.input_sessions[1:],
        ),
    )
    with pytest.raises(c.Refusal, match="FROZEN_INPUT_MISMATCH"):
        if split == c.Split.CALIBRATION:
            c.evaluate_calibration(freeze(), lambda config, requested: replace(result, config=config))
        elif split == c.Split.VALIDATION:
            c.evaluate_validation(report, result)
        else:
            c.evaluate_holdout(result, holdout_use(report))
