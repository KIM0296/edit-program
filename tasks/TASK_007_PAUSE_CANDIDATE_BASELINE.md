# TASK-007 — Pause Candidate Domain & Deterministic Baseline

Status: user-authorized foundation, Chat Gate pending. Basis: ADR-018 and TASK-007.
Base main a7270ee; TASK-006 approved and merged. Commit this spec before implementation.

## Scope

Pure `classify_pause(observation) -> PauseCandidate`. All features are caller-supplied
observations, never inferred from media. No STT/VAD/ML/LLM, feature extraction, actual
edit plan, authority transitions, shadow creation, execution or UI.
Absolute duration is used ONLY to check a supplied retained target, never to classify
pacing or choose removal. False REMOVE costs more than false KEEP.

## Immutable values

Reuse TimelineId, TimelineVersion, fake TimelineObjectId and integer half-open FrameRange.
PauseObservation contains timeline_id, base_version, object_id, pause_range,
relative_pause_band, boundary_kind, signals, optional local_reference_pause_frames,
content_mode. No new persistent identity. Full immutable observation is the candidate's
observation reference; this is not proof that a supplied range lies within a real clip.

- RelativePauseBand: SHORT / NORMAL / LONG / VERY_LONG / UNKNOWN.
- PauseBoundaryKind: WITHIN_PHRASE / SENTENCE_BOUNDARY / QUESTION_ANSWER /
  SPEAKER_TRANSITION / TAKE_GAP / UNKNOWN.
- PauseSignal: NATURAL_BREATH / THINKING / EMOTIONAL / HESITATION /
  RECORDING_DEAD_AIR / FAILED_TAKE_GAP / UNKNOWN.
- ContentMode: SPOKEN_CONTENT / UNSUPPORTED_NARRATIVE / UNKNOWN.
- PauseAction: KEEP / TIGHTEN / REMOVE / REVIEW.
- Confidence: HIGH / MEDIUM / LOW (rule labels, no calibrated probabilities).
- DecisionReason: EXPLICIT_DEAD_AIR, FAILED_TAKE_GAP, EMOTIONAL_CONTEXT,
  THINKING_PAUSE, QUESTION_ANSWER_CONTEXT, SPEAKER_TRANSITION, NATURAL_BREATH,
  HESITATION, RELATIVELY_LONG_PAUSE, NORMAL_LOCAL_PACING, CONFLICTING_EVIDENCE,
  INSUFFICIENT_CONTEXT, UNSUPPORTED_CONTENT_SCOPE, NO_SAFE_TIGHTEN_TARGET.
- CandidateRouting: NO_CHANGE / SHADOW_ELIGIBLE / BATCH_REVIEW.

Freeze values; copy/canonicalize signals and reasons into sorted deduplicated tuples.
Validate enum instances, identity, integer version/range/reference types (bool is not
an integer frame count). Invalid local-reference integer values remain evidence and
fail closed when tightening is considered; no clamping or synthesized target.
PauseCandidate holds observation, action, confidence, reasons and optional
suggested_retained_frames. Routing is a derived read-only property: HIGH edit ->
SHADOW_ELIGIBLE; MEDIUM or REVIEW -> BATCH_REVIEW; KEEP otherwise -> NO_CHANGE.
No routing value means Main Apply permission. Baseline never emits HIGH TIGHTEN;
the schema/routing can express it for future reviewed callers. LOW edits and non-HIGH
REMOVE are invalid candidate shapes; tightening must use the supplied local reference
and satisfy strict `0 < retained < original duration`. Other actions carry no target.

## Ordered conservative rules

1. Non-spoken/unknown content: REVIEW / LOW / UNSUPPORTED_CONTENT_SCOPE.
2. Explicit removal evidence (dead air/failed-take signal) conflicts with emotional,
   thinking, natural-breath or hesitation signals, or QUESTION_ANSWER/SPEAKER_TRANSITION
   boundaries: REVIEW / MEDIUM. Preserve all relevant reasons, no arbitrary priority.
3. EMOTIONAL / THINKING / QUESTION_ANSWER / SPEAKER_TRANSITION: KEEP / HIGH.
   HESITATION together with EMOTIONAL still preserves; it is not itself removal evidence.
4. Explicit UNKNOWN signal vetoes proactive editing: KEEP / LOW / INSUFFICIENT_CONTEXT.
5. Explicit dead air / failed-take signal with no preservation/conflict: REMOVE / HIGH.
   Neither duration, relative band nor TAKE_GAP boundary alone can trigger REMOVE.
   Missing band/boundary does not negate explicit dead-air evidence; UNKNOWN signal does.
6. NATURAL_BREATH + SHORT/NORMAL: KEEP / HIGH. Unknown band: KEEP / LOW.
7. LONG/VERY_LONG with breath or hesitation, or an ordinary known boundary with no
   meaningful signal: TIGHTEN / MEDIUM only with safe caller reference. Missing/zero/
   negative/not-shorter target: REVIEW / MEDIUM / NO_SAFE_TIGHTEN_TARGET. Never REMOVE.
8. SHORT/NORMAL + no signals + known ordinary boundary: KEEP / HIGH.
9. Remaining insufficient context (including generic long with UNKNOWN boundary,
   unknown relative band, short hesitation): KEEP / LOW / INSUFFICIENT_CONTEXT.

Rules 4/9 conservatively implement the requested fail-closed behavior. No seconds/FPS
thresholds, global targets, window sizes or inferred boundaries are introduced.
Machine-readable reasons include supplied evidence relevant to the selected rule.

## Acceptance and red-first tests

Cover all 14 requested cases; duration-only comparison; dead air across durations;
meaningful/breath/hesitation conflicts; target values None/0/negative/equal/longer;
unknown mixtures and content scope; duplicates/order permutations; frozen input/output;
routing distinction (including schema HIGH TIGHTEN); executor monkeypatch failure;
no authority integration; systematic combinations to assert REMOVE requires explicit
nonconflicting evidence and every TIGHTEN retains a positive local-reference portion.
Run TASK-001..006 regression unchanged, Ruff, strict mypy, Python 3.11 CI.
Update status/limitations/test matrix, docs/reports/TASK_007_COMPLETION.md, PR/Chat Gate.
No merge or next task.

## OPEN / limitations

OPEN-009: RelativePauseBand producer/window, prosody and transcript boundary schema,
emotion/thinking producer, confidence calibration, content detector, exact target
producer, FPS/mixed-FPS mapping, clip-boundary spans, crosstalk, dialogue cleanup schema.
Do not decide these production contracts. This foundation accepts already aligned
single-placement observations; no binding to an actual snapshot or boundary inference.
Dialogue restart/repetition/self-correction/filler are ADR-018 product scope only,
not implemented by TASK-007. Existing OPEN-001 identity contract remains unresolved.
