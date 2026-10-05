# edit-program

DaVinci Resolve AI Editing System

AI가 DaVinci Resolve의 현재 프로젝트와 타임라인을 이해하고, 자연어 편집 의도를 안전한 Edit Plan으로 변환하며, 기존 편집 구조를 보존한 채 반복 작업을 줄이는 **AI Assistant Editor** 프로젝트다.

## 핵심 원칙

- **Preserve Before Improve** — 개선보다 기존 편집 보존이 우선이다.
- **No Silent Damage** — 예상하지 못한 변경은 성공으로 취급하지 않는다.
- **First Use Must Save Time** — 첫 사용부터 사용자 시간이 실제로 절감되어야 한다.
- **No Training Tax** — 사용자가 AI를 훈련시키기 위해 별도 노동을 하지 않는다.
- **Resolve is the Source of Truth** — 실제 프로젝트 상태는 DaVinci Resolve가 기준이다.
- **LLM Never Executes Directly** — LLM은 Resolve API를 직접 호출하지 않고 Editing IR만 생성한다.

## Chat / Codex 역할 분담

### Chat
제품/아키텍처/안전 계약을 결정한다.

- 제품 방향 및 타깃
- 핵심 모듈의 책임
- 편집 의미론과 edge case 판단
- Timeline Invariant 변경
- Editing IR의 큰 변경
- Safety Rule 변경
- 사용자 workflow 변경
- 구현 중 발견된 구조적 문제의 최종 판단

### Codex
합의된 spec을 코드와 테스트로 구현한다.

- repository 작업
- Python 구현
- pytest 작성/실행
- mock/fake timeline 구축
- Resolve API adapter 구현
- 디버깅/리팩터링
- lint/typecheck
- Git 단위 작업
- 구현 중 발견한 architecture question 기록

**Codex는 architecture를 임의로 재정의하지 않는다.** 결정이 필요한 사항은 `DECISIONS.md`에 `OPEN`으로 기록하고 Chat 검토 대상으로 남긴다.

## 시작 순서

1. `AGENTS.md`
2. `START_HERE_CODEX.md`
3. `docs/PRODUCT_SPEC.md`
4. `docs/ARCHITECTURE.md`
5. `docs/TIMELINE_SAFETY.md`
6. `docs/EDITING_IR.md`
7. `docs/TEST_MATRIX.md`
8. `tasks/TASK_001_DOMAIN_AND_INV001.md`

## 초기 개발 순서

```text
01 Domain Model
02 Fake Timeline Engine
03 Stable Target Resolution
04 Timeline Invariants
05 Transaction / Rollback
06 Post-Edit Verification

--------- Safety Gate ---------

07 Resolve Connector
08 Marker / Non-destructive actions
09 STT / VAD
10 Pause Intelligence
11 Edit Planner
12 Safe Trim
13 Safe Delete
14 Safe Ripple
```

초기 단계에서는 **실제 Resolve destructive edit를 구현하지 않는다.**

## Windows + Codex 빠른 시작

자세한 내용은 `docs/WINDOWS_CODEX_SETUP.md` 참고.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\bootstrap.ps1
codex
```

Codex에 `AGENTS.md`와 `START_HERE_CODEX.md`부터 읽고 `TASK-001`만 수행하도록 지시한다.
