# TASK-018 — Native Capability Probe Evidence Foundation

Status: **IMPLEMENTED ? Chat Gate pending; TASK-017 approval/merge confirmed by user**

Basis:
- ADR-006 LLM Emits IR Only
- ADR-022 Read-only Snapshot / IdentityScope
- ADR-027 Transaction & Postflight
- ADR-028 Validated Execution IR
- ADR-029 Native Capability Probe & Effect Model Evidence v1

## Purpose

Implement a pure immutable evidence model and derivation foundation for future Resolve capability
probes.

No Resolve probe is actually executed.

## Mandatory architecture decisions

1. Destructive probe evidence may only represent isolated disposable fixture runs.
2. Production/authoritative timeline probes are invalid.
3. One successful run cannot derive VERIFIED/SUPPORTED_VERIFIED.
4. Repeatability policy is mandatory.
5. Only COMPLETE observation scope may support VERIFIED destructive semantics.
6. PARTIAL/UNKNOWN scope blocks VERIFIED.
7. Conflicting qualifying evidence -> CONFLICTING.
8. No latest-wins/majority-vote/ranking.
9. Capability/effect evidence is exact RuntimeProfile-bound.
10. API existence/native success bool is not sufficient verification.
11. Post-read/reconciliation/identity evidence are independent required evidence classes.
12. Fragment correspondence uses explicit evidence only.
13. Evidence is immutable.
14. ADR-030 is authoritative for v1 repetition budgets, fixture/challenge coverage and hard qualification values.

## Required domain

At minimum:

- RuntimeProfile
- ProbeFixture
- ProbeFixtureClass
- ProbeObservationScope
- ScopeCompleteness
- NativeInvocationSpec
- ProbeCase
- ProbeRunStatus
- ProbeRunResult
- NativeEffectEvidence
- EvidenceStatus
- CapabilityVerificationPolicy
- EffectModelStatus
- NativeEffectModel
- NativeCapabilityStatus
- ReconciliationStatus / ReconciliationEvidence
- IdentityCapabilityEvidence
- FragmentEvidenceStatus / FragmentCorrespondenceEvidence
- pure qualification/aggregation/derivation functions

## Fixture validity

A qualifying destructive run must state that:

- fixture is disposable/isolated
- observed pre-state matches canonical fixture state
- fixture version matches probe case
- no authoritative production timeline is used

Invalid/dirty fixture evidence cannot qualify.

Do not repair a dirty fixture inside derivation logic.

## Runtime profile

Bind evidence to explicit profile fields including at least adapter version, Resolve version/profile,
platform and versioned contracts.

Mixed profiles must not be aggregated into one VERIFIED model.

Profile mismatch/staleness must be explicit.

## Scope completeness

ScopeCompleteness exactly distinguishes:

- COMPLETE
- PARTIAL
- UNKNOWN

Only COMPLETE evidence may qualify toward a VERIFIED destructive model.

## Repeatability policy

CapabilityVerificationPolicy is explicit input.

It may include:

- minimum_successful_repetitions
- required fixture classes
- required challenge classes
- allowed_conflict_count
- required scope completeness
- required evidence classes
- profile-binding rules
- policy version

ADR-030 supplies the mandatory v1 policy values:
- TRANSLATE_PLACEMENT: 20 minimum positive runs (4 classes × 5)
- REMOVE_RANGE: 30 (6 × 5)
- COMPOUND_RIPPLE: 50 (10 × 5)
- each applicable mandatory challenge class: 3 additional clean runs
- conflicts/unexpected side effects/containment failures/ambiguous targets: 0 allowed
- scope COMPLETE, post-read VERIFIED, reconciliation VERIFIED, execution-grade identity required.

TASK-018 must not weaken these values.

## Effect evidence

NativeEffectEvidence records observed semantics independently from the probe hypothesis.

Do not derive observed effect sets from expected/hypothesized effects.

Qualification should fail closed when required observed data is missing.

## Effect-model derivation

At minimum:

- no qualifying evidence -> UNKNOWN/UNVERIFIED
- insufficient repetitions/coverage -> UNVERIFIED
- any qualifying semantic conflict -> CONFLICTING
- stale profile/evidence -> STALE
- policy fully satisfied with exact agreeing effect sets -> VERIFIED

A conflict cannot be overridden by support count or recency.

## Capability derivation

SUPPORTED_VERIFIED may only derive from the full approved evidence conditions, including a VERIFIED
effect model and any policy-required post-read/identity/reconciliation evidence.

API existence/call acceptance only -> at most SUPPORTED_UNVERIFIED.

No evidence -> UNKNOWN.

Known unavailable -> UNSUPPORTED.

## Post-read evidence

Represent whether required state can be independently observed.

Do not conflate mutation support with post-read support.

## Reconciliation evidence

Represent applied-vs-not-applied observable signatures and ambiguous cases.

Only VERIFIED reconciliation may satisfy future ADR-028 readiness.

## Identity evidence

Do not upgrade to PERSISTENT_VERIFIED or SESSION_LOCAL_VERIFIED based on identifier shape/string.

Require caller-supplied observed correspondence evidence.

Session-local evidence must bind a session and stale on session change.

## Fragment evidence

Statuses at least:

- VERIFIED
- AMBIGUOUS
- UNSUPPORTED
- UNKNOWN

No fragment ordering/name/position heuristic.

## Required tests

At minimum prove:

1. immutable/frozen nested values
2. defensive collection copies
3. destructive probe marked production/authoritative -> invalid/nonqualifying
4. isolated disposable fixture can qualify structurally
5. dirty/precondition-mismatch fixture cannot qualify
6. exact runtime-profile binding
7. mixed profiles do not aggregate to VERIFIED
8. ScopeCompleteness enum exact
9. COMPLETE required for verification
10. PARTIAL blocks VERIFIED
11. UNKNOWN scope blocks VERIFIED
12. one successful run cannot produce VERIFIED
13. repeatability policy explicitly required
14. insufficient repetition count -> UNVERIFIED
15. required fixture class omission -> UNVERIFIED
16. required challenge class omission -> UNVERIFIED
17. exact repeated effect equality can qualify
18. conflicting effect sets -> CONFLICTING
19. conflict never latest-wins
20. conflict never majority-vote
21. support count cannot override conflict
22. recency cannot override conflict
23. hypothesis differs from observed effect -> observed effect retained
24. unexpected observed side effect retained
25. containment failure cannot support VERIFIED
26. API success bool alone cannot support VERIFIED
27. evidence provenance/runtime versions required
28. stale Resolve version -> stale/nonqualifying
29. stale adapter semantics version -> stale/nonqualifying
30. stale observation/invocation contract -> stale/nonqualifying
31. VERIFIED effect model requires policy satisfaction
32. NativeCapability SUPPORTED_VERIFIED requires VERIFIED effect model
33. method exists/call accepted only -> max SUPPORTED_UNVERIFIED
34. no evidence -> UNKNOWN
35. known unavailable -> UNSUPPORTED
36. post-read evidence separate from mutation evidence
37. missing required post-read evidence blocks SUPPORTED_VERIFIED
38. reconciliation evidence statuses exact
39. ambiguous reconciliation blocks future verified readiness
40. identity evidence does not trust UUID-like/string identifiers
41. SESSION_LOCAL evidence requires session binding
42. session change stales session-local identity evidence
43. PERSISTENT verification requires caller-supplied cross-boundary correspondence evidence
44. fragment statuses exact
45. ambiguous fragment evidence not VERIFIED
46. no returned-order/name/position rebinding heuristic
47. independent clean-run metadata retained
48. evidence immutable; reclassification creates new derived artifact
49. no Resolve API call
50. no actual mutation
51. no actual post-read capture
52. no rollback
53. no retry
54. no production capability enablement
55. TASK-001..017 regression remains green

## Explicitly out of scope

- actual Resolve probe harness
- actual destructive capability probe
- actual read-only probe capture
- actual target lookup
- actual mutation
- rollback/Undo
- retry/recovery orchestration
- release gate policy
- production executor enablement

## ApplicabilityDomain

Model explicit applicability conditions. Conflict inside the declared domain is CONFLICTING.
Outside-domain behavior remains UNSUPPORTED until separately verified. Do not silently narrow the
domain after a failing qualifying run.

## Efficiency policy

Full probe suites are development/release/update validation, not ordinary editor runtime work.
Verified profile evidence is reusable until stale, and TASK-018 must not add manual production-editor
capability-probe steps.

## Workflow

1. Do not start until TASK-017 is Chat APPROVED and merged unless Chat explicitly reorders work.
2. Start from then-current main.
3. Treat ADR-029, ADR-030 and this spec as authoritative.
4. Red-first tests.
6. Implement pure immutable evidence/derivation foundation.
7. Full regression.
8. Python 3.11 CI / Ruff / strict mypy.
9. Write docs/reports/TASK_018_COMPLETION.md.
10. Open PR and request Chat Gate.
11. Do not merge or start a probe harness automatically.

## Success definition

Represent future native probe evidence so that destructive capability can become verified only from
isolated, repeatable, complete, conflict-free, exact-profile evidence, without running Resolve or
inventing verification thresholds.

## TASK-018 implementation notes (before code)

- New probe-evidence types do not silently convert TASK-017 EffectModelStatus into reconciliation
  or fragment status. ReconciliationStatus and FragmentEvidenceStatus are independent enums.
  No bridge to production lowering/executor is introduced.
- ADR-030 v1 policy fixes positive classes and counts. All five challenge applicability declarations
  are explicit in the immutable domain; each in-domain challenge needs three additional runs.
  Outside-domain runs remain recorded and unsupported, never positive-budget substitutes.
- A run stores its full declared domain and profile. Aggregation of differently declared domains
  fails closed, preventing rebucketing an existing failure by silently narrowing its domain.
- Raw canonical/pre/post subject observations use explicit typed fields and opaque structure refs.
  Pure observed changes retain every before/after difference, separately from the hypothesis.
  Exact equality uses complete supplied values; no cross-fixture role/identity normalization is inferred.
- Independent run/fixture-instance refs are supplied facts. Duplicate IDs are rejected. The immutable
  corpus appends new runs and retains failures; persistence/tamper-proof provenance is not implemented.
- Runtime profile excludes session so effect evidence can be reused; session-bound identity is
  independently checked against caller-supplied current session. There is no per-edit probe requirement.
