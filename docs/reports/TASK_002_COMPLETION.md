# TASK 완료 보고서

TASK: TASK-002
제목: INV-002 Unrequested Region / INV-003 HARD_LOCK Protected Range
상태: 구현 완료, Chat Gate 검토 대기
브랜치: `feat/task-002-inv002-inv003`
Commit: 구현 `84e15f71b9e6e6efe34205a5f8c90e099be02fc2`; 이 보고서와 상태 정리는 같은 PR의 후속 문서 커밋
PR: https://github.com/KIM0296/edit-program/pull/1
승인된 Specification / ADR: tasks/TASK_002_INV002_INV003.md, docs/TIMELINE_SAFETY.md, DECISIONS.md ADR-008~012
승인 근거: 2026-10-05 사용자 TASK-001 Chat Gate APPROVED WITH CHANGES 및 TASK-002 명시적 범위 승인
요청 Gate: **APPROVED** (Codex의 요청이며 Chat 판정이 아님)

## 1. 구현 내용

- ADR-008~012를 Accepted Decisions에 기록하고 ADR-007을 이동했습니다. TASK-001 required types를 13에서 12로 정정했습니다.
- 구현 전에 TASK-002 spec과 Python 3.11 CI를 `d65b3f4` 커밋에 기록했습니다.
- ProtectedRange는 HARD_LOCK입니다. 직접 겹침, 앞쪽 ripple로 인한 absolute position 이동 모두 첫 삭제 함수 호출 전에 전체 plan을 거부합니다.
- EditPlan의 명시적 approved_ripple_displacements만 허용합니다. 누락·잘못된 delta·잘못된 구간/track·중복·추가 승인은 거부합니다.
- 원본 snapshot에서 남아야 할 clip fragment들을 계산하고, sequential simulation 결과의 placement/media identity, source range, content order, timeline position과 비교합니다.
- 성공한 nonempty plan은 version을 한 번 증가시킵니다. 거부·실패·empty no-op은 snapshot/version을 변경하지 않습니다.
- 기존 INV-001 테스트의 검증 조건을 보존하고 fixture에 명시적 ripple 승인을 추가했습니다.

Acceptance criteria: TASK spec의 모든 구현/검증 항목 충족. Chat Gate 판정과 merge는 별도 대기입니다.
제외: Resolve API, A/V relationship, retime, transition, transaction/rollback engine, AI 및 후속 TASK.

## 2. 변경된 파일

| 파일 | 변경 목적 |
| --- | --- |
| `.github/workflows/ci.yml` | Python 3.11 pytest/Ruff/mypy, branch push 및 PR 검사 |
| `DECISIONS.md` | 승인 ADR, 기존 OPEN 해결 상태와 ADR-007 정렬 |
| `IMPLEMENTATION_STATUS.md` | 타입 수 정정, TASK-002 결과·CI·PR 기록 |
| `KNOWN_LIMITATIONS.md` | HARD_LOCK 범위, plan 호환성, 미지원 영역 |
| `docs/TEST_MATRIX.md` | INV-002/003 제한 범위 PASS |
| `docs/reports/TASK_002_COMPLETION.md` | 표준 완료 보고서 |
| `tasks/TASK_002_INV002_INV003.md` | 구현 전 spec 및 acceptance 체크리스트 |
| `src/davinci_ai_editor/domain.py` | ProtectedRange, RippleDisplacement, snapshot/plan 필드 |
| `src/davinci_ai_editor/fake_timeline.py` | preflight와 결과 검사 연결 |
| `src/davinci_ai_editor/safety.py` | 원본 기준 expected layout, 보호 및 승인 검사 |
| `tests/test_inv001.py` | 기존 회귀 fixture의 명시적 승인 |
| `tests/test_inv002_inv003.py` | 독립 frame oracle, HARD_LOCK, displacement, 변조 사례 |
| `tests/test_inv002_regressions.py` | 기존 구현에서 먼저 실패한 INV-002 두 사례 |

### git diff --stat

비교 기준: `main`의 `20bdc17938c308105fb4a026edae3b3f9114b791` → 이 보고서를 포함하는 PR 제출 트리.
보고서 아래 통계는 제출 직전 index와 실제 비교한 결과입니다. 코드 검증 commit은 `84e15f7`이며 후속 변경은 문서뿐입니다.

```text
 .github/workflows/ci.yml               |  21 +++
 DECISIONS.md                           |  56 +++++++-
 IMPLEMENTATION_STATUS.md               |  48 ++++++-
 KNOWN_LIMITATIONS.md                   |  22 +++-
 docs/TEST_MATRIX.md                    |   8 +-
 docs/reports/TASK_002_COMPLETION.md    | 146 ++++++++++++++++++++
 src/davinci_ai_editor/domain.py        |  37 +++++-
 src/davinci_ai_editor/fake_timeline.py |  30 ++---
 src/davinci_ai_editor/safety.py        |  98 ++++++++++++++
 tasks/TASK_002_INV002_INV003.md        |  76 ++++++++++-
 tests/test_inv001.py                   |  23 +++-
 tests/test_inv002_inv003.py            | 234 +++++++++++++++++++++++++++++++++
 tests/test_inv002_regressions.py       |  65 +++++++++
 13 files changed, 822 insertions(+), 42 deletions(-)
```

## 3. 테스트 결과

- 로컬: Windows / Python 3.14.6, **57 passed / 0 failed / 1 skipped**.
- CI: Ubuntu GitHub-hosted runner / Python **3.11.16**, **57 passed / 0 failed / 1 skipped**.
- Ruff: 통과. Mypy: source 4개 통과.
- CI 증거: https://github.com/KIM0296/edit-program/actions/runs/37274008568 (구현 commit PR 검사).
- skipped: 기존 opt-in naive 실패 시연 1건. 일반 naive 회귀 검사는 항상 실행됩니다.
- Red evidence: 변경 전 displacement 미승인과 media identity 변조를 거부하지 않아 새 테스트 2건이 `DID NOT RAISE`로 실패했습니다.
- 보호 테스트는 타입 구현 전 import 실패를 확인했습니다. 구현 후 spy로 mutation 전 거부를 검증했습니다.
- 미실행: 실제 Resolve, A/V sync, rollback, 나머지 P0. 범위 밖이며 후속 승인 TASK가 필요합니다.

### pytest 결과

```text
python -m pytest -q
57 passed, 1 skipped
python -m ruff check src tests
All checks passed!
python -m mypy
Success: no issues found in 4 source files
```

### Safety Gate

| Invariant | 결과 | 근거와 검증 범위 |
| --- | --- | --- |
| Wrong target edit | PASS (fake 범위) | INV-001 유지; 다중 삭제 정/역순, 동일 media 별도 placement |
| Protected range violation | PASS (fake 범위) | 내부/부분/전체 겹침, 앞쪽 ripple, 인접 경계, gap, 다중 보호/command; mutation 전 reject |
| Silent timeline damage | PASS (INV-002 범위) | 독립 frame oracle, 정확한 displacement, media/source/order/position 누락·추가·변조 탐지 |
| A/V sync regression | 미검증 | 관계 모델 미구현 |
| Failed rollback | 미검증 | transaction/rollback 미구현; snapshot 미공개 검사는 rollback 구현이 아님 |

전체 P0 release gate 통과를 주장하지 않습니다. INV-004~018은 미완료입니다.

## 4. 구현 과정에서 발견한 설계 문제

- 기존 ripple=True는 어떤 콘텐츠가 얼마나 움직여도 승인한 것인지 표현하지 못했습니다. ADR-011에 따라 원본 구간별 signed displacement를 plan에 명시하도록 했습니다.
- proposal helper는 계산만 수행합니다. 호출자가 plan에 명시적으로 포함해야 하며, apply는 누락된 승인을 채우지 않습니다. 별도 사용자 승인 UI는 구현하지 않았습니다.
- 일반 transaction/rollback이나 모든 NLE 의존성을 검사하는 postflight engine으로 확장하지 않았습니다.
- 기존 ADR-007의 누락된 legacy review 링크는 존재한다고 주장하지 않도록 historical artifact 부재를 명시했습니다.
- 이번 승인 범위를 막는 새 architecture ambiguity는 없습니다.

## 5. DECISIONS.md OPEN 항목

- 새 OPEN 추가 없음.
- OPEN-001: production persistent Resolve identity 문제 유지. fake lineage로 대체하지 않습니다.
- OPEN-003: version 단위와 fake lineage는 ADR-009/012로 해결, Resolved Decision History로 이동. production identity는 OPEN-001에 남습니다.
- OPEN-004: interval/protection/ripple 정책은 ADR-008/010/011로 해결. cross-clip/multi-track 범위만 OPEN으로 유지합니다.
- OPEN-002: 기존 후보 승인/live timeline authority UX 항목 유지, 이번 TASK 범위 밖입니다.
- 대안·trade-off: 다중 트랙/cross-clip은 분할 실행 또는 검토 정책이 필요하지만 임의 확대하지 않고 명시적 미지원 상태를 유지합니다.

## 6. KNOWN_LIMITATIONS.md 변경 사항

- 단일 트랙, integer half-open frame, 정속 1:1 mapping, 한 fragment 안의 ripple DELETE만 지원합니다.
- HARD_LOCK에는 override/soft/follow 모드가 없습니다. 보호 콘텐츠가 살아남더라도 absolute position이 움직이면 거부합니다.
- 기존 ripple=True만 있는 plan은 위치 이동 시 명시적 displacement를 추가해야 합니다.
- 보호는 fake 생성 시 제공하며 편집 UI, persistence, 보호 수정 lifecycle은 미구현입니다.
- Python 3.11 미검증 제한은 CI 실행으로 해소했습니다. 실제 Resolve/OS 연결 검증으로 확대 해석하지 않습니다.

## 7. Specification과 다르게 구현한 부분

- 승인 범위에서 확인된 차이: 없음.
- 내부 plan에 displacement 목록을 추가한 것은 ADR-011의 구체적 구현입니다. 외부 versioned IR JSON schema를 정의하거나 migration을 구현하지 않았습니다.
- empty plan은 commit하지 않는 no-op으로 기존 동작을 유지합니다. rollback 동작은 정책만 기록하고 구현하지 않았습니다.
- 새 기능의 main 직접 구현/merge 없음. 지정 branch와 PR에서 검토를 요청합니다.

## 8. 다음 TASK 제안

- 제안: TASK-003 범위 결정만 요청합니다. 아직 구현하지 않습니다.
- 후보 목표: 기존 OPEN과 잔여 P0 우선순위를 검토해 다음 단일 invariant를 선정합니다.
- 선행 결정: 관계 보존 또는 상태 안전성 중 우선순위와 필요한 domain 경계.
- Acceptance 초안: 선정 invariant의 red-first 재현, INV-001~003 회귀 통과, CI 통과, 미지원 범위 명시.
- 승인 여부: **미승인**. 이번 TASK의 금지 영역을 다음 TASK로 자동 승인하지 않습니다.

## 9. Chat 검토란

- 판정: Chat 작성 대기
- 판정 근거: 위 PR diff, TASK spec, ADR-008~012, 테스트 및 CI 증거
- 필수 수정 및 재검증: Chat 지정 대기
- 다음 TASK / 병행 허용 범위: 미확정
- 승인 기록 링크: TASK-002 최종 Gate 승인 없음
