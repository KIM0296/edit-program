# Known Limitations

TASK-001/002 fake safety and TASK-003 relationship domain foundation are implemented; production execution remains out of scope. The following capabilities remain unsupported/unverified.

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
- No A/V sync correction or relationship policy execution, retime, transitions, actual Resolve/media
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


## TASK-003 relationship foundation

- TimelineObjectId is snapshot-local (track_id, fake clip placement lineage), not a
  production/persistent Resolve ID. OPEN-001 remains unresolved.
- A Relationship value is an unbound descriptor, not a valid timeline relation by itself.
  Graph construction/addition validates registry references; snapshot construction validates
  that the registry exactly matches actual objects. Only bound graphs have snapshot meaning.
- Current registry covers clip placement lineages. Subtitle/B-roll relationships can be
  described using fake placements; real subtitle/marker/effect object adapters are absent.
- Graphs represent multi-track data but the FakeTimeline executor remains single-track.
- Per-member policies are metadata only. No default common movement, time alignment,
  sync repair, subtitle retiming, anchor following, cycle resolution or lifecycle propagation.
- Nonempty plans against a graph containing relationships reject for REVIEW before mutation.
  This conservative unsupported-scope guard is not a relationship policy executor or UI.
- Type-specific roles/cardinality and split/delete/conflict semantics remain OPEN-005.
- TASK-003 does not certify INV-004 A/V sync or full INV-006 relationship preservation.


## TASK-004 topology validation scope

- Pure topology projection, diff and validation; no mutation executor or new Resolve state.
- Track order is a zero-based snapshot tuple index, not verified native per-type indices.
- Comparison identity is independent of membership only through explicit fake origin IDs.
  Composite IDs after a move require caller-supplied one-to-one correspondence; without it,
  they appear as removed/added objects and cannot silently count as unchanged. No media matching.
- The adapter/caller must supply truthful provenance and correspondence. Topology cannot
  prove a native label or detect all hidden rendered media/effect replacements (OPEN-007).
- Preview/render/flattened origins are rejected as editable state even if topology matches;
  whole multi-layer replacement with one new object is conservatively REVIEW even if expected.
- Expected diffs are exact, including displaced indices on track insertion/removal. Validation
  does not constitute user approval, apply topology operations, or commit/increment version.
- Relationship records must remain unchanged; projection may translate explicitly supplied
  identity references, not execute relationship policy or lifecycle repair.
- Topology validation does not inspect media/source/time/effects/retime. INV-002 and other
  independent safety checks remain necessary; no full project editability guarantee.
- Preview/render can be represented as artifacts, but this task implements no renderer.
- Preferred effects path is documentation only; no Fusion/FX/external VFX integration.
