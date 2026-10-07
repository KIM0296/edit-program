# Resolve Probe Harness & Fixture Lifecycle Contract v1

Status: **Accepted Chat Product/Architecture baseline**

## Purpose

Define the execution boundary and lifecycle rules for a future Resolve capability probe harness.
The harness exists to measure native behavior in isolated disposable fixtures. It is not a
production executor and must never use a user's authoritative working project as a destructive
qualification target.

## Core isolation rules

1. Qualifying destructive probes run only in registered dedicated disposable probe projects.
2. A duplicated timeline inside a user working project is not sufficient isolation for v1.
3. Probe fixture definition and materialized fixture instance are separate immutable concepts.
4. Only CLEAN_VERIFIED fixture instances may be armed for destructive probing.
5. One qualifying run uses one fresh fixture instance and permits at most one native invocation
   attempt.
6. Dirty, quarantined or mutated fixtures are discarded/rebuilt rather than repaired and reused.
7. Qualifying and exploratory probes are distinct.
8. Exploratory success does not count directly toward ADR-030 verification budgets.
9. A containment failure or project contamination stops further qualifying mutation for the
   affected fixture/project generation.
10. Ordinary production editing never launches full verification suites implicitly.

## Probe environment

A ProbeEnvironmentBinding should bind:

- environment_ref
- runtime_profile_ref
- registered probe_project_ref
- fixture_catalog_ref
- project/environment generation
- harness version
- contract version

Project name/path alone is not authoritative evidence of a registered disposable probe environment.

A machine-readable sentinel may assist detection but never independently authorizes destructive
probing.

## Harness arming

Default harness state is DISARMED.

A qualifying destructive run follows:

```text
DISARMED
→ ENVIRONMENT_VERIFIED
→ FIXTURE_VERIFIED
→ ARMED_FOR_ONE_RUN
→ invocation attempted
→ authorization consumed
```

There is no global destructive-probe enable flag that authorizes arbitrary subsequent calls.

ProbeRunAuthorization binds:

- probe_run_ref
- environment_ref
- fixture_instance_ref
- probe_case_ref
- runtime_profile_ref
- allowed primitive
- allowed typed invocation
- pre-snapshot ref
- authorization contract version

## Primitive allowlist

The harness accepts only versioned typed probe primitives/invocation specifications.

Raw arbitrary Python/Lua/LLM-generated scripts are forbidden.

ADR-006 applies to both production execution and probe infrastructure.

## Fixture definition vs fixture instance

ProbeFixtureDefinition is the versioned canonical blueprint.

Recommended definition content:

- fixture_ref/version/class
- track structure
- placements and source ranges
- canonical test assets
- markers/subtitles
- transitions/effects/keyframes
- track/control states
- expected canonical snapshot model

ProbeFixtureInstance is one materialized run target bound to:

- fixture definition/version
- probe project generation
- materialization generation
- materialized snapshot
- lifecycle state

## Fixture lifecycle

Recommended lifecycle:

```text
DEFINED
→ MATERIALIZING
→ MATERIALIZED
→ VERIFYING
→ CLEAN_VERIFIED
→ LEASED_FOR_PROBE
→ MUTATED
→ OBSERVED
→ SEALED
→ DISCARDED
```

Failure/exception states:

- INVALID
- DIRTY
- QUARANTINED
- ABORTED

Only CLEAN_VERIFIED can become LEASED/ARMED for qualifying destructive probing.

## Fixture verification

After materialization:

```text
Observed Fixture Snapshot
vs
Expected Canonical Fixture State
```

Status:

- MATCH
- MISMATCH
- INCOMPLETE
- STALE

Only MATCH produces CLEAN_VERIFIED.

A mismatch is not repaired in place for the same qualifying run.

Required behavior:

```text
DIRTY
→ discard
→ fresh materialization
→ new instance
```

## Fresh fixture per qualifying repetition

Every ADR-030 qualifying repetition starts from a separately clean-verified fixture instance.

Undo is not the default reset mechanism because rollback/Undo is itself an unverified native
capability until separately proven.

Canonical reconstruction is the default reset path.

## Canonical assets

Capability probes use dedicated canonical test media rather than user footage.

A FixtureAssetManifest should bind test assets by stable metadata/content hash rather than filename
alone.

## Probe run state

Recommended run phases:

- PREPARING
- PRECHECKING
- ARMED
- INVOKING
- OBSERVING
- SEALED
- TERMINAL

Recommended outcomes:

- PASS_OBSERVED
- FAIL_OBSERVED
- INCONCLUSIVE
- INVALID_FIXTURE
- CONTAINMENT_FAILURE
- ABORTED
- HARNESS_ERROR

## One invocation attempt

A qualifying run permits zero or one native invocation attempt.

If command acknowledgement becomes uncertain, record OUTCOME_UNKNOWN and observe fresh native state.
Do not resend the destructive command in the same qualifying run.

Probe execution follows ADR-027's no-blind-retry principle.

## Observation contract

Pre and post observations use the same declared observation schema/scope.

The observation scope is fixed before invocation.

If the scope proves inadequate after the run, create a new probe case/run; do not retroactively
expand observation and count the run as qualifying.

## Containment envelope

Each ProbeCase declares both:

- required observation scope
- containment envelope / state that must remain unchanged

Unexpected mutation to unrelated objects, timelines, project-level state or safety-relevant state
is a CONTAINMENT_FAILURE.

Containment failure makes the run non-qualifying.

## Immediate pre-invocation checks

Immediately before a native probe call verify:

1. current project is the exact registered probe project/generation
2. current timeline is the exact fixture target
3. fixture is CLEAN_VERIFIED/leased for this run
4. current snapshot equals authorized pre-snapshot
5. RuntimeProfile is unchanged
6. primitive/invocation is allowlisted
7. run authorization is unused

Any mismatch aborts before invocation.

## Probe lease

A short exclusive lease may reserve the disposable fixture during a qualifying run.

This lease does not lock the user's working project.

Direct user edits to the disposable fixture during a qualifying run invalidate the run.

## Crash handling

Crash before invocation:
- run authorization is discarded
- fixture may only be used again after explicit re-verification/new run

Crash during/after invocation:
- fixture becomes QUARANTINED
- no new qualifying mutation on that fixture
- inspect/observe for evidence/diagnostics only
- v1 defaults to discard after inspection

Never assume a crashed run remained clean.

## Evidence sealing

After complete post observation, seal an immutable evidence bundle containing at least:

- run/fixture/environment refs
- RuntimeProfile
- pre snapshot
- typed invocation record
- native return metadata
- post snapshot
- observed diff
- containment result
- harness/contract versions

Evidence survives fixture disposal.

## Fixture disposal

Once a qualifying destructive run mutates a fixture, that fixture instance is discarded after
observation/evidence sealing regardless of PASS/FAIL.

Successful mutated fixtures are not reused.

Failed mutated fixtures are not reused.

## Probe project generation

A probe project may host multiple independently materialized fixtures only while project-level
containment remains verified.

Unexpected project-level mutation marks the project generation CONTAMINATED and stops further
qualifying mutation in that generation.

Rebuilding the probe project creates a new generation.

## ProbeSuite

ADR-030 verification runs may be grouped in an immutable ProbeSuite referencing:

- runtime profile
- verification policy
- probe cases
- project/fixture generations
- run/evidence refs

Suite aggregation derives new artifacts; it never rewrites individual runs.

## Qualifying vs exploratory

ProbeRunMode:

- QUALIFYING
- EXPLORATORY

QUALIFYING runs must satisfy all ADR-029/030 and lifecycle constraints.

EXPLORATORY runs may study unknown behavior but cannot directly count toward VERIFIED repetition
budgets even if the observed result looks correct.

## Applicability declaration

Qualifying ProbeCase records its declared applicability domain before invocation.

A failing qualifying run may not be removed later by silently narrowing the domain.

Explicit outside-domain challenges may be recorded as boundary evidence.

## Efficiency boundary

Full probe suites are development/release/update/explicit diagnostic workflows, not ordinary
editing-request paths.

A user pause-edit request must never synchronously trigger 20/30/50 verification runs.

Verified profile evidence is reused until stale.

## TASK-019 boundary

TASK-019 may implement pure domain/state-machine + non-native harness shell only:

- ProbeEnvironmentBinding
- ProbeHarnessState
- ProbeRunMode
- ProbeRunAuthorization
- ProbeFixtureDefinition
- FixtureAssetManifest
- ProbeFixtureInstance
- FixtureLifecycleState
- FixtureVerificationStatus/Result
- ProbeRunState/Outcome
- Containment model
- ProbeSuite
- one-run arming/consumption rules
- lifecycle/transition validators
- fake/mock adapter harness boundary

TASK-019 must not implement:

- actual Resolve destructive mutation
- actual native target lookup
- actual capability qualification
- actual rollback/Undo
- production project mutation
- real release automation

## Accepted v1 decisions

1. Qualifying destructive probes run only in dedicated disposable probe projects.
2. Duplicated timelines inside a user project are insufficient qualifying isolation.
3. Qualifying run = one fresh fixture instance + at most one native invocation attempt.
4. Fixture reset uses canonical reconstruction rather than assumed Undo.
5. Only CLEAN_VERIFIED fixtures may arm.
6. DIRTY/QUARANTINED fixtures are discarded/rebuilt, not repair-and-continue.
7. QUALIFYING and EXPLORATORY probe modes are distinct.
8. Exploratory success does not directly count toward VERIFIED budgets.
9. Containment failure or project contamination stops further qualifying mutation in that
   fixture/project generation.
10. Observation scope is fixed before invocation and pre/post schemas are symmetric.
11. Environment/currentness is revalidated immediately before invocation.
12. Native timeout/uncertainty never causes blind retry in the same run.
13. Crash during/after invocation quarantines the fixture.
14. Mutated fixtures are discarded after evidence sealing.
15. Probe evidence and disposable fixture lifecycle are separate.
16. Full verification suites never run implicitly in ordinary production editing.

## Final principle

> Every destructive probe run starts from a state we can prove, performs exactly one bounded
> experiment, records everything it changed, and then throws that experiment state away.
