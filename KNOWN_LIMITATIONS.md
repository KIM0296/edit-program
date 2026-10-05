# Known Limitations

TASK-001/002 fake safety, TASK-003 relationships and TASK-004 topology foundations are implemented; production execution remains out of scope. The following capabilities remain unsupported/unverified.

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
- ADR-013 resolves broad role/delete/conflict semantics. Exact type-specific role/cardinality,
  fragment rebinding and concrete execution rules remain OPEN-005.
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


## TASK-005 dependency compilation scope

- Pure diagnostic plan only; no execution authorization. SAFE_TO_CONTINUE means no
  dependency concern for a valid isolated MOVE/RIPPLE/TRIM/DELETE target, not a complete
  edit preflight. No destination/delta, resulting ranges, or Universal Editing IR exists.
- All connected relationship context is conservatively assessed, including upstream
  drivers/peers. This can over-report possible impact; it is not propagation reachability.
- Any reached relationship requires REVIEW. FOLLOW never becomes a universal action;
  STAY/RECALCULATE remain candidates. RETIME is UNSUPPORTED without Temporal Mapping.
- Roles are optional descriptive data; unspecified legacy roles require REVIEW. Exact
  cardinality/PEER/leader rules are not enforced. Only explicit DRIVER->DEPENDENT arcs
  define cycle diagnostics; unresolved PEER/mixed semantics already remain REVIEW.
- Policy disagreements conservatively conflict even when concrete action-specific
  outcomes might eventually agree. No implicit priority or conflict resolution exists.
- Primary range must bind one base fragment. Multiple dependent fragments return one
  candidate with all fragment evidence and REVIEW; no pairing or relationship cloning.
- Base topology must match the snapshot projection; alternate origin-ID remapping is
  not resolved by this compiler. Native provenance remains caller-declared (OPEN-007).
- Existing fake relationship-bearing editing still rejects before mutation. INV-004,
  full INV-006 and production sync/rollback/editability are not certified by these tests.
- Chat-approved action-specific semantics and concrete identity/mapping contracts are
  prerequisites to any future lowering into executable actions (OPEN-001/005/006/007).


## TASK-006 candidate authority state scope

- Immutable in-memory state contracts only. No actual candidate timeline creation,
  duplication, Apply, postflight, observer, lock, notification, UI or persistence.
- Application/verification are caller-supplied fake evidence. IDs/version equality and
  frozen data cannot prove that native Apply/postflight happened or close TOCTOU races.
  Trusted producers and artifact binding remain OPEN-002/001, not adapter shortcuts.
- WorkingAuthority carries a fake timeline/version comparison input, not a production
  schema decision. Result identity is an opaque test token with an observed reference.
- Eligibility checks candidate-authority preconditions only. It does not run safety,
  dependency/topology preflight, protection checks or authorize real destructive edits.
- Whole-version mismatch is conservatively STALE; there is no region exemption, automatic
  rebase, optimistic merge, recomputation or stale->fresh transition. Human observations
  only concern the current authority; live observation/provenance is not implemented.
- Validity describes reuse of the original proposal base, not historical postflight.
  After promotion changes authority, the old proposal may be STALE while applied/verified/
  promoted history remains intact. Subsequent candidates need the explicit current base.
- Branches are same-source-base explorations. Branching from an applied result needs a
  separate future contract. No global candidate registry/retention/approval policy exists.
- Multiple concurrent approvals, revoke, DIRTY distinction, partial refresh and crash/restart
  lifecycle remain OPEN-008. WorkPhase is descriptive progress only, no execution gate.
- No production Human Edit Wins or rollback guarantee is claimed from simulated state tests.
