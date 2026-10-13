# TRUST-001 — Exact Approval Binding and Independent Primary Verification

Qualification: CODE_COMPLETE / TEST_ONLY_SUPPORT, not native qualification.
PR review candidate only. No merge; OBS-001 has not started.

## Base and boundary

- Base main: `4f4e72429144eabfb3c71e392af2cf0efe5cd809`
- Base tree: `8fa0799c3795eade0265bcd5f8ac550cd3a4c2a8`
- Branch: `feature/trust001-exact-binding`
- Worktree: `C:/Users/c/source/repos/edit-program-trust001`

Exact repository allowlist (18 files):

1. `src/davinci_ai_editor/trust_evidence.py`
2. `src/davinci_ai_editor/orchestration.py`
3. `src/davinci_ai_editor/expected_diff.py`
4. `src/davinci_ai_editor/transaction.py`
5. `src/davinci_ai_editor/execution_ir.py`
6. `src/davinci_ai_editor/runtime_ports.py`
7. `src/davinci_ai_editor/runtime_integration.py`
8. `tests/test_trust001.py`
9. `tests/support/trust001_fixtures.py`
10. `tests/test_orchestration.py`
11. `tests/test_expected_diff.py`
12. `tests/test_execution_ir.py`
13. `tests/test_runtime_ports.py`
14. `tests/test_runtime_integration.py`
15. `tests/test_vs001_vertical_slice.py`
16. `tests/test_transaction.py`
17. `tests/support/vs001_simulation.py`
18. `docs/TRUST_001_STATUS.md`

## P0-A: semantic approval revision

`PreparedArtifactRevision` carries namespace, artifact ID, content-addressed revision
ID, schema `prepared-semantic-v1`, canonicalization `semantic-json-v1`, SHA-256,
and content digest. Revision ID equals digest; reusing an ID with changed digest
is rejected. An approval record retains the revision and the semantic artifact.
`authorize_edit` and `admit_execution` recompute/validate semantic content; Python
object identity, candidate labels, and structural equality alone cannot authorize.
Equivalent reconstruction can use the existing approval only with the same revision
and canonical content. The digest does not authenticate the human approver.

Canonical JSON uses UTF-8, sorted string keys, compact separators, exact integers,
ordered arrays, tagged enum/dataclass fields, and explicit nulls. Floats, sets, and
opaque objects are rejected. No repr/hash/object-ID canonicalization. The semantic
manifest includes candidate identity/base/lineage, proposal revision, semantic base,
preservation/modification scope, geometry, operation/proposal, exact ExpectedDiff,
and the immutable Safety input/result evaluated for that proposal. Live runtime
locators, live readiness/currentness, future results and approval state are excluded.
Snapshot-bound Safety evidence is retained; it is not asserted to be currently fresh.

Fixed vectors:

- `{"a":1,"b":2}` ->
  `43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777`
- Existing prepared fixture semantic manifest ->
  `99803f99a7009482c83dc4608f4691bac0680b4c47e64435af27b8db30980343`

Both canonical JSON round-trip and revision-record JSON reconstruction are tested.
Future changes to semantic serialization require deliberate schema/version review.

`ArtifactBinding` in transaction.py gains the revision; ExecutionAuthorization,
TransactionDefinition, PrecommitFacts, IR targets/lowering and currentness correlation
reuse that binding. No parallel binding or approval state machine. Legacy low-level
state/IR tests without revisions remain historical structural tests; shared production
admission requires the approved revision and evidenced target correspondence.

## P0-B: actual primary observations

`RangeRemovalEffect` remains expected-only. `ActualDiff.primary_changes` is retained
only for legacy diagnostics and is ignored as proof by the public vNext verifier.

`IndependentReadEvidence` retains an actual NativeTimelineSnapshot, snapshot identity,
capture/acquisition, PRE/POST phase, read sequence and explicit order domain, coverage,
source captures, limitations, evidence domain and post-dispatch journal linkage.
Journal sequence and read sequence are different domains; they are not compared as
timestamps. A command receipt is not a capture. Fresh reads cannot reuse a capture ID.
Typed completeness is COMPLETE / PARTIAL / UNKNOWN, never a boolean shorthand.

`TargetCorrespondence` retains semantic object/revision, original read/placement,
execution read/placement, lineage captures, and result-to-origin placements/read.
For staging, original and execution timeline IDs can differ only with the explicit
retained original/staging correspondence. Execution post-read must belong to the
execution timeline. Native identity authenticity remains a producer obligation.
Record correlation is not native proof merely because it has a new string or enum.

`PrimaryResultObservation` retains exact semantic pre-state, execution pre-state,
0..N post placements, correspondence, pre/post reads, completeness and limitations.
An empty COMPLETE result is observed disappearance; an empty incomplete result is
not disappearance. TIGHTEN with expected retained content cannot MATCH zero results.

`ActualDiff` v2 carries revision, semantic/execution snapshots, primary_results,
non-primary observations and their explicit correspondence, global acquisition and
coverage evidence, and relation/topology evidence. No production algorithm generates
observed after-values from ExpectedDiff. The verifier computes expected interval
coverage only as a comparison target.

Current verification is deliberately narrow: identity 1x source mapping, exact frame
rates/ranges and explicitly covered placements. It compares source coverage/order,
timeline coverage/order, media, track, duplicate/missing/overlapping fragments,
non-primary movement/preservation and extra captured objects. A supported single
placement or a correct split can MATCH. Duration equality alone cannot. Unsupported
mapping/unknown evidence does not become success. Proven mismatches remain diagnosed;
incomplete evidence is UNVERIFIED. No implicit frame tolerance.

`DiffVerificationResult.evidence_domain` preserves TEST_ONLY_SUPPORT versus producer
assertion/unqualified evidence. A synthetic MATCH/VERIFIED_COMMITTED in a pure contract
test is still synthetic; neither enum is NATIVE_MUTATION_QUALIFIED or VERIFIED_LIVE.

## Runtime composition

Exactly five Protocol responsibility families remain. Resolution supplies correspondence
bound to the approved revision. observe_postflight now receives admitted targets and
the exact Transaction as keyword-only context, in addition to scope/base observation.
Integration retains these through admission evidence/call records and validates the
returned raw read capture against the port receipt. Orchestration checks the admitted
target/pre-read and post-read journal correlation before committing or promoting.
Independent read failure yields typed uncertainty with the latest journal preserved.
No retry, event reconstruction, auto-reapproval, silent rebase or native execution.

Transaction and Candidate Authority remain their existing lifecycle authorities.
Safety policy is unchanged. Authority reacquisition, separate promotion acquisition,
historical commit preservation, and separate durable publication remain unchanged.

## Intentional semantic migrations

1. Equal reference labels no longer imply equal ArtifactBinding: revision changes
   when proposal/geometry/compiler semantic content changes. Two old orchestration
   assertions were updated accordingly.
2. Public `verify_diff` requires revision and independent primary reads. Missing
   legacy evidence is UNVERIFIED, even if expected-shaped effects match.
3. Historical `test_expected_diff`, VS-001 simulation/vertical and the port's old
   independence test explicitly use `_verify_legacy_semantics`. This private
   historical comparator is not called by production finalization/promotion and
   yields unqualified evidence. Existing journals are not rewritten.
4. Current orchestration positive fixtures now use independent simulator pre/post
   state captures. Primary mismatch tests mutate observed state (complete zero
   result), not diagnostic expected-shaped primary_changes.
5. New pure evidence-module imports are explicitly added to AST allowlists; no
   native, transport, UI, persistence or execution imports are permitted.
6. Read-producing test ports accept admitted target/journal context; integration
   receipts retain the actual post capture rather than a scalar placeholder.

## Validation receipts

Local final receipts:

- TRUST-001 adversarial tests: 34 cases (included in the targeted run).
- Required targeted suite (TRUST, orchestration, expected_diff, execution_ir,
  runtime_ports, runtime_integration): **420 passed**.
- Full regression: **1,773 passed / 1 skipped**. Skip is the existing opt-in
  intentional red test at `tests/test_naive_inv001.py:27`.
- `ruff check .`: passed.
- Repository `mypy`: passed, 39 source files.
- Explicit `mypy --strict --follow-untyped-imports --explicit-package-bases` over
  all seven changed production modules plus seven typed changed/new test/support
  modules: passed, 14 files. Separately, all three new Python files passed strict.
- Tracked `git diff --check`: passed. Final staged/untracked whitespace and
  exact 18-file allowlist: passed. Initial raw no-index checking detected CRLF
  as trailing whitespace (exit 3); files were normalized to LF. Rechecking all
  four new files returned exit 1 (files differ from NUL), zero diagnostics.
  Staged whitespace check returned exit 0. No hook failure was hidden.
- CI status is reported from the remote PR run; local results are not CI claims.

The required expanded
strict command was also run against the unchanged base tree: **840 errors in the
same four legacy test modules**, both before and after this change, with zero new
normalized diagnostic signatures. The affected baseline modules are
test_safety_preflight, test_expected_diff, test_execution_ir and test_transaction.
Those historical tests were not in repository strict mypy's configured file set.
No suppression/config weakening or unrelated bulk annotation was added. Therefore
the all-changed-files strict command is explicitly NOT green; it is not reported
as passing. Repository strict and separately typed new/changed modules are checked
independently. Full before/after logs are retained outside the repository in the
local temporary `trust001-validation` directory.

## NOT_IMPLEMENTED / remaining blockers

No Resolve live read, native mutation, real staging duplication/correspondence,
native acquisition authenticity, observation-to-execution atomicity, persistent
placement identity, crash-safe journal store, exactly-once execution/persistence,
automatic retry, approval authentication service, or OBS-001 work. No classifier,
style/profile, UI, accepted-scope resolver or other NLE implementation.

OPEN-002 / OPEN-008 remain open. Real producers must retain and qualify the read and
correspondence evidence; this code cannot detect a malicious producer fabricating
an entire read capture. Provenance/digest strings do not solve authenticity. General
retime/compound result mapping is unsupported, not guessed. Human value evidence
remains unproven: no real user session or native qualification occurred in this task.

Review candidate: GO for code/contract review with the disclosed legacy strict-test
baseline; native/live use remains HOLD. Next step is Chat Gate review, not OBS-001
or merge. The expanded strict-test baseline remains an explicit validation blocker
to claiming every requested check green.
