# Architecture

## 전체 구조

```text
DaVinci Resolve
      ↕
Resolve Adapter
      ↕
Timeline State Model
      ↓
Context Resolver
      ↓
Brief Resolver
      ↓
Scope Resolver
      ↓
Media Intelligence
      ↓
Editing Intelligence
      ├─ Pause Intelligence
      ├─ Dialogue Intelligence
      └─ Story Intelligence
      ↓
Edit Planner
      ↓
Universal Editing IR
      ↓
Validator
      ↓
Timeline Safety Core
      ↓
Risk / Confidence Engine
      ↓
Preview / Approval
      ↓
Resolve Executor
      ↓
Post-Edit Verification
      ↓
User Correction Observer
      ↓
Editing Profile
```

## Resolve is the Source of Truth

AI가 별도의 authoritative timeline을 만들지 않는다.
AI state는 Resolve state에서 파생된다.

## Timeline Safety Core

```text
Timeline Safety Core
├─ Timeline Integrity Engine
├─ Temporal Mapping Engine
├─ Relationship Integrity Engine
├─ Dependency Preservation Engine
├─ Media Identity Engine
├─ State & Transaction Engine
└─ Post-Edit Verification Engine
```

## Timeline Coordinate Contract

사용자 명령에서 여러 time range가 들어오면 모든 target을 **명령 시점 timeline version에 고정**한다.

잘못된 실행:

```text
A 실행 → timeline 이동 → B를 현재 좌표로 재해석
```

올바른 실행:

```text
명령 수신
↓
Snapshot vN
↓
A/B/C target 모두 stable resolution
↓
Preflight
↓
Transaction apply
```

## Core / Adapter 분리

```text
              Domain / Safety Core
                       │
             ┌─────────┴─────────┐
             │                   │
       FakeTimeline         ResolveAdapter
             │                   │
           pytest              Resolve
```

Safety Core는 Resolve API에 직접 종속되지 않는다.
