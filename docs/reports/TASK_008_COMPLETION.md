# TASK 완료 보고서

TASK: TASK-008 — Evaluation Schema & Pure Metric Foundation

상태: 구현 및 로컬/Python 3.11 CI 검증 완료, Chat Gate 대기.

브랜치: `feat/task-008-evaluation-schema`

Spec commit: `af180f8` (구현 전). 구현 commit: `ab189e5`.

Base main: `3c1ca49ffc7c4be7f74620afb090de51d9a51f2e`.
후속 보고 commit은 문서만 변경하며 최종 head는 PR 본문에 기록합니다.

PR: https://github.com/KIM0296/edit-program/pull/13

근거: [TASK-008 spec](../../tasks/TASK_008_EVALUATION_SCHEMA.md),
[ADR-019 / Evaluation Contract](../EVALUATION_DATA_CONTRACT.md).
요청 Gate: **APPROVED** (Codex 요청이며 Chat 판정 아님).

## 1. 구현 내용

평가의 raw evidence를 immutable value로 표현하고, 매번 같은 evidence에서 재계산 가능한
pure outcome/metric derivation을 구현했습니다. DB나 telemetry는 없습니다.

- BENCHMARK/PILOT/PRODUCT_FEEDBACK case와 model-agnostic producer 버전을 분리했습니다.
- Proposal, annotation, reference judgment는 immutable입니다. 제품 feedback을 bound
  benchmark reference/annotation으로 넣을 수 없고 derivation은 reference를 수정하지 않습니다.
- TIGHTEN reference는 단일 정답 대신 `0 < min <= preferred <= max < original`을 검증합니다.
- Feedback은 typed payload와 sequence 기반 immutable append log입니다. 순열을 정렬하며
  중복 ID/sequence, 누락 순서, 잘못된 case/proposal, finalization 이후 append를 거절합니다.
- Final outcome과 correction은 event에서만 파생합니다. Candidate review REMOVE→KEEP과
  실제 REMOVED_PAUSE_RESTORED를 구별하고, revert 후 알 수 없는 결과를 KEEP으로 추측하지 않습니다.
- Activity/WorkflowRun은 원시 timing·측정 source·coverage evidence입니다. 명시적 0과
  누락/None/불완전 coverage를 구분하고 필요한 evidence가 없으면 계산 불가를 반환합니다.
- Human Active / Mandatory Attention / Assisted Human Cost / Correction Debt / Net Time Saved,
  Critical False Removal / TIGHTEN range / Review Load / Decision Interruptions / Accepted As-Is를 계산합니다.
- Metric version과 source case/proposal/reference/event 또는 run/activity identity가 결과에 연결됩니다.
  Rate는 정확한 Fraction이며 numerical gate, tolerance 또는 임의 가중치를 넣지 않았습니다.

| Acceptance | 결과와 근거 |
| --- | --- |
| Immutable raw records / proposal / append-only events | PASS: nested freeze, defensive tuples, old value 보존 |
| Benchmark/product source separation | PASS: PRODUCT_FEEDBACK reference/annotation 거절, raw reference 불변 |
| Pure final outcome / correction | PASS: finalization, unknown revert, restore signal, TIGHTEN more/less |
| Pure timing and paired savings | PASS: missing != zero, scope/mode/case pairing, zero denominator/negative savings |
| Safety/editorial metrics | PASS: exact false-removal definition, inclusive range, review fraction, actual attention count |
| Explicit versioning / privacy | PASS: schema/producer/reference/metric version, opaque refs; media/username/consent 필수 아님 |
| No executor/telemetry | PASS: classifier/executor/authority monkeypatch guard, 신규 모듈은 pure data/functions |
| TASK-001~007 regression | PASS: 기존 코드/테스트 변경 없음 |
| Python 3.11 CI | PASS: CPython 3.11.16, run 37408687466 |
| Ruff / strict mypy | PASS: 10 source files |

## 2. 변경된 파일

| 파일 | 목적 |
| --- | --- |
| tasks/TASK_008_EVALUATION_SCHEMA.md | 구현 전 schema, event 의미, completeness, denominator 계약 |
| DECISIONS.md | OPEN-010 및 승인 이력 |
| src/davinci_ai_editor/evaluation.py | immutable raw records, typed log, binding/shape validation |
| src/davinci_ai_editor/evaluation_metrics.py | pure final outcome/correction/timing/editorial derivation |
| tests/test_evaluation.py | 신규 65개 acceptance·실패·순수성 테스트 |
| docs/EVALUATION_DATA_CONTRACT.md | 구현된 v1 subset과 OPEN 경계 |
| IMPLEMENTATION_STATUS.md | TASK-007 승인 및 TASK-008 구현/검증 상태 |
| KNOWN_LIMITATIONS.md | episode/timing/provenance/수집·저장 경계 |
| docs/TEST_MATRIX.md | 사례별 검증 근거 |
| docs/reports/TASK_008_COMPLETION.md | 표준 완료 보고서 |

### git diff --stat

비교: base main `3c1ca49` 대비 이 보고서를 포함한 제출 tree.

```text
 DECISIONS.md                                |  23 +
 IMPLEMENTATION_STATUS.md                    |  31 +-
 KNOWN_LIMITATIONS.md                        |  27 ++
 docs/EVALUATION_DATA_CONTRACT.md            |  18 +
 docs/TEST_MATRIX.md                         |  22 +
 docs/reports/TASK_008_COMPLETION.md         | 181 ++++++++
 src/davinci_ai_editor/evaluation.py         | 436 +++++++++++++++++++
 src/davinci_ai_editor/evaluation_metrics.py | 362 ++++++++++++++++
 tasks/TASK_008_EVALUATION_SCHEMA.md         | 131 ++++++
 tests/test_evaluation.py                    | 626 ++++++++++++++++++++++++++++
 10 files changed, 1856 insertions(+), 1 deletion(-)
```

## 3. 테스트 결과

- 로컬: Windows / Python 3.14.6. Resolve 미사용.
- Passed: 전체 342개, 신규 65개. Ruff PASS, strict mypy PASS (10 source files).
- Failed: 최종 0개. 구현 전 evaluation 모듈 부재 collection error 확인 후 구현했습니다.
  중간 실패는 정렬된 activity tuple을 위치로 고른 fixture 2건, Python 3.14 dataclass replace의
  예외 유형 차이 1건이었습니다. Kind로 선택하고 Python 3.11/3.14의 거절 예외를 허용하도록 수정했습니다.
  초기 import/lint 및 typed metric result 생성의 mypy 문제도 해결 후 전체 PASS입니다.
- Skipped: 기존 opt-in intentional naive red demonstration 1개. 일반 naive regression 실행됨.
- 미실행: 실제 Benchmark/Pilot, telemetry/timing 정확도, Resolve/Apply/postflight/rollback.
  모두 이번 TASK 범위 밖이며 별도 승인된 data/collection/실험 계약이 필요합니다.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
# 342 passed, 1 skipped
.\.venv\Scripts\python.exe -m ruff check src tests
# All checks passed!
.\.venv\Scripts\python.exe -m mypy
# Success: no issues found in 10 source files
```

Red-first: spec commit 뒤 `pytest tests/test_evaluation.py -q` 실행이
`ModuleNotFoundError: No module named 'davinci_ai_editor.evaluation'`로 실패했습니다.
사용자 20개 사례와 추가 binding/version/unknown/denominator/defensive-copy/recovery 사례를 검증했습니다.

Hosted CI: [run 37408687466](https://github.com/KIM0296/edit-program/actions/runs/37408687466), head `5784534` 기준. Ubuntu/CPython 3.11.16에서 342 passed / 1 skipped, Ruff PASS, mypy 10 files PASS를 로그로 확인했습니다. 후속 변경은 문서만이며 최종 head CI도 검토 제출 전에 확인합니다.

### Safety Gate

| Invariant | 결과 | 근거와 검증 범위 |
| --- | --- | --- |
| Wrong target edit | PASS (기존 fake 범위) | INV-001 회귀; 평가 함수는 editing target을 생성하지 않음 |
| Protected range violation | PASS (기존 fake 범위) | TASK-002 회귀 유지; 평가 함수는 executor/preflight 호출 없음 |
| Silent timeline damage | PASS (기존 fake 범위) | INV-002/019 회귀 및 raw evidence 불변 |
| A/V sync regression | 미검증 (execution) | 기존 relationship 회귀만 유지 |
| Failed rollback | 미검증 | transaction/rollback 범위 밖 |

Critical False Removal을 계산할 수 있다는 것이 실제 false-removal 성능이나 P0 gate 통과를 뜻하지 않습니다.

## 4. 구현 과정에서 발견한 설계 문제

Event 종류만으로 revert 후 정확한 결과를 알 수 없으며, 일부 timing record만으로 전체
측정이 완료됐다고 볼 수도 없습니다. 따라서 unknown outcome과 명시적 complete_activity_kinds
coverage evidence를 도입했습니다. 기록이 없는 kind를 0으로 대체하지 않습니다.
Final outcome에는 finalization과 명시적인 결정이 필요합니다. 단 revert/restore는 그 자체로
accepted_as_is=False를 증명하므로 final_action이 unknown이어도 false로 반환합니다.

Critical False Removal Rate 분모는 reference KEEP/REVIEW 사례 수로 spec에 고정했습니다.
Reference 보유/누락 및 eligible count도 함께 반환합니다. Reference가 AMBIGUOUS여도 raw
판단을 재작성하거나 임의로 제외하지 않습니다. NEAR_RANGE/숫자 threshold는 미정입니다.

## 5. DECISIONS.md OPEN 항목

**OPEN-010:** finalized episode 재개/late event, reaccept after recovery, partial restore,
cross-proposal/run ordering, collector의 attention batch 중복 제거, activity overlap/coverage
provenance, estimate calibration, paired-run governance. NEAR_RANGE tolerance/GatePolicy도 미정입니다.

대안은 수집 사실과 누락된 결과를 추론하거나, 명시적인 단일 episode/coverage만 받아 지원
범위 밖을 거절·계산 불가로 남기는 것입니다. 후자를 권고하고 pure subset으로 구현했습니다.
생산 환경의 collector/storage/reopen/partial restore/overlap 보정과 실제 Pilot 설계가 이 결정들에
의존합니다. 이번 foundation을 막지 않으며 나머지 기존 OPEN은 유지합니다.

## 6. KNOWN_LIMITATIONS.md 변경 사항

Raw evidence의 진실성, ID의 전역 존재/재사용, 실제 append-only 저장은 이 in-memory 계약이
증명하지 않습니다. 과거 event를 수정하는 API는 없지만 외부 caller가 새 값을 조립하는 것까지
보안적으로 막는 저장소는 없습니다. RUN_FINALIZED의 run reference도 caller가 제공합니다.

Timing은 완전하고 겹치지 않는 duration이라는 caller claim이 필요하며 overlap을 검출하지 않습니다.
동일 scope와 case set의 명시적 paired runs만 비교합니다. Missing log는 interruption 계산 불가,
명시적인 empty log는 공급된 episode에서 관측된 event 0개라는 의미입니다.
Accepted-as-is rate 분모는 finalized known outcomes뿐이며 unknown 수를 별도로 제공합니다.
모든 derived 결과는 raw data보다 authoritative하지 않고 gate/훈련 동의가 아닙니다.

## 7. Specification과 다르게 구현한 부분

기능 범위 차이 없음. 구현 중 spec 설명을 정밀화했습니다: revert/restore는 final_action이
unknown이어도 accepted_as_is=False이며, incomplete timing coverage도 유효한 raw evidence로
받되 metric을 계산하지 않습니다. 이는 missing fail-closed와 사용자 명시 요구를 따릅니다.
ReferenceAssessment로 annotation/judgment 공통 필드를 묶었으며 필수 의미는 유지했습니다.
실제 telemetry/DB/network/UI/training/dataset/Pilot/numeric Gate는 추가하지 않았습니다.

## 8. 다음 TASK 제안

TASK-009 범위 확정 전에 OPEN-010의 episode finalization/recovery/coverage provenance와
Pilot pairing protocol을 Chat에서 검토할 것을 제안합니다. Acceptance 초안: late/replayed evidence
처리, 실제 zero/partial coverage 구분, source separation, 같은 raw inputs의 versioned 재계산.
현재 미승인이며 실제 데이터 수집이나 다음 TASK는 시작하지 않았습니다.

## 9. Chat 검토란

- 판정: Chat 작성 대기.
- 판정 근거: spec / 보고서 / PR / CI.
- 필수 수정 및 재검증: Chat 작성.
- 다음 TASK / 병행 허용 범위: 미승인.
- 승인 기록 링크: 없음 (APPROVED는 요청).
