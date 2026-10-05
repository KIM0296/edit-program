# Candidate Authority Contract v1

Status: **Accepted product/architecture baseline**

## State separation

```text
SELECTED
→ APPROVED
→ APPLIED
→ VERIFIED
→ PROMOTED
```

These states are not interchangeable.

- SELECTED: comparison/further-edit target only.
- APPROVED: user authorizes an apply attempt.
- APPLIED: change was written to the target state.
- VERIFIED: postflight checks passed.
- PROMOTED: result becomes the default working authority for future requests.

## Candidate base

Every candidate records its base timeline ID/version. If the current Resolve state differs at apply
time, the candidate is stale.

Stale candidates are never destructively auto-rebased. Recompute against current state, show a diff,
or request review.

## Human edit precedence

Human edits after candidate creation always win. Candidate branching may continue independently
without changing the authoritative working timeline.

## Approval language

Positive feedback such as “B가 좋다” is not sufficient destructive approval. Explicit apply intent
or an equivalent UI action is required.

## Working authority

The currently visible/active Resolve timeline is not automatically the authoritative working
timeline. Switching timelines for preview/comparison must not silently promote them.

After a successful verified promotion, future requests default to that latest verified working state.
