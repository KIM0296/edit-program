# AGENTS.md — DaVinci AI Editor Agent Contract

이 파일은 Codex 및 repository를 수정하는 모든 AI agent가 반드시 따라야 하는 최상위 작업 규칙이다.

## 1. 역할

Codex의 역할은 **구현자(Implementation Agent)** 다.
제품 전략가나 최종 architecture 의사결정자가 아니다.

Chat의 역할은 **Product / Architecture / Safety Decision Layer** 다.

다음 변경은 Codex가 독단적으로 확정하면 안 된다.

- Timeline Invariant 추가/삭제/완화
- Safety Gate 완화
- destructive action 자동 실행 범위 확대
- Editing IR의 호환성을 깨는 변경
- 사용자의 기존 편집을 덮어쓰는 정책
- persistent media identity 전략 변경
- stale plan 처리 정책 변경
- transaction/rollback 의미 변경
- product target 또는 주요 UX 변경

필요 시 `DECISIONS.md`에 `OPEN` 상태로 기록한다.

---

## 2. 절대 제품 원칙

1. Preserve Before Improve.
2. No Silent Damage.
3. First Use Must Save Time.
4. No Training Tax.
5. Resolve is the Source of Truth.
6. Human edit wins.
7. LLM must never call Resolve APIs directly.
8. Every destructive operation must pass Safety Core.
9. AI edit one transaction should behave like one user-understandable operation.
10. Unknown or ambiguous destructive behavior defaults to REVIEW, not APPLY.
11. Preserve Editability.
12. Native Editing Environment Preservation.
13. Preview/render may flatten for display, but must not replace editable project state.

---

## 3. 필수 architecture path

```text
User Intent
    ↓
Context / Scope Resolver
    ↓
Media / Editing Intelligence
    ↓
Edit Planner
    ↓
Editing IR
    ↓
Validator
    ↓
Timeline Safety Core
    ↓
Validated Transaction
    ↓
Adapter
    ↓
Resolve
    ↓
Post-Edit Verification
```

우회 경로를 만들지 않는다.

금지 예:

```text
LLM → Resolve API
LLM → arbitrary Python execution
Edit Planner → destructive adapter without validation
```

---

## 4. Safety Core 구성

다음 모듈은 핵심 계층으로 취급한다.

- Timeline Integrity Engine
- Temporal Mapping Engine
- Relationship Integrity Engine
- Dependency Preservation Engine
- Media Identity Engine
- State & Transaction Engine
- Post-Edit Verification Engine

이 모듈을 편의상 생략하지 않는다.

---

## 5. 개발 규칙

모든 destructive behavior는 다음 순서를 따른다.

1. 테스트 케이스 작성
2. 테스트 실패 확인
3. 최소 구현
4. 해당 invariant 통과
5. 전체 P0 테스트 실행
6. expected diff와 actual diff 비교
7. 문서/상태 업데이트

새 destructive action을 만들 때 테스트 없이 구현하지 않는다.

---

## 6. Resolve API 규칙

- API 동작을 추측하지 않는다.
- 설치된 Resolve Developer/Scripting 문서 및 실제 runtime 결과로 검증한다.
- API가 불충분하면 우회 구현을 임의로 넣지 말고 `KNOWN_LIMITATIONS.md`와 `DECISIONS.md`에 기록한다.
- UI automation은 별도 승인 없이 기본 전략으로 채택하지 않는다.

---

## 7. 테스트 규칙

P0 invariant는 release gate다.

- P0: 100% pass 필요
- unexpected silent change: 0건
- wrong-target edit: 0건
- protected range violation: 0건
- A/V sync regression: 0건
- rollback failure: 0건

P0가 깨진 상태에서 destructive feature를 확장하지 않는다.

---

## 8. 작업 완료 시 보고

Codex 작업 완료 시 최소 다음을 남긴다.

```text
Changed:
- ...

Tests:
- N passed
- N failed
- N skipped

Open decisions:
- ...

Known limitations:
- ...

Next recommended task:
- ...
```

architecture 판단이 필요하면 구현을 억지로 진행하지 말고 명확한 질문으로 남긴다.
