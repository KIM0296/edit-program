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


# Open Decisions

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
