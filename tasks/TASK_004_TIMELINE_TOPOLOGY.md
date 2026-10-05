# TASK-004 - Timeline Topology & Preserve Editability Foundation

Status: authorized by user after TASK-003 / PR #2 APPROVED and merged.
Branch: feat/task-004-timeline-topology. Write and commit this spec before implementation.
Scope: pure representation/comparison/validation; no topology mutation executor.

## Approved contract

Preserve Editability / Native Editing Environment Preservation. Preview/render may
flatten for viewing, but must never replace editable project state. INV-019 preserves
track identity/type/order and object membership except explicitly expected changes.
Expected topology changes never authorize flattening or substituting preview/render.

## Minimal representation proposed for this fake foundation

Reuse TrackId, TrackType, TimelineObjectId and RelationshipGraph. No production ID scheme.
- TrackTopology: track_id, track_type, zero-based order (identity is not the index).
  Indices describe the existing snapshot tuple order, not Resolve API track indexing.
- ObjectMembership: stable comparison object_id and current track_id as separate fields.
- TimelineTopologySnapshot: timeline_id/version, ordered tracks, object memberships,
  relationship graph, and state origin (NATIVE_EDITABLE, PREVIEW, RENDER, FLATTENED).
- from_snapshot projects data without changing timeline/graph/version. Optional explicit
  ObjectIdentityBinding maps current snapshot IDs to original comparison IDs after a move.
  Mapping must be one-to-one and reference actual current objects. No media/name/time inference.
  Without mapping, moved composite IDs are removed/added identities, never silently equivalent.
- TopologyDiff: exact track additions/removals/type changes/order changes and object
  additions/removals/moves. Added/removed tracks include index and type; common-track
  absolute index changes are reported even when caused by insertion/removal.
- ExpectedTopologyChange: timeline ID, base version and exact expected TopologyDiff.
  Validation compares against the actual independently computed diff, including missing
  expected changes. No implicit broad whitelist or automatic approval.
- Existing graph identity references are projected through the same explicit binding.
  References must match actual comparison objects; no relationship propagation is executed.

## Preserve-editability boundary

Validation rejects non-native base/result origins unconditionally, even if topology
matches or all changes are expected. Flattened previews/renders can be represented as
artifacts but cannot pass editable-state validation. Native-tagged multi-layer replacement
with a single replacement object is also conservatively rejected for REVIEW when all
original objects are replaced and multiple occupied tracks collapse to one.
An explicitly expected deletion of tracks that retains surviving native objects is not
classified as flattening merely because the number of tracks decreases.
Topology alone cannot prove a caller's native/provenance claim; production evidence is
OPEN-007 and remains out of scope. This checker does not certify effects/retime/editability
outside the supplied topology and provenance.
Changes to relationship records reject for REVIEW; lifecycle/propagation is OPEN-005.
This is not a new relationship executor. Unchanged graph metadata may accompany approved
membership changes in the data comparison, with explicit correspondence supplied by the caller.

## Red-first acceptance criteria

- [x] Multiple VIDEO/AUDIO/SUBTITLE tracks and stable identity independent of index.
- [x] Object membership references existing tracks; duplicate/ambiguous identities reject.
- [x] Same media across placements/tracks is never used to merge object identities.
- [x] Track removal/addition/type change/order change each reported and rejected if unexpected.
- [x] Object move reported using stable comparison identity; unmapped composite moves fail closed.
- [x] Exact expected topology changes pass; extra and missing changes fail.
- [x] Multi-layer flattened replacement fails, even when listed as expected.
- [x] PREVIEW/RENDER/FLATTENED cannot become editable source of truth, even unchanged topology.
- [x] Existing graph compatible and unchanged; dangling/rebound wrong references reject.
- [x] Pure comparison leaves source snapshots, graph and versions unchanged.
- [x] TASK-001/002/003 regression files unchanged and full suite passes.
- [x] Python 3.11 CI, Ruff, mypy pass; standard report and PR for Chat Gate.

## Architecture ambiguities

OPEN-006: production cross-track object identity and track indexing semantics. Fake
comparison accepts explicit correspondence only; no changes to approved relationship IDs.
OPEN-007: production native/editability provenance and flatten evidence. Conservative
validation uses explicit artifact origin and recognizable whole-layer replacement only.
These decisions block adapters/execution/certification, not pure topology comparison.

## Out of scope

Multi-track ripple execution, A/V sync correction, relationship policy propagation,
Resolve API, Fusion/effect automation, subtitle retiming, B-roll movement,
transaction/rollback, retime, AI planning, external VFX integration. No next TASK.

## Future effects note (documentation only)

Record Preferred Effects Implementation Path in PRODUCT_SPEC/ARCHITECTURE:
Edit Page/Resolve FX first for editorial effects; consider Fusion first for motion
 graphics/tracking/simple compositing, preferred not required; no free-form full Fusion
 automation initially. Future effects should be editable/reversible/inspectable.
Specialist VFX: prioritize Assist/Handoff. External tools later and only without
breaking Native Editing Environment Preservation. None of this is implementation scope.

Implementation and CI complete; PR #3 awaits Chat Gate. Standard report: docs/reports/TASK_004_COMPLETION.md.
