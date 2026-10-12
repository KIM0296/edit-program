# VS-001C — test-only vertical slice

Classification: TEST_ONLY_SUPPORT. Implementation review candidate: GO.
This does not authorize production execution or native runtime validation.

## Base receipt

- Branch: `test/vs001c-shared-simulation`
- Worktree: `C:\Users\c\source\repos\edit-program-vs001c`
- Authoritative remote-main commit: `98bffaf204b1ee94636213ea9cd60bf7dfa45b75`
- Tree: `ea7a60f8d7fcddf8e81b3c92b622af70d6e7a505`
- Created clean from the supplied commit; no integration/transport working files copied.
- No commit, push, native execution, or production source modification.

## Implementation and evidence domain

`tests/support/vs001_simulation.py` defines frozen state, request, per-operation
records, receipt, and independently derived evidence. State carries the exact
NativeSnapshotRef, uniquely identified PlacementState values, and explicit track
inventory. Canonical ordering does not alter semantic facts.

The existing logical ExecutionIR operations are consumed inside a separate
SIMULATION admission boundary. Targets remain SNAPSHOT_LOCAL/UNRESOLVED for native
execution. No native validator, capability proof, or READY_FOR_EXECUTION result is
manufactured. Synthetic ActualDiff post-relation/identity correspondence refers
only to explicit immutable simulation objects; it proves no native identity.

Admission binds the complete base state and snapshot, candidate and explicit
approval, recomputed Safety PASS, diff/safety/authorization references, target
bindings, exact effect coverage, unique targets, and supported geometry. The
supported subset is one nonempty proper suffix removal and at most one exact
translation, on identity-1x placements. Overlap is rejected at admission.

All operations are validated before interpretation. Interpretation uses a private
draft; only a complete batch publishes a new immutable state. A rejected or failed
batch returns the exact original state object. Receipts distinguish attempted
evaluation, error, and NOT_ATTEMPTED; evaluated draft steps are not publication.
There is no ripple, participant discovery, range repair, or native mutation.

## Independent ActualDiff

`derive_actual(base, post, receipt, refs)` does not accept ExpectedDiff, Request,
planned ranges, deltas, or planned after-states. Correlations contain only artifact,
operation, target, scope, and geometry identifiers. The producer checks receipt
coverage and before/after correspondence, derives the removed suffix from actual
primary endpoints and source loss, and creates a new RangeRemovalEffect. It
observes every other before/post object, including unchanged, extra, and missing
objects, and records track inventory changes. Missing correspondence is incomplete
and UNVERIFIED (or yields no ActualDiff). Unrepresentable primary damage is not
repaired. Existing `verify_diff()` performs all expected-versus-actual comparison.

The transaction adapter translates receipts into the existing lifecycle events.
Only a bound postflight MATCH reaches VERIFIED_COMMITTED. Promotion rechecks the
actual run, transaction, current complete state, and existing eligibility before
RecordApplication, RecordVerification(True), and PromoteCandidate. AI post V2 is
an ApplicationRecord result, never ObserveHumanVersion.

## Fixture and outcomes

- V1 primary timeline/source `[0,420)`; pause `[300,420)`; TIGHTEN/MEDIUM.
- Retain 48; remove `[348,420)` (72); primary post timeline/source `[0,348)`.
- Downstream timeline `[420,540)` -> `[348,468)`; source `[500,620)` unchanged.
- Exact displacement -72; primary + downstream preservation scope; no topology change.
- All 17 Safety checks pass, followed by explicit candidate approval.
- Independently derived ActualDiff MATCH; transaction VERIFIED_COMMITTED.
- Historical candidate: APPLIED / VERIFIED / PROMOTED / STALE. STALE is preserved.

Required negative cases A–F pass: human V2 aborts stale without publication;
same-token changed contents reject; primary off-by-one and wrong downstream delta
mismatch; unexpected object change mismatches; invalid second operation rejects
the entire batch before any attempt. Additional cases cover discarded draft after
an evaluation failure, remaining NOT_ATTEMPTED operations, missing receipt coverage,
no approval, duplicate identity, topology mismatch, post-publication human change,
and unchanged scoped objects without implicit ripple.

## Validation

- Targeted VS-001 tests: 16 passed.
- Full pytest: 1433 passed, 2 skipped.
- Skips: host symlink privilege unavailable; opt-in intentional red invariant test.
- Ruff repository check: PASS.
- Existing strict mypy configuration: PASS, 33 files.
- Explicit strict mypy for both new Python files: PASS, 2 files.
- Tracked diff/whitespace checks: PASS; production tree unchanged.

Commands use this worktree's `src` and `tests` on PYTHONPATH. For the two new files,
MYPYPATH also includes `src` and `tests`, with `--explicit-package-bases`; no package
initializer or production configuration change is required.

## Boundaries and next gate

No FakeTimeline reuse; no changes to native IR validation, Safety, transaction,
authority, Free transport, Studio checkpoint, MCP, or Core. No native VERIFIED
evidence and no runtime responsiveness/currentness/identity-lifetime claim.
This is a synchronous immutable test harness, not a concurrency protocol,
production executor, rollback implementation, or external authority boundary.
Receipt identifiers are fixture-local and not security or currentness tokens.

No semantic contract weakening was required. Next gate may review this test-only
composition and its intentionally bounded operation subset; production execution,
additional operation shapes, and native runtime remain separate decisions.
