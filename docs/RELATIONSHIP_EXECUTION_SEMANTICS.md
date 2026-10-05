# Relationship Execution Semantics v1

Status: **Architecture baseline — accepted by Chat review**

This document defines safe default semantics for future relationship-aware editing.
It does **not** authorize relationship execution by itself.

## Core rule

A relationship describes editorial dependency/context. It is not an executable command.

Never infer:

- move together
- trim together
- delete together
- identical time boundaries
- identical ripple displacement
- automatic retime propagation

from relationship existence alone.

## Roles

Future executable semantics may use explicit roles:

- `PEER`: symmetric participant
- `DRIVER`: primary edited object
- `DEPENDENT`: object whose expected response is evaluated from the driver/action

Member tuple order has no meaning.

## Action-specific resolution

Execution must resolve the combination of relationship and edit action.

```text
Primary Edit
→ Relationship Graph
→ Action-specific Relationship Resolver
→ Dependency Closure from Base Snapshot
→ Concrete Fragment Binding
→ Conflict / Cycle Detection
→ Expected Dependent Actions
→ Safety Preflight
→ APPLY or REVIEW
```

Generic `FOLLOW` metadata must not become a universal propagation rule.

## Safety defaults

### A/V and sync

- Preserve existing relative A/V sync.
- Intentional J-cuts and L-cuts are valid state.
- Never force matching audio/video start or end boundaries merely because AV_LINK or
  SYNC_GROUP exists.

### Delete

Delete does not cascade automatically.

Deleting a DRIVER does not automatically delete every DEPENDENT. Subtitle, B-roll,
SFX, graphic, marker, or other dependents may need recalculation, preservation, or review.

### Split

A split may create multiple fragments from one lineage. Before executing dependent actions,
resolve which concrete fragments correspond to each other.

Ambiguous fragment binding → `REVIEW`.

### Retime

Retime is not inferred from relationship membership. Any dependent retime requires explicit
action semantics and temporal mapping support.

### Conflicts

If multiple relationships require incompatible outcomes for the same object:

```text
CONFLICT → REVIEW
```

Do not choose an implicit relationship priority.

### Cycles

Relationship propagation must never be recursive side effects.

Compute closure from the immutable base snapshot, derive a finite expected action set,
deduplicate, detect cycles/conflicts, and compile one plan.

Cycle or ambiguous outcome → `REVIEW`.

## Change policy

These rules are deliberately conservative. Real Resolve behavior, professional workflow
evidence, or complex timeline cases may require refinement.

Changes are allowed only through Chat Architecture Review and must be recorded as an ADR.
No later implementation may silently weaken these defaults.

## Still open

- per-relationship cardinality
- exact role constraints by relationship type
- fragment rebinding algorithms after split/delete
- Resolve native linked-selection mapping
- production sync offset/reference representation
- multi-track ripple interaction
- Compound / Multicam / nested timelines
- subtitle / marker / effect adapters
