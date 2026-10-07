# Native Capability Probe & Effect Model Evidence Contract v1

Status: **Accepted Chat Product/Architecture baseline**

## Purpose

Define how real Resolve/runtime behavior can produce evidence for the execution-grade claims consumed
by ADR-028:

- NativeCapabilityStatus == SUPPORTED_VERIFIED
- EffectModelStatus == VERIFIED
- execution-grade target identity evidence
- verified post-read capability
- verified reconciliation evidence
- optional fragment-correspondence evidence

This contract defines evidence and derivation semantics. It does not run Resolve probes itself.

Core principle:

> A native capability becomes trusted not because the API exists or returns success, but because
> repeatable, isolated, independently observed evidence proves its exact semantic effects for the
> exact runtime profile.

## Probe and production execution are separate

Capability probes are not production editing.

A probe may discover native semantics. Production execution may only consume already-verified
capability/effect evidence.

Probe results never directly authorize user-project mutation.

## Destructive probe isolation

Destructive native capability probes must run only in an isolated disposable environment.

Allowed examples include:

- a dedicated test project
- a disposable duplicated test timeline
- a fixture reconstructed from a canonical test asset set

Destructive probe execution on the user's authoritative working timeline is forbidden.

## Sacrificial fixture contract

Every probe run uses a versioned ProbeFixture defining a known initial state.

Recommended fields:

- fixture_ref
- fixture_version
- expected initial snapshot/state
- required tracks
- required placements
- optional marker/subtitle/transition/effect/keyframe conditions
- fixture class
- fixture contract version

Before a destructive probe begins, the observed pre-state must match the fixture's required initial
state.

Dirty/stale fixture -> probe does not run.

Do not silently repair a dirty fixture and continue the same qualifying run.

## Independent clean runs

Qualifying repeated probes should begin from independently reconstructed/verified clean initial
states.

Do not assume Undo restored a clean fixture unless rollback itself is independently verified.

## RuntimeProfile binding

Every probe/effect/capability record is bound to an explicit RuntimeProfile.

Recommended fields:

- resolve version
- resolve build when available
- platform
- architecture when relevant
- adapter name/version
- API surface/profile version
- session characteristics where evidence is session-local
- runtime profile contract version

Evidence from one profile is not automatically promoted to another profile.

## Native primitive contract identity

Capability identity should use a versioned logical native primitive identifier, not only a raw API
method name.

Examples:

- NATIVE_RANGE_REMOVE_CANDIDATE
- NATIVE_TRANSLATE_CANDIDATE
- NATIVE_COMPOUND_RIPPLE_CANDIDATE

The actual API method/invocation may be recorded as provenance.

## Typed probe invocation

Probe harnesses use bounded typed NativeInvocationSpec records.

Arbitrary LLM-generated Python/Lua/script strings are not permitted in probe execution.

ADR-006 applies to probe harnesses as well as production execution.

## Probe lifecycle

A destructive qualifying probe follows:

```text
Canonical Fixture
→ Pre-State Verification
→ Fresh Pre Snapshot
→ Typed Native Probe Invocation
→ Fresh Post Snapshot
→ Observed Native Diff
→ Evidence Record
```

A native return value alone is not evidence of semantic success.

## ProbeObservationScope

Probe observation must cover the native primitive's possible safety-relevant effects.

Scope may include:

- tracks
- placements
- topology
- track states
- markers
- subtitles/captions
- transitions
- effects
- keyframes
- relationship-relevant state

Scope completeness is explicit:

- COMPLETE
- PARTIAL
- UNKNOWN

Only COMPLETE scope evidence may support VERIFIED destructive semantics.

## Side-effect blindness is forbidden

A probe may not inspect only the intended target effects while ignoring possible collateral state.

Example:

If a native operation correctly removes A and moves B/C but also moves subtitle S, the subtitle
change must appear in observed evidence.

Expected/hypothesized effects never filter out actual observed effects.

## Probe hypothesis vs observation

ProbeHypothesis and ProbeObservedDiff are separate artifacts.

ObservedDiff is derived from independently observed before/after state and may contradict the
hypothesis.

Never copy the hypothesis into the result when native state observation is unavailable.

## NativeEffectEvidence

Recommended immutable fields:

- evidence_ref
- probe_case_ref
- runtime_profile_ref
- fixture_ref/version
- pre_snapshot_ref
- post_snapshot_ref
- observed_diff
- observation_scope
- scope_completeness
- native result metadata
- identity/correspondence evidence refs
- harness/adapter provenance
- evidence contract version

Evidence status should distinguish at least:

- VALID
- STALE
- INCOMPLETE
- CONFLICTING
- INVALID

## Single-run evidence cannot create VERIFIED destructive capability

A single successful destructive probe observation is insufficient to derive:

- SUPPORTED_VERIFIED
- VERIFIED NativeEffectModel

A repeatability requirement is mandatory.

The exact minimum run count remains a versioned verification-policy decision.

## Repeatability

Qualifying evidence for one effect model must be repeatable under the same relevant:

- runtime profile
- fixture class/conditions
- primitive/invocation contract
- observation contract

For deterministic editing primitives, qualifying semantic effect sets must match exactly.

## Conflict handling

Conflicting qualifying probe evidence is never hidden.

Do not use:

- latest-wins
- majority vote
- confidence averaging
- producer priority

A semantic conflict yields EffectModelStatus.CONFLICTING and blocks destructive eligibility.

A future verification policy may require zero conflicts; v1 architecture does not permit a conflict
to be converted into VERIFIED by ranking evidence.

## CapabilityVerificationPolicy

A versioned policy controls quantitative/coverage requirements without changing this evidence model.

Recommended fields:

- policy_ref/version
- minimum successful repetitions
- required fixture classes
- required challenge classes
- required scope completeness
- allowed conflict count
- runtime-profile binding rules
- required identity/post-read/reconciliation evidence classes

Concrete numeric thresholds and final fixture matrices remain OPEN-018 until separately approved.

## NativeEffectModel derivation

NativeEffectModel is derived from qualifying evidence, not directly self-reported by the adapter.

Recommended fields:

- effect_model_ref
- runtime_profile_ref
- primitive kind
- invocation contract ref
- exact semantic effect set
- possible side-effect scope
- supporting evidence refs
- verification policy ref/version
- status
- model contract version

EffectModelStatus:

- VERIFIED
- UNVERIFIED
- CONFLICTING
- STALE
- UNKNOWN

## VERIFIED effect-model minimum conditions

At minimum:

1. exact runtime-profile binding
2. verified clean fixture preconditions
3. COMPLETE observation scope
4. repeatability policy satisfied
5. all qualifying runs agree on exact effect semantics
6. no unmodeled side effects
7. target identity/correspondence evidence sufficient
8. post-read evidence sufficient
9. reconciliation evidence sufficient
10. verification policy satisfied

Failure of any required condition prevents VERIFIED.

## Capability derivation

NativeCapabilityStatus remains:

- SUPPORTED_VERIFIED
- SUPPORTED_UNVERIFIED
- UNSUPPORTED
- UNKNOWN

SUPPORTED_VERIFIED requires qualifying evidence consistent with ADR-028, including the required
VERIFIED effect model and associated execution-grade observation/identity capabilities.

Examples:

- method/API exists, call accepted -> at most SUPPORTED_UNVERIFIED
- no evidence collected -> UNKNOWN
- known unavailable/unsupported on profile -> UNSUPPORTED
- repeatable exact observed semantics + required evidence/policy -> may derive SUPPORTED_VERIFIED

## Adapter self-report is not authority

An adapter declaration such as "supports ripple" or a successful native return code is provenance,
not sufficient verification evidence.

Capability status is derived from observed evidence.

## Post-read capability evidence

Post-read capability is independently verified.

Question:

> Can the system independently observe all state required to determine whether the approved
> postcondition occurred?

A mutation primitive cannot become production-destructive READY if the required postcondition cannot
be independently read.

## Reconciliation evidence

ADR-027 requires OUTCOME_UNKNOWN reconciliation.

Recommended ReconciliationEvidence fields:

- evidence_ref
- primitive kind
- runtime profile
- observable signature if applied
- observable signature if not applied
- ambiguous signatures
- supporting probe refs
- required post-read capabilities
- status
- contract version

ReconciliationStatus:

- VERIFIED
- AMBIGUOUS
- UNVERIFIED
- STALE

Only VERIFIED may satisfy ADR-028 execution readiness.

## Identity capability evidence

Identity evidence must prove semantic correspondence, not merely expose an ID-shaped value.

Recommended IdentityCapabilityEvidence fields:

- evidence_ref
- runtime profile
- native locator kind
- claimed IdentityScope
- pre/post identity observations
- mutation cases tested
- session/reload boundary conditions
- correspondence outcome
- supporting evidence refs
- contract version

### PERSISTENT_VERIFIED

Requires actual persistence/correspondence evidence across the boundaries the product claims to
support.

A UUID-like string alone is not proof.

### SESSION_LOCAL_VERIFIED

Requires demonstrated correspondence inside the same verified session and becomes stale when the
session changes.

### SNAPSHOT_LOCAL

May remain valid for observation but does not become destructive target authority under ADR-028.

## Fragment correspondence evidence

If lowering relies on split/fragment-producing behavior, probe evidence must explicitly establish
fragment correspondence.

Recommended statuses:

- VERIFIED
- AMBIGUOUS
- UNSUPPORTED
- UNKNOWN

Returned-list order, filename similarity, current position, or first-match behavior are not proof
unless explicitly covered by the verified runtime contract.

## Probe containment failure

Unexpected mutation outside the complete intended probe observation/containment scope is a probe
failure.

Represent explicitly, e.g.:

- CONTAINMENT_FAILURE

Such evidence cannot support a VERIFIED effect model.

## ProbeRunResult

Suggested statuses:

- PASS_OBSERVED
- FAIL_OBSERVED
- INCONCLUSIVE
- STALE
- INVALID_FIXTURE
- CONTAINMENT_FAILURE

A ProbeRunResult status is not itself a capability status.

Multiple qualifying runs are aggregated under CapabilityVerificationPolicy.

## Evidence immutability

Probe evidence is immutable.

Do not rewrite an earlier observation from FAIL/INCONCLUSIVE to PASS after later interpretation.

Derive a new model/evidence artifact instead.

## Evidence provenance

Record at least:

- probe harness version
- adapter version
- Resolve version/build
- platform
- fixture version
- observation contract version
- invocation contract version
- evidence/model contract version

## Invalidation

Evidence/model invalidation must be explicit.

At minimum, changes to these may stale relevant evidence/models:

- Resolve version/build
- adapter version affecting mutation/read semantics
- platform
- primitive invocation contract
- observation contract
- effect-model contract
- verification policy version

Session-bound identity evidence is always invalidated by a session change.

Capability/effect semantics and session-local identity may have different invalidation scopes.

## Profile-specific conflicts stay separate

If Windows and macOS differ, maintain profile-specific evidence/models.

Do not merge conflicting profiles into one global semantic model.

## Capability probe is not editorial benchmarking

Probe question:

> What does this native operation actually change?

Editorial benchmark question:

> Is this pause edit good?

These remain separate evidence domains.

## Initial probe program ordering

Recommended sequence:

1. read-only capability mapping
2. identity/locator stability
3. isolated single-operation mutation
4. compound/ripple side-effect mapping
5. OUTCOME_UNKNOWN reconciliation
6. fragment correspondence where required
7. rollback/Undo behavior

Read capability comes before mutation because mutation semantics cannot be verified without an
independent observation path.

## TASK-018 boundary

TASK-018 may implement pure immutable evidence/derivation foundation only:

- RuntimeProfile
- ProbeFixture / fixture classes
- NativeInvocationSpec
- ProbeCase
- ProbeObservationScope / ScopeCompleteness
- ProbeRunResult
- NativeEffectEvidence
- CapabilityVerificationPolicy
- NativeEffectModel / EffectModelStatus derivation
- NativeCapabilityStatus derivation
- ReconciliationEvidence
- IdentityCapabilityEvidence
- FragmentCorrespondenceEvidence
- stale/conflict/incomplete derivation
- deterministic/immutable tests

TASK-018 must not implement:

- actual Resolve probe execution
- actual destructive mutation
- actual adapter target lookup
- actual post-read capture
- actual rollback
- actual retry
- production capability enablement
- release-policy numeric thresholds not yet approved

## Accepted v1 decisions

1. Destructive capability probes never run on the authoritative production/working timeline.
2. Destructive probes require isolated disposable canonical fixtures with verified pre-state.
3. A single successful probe cannot create SUPPORTED_VERIFIED or VERIFIED EffectModel.
4. Repeatability is mandatory for destructive verification.
5. Observation scope must be COMPLETE to support VERIFIED destructive semantics.
6. Partial/unknown scope evidence cannot create VERIFIED.
7. Native observed side effects are recorded even when they contradict the hypothesis.
8. Conflicts are retained as CONFLICTING; no latest-wins/majority-vote/ranking.
9. Any qualifying conflict blocks destructive VERIFIED eligibility.
10. Capability/effect evidence is bound to exact runtime profile and versioned contracts.
11. API existence/return success is insufficient verification evidence.
12. Verified post-read capability is independently evidenced.
13. Verified reconciliation capability is independently evidenced.
14. Identity verification requires observed correspondence, not ID shape.
15. Fragment correspondence is explicit evidence; no order/name/position heuristics.
16. Probe runs are immutable and should begin from independently clean fixture states.
17. Runtime/profile/contract changes stale relevant evidence.
18. Capability probes are separate from editorial-quality evaluation.

## Final principle

> Trust native behavior only after isolated, repeatable, complete observation proves its exact
> effects for the exact runtime profile.
