# Evaluation Data Contract & Feedback Event Schema v1

Status: **Accepted product/architecture baseline**

## Purpose

Provide a stable, model-agnostic evaluation contract for Pause Intelligence so safety, editorial
quality, attention cost, correction debt and net time saved can be compared across rule, VAD, STT,
prosody, semantic and future LLM generations.

## Source classes

- `BENCHMARK`: fixed reference editorial judgment for regression/release comparison.
- `PILOT`: reference judgment plus human workflow evidence for calibration.
- `PRODUCT_FEEDBACK`: real-use accept/modify/revert/restore/timing evidence; never benchmark truth.

## Core immutable records

Recommended meanings:

- `EvaluationCase`: case identity, source kind, evaluation-scope identity, opaque pause subject ref,
  schema version.
- `DecisionProducerRef`: producer kind/name/version plus decision/feature contract versions.
- `AIProposalSnapshot`: immutable action/confidence/reasons/original pause/retained proposal/routing.
- `ReferenceAnnotation`: one annotator's action/confidence/reason and optional TIGHTEN range.
- `ReferenceJudgment`: adjudicated reference with ambiguity/adjudication status.
- `FeedbackEvent`: append-only user/system event keyed to case/proposal with explicit sequence number.
- `ActivityRecord`: measured human-time evidence with activity kind and measurement source.
- `WorkflowRun`: one MANUAL_BASELINE or AI_ASSISTED run for the same evaluation scope.

## Feedback events v1

Minimum event vocabulary:

- `ATTENTION_REQUESTED`
- `REVIEW_OPENED`
- `PROPOSAL_ACCEPTED`
- `FINAL_DECISION_SET`
- `PROPOSAL_REVERTED`
- `REMOVED_PAUSE_RESTORED`
- `RUN_FINALIZED`

Feedback is append-only. Recalculated AI decisions create new proposal snapshots.

## Derived user outcome

Derive, do not treat as raw truth:

- final action / final retained frames
- accepted as-is
- modified
- reverted
- restored removed pause

Suggested derived correction taxonomy:

- `NONE`
- `KEEP_INSTEAD`
- `REMOVE_INSTEAD`
- `TIGHTEN_INSTEAD`
- `TIGHTEN_MORE`
- `TIGHTEN_LESS`
- `RESTORE_REMOVED_PAUSE`
- `OTHER_ACTION_CHANGE`

## Timing contract

Activity kinds:

- `INSTRUCTION`
- `REVIEW`
- `CORRECTION`
- `MANUAL_COMPLETION`
- `RECOVERY_REVERT`
- `AI_BLOCKED_IDLE`

Measurement source:

- `INSTRUMENTED`
- `MANUAL_ESTIMATE`

Missing timing is missing, never zero.

Human Active Time is instruction + review + correction + manual completion + recovery/revert.
Mandatory Attention excludes manual completion.
Assisted Human Cost adds AI-blocked idle only when AI actually prevented useful parallel work.
Correction Debt is correction + recovery/revert.
Net Time Saved compares a paired MANUAL_BASELINE run with an AI_ASSISTED run over the same
`evaluation_scope_id`.

## Safety and quality derivation

For BENCHMARK/PILOT with a reference:

- Critical false removal: Reference KEEP/REVIEW and AI REMOVE.
- TIGHTEN quality: compare retained frames with an acceptable reference range.
- Review Load: AI REVIEW count / evaluated cases.
- Decision Interruptions: count `ATTENTION_REQUESTED` events, not review-item count.
- Accepted-as-is requires final result == proposal and no later revert/restore.
- REMOVE revert/restore is a distinct safety signal.

Exact NEAR_RANGE tolerance and numeric release thresholds are not part of v1.

## Versioning

Keep explicit versions for:

- schema
- decision producer
- decision contract
- feature contract
- metric definition

Derived `MetricSnapshot` values may be cached but must remain reproducible from source evidence.
Gate thresholds belong to a separate versioned `GatePolicy` after pilot calibration.

## Privacy and governance

PRODUCT_FEEDBACK core schema must not require raw video/audio, full transcripts, project names,
filenames or personal identity. Use opaque references where possible. Benchmark assets may be governed
separately. Feedback capture does not imply permission for model training.

## TASK-008 boundary

Implement only immutable domain/schema, structural validation, pure user-outcome derivation and pure
metric derivation. No DB, SQL, storage service, telemetry uploader, Resolve observer, background
tracking, cloud upload, dashboard, UI, training, personalization update, raw-media capture, automatic
gate enforcement or numerical thresholds.
