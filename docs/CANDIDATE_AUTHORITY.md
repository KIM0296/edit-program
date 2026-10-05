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

## TASK-006 state foundation clarification

The illustrative SELECTED -> APPROVED -> APPLIED -> VERIFIED -> PROMOTED flow above
is UX vocabulary, not one combined enum. TASK-006 keeps selection, approval, validity,
application, verification, promotion and work phase as separate immutable axes.

Only an explicit approval event records approval. Selection/preview/phase changes do
not imply approval. Validity is checked against the whole supplied source identity and
version, independently of historical approval or verification. Stale candidates remain
stale and cannot be silently refreshed by branching or changing a version/phase.

Application/verification records in TASK-006 are supplied fake facts for state tests;
the module does not apply or verify anything. Promotion requires matching candidate,
source and result evidence plus a matching current result observation. WorkingAuthority
is a fake comparison context, not a settled production persistence/Resolve schema.
OPEN-002/008 retain result identity, representation, provenance and coordination.
