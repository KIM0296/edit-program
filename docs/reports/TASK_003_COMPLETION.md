# TASK 완료 보고서

TASK: TASK-003
제목: Relationship Domain Foundation
상태: 구현 완료, Chat Gate 검토 대기
브랜치: `feat/task-003-relationship-domain`
Commit: 구현 `3186cbdf9fc8696eb625a91c19f9e0563fd8d414`; 이 보고서와 검증 기록은 같은 PR의 후속 문서 커밋
PR: https://github.com/KIM0296/edit-program/pull/2
승인된 Specification / ADR: tasks/TASK_003_RELATIONSHIP_DOMAIN.md, docs/TIMELINE_SAFETY.md, ADR-008/009/012
승인 근거: 사용자 TASK-002 APPROVED 및 PR #1 병합 통보, Relationship Domain Foundation 명시적 구현 지시
요청 Gate: **APPROVED** (Codex 요청이며 Chat 판정이 아님)

## 1. 구현 내용

- 구현 전에 TASK-003 spec과 OPEN-005를 `88d1257`에 기록했습니다. 병합된 `main`의 `747474a`에서 새 브랜치를 만들었습니다.
- TrackType, fake TimelineObjectId, RelationshipId, RelationshipType, RelationshipMember, RelationshipPolicy, Relationship, RelationshipGraph를 추가했습니다.
- AV_LINK / SYNC_GROUP / SUBTITLE_FOLLOWS_DIALOGUE / ANCHOR를 표현합니다.
- FOLLOW / STAY / RECALCULATE / REVIEW는 객체별 immutable metadata입니다. 정책 실행, 암묵적 공동 이동, 시간 정렬을 하지 않습니다.
- RelationshipGraph는 immutable TimelineSnapshot에 포함됩니다. graph 생성/추가 시 없는 객체 참조를 거부하고, snapshot 부착 시 registry와 실제 placement들의 일치를 검증합니다.
- fake 객체 identity는 `(track_id, clip_id placement lineage)`입니다. 같은 media의 여러 placement와 다른 track의 동일 clip_id를 혼동하지 않습니다. production ID로 간주하지 않습니다.
- J-cut/L-cut의 서로 다른 video/audio 시작·끝과 source range를 그대로 유지합니다.
- 관계가 있는 nonempty plan은 첫 delete 전에 REVIEW 오류로 거부합니다. 관계 실행 의미를 임의 구현하지 않았습니다.

| Acceptance criteria | 결과와 근거 |
| --- | --- |
| 필수 모델과 후보 relation type | 모두 구현, 각 enum과 n-ary SYNC_GROUP 테스트 |
| immutable snapshot graph | frozen 값 객체, tuple 방어 복사, 이전 graph/snapshot 불변 검사 |
| 없는 객체 참조 금지 | graph dangling reference 및 snapshot phantom/incomplete registry 거부 |
| 반복 media placement 구분 | 같은 media/source를 사용하는 별도 placement 조회 테스트 |
| J/L-cut 정상 상태 | AV_LINK 부착 전후 video/audio 범위 동일, 강제 정렬 없음 |
| policy는 표현만 | member별 서로 다른 policy 보존, 실행 전 REVIEW 거부 |
| 기존 회귀 유지 | TASK-001/002 테스트 파일 4개 수정 없음, 전체 suite 통과 |
| PR/CI/보고 | PR #2, Python 3.11 CI 통과, 본 표준 보고서 제출 |

제외: 실제 A/V sync 수정, multi-track ripple execution, subtitle retiming, B-roll 이동, Resolve API, transaction/rollback, retime, AI.

## 2. 변경된 파일

| 파일 | 변경 목적 |
| --- | --- |
| `tasks/TASK_003_RELATIONSHIP_DOMAIN.md` | 구현 전 spec 및 acceptance 기준 |
| `DECISIONS.md` | TASK-002 승인 기록과 OPEN-005 |
| `src/davinci_ai_editor/domain.py` | immutable 관계 타입, graph/reference/snapshot 검증 |
| `src/davinci_ai_editor/fake_timeline.py` | graph 저장, 관계 없는 편집 후 registry 재생성 |
| `src/davinci_ai_editor/safety.py` | 관계가 있는 plan의 실행을 mutation 전에 거부 |
| `tests/test_relationship_domain.py` | foundation 신규 테스트 26개 |
| `IMPLEMENTATION_STATUS.md` | TASK-003 구현/검증/PR 상태 |
| `KNOWN_LIMITATIONS.md` | fake identity, descriptor binding, 정책 실행 미지원 |
| `docs/TEST_MATRIX.md` | foundation 검증 추가; INV-004/006 TODO 유지 |
| `docs/reports/TASK_003_COMPLETION.md` | 표준 완료 보고서 |

### git diff --stat

비교 기준: `main`의 `747474a66af1b8ebbf5254de8df426e5e4f17000` → 본 보고서를 포함한 PR 제출 트리.
아래는 제출 직전 실제 index 비교 결과입니다. 검증된 구현 commit은 `3186cbd`; 후속 변경은 문서뿐입니다.

```text
 DECISIONS.md                           |  28 ++++
 IMPLEMENTATION_STATUS.md               |  36 ++++-
 KNOWN_LIMITATIONS.md                   |  22 ++-
 docs/TEST_MATRIX.md                    |   9 ++
 docs/reports/TASK_003_COMPLETION.md    | 156 +++++++++++++++++++
 src/davinci_ai_editor/domain.py        | 150 +++++++++++++++++-
 src/davinci_ai_editor/fake_timeline.py |  11 +-
 src/davinci_ai_editor/safety.py        |   2 +
 tasks/TASK_003_RELATIONSHIP_DOMAIN.md  |  83 ++++++++++
 tests/test_relationship_domain.py      | 272 +++++++++++++++++++++++++++++++++
 10 files changed, 762 insertions(+), 7 deletions(-)
```

## 3. 테스트 결과

- 로컬 Windows / Python 3.14.6: **83 passed / 0 failed / 1 skipped**.
- CI Ubuntu / Python 3.11.16: **83 passed / 0 failed / 1 skipped**.
- Ruff 통과, mypy source 4개 통과.
- CI 증거: https://github.com/KIM0296/edit-program/actions/runs/37276145821
- 테스트 먼저 작성: 구현 전 Relationship 타입 부재로 collection error 확인 후 구현했습니다. 이번에는 새 destructive action을 만들지 않았습니다.
- 중간 Ruff 검사에서 타입 오류에 ValueError를 사용한 4건을 발견해 TypeError로 수정했습니다. 최종 lint 실패는 없습니다.
- skipped: 기존 opt-in naive 실패 시연 1건. 일반 naive 회귀 검사는 실행합니다.
- 미실행: Resolve 통합, 실제 A/V sync 보정, 관계 policy 실행, rollback. 범위 밖이며 후속 승인 TASK에서 별도 검증해야 합니다.

### pytest 결과

```text
python -m pytest -q
83 passed, 1 skipped
python -m ruff check src tests
All checks passed!
python -m mypy
Success: no issues found in 4 source files
```

### Safety Gate

| Invariant | 결과 | 검증 범위 |
| --- | --- | --- |
| Wrong target edit | PASS (기존 fake 범위) | INV-001 회귀 유지, graph가 반복 placement를 media로 혼동하지 않음 |
| Protected range violation | PASS (기존 fake 범위) | INV-003 HARD_LOCK 회귀 유지 |
| Silent timeline damage | PASS (INV-002 및 표현 범위) | 기존 INV-002 유지, graph 부착 시 timing/source 변경 없음, 관계 편집은 실행 전 거부 |
| A/V sync regression | 미검증 | J/L-cut 표현 보존만 검사; 실제 sync/relationship execution 미구현 |
| Failed rollback | 미검증 | transaction/rollback 미구현 |

INV-004 및 full INV-006, 전체 P0 release gate 통과를 주장하지 않습니다.

## 4. 구현 과정에서 발견한 설계 문제

- 기존 fake split은 하나의 placement lineage를 여러 clip fragment로 표현합니다. 관계 registry는 fragment 좌표 대신 lineage를 사용하며, 다른 media 또는 겹친 source range를 같은 lineage로 모호하게 넣는 경우 거부합니다.
- 관계 타입만으로 방향, leader/follower 역할, 공통 이동량을 정하면 J/L-cut 등 편집 의도를 손상할 수 있습니다. 이번 모델은 n-ary membership과 member별 policy metadata만 표현합니다.
- Relationship 값 자체에는 timeline context가 없습니다. unbound descriptor는 만들 수 있지만, 존재하지 않는 객체를 가리키는 graph 생성/추가 및 snapshot binding은 실패합니다. descriptor를 유효한 timeline 관계로 취급하지 않습니다.
- registry가 허구의 객체 목록으로 만들어져도 실제 snapshot과 일치하지 않으면 부착할 수 없습니다.
- 정책 실행이 없는 상태에서 기존 delete가 관계를 조용히 손상시키지 않도록 nonempty graph 편집은 REVIEW로 거부합니다.

## 5. DECISIONS.md에 추가한 OPEN 항목

**OPEN-005 — Relationship execution semantics and lifecycle**

- 문제: 타입별 방향/역할/cardinality, split/delete 후 관계 재연결, cycle 및 policy 충돌 처리 의미가 미정입니다.
- 대안: symmetric/n-ary membership 대 directed roles; lineage 유지 대 fragment별 재연결; 충돌 REVIEW 대 승인된 결정적 처리.
- trade-off: 표현 범용성과 실행 안전성 사이의 선택이며, 편집 의도 및 향후 IR 계약에 영향을 줍니다.
- 권고: 이번에는 데이터 표현만 유지하고 실제 실행 전 Chat에서 의미를 결정합니다.
- 의존 작업: 향후 A/V sync, subtitle following, B-roll anchor, multi-track ripple.
- 보류 범위: 모든 relationship policy execution. 이번 foundation 구현은 완료했습니다.

**OPEN-001** production Resolve persistent identity는 그대로 OPEN입니다. 기존 OPEN-002/004도 임의 확정하지 않았습니다.

## 6. KNOWN_LIMITATIONS.md 변경 사항

- TimelineObjectId는 snapshot-local fake placement lineage이며 persistent ID가 아닙니다.
- 현재 registry는 clip placement 기반입니다. subtitle/anchor 관계를 fake placement로 표현할 수 있으나 실제 subtitle/marker/effect adapter는 없습니다.
- 여러 track의 관계 snapshot은 표현할 수 있지만 FakeTimeline executor는 여전히 single-track입니다.
- relation type별 의미론적 cardinality/역할, 자동 propagation, cycle 해소, split/delete lifecycle은 미구현입니다.
- 관계가 있는 plan은 REVIEW 오류로 거부합니다. 이는 정책 실행이나 사용자용 REVIEW UI 구현이 아닙니다.
- 해소 조건: OPEN-005 승인 및 해당 실행 기능의 별도 TASK·테스트. OPEN-001은 실제 Resolve 검증 필요.

## 7. Specification과 다르게 구현한 부분

- 작성된 TASK-003 spec과 확인된 차이: 없음.
- 사용자 요구의 참조 무결성은 graph 생성/추가와 snapshot binding에서 보장합니다. standalone Relationship은 unbound descriptor라는 구현 해석을 spec·PR에 명시했으며 Gate 검토 대상입니다.
- enum의 FOLLOW/STAY 등은 명령 실행이 아닌 데이터입니다. 관계 존재를 동일한 움직임으로 해석하지 않았습니다.
- 외부 IR schema, production identity 및 timeline semantics를 새로 확정하지 않았습니다.

## 8. 다음 TASK 제안

- 다음 TASK는 자동 착수하지 않습니다. 번호에 따라 INV-004를 선택하지 않습니다.
- 제안 목표: Chat에서 OPEN-005의 역할·방향·정책 충돌 의미 중 필요한 범위를 먼저 결정합니다.
- Acceptance 초안: 승인된 관계 의미를 표현하는 사례, J/L-cut 유지, 모든 기존 회귀 및 CI 통과, 미지원 시 명시적 REVIEW.
- 실제 relationship execution 여부와 범위는 별도 승인 필요합니다.
- 현재 승인 여부: **미승인**.

## 9. Chat 검토란

- 판정: Chat 작성 대기
- 판정 근거: TASK-003 spec, PR #2 diff, 참조/불변성/identity/J-L-cut 테스트와 CI
- 필수 수정 및 재검증: Chat 지정 대기
- 다음 TASK / 병행 허용 범위: 없음, 추가 승인 대기
- 승인 기록 링크: TASK-003 최종 Gate 승인 없음
