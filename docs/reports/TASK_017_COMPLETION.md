# TASK 완료 보고서

TASK: TASK-017 — Validated Execution IR Foundation

상태: 구현 및 로컬/Python 3.11 CI 검증 완료, Chat Gate 대기.
브랜치: `feat/task-017-validated-execution-ir`.
Base main: `6b5a3d8eb075a98deb901018314f28cf5d9d05a5`.
Spec notes: `f3c0ec8`, red tests: `309516d`, 구현: `e3ae5b7`.
최종 제출 head 및 최종 CI 근거는 PR 본문에 기록합니다.
PR: [#37](https://github.com/KIM0296/edit-program/pull/37).
근거: [TASK-017 spec](../../tasks/TASK_017_VALIDATED_EXECUTION_IR.md),
[ADR-028 상세 계약](../VALIDATED_EXECUTION_IR_CONTRACT.md).
요청 Gate: **APPROVED** (Codex 요청이며 Chat 판정 아님).

## 1. 구현 내용

ExpectedDiff, precomputed SafetyPreflightResult, ExecutionAuthorization과 제안된 logical IR/native
lowering을 소비하는 pure immutable validator를 구현했습니다. Native method 선택, participant 탐색,
range/delta repair, runtime fallback은 수행하지 않습니다.

- Logical vocabulary는 정확히 REMOVE_RANGE / TRANSLATE_PLACEMENT 두 종류입니다.
  기존 RangeRemovalEffect / TemporalDisplacement 값을 재사용하여 before state와 range/delta,
  source/media/track을 포함한 전체 semantic value와 multiplicity를 비교합니다.
- 모든 logical op 및 native step은 정확히 하나의 LoweringRealization에 속합니다.
  Fusion은 여러 op를 한 step에, decomposition은 명시적인 ordered step sequence에 연결합니다.
  Sequence-bound NativeEffectModel은 caller-supplied net effect를 표현하며 intermediate effect를
  추론하거나 fragment에 새 opcode를 부여하지 않습니다.
- IdentityScope, TargetResolutionStatus, native locator와 domain placement를 분리합니다.
  Session-local은 동일 session과 mutation/postflight proof가 필요하고 snapshot-local은 unsupported입니다.
- Native capability 4-state / effect-model 5-state를 유지합니다. Verified evidence와 runtime profile,
  exact artifact binding, PreservationScope, 모든 step의 post-read/reconciliation이 필요합니다.
- Fragment-producing path는 bound verified compound 또는 intermediate-rebinding evidence를 요구합니다.
- Status는 STALE > INVALID > UNSUPPORTED > INCOMPLETE > READY_FOR_EXECUTION이며 모든 finding을 보존합니다.
  Result constructor도 입력의 검증 결과와 다른 READY를 만들 수 없습니다.
- Rollback capability는 별도 axis입니다. READY는 applied/committed/promoted/Auto-Apply를 의미하지 않습니다.

Prepared spec의 48개 최소 요구사항별 테스트 매핑은 [TEST_MATRIX](../TEST_MATRIX.md)의 TASK-017 표에
기록했습니다. 117개 신규 테스트는 coverage 누락/추가/중복, 잘못된 range/delta, proof transplant,
identity/capability/effect matrix, decomposition, stale, immutability와 금지된 계층 호출을 검증합니다.

## 2. 변경된 파일

| 파일 | 변경 목적 |
| --- | --- |
| src/davinci_ai_editor/execution_ir.py | bounded IR, typed native evidence, pure validation |
| tests/test_execution_ir.py | red-first 및 117개 foundation 테스트 |
| tasks/TASK_017_VALIDATED_EXECUTION_IR.md | 구현 전 representation notes 및 작업 상태 |
| DECISIONS.md | OPEN-017/001/016 적용 범위와 native guarantee 보류 |
| IMPLEMENTATION_STATUS.md | 구현·검증 상태 |
| KNOWN_LIMITATIONS.md | supplied evidence와 runtime 검증의 차이 |
| docs/TEST_MATRIX.md | 48 requirements 대응표 |
| docs/reports/TASK_017_COMPLETION.md | 완료 보고서 |

### git diff --stat

비교 기준: 작업 중 추가된 문서까지 반영한 main `d83713a`. 시작 main은 `6b5a3d8`이며, 후속 read-capability 계약 문서만 merge하여 동기화했습니다. 후속 TASK 구현은 없습니다.

```text
 DECISIONS.md                             |  10 +
 IMPLEMENTATION_STATUS.md                 |  14 +
 KNOWN_LIMITATIONS.md                     |  12 +
 docs/TEST_MATRIX.md                      |  27 ++
 docs/reports/TASK_017_COMPLETION.md      | 138 ++++++
 src/davinci_ai_editor/execution_ir.py    | 702 ++++++++++++++++++++++++++++
 tasks/TASK_017_VALIDATED_EXECUTION_IR.md |  18 +-
 tests/test_execution_ir.py               | 755 +++++++++++++++++++++++++++++++
 8 files changed, 1675 insertions(+), 1 deletion(-)
```

## 3. 테스트 결과

| 검사 | 결과 |
| --- | --- |
| Red-first | 모듈 구현 전 ImportError: execution_ir 없음, collection error 1건 확인 |
| 신규 테스트 | 117 passed |
| 전체 pytest | 1149 passed, 0 failed, 1 skipped |
| Ruff | PASS |
| strict mypy | PASS, 19 source files |
| Python 3.11 CI | 1149 passed / 1 skipped; Ruff / strict mypy PASS |

로컬 환경: Windows, CPython 3.14.6. 테스트 명령은 `.venv/Scripts/python.exe -m pytest -q`,
`-m ruff check src tests`, `-m mypy`입니다. Skip은 `test_naive_inv001.py`의 opt-in intentional
red demo 1개이며 정상 INV-001 회귀는 실행됩니다. 기존 TASK-001~016 source/test 변경은 없습니다.

Python 3.11 GitHub CI: [run 37572985389](https://github.com/KIM0296/edit-program/actions/runs/37572985389), head `4f4eef230d40a07839bbb0f6a5c9cb7e66d93902` PASS. 최종 문서 commit의 CI는 PR 본문에 연결합니다.
실제 Resolve/Undo/probe/post-read/reconciliation은 실행하지 않았으며 이번 scope 밖입니다.

### Safety Gate

| Invariant | 결과 | 근거와 검증 범위 |
| --- | --- | --- |
| Wrong target edit | domain PASS / native 미검증 | exact target/before/binding, lifetime, ambiguity 차단 |
| Protected range violation | 기존 domain 회귀 PASS / native 미검증 | Safety PASS 소비, failure workaround 없음 |
| Silent timeline damage | domain PASS / native 미검증 | exact effect equality/multiplicity, scope expansion 차단 |
| A/V sync regression | 기존 domain 회귀 PASS / 실제 A/V 미검증 | relationship 실행 및 boundary normalization 없음 |
| Failed rollback | 기존 logical 회귀 PASS / 실제 rollback 미검증 | rollback capability는 별도 axis, rollback 실행 없음 |

## 4. 구현 과정에서 발견한 설계 문제

- API 존재, opaque primitive name, locator/proof reference만으로 실제 runtime correctness를 증명할 수 없습니다.
  모든 VERIFIED 상태는 caller-supplied typed evidence이며 생성·인증은 OPEN-017의 별도 문제입니다.
- Decomposition의 intermediate fragment semantics를 임의 구현하면 exactly-once 의미가 바뀔 수 있습니다.
  따라서 전체 ordered sequence에 bound된 net-effect model과 별도 fragment evidence만 구조적으로 검증합니다.
  반환 item 순서, native split 결과, intermediate source mapping은 추론하지 않습니다.
- Unordered effect 비교에서 set을 사용하면 duplicate realization을 숨길 수 있으므로 Counter로 multiplicity를
  보존합니다. 정렬은 deterministic representation이며 preference나 deduplication이 아닙니다.

## 5. DECISIONS.md에 추가한 OPEN 항목

새 Architecture 결정을 확정하지 않았습니다. 기존 OPEN-017 / OPEN-001 / OPEN-016을 유지하고
TASK-017 적용 note를 추가했습니다. 실제 evidence 생산·진위·fragment correspondence·runtime capability는
별도 승인된 계약에 따라 검증해야 합니다. 이번 PR은 후속 probe 구현을 포함하지 않습니다.

## 6. KNOWN_LIMITATIONS.md 변경 사항

- 구조적 READY와 실제 native guarantee를 구분했습니다.
- Native primitive/locator/proof는 opaque caller data이며 runtime authenticity는 미검증입니다.
- Decomposition evidence를 소비할 수 있지만 실제 fragment 생성·재식별은 수행하지 않습니다.
- 실제 target lookup, probe, mutation, post-read, reconciliation, retry, rollback 및 Authority는 없습니다.

## 7. Specification과 다르게 구현한 부분

Architecture 의미 변경 없음. 내부 명명과 sequence-level net-effect representation은 구현 전에 spec note에
기록했습니다. 실제 native evidence를 생성하거나 VERIFIED로 승격하지 않습니다. Approval 또는 transaction
execution을 대신하지 않습니다.

## 8. 다음 TASK 제안

TASK-018은 착수하지 않았습니다. Chat 승인 이후 당시 최신 main의 authoritative 계약을 먼저 확인해야 합니다.
Native evidence를 생산하는 후속 작업에서는 fixture 격리, profile binding, side-effect completeness,
post-read/reconciliation 및 fragment correspondence의 재현 가능한 증거가 선행되어야 합니다.
현재 다음 TASK 구현 승인 없음.

## 9. Chat 검토란

- 판정: Chat 작성 대기.
- 요청: TASK-017 Chat Gate Review.
- PR merge 및 TASK-018 구현은 수행하지 않습니다.
