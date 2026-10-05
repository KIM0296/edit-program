# TASK-002 - INV-002 / INV-003

Status: implementation authorized by Chat Gate Review, 2026-10-05.
Branch: feat/task-002-inv002-inv003. Deliver through PR; merge requires separate Gate.

## Approved basis

TASK-001 implementation approved with changes. DECISIONS.md ADR-008..012 govern
this task; docs/TIMELINE_SAFETY.md INV-002/003 remain the safety contract.
Record the ADRs, correct documentation, and add Python 3.11 CI before implementation.

## Scope

Extend the existing one-track, 1:1, ripple-DELETE fake only:
- INV-002: retain unrequested media identity, source intervals and content order.
- INV-003: immutable ProtectedRange with HARD_LOCK, including ripple displacement.
- All ranges are integer [start, end); touching end boundaries do not overlap.
- Reject direct overlap OR any earlier delete that would shift a protected interval,
  including a protected interval in a gap, before invoking any simulated delete.
- Protection after a delete cannot be bypassed by approving ripple displacement.
- A delete beginning at the protected end is permitted if other checks pass.
- Validate all commands and all protections before mutation, regardless of command order.
- Version increments once when the resulting nonempty plan is committed to fake state;
  all rejection paths leave snapshot/version unchanged. Empty plan remains a no-op.

## Minimal internal representation

ProtectedRange stores track_id, frame_range and a fixed HARD_LOCK policy on the snapshot.
No override, scope expansion, or Resolve persistence is introduced.
EditPlan adds approved_ripple_displacements: an immutable tuple of track_id,
original surviving timeline interval and signed delta_frames. Coordinates refer to the
base snapshot. It must match the exact calculated nonzero displacement set: missing,
extra, duplicate, wrong-range or wrong-delta entries reject before simulated deletion.
The existing ripple flag alone is not sufficient authorization of the affected content.
A pure proposal helper calculates these entries for a caller to review/include explicitly;
apply never fills in approvals. This is an internal additive model, not an external IR schema.
After simulation, compare every surviving fragment's identity, source range, order and
position against the independent base-snapshot expectation before publishing fake state.
This scoped comparison is not a general postflight engine or production rollback.

## Test-first acceptance criteria

- [x] Existing TASK-001 tests remain green, with explicit displacement approval where needed.
- [x] Tests first demonstrate missing INV-002 enforcement and HARD_LOCK behavior.
- [x] Mixed media, repeated placements, gaps, multiple deletes and reverse order preserve
      the full ordered (placement, media, source frame, timeline frame) oracle.
- [x] Missing/incorrect/extra ripple approval rejects before mutation.
- [x] Corrupted simulated media/source/order/position results are rejected, not published.
- [x] Direct inside/partial/covering HARD_LOCK edits reject before any delete.
- [x] Earlier ripple, including end-touching before protection, rejects before any delete.
- [x] Boundary after protection and unrelated later edits succeed with protection unchanged.
- [x] Multiple protections, multi-command late violation and gap protection are covered.
- [x] Rejection leaves identical snapshot/version; successful multi-command plan adds one version.
- [x] Python 3.11 GitHub Actions runs pytest, ruff, mypy and passes all implemented invariants.
- [x] Update status/limitations/decisions, open PR and submit standard report for Chat Gate.

## Explicit exclusions

Resolve API, A/V relationships, retime, transitions, transaction/rollback engine,
AI, UI, multi-track ripple, cross-clip or gap-spanning deletion, overlapping requests,
production persistent identity. INV-004..018 are not certified by this task.

## Verification

python -m pytest -q
python -m ruff check src tests
python -m mypy

CI: Python 3.11, ubuntu-latest, pull_request and push on main/task branches.
The one opt-in naive intentional failure stays skipped by default; the normal
naive regression always runs. Reproduction command remains in IMPLEMENTATION_STATUS.md.

Implementation and CI complete; Chat Gate pending. PR #1. See docs/reports/TASK_002_COMPLETION.md.
