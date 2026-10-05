# Timeline Safety Contract

## 최상위 원칙

### Preserve Before Improve
AI가 기존 편집을 개선하기 전에 기존 구조와 의도를 먼저 보존한다.

### No Silent Damage
예상하지 못한 변경은 성공이 아니다.

### Human Edit Wins
AI 분석 중 사용자가 변경한 최신 편집 상태가 우선한다.

---

# P0 Timeline Invariants

## INV-001 Target Coordinate Stability
앞쪽 ripple/delete 후에도 후속 target은 명령 수신 당시의 원래 target을 가리켜야 한다.

## INV-002 Unrequested Region Invariance
요청 범위 밖 콘텐츠는 승인된 ripple dependency 외에는 변경되지 않는다.

## INV-003 Protected Range Invariance
Protected Range는 명시적 override 없이는 변경할 수 없다.

## INV-004 A/V Sync Preservation
의도된 J/L-cut을 포함한 기존 A/V 관계를 파괴하지 않는다.

## INV-005 Track State Preservation
Track Lock / Sync Lock / Auto Select / Enable / Mute / Solo 상태를 보존한다.

## INV-006 Relationship Preservation
Video / audio / subtitle / B-roll / SFX / marker 등 관계를 graph로 인식한다.

## INV-007 Retime Safety
speed change, reverse, freeze, speed ramp, VFR에서는 timeline/source 시간을 단순 1:1로 취급하지 않는다.

## INV-008 Hierarchy Safety
Timeline / Compound / Nested Timeline / Multicam / Source 계층을 혼동하지 않는다.

## INV-009 Transition Handle Preservation
trim 후 transition source handle이 무효화되지 않는지 확인한다.

## INV-010 Effect & Keyframe Preservation
clip duration/change가 keyframe/effect/Fusion/audio automation/color 등의 의존성을 손상시키지 않는다.

## INV-011 Media Identity
filename만으로 media를 식별하지 않는다.

## INV-012 Stale Plan Rejection
plan base timeline version과 current timeline version이 다르면 그대로 실행하지 않는다.

## INV-013 Atomic Transaction
다중 destructive edit는 전체 성공 또는 rollback을 기본으로 한다.

## INV-014 No Silent Partial Success
일부 실패를 전체 성공으로 보고하지 않는다.

## INV-015 Post-Edit A/V Verification
execution 후 실제 sync/identity/track/dependency를 재검증한다.

## INV-016 Expected Diff = Actual Diff
예상하지 않은 변경이 1건이라도 존재하면 검증 실패다.

## INV-017 Protected User Work
AI 분석 이후 사용자가 만든 최신 작업을 오래된 plan이 덮어쓰지 않는다.

## INV-018 Marker / Subtitle Temporal Integrity
ripple 후 temporal object마다 올바른 follow/stay policy를 적용한다.

---

## INV-019 Track / Layer Topology Preservation
Approved by user for TASK-004.

Preserve existing Track IDs, types, order, and object-to-track membership. No unrequested
track creation/deletion or object movement. Explicit expected topology change is required
for AI track additions/removals/reordering/moves. Never flatten multiple editable video/audio
layers into one replacement, or use preview/render as editable source of truth.
TASK-004 validates the supplied domain topology/provenance only; no native execution.

---

# P1

- J-cut Preservation
- L-cut Preservation
- B-roll Anchor
- Music Beat Anchor
- Client-approved Segment
- Render-in-place / Compound Awareness
- Offline Media Safety
- Mixed Frame Rate Safety

---

# Severity

## SEV-0 — Project Integrity
wrong target, wrong media, sync damage, protected range violation, failed rollback.

## SEV-1 — Edit Intent Damage
transition/keyframe/B-roll anchor/subtitle 등의 손상.

## SEV-2 — AI Quality
pause, pacing, unnecessary cut 등.

## SEV-3 — Preference
조금 더 길게/빠르게 등의 취향 차이.

**SEV-0/1을 personalization 문제로 처리하지 않는다.**

---

# Release Gate

Destructive editing alpha 조건:

- P0 100% pass
- silent unexpected change 0
- wrong-target edit 0
- protected range violation 0
- A/V sync regression 0
- rollback failure 0
