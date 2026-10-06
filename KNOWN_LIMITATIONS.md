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


## TASK-007 pause baseline scope

- All contextual features are caller observations; no media analysis or feature truth/provenance
  checks. HIGH is a deterministic rule label, not empirically calibrated model confidence.
- No snapshot binding: caller supplies already aligned single-placement frame ranges. Cross-clip,
  mixed-FPS, crosstalk and real identity mapping remain OPEN-009/001, never inferred here.
- Explicit removal signal can be accepted with unknown band/boundary, but explicit UNKNOWN
  signal vetoes proactive edits. Preserve/removal conflicts REVIEW, including breath/hesitation.
- Generic long pauses with unknown boundary preserve LOW; missing/unsafe local reference
  returns REVIEW. No target generation or clamp. Baseline emits only MEDIUM TIGHTEN.
- Candidate schema/routing can represent HIGH TIGHTEN, but no baseline rule emits it.
  SHADOW_ELIGIBLE is planning metadata only; no shadow creation or authority/apply permission.
- Public candidate values validate structural shape, not media truth or approved editing intent.
  All supplied evidence must be independently validated before any future executable plan.
- Dialogue restart/repetition/self-correction/filler remains product scope only; no dialogue
  classifier or deletion, UI, learned confidence or actual edit plan in this foundation.
- Synthetic rule tests do not establish real-world pause quality, false-removal rates or time saved.


## TASK-008 evaluation language / pure metric limits

- No collection, storage, live observers, dashboards, raw media, training or gate enforcement.
  Opaque identity/provenance is caller-supplied and cannot prove evidence authenticity.
  Feedback events never imply training consent or rewrite reference judgments.
- One case/proposal episode per log; contiguous sequence starts at 1 and finalization is
  terminal. Late-event/reopen/cross-proposal ordering and partial restore remain OPEN-010.
- Revert alone leaves final action unknown, while accepted_as_is is definitively false.
  Recovery flags stay visible even after later reaccept; no inferred post-revert KEEP.
- Final outcome requires terminal finalization and an explicit known decision. Restore is
  retained as a strong safety signal even before finalization, not erased by later edits.
- Timing needs explicit complete-kind coverage plus known durations for each required kind.
  Explicit zero records are valid; absent/None/partial coverage is not computable. Overlap
  detection, collector completeness, manual estimate calibration are not implemented.
- Paired savings requires explicit manual/assisted runs with same scope AND case set.
  No automatic pairing, estimation of missing baseline, or inference of independent work.
- Rates use exact Fraction. Critical false removal denominator is reference KEEP/REVIEW
  cases; reference/unknown counts are reported. Ambiguous supplied references are retained,
  not re-adjudicated or silently excluded. NEAR_RANGE/threshold policies remain undefined.
- Batches choose one proposal per case explicitly; no automatic latest-proposal selection.
  Finalized known outcomes define accepted-as-is denominator; unknown outcomes are separate.
- RUN_FINALIZED holds a supplied run reference. This in-memory layer has no global run/ID
  registry to prove references existed, compare changed payloads under reused IDs, or enforce
  append-only storage against external callers reconstructing values. Public raw types are
  evidence contracts, not persistence/security enforcement. No production metric accuracy claim.


## TASK-009 evidence / pure preparation limits

- Evidence is supplied descriptive metadata, not proof of truth, trust, calibrated probability,
  approval or apply permission. No actual producer/media decoding/network/telemetry is present.
- Strength is retained but never ranked or converted to editorial Confidence. All conflicting
  positive claims are visible; no priority, latest-wins or averaging. Real producer policy and
  calibration remain OPEN-009; missing required band/boundary/content and unknown claims review.
- Optional missing cue/reference records stay absent. ABSENT does not invent its opposite.
  Unknown local reference uses an UNKNOWN assertion on a typed value; missing reference needs
  no record. Nonpositive reference payloads reject; oversized positive references review.
- Constructor rejects malformed/mixed-binding/out-of-context/duplicate-ID bundles. Preparation
  reports conflicts and all applicable reasons for structurally valid bundles. Unsupported
  scope takes status precedence over stale, then review; stale reason is never lost.
- Target/context must fit one concrete fragment of the supplied immutable fake snapshot.
  No source conversion or native persistence proof; split-lineage spans and cross-placement
  inputs are not READY. The caller must supply already-aligned data and the current snapshot.
  A stale caller snapshot cannot be detected without a future live observer (out of scope).
- Context is explicit same-placement scope, not a pacing extractor or license to bind unrelated
  evidence. Crosstalk PRESENT requires review; cross-clip context requires unsupported handling.
- The public result value validates shape/binding; it is not a cryptographic attestation of
  derivation and cannot grant authority. No classifier/authority/executor integration.
- Producer algorithms/semantic quality and production native mapping remain unverified under
  OPEN-009 and OPEN-001/006. ADR-021 now resolves OPEN-011 v1 mapping semantics, but
  that implementation belongs to TASK-010 and is not started here. These synthetic tests
  make no real editing-quality claim.


## TASK-010 temporal mapping limits

- Mathematical correspondence is conditional on caller-supplied bindings and current
  snapshot. No Resolve truth, live freshness, state-token generation, native discovery or
  persistent identity is proven (OPEN-001/006/008/012). Object IDs remain fake lineage.
- Distinct SourceFrameRange/TimelineFrameRange wrap existing integer half-open FrameRange.
  Rational arithmetic stays inside the mapper; no global fractional time primitive.
  Rate canonicalization is exact gcd reduction, not temporal boundary rounding.
- Explicit IDENTITY_1X has equal span lengths; AFFINE_FORWARD slope comes from supplied
  spans, never FPS. FPS metadata is not physical retime validation or INV-007 certification.
- Reverse/freeze/variable/unknown kinds are representable descriptors but never lowered.
  FrameRange remains nonempty even for unsupported descriptor spans; this is not a complete
  production freeze/retime representation or sample-accurate audio model.
- Requests require placement AND media. Single-fragment containment resolves explicit
  fragments of that identity only; multiple containing bindings are AMBIGUOUS. Cross-fragment
  ranges never union. If no containing binding exists, multiple overlapping supplied spans
  conservatively report ambiguity; otherwise OUT_OF_RANGE, without clamp.
- Any relevant old-snapshot binding blocks as STALE, even alongside a fresh candidate.
  No latest-binding winner or scope-aware reuse. Unrelated identities are not selected.
- No supplied binding -> UNSUPPORTED; identity mismatch -> AMBIGUOUS. Duplicate references
  within requested placement/media candidates are AMBIGUOUS. No global ID registry exists.
- Only EXACT carries a complete source/timeline range pair and selected binding. Failures
  retain raw request/candidate/current-snapshot provenance, not a usable mapped output.
- Public values are data contracts, not authorization/security tokens. Even EXACT cannot
  bypass future ordinary Safety/Authority checks or create Evidence/StableTarget/EditPlan.
- No native SMPTE/drop-frame parsing, mapping inference, decoding, actual adapter, media
  intelligence, execution, storage/network/UI or TASK-011. Synthetic tests prove arithmetic
  and domain boundaries only; real Resolve correspondence awaits separate approved work.


## TASK-011 read-only snapshot / readiness limits

- Caller supplies identity scopes/bases, capability declarations, capture IDs, consistency
  evidence refs and state token. This domain validates their shape/coherence, not native
  truth, persistent continuity or live freshness (OPEN-001/006/008/012). No tokens generated.
- Explicit FILENAME_ONLY identity basis rejects. Opaque reference strings are not lexically
  classified as filenames; lying about NATIVE/ADAPTER_VERIFIED basis cannot be detected here.
  Snapshot-assigned identities cannot claim session/persistent lifetime. No fuzzy score.
- Known observations require SUPPORTED capability. SUPPORTED + explicit UNKNOWN is valid.
  Missing supported fields require PARTIAL, while explicit UNKNOWN can be structurally complete.
  A manifest's omitted capability reads UNKNOWN, never FALSE or implicitly SUPPORTED.
- Different capture IDs reject instead of joining old cached/new values. CONSISTENT needs a
  supplied evidence ref. This cannot prove that an adapter actually read everything atomically.
- PAUSE_ANALYSIS v1 is whole-snapshot input readiness, requiring all captured placements'
  identity/ranges/rates/retime and known track types, complete capture, consistency and current
  snapshot comparison. Unknown required fields fail closed; empty input requires review.
  It does not determine spoken content or exact mapping boundaries, or run pause analysis.
- Snapshot-local identities are usable only for this explicitly current captured analysis;
  readiness never promotes lifetime or grants cross-capture identity correspondence.
- Optional native observations are typed presence/state flags only; links/sync do not bind
  member graphs or imply move/delete together. No policy propagation or semantic track role.
- Profiles carry explicit ID/version, capability/scopes and requirements. Richer profiles
  cannot infer values from completeness. Only the conservative analysis profile is shipped;
  arbitrary caller profiles are metadata, not an approved destructive product contract.
- Multiple problems are preserved as issues. Status precedence: STALE, UNSUPPORTED,
  REVIEW_REQUIRED, UNVERIFIED, then READY. Snapshot data never changes during evaluation.
- Real native capture, capability discovery, time normalization, feature evidence, Safety,
  authority, observer/partial refresh, DB/network/UI and TASK-012 remain outside this task.
  Public result values are structural evidence records, not security/authorization tokens.
