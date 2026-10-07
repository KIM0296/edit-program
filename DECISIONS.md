# Architecture Decisions

# Accepted Decisions

## ADR-001 — Resolve is Source of Truth
Status: ACCEPTED

AI는 별도 authoritative timeline을 유지하지 않는다.

## ADR-002 — Frame Integer as Internal Time Primitive
Status: ACCEPTED FOR DOMAIN PROTOTYPE

초기 domain model은 float seconds보다 integer frame을 우선한다.
Drop-frame/timecode 표현은 별도 mapping layer에서 처리한다.

## ADR-003 — No Filename-only Media Identity
Status: ACCEPTED

Media identity는 filename 단독으로 결정하지 않는다.

## ADR-004 — Stale Plan Cannot Auto-Execute
Status: ACCEPTED

base timeline version과 current version이 다르면 destructive plan을 그대로 실행하지 않는다.

## ADR-005 — Safety Core Before Resolve Destructive Integration
Status: ACCEPTED

P0 domain tests 없이 destructive Resolve integration을 시작하지 않는다.

## ADR-006 — LLM Emits IR Only
Status: ACCEPTED

LLM이 Python/Lua/Resolve scripting code를 직접 실행 경로에 생성하지 않는다.

---

## ADR-007 — Main Repository and Product-first Development
Status: ACCEPTED — 사용자 지시, 2026-10-05

이 저장소를 메인 제품으로 삼고 기존 영상 편집자동화 시스템연구는 재사용 자산/검증 사례로 보존한다. 제품은 Mac 전용이 아니며 Windows는 현재 개발 환경이다. OS별 설치·권한·연결 검증은 핵심 구축 후 마무리 단계에 수행한다. 기존 Safety Core 경로를 유지하며 이번 결정은 invariant 완화나 실제 API 검증 생략을 뜻하지 않는다. 비교 결과: (historical review artifact is not present in this repository).

## ADR-008 - Integer Half-open Internal FrameRange
Status: ACCEPTED - Chat Gate Review, 2026-10-05

All internal FrameRange values use integer half-open [start, end) coordinates.

## ADR-009 - Version Advances on Successful Plan Commit
Status: ACCEPTED - Chat Gate Review, 2026-10-05

TimelineVersion increases by one per successfully committed EditPlan/Transaction,
not per command. Failure or rollback does not increase it. An empty fake plan is
an uncommitted no-op. This decision does not authorize transaction/rollback implementation.

## ADR-010 - TASK-002 ProtectedRange Is HARD_LOCK
Status: ACCEPTED - Chat Gate Review, 2026-10-05

Direct edits and ripple-induced absolute timeline position changes are violations.
Reject the entire offending plan before mutation. No override is provided in TASK-002.

## ADR-011 - Unrequested Content Preservation
Status: ACCEPTED - Chat Gate Review, 2026-10-05

INV-002 preserves unrequested media identity, source range, and content order.
Timeline positions may change only by ripple displacement explicitly approved in EditPlan.

## ADR-012 - Fake Placement Lineage Identity
Status: ACCEPTED - Chat Gate Review, 2026-10-05

TASK-001 FakeTimeline clip_id is fake placement lineage identity, not a production
persistent TimelineItem ID. Resolve persistent identity remains OPEN-001.



## ADR-013 - Relationship Execution Semantics v1
Status: ACCEPTED - Chat Architecture Review, 2026-10-05

Relationship data is descriptive, not directly executable. A relationship never by itself
means "move together", "trim together", "delete together", or "retime together".

Execution is action-specific. Relationship handling must be compiled as:
Relationship × Edit Action → expected dependent actions → conflict detection → Safety Preflight.
Do not implement relationship propagation as recursive side effects.

Member roles use explicit semantics when execution is introduced:
- PEER: symmetric participant; no leader/follower inference.
- DRIVER: primary object whose edit may affect dependents.
- DEPENDENT: object whose expected response is evaluated from the driver/action.
Member tuple order has no semantic authority.

Initial safety rules:
1. AV_LINK and SYNC_GROUP do not imply identical boundaries or identical movement.
2. Preserve existing A/V relative sync and intentional J/L-cut structure; do not normalize
   audio/video start/end boundaries merely because objects are related.
3. DELETE does not cascade automatically from DRIVER to DEPENDENT.
4. SPLIT/DELETE/RETIME require concrete fragment rebinding or REVIEW; lineage alone is not
   sufficient execution authority when fragment correspondence is ambiguous.
5. Conflicting relationship outcomes for one object escalate to REVIEW. Do not hide conflict
   behind implicit priority.
6. Cycles are never executed recursively. Resolve the relationship closure against the base
   snapshot, produce one finite expected-action set, detect cycles/conflicts, then either
   validate the compiled plan or REVIEW.
7. Unknown/unsupported relationship behavior defaults to REVIEW, not APPLY.

These are v1 safety defaults. They may be extended when Resolve/native evidence or real
editorial cases justify it, but changes require Chat Architecture Review and must not weaken
existing invariants silently.




## ADR-014 - Track Stewardship v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-05

The timeline's existing track organization is user-owned project structure. AI may edit content
within that structure, but must not silently reorganize the editor's workspace.

Safety/product defaults:
1. Existing Structure Is User-Owned: do not delete, rename, reorder, repurpose, or silently
   move objects across existing tracks without an explicit approved topology change.
2. Reuse Before Create, But Only When Safe: reuse an existing track only when its role is
   sufficiently established and the planned placement is conflict-free. Ambiguous tracks are
   not AI-owned free space.
3. Empty Does Not Mean Disposable: an empty track may be intentional staging/organization and
   must not be deleted merely because it is empty.
4. AI-Created Becomes User-Owned: once an AI-created track/object enters the editable project,
   it becomes ordinary user project state. Later AI work may not reset or remove it merely
   because AI originally created it. Human edits take precedence.
5. Explicit Selection Is Strong Intent, Not a Safety Bypass: a user-selected target track is a
   strong placement signal, but lock/protection/topology/relationship checks still apply.
6. Track Creation Is a Topology Change: creating, deleting, reordering, renaming/repurposing,
   or moving membership across tracks must be represented as an expected topology change.
7. Stacking Ambiguity Escalates to REVIEW: when the visual/audio result depends on layer order
   and a safe insertion position cannot be determined, do not guess.

These are v1 conservative defaults. Real Resolve metadata and professional workflow evidence may
justify future refinement, but any change requires Chat Product/Architecture Review and must not
silently weaken Preserve Editability or INV-019.

Track semantic roles (for example MAIN_VIDEO/BROLL/GRAPHICS/DIALOGUE/BGM/SFX/SUBTITLE) are a
future architecture topic. Track names or ordinal positions alone are not authoritative role data.



## ADR-015 - Candidate Authority Contract v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-05

Candidate selection, approval, application, verification, and promotion are distinct states.

1. Selection Is Not Approval: selecting a candidate only chooses it for comparison or further edits.
2. Approval Is Not Promotion: approval grants permission to attempt application; it does not change
   the authoritative working timeline by itself.
3. Promotion Requires Verified Apply: only a successfully applied and postflight-verified result may
   become the default working authority for subsequent requests.
4. Every Candidate Carries Its Base: every candidate records the source timeline identity/version
   from which it was derived.
5. Human Edit Wins / Stale Candidate Reject: if Resolve changes after candidate creation, do not
   apply the stale candidate unchanged.
6. No Automatic Destructive Rebase: stale candidates must be recomputed/reviewed; never silently
   merge an old candidate over newer human edits.
7. Candidate Branching Does Not Change Main: candidate A/B/B2 exploration does not change working
   authority until verified promotion.
8. Ambiguous Praise Is Not Approval: positive evaluation is not equivalent to an explicit apply.
9. Active Timeline Is Not Automatically Working Authority: merely viewing/selecting another Resolve
   timeline does not silently move the working pointer.
10. Next Request Defaults to Latest Verified Working Timeline after successful promotion.

Implementation details for whether candidates are native duplicated timelines, virtual plans, or
rendered previews remain separate decisions. Resolve remains the Source of Truth.

## ADR-016 - Parallel Editing / Human Priority v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-05

AI work should not block the editor by default. Analysis and candidate generation happen against an
immutable base snapshot/shadow candidate rather than writing directly into the authoritative working
state.

1. Parallel Editing Principle: editor and AI may work concurrently when changes are isolated.
2. Human Priority Principle: human changes always take precedence over in-flight AI candidates.
3. Shadow Candidate Principle: analysis/candidate building does not mutate the authoritative working
   timeline.
4. Minimal Commit Lock: exclusive write coordination, when required, is limited to the smallest
   affected scope and shortest commit/verification window practical.
5. No Silent Rebase: an AI candidate invalidated by human work must be marked dirty/stale and
   recomputed or reviewed rather than silently reapplied.

Future Concurrent Work Coordinator responsibilities may include AI work scope, human-change
detection, staleness, conflict classification, dependency impact, incremental recomputation and
commit coordination. A soft work lease may communicate AI scope but must not prevent the human from
editing; human edits invalidate/recompute AI work instead.

These are conservative v1 product/architecture rules. Changes require Chat review.




## ADR-017 - Effect / VFX Product Boundary v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-05

Effect automation is scoped by editorial responsibility, complexity, editability and
verifiability, not by which application or page can technically perform the work.

1. Editorial Effects are Core Scope: normal NLE-level transforms, simple punch-ins,
   basic blur/transitions/speed/audio fades/subtitle styling/basic titles and similar
   editor-owned effects may become directly supported after normal safety validation.
2. Controlled Motion / Simple Composite is Limited Scope: lower thirds, tracked text,
   simple masks/object blur/screen replacement and similar work should use validated
   primitives/templates rather than unrestricted free-form graph generation.
3. Fusion Preferred, Not Required: for Resolve-centered motion/tracking/simple composite,
   Fusion is the preferred implementation path when it preserves the native workflow,
   but it is not a hard dependency or universal requirement.
4. Preserve Effect Editability: committed effects should remain native, inspectable,
   reversible and editable whenever reasonably possible; rendered/flattened substitutes
   must not silently replace editable project state.
5. Existing Effect Structure Is User-Owned: existing effects, nodes, keyframes and graph
   organization are not AI-owned scratch space and must not be silently rewritten.
6. No Unrestricted Free-form Fusion Automation Initially: early automation must pass
   through validated primitives/templates and bounded parameter contracts.
7. Complexity Escalates to VFX Handoff: when outcome verification, reversibility,
   inspectability or editability become weak, prefer VFX Assist/Handoff over direct automation.
8. Color, Audio and Generative Asset Creation are separate verticals and are not silently
   absorbed into this Effect/VFX contract.

Effect Automation Eligibility is judged by:
Predictable + Reversible + Inspectable + Editable + Verifiable.
As these qualities weaken, behavior moves from AUTO-ELIGIBLE to REVIEW-REQUIRED to HANDOFF.

Initial scope explicitly excludes unrestricted Effect ALL Auto. Do not build a system that
freely chooses and applies arbitrary effects across the project merely because the effects
are technically possible. First validate individual E1/E2 primitives for real time savings,
editability and correction cost. A future validated Effect Auto Pass may be reconsidered
only over an approved bounded primitive set and only if evidence shows favorable net time saved.




## ADR-018 - Pause / Dialogue Editing v1 Product Contract
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-06

The first editing vertical targets spoken-content pacing and dialogue cleanup, not generic
silence removal or story restructuring.

1. Pause decisions use KEEP / TIGHTEN / REMOVE / REVIEW.
2. Absolute silence duration is evidence, never the sole decision rule.
3. TIGHTEN is the primary proactive edit for natural speech pacing.
4. REMOVE is reserved for high-confidence meaningless recording gaps/dead air.
5. The cost of a false removal is treated as higher than the cost of a false keep.
6. Immediate restart, short repetition, and obvious self-correction are in v1 scope.
7. Long-range semantic redundancy is not auto-deleted in v1.
8. Filler removal is conservative and context-sensitive; natural speech texture may remain.
9. Product-level confidence bands are HIGH / MEDIUM / LOW.
10. HIGH confidence may auto-populate a Shadow Candidate but never silently mutate Main.
11. MEDIUM confidence goes to batched review rather than interrupting the editor immediately.
12. Audio + transcript/dialogue structure are the primary v1 evidence sources; visual context
    is optional supporting evidence and is not required for the first implementation.
13. Initial supported content focuses on interview, talking-head, podcast, lecture and similar
    spoken-content workflows; narrative/drama/music-video pacing is outside the first vertical.
14. Success is measured by net time saved, human active/review/correction time, accepted
    suggestions, reverted edits, and especially false removal of necessary pauses.
15. Compression ratio or total duration reduction is not a quality metric.

The first implementation must not introduce STT, VAD, prosody models, LLM reasoning, actual
timeline mutation, or a learned classifier. TASK-007 starts with immutable Pause Candidate
domain/schema and a deterministic, conservative rule baseline over caller-supplied observations.




## ADR-019 - Evaluation Data Contract & Feedback Event Schema v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-06

Pause Intelligence evaluation uses immutable raw records/events first and derives metrics second.
Benchmark reference judgments and real product feedback are separate evidence classes.

Core rules:
1. Raw Events First, Derived Metrics Second. Store proposal/reference/final-decision/feedback/timing
   evidence so metric formulas may be recomputed later.
2. BENCHMARK, PILOT and PRODUCT_FEEDBACK are distinct source kinds.
3. Product feedback never rewrites benchmark reference judgments automatically.
4. AI proposal snapshots are immutable. Recalculation creates a new proposal.
5. Feedback is append-only and ordered by explicit sequence number, not wall-clock timestamp alone.
6. User final outcome, correction classes and metric snapshots are derived state, never more
   authoritative than their raw source events.
7. REMOVE restore/revert is a distinct safety signal from an ordinary correction.
8. Missing timing evidence is unknown, never silently interpreted as zero.
9. Producer version, decision contract version, feature contract version and metric-definition
   version must be explicit enough to compare generations reproducibly.
10. Product-feedback core schema must not require storing raw video/audio/full transcripts,
    project names, filenames or user identity; prefer opaque references plus decision/event metadata.
11. Feedback capture does not imply training consent or authorization.
12. Numerical release thresholds are not embedded in evaluation records. GatePolicy is a separate,
    versioned policy defined only after pilot evidence exists.
13. Net Time Saved is based on human cost: instruction + review + correction + manual completion +
    recovery, plus AI-blocked idle only when AI actually prevented useful parallel work.
14. Decision Interruptions count actual attention requests/batches, not the number of review items.
15. Evaluation schema is model-agnostic and must support deterministic rules, future VAD/STT/prosody/
    semantic/LLM producers under the same comparison contract.

TASK-008 may implement immutable schema, pure validation, pure final-outcome derivation and pure metric
derivation only. It must not add DB/storage, telemetry collection, Resolve listeners, cloud upload,
dashboard, model training, personalization updates, raw-media capture, automatic gate enforcement or
numeric thresholds.




## ADR-020 - Observation Evidence & Producer Provenance Contract v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-06

Future media-intelligence producers must communicate through immutable, typed, snapshot-bound
evidence rather than directly authoring editorial decisions or executable commands.

Core rules:
1. Evidence is descriptive, never apply/approval/authority permission.
2. Producer evidence strength and PauseCandidate editorial confidence are separate types with no
   implicit conversion.
3. Every evidence record carries producer kind/name/version/evidence-contract provenance.
4. Every record is bound to timeline ID, base version, placement identity and observed range.
5. Evidence from different timeline/version/placement identities is not silently merged into one
   READY PauseObservation in v1.
6. Explicit evidence assertions are PRESENT / ABSENT / UNKNOWN. Missing means no record and is not
   equivalent to ABSENT or UNKNOWN.
7. ABSENT does not imply the opposite positive cue. Silence/duration does not imply dead air.
8. Conflicting producer evidence remains visible; no latest-wins, hidden producer priority or
   confidence arithmetic.
9. Stale evidence is never silently rebased after human timeline changes.
10. v1 supports already-aligned single-placement internal FrameRange evidence only. Native
    timecode/FPS/drop-frame/mixed-FPS mapping is deferred.
11. Cross-clip/multi-placement and unresolved crosstalk cases fail closed to REVIEW_REQUIRED or
    UNSUPPORTED.
12. Pure preparation may create an existing PauseObservation only from explicit, supported,
    non-conflicting typed evidence. It does not execute the classifier or timeline mutation.
13. Raw media, full transcripts, filenames/project names and user identity are not required in the
    core evidence domain.
14. TASK-009 implements immutable evidence/provenance/bundle/conflict/preparation only; no actual
    VAD/STT/diarization/prosody/semantic inference or Resolve media extraction.

Detailed contract: docs/OBSERVATION_EVIDENCE_CONTRACT.md.



## ADR-021 - Native Time & Snapshot Mapping Contract v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-06

Native/source/timeline time must be mapped through explicit snapshot-bound placement correspondence;
it must never be guessed from filenames, similar timecodes, frame-rate ratios or float seconds.

Core rules:
1. TIMELINE_FRAME and SOURCE_FRAME are distinct coordinate domains.
2. Internal project ranges remain integer half-open FrameRange values (ADR-008).
3. Frame-rate metadata is exact rational; 30000/1001 is not 30/1. Drop-frame labeling is separate
   from actual frame cadence.
4. Frame-rate metadata alone never proves source↔timeline placement mapping.
5. Mapping is bound to timeline ID, product timeline version, opaque native state token, placement
   identity, media identity and explicit source/timeline spans.
6. Snapshot mismatch is STALE in v1. No silent rebase or scope-aware reuse.
7. Mixed FPS is not globally prohibited. An explicit mapping may return EXACT only when both requested
   boundaries land exactly on integer internal frames.
8. A mathematically non-integral frame boundary returns NON_INTEGRAL. Never round/floor/ceil.
9. OUT_OF_RANGE is not clamped and ambiguous placement correspondence is not guessed.
10. TASK-010 pure lowering supports IDENTITY_1X and explicit AFFINE_FORWARD only.
    REVERSE/FREEZE/VARIABLE_RETIME/UNKNOWN remain UNSUPPORTED in v1.
11. Mapping EXACT proves temporal correspondence only; it is not edit approval, Safety clearance or
    Candidate Authority.
12. Cross-placement ranges are not collapsed into one SourceRange for ADR-020 single-placement
    evidence.
13. Production persistent identity and native track/object correspondence remain OPEN-001/OPEN-006.
14. Sub-frame/rational time is not introduced as the system-wide domain primitive in v1. If real
    audio/sample-accurate use proves integer frames insufficient, that requires a separate ADR.

Detailed contract: docs/NATIVE_TIME_SNAPSHOT_MAPPING.md.



## ADR-022 - Read-only Resolve Snapshot & Adapter Observation Contract v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-06

Resolve remains Source of Truth. A Resolve snapshot is an immutable, read-only observation of native
state and never an independently authoritative timeline.

Core rules:
1. Snapshot capture is read-only; mutation belongs to later Safety/Authority-controlled paths.
2. Identity lifetime is explicit and categorical: PERSISTENT_VERIFIED,
   SESSION_LOCAL_VERIFIED, SNAPSHOT_LOCAL, UNKNOWN. Identity is never a confidence probability.
3. Adapter capability and per-capture observed value are separate axes. SUPPORTED/UNSUPPORTED/UNKNOWN
   capability must not be conflated with TRUE/FALSE/UNKNOWN observed state.
4. Unsupported or unknown capability never becomes a false negative observation.
5. Capture consistency is CONSISTENT / UNSTABLE / UNVERIFIED. UNVERIFIED is never assumed stable.
6. state_token is an opaque mapping-relevant state identity, not a security token and not necessarily
   a Resolve-native token. If a trustworthy token cannot be produced, the adapter must expose that
   limitation rather than fabricate one.
7. Snapshot completeness describes structural capture against declared capabilities only. It does
   not imply feature safety/readiness.
8. Feature readiness is evaluated separately against an explicit FeatureRequirementProfile.
9. Snapshot READY means sufficient observation evidence for that feature, not Apply/Approval/Safety
   authorization.
10. Timeline/track/placement/media names, filenames and native ordinals are descriptive metadata,
    not persistent identity or semantic roles.
11. Media identity and placement identity remain separate. Same media may have multiple placements.
12. UNKNOWN retime is not assumed IDENTITY_1X. Native time normalization must follow ADR-021.
13. Partial/unstable/unverified captures remain visible; stale/new observations are not silently
    mixed into one current snapshot.
14. Native relationship/effect/transition/track-state observations are descriptive and
    capability-based; absence of capability is not absence of structure.
15. Persistent identity, native correspondence and scope-aware invalidation remain OPEN-001,
    OPEN-006 and OPEN-008 until runtime evidence resolves them.

Detailed contract: docs/READ_ONLY_RESOLVE_SNAPSHOT_CONTRACT.md.



## ADR-023 - Pause Edit Planning & Safety Lowering Contract v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-06

Pause editorial decisions must not be lowered directly into executable timeline commands.

Core rules:
1. A Pause decision specifies editorial intent, not cut geometry.
2. TIGHTEN may not be lowered until exact retained/removed temporal geometry is explicitly resolved.
3. PlanningDisposition and SafetyDisposition are separate; READY_FOR_PREFLIGHT is not Safety PASS.
4. KEEP -> NO_OP and REVIEW -> REVIEW_ONLY; neither creates a destructive plan.
5. TIGHTEN v1 supports exactly one contiguous removed range.
6. TIGHTEN geometry must be contained in the original pause and its removed duration must exactly
   equal original duration minus candidate retained frames. Do not clamp/repair mismatches.
7. REMOVE also uses a separate explicit geometry artifact; v1 full-pause removal geometry removes
   exactly the pause and retains zero frames.
8. TASK-012 is a geometry consumer only. Caller-supplied geometry is structurally/binding validated
   but not inferred from audio, prosody, semantics or candidate confidence.
9. Geometry production belongs to a separate future Cut Geometry Resolution Contract.
10. Candidate confidence never bypasses current target, exact mapping, geometry, dependency or Safety.
11. Planner consumes already-computed mapping/snapshot/dependency readiness and does not reimplement
    those layers or invoke them as side effects.
12. Ripple mechanics are not inferred directly from TIGHTEN/REMOVE; expected displacement must be
    explicit in later plan compilation/Safety.
13. Relationship membership never implies automatic delete/trim/move propagation; ADR-013 remains
    authoritative.
14. Human edits invalidate stale candidate/geometry/dependency artifacts; no silent rebase.
15. Planner output remains immutable descriptive proposal data, not Approval/Apply authority.

Detailed contract: docs/PAUSE_EDIT_PLANNING_CONTRACT.md.



## ADR-024 - Cut Geometry Resolution Contract v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-06

TIGHTEN cut location is resolved from explicit typed geometry constraints, never from retained
duration alone.

Core rules:
1. v1 constraint vocabulary is exactly CUT_START_ANCHOR, CUT_END_ANCHOR,
   MUST_PRESERVE_RANGE and ALLOWED_REMOVAL_RANGE.
2. GeometryConfidence is a separate typed value (STRONG/MODERATE/WEAK/UNKNOWN) supplied by the
   producer and preserved by the resolver.
3. The resolver does not derive/calibrate GeometryConfidence from EvidenceStrength, PauseCandidate
   Confidence, producer kind, agreement count or other metadata.
4. GeometryConfidence never ranks competing valid candidates.
5. Retained duration determines how much to remove, never where to remove it.
6. Exact/current internal-frame mapping must precede geometry resolution; the resolver does not call
   or reimplement native mapping.
7. TIGHTEN v1 resolves exactly one contiguous removed range.
8. Candidate production paths are limited to explicit geometry and exact explicit start/end anchor
   pairs.
9. MUST_PRESERVE_RANGE invalidates overlapping removal candidates; the resolver does not shift them.
10. ALLOWED_REMOVAL_RANGE is optional; when multiple applicable allowed ranges exist, v1 uses
    conservative intersection semantics.
11. Equal geometric ranges supported by multiple producers count as one distinct geometry only if
    all provenance/support is retained.
12. Resolution rule: 0 distinct valid geometries -> UNRESOLVED; 1 -> RESOLVED; 2+ ->
    REVIEW_REQUIRED.
13. No latest-wins, hidden ranking, center/leading/trailing defaults or nearest-anchor repair.
14. Geometry resolution does not change KEEP/TIGHTEN/REMOVE editorial action.
15. Geometry does not decide ripple mechanics, seam treatment, Safety, Approval or Apply authority.
16. TASK-013 is pure immutable foundation only; no audio/VAD/STT/prosody/LLM/media inference.

Detailed contract: docs/CUT_GEOMETRY_RESOLUTION_CONTRACT.md.



## ADR-025 - Expected Diff & Temporal Displacement Contract v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-06

Pause gap closure must be represented as explicit expected state changes before Safety or execution.

Core rules:
1. Primary range removal and collateral temporal displacement are separate change classes.
2. Unlisted Object Invariance applies inside an explicit PreservationScope.
3. A ripple boolean, all-downstream token or similar symbolic instruction is insufficient for
   Safety-ready planning.
4. Concrete displacement participants must be explicitly enumerated.
5. ExpectedDiff Compiler consumes a precomputed DisplacementParticipationAssessment and does not
   select participants itself.
6. v1 supported participants are pure translations fully downstream of the removed interval.
7. Every v1 participant uses uniform integer delta = -removed_duration; uniformity never selects who
   participates.
8. Crossing objects, nonuniform displacement and unresolved gap interaction are non-ready/unsupported.
9. Pure displacement preserves placement/media/source identity, duration and track membership.
10. ExpectedDiff completeness and Safety acceptability are separate. A fully described consequence
    may be READY_FOR_PREFLIGHT even when a later Safety rule will reject it.
11. Expected topology change is empty by default for Pause v1.
12. Human edits stale ExpectedDiff; no silent rebase.
13. Within PreservationScope, an object absent from ExpectedDiff is expected unchanged.
14. Expected-vs-Actual verification uses exact integer-frame equality; no implicit tolerance.
15. Extra, missing or wrong actual changes are mismatch.
16. UNVERIFIED is not MATCH.
17. Verified promotion requires Expected Diff = Actual Diff under ADR-015/INV-016.
18. TASK-014 is pure foundation only; no participant policy, Resolve mutation, Safety verdict or
    actual postflight capture.

Detailed contract: docs/EXPECTED_DIFF_TEMPORAL_DISPLACEMENT_CONTRACT.md.



## ADR-026 - Safety Preflight Integration Contract v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-06

Safety Preflight validates an already specified ExpectedDiff against current safety evidence; it
does not invent, repair or optimize the edit.

Core rules:
1. PreflightStatus and SafetyVerdict are separate axes.
2. Status precedence is STALE > UNSUPPORTED > INCOMPLETE > EVALUATED.
3. SafetyVerdict exists only for EVALUATED and uses REJECT > REVIEW_REQUIRED > PASS.
4. Unknown/missing mandatory safety state reduces autonomy and never defaults safe.
5. All evaluable findings are retained; no diagnostic short-circuit.
6. PAUSE_DESTRUCTIVE_PREFLIGHT_V1 has exactly 17 mandatory checks.
7. PASS requires every mandatory check to be evaluated.
8. ExpectedDiff completeness and Safety acceptability remain separate.
9. Safety consumes consequences and never repairs/replans them.
10. Protected direct change/displacement and locked-track mutation are hard rejects.
11. Unsupported retime/topology is UNSUPPORTED, not silently REVIEW/PASS.
12. Pure displacement must preserve media identity, source range, duration and track membership.
13. Transition/effect/keyframe states distinguish absent, unknown, present-without-proof,
    PRESERVATION_PROVEN and explicit violation.
14. Known transition/effect/keyframe presence may PASS only with a valid typed PreservationProof.
15. Known presence without proof yields REVIEW_REQUIRED; unknown yields INCOMPLETE; explicit
    violation yields REJECT.
16. Safety consumes PreservationProof but does not generate it.
17. Safety PASS is bound to exact ExpectedDiff, snapshot, profile, protection context and proofs.
18. Human edits or relevant safety-context changes invalidate prior PASS.
19. No generic v1 hard-safety override.
20. Safety PASS is not Approval, Apply, Verified Apply or Promotion.

Detailed contract: docs/SAFETY_PREFLIGHT_INTEGRATION_CONTRACT.md.



## ADR-027 - Execution Transaction & Postflight Verification Contract v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-07

Destructive execution is successful only after the exact authorized state transition has been
postflight-verified against Resolve-observed state.

Core rules:
1. Product commit point is after postflight MATCH, never after native mutation calls merely return.
2. Safety PASS is not execution authorization; authorization binds exact ExpectedDiff, Safety result,
   base snapshot and approval reference.
3. Precommit currentness is mandatory and human edits win over pending AI execution.
4. TransactionPhase and TransactionOutcome are separate axes.
5. VERIFIED_COMMITTED is the only successful destructive outcome.
6. Partial mutation is never committed success.
7. ExecutionStepStatus includes OUTCOME_UNKNOWN as a first-class state.
8. Blind retry after uncertain mutation response is forbidden; fresh state reconciliation comes first.
9. Executor self-report/native return values are not postflight truth.
10. Fresh post-apply observation and ExpectedDiff == ActualDiff MATCH are mandatory for commit.
11. UNVERIFIED/MISMATCH/STALE postflight cannot commit or promote.
12. Rollback capability is never assumed.
13. RollbackCapability and RollbackPolicy are separate; auto rollback may be eligible only when
    capability is SUPPORTED_VERIFIED and policy allows it.
14. Rollback command success is insufficient; recovery requires fresh-state verification against base.
15. Failed edit + verified recovery remains a failed edit, not success.
16. Unrecovered partial/postflight failure triggers destructive AI recovery-required lockdown.
17. Promotion requires current authorization, current Safety PASS, VERIFIED_COMMITTED, postflight
    MATCH and no recovery-required state.
18. Stable targets are resolved against the authorized base; no mid-transaction re-resolution by
    shifted timeline position.
19. Destructive commands are not assumed idempotent.
20. LLM-generated native script/code is never executed directly.

Detailed contract: docs/EXECUTION_TRANSACTION_POSTFLIGHT_CONTRACT.md.



## ADR-028 - Validated Execution IR & Resolve Executor Boundary Contract v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-07

The Resolve Executor is a deterministic actuator, not an editor. It may cause only effects already
present in the exact authorized ExpectedDiff and validated through bounded logical IR.

Core rules:
1. Pause v1 logical IR vocabulary is exactly REMOVE_RANGE and TRANSLATE_PLACEMENT.
2. Generic ripple/participant-expanding opcodes are forbidden.
3. Every ExpectedDiff effect must be covered exactly once; missing, extra or duplicate effects are invalid.
4. Native fusion requires SUPPORTED_VERIFIED capability plus a current VERIFIED NativeEffectModel.
5. Predicted native effects must equal ExpectedDiff effects exactly; do not expand ExpectedDiff to
   accommodate native side effects.
6. Execution identity is stronger than observation identity.
7. PERSISTENT_VERIFIED is execution eligible.
8. SESSION_LOCAL_VERIFIED is conditional on same-session mutation stability and postflight
   correspondence proof.
9. SNAPSHOT_LOCAL is unsupported for destructive v1 target authority; UNKNOWN is incomplete.
10. Target ambiguity never resolves by first match or name/position/media heuristics.
11. Domain identity and native locator are separate.
12. Every destructive native step requires verified post-read and a verified reconciliation path
    before execution begins.
13. Fragment-producing decomposition requires verified intermediate fragment rebinding.
14. Capability UNKNOWN/SUPPORTED_UNVERIFIED never becomes destructive support.
15. Runtime/profile changes stale capability/effect evidence.
16. Runtime fallback requires a new lowering plan and revalidation.
17. Adapter/executor never repairs geometry, participant set, tracks, source ranges or Safety failures.
18. Rollback capability/policy is separate from semantic lowering readiness.
19. READY_FOR_EXECUTION means semantic/native readiness only, not apply/commit/promotion.
20. Executor does not declare commit or rollback verification; ADR-027 remains authoritative.

Detailed contract: docs/VALIDATED_EXECUTION_IR_CONTRACT.md.



## ADR-029 - Native Capability Probe & Effect Model Evidence Contract v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-07

Execution-grade native capability must be earned from isolated, repeatable and independently observed
runtime evidence, not from API presence or return codes.

Core rules:
1. Destructive capability probes never run on the authoritative production/working timeline.
2. Destructive probes use isolated disposable canonical fixtures whose pre-state is verified.
3. One successful probe cannot create SUPPORTED_VERIFIED or VERIFIED NativeEffectModel.
4. Repeatability is mandatory for destructive verification.
5. Probe observation scope must be COMPLETE to support VERIFIED destructive semantics.
6. PARTIAL/UNKNOWN observation scope cannot produce VERIFIED.
7. Actual observed side effects are retained even when they contradict the probe hypothesis.
8. Conflicting qualifying evidence is CONFLICTING; no latest-wins, majority-vote or hidden ranking.
9. Any qualifying semantic conflict blocks destructive VERIFIED eligibility.
10. Evidence/model derivation is bound to exact RuntimeProfile and versioned invocation/observation
    contracts.
11. API/method existence and native success booleans are provenance only, not semantic proof.
12. Post-read, reconciliation, identity and fragment-correspondence capabilities are independently
    evidenced.
13. IdentityScope is not upgraded from identifier shape alone.
14. Fragment correspondence never uses order/name/position heuristics without verified evidence.
15. Qualifying runs should start from independently clean canonical fixture state.
16. Probe evidence is immutable; later interpretation creates new derived artifacts.
17. Relevant Resolve/adapter/platform/contract changes stale evidence/model applicability.
18. Capability probes verify native behavior, not editorial quality.

Detailed contract: docs/NATIVE_CAPABILITY_PROBE_EVIDENCE_CONTRACT.md.



## ADR-030 - Capability Verification Policy & Challenge Matrix v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-07

1. TRANSLATE_PLACEMENT requires 4 positive fixture classes × 5 independent clean runs = 20 minimum positive runs.
2. REMOVE_RANGE requires 6 positive fixture classes × 5 runs = 30 minimum positive runs.
3. COMPOUND_RIPPLE requires 10 positive fixture classes × 5 runs = 50 minimum positive runs.
4. Applicable mandatory challenge classes require 3 additional clean runs each.
5. COMPLETE observation scope is mandatory.
6. Semantic conflicts, unexpected side effects, containment failures and ambiguous targets each have allowed count 0.
7. Post-read and reconciliation must be VERIFIED and identity must be execution eligible.
8. Verification is deterministic contract validation; 19/20 does not qualify.
9. NativeEffectModel uses an explicit ApplicabilityDomain. Conflict inside the declared domain is CONFLICTING; outside-domain behavior remains UNSUPPORTED until separately verified.
10. Applicability may not be narrowed after a failing qualifying run merely to hide conflict.
11. VERIFIED profile evidence is reusable until stale; full probe suites are not repeated per project/edit.
12. Ordinary production editors perform no manual capability-probe work.
13. SUPPORTED_VERIFIED proves native semantics only and does not itself authorize auto-apply.

Detailed policy: docs/CAPABILITY_VERIFICATION_POLICY.md.



## ADR-031 - Resolve Probe Harness & Fixture Lifecycle Contract v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-07

1. Qualifying destructive probes run only in dedicated registered disposable probe projects.
2. A duplicated timeline inside a user working project is insufficient isolation for v1.
3. One qualifying run uses one fresh fixture instance and permits at most one invocation attempt.
4. Fixture reset uses canonical reconstruction, not assumed Undo.
5. Only CLEAN_VERIFIED fixtures may be armed.
6. DIRTY or QUARANTINED fixtures are discarded/rebuilt rather than repair-and-continue.
7. QUALIFYING and EXPLORATORY probe modes are distinct; exploratory success does not directly count
   toward verification budgets.
8. Observation scope is fixed before invocation and pre/post observation schemas are symmetric.
9. Containment failure or project contamination stops further qualifying mutation in that
   fixture/project generation.
10. Environment/currentness is revalidated immediately before invocation.
11. Native timeout/uncertainty does not trigger blind retry in the same run.
12. Crash during/after invocation quarantines the fixture.
13. Mutated fixture instances are discarded after evidence sealing regardless of pass/fail.
14. Probe evidence remains immutable independently of fixture disposal.
15. Full verification suites never run implicitly in ordinary production editing.

Detailed contract: docs/RESOLVE_PROBE_HARNESS_FIXTURE_LIFECYCLE.md.


## ADR-032 - Read-only Probe Adapter & Fixture Materialization Contract v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-07

1. Probe Environment Controller, Fixture Materializer, Read-only Probe Adapter and Native Probe Invoker are separate responsibilities.
2. Read-only Adapter has no generic native execute/eval/script surface and never repairs fixture state.
3. v1 materialization is template-first using a versioned content-hashed project template plus content-hashed canonical test assets.
4. Materializer return success never proves fixture correctness; independent read-only canonical MATCH is required for CLEAN_VERIFIED.
5. Verification mismatch is discarded/rebuilt rather than repaired-and-qualified in place.
6. Canonical fixture identity is semantic and separate from generated native object identity.
7. FixtureRoleBinding is explicit and ambiguous binding fails closed.
8. Filename alone is never asset/object identity.
9. Required read observations are explicit and fixture-class dependent; missing is INCOMPLETE and known wrong state is MISMATCH.
10. Capture consistency is explicitly fenced; unstable capture is non-qualifying.
11. Read stability is qualified before destructive mutation probing.
12. Integration order is Read-only Adapter -> Fixture Materializer -> Read Stability -> Native Mutation Probe.
13. Actual Resolve API support is discovered for the exact installed RuntimeProfile, not assumed.

Detailed contract: docs/READ_ONLY_PROBE_ADAPTER_FIXTURE_MATERIALIZATION.md.


## ADR-033 - TASK-020 Read Stability & Runtime Validation Policy v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-07

TASK-020 read-only runtime validation uses the following fixed v1 policy:

1. Every qualifying Tier A fixture uses 10 consecutive double-capture semantic stability pairs.
2. Each pair is a complete Tier A capture A followed immediately by the same capture B.
3. A and B must be semantically equal after only explicitly approved non-semantic ordering normalization.
4. All 10 accepted pairs for a fixture must yield the same semantic snapshot.
5. Any unexplained drift is retained as evidence and yields SUPPORTED_UNSTABLE for the affected read scope; do not retry until green and erase the failure.
6. Project/Timeline/TimelineItem identity candidates require 3 timeline-switch round trips before any same-project switch-stability claim.
7. Project reopen stability requires 3 reopen cycles only if that lifetime is claimed.
8. Resolve application restart testing is required before any cross-session PERSISTENT_VERIFIED claim, but is not required for basic TASK-020 completion.
9. Readable GetUniqueId values are observation data only and do not by themselves grant PERSISTENT_VERIFIED identity.
10. TASK-020 first-milestone completion requires stable RuntimeProfile, registered Project/Timeline context, stable core Timeline/Track/TimelineItem geometry and media/source reads, unique role binding, qualifying fixture-class requirements, 10/10 full-snapshot pair equality, and a read-only adapter surface with no mutation/generic execute/eval/repair path.
11. Project reopen/restart/split/delete identity claims remain outside the basic completion gate unless explicitly tested.
12. Tier B remains diagnostic only and Tier C remains fail-closed.

Detailed policy: docs/TASK_020_RUNTIME_VALIDATION_MATRIX.md.



## ADR-034 - Probe Fixture Catalog v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-07

TASK-020/TASK-021 use five canonical synthetic fixture classes:

1. F0_BASIC — three linked A/V placements with explicit timeline/source ranges and known gaps.
2. F1_REPEATED_MEDIA — the same MediaPool item repeated, including two placements with the same
   source range, to prevent media/filename/source-only identity.
3. F2_TRACK_STATE — explicit enabled/disabled and locked/unlocked track-state combinations.
4. F3_MARKER_SUBTITLE — explicit timeline marker, item marker and subtitle timing/text candidates.
5. F4_IDENTITY_BOUNDARY — two timelines in one disposable project with intentionally identical
   media/track/timeline/source layouts for same-project switch identity testing.

All timeline geometry is defined as half-open offsets from T0 = Timeline.GetStartFrame(); source
ranges remain separate source-frame coordinates.

F0-F3 materialize as independent disposable project instances. F4 is one disposable project with two
timelines. Do not use one shared mega-project as independently isolated destructive fixtures.

Canonical assets are synthetic, dedicated test media and are bound by TASK-021 package content hashes,
never filename. Real editorial footage is reserved for Pause/Dialogue quality and workflow evaluation
and does not satisfy F0-F4 canonical fixture identity.

Detailed catalog: docs/PROBE_FIXTURE_CATALOG.md.



## ADR-035 - Probe Environment Registry & Runtime Control Plane v1
Status: ACCEPTED - Chat Product/Architecture Review, 2026-10-07

1. Probe environment registration, environment verification and run arming are separate states.
2. Project display name/path/folder/sentinel never independently authorize destructive probing.
3. Every run authorization binds exact environment/project generation, fixture instance, case/domain,
   RuntimeProfile, pre-snapshot, observation scope, containment envelope, lease and typed invocation.
4. Authorization is single-use and is consumed/discarded on final pre-invocation failure as well as
   after invocation submission.
5. No wall-clock TTL is required in v1; freshness comes from exact generation/profile/snapshot binding.
6. There is no reusable global destructive-probe enable switch.
7. Invocation submission consumes authorization even when native outcome becomes OUTCOME_UNKNOWN.
8. A no-further-mutation BLOCKED gate prevents new calls but does not claim cancellation of an
   already-submitted native command.
9. Unexpected fixture-local mutation makes the current project generation REVERIFY_REQUIRED; no
   further qualifying mutation is allowed until independent project-level re-verification succeeds.
10. Project-level contamination makes the generation CONTAMINATED and requires rebuild/new generation.
11. Crash/bridge uncertainty after invocation locks down further mutation until explicit
    re-establishment/rebuild.
12. CONTAMINATED cannot transition back to VERIFIED_CLEAN in-place.
13. Exploratory probes do not bypass registration, one-run arming, containment or no-blind-retry.
14. Ordinary editing requests never implicitly arm the probe harness or run qualification suites.

Detailed contract: docs/PROBE_RUNTIME_CONTROL_PLANE.md.

# Open Decisions


## OPEN-020 - Native Probe Environment Registration Authenticity
Status: OPEN (created by ADR-035, 2026-10-07)

ADR-035 defines pure registration/currentness/control-plane semantics but does not authenticate that a
caller-supplied project reference really identifies a disposable non-production Resolve project.

TASK-019 may validate typed bindings only. Actual runtime work must later establish:

- trustworthy native project/library correspondence for a registered environment
- how project generation is derived across import/rebuild/reopen
- how the environment fingerprint/currentness token is captured
- how working/production projects are excluded from registration using native evidence
- whether a dedicated project library can become a hard isolation requirement
- persistence/registry storage and tamper/authenticity guarantees

Until then, registration facts remain typed control-plane evidence, not native truth.

## OPEN-019 - Installed Resolve Read / Materialization Capability Map
Status: PARTIALLY RESOLVED — DOCUMENTED READ MAP; RUNTIME VALIDATION REQUIRED (2026-10-07)

ADR-032 architecture is now paired with a documented Resolve 21.x read-capability map in
`docs/RESOLVE_READ_CAPABILITY_MAP.md`. This is a candidate adapter surface, not runtime proof.

Documented Tier A candidates for TASK-020 include RuntimeProfile/version, Project/Timeline unique IDs,
timeline range/settings, track count/name/subtype/enabled/locked state, TimelineItem unique ID and
track membership, timeline/source ranges, MediaPoolItem identity, linked items, clip-enabled state,
markers, and subtitle-track/item enumeration.

Tier B remains partial/non-authoritative for Safety proof: simple speed/fades and generic item
properties, transition presence/span/type surface, Fusion-comp presence and color-node graph presence.

Tier C remains UNKNOWN or insufficient for production Safety proof until direct runtime evidence:
identity lifetime across session/reload/split, stable native Track identity, full transition
parameters/alignment, generic Edit/Fairlight effect graph, generic keyframe/interpolation state,
complete variable-retime curves, and generic preservation-proof production.

Capability discovery order is fixed:
1. inspect the exact installed `DaVinciResolveScript.pyi` / Developer Scripting reference,
2. confirm the native object's callable surface,
3. perform a bounded read call,
4. validate the typed return value,
5. repeat unchanged reads to establish stability.

`hasattr()`, method-name presence, README examples, or a non-erroring call alone do not upgrade a
capability to runtime SUPPORTED/VERIFIED.

Remaining resolution requires TASK-020 on the exact Windows Resolve/adapter RuntimeProfile and
TASK-021 materialization validation. Unsupported/unavailable fields remain UNKNOWN/UNSUPPORTED rather
than being synthesized.



## OPEN-018 - Capability Verification Policy / Challenge Matrix
Status: RESOLVED FOR v1 by ADR-030 (2026-10-07)

ADR-030 fixes 20/30/50 minimum positive runs using 5 clean runs per positive fixture class, 3 clean
runs per applicable mandatory challenge class, COMPLETE observation scope, zero conflicts/unexpected
side effects/containment failures/ambiguous targets, and VERIFIED post-read/reconciliation plus
execution-grade identity.

New primitives or materially different challenge matrices require a new policy version and Chat review.


## OPEN-017 - Native Capability / Effect Model Evidence Production
Status: OPEN (created by ADR-028, 2026-10-07)

ADR-028 consumes verified execution identity, capability profiles, native effect models, post-read
capability and reconciliation specifications but does not define how real Resolve runtime evidence
earns VERIFIED status.

A separate Native Capability Probe / Effect Model Evidence contract must define:
- probe isolation and sacrificial test timeline requirements
- before/after observation completeness
- version/platform/adapter/session binding
- primitive target identity proof
- predicted side-effect scope evidence
- repeatability/conflict handling
- reconciliation probe evidence
- post-read capability evidence
- fragment rebinding evidence
- criteria for SUPPORTED_VERIFIED / VERIFIED vs UNVERIFIED/CONFLICTING/STALE
- evidence invalidation after Resolve/adapter/platform changes

Until then, actual destructive Resolve lowering remains unverified/fail-closed.



## OPEN-016 - Resolve Mutation / Rollback Runtime Capability
Status: OPEN (created by ADR-027, 2026-10-07)

ADR-027 defines product transaction, rollback and postflight semantics without claiming actual
Resolve mutation/Undo guarantees.

Runtime validation is still required for:
- exact native lowering for range removal/displacement
- target identity stability during mutation
- command acknowledgement vs actual state semantics
- Undo/rollback availability and reliability
- whether rollback can be scoped to one AI transaction
- post-rollback base-state verification
- bridge timeout/OUTCOME_UNKNOWN reconciliation
- crash/restart behavior
- safe commit-window coordination
- executor capability differences by Resolve version/platform

Until verified, rollback capability must not be upgraded to SUPPORTED_VERIFIED and destructive runtime
integration must remain fail-closed.



## OPEN-015 - Native Preservation Proof Production
Status: OPEN (created by ADR-026, 2026-10-06)

ADR-026 allows transition/effect/keyframe structures to pass preflight when a valid typed
PRESERVATION_PROVEN proof is supplied, but Safety does not create that proof.

Future runtime/API work must decide:
- what native observations are sufficient to prove transition preservation
- what effect/node/editability state must be compared
- how keyframe integrity is represented and verified
- proof scope and identity requirements across snapshots
- which Resolve versions/platforms expose sufficient evidence
- proof invalidation after human/native changes
- whether some structures remain permanently REVIEW-only

Until resolved, TASK-015 may consume synthetic/precomputed PreservationProof records only and must not
invent proof-generation semantics.



## OPEN-014 - Temporal Participation and Gap Interaction Policy
Status: OPEN (created by ADR-025, 2026-10-06)

ADR-025 requires an explicit resolved DisplacementParticipationAssessment but deliberately does not
decide how production code selects participants or how existing gaps alter ripple participation.

Future Chat Architecture Review must decide:
- track-local vs dependency-resolved multi-track participation
- native sync-lock/linked-selection evidence, if any
- subtitle/marker temporal participation policy
- gap preservation vs gap absorption semantics
- behavior for objects crossing the removed interval
- nonuniform displacement cases
- production scope construction from Resolve snapshots

Until resolved, TASK-014 may consume explicit synthetic/precomputed participant facts only and must
not infer these policies.




## OPEN-013 - Cut Geometry Resolution Contract
Status: RESOLVED FOR v1 FOUNDATION by ADR-024 (2026-10-06)

ADR-024 fixes the v1 geometry-resolution vocabulary, ambiguity behavior and confidence boundary.
TASK-013 may implement pure explicit-constraint geometry resolution after TASK-012 is approved/merged.

Still deferred beyond the v1 foundation:
- actual audio/VAD/STT/prosody/breath/semantic geometry producers
- GeometryConfidence calibration/derivation
- candidate ranking policy
- multi-range/cross-placement geometry
- ALLOWED_REMOVAL alternative/union semantics
- audio seam/crossfade/room-tone treatment
- numeric geometry quality gates

These deferred producer/quality topics require future Chat Architecture Review and real pilot/media
evidence. ADR-024 does not authorize them.

## OPEN-012 - Resolve Adapter Runtime Capability / State Identity Realization
Status: OPEN (created by ADR-022, 2026-10-06)

ADR-022 defines the observation contract but deliberately does not claim which DaVinci Resolve
versions/platforms expose each field reliably or how a production adapter derives a trustworthy
mapping-relevant state token.

Runtime validation is still required for:
- persistent/session-local timeline, track and placement identity
- media-pool/native media identity
- source/timeline range fidelity
- retime visibility
- relationship/link visibility
- transition/effect/keyframe and track-state visibility
- capture start/end consistency checks
- trustworthy state_token/fingerprint derivation
- platform/Resolve-version differences

Until validated, capability values and identity scopes must remain conservative. Do not upgrade
UNKNOWN/SNAPSHOT_LOCAL/UNVERIFIED based on heuristics.




## OPEN-011 - Native Time & Snapshot Mapping
Status: RESOLVED FOR v1 FOUNDATION by ADR-021 (2026-10-06)

ADR-020 requires evidence to be bound to timeline ID/version/placement/range but deliberately accepts
already-aligned internal integer half-open FrameRange values. Production Resolve source/timeline
timecode, drop-frame, media FPS, timeline FPS, retime, mixed-FPS and native object correspondence are
not yet mapped into that domain.

Needs Chat contract before production media producers or cross-clip evidence binding:
- authoritative timeline/source time domains
- frame-rate and drop-frame conversion ownership
- mixed-FPS mapping
- source-range vs timeline-range correspondence
- clip boundary / split fragment mapping
- retime interaction
- snapshot fingerprint/version evidence
- stale/revalidation behavior against live Resolve
- relationship with OPEN-001 persistent identity and OPEN-006 native correspondence

No TASK-009 code may invent these mappings. TASK-009 operates only on already-aligned internal ranges.

## OPEN-010 - Evaluation event episodes and timing completeness
Status: OPEN (TASK-008, 2026-10-06)

ADR-019 settles raw evidence, source separation and metric formulas; real collection is absent.
Remaining questions: finalized-episode reopening/late events, reaccept after recovery,
partial versus full pause restoration, cross-proposal/run ordering, batch-event deduplication
in collectors, activity overlap/coverage provenance, manual estimates and pairing governance.
Options: infer missing decision/timing/collection semantics, or accept explicit complete
single-proposal episodes and reject/return unknown outside the supported subset.
Recommendation: latter. TASK-008 spec records contiguous sequences, terminal finalization,
unknown result after revert, sticky recovery flags and explicit timing coverage/zero evidence.
These are conservative pure-evidence constraints, not authorization for production tracking.
Frame tolerance NEAR_RANGE and GatePolicy thresholds remain undefined; no numeric guesses.
Needs Chat decision before real collection, late-event/reopen/partial-restore support,
overlap correction or actual pilot pairing. None blocks immutable records/pure metrics.


## OPEN-006 - Topology correspondence and native track indices
Status: OPEN

Context/evidence: TASK-003 fake TimelineObjectId includes track_id, so a native object
move changes that composite reference. Track tuples do not define Resolve's indexing API.
Affected contract: INV-019 object membership/track order without wrong identity matching.
Options: production independent persistent ID, approved adapter correspondence, or fake
explicit origin bindings. Media/name/source/time matching can confuse repeated placements.
Recommendation for TASK-004: preserve existing relationship IDs; separate comparison identity
from current membership using explicit one-to-one fake bindings. Tuple index is fake order only.
Needs Chat decision: production stable identity/correspondence and per-type native track indices.
Deferred: adapters, implicit identity inference, actual track movement. OPEN-001 remains OPEN.

## OPEN-007 - Native editability / flatten provenance evidence
Status: OPEN

Context: topology alone cannot prove that a clip tagged native is individually editable
or distinguish every intentional replacement from a hidden render/flatten result.
Options: verified adapter provenance, retained source object graph, or conservative REVIEW
when provenance/structure is ambiguous. Blind trust in labels is insufficient for production.
Recommendation: fake input declares origin; reject preview/render/flattened editable substitutes,
and REVIEW whole multi-layer collapse into one replacement even if changes are expected.
Needs Chat decision: authoritative native-state evidence and acceptable editable replacement
semantics before production integration. No generic effect/editability certification here.
Deferred: Resolve/render adapters and broad flatten detection beyond the scoped data contract.


## OPEN-005 - Relationship execution semantics and lifecycle
Status: PARTIALLY RESOLVED by ADR-013

Resolved:
- relationships are descriptive, not executable by themselves
- explicit PEER / DRIVER / DEPENDENT roles for future execution semantics
- action-specific propagation rather than a generic FOLLOW behavior
- preserve existing sync/J-L cuts; never normalize boundaries by default
- no automatic delete cascade
- conflicts escalate to REVIEW
- cycles are compiled from the base snapshot, never recursively executed

Still OPEN:
- type-specific cardinality and exact role constraints
- concrete fragment rebinding after split/delete
- native Resolve linked-selection versus internal relationship semantics
- source-timecode/offset representation for production sync evidence
- multi-track ripple + relationship propagation interaction
- Compound/Multicam/nested relationship semantics
- actual subtitle/marker/effect object adapters

These unresolved details block relationship-aware execution, not the approved domain foundation.
OPEN-001 remains the separate production identity decision.


## OPEN-002 - Candidate authority representation and evidence boundary
Status: PARTIALLY RESOLVED by ADR-015/016 and TASK-006 user instruction

Resolved: selection != approval != apply != verification != promotion; base identity/
version required; verified apply prerequisite for promotion; active timeline separate;
human edit priority; whole-version stale rejection; no automatic rebase.

Still OPEN: candidate native duplicated timeline versus virtual plan; concrete result
identity; production WorkingAuthority timeline-only versus timeline+version schema;
evidence provenance and same-timeline apply/authority observation coordination.
Evidence: the repository has only immutable fake snapshots and no live observer,
Apply, postflight or persistent result identity. State flags cannot prove native facts.
Options: native verified timeline references, virtual result references mapped by an
adapter, or explicit fake observation/evidence values for foundation tests.
Recommendation for TASK-006: the latter, with opaque fake result IDs and timeline/version
comparison inputs. Do not adopt that fixture schema as the production architecture.
Chat must decide production representation/provenance before adapter/persistence/apply.
Deferred: real candidate creation, actual result binding/verification and coordination.

## OPEN-008 - Concurrent work invalidation and candidate lifecycle details
Status: OPEN (TASK-006, 2026-10-05)

Questions: exact DIRTY vs STALE distinction; human changeset representation; scope-aware
invalidation; partial candidate refresh; garbage collection/retention; simultaneous
multiple approvals; approval revocation; crash/restart candidate-state persistence.
Evidence: current state has a whole timeline version only, no changesets or authoritative
observer. A single candidate transition context cannot settle session-wide approval policy.
Options: infer region independence/lifecycle defaults now, or retain strict version
invalidation and omit underspecified transitions. Recommendation: strict version mismatch
=> STALE, sticky invalidation, no rebase/refresh/revoke/retention implementation.
Work phase is separate descriptive progress, not validity. DIRTY is not given invented
semantics. Single-candidate approval does not decide whether global multiple approvals
are allowed. Branching preserves source base; applied-result branching remains OPEN-002.
Needed Chat decision: contracts for these features before implementing them. Deferred:
coordinator/observer/scope merge/refresh/revoke/persistence, not the pure state foundation.

## OPEN-001 — Persistent Timeline Item Identity
Status: OPEN

Resolve에서 session/프로젝트 재오픈 후에도 신뢰할 수 있는 persistent TimelineItem ID를 확보할 수 있는지 runtime/API 검증이 필요하다.

Options to investigate:

1. native unique id
2. media pool identity + source range + track context
3. synthetic session id
4. composite fingerprint

이 결정을 TASK-001에서 임의로 확정하지 않는다.

## OPEN-004 — Range boundaries and multi-item delete scope
Status: PARTIALLY RESOLVED by ADR-008/010/011; cross-clip and multi-track scope remains OPEN

Context: TASK-001 does not specify end-frame inclusion, gaps, overlapping requests,
or ripple participation across tracks and clips.
Observed behavior: a minimal INV-001 fixture needs an exact frame interval convention.
Options: half-open versus inclusive end; split cross-clip requests versus review;
track-local versus dependency-based ripple.
Codex recommendation: use integer [start, end) only inside the TASK-001 fake;
accept one track, 1:1 source mapping, and targets contained in a single clip fragment.
Reject unsupported or overlapping requests explicitly, without choosing production policy.
Needs Chat decision: confirm production interval and ripple scope before broadening support.

## Chat Gate resolution - TASK-001 / TASK-002, 2026-10-05

TASK-001 Domain Model, FakeTimeline, StableTarget and INV-001: APPROVED WITH CHANGES.
ADR-008..012 above record the explicit user approval in this session.
OPEN-003 is resolved for fake lineage and version granularity by ADR-009/012;
production split identity remains deferred to OPEN-001.
OPEN-004 is resolved for interval convention and TASK-002 protection/ripple policy
by ADR-008/010/011. Multi-track and cross-clip request scope remains OPEN and unsupported.
Original OPEN descriptions are retained as historical context, not competing policy. Current status labels and accepted ADRs take precedence.
TASK-002 is authorized only for INV-002/003; work on feat/task-002-inv002-inv003,
submit a PR, and request Chat Gate. Do not merge or proceed to further tasks automatically.

### TASK-017 application of OPEN-017 / OPEN-001 / OPEN-016 (remain OPEN)

The pure validator consumes caller-declared verified capability/effect/identity/reconciliation
records. A sequence-level effect model is the explicit net-effect evidence for a decomposition;
intermediate fragment correspondence must have separate bound verification evidence. The validator
cannot establish that a real Resolve primitive, locator or fragment actually satisfies those claims.
No native recipe, returned-item order, locator lifetime or rollback guarantee is inferred. Evidence
production/authenticity, intermediate native state acquisition and runtime validation remain deferred
to their separately approved contracts/tasks. TASK-017 does not implement TASK-018 or later probes.

# Resolved Decision History

## OPEN-003 — Split identity and version granularity
Status: RESOLVED FOR FAKE by ADR-009/012; production identity remains OPEN-001

Context: stable targets must survive an earlier delete within the same plan, while stale
plans cannot execute. Persistent identity is already OPEN-001.
Options: fragment IDs with parent lineage versus composite source identity; version per
edit versus per plan. Production transaction/rollback semantics remain a separate task.
Codex recommendation: fake-only clip_id denotes placement lineage; fragments retain it
and are distinguished by source range. Distinct placements require distinct clip IDs.
The fake checks the base snapshot before application and advances version once per plan.
Needs Chat decision: production split identity and version/transaction boundaries.
No Resolve identity, automatic rebase, or rollback guarantee is established by TASK-001.


## Chat Gate - TASK-002 approval and TASK-003 authorization

User reports TASK-002 / PR #1 APPROVED and merged; fetched main contains merge 747474a.
TASK-003 is Relationship Domain Foundation only, as specified in
 tasks/TASK_003_RELATIONSHIP_DOMAIN.md. INV-004 is not the next implementation by number.
Immutable relationships, reference validity, independent J/L-cut timing and fake-only identity
are required. No relationship policy execution, actual sync changes or later task is authorized.


## Chat Gate - TASK-003 approved / TASK-004 authorized

User reports TASK-003 PR #2 APPROVED and merged. TASK-004 is topology foundation only.
Preserve Editability, Native Editing Environment Preservation and INV-019 are explicitly
approved user requirements; preview/render must not replace editable source state.
Effect/VFX preferences are product/architecture notes only, not execution authorization.
Implementation follows tasks/TASK_004_TIMELINE_TOPOLOGY.md; PR and Chat Gate required.

### TASK-005 application of OPEN-005 (2026-10-05, remains OPEN)

ADR-013 is accepted; TASK-004/PR #3 and semantics/PR #4 are merged per Chat.
The TASK-005 spec proposes explicit optional roles without inferring legacy roles.
Exact type-specific cardinality, AV_LINK PEER rules, SYNC_GROUP leader, split fragment
rebinding, Compound/Multicam, native Linked Selection and concrete sync offsets remain
OPEN-005. Evidence: current fake IDs can identify multiple split fragments and existing
policy metadata contains no action-specific offset/mapping contract.

Options: infer a universal FOLLOW propagation rule (unsafe/contradicts ADR-013), or
retain finite impact candidates and require REVIEW until individual semantics are
approved. Recommendation: the latter, as specified in TASK-005. Conservative connected
impact assessment is not execution reachability. All related intents remain REVIEW;
only dependency-free inspection may be SAFE_TO_CONTINUE (never apply permission).
Chat decisions are needed before lowering any candidate into executable action.
Execution/rebinding/cardinality enforcement are deferred; pure diagnostic compilation
can proceed. OPEN-001 and OPEN-006/007 are unchanged.


## Chat Gate - TASK-005 approved / TASK-006 authorized

User reports TASK-005 / PR #6 APPROVED and merged. ADR-015/016 are accepted in main.
TASK-006 builds pure candidate/concurrent state only; no actual apply or postflight.
Attention Economy notes follow the user-approved four principles without UI/telemetry.

## OPEN-009 - Pause observation producers and media mapping
Status: PARTIALLY RESOLVED by ADR-020 (TASK-007 onward, 2026-10-06)

Evidence: ADR-018 defines decisions/confidence but the repository has no audio/transcript
analysis, feature provenance or native media mapping. Caller observations cannot prove
meaning or safely map a pause spanning native items.
Questions: RelativePauseBand calculation and local pacing window size; prosody feature
schema; transcript boundaries; emotion/thinking signal producer; numeric confidence
calibration; genre/content-mode detection; exact tighten target generation; frame-rate/
mixed-FPS mapping; clip-boundary spans; multi-speaker overlap/crosstalk; dialogue cleanup.
Options: infer these using arbitrary global duration thresholds (contrary to TASK-007),
or accept explicit typed observations and preserve/review uncertain inputs.
Recommendation: latter for TASK-007. Positive local reference must be shorter than the
original for TIGHTEN; no synthesized target, signal extraction or native binding.
Chat must approve producer/provenance/mapping and dialogue schema before those layers
are implemented. Deferred: Intelligence/Media Analysis, real clip binding, execution.
This OPEN does not block pure domain/rule tests and does not resolve OPEN-001.

## Chat Gate - TASK-006 approved / TASK-007 authorized

User reports TASK-006 APPROVED/merged; ADR-018 is accepted in main. TASK-007 is solely
Pause Candidate domain and conservative deterministic rules over supplied observations.
Dialogue cleanup and actual intelligence/editing remain outside the implementation task.

## Chat Gate - TASK-007 approved / TASK-008 authorized

User reports TASK-007 / PR #11 APPROVED and merged. ADR-019 accepted in main.
TASK-008 is evaluation language and pure derivation only; no telemetry, storage, raw media,
training consent inference or automatic reference/model update.


## TASK-009 application of OPEN-009 / OPEN-011 (remain OPEN)

ADR-020 provides evidence vocabulary but not a native mapping proof or a calibrated
producer/strength interpretation policy. The existing fake snapshot can validate
already-aligned single-fragment containment only. Inferring native binding from
lineage/range would violate OPEN-001/011; resolving it requires the separately
approved Native Time & Snapshot Mapping Contract. TASK-009 reads snapshot ranges
without source conversion and fails closed on missing/cross-fragment targets.

Unknown assertions and missing required preparation values remain reviewable; no
producer ranking, strength-to-confidence rule, negative-to-positive inference or
local target generation is introduced. Alternatives are producer-specific readiness
rules (need future approved semantics) versus conservative review (recommended for
v1). Actual producer algorithms/calibration and native binding stay deferred under
OPEN-009/011; no new architecture decision is marked accepted.


### TASK-009 submission reconciliation with newer main

During TASK-009, main advanced to f229576 with accepted ADR-021 and prepared TASK-010.
Merged that documentation into this branch without implementing TASK-010. OPEN-011 is
now RESOLVED FOR v1 FOUNDATION, superseding the pre-implementation OPEN status recorded
above. Actual native mapping implementation remains outside TASK-009. OPEN-009 producer
algorithms/calibration and OPEN-001/006 production correspondence remain unresolved.


## TASK-010 application of OPEN-001 / OPEN-006 / OPEN-008 / OPEN-012

User confirms TASK-009 APPROVED and merged. TASK-010 follows accepted ADR-021 only.
Opaque supplied state tokens and explicit concrete spans are sufficient for pure
mathematical validation, but do not establish native identity, live freshness or an
adapter token-generation algorithm. Those remain OPEN under the existing decisions.
Inferring these from FPS/filename/timecode would violate ADR-021; the alternative
(recommended here) is explicit binding plus fail-closed validation. Runtime discovery,
scope-aware reuse and production correspondence stay deferred. No new native policy
or accepted architecture decision is introduced. TASK-011 remains unstarted.


## TASK-011 application of OPEN-012 (and OPEN-001/006/008)

User confirms TASK-010 APPROVED/merged. ADR-022 leaves native identity lifetime evidence,
capability availability, consistency proof and state-token derivation dependent on actual
runtime/API validation. This foundation accepts explicit categorical claims and evidence
references; it cannot verify native truth or turn opaque strings into persistent identity.
Options: infer capabilities/identity/freshness from metadata (forbidden), or preserve
unknown/partial/unverified values and block readiness (recommended). Runtime capability
verification and producer-specific token algorithms remain OPEN-012, not implemented.
PAUSE_ANALYSIS is a versioned conservative input-readiness profile only. Passing it is not
mapping EXACT, content classification, Safety clearance or authority. Native integration,
partial refresh and production identity remain deferred; TASK-012 is not authorized here.


## TASK-012 precomputed-fact boundary (OPEN-001/006/008/012 remain OPEN)

TASK-011 APPROVED/merged per user. ADR-023 authorizes geometry consumption and precomputed
readiness only. Native readiness identities and existing fake placement IDs have no approved
production correspondence bridge yet (OPEN-001/006). TASK-012 therefore requires explicitly
bound caller facts with assessment references rather than inventing a bridge, calling mapper/
adapter/compiler, or interpreting relationship members. Scope-aware freshness/assessment
refresh and runtime authenticity remain OPEN-008/012. Reusing a pause-level EXACT fact for
another cut range could bypass fractional-boundary checks: require an explicit primary-range
assessment and matching geometry/action-specific dependency input instead. Recommendation:
keep this conservative contract until a separately approved orchestration/lowering layer can
validate real provenance. Actual integration and Safety remain deferred. OPEN-013 v1 contract
is resolved by ADR-024; this does not authorize TASK-013 implementation in this task.


## TASK-013 application of ADR-024 / deferred OPEN-013 topics

ADR-024 resolves OPEN-013 for v1 geometry semantics, not confidence aggregation/calibration,
ranking or actual producer algorithms. Equal ranges can have different supplied confidence
labels. Choosing/averaging one would invent a confidence policy; TASK-013 retains typed
confidence on every support record instead. Recommendation: preserve all metadata and count
only distinct ranges, as ADR-024 requires. Any future scalar aggregation policy still needs
separate approval. No new accepted product decision is introduced.

OPEN-001/006/008/012 still govern production correspondence/currentness. Caller supplies the
already-aligned placement span, current ref and mapping status; resolver cannot verify native
truth and does not call mapping/evaluator. Native integration, confidence derivation, raw-media
producers and ranking stay deferred. TASK-014 / ADR-025 preparation does not authorize that
implementation in TASK-013.


## TASK-014 application of OPEN-001/006/008/012 (remain OPEN)

ADR-025 authorizes typed expected effects and synthetic comparison, not a native post-capture
or fragment identity algorithm. Existing fake lineage IDs may span split fragments, and a
range removal does not supply concrete native post-fragment correspondence. Inferring that
correspondence would invent the deferred native policy. Recommendation: compare the explicitly
supplied semantic RangeRemovalEffect, require caller identity/base-post evidence and complete
scope observations for other objects, and leave native capture/rebinding/authentication OPEN.
Alternatives such as filename matching or generated fragments would conceal uncertainty and
are not implemented. Actual adapter proof and scope-aware refresh require a later contract.
Participant discovery and gap interaction policy remain explicitly deferred by ADR-025; the
compiler accepts a resolved, uniform-consequence assessment only. This is not a Safety verdict.
No new accepted architecture decision; TASK-015 is not started.


## TASK-015 application of OPEN-015 / OPEN-001/006/008/012 (remain OPEN)

ADR-026 accepts typed precomputed preservation proofs but does not specify a trustworthy
native producer. TASK-015 validates exact subject, snapshot, ExpectedDiff, kind, contract and
outcome bindings; opaque producer/evidence references are retained, not authenticated.
Inferring safety from producer name/confidence or generating proof locally would conceal
missing native guarantees. Recommendation: preserve supplied categorical evidence and fail
closed on missing/invalid facts, while leaving native proof algorithms, runtime capability,
identity bridging and freshness authenticity deferred. Real producer implementation requires
Chat decisions on OPEN-015's native observations and invalidation semantics. No accepted
policy is added; the existing 17-check profile and precedence are unchanged. TASK-016 is not
started. Earlier fake safety.py behavior remains separate from this pure integration layer.


## TASK-016 application of OPEN-016 / OPEN-001/006/008/012 (remain OPEN)

ADR-027 authorizes pure lifecycle semantics, not native atomicity, Undo reliability, commit-window
coordination or crash/restart proof. Caller-supplied step, reconciliation, postflight and base-state
verification records are binding-checked but not authenticated. Inferring applied/failed state from
timeout or assuming an Undo capability would violate the contract. Recommendation: retain unknown
reports and failed/recovered history; require fresh bound evidence before any success classification.
Native evidence production, target correspondence and runtime guarantees remain OPEN-016 and the
existing identity/freshness OPENs. Exact runtime handling/release of UNVERIFIED_APPLY or unresolved
recovery needs later decisions; this foundation blocks new destructive eligibility and implements
no automatic retry, recovery or lockdown release. Base-state verification MATCH, not a native return,
is the recovery evidence, including reconciliation of an uncertain rollback response. No new runtime
policy is marked accepted. TASK-017 is not started.

### TASK-018 application of OPEN-017 (native semantic correspondence remains OPEN)

ADR-030 resolves quantitative v1 policy (OPEN-018 remains resolved). Different concrete fixtures may
have different placement IDs/ranges while exercising the same operation. No accepted native role or
cross-fixture normalization contract defines equivalence for those values. TASK-018 therefore compares
explicit observed semantic values exactly and does not infer equivalence from names/order/positions.
A future producer must supply explicit, independently justified correspondence under its approved
contract; normalization algorithm and native proof authenticity remain deferred. This can conservatively
leave real heterogeneous fixtures UNVERIFIED/CONFLICTING; it cannot create a false VERIFIED model.

Likewise, domain declarations and independent clean-run metadata are immutable supplied facts. The
pure foundation detects mixed declarations and duplicate identities, but cannot prove a caller did
not omit historical evidence or falsify fixture reconstruction. Ledger persistence, registry validation,
and native acquisition belong to separately authorized harness work. No TASK-019 implementation or
native guarantee is introduced. Existing TASK-017 status fields are not implicitly reused by new
reconciliation/fragment evidence; production integration remains deferred.

### TASK-019 application of OPEN-020 (remain OPEN)

The fake control plane validates exact typed registrations/generations/fingerprints, but does not
establish their native truth. Registry persistence, native generation discovery, crash-safe durable
consumption and cross-process lease atomicity remain unimplemented. The pure transition API consumes
an immutable authoritative input state and returns its successor; native runtime serialization must
later ensure old state snapshots cannot be replayed as new authority. No name/path/sentinel or caller
flag is promoted to a native authenticity guarantee. This PR does not implement TASK-020.

Project re-establishment is represented only by independent bound observation evidence after affected
fixtures are discarded. It never repairs project state; CONTAMINATED cannot use that path. A supplied
new generation can replace an old one while retaining its records, without claiming native rebuild or
cancellation of pending calls.
