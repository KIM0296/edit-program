# TASK 완료 보고서

TASK: TASK-019 — Probe Harness & Fixture Lifecycle Foundation
상태: 구현 및 로컬 검증 완료; Python 3.11 CI / Chat Gate 대기.
브랜치: `feat/task-019-probe-harness-lifecycle`.
시작 main: `9715a28ff786e8cb8c009008e4831f127b7eefc8`.
Spec notes: `76726d4`, red tests: `1f401a3`, 구현: `3727c2f`.
최종 제출 head와 CI 근거는 PR 본문에 기록합니다.
PR: 생성 예정.
근거: ADR-006/029/030/031/035, [TASK-019](../../tasks/TASK_019_PROBE_HARNESS_FIXTURE_LIFECYCLE.md),
[fixture lifecycle](../RESOLVE_PROBE_HARNESS_FIXTURE_LIFECYCLE.md),
[runtime control plane](../PROBE_RUNTIME_CONTROL_PLANE.md).
요청 Gate: **APPROVED** (Codex의 요청이며 Chat 판정 아님).

## 1. 구현 내용

등록, 환경 검증, fixture 검증, one-run arming을 별도 immutable 값으로 표현했습니다.
현재 state에서 반환된 다음 state를 사용하는 순수 함수와 fake submission shell입니다.

- EnvironmentVerification은 registration/generation/profile/catalog/current facts에 exact bind됩니다.
  Production/working project 또는 비격리 환경은 거부하며 이름/path/sentinel을 authority로 쓰지 않습니다.
- Fixture는 정의→materialization 기록→verification→clean→lease→mutation attempt→observation→seal→discard
  경로를 따릅니다. Dirty/quarantined/mutated fixture의 repair/reuse 경로는 없습니다.
- Lease는 fixture당 하나만 활성화할 수 있습니다. Case/domain/profile/pre-snapshot/scope/envelope와
  typed invocation을 authorization에 bind합니다. Fixture envelope 밖의 target을 허용하지 않습니다.
- Final gate는 모든 필수 조건을 확인하며 실패 finding을 모두 남깁니다. 실패 시에도 authorization은
  consumed이고 attempt는 0입니다. 성공 시 정확히 한 개의 fake boundary submission을 기록합니다.
- Native 응답은 별도 입력입니다. 성공 bool만으로 PASS하지 않으며 timeout/unknown/crash는 quarantine과
  BLOCKED를 발생시킵니다. 기존 submission을 취소했다고 주장하거나 blind retry를 허용하지 않습니다.
- Fixture-local containment failure는 REVERIFY_REQUIRED, project contamination은 CONTAMINATED,
  environment uncertainty는 BLOCKED입니다. 독립적인 새 project observation은 affected fixture discard 후에만
  재검증에 사용합니다. 실패/unknown 재검증은 CONTAMINATED이며 이 상태는 새 generation으로만 대체됩니다.
- Sealed evidence는 exact pre/post, authorization, lease, invocation, native metadata, observed diff,
  containment 및 진단을 보존합니다. 실패 run의 applicability를 나중에 좁혀 재분류할 수 없습니다.
- Suite는 evidence refs를 보존합니다. Exploratory는 qualifying count에 포함되지 않습니다.
  `eligible_for_qualification`은 lifecycle 입력 후보일 뿐 TASK-018 VERIFIED나 반복 budget 충족이 아닙니다.

50개 prepared 요구사항과 ADR-035 추가 규칙의 대응은 [TEST_MATRIX](../TEST_MATRIX.md)에 있습니다.
실제 Resolve/API/fixture 생성/lookup/rollback 및 TASK-020은 구현하지 않았습니다.

## 2. 변경된 파일

| 파일 | 변경 목적 |
| --- | --- |
| src/davinci_ai_editor/probe_harness.py | immutable control-plane / lifecycle / fake submission |
| tests/test_probe_harness.py | red-first 및 88개 신규 테스트 |
| tasks/TASK_019_PROBE_HARNESS_FIXTURE_LIFECYCLE.md | 구현 전 notes 및 상태 |
| DECISIONS.md | OPEN-020 적용 범위와 미해결 runtime 보장 |
| IMPLEMENTATION_STATUS.md | 구현·검증 상태 |
| KNOWN_LIMITATIONS.md | pure/native 경계와 영속적 권한 한계 |
| docs/TEST_MATRIX.md | 50개 요구사항 및 ADR-035 대응 |
| docs/reports/TASK_019_COMPLETION.md | 완료 보고서 |

### git diff --stat

비교 main: `e816179`. 작업 중 추가된 ADR-036/037 및 후속 task 문서만 동기화했습니다.
해당 문서의 구현을 시작하지 않았습니다.

```text
 DECISIONS.md                                      |   14 +
 IMPLEMENTATION_STATUS.md                          |   15 +
 KNOWN_LIMITATIONS.md                              |   21 +
 docs/TEST_MATRIX.md                               |   40 +
 docs/reports/TASK_019_COMPLETION.md               |  137 ++
 src/davinci_ai_editor/probe_harness.py            | 1458 +++++++++++++++++++++
 tasks/TASK_019_PROBE_HARNESS_FIXTURE_LIFECYCLE.md |   23 +-
 tests/test_probe_harness.py                       |  761 +++++++++++
 8 files changed, 2468 insertions(+), 1 deletion(-)
```

## 3. 테스트 결과

실행 환경: Windows, local Python 3.14.6. 실제 Resolve는 연결하지 않았습니다.

- red-first: 구현 전 missing-module ImportError 확인. 추가 binding/seal 검증도 실패를 먼저 재현했습니다.
- 신규: `pytest tests/test_probe_harness.py -q` → **88 passed**.
- 전체: `pytest -q` → **1347 passed, 0 failed, 1 skipped**.
- skip: `test_naive_inv001.py`의 opt-in intentional red demo 1개. 실제 INV-001 회귀는 실행·통과했습니다.
- `ruff check src tests` → PASS.
- strict `mypy` → PASS, 21 source files.
- Python 3.11 GitHub Actions CI: PR 생성 후 확인 예정.
- 실제 native integration/fixture materialization/lookup/fingerprint 검증은 범위 밖으로 미실행입니다.

### Safety Gate

| Invariant | 결과 | 근거와 검증 범위 |
| --- | --- | --- |
| Wrong target edit | domain/fake PASS, native 미검증 | exact binding / scope / target envelope mismatch 차단 |
| Protected range violation | 기존 domain 회귀 PASS, native 미검증 | TASK-001~018 회귀; 신규 실제 edit 없음 |
| Silent timeline damage | domain/fake PASS, native 미검증 | containment / uncertainty 차단과 모든 raw 진단 보존 |
| A/V sync regression | 기존 domain 회귀 PASS, native 미검증 | 관계/temporal semantics 변경 및 실제 이동 없음 |
| Failed rollback | 기존 domain 회귀 PASS, native 미검증 | rollback/Undo 호출 없음; quarantine을 recovery로 표시하지 않음 |

## 4. 구현 과정에서 발견한 설계 문제

Immutable state 복사만으로 native 세계에서 single-use를 보장할 수 없습니다. Future runtime에는
영속적 consumption과 원자적 lease, 재시작 후 reconciliation이 필요합니다. 이번 API는 반환된 successor를
연속 사용하며 이전 state replay를 실제 권한으로 해석하지 않는 foundation으로 제한했습니다.
또한 caller가 공급한 fingerprint/registration은 native 진위성을 증명하지 않습니다.
이 한계를 OPEN-020에 기록했고 새로운 native 보장은 만들지 않았습니다.

## 5. DECISIONS.md에 추가한 OPEN 항목

새 ID 없이 기존 **OPEN-020**을 유지하고 TASK-019 application note를 추가했습니다.
결정 대상은 native registration authenticity, generation discovery, durable consumption, cross-process lease입니다.
대안은 future trusted registry와 atomic persistence 및 native correspondence evidence이며,
현재는 typed facts만 검증합니다. 이름/path/sentinel 우회는 허용하지 않습니다.
후속 runtime 작업에서 별도 계약과 검증이 필요합니다.

## 6. KNOWN_LIMITATIONS.md 변경 사항

순수 상태 전이, fake invocation record, precomputed observation/containment의 한계와
native registry/capture/materialization/rebuild/Undo 미구현을 명시했습니다.
Asset hash는 opaque supplied evidence이며 실제 canonical binary/checksum 생성이나 검증이 아닙니다.
Suite eligibility는 capability qualification이 아니며 ordinary editor probe 작업은 0입니다.

## 7. Specification과 다르게 구현한 부분

의미상 차이 없음. `ProbeEnvironmentBinding`은 `RegisteredProbeEnvironment`의 호환 alias입니다.
LEASED_FOR_PROBE는 해당 lease의 exact CLEAN_VERIFIED proof를 보존할 때만 final gate를 통과합니다.
Pre-invocation abort는 새 검증과 새 run/authorization을 요구합니다. 제출된 fixture는 재사용하지 않습니다.
실제 runtime 보장과 영속성은 승인된 범위에 포함하지 않았습니다.

## 8. 다음 TASK 제안

TASK-020은 사용자 지시에 따라 **미착수**입니다. TASK-019 Chat Gate 이후 별도 승인된 spec으로
진행하며, native registration/capture/currentness를 실제로 증명할 때 OPEN-020 경계를 검토해야 합니다.
이번 보고서는 후속 구현 승인이나 executor enablement가 아닙니다.

## 9. Chat 검토란

- 판정: Chat 작성 대기.
- 요청: TASK-019 **Chat Gate Review**.
- 검토 초점: exact authorization 소비, fixture/generation 오염 전이, native 보장과 pure model의 구분.
- 필수 수정 및 재검증: Chat 판단 대기.
- PR merge: 수행하지 않음.
- TASK-020: 시작하지 않음.
