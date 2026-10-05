# Known Limitations

Only the TASK-001/002 domain prototype is implemented. The following capabilities remain unsupported/unverified.

## Resolve API 미검증 영역

- persistent TimelineItem identity
- precise ripple behavior via scripting
- arbitrary trim behavior
- nested timeline write
- multicam internal write
- Fusion dependency preservation
- full effect/keyframe serialization
- transaction-level native undo grouping

## 초기 Safety Core에서 REVIEW-only 가능성이 높은 영역

- Variable Frame Rate
- complex speed ramp
- nested multicam
- compound clip internal edits
- offline media
- render-in-place replacement
- complex Fusion composition

## 원칙

미지원 상태를 숨기지 않는다.

```text
unknown → REVIEW
unsupported → explicit limitation
unsafe → reject
```


## TASK-001 FakeTimeline scope

- Memory-only, one track, integer half-open [start, end) frames, 1:1 source mapping.
- Each request must lie inside one clip fragment; cross-clip/gap and overlapping
  requests raise ValueError. No production REVIEW workflow exists yet.
- clip_id is fake placement lineage across splits, not a persistent Resolve item ID.
- Version starts at 1 and advances once per nonempty fake plan. Base version is
  checked before application; full concurrent-state/stale-plan coverage is deferred.
- FakeTimeline.apply is a simulation entry point, not the production safety pipeline.
- No A/V relationships, retime, transitions, actual Resolve/media
  edits, transaction engine, failure-injection rollback or postflight engine.
- Domain values do not define a versioned Editing IR JSON serialization contract.
- Only INV-001/002/003 have scoped fake coverage; the destructive alpha P0 release gate is not satisfied.
- TASK-001 initially used Python 3.14.6 locally; TASK-002 CI verifies the full suite on Python 3.11.16 (run 37274008568).


## TASK-002 scope and remaining limitations

- ProtectedRange is HARD_LOCK per ADR-010; no override or soft/follow policy.
  Earlier ripple is forbidden even when protected source content itself would survive.
- Explicit displacement approval is required for all shifted surviving intervals.
  Old plans containing only ripple=True now reject if content would move (ADR-011).
- The proposal helper does not constitute user approval or bypass protection checks.
- Protection is supplied when constructing the fake snapshot. No UI/persistence/editor
  for changing protection is implemented; production protection lifecycle is out of scope.
- Expected/candidate comparison covers only this fake's clip fields, not arbitrary
  NLE dependencies, production postflight, transaction rollback or concurrency.
- CI targets Python 3.11 on Ubuntu; this does not verify Resolve on any OS.
