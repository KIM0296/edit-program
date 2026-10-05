# Chat ↔ Codex Collaboration Workflow

## 목적

Chat과 Codex가 서로 같은 일을 중복하거나, 반대로 중요한 의사결정을 누락하지 않게 한다.

## Chat 책임

Chat은 다음 질문에 답한다.

- 무엇을 만들 것인가?
- 왜 필요한가?
- 어떤 사용자 행동이 맞는가?
- 어떤 실패를 절대 허용하면 안 되는가?
- ambiguity가 있을 때 어느 방향이 제품 원칙에 맞는가?

대표 산출물:

- Product Spec
- Architecture Decision
- Timeline Invariant
- UX policy
- Safety rule
- scope / milestone decision

## Codex 책임

Codex는 다음 질문에 답한다.

- spec을 어떤 type/module로 구현할 것인가?
- 테스트를 어떻게 재현할 것인가?
- 어떤 코드 변경이 필요한가?
- 테스트/타입체크가 통과하는가?
- Resolve runtime에서 실제 API가 어떻게 동작하는가?

대표 산출물:

- source code
- tests
- adapters
- mocks
- refactoring
- bug reproduction
- implementation finding

## Escalation Rule

Codex가 다음 상황을 만나면 Chat decision이 필요하다.

1. spec끼리 충돌
2. Resolve API 한계 때문에 invariant를 그대로 구현하기 어려움
3. persistent identity를 얻을 방법이 불명확
4. safe action의 의미가 여러 개 가능
5. 자동화와 사용자 확인의 경계가 애매함
6. 기존 product principle을 완화해야만 구현 가능

이 경우:

```text
DECISIONS.md

OPEN-XXX
Context:
Observed behavior:
Options:
Codex recommendation:
Needs Chat decision:
```

형식으로 기록한다.

## Milestone Handoff

Codex → Chat 보고 형식:

```text
Milestone:

Implemented:
- ...

Tests:
- 42 passed
- 0 failed
- 2 skipped

Observed constraints:
- ...

Architecture questions:
- OPEN-003 ...

Next proposed milestone:
- ...
```

Chat은 질문을 검토하고 `DECISIONS.md`를 업데이트한 뒤 다음 구현 범위를 고정한다.

## Source of Truth

- Runtime/project truth: Resolve
- Code truth: repository
- Product/safety truth: repository docs approved through Chat decision
- Temporary discussion: Chat conversation

중요한 결정은 대화에만 남기지 않고 repository 문서로 이관한다.
