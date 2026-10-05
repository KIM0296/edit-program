# TASK-005 — Relationship Resolver & Dependency Plan Compiler

Status: implementation specification for the user-authorized TASK-005; Chat Gate pending.
Basis: ADR-013 and docs/RELATIONSHIP_EXECUTION_SEMANTICS.md (PR #4);
TASK-004 approved/merged (PR #3). This spec is committed before tests/implementation.

## Scope and output contract

Build a pure function `compile_dependencies(snapshot, topology, intent)`.
The immutable snapshot owns the RelationshipGraph; topology must describe that same
base, including identity, track type/order/membership and graph. No executor, adapter,
mutation, snapshot version increment or Universal Editing IR command is produced.

Proposed statuses (planning only):
- SAFE_TO_CONTINUE: this dependency inspection found no unresolved dependency. This
  does NOT authorize applying the primary edit, bypass INV-001/002/003/019 or preflight.
- REVIEW_REQUIRED: uncertainty, conflict, cycle, invalid base/target binding or
  unresolved action/role/fragment semantics. No action may be applied from this plan.
- UNSUPPORTED: RETIME requires the absent Temporal Mapping foundation.
  Unsupported takes precedence over review, while all review evidence is retained.

## Minimal domain proposal, before implementation

- Add RelationshipRole PEER / DRIVER / DEPENDENT to domain.py.
- Add trailing optional `RelationshipMember.role=None`. Existing graphs remain valid;
  None means unspecified and causes REVIEW, never an inferred role. Member tuple order
  has no meaning. Do not enforce new relationship-specific cardinality/leader rules.
- EditActionType: MOVE, RIPPLE, TRIM, DELETE, SPLIT, RETIME.
- PrimaryEditIntent: timeline ID, base version, target fake TimelineObjectId, action,
  requested half-open timeline range. One intent per compilation. No destination,
  executable displacement, replacement media or temporal mapping in this foundation.
- ConcreteFragment: fake object ID, media ID, unchanged timeline/source ranges.
- DependencyAction: object ID, triggering primary action, descriptive disposition,
  original policy, relationship ID and structured reason, concrete fragment candidates.
  Dispositions reuse FOLLOW/STAY/RECALCULATE/REVIEW vocabulary as *proposals only*;
  FOLLOW is downgraded to REVIEW because execution semantics are not yet approved.
  There is no dependent DELETE/TRIM/MOVE instruction or boundary normalization field.
- DependencyReason / ReviewReason: stable enum codes plus object/relationship evidence.
- Conflict: object ID plus relationship/policy requirements, without selecting a winner.
- Cycle: canonical set of objects in a directed strongly connected component.
- CompiledDependencyPlan: base identity/version, primary intent, canonical closure,
  finite deduplicated actions, conflicts, cycles, review reasons and status. All frozen.

## Resolution and safety rules

1. Validate topology against snapshot projection. Relationship registry/records/member
   order are compared canonically; track order remains meaningful. Reject non-native
   editable origins or inconsistent base with REVIEW and no dependent actions.
2. Resolve the requested primary range to exactly one fragment of its fake lineage.
   Missing object, gap-spanning or ambiguous binding => REVIEW, no guessed target.
3. Compute conservative *impact assessment* closure by connected relationship incidence
   from the primary object. This intentionally includes context peers and upstream
   drivers as review candidates; it is NOT directed execution reachability. A visited
   set guarantees termination. Disconnected components are excluded.
4. Canonicalize all evidence using (track ID, placement ID), relationship ID and enums.
   Return one action per (relationship, non-primary object), not per fragment/path.
   Multiple concrete dependent fragments remain evidence on one REVIEW action; never
   clone relationships or infer source-overlap correspondence.
5. Explicit DRIVER -> DEPENDENT pairs form the directed diagnostic graph. Detect true
   SCC cycles only; symmetric PEER context does not create a spurious two-edge cycle.
   Mixed/unspecified roles and cardinality remain unresolved and require review.
6. Preserve all per-object relationship policies as requirements. Different policies
   conservatively conflict (including FOLLOW vs STAY); do not silently prioritize.
   Equal duplicate requirements are not conflicts. This is an ambiguity diagnostic,
   not an assertion that generic FOLLOW/STAY supplies action-specific execution rules.
7. Any reached relationship needs REVIEW in this first compiler: exact action semantics,
   offsets and safe execution are deliberately unimplemented. Dependency-free MOVE,
   RIPPLE, TRIM and DELETE may return SAFE_TO_CONTINUE for further safety planning only.
   SPLIT requires rebinding review; RETIME is UNSUPPORTED even without relationships.

## Action-specific response table

| Trigger | Candidate dependent response | Safety outcome |
| --- | --- | --- |
| MOVE | STAY / RECALCULATE metadata retained; FOLLOW -> REVIEW | relation-specific displacement unresolved: REVIEW |
| RIPPLE | same vocabulary, distinct ripple reason | no multitrack propagation: REVIEW |
| TRIM | subtitle DEPENDENT with an explicit DRIVER: RECALCULATE; otherwise conservative metadata/review | no boundary alignment: REVIEW |
| DELETE | subtitle DEPENDENT with explicit DRIVER: RECALCULATE; otherwise STAY/RECALCULATE metadata or REVIEW | never dependent DELETE: REVIEW |
| SPLIT | REVIEW, existing fragments only | no rebinding or replicated links |
| RETIME | REVIEW candidate, unsupported temporal mapping reason | UNSUPPORTED; no propagation |

AV_LINK and SYNC_GROUP always retain existing mismatched ranges and return sync review;
ANCHOR has unresolved anchor semantics and returns review. Responses are assessments of
possible impact along the closure, not a claim that the primary action executes at
intermediate nodes. No policy or role can override these restrictions.

## Acceptance / red-first tests

Before source implementation, add tests and record the missing-compiler collection
failure. Then verify all seven requested cases: AV DELETE; subtitle DELETE/TRIM;
anchor DELETE; conflicting FOLLOW/STAY; A->B->C->A; unrelated exclusion; intentional
J/L cut. Also test all six actions, PEER/legacy roles, dependency-free status limits,
fragment ambiguity and single-fragment primary binding, exact topology/base rejection,
repeated-media placements, member/relationship/registry permutation determinism,
immutable inputs/results, diamond versus true cycle, disconnected cycles, finite
closure on a long chain, and unchanged TASK-001..004 regressions.
Run full pytest, Ruff and strict mypy locally and existing Python 3.11 GitHub Actions.
Update status, test matrix, known limitations, standard report; open PR and request
Chat Gate. Do not merge or start the next task.

## Open architecture and exclusions

OPEN-001 production identity remains. OPEN-005 retains cardinality, exact AV PEER
rules, SYNC_GROUP leader, fragment rebinding, Compound/Multicam, native Linked
Selection and sync offsets. OPEN-006/007 topology identity/provenance remain.
No new execution rule is settled by conservative REVIEW handling.
Actual edit/Resolve/multitrack ripple/A-V correction/subtitle retiming/B-roll movement/
transaction/rollback/retime/Fusion/effects/AI/external VFX are outside this task.
