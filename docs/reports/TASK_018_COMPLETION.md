# TASK 완료 보고서

TASK: TASK-018 — Native Capability Probe Evidence Foundation

상태: 구현 및 로컬/Python 3.11 CI 검증 완료, Chat Gate 대기.
브랜치: `feat/task-018-native-probe-evidence`.
Base main: `0c84a081cbfd25a124215885c553ec27af1e81d3`.
Spec notes: `9f1f30b`, red tests: `9c7e2ec`, 구현: `6aa8290`.
최종 제출 head 및 최종 CI 근거는 PR 본문에 기록합니다.
PR: [#40](https://github.com/KIM0296/edit-program/pull/40).
근거: [TASK-018 spec](../../tasks/TASK_018_NATIVE_CAPABILITY_PROBE_EVIDENCE.md),
[ADR-029 상세 계약](../NATIVE_CAPABILITY_PROBE_EVIDENCE_CONTRACT.md),
[ADR-030 정책](../CAPABILITY_VERIFICATION_POLICY.md).
요청 Gate: **APPROVED** (Codex 요청이며 Chat 판정 아님).

## 1. 구현 내용

실제 Resolve 호출 없이 supplied probe evidence를 immutable하게 표현하고, ADR-030 조건으로
NativeEffectModel/NativeCapabilityStatus를 derive하는 foundation을 구현했습니다.

- EffectModelStatus, ReconciliationStatus, FragmentEvidenceStatus 및 PostReadStatus를 별도 typed axis로
  유지합니다. 다른 enum을 전달하면 거부합니다. TASK-017 schema를 변경하거나 자동 변환하지 않습니다.
- RuntimeProfile은 Resolve version/build, platform, adapter name/version, invocation/observation,
  evidence/model/policy/profile contract를 포함합니다. Session-local identity는 별도로 current session을 확인합니다.
- Production 또는 authoritative working fixture, unregistered/non-disposable/non-isolated fixture,
  dirty canonical pre-state와 fixture version mismatch는 qualifying run이 아닙니다.
- NativeInvocationSpec에는 explicit target과 integer delta 또는 removal range가 필요합니다.
  Native script/method 실행 및 participant selection 기능은 없습니다.
- Raw before/after subject observation에서 모든 change를 파생합니다. Placement, track, topology,
  marker/subtitle, transition/effect/keyframe, relationship의 관측 차이를 hypothesis로 filter하지 않습니다.
- Policy v1은 정확히 4/6/10 positive classes × 5 = 20/30/50과 applicable challenge별 추가 3 runs입니다.
  Positive와 challenge count는 분리되며 19/20 또는 다른 class의 초과 run으로 부족분을 채울 수 없습니다.
- Run/fixture instance/effect evidence/pre-post capture refs의 중복을 거부합니다.
  Full positive budget이 있어도 추가 실패·INCONCLUSIVE·partial/unknown observation을 숨기지 않습니다.
- 같은 declared domain의 conflicting effect는 CONFLICTING이며 majority/recency/support count로 승격하지 않습니다.
  Outside-domain challenge는 보존하고 UNSUPPORTED로 표시합니다. Case에 묶인 전체 domain을 비교하므로
  기존 evidence를 다른 좁은 domain으로 재분류할 수 없습니다.
- Post-read 독립 관측, distinguishable reconciliation signatures, execution-grade correspondence,
  필요한 fragment evidence를 각각 평가합니다. API success bool과 UUID 형태는 증거를 대체하지 않습니다.
- Derived model은 모든 raw input과 run qualification/coverage/finding을 보존합니다. VERIFIED가 아니면
  `verified_effects`는 없습니다. Constructor도 근거와 다른 derived status를 거부합니다.
- Ordinary production editor manual probe work는 0이며 per-project/per-edit full suite 의미가 없습니다.

Prepared spec 55개 요구사항과 110개 신규 테스트의 대응표는 [TEST_MATRIX](../TEST_MATRIX.md)의
TASK-018 표에 있습니다. 테스트는 synthetic evidence의 구조적 qualification을 검증합니다.

## 2. 변경된 파일

| 파일 | 변경 목적 |
| --- | --- |
| src/davinci_ai_editor/probe_evidence.py | immutable records, independent evidence axes, exact policy/derivation |
| tests/test_probe_evidence.py | red-first 및 110개 qualification 테스트 |
| tasks/TASK_018_NATIVE_CAPABILITY_PROBE_EVIDENCE.md | 구현 전 notes 및 작업 상태 |
| DECISIONS.md | OPEN-017 native correspondence/authenticity 한계 기록 |
| IMPLEMENTATION_STATUS.md | 구현·검증 결과 |
| KNOWN_LIMITATIONS.md | pure evidence와 native 보장의 경계 |
| docs/TEST_MATRIX.md | 55 requirements 대응표 |
| docs/reports/TASK_018_COMPLETION.md | 표준 완료 보고서 |

### git diff --stat

비교 기준: 작업 중 추가된 문서까지 동기화한 main `3c0015b`. 시작 main은 `0c84a08`이며, 후속 fixture catalog/runtime 계약 문서만 merge했습니다. 후속 TASK 구현은 없습니다.

```text
 DECISIONS.md                                       |   17 +
 IMPLEMENTATION_STATUS.md                           |   15 +
 KNOWN_LIMITATIONS.md                               |   15 +
 docs/TEST_MATRIX.md                                |   28 +
 docs/reports/TASK_018_COMPLETION.md                |  148 +++
 src/davinci_ai_editor/probe_evidence.py            | 1139 ++++++++++++++++++++
 tasks/TASK_018_NATIVE_CAPABILITY_PROBE_EVIDENCE.md |   20 +-
 tests/test_probe_evidence.py                       |  808 ++++++++++++++
 8 files changed, 2189 insertions(+), 1 deletion(-)
```

## 3. 테스트 결과

| 검사 | 결과 |
| --- | --- |
| Red-first | 구현 전 ImportError: probe_evidence 없음, collection error 1건 |
| 추가 red 확인 | missing invocation parameters 3건, authoritative/verified-effect contract 2건 실패 후 구현 |
| 신규 테스트 | 110 passed |
| 전체 pytest | 1259 passed, 0 failed, 1 skipped |
| Ruff | PASS |
| strict mypy | PASS, 20 source files |
| Python 3.11 CI | 1259 passed / 1 skipped; Ruff / strict mypy PASS |

로컬 환경: Windows / CPython 3.14.6. 명령: `.venv/Scripts/python.exe -m pytest -q`,
`-m ruff check src tests`, `-m mypy`.
Skip은 `test_naive_inv001.py`의 opt-in intentional red demo 1개입니다. 정상 INV-001 회귀는 실행됩니다.
기존 TASK-001~017 source/test는 수정하지 않았습니다.

Python 3.11 GitHub CI: [run 37575858937](https://github.com/KIM0296/edit-program/actions/runs/37575858937), head `f3e9cafdf9c84c8df88577b62304514c32456859` PASS. 최종 문서 commit의 CI는 PR 본문에 연결합니다.
Resolve native fixture/probe/observation/Undo는 실행하지 않았습니다.

### Safety Gate

| Invariant | 결과 | 근거와 검증 범위 |
| --- | --- | --- |
| Wrong target edit | domain 회귀 PASS / native 미검증 | ambiguous identity 차단, UUID/heuristic 승격 없음 |
| Protected range violation | 기존 domain 회귀 PASS / native 미검증 | 실제 mutation/production enablement 없음 |
| Silent timeline damage | domain PASS / native 미검증 | observed collateral change 보존, containment/completeness 평가 |
| A/V sync regression | 기존 domain 회귀 PASS / native 미검증 | challenge metadata만 표현하며 실제 A/V probe 없음 |
| Failed rollback | 기존 logical 회귀 PASS / 실제 rollback 미검증 | Undo를 clean fixture의 증거로 추론하지 않음; rollback 호출 없음 |

## 4. 구현 과정에서 발견한 설계 문제

- Concrete fixture의 placement ID/range가 다를 때 동등한 native semantics로 정규화하는 계약이 없습니다.
  이번 구현은 explicit concrete values를 정확히 비교하며 role/filename/order/position 기반 normalization을
  만들지 않습니다. 실제 heterogeneous fixtures는 추가 correspondence 계약 없이 보수적으로 non-VERIFIED일 수 있습니다.
- Registry/clean instance/probe refs는 immutable caller facts입니다. 중복은 거부하지만 physical reconstruction이나
  historical evidence의 완전성·진위를 pure domain이 증명하지는 않습니다.
- 기존 ADR-029 문서의 OPEN-018 참조보다 최신 ADR-030의 승인된 고정 policy가 우선합니다.
  20/30/50과 challenge 3, zero-tolerance 조건은 완화하지 않았습니다.

## 5. DECISIONS.md에 추가한 OPEN 항목

새 Architecture 결정을 확정하지 않았습니다. 기존 OPEN-017에 TASK-018 적용 note를 추가했습니다.
Native cross-fixture correspondence, provenance authenticity 및 immutable corpus의 외부 persistence는
후속 승인된 producer/harness 계약이 필요합니다. OPEN-018은 ADR-030으로 해결된 상태를 유지합니다.
OPEN-001 production persistent identity 및 실제 runtime 보장은 해결했다고 주장하지 않습니다.

## 6. KNOWN_LIMITATIONS.md 변경 사항

- Supplied evidence의 qualification과 실제 native evidence acquisition을 구분했습니다.
- Fixture class/condition의 실물 충족 여부와 proof authenticity는 caller 책임이며 이번 domain이 검사할 수 없습니다.
- Exact comparison에는 native identity normalization이 없습니다.
- In-memory append-style corpus는 history persistence나 tamper-proof ledger가 아닙니다.
- TASK-017 production lowering으로 연결하는 bridge, capability enablement, release gate enforcement는 없습니다.
- Probe/harness/capture/fixture creation/mutation/rollback/retry는 없습니다.

## 7. Specification과 다르게 구현한 부분

승인된 Architecture 의미와 numeric policy 변경 없음. Caller-bound representation과 보수적인 exact-value
비교 제한은 구현 전에 spec 및 OPEN-017 note에 기록했습니다. Reconciliation/fragment axis 분리는 사용자
보완 지시를 반영했으며, 기존 TASK-017 artifact를 암묵적으로 변환하지 않습니다.

## 8. 다음 TASK 제안

TASK-019는 시작하지 않았습니다. 승인 후 당시 최신 main의 authoritative harness/fixture 계약을 확인해야 합니다.
실제 probe 작업은 disposable registry, canonical reconstruction, complete independent observation과
runtime-bound correspondence 증거를 선행 검증해야 합니다. 현재 다음 TASK 구현 승인 없음.

## 9. Chat 검토란

- 판정: Chat 작성 대기.
- 요청: TASK-018 Chat Gate Review.
- PR merge 및 TASK-019 구현은 수행하지 않습니다.
