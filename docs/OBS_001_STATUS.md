# OBS-001 — Native Observation & Candidate Preparation

Qualification: **CODE_COMPLETE / TEST_ONLY_SUPPORT**. Candidate evidence
preparation only. No native/media intelligence qualification or edit authority.

## Receipt and exact scope

Remote main verified before implementation:

- SHA: `8a0b3cf256dfde9c456140d1a941edb9c3e145db`
- Tree: `dac92d77e87aea35e6ad6d3cb42a389a4108743f`
- Branch: `feature/obs001-observation-pipeline`
- Worktree: `C:/Users/c/source/repos/edit-program-obs001`
- Final head/tree and remote CI receipt are recorded in the PR.

Exact changed-file allowlist:

1. `src/davinci_ai_editor/observation_pipeline.py`
2. `tests/test_observation_pipeline.py`
3. `docs/OBS_001_STATUS.md`

All existing production modules remain unchanged, including TRUST-001,
evidence.py, pause.py, native_snapshot.py, temporal_mapping.py, authority,
Safety, orchestration and transactions. No dependency/config changes.

## Existing contracts reused unchanged

- NativeTimelineSnapshot, NativeTrackSnapshot, NativePlacementSnapshot,
  IdentityRef/IdentityScope, PAUSE_ANALYSIS, evaluate_readiness/ReadinessResult.
- NativeSnapshotRef, PlacementTemporalBinding, MappingRequest, map_range,
  MappingStatus/TemporalMappingResult, typed ranges and exact FrameRate values.
- ProducerRef, EvidenceRecord, EvidenceBinding, EvidenceBundle,
  PreparationResult/PreparationStatus, prepare_observation.
- PauseObservation, PauseCandidate and classify_pause, including all existing
  KEEP/TIGHTEN/REMOVE/REVIEW semantics.
- Existing TimelineSnapshot/Track/Clip/TimelineObjectId/FrameRange for an ephemeral
  placement-only projection. Native snapshot remains the source of truth.

TRUST execution-grade TargetCorrespondence and IndependentReadEvidence are not
used as analysis readiness requirements. Analysis does not upgrade identity.

## New immutable records and why they are needed

- `ObservationPlacementLink`: an explicit producer-supplied native-placement to
  PlacementTemporalBinding link. Existing EvidenceBinding expressly does not prove
  native correspondence; execution-grade correspondence would incorrectly reject
  snapshot-local analysis. Retains exact native placement, mapping, producer and
  source refs. The mapping already retains snapshot, semantic object/media,
  source/timeline ranges, frame rates and mapping kind; these are not duplicated.
- `AnalysisCoverage` / `CoverageStatus`: retains declared scope, snapshot,
  link/native/semantic identity, covered range, producers, source refs and
  limitations. Existing evidence does not represent analyzed zero-subject input.
- `PreparedPauseSubject`: exact bundle, mapping results, optional existing
  PreparationResult and PauseCandidate. Its observation is the existing
  preparation's observation, not another observation model.
- `NativePausePreparation`: evidence retention for readiness, original links and
  coverage, effective coverage status, subjects, diagnostics and optional existing
  domain projection. It is not a workflow or another timeline model.
- `ObservationDiagnostic`: bounded composition failure reasons. Native readiness,
  temporal mapping, evidence preparation and editorial decisions retain their
  existing separate statuses. No approval/lifecycle/Safety enum was added.

## Application and producer boundary

`prepare_pause_candidates_from_native(native, current_snapshot, *, links,
coverage, bundles)` is pure and performs no IO. Its caller supplies an actual
native capture and already-aligned producer EvidenceRecords inside existing
EvidenceBundles. Raw inference is not implemented; no second feature schema or
unused producer Protocol was added.

1. Evaluate the supplied native capture using the unchanged PAUSE_ANALYSIS profile.
2. Require exactly one explicit placement link for this placement's batch. Missing
   or multiple proposed links stop. Repeated-media placements remain distinct;
   no search by names, media, range similarity, index or first returned placement.
3. Validate capture membership and exact snapshot/media/range/track/rate/retime
   correlation. The retained capture reference must occur in link provenance.
   Producer authentication and correspondence authenticity remain producer duties;
   provenance strings alone are not independent native proof.
4. Validate coverage binding and provenance. Record producers and record IDs must
   occur in coverage's producers/source refs. Evidence IDs identify records within
   their retained bundles; they do not establish native identity.
5. Map the context, pause range and every evidence range through existing
   map_range. Every result must be EXACT. Keep all mapping results; no rounding,
   clamping, inference, placement switching or rebasing.
6. Project only the linked placement into existing TimelineSnapshot/Track/Clip.
   This is a non-persisted analysis view, not a complete project, preservation
   guarantee, relationship analysis, Safety input or execution qualification.
7. Call existing prepare_observation for each eligible bundle. Only READY calls
   classify_pause. REVIEW_REQUIRED keeps the exact unresolved preparation and
   `candidate=None`; it does not synthesize an editorial REVIEW candidate.

EvidenceBundle's existing constructor rejects mixed timeline/version/placement
records and records outside context. Other stale/unsupported/missing/conflicting
evidence stops conservatively via existing preparation or composition diagnostics.
Ordinary unavailable/stale/ambiguous input does not require exceptions. Invalid
typed contracts retain existing constructor errors.

## Mapping support boundary

The existing Clip requires equal timeline/source span lengths. IDENTITY_1X and
equal-span AFFINE_FORWARD are supported when map_range proves EXACT and all
native fields agree. A mathematically exact non-1:1 affine cannot be projected
without changing that domain contract, so returns PROJECTION_UNSUPPORTED.
Non-integral, unsupported or ambiguous mapping never yields a candidate. No
existing domain contract is weakened and no parallel mapping algorithm exists.

## Coverage, staleness and batching

- ANALYZED + zero bundles: valid producer-declared analyzed zero-subject result.
- NOT_EVALUATED / UNAVAILABLE + zero bundles: retained distinctly, never a claim
  that no pause exists. Missing coverage has `coverage_status=None` plus a diagnostic.
- PARTIALLY_ANALYZED + subjects: those eligible subjects may prepare; status stays
  partial and supplied limitations remain retained. Covered range is a declared
  scope bound, not a claim that every frame inside a partial scope was analyzed.
- Native/current/mapping/coverage snapshot disagreement: effective coverage STALE,
  original evidence retained, no current candidate. Immutable old results do not
  become live: callers must re-evaluate against supplied current snapshot facts.
- One placement accepts zero or many internal subjects, without UI decisions,
  interruption counts, approval or feedback. Classifier REMOVE remains only a
  proposal; automatic REMOVE and all mutation remain HOLD.

## Adversarial and regression evidence

All fixtures explicitly use TEST_ONLY_SUPPORT producer/capture provenance and
snapshot-local identities. No native read or real media was used.

- New targeted module: **43 passed**. Covers READY end-to-end composition;
  stale/unverified/partial/unstable/unsupported native input; repeated media and
  missing/ambiguous exact links; name-only failure; wrong media/source/timeline/
  track/rates/retime/snapshot; unsupported and non-integral mappings; exact
  equal-span affine and exact non-1:1 projection refusal; wrong evidence bindings,
  mixed/out-of-context evidence, unsupported contract, conflicts/missing evidence;
  all five coverage meanings and missing coverage; partial multi-subject output;
  immutable stale re-evaluation; provenance mismatch; no extra state machine,
  native/authority imports or classifier implementation.
- Targeted OBS + native_snapshot + temporal_mapping + observation_evidence +
  pause_baseline + pause_planning + orchestration: **462 passed**.
- Full regression: **1,836 passed / 1 skipped**. Existing opt-in intentional red
  test `test_naive_inv001.py:27` is the only skip.
- Ruff `check .`: **PASS**.
- Repository strict mypy: **PASS**, 40 source files.
- Explicit strict mypy over both new Python files: **PASS**, 2 files.
- Whitespace and exact three-file allowlist checked before commit. Remote CI is
  reported separately in the PR; local tests are not CI qualification.

No expanded all-legacy-tests strict-green claim is made. TRUST-001's previously
disclosed 840-error legacy-test baseline was not changed or included in the new
two-file strict scope. No suppression/config weakening was introduced.

## NOT_IMPLEMENTED / open dependencies

No VAD, STT, diarization, prosody/emotion/semantic model, LLM, audio extraction,
network/model calls, native polling, Resolve live read qualification, mutation,
staging, native execution, approval, delegated request parsing, UI, persistence,
Style/Editing DNA, other hosts or full human-value proof. No actual producer
quality/recall measurement or DP001 session. No execution-grade identity upgrade.

Producer acquisition/authenticity, exact analysis correspondence production,
real-media feature extraction/alignment/coverage and native read qualification
remain open. TRUST-001 atomicity/identity and OPEN-002/008 remain unchanged.

Review candidate: **GO for PR review, CODE_COMPLETE / TEST_ONLY_SUPPORT**.
Live/native/media qualification remains **HOLD**. Recommended next milestone only
after Chat Gate: narrow Pause Vertical Producer; do not begin it in this PR.
STOP after PR creation and CI receipt. Do not merge.
