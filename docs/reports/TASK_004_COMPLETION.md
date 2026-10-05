# TASK 완료 보고서

TASK: TASK-004
제목: Timeline Topology & Preserve Editability Foundation
상태: 구현 완료, Chat Gate 검토 대기
브랜치: `feat/task-004-timeline-topology`
Commit: 구현 `72a868477fb23f4b0c4f5d8fe3dc090192178ad2`; 본 보고서 및 결과 기록은 후속 문서 커밋
PR: https://github.com/KIM0296/edit-program/pull/3
승인된 Specification / ADR: tasks/TASK_004_TIMELINE_TOPOLOGY.md, docs/TIMELINE_SAFETY.md INV-019, 사용자 TASK-004 지시
요청 Gate: **APPROVED** (Codex 요청이며 Chat 판정이 아님)

## 1. 구현 내용

- TASK-003 APPROVED/PR #2 병합 후 main `642f9f4`에서 작업 브랜치를 만들었습니다.
- 구현 전에 spec, INV-019, Preserve Editability / Native Editing Environment Preservation 및 Effects/VFX note를 `dc32051`로 커밋했습니다.
- 새 `topology.py`는 표현·projection·diff·검증만 제공합니다. 기존 편집 executor를 변경하지 않았습니다.
- TrackId/TrackType/TimelineObjectId/RelationshipGraph를 재사용합니다. TrackTopology의 identity와 index, ObjectMembership의 comparison identity와 current track을 분리합니다.
- Track 추가/삭제/type/order 변경과 object 추가/삭제/track 이동을 TopologyDiff로 보고합니다.
- ExpectedTopologyChange는 base timeline/version에 고정되며 실제 diff와 정확히 같아야 합니다. 추가 변경뿐 아니라 누락된 기대 변경도 거부합니다.
- PREVIEW/RENDER/FLATTENED 출처는 승인 diff가 있어도 editable source state로 사용할 수 없습니다.
- native로 표시돼도 여러 occupied layer 전체가 하나의 새 object로 교체되면 flatten 가능성으로 REVIEW합니다. 기존 native object를 유지하는 명시적 layer 삭제는 단순 track 수 감소만으로 flatten으로 간주하지 않습니다.
- 관계 records는 보존하며 관계 변경은 REVIEW합니다. 명시적 fake identity binding의 reference projection만 수행하고 관계 정책은 실행하지 않습니다.

| Acceptance criteria | 결과와 근거 |
| --- | --- |
| 1~4: 다중 track, identity/order/membership, 반복 media | VIDEO/AUDIO/SUBTITLE 혼합 layer 및 같은 media/source/clip 이름의 track별 placement 구분 |
| 5~8: 추가/삭제/이동/순서 변경 감지 | 각각 독립 테스트, identity 교체와 reorder 구분, insertion에 따른 index 이동도 보고 |
| 9: flattened layer 교체 감지 | artifact 출처와 native-tagged 전체 multi-layer→단일 새 object 치환 모두 거부 |
| 10: 승인/예상 밖 변화 구분 | exact expected diff, extra/missing/mismatched context 거부 |
| 11: RelationshipGraph 호환 | 기존 참조/정책 보존, mapping 일대일 검사, dangling registry 거부 |
| 12: TASK-001/002/003 회귀 | 기존 테스트 파일 5개 변경 없이 전체 PASS |
| 13: Python 3.11/Ruff/mypy | CI에서 모두 PASS |

Effect/VFX는 note만 기록했습니다. Edit Page/Resolve FX 우선, Fusion preferred-not-required, 자유 자동화 제외, editable/reversible/inspectable, specialist VFX Assist/Handoff 우선, native 보존 조건의 후순위 외부 연동 원칙을 반영했습니다.

## 2. 변경된 파일

| 파일 | 변경 목적 |
| --- | --- |
| `AGENTS.md` | 사용자 승인 Preserve Editability / native 보존 원칙 |
| `docs/PRODUCT_SPEC.md` | 제품 원칙과 future effects 경계 |
| `docs/ARCHITECTURE.md` | editable/output 구분 및 effects preferred path note |
| `docs/TIMELINE_SAFETY.md` | 사용자 승인 INV-019 기록 |
| `DECISIONS.md` | OPEN-006/007, TASK-003 승인 및 TASK-004 범위 |
| `tasks/TASK_004_TIMELINE_TOPOLOGY.md` | 구현 전 spec 및 acceptance checklist |
| `src/davinci_ai_editor/topology.py` | immutable topology projection/diff/validation |
| `tests/test_topology.py` | 신규 topology 테스트 31개 |
| `IMPLEMENTATION_STATUS.md` | 구현 결과, PR, CI 및 한계 |
| `KNOWN_LIMITATIONS.md` | fake provenance/correspondence/index 검증 한계 |
| `docs/TEST_MATRIX.md` | INV-019 scoped coverage 및 회귀 결과 |
| `docs/reports/TASK_004_COMPLETION.md` | 표준 완료 보고서 |

### git diff --stat

비교 기준: `main`의 `642f9f42c39df350b08710e6b20aea48a942abae` → 본 보고서를 포함한 PR 제출 트리.
아래는 제출 직전 실제 index 비교 결과입니다. 검증된 구현 commit은 `72a8684`; 후속 변경은 문서뿐입니다.

```text
 AGENTS.md                           |   3 +
 DECISIONS.md                        |  36 ++++
 IMPLEMENTATION_STATUS.md            |  31 ++-
 KNOWN_LIMITATIONS.md                |  23 ++-
 docs/ARCHITECTURE.md                |  19 ++
 docs/PRODUCT_SPEC.md                |  19 ++
 docs/TEST_MATRIX.md                 |  10 +
 docs/TIMELINE_SAFETY.md             |  11 ++
 docs/reports/TASK_004_COMPLETION.md | 166 ++++++++++++++++
 src/davinci_ai_editor/topology.py   | 256 ++++++++++++++++++++++++
 tasks/TASK_004_TIMELINE_TOPOLOGY.md |  89 +++++++++
 tests/test_topology.py              | 383 ++++++++++++++++++++++++++++++++++++
 12 files changed, 1044 insertions(+), 2 deletions(-)
```

## 3. 테스트 결과

- 로컬 Windows / Python 3.14.6: **114 passed / 0 failed / 1 skipped**.
- CI Ubuntu / Python 3.11.16: **114 passed / 0 failed / 1 skipped**.
- Ruff 통과; mypy source 5개 통과.
- CI 증거: https://github.com/KIM0296/edit-program/actions/runs/37279654222
- red-first: 테스트를 먼저 작성하고 topology 모듈 부재로 collection failure 확인 후 구현했습니다. 새 destructive executor는 없습니다.
- 중간 검증에서 graph registry의 열거 순서까지 같다고 가정한 테스트를 수정했습니다. 이동 후 순서가 달라도 registry identity 집합과 관계 records는 동일해야 하며 이를 별도로 검증합니다. Track order 비교는 엄격하게 유지합니다.
- skipped: 기존 opt-in naive 실패 시연 1건. 일반 naive 회귀 검사는 실행합니다.
- 미실행: 실제 Resolve topology/편집 가능성, effect/VFX, A/V correction, multi-track 실행, rollback. 범위 밖이며 별도 승인과 runtime 증거가 필요합니다.

### pytest 결과

```text
python -m pytest -q
114 passed, 1 skipped
python -m ruff check src tests
All checks passed!
python -m mypy
Success: no issues found in 5 source files
```

### Safety Gate

| Invariant | 결과 | 검증 범위 |
| --- | --- | --- |
| Wrong target edit | PASS (기존 fake 범위) | INV-001 회귀, topology에서 media 기반 identity 추측 없음 |
| Protected range violation | PASS (기존 fake 범위) | INV-003 회귀 유지 |
| Silent timeline damage | PASS (scoped domain) | INV-002 회귀, expected topology와 actual diff 일치 |
| A/V sync regression | 미검증 | 관계 표현 회귀만 유지; 실제 sync correction 없음 |
| Failed rollback | 미검증 | transaction/rollback 미구현 |
| INV-019 topology preservation | PASS (fake topology/provenance 범위) | track/type/order/membership diff, output-source 거부, whole-layer replacement REVIEW |

전체 P0 또는 실제 native editability 보증을 주장하지 않습니다.

## 4. 구현 과정에서 발견한 설계 문제

- 기존 TimelineObjectId에 track_id가 포함되어 이동 후 같은 object인지 자동 판단할 수 없습니다. Comparison identity와 membership을 분리하고, snapshot 간 이동 대응은 명시적 일대일 binding만 받습니다. Binding이 없으면 removed/added로 나타나며 조용히 같은 것으로 간주하지 않습니다.
- native track 인덱스가 type별인지 전역인지 실제 API 근거가 없습니다. 이번 order는 기존 snapshot tuple index라는 fake 의미로 제한했습니다.
- topology만으로 native 편집 가능성이나 모든 flatten을 판정할 수 없습니다. 선언된 origin과 특정 전체 교체 구조를 검증하며, 실제 출처 입증은 미구현입니다.
- 기존 RelationshipGraph를 변경하지 않고, projection에서 명시된 identity reference만 변환합니다. 관계 record 변경은 별도 lifecycle 결정이 필요해 REVIEW합니다.

## 5. DECISIONS.md에 추가한 OPEN 항목

**OPEN-006 — Topology correspondence and native track indices**

- 문제/근거: track-qualified fake ID와 이동 후 identity, native indexing 의미.
- 대안: production persistent ID, 검증된 adapter correspondence, fake explicit origin binding.
- trade-off: 자동 matching 편의성보다 반복 placement 오인 방지가 우선입니다.
- 권고: TASK-004는 explicit mapping과 fake tuple index로 제한합니다.
- 필요한 결정/보류: production object identity·mapping·track index와 실제 이동 adapter. OPEN-001 유지.

**OPEN-007 — Native editability / flatten provenance evidence**

- 문제/근거: 같은 topology 또는 native label만으로 실제 render/flatten 여부를 입증할 수 없습니다.
- 대안: adapter가 검증한 provenance, 유지된 source object graph, 불확실한 치환 REVIEW.
- 권고: fake에서는 artifact origin을 거부하고 전체 multi-layer 치환을 보수적으로 REVIEW합니다.
- 필요한 결정/보류: production provenance 근거와 허용 가능한 editable replacement 의미, 실제 Resolve/render adapter.
- foundation 작업은 완료했으며 관계 실행 OPEN-005와 persistent identity OPEN-001은 그대로 유지합니다.

## 6. KNOWN_LIMITATIONS.md 변경 사항

- 데이터 표현·검증 foundation으로 실제 Track/object 이동을 실행하지 않습니다.
- Origin/mapping은 caller가 제공하는 fake 입력입니다. 잘못된 native 주장, 숨겨진 media render 치환 등은 topology만으로 모두 검출할 수 없습니다.
- Expected diff 통과는 사용자 승인 절차, version commit 또는 실제 native 상태 보증이 아닙니다.
- Track insertion/removal이 다른 index에 주는 영향까지 expected diff에 명시해야 합니다.
- Object topology는 source/media/time/effect를 검사하지 않으므로 다른 invariants를 대체하지 않습니다.
- Preview/render artifact 표현은 가능하지만 renderer는 없습니다. Effects/VFX note의 기능도 구현하지 않았습니다.
- 해소 조건: OPEN-006/007 승인, 실제 native adapter 증거와 별도 범위 테스트.

## 7. Specification과 다르게 구현한 부분

- 작성된 TASK-004 spec과 확인된 차이: 없음.
- 새 TrackIdentity는 만들지 않고 기존 TrackId를 재사용했습니다. Track order는 별도 필드로 표현합니다.
- Track movement 대응을 추측하거나 기존 Relationship identity 의미를 바꾸지 않았습니다. Explicit origin binding은 fake 비교용 구현이며 production 정책으로 확정하지 않았습니다.
- NoFlatten은 선언된 origin 및 recognizable whole-layer replacement에 대한 scoped 검사입니다. 모든 실제 flatten을 탐지한다고 해석하면 미충족이므로 OPEN-007과 범위 제한을 명시했습니다.
- 기존 source 파일과 TASK-001/002/003 테스트는 변경하지 않았습니다. 새 topology 모듈은 executor 경로에 자동 연결하지 않습니다.

## 8. 다음 TASK 제안

- 다음 TASK는 자동 착수하지 않습니다.
- 제안: OPEN-006/007 중 필요한 identity/provenance 근거와 안전한 topology 변경 경계를 Chat에서 먼저 결정합니다.
- Acceptance 초안: 승인된 correspondence/provenance 사례와 모호한 입력 거부, 기존 invariant 회귀·CI PASS, 실제 실행 여부 명시.
- multi-track/effect/Resolve 기능을 자동 제안 범위에 포함하지 않습니다.
- 현재 승인 여부: **미승인**.

## 9. Chat 검토란

- 판정: Chat 작성 대기
- 판정 근거: TASK-004 spec, PR #3 diff, INV-019 범위, topology 및 기존 회귀 테스트, CI
- 필수 수정 및 재검증: Chat 지정 대기
- 다음 TASK / 병행 허용 범위: 없음, 추가 승인 대기
- 승인 기록 링크: TASK-004 최종 Gate 승인 없음
