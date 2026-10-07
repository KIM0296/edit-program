# TASK 완료 보고서

TASK: TASK-014 — Expected Diff & Temporal Displacement Foundation

상태: 구현 및 로컬 검증 완료, Python 3.11 CI/Chat Gate 대기.
브랜치: `feat/task-014-expected-diff`.
Base main: `b5bdedec90965764b7c2736f7d0e9012e657fe54`.
Spec notes: `46adfff`, red tests: `99bab2e`, 구현: `bb28291`.
후속 보고 commit을 포함한 최종 제출 head는 PR 본문에 기록합니다.
PR: 생성 후 기록.
근거: [TASK-014 spec](../../tasks/TASK_014_EXPECTED_DIFF_TEMPORAL_DISPLACEMENT.md),
[ADR-025 상세 계약](../EXPECTED_DIFF_TEMPORAL_DISPLACEMENT_CONTRACT.md).
요청 Gate: **APPROVED** (Codex 요청이며 Chat 판정 아님).

## 1. 구현 내용

하나의 PauseEditProposal, precomputed participation assessment, explicit PreservationScope에서
primary removal과 uniform temporal displacement를 완전히 기술하는 pure compiler 및
caller-supplied synthetic ActualDiff를 정확하게 비교하는 verifier를 구현했습니다.

| Acceptance | 결과 및 근거 |
| --- | --- |
| Immutable domain | PASS: nested frozen values, defensive copy, deterministic ordering |
| Primary change 분리 | PASS: proposal primary range 그대로 RangeRemovalEffect에 보존; TIGHTEN/REMOVE 테스트 |
| Participant selection 금지 | PASS: explicit 목록만 소비, same-track/downstream 및 empty set으로 자동 선택 안 함 |
| RESOLVED requirement | PASS: unresolved/conflict/unsupported/stale 및 uniform-consequence 미확인 차단 |
| Exact uniform delta | PASS: 모든 participant가 -removed duration; before/after start/end exact equality |
| Crossing / gap | PASS: fully downstream만 지원; crossing trim+move, gap absorption 추측 없음 |
| Pure displacement | PASS: placement/media/source/duration/track/retime metadata 보존; cross-track 거절 |
| Scope completeness | PASS: primary/participants/known impact가 scope에 포함; unlisted scope object는 unchanged |
| Topology | PASS: expected topology changes는 빈 tuple, 실제 reported topology 변경은 mismatch |
| Completeness vs Safety | PASS: protected risk가 있어도 complete diff 가능; Safety/Approval/Apply 필드 없음 |
| Human Edit Wins | PASS: proposal/geometry/assessment/scope/current base mismatch → STALE, no rebase |
| Synthetic verification | PASS: exact match, missing/extra changes, ±1 오류, source/media/duration/track 변화 검출 |
| Evidence required | PASS: identity/post relation 근거 부족 또는 unchanged observation 누락은 UNVERIFIED |
| Stale post relation | PASS: base/post/current 관계 불일치 및 explicit stale 차단 |
| Layer isolation | PASS: mapper/evaluator/planner/resolver/compiler/classifier/Safety/Authority/executor 호출 없음 |
| TASK-001~013 regression | PASS: 기존 source/test 변경 없이 전체 810 passed / 1 skipped |
| Ruff / strict mypy | PASS: 16 source files |
| Python 3.11 CI | PR 생성 후 확인 |

Participant policy, actual ripple, native post capture, Resolve mutation, protected-range Safety verdict,
transaction/rollback, authority 및 TASK-015는 구현하지 않았습니다. MATCH는 명시된 scope와
synthetic semantic evidence의 일치를 뜻하며 production Safety 인증이 아닙니다.

## 2. 변경된 파일

| 파일 | 목적 |
| --- | --- |
| src/davinci_ai_editor/expected_diff.py | Immutable domain, compiler 및 synthetic verifier |
| tests/test_expected_diff.py | 78개 신규 테스트 |
| tasks/TASK_014_EXPECTED_DIFF_TEMPORAL_DISPLACEMENT.md | 구현 전 API/증거 범위 notes와 상태 |
| DECISIONS.md | Native correspondence 관련 기존 OPEN 적용 범위 |
| IMPLEMENTATION_STATUS.md | 구현/검증 상태 |
| KNOWN_LIMITATIONS.md | Synthetic proof 및 native 미검증 한계 |
| docs/TEST_MATRIX.md | Red-first 및 테스트 범위 |
| docs/reports/TASK_014_COMPLETION.md | 표준 완료 보고서 |

### git diff --stat

비교 기준: 위 base main 대비 TASK-014 전체 변경(보고서 포함).

```text
 DECISIONS.md                                       |  15 +
 IMPLEMENTATION_STATUS.md                           |  24 +
 KNOWN_LIMITATIONS.md                               |  21 +
 docs/TEST_MATRIX.md                                |  18 +
 docs/reports/TASK_014_COMPLETION.md                | 153 +++++
 src/davinci_ai_editor/expected_diff.py             | 626 +++++++++++++++++++
 ...TASK_014_EXPECTED_DIFF_TEMPORAL_DISPLACEMENT.md |  32 +-
 tests/test_expected_diff.py                        | 682 +++++++++++++++++++++
 8 files changed, 1570 insertions(+), 1 deletion(-)
```

## 3. 테스트 결과

- 로컬: Windows / CPython 3.14.6, Resolve 연결 없음.
- `.venv\Scripts\python.exe -m pytest -q`: **810 passed, 0 failed, 1 skipped**.
- `.venv\Scripts\python.exe -m ruff check src tests`: **All checks passed!**
- `.venv\Scripts\python.exe -m mypy`: **Success: no issues found in 16 source files**, strict 설정.
- 신규 TASK-014 테스트 **78개**. 기존 TASK-001~013 source/test 변경 없음.
- Skip: `tests/test_naive_inv001.py:27`, 의도적 opt-in naive red demonstration.
  정상 INV-001 회귀 테스트는 항상 실행됩니다.
- Red-first: spec notes 이후 source 작성 전 `pytest tests/test_expected_diff.py -q`에서
  `ModuleNotFoundError: davinci_ai_editor.expected_diff`, collection error 1건 확인.
  테스트 commit `99bab2e` 이후 구현으로 green 전환했습니다.
- Python 3.11 GitHub CI: PR 생성 후 확인.
- 실제 Resolve/native post capture/실행/rollback 검증: 범위 밖으로 미실행.

### Safety Gate

| Invariant | 결과 | 근거 및 범위 |
| --- | --- | --- |
| Wrong target edit | PASS (기존 fake/domain 범위) | INV-001 회귀 및 bound placement/base 일치 검사 |
| Protected range violation | PASS (기존 fake/domain 회귀 범위) | 기존 INV-003 회귀; 신규 compiler는 protected Safety 판정을 하지 않음 |
| Silent timeline damage | PASS (기존 fake/domain 및 synthetic 비교 범위) | INV-002/topology 회귀, scoped unexpected change 및 정확한 actual diff 비교 |
| A/V sync regression | 실제 실행 미검증 | Independent J/L boundaries/source 보존 검사; native 실행 없음 |
| Failed rollback | 미검증 | Transaction/rollback 범위 밖 |

## 4. 구현 과정에서 발견한 설계 문제

Primary removal 후 native fragment identity를 생성하면 승인되지 않은 rebinding policy가 됩니다.
따라서 RangeRemovalEffect라는 semantic effect를 비교하고, 추가 primary 변경은 unexpected
change로 표현하도록 했습니다. Native post fragment 재구성과 인증은 구현하지 않았습니다.

단순히 actual changed list가 비어 있다는 사실만으로 unchanged를 증명할 수 없습니다.
Primary 외의 모든 scope 객체에 before/after observation을 요구하며, 미변경 객체의 관측 누락은
UNVERIFIED입니다. Expected participant 관측/변경 누락은 MISMATCH입니다.
Identity 또는 post-relation 근거가 부족하면 다른 mismatch 진단도 보존하면서 UNVERIFIED를 반환합니다.

## 5. DECISIONS.md에 추가한 OPEN 항목

신규 OPEN ID 없음. `TASK-014 application of OPEN-001/006/008/012 (remain OPEN)`에 기록했습니다.
Native identity, fragment correspondence, capture authenticity, scope-aware freshness는 계속 OPEN입니다.

Filename/media/lineage 기반 추론이라는 대안은 uncertainty를 숨기므로 사용하지 않았습니다.
권고안은 typed caller evidence를 보존하며 일치 여부만 비교하는 이번 foundation입니다.
Native capture와 진위 검증은 별도 계약 및 runtime 검증이 필요합니다.
ADR-025가 보류한 participant/gap policy도 구현으로 결정하지 않았습니다.

## 6. KNOWN_LIMITATIONS.md 변경 사항

- Caller의 RESOLVED/verified uniform-consequence 주장 자체를 native runtime에서 검증하지 않습니다.
- Placement retime 기본값은 UNKNOWN입니다. Changed placement는 explicit supported metadata가 필요합니다.
- Pure translation만 지원하며 source↔timeline mapping을 수행하지 않습니다.
- Native primary fragments를 합성하지 않습니다. Primary 비교는 explicit semantic range-removal입니다.
- Identity/base-post evidence reference가 있어야 MATCH가 가능하지만 reference 진위를 인증하지 않습니다.
- Scope 밖 미관측 공간은 인증하지 않습니다. 보고된 추가 변경은 MISMATCH로 남깁니다.
- Nonuniform/crossing/cross-track/unsupported retime 및 stale/mixed binding은 non-ready입니다.
- READY_FOR_PREFLIGHT는 consequence completeness이며 Safety PASS가 아닙니다.

## 7. Specification과 다르게 구현한 부분

계약 의미 변경 없음. API 명칭, explicit scope state, per-object actual observations 및 결과
우선순위는 구현 전 spec notes에 기록했습니다. Native postflight나 fragment correspondence를
추측하지 않았으며, 승인된 Safety rule을 추가·완화하지 않았습니다.

## 8. 다음 TASK 제안

TASK-014 Chat Gate 승인 및 merge 후 준비된 TASK-015 계약을 다음 검토 대상으로 제안합니다.
착수 전 최신 main의 authoritative spec과 별도 사용자 지시를 확인해야 합니다.
현재 TASK-015 착수는 **미승인**이며 구현하지 않았습니다. Acceptance criteria를 여기서
독자적으로 정하지 않으며 prepared spec을 후속 승인 범위의 기준으로 사용해야 합니다.

## 9. Chat 검토란

- 판정: Chat 작성 대기.
- 요청: TASK-014 **Chat Gate Review / APPROVED** 검토.
- 검토 초점: participant selection 분리, exact uniform consequence, unchanged scope,
  identity/coverage fail-closed, synthetic semantic 비교와 native proof의 경계.
- 필수 수정 및 재검증: Chat 판정 후 기록.
- 승인 기록 링크: 대기.
- Merge 및 TASK-015 자동 착수 없음.
