# UX-001B — Linear Assist Presentation Foundation

Status: implementation complete; local validation receipts recorded below.

## Base and file boundary

- Authoritative main: `a5139c2791fe7ed51529aafad40dc3a5adeb6401`
- Authoritative tree: `60f70a83fb7499bf8cdaf72e52ac89866e699043`
- Branch: `feature/ux001b-linear-assist`
- Worktree: `C:/Users/c/source/repos/edit-program-ux001b`
- Allowlist: `src/davinci_ai_editor/linear_assist.py`,
  `tests/test_linear_assist.py`, `docs/UX_001B_LINEAR_ASSIST_STATUS.md`.
- No existing production, test, configuration, or semantic contract modified.

## Public contracts

`AssistMode` supports default LINEAR_ASSIST and optional REVIEW_QUEUE. Both modes
retain the same exact `CandidatePresentation`; neither owns a separate edit state.

`ReviewClassification` and `ReviewAssessment` retain externally supplied advisory
classification, existing `ProducerRef`, provenance, and basis. NOT_EVALUATABLE is
distinct from LOW_REVIEW_NEED and from an absent assessment. REVIEW_REQUIRED is
not an instruction to interrupt playback and never grants Apply authority.

`CandidatePresentation` retains exact existing `PauseCandidate`,
`CandidateWorkState` (and therefore its authority Candidate), `NativeSnapshotRef`,
`ExpectedDiff`, `SafetyPreflightResult`, `PauseCutGeometry`, `PreservationScope`, and
`EffectiveStyleContext` objects when supplied. Optional facts remain absent.
The caller supplies an opaque proposal revision reference; this module neither
allocates authoritative candidate identity nor proves revision authenticity.
PauseCandidate and authority Candidate remain distinct.

`ScopePresentation` retains modification, accepted, explicitly reopened, and
conflict references. Conflict assessment is supplied: None is unassessed, an
empty tuple is supplied no conflict, and nonempty references identify conflicts.
It does not infer containment or accepted-work overlap from opaque strings.
The scope producer must establish that reopened scope is explicitly authorized
and bounded; presentation does not implement that resolver. Scope uncertainty or
conflict suppresses actionable descriptions. A style modification-scope mismatch
is surfaced, never repaired by expanding modification/reopened scope.

`ActionAvailability` describes selection, keep original, adjustment, deferral,
and an externally available request-apply path. `ProjectedAction` retains that
exact description and may suppress, never upgrade, availability. This is not an
Apply eligibility evaluator. Even an available request-apply path merely describes
an external request: approval, execution, and postflight remain separate contracts.
Currentness/continuity/scope uncertainty suppresses proposal actions; defer remains
non-mutating. Request-apply additionally requires supplied existing context objects.

`PositionWindow`, `PositionRelation`, `ProjectedCandidate`, `UpcomingProjection`,
and pure `project_upcoming()` compare only caller-supplied snapshot-bound timeline
coordinates and half-open windows. No lookahead duration or threshold is chosen.
The pause observation's aligned range is never converted into native coordinates.
Missing location/window/position remains UNKNOWN. Snapshot equality supports only
correlation; it cannot manufacture currentness. Stale authority or mismatched
bindings suppress actions even if a caller supplied a positive currentness flag.
Receipt/reference retention is not proof of authenticity or temporal freshness.

## Presentation behavior

- KEEP is silent by default in both modes; optional show-more permits inspection.
- TIGHTEN/REMOVE can be displayed as recommendations, not execution instructions.
  HIGH confidence is never approval.
- REVIEW is retained as REVIEW. No response means PRESERVE_CURRENT_STATE, including
  any human changes; it does not restore an older snapshot or create a KEEP decision.
- LINEAR_ASSIST displays supplied in-window recommendations without forced review.
  A late candidate is PASSED and does not move the playhead. REVIEW_QUEUE/show-more
  can expose late, stale, and unlocated records for inspection.
- Hidden candidates stay retained but invisible. Deferred candidates stay retained
  and may appear in REVIEW_QUEUE. Neither operation emits feedback, approval,
  rejection, execution, or success events.
- `AssistCounts` independently retains measured internal observations, visible
  recommendations, attention requests, explicit human decisions, and executed
  changes. None is unmeasured, not zero. Counts have supplied measurement provenance
  and are not inferred from display rows; measurement scope need not equal one view.
  Batch display never means batch decisions, batch approval, or batch execution.

All records are frozen with immutable collections. Enums describe display mode,
advisory class, action request, and coordinate relation only. AST tests prohibit
domain event/candidate construction, classifier calls, lifecycle constructors,
and runtime imports. No second candidate/transaction/authority/Safety state machine
is introduced.

## Validation

Fixtures are explicitly TEST_ONLY_SUPPORT. Supplied currentness and availability
are contract test inputs, not native qualification, media understanding, or a
production review-risk assessment. Coverage includes every requested UX-001B case,
half-open coordinates, missing observation/window, exact object retention, stale
authority, mismatched snapshots, scope/style conflict, and action suppression.

Validation receipts (Python 3.11 validation environment):

- Targeted: `pytest -q -p no:cacheprovider tests/test_linear_assist.py` — 41 passed.
- Full: `pytest -q -p no:cacheprovider` — 1,739 passed, 1 skipped. The skipped case
  is the repository's opt-in intentional red test at `tests/test_naive_inv001.py:27`.
- Ruff: `ruff check .` — all checks passed.
- Repository strict mypy: `mypy` — 38 source files, no issues.
- Explicit strict mypy: `mypy --strict --follow-untyped-imports
  --explicit-package-bases src/davinci_ai_editor/linear_assist.py
  tests/test_linear_assist.py` — 2 source files, no issues after replacing a dynamic
  test-field update with typed alternatives.
- Whitespace and exact three-file allowlist checked before commit. Untracked-file
  `git diff --no-index --check NUL <file>` exit 1 means files differ (expected for
  new files); whitespace diagnostics must be empty. Staged diff check must exit 0.
- Initial local failures were fixture/type/lint issues corrected in these new
  files, not hidden hook failures or modifications of existing semantic contracts.

## Architectural boundary and NOT_IMPLEMENTED

Pure host-neutral immutable presentation/domain support only. Existing Editing
Environment First; no new editing surface; native NLE remains source of truth.
Human Edit Wins, ExpectedDiff != ActualDiff, Unknown remains Unknown, and
modification scope != preference scope remain unchanged.

NOT_IMPLEMENTED: native UI, playback/playhead polling or movement, marker writes,
queue persistence, native locking, scope containment/resolution or reopening,
automatic review classification/risk scoring, numeric attention thresholds,
classifier changes, Safety evaluation changes, Authority changes, execution,
native adapters, transports, persistence, feedback production, style learning,
Apply handlers, automatic batching of edits, telemetry capture, or production
metric/recall claims. No standalone timeline/media bin/project format.

OPEN: authoritative scope overlap/reopen production, native position and identity
correspondence, currentness/acquisition authenticity, observation-to-execution
atomicity, OPEN-002 / OPEN-008, persistence/concurrency/exactly-once, real review
assessment producers, UI integration and DP001 measurement. The one DP001 signal
remains a hypothesis, not market-wide validation. Structural presentation readiness
does not qualify live mutation. Next scope should separately approve the producer
contracts and host presentation integration; this PR does not choose either.

GO candidate is limited to PR review of this foundation after local checks pass.
No merge is authorized by this task.
