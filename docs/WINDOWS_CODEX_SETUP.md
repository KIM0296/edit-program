# Windows + Codex CLI Setup

## 1. 프로젝트 위치

권장 예시:

```powershell
C:\dev\davinci-ai-editor
```

압축 파일을 해당 위치에 풀거나 repository를 이동한다.

## 2. PowerShell

프로젝트 root에서:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\bootstrap.ps1
```

bootstrap은:

1. Python 확인
2. `.venv` 생성
3. 개발 의존성 설치

까지만 수행한다.

## 3. Git 시작

```powershell
git init
git add .
git commit -m "chore: initialize safety-first project spec"
```

## 4. Codex 시작

```powershell
codex
```

Codex 첫 메시지는 다음 취지로 전달한다.

```text
Read AGENTS.md and START_HERE_CODEX.md first.
Treat repository docs as the current approved specification.
Implement only tasks/TASK_001_DOMAIN_AND_INV001.md.
Do not connect to DaVinci Resolve yet.
Do not implement future tasks.
Start with tests, reproduce the failure, then implement the minimum domain layer required to make INV-001 pass.
Record architecture ambiguity in DECISIONS.md instead of making an irreversible product decision.
When finished, update IMPLEMENTATION_STATUS.md and report tests, files changed, open decisions, and the proposed TASK-002 scope.
```

## 5. TASK-001 완료 후

Codex가 다음을 보고하도록 한다.

```text
TASK-001 complete

Implemented:
Tests:
Files changed:
Open decisions:
Known limitations:
Recommended TASK-002:
```

구조적 결정이 없다면 다음 task로 진행한다.
구조적 문제가 발견되면 Chat에서 검토 후 `DECISIONS.md`에 결정을 기록한다.

## 6. 중요한 원칙

처음부터 Resolve에서 실제 영상을 자르지 않는다.

```text
Domain
→ Fake Timeline
→ Invariants
→ Transaction
→ Verification
→ Resolve Read-only
→ Resolve Destructive Sandbox
```

순서를 유지한다.
