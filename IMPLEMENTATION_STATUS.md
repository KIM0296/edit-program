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

- [ ] Relationship Graph
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

Current task: `TASK-002` implemented on feat/task-002-inv002-inv003; PR #1 created, Python 3.11 CI passed; Chat Gate pending. TASK-001 approved with changes.


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
