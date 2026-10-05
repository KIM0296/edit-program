# Parallel Editing & Human Priority v1

Status: **Accepted product/architecture baseline**

## Goal

AI assistance should reduce editor idle time. The editor should not be forced to wait while AI
analyzes or builds candidates.

## Model

```text
              Immutable Base Snapshot
                     /       \
                 Human       AI
                Working   Shadow Candidate
                     \       /
                   Conflict / Stale Check
                         |
                    Verified Commit
```

## Rules

### Never block the editor by default

Analysis and candidate building are read-only with respect to authoritative working state.

### Human edit wins

If the human modifies data that an AI candidate depends on, mark the candidate dirty/stale.
Do not overwrite or silently rebase the human change.

### Soft work lease

AI may advertise its intended scope, but this is not a hard lock. The human may continue editing.
Human changes may invalidate some or all of the candidate.

### Minimal commit lock

If an exclusive write window is required, restrict it to the smallest affected scope and shortest
possible apply + postflight verification period.

### Incremental recompute

When feasible, recompute only affected dependency scope rather than restarting unrelated analysis.

## Conflict classes

- GREEN: unrelated work / different timeline / independent scope.
- YELLOW: dependency may be affected; candidate refresh may be required.
- RED: primary target, ripple, retime, topology or relationship change directly invalidates plan.

These classifications are product guidance, not yet executable rules.

## Metrics

Track:
- editor idle time caused by AI
- conflict rework
- candidate invalidation/recompute rate
- net time saved

The objective is not only fast AI execution, but minimal human waiting and minimal AI-induced rework.

## TASK-006 conservative concurrency subset

The scope-aware goals and conflict colors above are future product guidance. TASK-006
has no scope analysis, actual observer, lock, lease, watcher, recompute or coordinator.
Any source timeline identity/version mismatch makes the candidate STALE. Even an edit
believed to be outside the candidate's region gets no exemption in this foundation.
DIRTY has no separate approved contract and is deferred under OPEN-008.

WorkPhase is descriptive ANALYZING / BUILDING_CANDIDATE / READY metadata. Phase changes
do not authorize application or restore validity. A human-version observation is explicit
caller input for the currently authoritative timeline; it does not switch the working
pointer to a preview timeline. Live observation ordering/provenance and commit-time
concurrency protection require future approved contracts.

[Attention Economy v1](PRODUCT_SPEC.md#attention-economy-v1-approved-task-006-product-notes)
is documentation only; no metrics, notification or batching UI is introduced.
