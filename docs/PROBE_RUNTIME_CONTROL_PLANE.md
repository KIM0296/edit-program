# Probe Environment Registry & Runtime Control Plane Contract v1

Status: **ACCEPTED — Chat Product/Architecture baseline**

## Purpose

Define the pure control-plane rules that decide whether a registered disposable probe environment
may arm exactly one bounded probe run.

This contract does not execute Resolve calls. It governs registration, generation binding, one-run
authorization, currentness, contamination, re-verification and no-further-mutation lockdown.

## Environment registration

A qualifying probe environment is represented by an immutable RegisteredProbeEnvironment containing
at least:

- environment_ref
- registry_ref / registry_generation
- probe_project_ref
- project_generation
- fixture_catalog_ref/version
- runtime_profile_ref
- harness_contract_version
- disposable = true
- isolated = true
- production = false
- authoritative = false

Project name, path, folder, sentinel text or currently active selection are never sufficient
registration authority.

A working/production/authoritative project cannot be registered as a qualifying destructive probe
environment.

## Generation semantics

Registration identity and project generation are distinct.

Rebuilding or replacing the disposable probe project creates a new project_generation.

Evidence/authorization from generation N is stale for generation N+1 even if the project display
name is unchanged.

A contaminated generation is never "cleaned" by editing it back to look correct. Either explicit
project-level re-verification succeeds when permitted by the contamination class, or a new generation
is created.

## Environment verification

Registration is necessary but not sufficient.

EnvironmentVerification binds:

- exact registration
- exact project generation
- exact RuntimeProfile
- exact fixture catalog version
- observed current project/timeline context
- environment snapshot/fingerprint ref
- verification result

Suggested result states:

- VERIFIED
- STALE
- MISMATCH
- INCOMPLETE
- CONTAMINATED

Only VERIFIED can contribute to arming.

The pure foundation validates bindings; actual Resolve truth acquisition remains TASK-020/later work.

## Harness state

Recommended process-level states:

- DISARMED
- ENVIRONMENT_VERIFIED
- FIXTURE_VERIFIED
- ARMED_FOR_ONE_RUN
- INVOCATION_ATTEMPTED
- OBSERVING
- SEALED
- QUARANTINED
- LOCKED_DOWN

There is no persistent global "destructive probes enabled" state.

## Probe lease

A qualifying run obtains one immutable ProbeLease bound to:

- environment_ref
- project_generation
- fixture_instance_ref
- probe_run_ref
- RuntimeProfile ref
- pre-snapshot ref
- observation-scope ref
- containment-envelope ref
- applicability-domain ref

Only one active qualifying lease may exist for the same fixture instance.

The lease does not lock the user's working project or prevent normal human work outside the disposable
probe fixture.

Any fixture/currentness change invalidates the lease rather than blocking the human.

## One-run authorization

ProbeRunAuthorization binds exactly:

- environment registration + project generation
- fixture instance + fixture lifecycle state
- probe case
- probe mode
- applicability domain
- primitive
- typed invocation spec
- RuntimeProfile
- pre-snapshot
- observation scope
- containment envelope
- lease
- authorization contract version

Authorization is single-use.

## Authorization consumption

The authorization is consumed when the harness attempts to cross the final pre-invocation gate.

It is also discarded/consumed when final pre-invocation validation fails.

Do not keep an old authorization reusable after:

- project/timeline switch
- profile change
- fixture snapshot mismatch
- lease invalidation
- environment generation change
- primitive/invocation mismatch
- containment-policy mismatch
- pre-invocation abort

A fresh run requires a fresh authorization.

No wall-clock TTL is required in v1; freshness is established through exact generation/profile/snapshot
bindings.

## Final pre-invocation gate

Immediately before the native invocation attempt verify all of:

1. harness not LOCKED_DOWN
2. exact registered environment
3. project generation current and eligible
4. EnvironmentVerification == VERIFIED
5. exact fixture instance is CLEAN_VERIFIED
6. fixture lease valid and unique
7. fixture/current pre-snapshot == authorized pre-snapshot
8. RuntimeProfile unchanged
9. probe case/domain unchanged
10. observation scope unchanged
11. containment envelope unchanged
12. primitive and typed invocation exactly allowlisted
13. authorization unused
14. probe mode allowed

Any failure:

- native invocation count remains zero
- authorization becomes consumed/aborted
- finding is retained
- no fallback project/fixture/primitive selection occurs

## Invocation attempt semantics

A qualifying authorization permits at most one native invocation attempt.

After the call is submitted to the native boundary, authorization remains consumed regardless of:

- SUCCEEDED response
- FAILED response
- timeout
- bridge error
- OUTCOME_UNKNOWN

No same-run destructive retry exists.

## No-further-mutation gate

The harness exposes a derived gate:

- ALLOWED
- BLOCKED

This is not a native kill/cancel primitive.

BLOCKED means no additional probe invocation may be submitted.

It does not claim an already-submitted native command can be cancelled.

BLOCKED is mandatory when:

- environment/project generation CONTAMINATED
- environment truth becomes uncertain during/after invocation
- crash/bridge loss leaves mutation state unknown
- fixture is QUARANTINED
- current environment cannot be re-established exactly

## Containment classification

ContainmentResult should distinguish at least:

### CLEAN
Observed change stayed within the declared expected/allowed envelope.

### UNEXPECTED_FIXTURE_LOCAL
Unexpected mutation occurred but observation proves it remained within the disposable fixture/project
scope and no project-level state outside the fixture changed.

Consequences:
- run non-qualifying
- fixture QUARANTINED/DISCARDED
- project generation becomes REVERIFY_REQUIRED
- no further qualifying mutation until project-level containment re-verification

### PROJECT_LEVEL_CONTAMINATION
Unexpected mutation affected state outside the fixture envelope or project baseline.

Consequences:
- run non-qualifying
- fixture QUARANTINED
- project generation CONTAMINATED
- no further qualifying mutation in that generation
- rebuild/new generation required

### ENVIRONMENT_UNCERTAIN
Observation cannot prove where mutation stopped, including bridge/crash uncertainty.

Consequences:
- run non-qualifying
- fixture QUARANTINED
- environment LOCKED_DOWN
- generation cannot resume by assumption
- explicit re-establishment/rebuild required

## Project generation status

Suggested states:

- VERIFIED_CLEAN
- REVERIFY_REQUIRED
- CONTAMINATED
- RETIRED

Rules:

- only VERIFIED_CLEAN can arm a qualifying run
- UNEXPECTED_FIXTURE_LOCAL -> REVERIFY_REQUIRED
- successful independent project-level baseline re-verification may transition REVERIFY_REQUIRED -> VERIFIED_CLEAN
- failed/unknown re-verification -> CONTAMINATED
- PROJECT_LEVEL_CONTAMINATION -> CONTAMINATED directly
- CONTAMINATED cannot return to VERIFIED_CLEAN in-place
- rebuild creates a new generation; old generation becomes RETIRED/CONTAMINATED historical evidence

## Project-level re-verification

Re-verification is observation only.

It compares the current disposable project generation against its registered project-level baseline,
excluding the discarded fixture instance only where the baseline contract explicitly permits that
fixture lifecycle.

It may never "repair" state.

## Crash rules

### Before invocation submission

- authorization consumed/aborted
- no mutation inferred
- fixture must be re-verified before a different run may use it

### During/after invocation submission

- fixture -> QUARANTINED
- no-further-mutation -> BLOCKED
- state -> ENVIRONMENT_UNCERTAIN until explicit observation/re-establishment
- no clean-state inference from missing acknowledgement

## Evidence sealing

A sealed run record preserves:

- registration/project generation
- lease
- authorization
- pre-snapshot
- invocation-attempt record
- native return/uncertainty metadata
- post-observation
- containment result
- environment/project-generation status after the run

Fixture disposal does not remove the sealed evidence.

## Qualifying vs exploratory

Exploratory probes still require a registered disposable environment and bounded typed invocation.

They may use a different policy for qualification counting, but they do not bypass:

- working-project prohibition
- one-run authorization
- generation binding
- observation scope
- containment
- no-blind-retry
- crash quarantine

Exploratory mode is not an unrestricted scripting mode.

## Efficiency boundary

Ordinary editing requests cannot:

- create a probe environment implicitly
- arm the harness
- run a full verification suite
- block the user's working project waiting for probe qualification

Probe qualification is explicit development/release/update/diagnostic workflow.

## TASK-019 implementation boundary

TASK-019 should model this contract as pure immutable domain/state transitions and fake/mock control
plane only.

It may implement:

- RegisteredProbeEnvironment
- EnvironmentVerification
- ProjectGenerationStatus
- ProbeHarnessState
- ProbeLease
- ProbeRunAuthorization
- authorization consumption
- final pre-invocation validation
- no-further-mutation gate
- ContainmentResult classification
- REVERIFY_REQUIRED / CONTAMINATED / RETIRED transitions
- sealed run references

It must not implement:

- actual Resolve project lookup
- actual environment fingerprint acquisition
- native mutation
- actual cancellation
- real project rebuild
- actual project-level read verification
- release scheduling

## Accepted v1 decisions

1. Registration, environment verification and arming are separate.
2. Display name/path/sentinel never independently authorize a probe.
3. Every authorization is exact-generation/exact-fixture/exact-snapshot and single-use.
4. Pre-invocation failure consumes/discards authorization.
5. No wall-clock TTL is needed in v1; currentness comes from exact bound state.
6. There is never a reusable global destructive-probe enable switch.
7. Invocation submission consumes authorization even when outcome becomes unknown.
8. No-further-mutation BLOCKED prevents new calls but does not claim cancellation of in-flight calls.
9. Fixture-local unexpected mutation forces project re-verification before another qualifying run.
10. Project-level contamination requires a new project generation.
11. Environment uncertainty after crash/bridge loss locks down further mutation until explicit
    re-establishment/rebuild.
12. A contaminated generation is never repaired back to verified clean in place.
13. Exploratory mode never bypasses isolation/arming/containment rules.
14. Ordinary editor workflows never implicitly arm or run qualification suites.

## Final principle

> Registration tells us which disposable world is allowed to be tested; currentness proves we are
> still in that exact world; one-run arming permits one bounded experiment; contamination ends that
> authority until the world is independently proven clean or rebuilt.
