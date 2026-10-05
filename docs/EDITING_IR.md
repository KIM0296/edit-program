# Universal Editing IR

## 목적

LLM과 Resolve API를 분리한다.
LLM은 실행 코드를 만들지 않고 structured Edit Plan을 생성한다.

## Initial Actions

```text
ADD_MARKER
REMOVE_MARKER
TRIM
DELETE
MOVE
INSERT
ADD_SUBTITLE
```

MVP에서는 non-destructive action부터 whitelist한다.

## EditCommand 예시

```json
{
  "action": "DELETE",
  "target": {
    "stable_target_id": "target_001"
  },
  "params": {
    "ripple": true
  },
  "reason": "unnecessary pause",
  "confidence": 0.96
}
```

## StableTarget 최소 모델

```json
{
  "timeline_id": "timeline_main",
  "timeline_version": 42,
  "coordinate_space": "TIMELINE",
  "timeline_start_frame": 900,
  "timeline_end_frame": 960,
  "track_id": "V1",
  "clip_id": "clip_0182",
  "media_id": "media_A003",
  "source_start_frame": 12430,
  "source_end_frame": 12490
}
```

실제 persistent identity 전략은 Resolve API 검증 후 확정한다.

## Plan lifecycle

```text
DRAFT
→ VALIDATED
→ PREFLIGHT_PASSED
→ APPROVED
→ EXECUTING
→ VERIFIED
→ COMMITTED
```

실패:

```text
REJECTED
STALE
FAILED
ROLLED_BACK
```
