# TASK 완료 보고서

TASK: TASK-005 — Relationship Resolver & Dependency Plan Compiler
상태: 구현 완료, Chat Gate Review 대기
브랜치: `feat/task-005-relationship-resolver`
Spec commit: `1dd8001` (구현 전)
구현 commit: `7f16b61beaea66995600a49cad4829bbbe2f72cb`
최신 main 문서 반영 commit: `40781ce8209983bf7fa6207fda59cec45b3da9f9`
이 보고서를 추가한 후속 commit은 문서만 변경합니다. 최종 head SHA는 PR에서 확인할 수 있습니다.
PR: https://github.com/KIM0296/edit-program/pull/6
근거: [TASK-005 spec](../../tasks/TASK_005_RELATIONSHIP_RESOLVER.md), [ADR-013](../RELATIONSHIP_EXECUTION_SEMANTICS.md)
요청 Gate: **APPROVED** (Codex의 요청이며 Chat 판정이 아님)

## 1. 구현 내용

실제 timeline을 변경하지 않고 primary intent와 immutable base snapshot의 관계,
동일 base의 topology를 읽어 dependency 검토 plan을 반환합니다.

- `RelationshipRole` PEER / DRIVER / DEPENDENT 추가. 기존 member의 role 기본값은
  None이며 순서로 역할을 추론하지 않습니다.
- MOVE / RIPPLE / TRIM / DELETE / SPLIT / RETIME을 구분하는 primary intent와
  action별 review reason, concrete fragment evidence를 구현했습니다.
- Snapshot의 connected relationship context를 유한한 incidence closure로 수집합니다.
  이 범위에는 upstream/peer도 보수적으로 포함되며 실행 전파 방향을 의미하지 않습니다.
- Object/relationship별 검토 후보를 deduplicate하며 fragment 수나 경로 수에 따라
  relationship 또는 dependent action을 복제하지 않습니다.
- 명시적 DRIVER → DEPENDENT graph에서 iterative SCC 검출을 수행합니다.
  실제 cycle과 diamond/대칭 PEER 관계를 구분하며 재귀 side effect가 없습니다.
- 정책 충돌의 모든 근거를 보존하고 우선순위를 선택하지 않습니다.
- SAFE_TO_CONTINUE / REVIEW_REQUIRED / UNSUPPORTED를 구현했습니다.
  관계가 있으면 REVIEW, RETIME은 UNSUPPORTED입니다. SAFE는 관계 없는 유효 입력의
  후속 planning 허용만 뜻하며 Safety Core나 실행 승인을 대체하지 않습니다.

| Acceptance criteria | 결과와 근거 |
| --- | --- |
| Graph/snapshot 읽기 전용 | PASS: 입력 repr 및 불변 결과 검증, 버전 변화 없음 |
| Determinism, member order 독립 | PASS: 반복 compile 및 members/relationships/registry 순열 비교 |
| DELETE cascade 없음 | PASS: AV/anchor REVIEW, subtitle DELETE/TRIM RECALCULATE 후보 |
| J/L cut 보존 | PASS: 서로 다른 원본 boundary 유지, boundary normalize 명령 없음 |
| Conflict / cycle | PASS: FOLLOW/STAY 충돌 근거, SCC와 diamond/PEER 구분 |
| Unrelated exclusion | PASS: disconnected cycle 및 같은 media의 별도 placement 제외 |
| Fragment 모호성 | PASS: 다중 fragment 후보 하나와 REVIEW, 임의 pairing 없음 |
| Fail closed | PASS: stale/missing target, base topology 불일치, SPLIT/RETIME/legacy role |
| TASK-001~004 회귀 | PASS: 기존 테스트 파일 변경 없음 |
| Python 3.11 / Ruff / mypy | PASS: 아래 hosted CI 근거 |

실제 mutation/Resolve API/multitrack ripple/sync correction/subtitle retiming/B-roll 이동/
transaction/rollback/retime/effect/Fusion/AI/external VFX/production identity는 구현하지 않았습니다.

## 2. 변경된 파일

| 파일 | 변경 목적 |
| --- | --- |
| tasks/TASK_005_RELATIONSHIP_RESOLVER.md | 구현 전 상태·역할·응답·closure·검증 계약 |
| DECISIONS.md | OPEN-005에 TASK-005 적용과 보류 범위 기록 |
| src/davinci_ai_editor/domain.py | 명시적 optional relationship role |
| src/davinci_ai_editor/dependency.py | immutable dry-run compiler 및 planning domain |
| tests/test_dependency_compiler.py | 44개 신규 acceptance/안전성 테스트 |
| IMPLEMENTATION_STATUS.md | 구현·승인 이력·검증 상태 |
| KNOWN_LIMITATIONS.md | planning-only 의미와 보수적 review 한계 |
| docs/TEST_MATRIX.md | 시나리오별 검증 근거 |
| docs/reports/TASK_005_COMPLETION.md | 표준 완료 보고서 |

작업 시작 base는 `4d003fe`였습니다. PR 생성 중 main의 Track Stewardship v1 병합
(`6421b8d`)을 확인해 해당 문서만 merge했습니다. ADR-014와 TASK-005는 충돌하지 않으며,
새 track 역할이나 placement 실행을 추가하지 않았습니다. 아래 diff는 최신 main
`6421b8d7f56945b7dc7159bdabbb6086f6eaf47b` 대비 이 보고서를 포함한 PR 제출 tree 기준입니다.
따라서 upstream ADR-014/TRACK_STEWARDSHIP 문서는 TASK-005 변경 파일로 집계하지 않습니다.

### git diff --stat

```text
 DECISIONS.md                            |  18 ++
 IMPLEMENTATION_STATUS.md                |  33 ++-
 KNOWN_LIMITATIONS.md                    |  27 ++-
 docs/TEST_MATRIX.md                     |  22 ++
 docs/reports/TASK_005_COMPLETION.md     | 182 +++++++++++++++
 src/davinci_ai_editor/dependency.py     | 391 +++++++++++++++++++++++++++++++
 src/davinci_ai_editor/domain.py         |  13 +-
 tasks/TASK_005_RELATIONSHIP_RESOLVER.md | 108 +++++++++
 tests/test_dependency_compiler.py       | 403 ++++++++++++++++++++++++++++++++
 9 files changed, 1194 insertions(+), 3 deletions(-)
```

## 3. 테스트 결과

- 로컬: Windows / Python 3.14.6.
- Hosted CI: Ubuntu / CPython 3.11.16.
- Passed: 전체 pytest 158개, 신규 compiler 44개. Ruff PASS, strict mypy PASS (6 source files).
- Failed: 최종 0개. 구현 전 missing compiler collection error를 확인한 후 구현했습니다.
  초기 Ruff import ordering 1건은 수정 후 전체 검사 PASS입니다.
- Skipped: 기존 opt-in intentional naive failure 1개. 일반 naive 회귀는 실행됩니다.
- 미실행: 실제 Resolve/미디어/A-V 수정/rollback 통합 검증. 범위 밖이며 후속 승인 task가 필요합니다.

### pytest 결과

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dependency_compiler.py -q
# 44 passed
.\.venv\Scripts\python.exe -m pytest -q
# 158 passed, 1 skipped
.\.venv\Scripts\python.exe -m ruff check src tests
# All checks passed!
.\.venv\Scripts\python.exe -m mypy
# Success: no issues found in 6 source files
```

Red-first: 같은 신규 test command가 구현 전
`ModuleNotFoundError: No module named 'davinci_ai_editor.dependency'`로 실패했습니다.
Spec은 이미 `1dd8001`로 commit된 상태였습니다.

Hosted CI: [run 37282763459](https://github.com/KIM0296/edit-program/actions/runs/37282763459),
PR 구현 head `7f16b61` 기준. Job log에서 CPython 3.11.16, 158 passed / 1 skipped,
Ruff PASS, mypy 6 files PASS를 확인했습니다. 이후 변경은 upstream 문서 merge와
완료 보고 문서이며, 최종 PR head의 CI도 검토 제출 전에 확인합니다.

### Safety Gate

| Invariant | 결과 | 근거와 검증 범위 |
| --- | --- | --- |
| Wrong target edit | PASS (fake scope) | INV-001 회귀와 compiler base/fragment binding 검사 |
| Protected range violation | PASS (TASK-002 fake scope) | HARD_LOCK 회귀 유지. Compiler SAFE는 protection 승인 아님 |
| Silent timeline damage | PASS (범위 한정) | INV-002/019 회귀, compiler 입력 무변경; production 미검증 |
| A/V sync regression | 미검증 (execution) | J/L boundary와 no-cascade 검증만 PASS. 실제 sync 수정 없음 |
| Failed rollback | 미검증 | transaction/rollback 범위 밖 |

전체 P0 release gate 또는 INV-004/full INV-006의 완료를 주장하지 않습니다.

## 4. 구현 과정에서 발견한 설계 문제

기존 graph는 role과 action-specific offset/mapping을 갖지 않습니다. 같은 fake lineage가
여러 concrete fragment를 가질 수도 있습니다. 따라서 generic FOLLOW로 결과 위치나
동기화를 확정할 수 없습니다. 명시적 role만 추가하고 legacy/fragment/정확한 실행 의미는
REVIEW로 남겼습니다. Closure는 영향 검토 후보이며 실행 reachability가 아닙니다.
구체적인 type별 cardinality, fragment rebinding, sync reference는 Chat 결정이 필요합니다.

## 5. DECISIONS.md의 OPEN 항목

신규 번호를 만들지 않고 기존 **OPEN-005** 아래 TASK-005 적용 근거를 추가했습니다.

- 결정 대상: AV_LINK PEER 규칙, SYNC_GROUP leader, type별 cardinality,
  split rebinding, Compound/Multicam, native Linked Selection, sync offset.
- 대안: generic FOLLOW를 실행 규칙으로 추론하면 편리하지만 ADR-013을 위반합니다.
  후보와 근거만 생성하면 review가 많아지지만 현재 계약을 지킬 수 있습니다.
- 권고: action별 의미가 승인될 때까지 후자를 유지합니다.
- 보류: concrete action lowering, 실행/자동 propagation/rebinding.
- OPEN-001 production persistent identity, OPEN-006 topology correspondence,
  OPEN-007 native provenance도 해결로 표시하지 않았습니다.

## 6. KNOWN_LIMITATIONS.md 변경 사항

- 모든 relation-bearing input은 REVIEW입니다. 보수적 upstream/peer closure와
  policy disagreement 검출은 실제 영향보다 많은 검토 후보를 만들 수 있습니다.
- MOVE 목적지/RIPPLE delta/temporal mapping은 이 planning foundation에 없습니다.
- Multi-fragment dependent는 하나의 후보에 evidence만 보관하고 REVIEW합니다.
- Base topology는 snapshot projection과 일치해야 하며 임의 identity remapping을
  compiler가 추론하지 않습니다. Native provenance는 여전히 fake 선언입니다.
- 기존 FakeTimeline은 relationship-bearing plan을 계속 거절합니다.
- 정확한 실행 의미/identity/mapping 계약이 승인되어야 이 한계를 축소할 수 있습니다.

## 7. Specification과 다르게 구현한 부분

기능 범위 차이 없음. 상태명, optional role, 보수적 closure, 모든 관계 REVIEW,
RETIME UNSUPPORTED 의미를 구현 전 spec에 명시했습니다. Universal Editing IR나
실제 executor를 추가하지 않았습니다. Scope에 없는 ADR-014 구현도 추가하지 않았습니다.

## 8. 다음 TASK 제안

제안: TASK-006 범위를 정하기 전에 OPEN-005 중 하나의 relationship/action 조합에
대한 concrete fragment binding 및 expected-result 계약을 Chat에서 확정합니다.
예를 들어 명시적 A/V relative sync reference와 MOVE dry-run 요구사항을 정의할 수 있습니다.
Acceptance 초안: 동일 offset 보존 증거, 의도적 J/L 차이 유지, ambiguity/conflict REVIEW,
기존 회귀 유지. Cardinality/offset/identity를 먼저 결정해야 합니다.
현재 미승인이며 실행/다음 TASK는 착수하지 않았습니다.

## 9. Chat 검토란

- 판정: Chat 작성 대기.
- 판정 근거: 이 보고서와 PR #6, spec 및 CI 결과.
- 필수 수정 및 재검증: Chat 작성.
- 다음 TASK / 병행 허용 범위: 미승인.
- 승인 기록 링크: 없음 (본 보고서의 APPROVED는 요청).
