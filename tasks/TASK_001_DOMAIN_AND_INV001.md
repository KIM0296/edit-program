# TASK-001 — Domain Model + FakeTimeline + INV-001

## Goal

실제 Resolve API 없이 **Target Coordinate Stability**를 재현하고 검증할 최소 domain layer를 구현한다.

## User Case

사용자 명령:

> 00:00:30~00:00:32와 00:01:30~00:01:32를 삭제해줘.

첫 target을 ripple delete하면 뒤의 timeline position이 2초 당겨진다.
그렇더라도 두 번째 target은 명령 수신 당시의 원래 01:30~01:32 구간을 정확히 가리켜야 한다.

## Required Types

최소 다음 type을 설계한다.

```text
TimelineId
TimelineVersion
TrackId
ClipId
MediaId
FrameRange
Clip
Track
TimelineSnapshot
StableTarget
EditCommand
EditPlan
```

구현 언어: Python.
가능하면 dataclass 또는 명확한 immutable value object를 사용한다.

## FakeTimeline Requirements

FakeTimeline은 최소 다음 동작을 지원한다.

1. timeline 생성
2. clip 배치
3. snapshot/version
4. time range → stable target resolve
5. ripple delete simulation
6. 현재 clip 위치 확인

실제 NLE 기능 전체를 흉내 내지 않는다.
INV-001 재현에 필요한 최소 기능만 만든다.

## Key Rule

다중 target command는 실행 중 현재 timeline coordinate를 다시 조회하여 target을 재해석하면 안 된다.

반드시:

```text
Snapshot v1
↓
Resolve target A
Resolve target B
↓
Execute A/B
```

이어야 한다.

## Test 1 — Failure Reproduction

naive implementation에서 다음 실패를 재현할 수 있어야 한다.

```text
Delete 30~32
timeline shifts -2 sec
Delete current 90~92
→ wrong original content deleted
```

이 테스트/fixture는 설명용으로 유지할 수 있다.

## Test 2 — INV-001 PASS

stable target을 사용하면:

```text
Target A = original 30~32
Target B = original 90~92
```

두 target이 정확히 삭제되어야 한다.

Expected total duration change:

```text
-4 seconds
```

Unexpected original region deletion:

```text
0
```

## Acceptance Criteria

- [x] domain model exists
- [x] FakeTimeline exists
- [x] timeline version exists
- [x] both targets resolved before mutation
- [x] stable target survives first ripple mutation
- [x] INV-001 pytest passes
- [x] naive failure is documented or reproducible
- [x] `IMPLEMENTATION_STATUS.md` updated
- [x] tests pass

## Out of Scope

- actual Resolve API
- audio/video relationships
- transitions
- multicam
- retime
- LLM
- FastAPI
- UI
- database

## Completion Report

작업 종료 시 다음 형식으로 보고한다.

```text
TASK-001 complete

Implemented:
- ...

Tests:
- ...

Files changed:
- ...

Open decisions:
- ...

Recommended TASK-002:
- ...
```
