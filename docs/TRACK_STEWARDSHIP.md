# Track Stewardship v1

Status: **Accepted product/architecture baseline**

## Principle

AI may assist editing inside the user's existing NLE, but it must not silently reorganize the
editor's workspace. Track/layer organization is part of editorial intent and working memory.

## Rules

### Existing Structure Is User-Owned

Without an explicit approved topology change, do not:

- delete tracks
- rename or repurpose tracks
- reorder tracks
- move existing objects to another track
- treat an existing track as AI-owned scratch space

### Reuse Before Create, But Only When Safe

Prefer reuse only when the destination track's role is sufficiently established and placement
is compatible. If the role or stacking semantics are ambiguous, REVIEW instead of guessing.

### Empty Does Not Mean Disposable

An empty track may be intentionally reserved. Never auto-delete a track solely because it is empty.

### AI-Created Becomes User-Owned

Once an AI-created track/object is committed into the editable project, treat it exactly like
user project state. Human edits to it win. AI may not reset/remove it merely because it created it.

### Explicit Selection Is Strong Intent

A user selecting a track and asking to place content there is a strong intent signal. It does not
bypass Safety Core checks such as locks, protected ranges, topology, or relationship constraints.

### Track Creation Is a Topology Change

Track additions/removals/reorders/repurposing and object membership moves must be included in
the expected topology change and verified against actual topology.

### Stacking Ambiguity → REVIEW

Layer order affects compositing and audio behavior. If a new track's correct stacking position is
unclear, do not place it at an arbitrary top/bottom index.

## Track role confidence

Future TrackRole work should separate physical identity from semantic use:

```text
Track ID   = V2
Track Type = VIDEO
Track Role = BROLL
```

Role confidence should prefer, in order:

1. explicit user instruction
2. project-approved role metadata
3. repeated confirmed project behavior
4. structured metadata
5. track name
6. position-only inference

Track names/positions alone are never authoritative.

## Change policy

These are conservative v1 defaults. Refinement is allowed only through Chat Product/Architecture
Review with new tests/ADR updates. Implementations may not weaken them silently.
