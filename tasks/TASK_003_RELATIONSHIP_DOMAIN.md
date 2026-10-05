# TASK-003 - Relationship Domain Foundation

Status: implementation authorized by user after TASK-002 Chat Gate APPROVED / PR #1 merged.
Base: main 747474a. Branch: feat/task-003-relationship-domain. Submit PR and request Chat Gate.
This specification is written before implementation; no next TASK is authorized.

## Goal and approved constraints

Represent relationships between timeline placements as immutable domain data before
implementing A/V sync, subtitle following, B-roll anchors or multi-track ripple.
TimelineSnapshot owns the immutable RelationshipGraph. Fake identity never claims
Resolve persistence: OPEN-001 remains OPEN. A relation never implies identical movement.
J-cut and L-cut are valid; no start/end alignment, normalization or sync correction.

## Minimal representation (implementation proposal for review)

- TrackType: UNKNOWN, VIDEO, AUDIO, SUBTITLE, OTHER. Existing tracks default to UNKNOWN;
  never infer type from a track name. Add as trailing field to preserve existing call sites.
- TimelineObjectId: fake-only composite (track_id, clip_id placement lineage). MediaId
  and current coordinates are not identity. Split fragments of an existing fake lineage
  share an ID; distinct placements require distinct IDs. No new persistent-ID scheme.
- RelationshipId: local identifier, unique within one graph.
- RelationshipType: AV_LINK, SYNC_GROUP, SUBTITLE_FOLLOWS_DIALOGUE, ANCHOR.
- RelationshipPolicy: FOLLOW, STAY, RECALCULATE, REVIEW; inert metadata per member,
  default REVIEW. No execution, propagation or inferred policy from relationship type.
- RelationshipMember: object_id plus policy. No inferred direction/role semantics.
- Relationship: immutable ID/type/member descriptor, at least two distinct members.
  A standalone descriptor has no timeline authority. Graph construction/addition is
  the binding step and MUST reject all unknown object references.
- RelationshipGraph: immutable object-ID registry and relationships, unique IDs,
  validated references, read-only lookup by placement, immutable addition.
- Snapshot derives its object registry from actual tracks/clips. An attached graph must
  match this registry exactly (no phantom or omitted objects); all references are checked.
  Omitting a graph creates an empty graph over existing objects, never a shared mutable value.
- Duplicate track IDs and ambiguous fake lineage fragments (different media or overlapping
  source ranges under one ID) reject; legal disjoint split fragments remain supported.

These are internal Python types, not a published/versioned IR serialization contract.
N-ary representation permits sync groups; type-specific cardinality/roles are not invented.

## Execution boundary

No relation policy execution is added. Existing one-track FakeTimeline accepts an optional
validated graph for storage. A nonempty edit plan against any nonempty relationship graph
is explicitly rejected for REVIEW before simulated mutation (unsupported semantics).
An empty plan remains a no-op. Existing relationship-free edits retain INV-001/002/003.
Their empty graph registry is rebuilt with the resulting surviving placement lineages.
Multi-track snapshots are representable; multi-track fake execution remains unsupported.

## Tests / acceptance criteria

- [x] Required types and all four relationship types/policies are representable.
- [x] Graph is an immutable part of immutable TimelineSnapshot; input lists cannot mutate it.
- [x] Unknown members, phantom registry entries, duplicate relationship/object/track IDs reject.
- [x] Same-media repeated placements resolve independently by object identity.
- [x] J-cut/L-cut examples retain independent video/audio ranges and source ranges unchanged.
- [x] Mixed member policies do not imply or perform identical movement.
- [x] Read-only graph lookup and immutable addition do not modify prior graph/snapshot/version.
- [x] Multi-track relationships are representable without adding multi-track edit execution.
- [x] Relation-bearing mutation rejects before delete and preserves snapshot/version.
- [x] TASK-001/002 test files and their INV-001/002/003 assertions remain unchanged and pass.
- [x] Full pytest, Ruff, mypy, Python 3.11 CI pass; standard report and PR prepared.

## Test-first plan

Write model/identity/reference/J-L-cut/immutability/execution-boundary tests first,
confirm missing-model failure, implement the minimum model and validation, then run
all regression tests. Compare coordinates and identities before/after representation.
No destructive feature is introduced.

## Open / deferred decisions

OPEN-001 persistent Resolve identity remains unchanged. Record OPEN-005 for directed
roles/cardinality, cycles/conflicting policies, and split/delete relationship lifecycle.
Those decisions block policy execution, not the explicitly authorized data foundation.

## Out of scope

Actual A/V sync modification, multi-track ripple execution, subtitle retiming, B-roll
movement, Resolve API, transaction/rollback, retime, AI, UI, production object identity,
INV-004 or full INV-006 certification. No timing inference or next TASK implementation.

Implementation and CI complete; PR #2 awaits Chat Gate. Standard report: docs/reports/TASK_003_COMPLETION.md.
