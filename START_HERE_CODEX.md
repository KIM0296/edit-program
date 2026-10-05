# START HERE — Codex

## 현재 단계

프로젝트는 **기획 → 안전 계약 → 구현 준비** 단계까지 고정되었다.
이제 실제 코드 구현을 시작한다.

현재 최우선 목표는 DaVinci Resolve를 직접 제어하는 것이 아니다.
**Resolve 없이도 검증 가능한 Timeline Safety Core를 먼저 구축한다.**

---

## 먼저 읽을 파일

순서대로 읽는다.

1. `AGENTS.md`
2. `docs/PRODUCT_SPEC.md`
3. `docs/ARCHITECTURE.md`
4. `docs/TIMELINE_SAFETY.md`
5. `docs/EDITING_IR.md`
6. `docs/TEST_MATRIX.md`
7. `DECISIONS.md`
8. `KNOWN_LIMITATIONS.md`
9. `tasks/TASK_001_DOMAIN_AND_INV001.md`

---

## 첫 작업

`tasks/TASK_001_DOMAIN_AND_INV001.md`만 구현한다.

처음부터 Resolve API 연결, STT, LLM, UI를 구현하지 않는다.

첫 milestone:

```text
Timeline domain model
        ↓
FakeTimeline
        ↓
Stable target resolution
        ↓
INV-001 test
```

### 목표

다음 사용자 명령이 안전하게 표현될 수 있어야 한다.

> 00:00:30~00:00:32와 00:01:30~00:01:32를 삭제

첫 번째 삭제로 타임라인이 당겨지더라도 두 번째 target이 최초 명령 시점의 위치를 가리켜야 한다.

---

## 구현 전 Codex가 해야 할 일

1. repository 문서를 읽는다.
2. TASK-001 구현 계획을 짧게 작성한다.
3. architecture ambiguity가 있으면 구현 전에 `DECISIONS.md`에 OPEN 항목을 남긴다.
4. 테스트부터 작성한다.
5. 테스트 실패를 확인한다.
6. 최소 구현으로 통과시킨다.
7. 전체 결과를 `IMPLEMENTATION_STATUS.md`에 반영한다.

---

## 첫 구현에서 금지되는 것

- Resolve API 사용
- LLM API 사용
- FastAPI 서버 구현
- UI 구현
- 실제 파일 삭제/변경
- 자동 rebase
- arbitrary shell integration
- future feature 선구현

---

## 첫 작업 완료 기준

- domain type이 최소 요구사항을 충족
- FakeTimeline 존재
- timeline version 존재
- StableTarget 존재
- INV-001 pytest가 재현 가능
- 첫 deletion 이후 두 번째 target 오인 없음
- tests pass
- 상태 문서 갱신

완료 후 다음 작업을 임의로 크게 확장하지 말고 TASK-002 제안을 남긴다.
