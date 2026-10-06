# Implementation Status

## 2026-10-05 Integration Review

- 사용자 요청에 따라 이 저장소를 메인으로 지정. 기존 연구 자산 비교 완료: docs/LEGACY_INTEGRATION_REVIEW.md.
- 실제 src/tests는 .gitkeep만 존재. 기능 이식/구현 및 테스트 실행은 이번 검토에서 수행하지 않음. 아래 체크 상태 유지.
- 구 시스템의 120개 통과 기록을 이 저장소의 P0 통과로 간주하지 않음.
- 다음 권장 작업: TASK-001, 기존 고정 기준본 일괄 수정 사례를 domain 테스트로 재사용.

## Phase 0 — Specification

- [x] Product direction
- [x] Chat / Codex role split
- [x] Safety Core definition
- [x] Timeline Coordinate Contract
- [x] P0 Timeline Invariants
- [x] Initial Editing IR
- [x] Initial test matrix

## Phase 1 — Domain & Fake Timeline

- [x] Domain model
- [x] FakeTimeline
- [x] timeline version model
- [x] StableTarget model
- [x] Target Resolver
- [x] INV-001
- [x] INV-002
- [x] INV-003

## Phase 2 — Safety Core

- [x] Relationship Graph domain foundation (TASK-003; no execution)
- [ ] Relationship Integrity Engine / policy execution
- [ ] Temporal Mapping
- [ ] Media Identity
- [ ] Transaction Engine
- [ ] Rollback
- [ ] Postflight diff
- [ ] P0 complete

## Phase 3 — Resolve Read-only

- [ ] Resolve connector
- [ ] project snapshot
- [ ] timeline snapshot
- [ ] track state snapshot
- [ ] TimelineItem mapping
- [ ] marker round-trip

## Phase 4 — Intelligence

- [ ] STT
- [ ] VAD
- [ ] Pause Intelligence
- [ ] semantic search
- [ ] Edit Planner

## Phase 5 — Destructive Sandbox

- [ ] Safe Trim
- [ ] Safe Delete
- [ ] Safe Ripple

Current task: `TASK-008` immutable evaluation evidence and pure metrics implemented; PR/CI and Chat Gate pending. TASK-007 approved/merged; ADR-019 accepted in main.


## TASK-001 completion - 2026-10-05

This completion section supersedes the pre-implementation src/tests observations in the earlier Integration Review. That review is preserved as history.

Implemented:
- All 12 required domain types; frozen dataclasses and integer half-open FrameRange.
- FakeTimeline creation/clip placement via a single Track, immutable snapshot/version,
  snapshot target resolution, ordered ripple-delete simulation, current clip positions.
- All targets are resolved and checked against the same base snapshot before mutation.
  Execution finds clip placement lineage + media identity + source interval, without
  resolving original timeline coordinates against the shifted timeline.
- Same-clip splits retain fake placement lineage. Repeated media placements remain distinct.
- Explicit errors for unsupported/invalid requests; no automatic rebase.
- Python 3.14.6 local virtual environment with declared dev dependencies installed.

Test-first evidence:
1. Wrote independent naive frame-list oracle and domain acceptance tests before source code.
2. Opt-in naive invariant assertion: **1 failed, 1 passed**. After deleting original
   [900,960), deleting current [2700,2760) incorrectly removes original [2760,2820).
   Original [2700,2760) remains. First differing output index: 2640.
3. Domain test collection failed with missing `davinci_ai_editor.domain` before implementation.
4. Implemented domain and FakeTimeline, then ran all available tests and static checks.

Final validation:
- `python -m pytest -q`: **25 passed, 0 failed, 1 skipped**.
- Skipped test is only the opt-in intentional naive failure; ordinary naive regression runs.
- `python -m ruff check src tests`: passed.
- `python -m mypy`: passed (3 source files).
- INV-001 at 30 fps: first applied range [900,960), second [2640,2700),
  while original second target remains [2700,2760).
- Expected duration: 3600 - 120 = 3480 frames (120s to 116s); actual matches.
- Ordered remaining source-frame sequence equals the independent expected sequence;
  unexpected original-region deletion = 0 in these fixtures.
- Reverse command order, adjacent/end/whole-clip deletes, duplicate-media placements,
  invalid inputs, immutable snapshots and basic base-version rejection are covered.
- Only INV-001 has milestone coverage. INV-002..INV-018 remain TODO; basic guards do
  not certify the complete stale-plan/transaction/diff invariants or the P0 release gate.

Reproduce from repository root (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m mypy

# Expected intentional failure (exit code 1):
$env:REPRODUCE_NAIVE_FAILURE = '1'
.\.venv\Scripts\python.exe -m pytest tests/test_naive_inv001.py -q
Remove-Item Env:REPRODUCE_NAIVE_FAILURE
```

Open decisions:
- OPEN-001: persistent Resolve item identity (unchanged).
- OPEN-004: production range boundaries and cross-clip/track ripple scope.
- OPEN-003: split identity and version/transaction boundaries.
- OPEN-003/004 were recorded before implementation; fake conventions are not production decisions.

Known limitations:
- One track, integer frames, 1:1 source mapping; each target fits one current fragment.
- Overlapping targets, gap-spanning and cross-clip requests are explicitly unsupported.
- No Resolve/LLM/STT/UI, real media operations, relationships, retime, transitions,
  protected ranges, full safety pipeline, transaction engine or rollback.
- This is a test simulator, not authorization for production destructive editing.

Files changed/added:
- src/davinci_ai_editor/__init__.py
- src/davinci_ai_editor/domain.py
- src/davinci_ai_editor/fake_timeline.py
- tests/test_inv001.py
- tests/test_naive_inv001.py
- pyproject.toml (local src discovery for the configured mypy package check)
- DECISIONS.md
- KNOWN_LIMITATIONS.md
- IMPLEMENTATION_STATUS.md
- docs/TEST_MATRIX.md
- tasks/TASK_001_DOMAIN_AND_INV001.md

Recommended TASK-002:
- First confirm interval/ripple scope in OPEN-004 and how protection interacts with ripple.
- Test and implement only INV-002 unrequested content preservation (apart from approved
  ripple) and INV-003 protected ranges, using the existing fake/domain.
- Keep Resolve integration, production transaction/rollback, relationships and future
  invariants outside that task. TASK-002 has not been implemented.

Git setup:
- Repository: https://github.com/KIM0296/edit-program (origin).
- Repository-local author configured from user-provided name and email.
- Original specification and TASK-001 implementation recorded as separate commits.
- Existing remote initial commit is preserved when integrating main.
- No nested Codex session was launched.

TASK-001 Chat Gate: APPROVED WITH CHANGES (2026-10-05). ADR-008..012 accepted; TASK-002 authorized for INV-002/003 only.


## TASK-002 implementation - 2026-10-05

Approved basis: TASK-001 Chat Gate APPROVED WITH CHANGES and explicit authorization
of TASK-002 INV-002/003. ADR-008..012 recorded before code, ADR-007 moved into
Accepted Decisions, original required-type count corrected to 12. Prior TASK-001
sections above are historical; the current status is this section.

Implemented:
- Immutable HARD_LOCK ProtectedRange on snapshots. Direct overlap and earlier ripple
  (including before a protected gap) reject before any simulated deletion.
- EditPlan explicitly lists approved surviving-range ripple displacements. Missing,
  incorrect, duplicate or extra approval rejects before deletion. No automatic approval.
- Base-snapshot expected survivor layout is computed independently of sequential deletes.
  Candidate media/placement identity, source intervals, order and positions must match
  before publishing fake state. Production transaction/rollback is not implemented.
- One version increase per successful nonempty plan; rejection and no-op leave it unchanged.
- Scope stays one track, 1:1 mapping, ripple DELETE, single-fragment targets.

Test-first evidence:
- Before changes, two new INV-002 tests failed with DID NOT RAISE: missing displacement
  authorization and unrequested media corruption were accepted by TASK-001's fake.
- ProtectedRange acceptance suite initially could not collect because the type was absent.
- After implementation: 57 passed, 0 failed, 1 skipped locally (Windows / Python 3.14.6).
- Mypy passed (4 source files); Ruff checks passed after formatting/import cleanup.
- TASK-001 assertions remain; successful-plan fixtures now supply explicit displacement
  approvals required by ADR-011. Naive regression still runs; intentional red demo is skipped.
- CI workflow added for Python 3.11 with pytest, Ruff, mypy. Hosted PR run 37274008568 passed on Python 3.11.16: 57 passed, 1 skipped; Ruff and mypy passed.

Gate scope:
- INV-001/002/003 verified for the fake only. INV-004..018 remain unverified/incomplete.
- No Resolve, A/V relationships, retime, transition, transaction/rollback or AI added.
- TASK-002 Chat Gate requested after PR/CI evidence; no merge or TASK-003 authorization.

TASK-002 PR: https://github.com/KIM0296/edit-program/pull/1
CI evidence: https://github.com/KIM0296/edit-program/actions/runs/37274008568
Standard report: docs/reports/TASK_002_COMPLETION.md. Requested Gate: APPROVED (request only, not Chat decision).


## TASK-003 Relationship Domain Foundation - 2026-10-05

User approval: TASK-002 Chat Gate APPROVED, PR #1 merged. Main base 747474a.
TASK-003 specification committed first (88d1257), followed by tests, missing-type
collection failure, minimal implementation and full regression verification.

Implemented:
- TrackType, fake-only TimelineObjectId, RelationshipId/Type/Member/Policy,
  Relationship and immutable RelationshipGraph as part of TimelineSnapshot.
- Typed n-ary membership and per-member FOLLOW/STAY/RECALCULATE/REVIEW metadata;
  no implied alignment, shared displacement or policy execution.
- Graph construction/addition rejects missing members and duplicate IDs. Snapshot
  binding additionally requires the graph registry to match actual placement lineages.
- Object IDs distinguish track/placement, not media or coordinates. Legal split fragments
  share fake lineage; conflicting media/overlapping source under one lineage reject.
- J/L-cut ranges and source ranges remain unchanged when relationships are represented.
- Nonempty relation-bearing plans explicitly reject for REVIEW before simulated delete.
  Existing relation-free execution rebuilds its empty graph registry after deletion.

Local verification: Windows / Python 3.14.6, 83 passed / 0 failed / 1 skipped;
Ruff passed, mypy passed (4 source files). All four TASK-001/002 test files are unchanged.
The skipped test remains the opt-in intentional naive failure demonstration.
Python 3.11.16 CI: 83 passed / 0 failed / 1 skipped, Ruff and mypy passed (run 37276145821). No Resolve/A/V correction/subtitle/B-roll/multi-track
ripple/transaction/rollback/retime/AI added. INV-004/full INV-006 remain unverified.
OPEN-001 retained; OPEN-005 records role/cardinality/policy-conflict and split/delete
lifecycle decisions for future execution. No next TASK is authorized.

TASK-003 PR: https://github.com/KIM0296/edit-program/pull/2
Standard report: docs/reports/TASK_003_COMPLETION.md. Requested Gate: APPROVED (request only, not a Chat decision).


## TASK-004 Timeline Topology / Preserve Editability - 2026-10-05

Approved basis: user TASK-003 APPROVED / PR #2 merged; main 642f9f4.
Spec and approved product/safety notes committed first (dc32051), tests written next
and confirmed missing-topology-module collection failure, followed by minimal implementation.

Implemented pure topology.py (no executor changes):
- Track ID/type/order and object identity/current membership stored separately.
- Snapshot projection and explicit one-to-one fake identity bindings; no matching by media.
- Exact TopologyDiff and base-bound ExpectedTopologyChange comparison.
- Track additions/removals/type/index changes and object additions/removals/moves detected.
- Reject PREVIEW/RENDER/FLATTENED as editable source state regardless of approval.
- Conservative REVIEW for native-tagged whole multi-layer collapse into one new replacement.
- Existing native objects can survive explicitly approved layer deletion; count reduction
  alone is not treated as flatten. Relationship records cannot silently change.
- Pure projection/comparison does not alter snapshots, graphs or versions.

Local verification: Windows/Python 3.14.6, 114 passed / 0 failed / 1 skipped;
Ruff passed; mypy passed (5 source files). All TASK-001/002/003 test files unchanged.
Python 3.11.16 CI passed (run 37279654222): 114 passed / 0 failed / 1 skipped, Ruff/mypy passed. INV-019 coverage is limited to supplied fake topology/provenance;
no production native editability or all P0 certification is claimed.
OPEN-006/007 record identity/index/provenance uncertainties; OPEN-001/005 retained.
Effect/VFX preferences are notes only. No Resolve/multi-track ripple/A-V/effect/Fusion/
subtitle/B-roll/transaction/rollback/retime/AI/external-tool execution added.

TASK-004 PR: https://github.com/KIM0296/edit-program/pull/3
Standard report: docs/reports/TASK_004_COMPLETION.md. Requested Gate: APPROVED (request only, not Chat decision).


## TASK-005 Relationship Resolver / Dependency Plan Compiler - 2026-10-05

Base main: 4d003fe3ad75dbc7cc8807903868965e2be6643f. Approved basis: user TASK-005
and ADR-013. Spec/OPEN-005 application committed first: 1dd8001.
New tests then failed collection with missing davinci_ai_editor.dependency (red-first).

Implemented:
- Optional explicit PEER/DRIVER/DEPENDENT roles; legacy None never inferred from order.
- Immutable primary intent, fragment evidence, actions, reasons, conflicts, SCC cycles,
  compiled plan/status. Pure compiler reads snapshot graph and matching native topology.
- Finite conservative incidence closure; explicit role arcs only for directed SCC diagnosis.
- Six action-specific triggers; no delete cascade, alignment, movement or retime commands.
- Subtitle DELETE/TRIM produces RECALCULATE assessment, not automatic subtitle deletion.
- Conflicting policy requirements retained without priority; ambiguous fragments REVIEW.
- All reached relationships REVIEW; RETIME UNSUPPORTED. Dependency-free MOVE/RIPPLE/
  TRIM/DELETE may continue planning, never bypass independent safety/execution gates.
- No modifications to FakeTimeline/safety/topology execution or earlier regression tests.

Local Windows / Python 3.14.6: 158 passed, 0 failed, 1 skipped (44 new compiler tests).
Skipped test is the existing opt-in intentional naive failure demonstration.
Ruff passed; strict mypy passed (6 source files). Python 3.11.16 hosted CI passed:
run 37282763459, 158 passed / 1 skipped, Ruff/mypy passed.
OPEN-001/005/006/007 retained; OPEN-005 application records deferred exact execution,
cardinality, fragment rebinding, native linked selection and sync offsets.
No production Resolve, real edit, rollback, multitrack execution or next task started.
PR: https://github.com/KIM0296/edit-program/pull/6
Standard report: docs/reports/TASK_005_COMPLETION.md. Requested Gate: APPROVED (request only).
During implementation, main advanced to 6421b8d with ADR-014/Track Stewardship v1.
Merged that documentation at 40781ce; no TASK-005 scope expansion or source change.


## TASK-006 Candidate Authority / Concurrent Work State - 2026-10-05

Approved basis: TASK-005 APPROVED/PR #6 merged; ADR-015/016 and explicit TASK-006 request.
Main base fe8ee5ee188df52fe930f4d1dac47d57fa329544. New branch:
feat/task-006-candidate-concurrency-state. Spec/OPEN/product notes committed before code
at f552852. New tests failed collection with missing davinci_ai_editor.authority first.

Implemented:
- Separate immutable selection, approval, validity, application, verification, promotion
  and work-phase axes. Every candidate has explicit base identity/version and lineage.
- Pure selection/explicit approval/preview/progress events never implicitly promote.
- Whole-version/identity mismatch invalidates; stale remains blocked without rebase.
- Explicit human observation updates current authority version knowledge, never a
  preview pointer. Source base/approval/application/verification history is not rewritten.
- Bound fake application/result/verification evidence and guarded verified promotion.
  No actual Apply/Postflight is implemented; caller facts do not prove native operations.
- Same-base exploration branching copies no approval/result/authority and cannot refresh stale.
- Attention Economy's four principles documented only; small commands remain allowed.

Local Windows/Python 3.14.6: 210 passed / 0 failed / 1 skipped (52 new state tests).
Ruff PASS; strict mypy PASS (7 source files). Hosted Python 3.11.16 CI also passed:
run 37287250147, 210 passed / 1 skipped, Ruff/mypy PASS.
The skipped case remains the opt-in intentional naive failure; earlier regressions unchanged.
OPEN-002 partially resolved by ADR-015/016, production representation/evidence still OPEN.
OPEN-008 records DIRTY/STALE, scope/changeset/refresh, multiple approvals/revocation,
retention/persistence questions. Production WorkingAuthority/result identity not settled.
No actual timeline/candidate creation, apply/observer/rollback/Resolve/UI/AI introduced.
Standard report: docs/reports/TASK_006_COMPLETION.md. Requested Gate: APPROVED (request only).

TASK-006 PR: https://github.com/KIM0296/edit-program/pull/8
CI evidence: https://github.com/KIM0296/edit-program/actions/runs/37287250147

## TASK-007 Pause Candidate Domain / Deterministic Baseline - 2026-10-06

Approved basis: TASK-006 APPROVED/merged and ADR-018; main a7270ee.
Spec/OPEN-009 committed first (a18907c). New tests failed collection with missing
pause module before implementation. Branch feat/task-007-pause-candidate-baseline.

Implemented immutable PauseObservation/PauseCandidate and pure classify_pause:
- Caller-supplied relative band, boundary, multi-signal evidence, scope and local reference.
- KEEP/TIGHTEN/REMOVE/REVIEW, HIGH/MEDIUM/LOW, structured reasons and routing metadata.
- Explicit gap evidence only for REMOVE; meaningful pause KEEP; conflicts REVIEW.
- TIGHTEN uses only a positive supplied reference shorter than the original pause.
- No seconds thresholds, inferred feature values, global targets or numeric probabilities.
- UNKNOWN/unsupported/unsafe target fail closed. Routing is not execution permission.

Local Windows/Python 3.14.6: 277 passed / 0 failed / 1 skipped; 67 new tests.
Ruff PASS; strict mypy PASS (8 source files). Hosted Python 3.11.16 CI passed:
run 37405319840, 277 passed / 1 skipped, Ruff/mypy PASS.
Systematic all signal subsets x relative bands x boundaries check removal/target safety.
Existing TASK-001..006 tests/source unchanged. Executor/authority monkeypatch guard passes.
OPEN-009 records observation producers/media mapping/dialogue schema; OPEN-001 retained.
No STT/VAD/ML/LLM/media analysis/Resolve/edit plan/authority integration/shadow/UI added.
Report: docs/reports/TASK_007_COMPLETION.md. Chat Gate requested after PR/CI evidence.

TASK-007 PR: https://github.com/KIM0296/edit-program/pull/11
CI: https://github.com/KIM0296/edit-program/actions/runs/37405319840
Requested Gate: APPROVED (request only, not Chat decision).

## TASK-008 Evaluation Schema / Pure Metric Foundation - 2026-10-06

Approved basis: TASK-007 / PR #11 APPROVED and merged; ADR-019. Main base 3c1ca49.
Spec/OPEN-010 committed before code (af180f8). New tests failed collection due to missing
'davinci_ai_editor.evaluation' before implementation. Branch feat/task-008-evaluation-schema.

Implemented:
- Immutable source-separated case/proposal/producer/reference/annotation records.
- Typed append-only event episodes, canonical contiguous sequence and payload validation.
- Derived final outcomes, explicit correction taxonomy, distinct actual removal restoration.
- Immutable workflow/activity evidence with explicit timing completeness; missing is not zero.
- Pure human/attention/correction cost, paired Net Time Saved, safety/editorial metrics.
- Exact Fraction rates, explicit version/provenance and denominator counts; no gate thresholds.
- PRODUCT_FEEDBACK cannot carry benchmark references; raw evidence never mutated by metrics.

Local Windows/Python 3.14.6: 342 passed / 0 failed / 1 skipped (65 new tests).
Ruff PASS; strict mypy PASS (10 source files). Python 3.11 hosted CI pending.
Existing TASK-001..007 code/tests unchanged. Classifier/executor/authority monkeypatch guard passes.
Skip remains the opt-in intentional naive red demo. No production editing/P0 certification.
OPEN-010 records event episode/recovery/timing completeness/overlap/pairing provenance;
NEAR_RANGE tolerance and future numeric GatePolicy remain undefined.
No DB, telemetry/listener/upload/UI, media capture, dataset/pilot, training/personalization.
Report: docs/reports/TASK_008_COMPLETION.md. Chat Gate requested after PR/CI evidence.
