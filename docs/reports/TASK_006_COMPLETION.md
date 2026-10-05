# TASK 완료 보고서

TASK: TASK-006 — Candidate Authority & Concurrent Work State Foundation

상태: 구현 및 로컬/Python 3.11 CI 검증 완료, Chat Gate 대기.

브랜치: `feat/task-006-candidate-concurrency-state`

Spec commit: `f552852` (구현 전). 구현 commit: `5fb6901`.

Base main: `fe8ee5ee188df52fe930f4d1dac47d57fa329544`.
후속 보고 commit은 문서만 변경합니다. 최종 제출 SHA는 PR 본문에 기록합니다.

PR: https://github.com/KIM0296/edit-program/pull/8

근거: [TASK-006 spec](../../tasks/TASK_006_CANDIDATE_CONCURRENCY_STATE.md),
[ADR-015](../CANDIDATE_AUTHORITY.md), [ADR-016](../PARALLEL_EDITING.md).

요청 Gate: **APPROVED** (Codex 요청이며 Chat 판정 아님).

## 1. 구현 내용

선택·승인·유효성·적용·검증·승격·작업 단계를 별도 immutable axis로 모델링했습니다.
현재 화면의 Active Timeline과 이후 요청의 Working Authority를 분리했습니다.
동작은 frozen 입력을 받아 새 state/result를 반환하는 pure transition입니다.

- Candidate ID, 원본 timeline/version, immutable ancestor lineage를 보유합니다.
- Selection은 selection만, 명시적 approval event는 approval만 변경합니다.
  승인·선택·phase 변경·preview 활성화가 적용이나 authority 변경을 일으키지 않습니다.
- 원본과 현재 authority의 ID/version이 다르면 STALE이고 eligibility는 false입니다.
  승인 후 human edit가 생겨도 승인 이력은 보존하되 적용·승격을 차단합니다.
- Stale 상태를 phase 변경/branch/예전 version 복원으로 fresh로 만들지 않습니다.
- ApplicationRecord는 candidate/base/result에 결합된 외부 제공 fake fact입니다.
  Verification도 그 정확한 기록을 참조해야 하며 다른 result나 재사용 기록은 거절합니다.
- Promotion은 approved + applied + verified + fresh 및 현재 result 관측값 일치가
  모두 충족된 경우에만 명시적으로 Working Authority를 갱신합니다.
- Branch는 같은 원본 base의 새 탐색 후보입니다. 부모의 approval/result를 복사하지
  않으며, 부모·authority를 변경하거나 stale을 해소하지 않습니다.
- WorkPhase는 ANALYZING/BUILDING_CANDIDATE/READY의 정보성 값입니다. DIRTY는 미정입니다.
- Attention Economy 네 원칙을 기록했습니다. 작은 명령 금지나 UI/telemetry 구현은 없습니다.

| Acceptance | 결과와 근거 |
| --- | --- |
| 분리된 immutable axes/base/lineage | PASS: 타입·불변성·branch 테스트 |
| Selection != approval != apply != promotion | PASS: one-axis 변경과 authority 유지 |
| Human Edit Wins / stale / no rebase | PASS: v42/v45, 다른 timeline 동일 version, sticky invalidation |
| Invalid promotion rejection | PASS: created/selected/approved/unverified/stale/failed verification 거절 |
| Verified promotion | PASS: 정확한 supplied result로만 authority 갱신; 실제 mutation 없음 |
| Active != Working | PASS: preview switch는 active ID만 변경 |
| Determinism / no execution | PASS: 반복 event 결과 동일; FakeTimeline.apply를 실패하도록 교체해도 통과 |
| TASK-001~005 regression | PASS: 기존 테스트·executor 파일 변경 없음 |
| Python 3.11 CI | PASS: run 37287250147, CPython 3.11.16 |
| Ruff / strict mypy | PASS: 7 source files |

범위 밖의 Resolve, 실제 candidate timeline/duplication, actual Apply/postflight,
transaction/rollback, rebase/merge/refresh, observer/watcher, UI/notifications/telemetry,
A/V/subtitle/B-roll/retime/effects/LLM 구현은 없습니다.

## 2. 변경된 파일

| 파일 | 목적 |
| --- | --- |
| tasks/TASK_006_CANDIDATE_CONCURRENCY_STATE.md | 구현 전 domain/events/guard 및 OPEN 경계 명시 |
| DECISIONS.md | OPEN-002 부분 해결, OPEN-008 미정 concurrency 계약 |
| docs/PRODUCT_SPEC.md | Attention Economy 네 가지 승인 원칙 |
| docs/CANDIDATE_AUTHORITY.md | UX 흐름과 분리된 state axes, evidence 한계 |
| docs/PARALLEL_EDITING.md | 현재 strict version subset와 향후 scope 기능 구분 |
| src/davinci_ai_editor/authority.py | immutable state, eligibility와 pure transitions |
| tests/test_candidate_authority.py | 신규 52개 시나리오·거절·불변성 테스트 |
| IMPLEMENTATION_STATUS.md | TASK-005 승인/현재 TASK-006 및 검증 결과 |
| KNOWN_LIMITATIONS.md | fake evidence/provenance, stale/branch/authority 한계 |
| docs/TEST_MATRIX.md | 사용자 10개 시나리오와 회귀 검증 근거 |
| docs/reports/TASK_006_COMPLETION.md | 이 표준 완료 보고서 |

### git diff --stat

비교: base main `fe8ee5e` 대비 이 보고서를 포함한 제출 tree.

```text
 DECISIONS.md                                  |  50 ++-
 IMPLEMENTATION_STATUS.md                      |  35 +-
 KNOWN_LIMITATIONS.md                          |  24 ++
 docs/CANDIDATE_AUTHORITY.md                   |  17 +
 docs/PARALLEL_EDITING.md                      |  17 +
 docs/PRODUCT_SPEC.md                          |  17 +
 docs/TEST_MATRIX.md                           |  22 ++
 docs/reports/TASK_006_COMPLETION.md           | 185 +++++++++++
 src/davinci_ai_editor/authority.py            | 432 +++++++++++++++++++++++++
 tasks/TASK_006_CANDIDATE_CONCURRENCY_STATE.md | 106 ++++++
 tests/test_candidate_authority.py             | 442 ++++++++++++++++++++++++++
 11 files changed, 1338 insertions(+), 9 deletions(-)
```

## 3. 테스트 결과

- 로컬 환경: Windows / Python 3.14.6. Resolve 미사용.
- Passed: 신규 52개; 전체 210개. Ruff PASS, strict mypy PASS (7 source files).
- Failed: 최종 0개. 구현 전 authority 모듈 부재의 collection failure 확인.
  초기 Ruff import ordering 1건은 수정 후 전체 PASS.
- Skipped: 기존 opt-in intentional naive red test 1개. 일반 naive 회귀는 실행됨.
- 미실행: 실제 Apply/postflight/Resolve/concurrent observer/rollback. 범위 밖이며 별도 승인 필요.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_candidate_authority.py -q
# 52 passed
.\.venv\Scripts\python.exe -m pytest -q
# 210 passed, 1 skipped
.\.venv\Scripts\python.exe -m ruff check src tests
# All checks passed!
.\.venv\Scripts\python.exe -m mypy
# Success: no issues found in 7 source files
```

Red-first: spec `f552852` commit 후 새 테스트 실행은
`ModuleNotFoundError: No module named 'davinci_ai_editor.authority'`로 실패했습니다.
이후 최소 state foundation을 구현했습니다.

Hosted CI: [run 37287250147](https://github.com/KIM0296/edit-program/actions/runs/37287250147), head `e7a5d3e` 기준. Ubuntu/CPython 3.11.16에서 210 passed / 1 skipped, Ruff PASS, mypy 7 files PASS를 job log로 확인했습니다. 후속 변경은 문서만이며, 최종 PR head CI도 검토 제출 전 확인합니다.

### Safety Gate

| Invariant | 결과 | 근거와 검증 범위 |
| --- | --- | --- |
| Wrong target edit | PASS (fake scope) | INV-001 회귀, candidate/base/result evidence mismatch 거절 |
| Protected range violation | PASS (TASK-002 fake scope) | HARD_LOCK 회귀 유지; eligibility는 Safety Core 승인 아님 |
| Silent timeline damage | PASS (기존 fake 범위) | INV-002/019 회귀 및 pure state 입력 불변 |
| A/V sync regression | 미검증 (execution) | 기존 relationship/no-normalization 회귀만 유지 |
| Failed rollback | 미검증 | transaction/rollback 구현 없음 |
| Stale / Human Edit Wins | PASS (state scope) | 모든 ID/version mismatch 차단; 실제 concurrent writer/observer 미검증 |

INV-012/017 전체나 production P0 release gate의 완료를 주장하지 않습니다.

## 4. 구현 과정에서 발견한 설계 문제

버전 비교만으로 live 관측의 진실성, application/postflight 수행 사실, crash 복구,
commit 시점 race를 증명할 수 없습니다. 따라서 입력 evidence를 fake fact로 명시하고
그 결합과 state transition만 검증합니다. Real event producer나 자동 관측은 없습니다.
또한 현재 version만으로 DIRTY와 STALE 또는 독립 구간의 무해한 변경을 구분할 수 없어
미정 의미를 추가하지 않았습니다. 운영 provenance/coordination은 Chat 결정이 필요합니다.

## 5. DECISIONS.md OPEN 항목

- **OPEN-002 (부분 해결):** ADR-015/016의 상태 분리/authority 원칙은 해결됐습니다.
  실제 candidate 형태, result identity, production authority timeline-only vs version
  schema 및 evidence provenance/동일 timeline apply 관측 순서는 여전히 미정입니다.
  Native reference와 virtual plan mapping 중 임의 선택하지 않았습니다. 테스트에는
  명시적 fake token/관측값을 쓰되 production 채택은 보류하는 방식을 권고합니다.
- **OPEN-008 (신규):** DIRTY/STALE 구분, scope-aware invalidation, changeset, partial
  refresh, retention, multiple approvals, revoke, crash/restart persistence.
  지금 규칙을 추론하면 human priority를 훼손할 수 있어 strict whole-version invalidation과
  미정 transition 미구현을 권고합니다. Coordinator/refresh/revoke/storage가 이에 의존합니다.
- OPEN-001 production persistent identity 등 이전 OPEN을 해결로 표시하지 않았습니다.

## 6. KNOWN_LIMITATIONS.md 변경 사항

Fake state/evidence 모델이고 실제 운영 보안·transaction 경계가 아닙니다.
Eligibility는 candidate authority 전제만 검사하며 protection/topology/relationship
preflight를 대체하지 않습니다. WorkPhase도 승인이나 실행 gate가 아닙니다.
Promotion 뒤 원본 base는 바뀌지 않으므로 기존 proposal의 validity는 STALE이 될 수 있지만
과거 applied/verified/promoted 기록은 유지됩니다. 새 요청 후보에는 현재 authority base가
명시적으로 필요합니다. Applied-result branching은 아직 지원하지 않습니다.
이 한계는 result identity/provenance/changeset/coordination 계약 승인 후 별도 작업으로 해결합니다.

## 7. Specification과 다르게 구현한 부분

기능 범위 차이 없음. optional 작업 단계를 정보성 축으로만 구현했고 DIRTY는 OPEN으로
남겼습니다. ResultRef와 WorkingAuthority의 timeline/version 값은 spec에 적은 fake 관측
표현이며 production schema 결정을 의미하지 않습니다. Timeline version을 자동 증가시키는
Apply 함수나 candidate를 자동 생성하는 시스템은 없습니다.

## 8. 다음 TASK 제안

TASK-007 범위 확정 전에 OPEN-002의 result evidence/authority 관측 계약을 Chat에서
정의할 것을 제안합니다. 예: candidate artifact와 승인 결합, application/postflight evidence의
생성 주체 및 현재 authoritative observation 검증 경계. Acceptance 초안은 stale evidence,
다른 candidate/result, 관측 순서 역전과 replay의 fail-closed 검증입니다.
현재 미승인이며 다음 TASK는 착수하지 않았습니다. 실제 Resolve 연동은 별도 승인 대상입니다.

## 9. Chat 검토란

- 판정: Chat 작성 대기.
- 판정 근거: TASK spec / 표준 보고서 / PR 및 CI.
- 필수 수정 및 재검증: Chat 작성.
- 다음 TASK / 병행 허용 범위: 미승인.
- 승인 기록 링크: 없음 (APPROVED는 요청).
