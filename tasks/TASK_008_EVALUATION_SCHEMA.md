# TASK-008 — Evaluation Schema & Pure Metric Foundation

Status: implementation spec for approved TASK-008 / ADR-019, before code.
Base main 3c1ca49. TASK-007 approved/merged. Raw Events First, Derived Metrics Second.

## Immutable records and scope

New evaluation.py (schema) and evaluation_metrics.py (pure derivation), reusing pause
Action/Confidence/Routing enums only. Never call classifier, executor or authority.
All IDs are opaque strings, all ordered collections frozen defensive tuples. No timestamps,
IO/randomness, DB, telemetry, dataset/pilot execution, training, consent inference or gates.

- EvaluationCase: case_id, source_kind BENCHMARK/PILOT/PRODUCT_FEEDBACK,
  evaluation_scope_id, pause_subject_ref, schema_version (supported value `evaluation-v1`).
- DecisionProducerRef: kind RULE/VAD/STT/PROSODY/SEMANTIC/LLM/MANUAL, name, version,
  decision_contract_version, feature_contract_version. Strings nonempty; no producer runs.
- AIProposalSnapshot: proposal_id, case_id, action/confidence/reasons, original_pause_frames,
  suggested_retained_frames, routing_hint, producer_ref. Recalculation is a NEW ID/value.
  Validate shape, not editorial correctness: a low-confidence REMOVE can be evaluated.
- ReferenceAssessment groups common action/confidence/reasons, original_pause_frames,
  preferred_retained_frames and acceptable_min/max_frames. This nested structure is shared
  by ReferenceAnnotation(annotation_id,case_id,annotator_ref,assessment) and
  ReferenceJudgment(case_id,reference_version,assessment,ambiguity,adjudication_status).
- Ambiguity CLEAR/AMBIGUOUS; Adjudication SINGLE_ANNOTATOR/AGREED/ADJUDICATED.
  Preserve supplied ambiguity, never auto-adjudicate. For TIGHTEN strictly validate
  0 < min <= preferred <= max < original; for other actions all target/range fields absent.
- EvaluationRecord binds case, proposal, optional reference, annotations and feedback.
  Check matching IDs/original frames, unique annotation IDs. PRODUCT_FEEDBACK cannot carry
  reference/annotations. Feedback never writes or generates ReferenceJudgment. Importing
  corrected reference versions is explicit caller work, not a reducer side effect.

## Append-only event evidence

FeedbackEvent: event_id/case_id/proposal_id/sequence_no/actor/event_type/typed payload.
Actor EDITOR/SYSTEM is provenance metadata, not authorization inference.
Event types: ATTENTION_REQUESTED, REVIEW_OPENED, PROPOSAL_ACCEPTED, FINAL_DECISION_SET,
PROPOSAL_REVERTED, REMOVED_PAUSE_RESTORED, RUN_FINALIZED.
Payload types: EmptyPayload for notification/accept/revert/restore; FinalDecisionPayload
for final action/retained frames; RunFinalizedPayload(run_id) for finalization.
TIGHTEN payload has a positive integer target; other actions have None. Bound derivation
checks target < proposal original duration. Bool/floats invalid for integer fields.

FeedbackLog is one case/proposal episode. Canonicalize supplied events by sequence_no;
require unique event IDs and contiguous sequence 1..N, matching case/proposal, at most one
RUN_FINALIZED, terminal. append(event) returns a new log and requires next sequence; no
update/delete API. No timestamp authority. Missing sequence rejects (no guessed history).

## Pure outcome and correction interpretation (conservative v1 subset)

Process canonical raw events:
- ACCEPTED records current decision equal to proposal; FINAL_DECISION_SET replaces the
  current decision explicitly. This is derived state; earlier events are never removed.
- REVERTED sets sticky reverted flag and clears current decision: actual resulting action
  is unknown until a later explicit decision/accept/restore, never guessed KEEP.
- RESTORED sets sticky restored flag and explicit KEEP (full original pause restored).
  Only valid against a REMOVE proposal; it is an observed restoration, not candidate review.
- FINALIZED marks this episode complete and carries run identity; no decision inferred.
- ATTENTION/REVIEW_OPENED do not imply any decision.
UserFinalOutcome includes case/proposal/event IDs, metric_definition_version, final action/
retained frames (None until finalized, or if unknown), accepted_as_is/modified (optional),
reverted/restored and finalized flag/run_id. Accepted_as_is requires finalized known result
identical to proposal AND no revert/restore in this episode. modified compares final tuple
with proposal tuple; it does not erase historical recovery. No events => outcome unknown.

CorrectionClass: NONE, KEEP_INSTEAD, REMOVE_INSTEAD, TIGHTEN_INSTEAD, TIGHTEN_MORE (smaller
retained value), TIGHTEN_LESS (larger), RESTORE_REMOVED_PAUSE, OTHER_ACTION_CHANGE.
Restore evidence has precedence as a safety signal even before finalization. Otherwise
unknown final outcome => no computable correction. REMOVE->KEEP with only FINAL_DECISION_SET
is KEEP_INSTEAD; actual restore event is RESTORE_REMOVED_PAUSE.
Terminal/reopen/reaccept/partial restore details remain OPEN-010; no event repair/inference.

## Raw timing and run evidence

WorkflowRun: run_id, evaluation_scope_id, run_mode MANUAL_BASELINE/AI_ASSISTED,
producer_ref, unique case_ids, complete_activity_kinds (explicit caller coverage claim).
This extra raw coverage field prevents partial event samples from masquerading as complete
measurement. It is not produced by instrumentation in this task.
ActivityRecord: activity_id, run_id, optional case_id, activity_kind, duration_ms int|None,
measurement_source INSTRUMENTED/MANUAL_ESTIMATE. Nonnegative integer, bool excluded.
RunEvidence binds run and activities; rejects duplicate IDs, wrong run/case/kind coverage.
Each metric requires coverage declared for every included kind AND at least one known
record for each kind. Explicit zero record means measured zero; absent kind or any None
means not computable. No default zero or timing estimation. Multiple records of a kind sum;
caller coverage asserts nonoverlapping complete durations (overlap detection remains OPEN).

Pure TimingMetrics (version + scope/run/case/activity IDs) formulas:
- Human Active = INSTRUCTION + REVIEW + CORRECTION + MANUAL_COMPLETION + RECOVERY_REVERT.
- Mandatory Attention = same excluding MANUAL_COMPLETION.
- Assisted Human Cost = Human Active + AI_BLOCKED_IDLE (only actually blocked human time).
- Correction Debt = CORRECTION + RECOVERY_REVERT.
Ordinary AI computation has no activity kind and is never included.

NetTimeSaved consumes paired raw RunEvidence, not user-authored metric numbers. Require
correct modes, distinct run IDs, same scope AND same case set; mismatch rejects. Missing
partner => not computable. Difference = manual Human Active - assisted Human Cost, including
negative results. Rate = difference/manual Human Active only if baseline > 0, exact Fraction.

## Pure editorial metrics and versioning

Metric definition version fixed by the implemented formula: `evaluation-metrics-v1`.
All derived results identify source cases/proposals/reference versions/events or runs/
activities, not just metric numbers. Future formula versions recalculate from unchanged raw
records; arbitrary caller version labels cannot relabel this implementation.

One explicit selected proposal per unique case in each evaluation batch; duplicate cases/
proposal IDs/global event IDs reject. Refresh comparisons use separate batches, no auto latest.
- CriticalFalseRemoval per reference-bearing BENCHMARK/PILOT: reference KEEP/REVIEW and AI REMOVE.
- Rate denominator: eligible reference KEEP/REVIEW case count (at-risk preservation cases).
  Numerator false removal count. Report reference-bearing, missing-reference and eligible
  counts explicitly. Zero denominator => None. PRODUCT_FEEDBACK excluded from this metric.
- TIGHTEN comparison only when both reference and proposal TIGHTEN: IN_RANGE if inclusive
  min <= proposed <= max, otherwise OUT_OF_RANGE. Other cases => None. No NEAR_RANGE.
- Review Load = AI REVIEW count / evaluated unique cases, including feedback-only cases;
  empty batch => None. No silent proposal-refresh double counting.
- Decision Interruptions = count ATTENTION_REQUESTED, not REVIEW_OPENED or review items.
  Missing log for any evaluated case => total None, not zero. Explicit empty log means zero
  observed events in that supplied episode, not a claim of future run completeness.
- Accepted-as-is count/rate over finalized KNOWN outcomes only; report unknown outcome count.
  Zero eligible outcomes => None. Revert/restore never becomes accepted-as-is.
Rates use Fraction; no numerical threshold, gate pass/fail, tolerance or weighting.

## Test-first and delivery

Red-first missing module tests, then all 20 requested cases plus source binding, invalid
payloads/sequences/replay/finalization, unknown outcomes, complete-coverage vs explicit zero,
reference bounds, missing/zero paired baseline, negative savings, unique batch identity,
immutable/deterministic ordering and no classifier/executor/authority calls.
Run all TASK-001..007 tests unchanged, Ruff, strict mypy, Python 3.11 CI.
Update status/limitations/test matrix; standard TASK_008_COMPLETION report, PR, Chat Gate.
Do not merge or start another task. No raw media/name/file/transcript/consent fields required.
