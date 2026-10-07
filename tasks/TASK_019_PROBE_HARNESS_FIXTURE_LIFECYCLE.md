# TASK-019 — Probe Harness & Fixture Lifecycle Foundation

Status: **PREPARED, NOT AUTHORIZED UNTIL TASK-018 IS APPROVED/MERGED**

Basis:
- ADR-006 LLM Emits IR Only
- ADR-029 Native Capability Probe Evidence
- ADR-030 Capability Verification Policy
- ADR-031 Resolve Probe Harness & Fixture Lifecycle v1
- ADR-035 Probe Environment Registry & Runtime Control Plane v1

## Purpose

Implement a pure immutable domain/state-machine foundation and fake/mock harness shell for safe probe
environment registration, fixture lifecycle, one-run arming, containment, evidence sealing and
qualifying/exploratory separation.

No Resolve destructive mutation is implemented.

## Required domain

At minimum:

- ProbeEnvironmentBinding
- ProbeHarnessState
- ProbeRunMode
- ProbeRunAuthorization
- ProbeFixtureDefinition
- FixtureAssetManifest
- ProbeFixtureInstance
- FixtureLifecycleState
- FixtureVerificationStatus / FixtureVerificationResult
- ProbeRunState
- ProbeRunOutcome
- ContainmentEnvelope / ContainmentResult
- ProbeSuite
- pure lifecycle transition functions
- one-run authorization consumption validation

## Mandatory isolation rules

- qualifying destructive environment must be a registered dedicated disposable probe project
- a user working project is never eligible
- duplicate timeline inside user project is not eligible
- project name/path/sentinel alone is insufficient
- environment/project generation must bind the run

## Fixture lifecycle

Support:

DEFINED → MATERIALIZING → MATERIALIZED → VERIFYING → CLEAN_VERIFIED → LEASED_FOR_PROBE →
MUTATED → OBSERVED → SEALED → DISCARDED

and failure states:

INVALID / DIRTY / QUARANTINED / ABORTED

Only CLEAN_VERIFIED may become leased/armed.

Do not implement repair-and-continue for DIRTY fixtures.

## Fresh-instance rule

Each qualifying repetition uses a new clean fixture instance.

Do not model Undo as the default fixture reset.

## Run authorization

Authorization is bound to exact:

- environment
- fixture instance
- probe case
- RuntimeProfile ref
- allowed primitive/invocation
- pre-snapshot
- run ref

One authorization can be consumed for at most one invocation attempt.

## Probe modes

- QUALIFYING
- EXPLORATORY

Exploratory results cannot be directly counted as qualifying repetitions.

## Observation / containment

Represent fixed predeclared observation scope and containment envelope.

Containment failure is explicit, non-qualifying, and may contaminate the current project generation.

Do not permit post-hoc observation scope expansion to make a run qualifying.

## Crash / quarantine

- pre-invocation abort consumes/discards run authorization
- crash/unknown state during or after invocation quarantines fixture
- quarantined fixture cannot run another qualifying mutation
- no clean-state inference from crash

## Evidence seal

Represent immutable sealed run refs for pre/post snapshot, invocation, native metadata, observed diff
and containment result.

Fixture may then be discarded without deleting evidence.

## Project contamination

Represent project generation.

Containment failure outside the fixture may mark generation contaminated and block further
qualifying runs in that generation.

## Required tests

At minimum prove:

1. immutable/frozen values
2. defensive collection copies
3. qualifying environment rejects working/production project
4. user-project duplicate timeline not sufficient isolation
5. exact environment/project generation binding
6. project name/sentinel alone not authority
7. lifecycle legal transitions
8. illegal lifecycle transition rejected
9. only CLEAN_VERIFIED may lease/arm
10. MATCH-only fixture verification -> CLEAN_VERIFIED
11. MISMATCH/INCOMPLETE/STALE cannot arm
12. dirty fixture cannot repair-and-continue
13. dirty fixture must discard/new instance for qualifying run
14. fresh fixture instance per qualifying repetition
15. no Undo-reset assumption
16. one-run authorization exact binding
17. one authorization at most one invocation attempt
18. used authorization cannot re-arm
19. runtime/profile mismatch before invocation aborts
20. pre-snapshot mismatch aborts
21. wrong project/timeline/fixture aborts
22. primitive/invocation allowlist binding
23. QUALIFYING/EXPLORATORY distinct
24. exploratory result cannot increment qualifying count
25. fixed observation scope before invocation
26. symmetric pre/post observation contract
27. post-hoc scope expansion cannot qualify old run
28. containment failure non-qualifying
29. containment failure may contaminate project generation
30. contaminated generation blocks further qualifying mutation
31. rebuild creates new project generation
32. native outcome unknown does not allow retry in same run
33. crash before invocation invalidates run authorization
34. crash during/after invocation -> QUARANTINED
35. quarantined fixture cannot qualify again
36. mutated PASS fixture not reused
37. mutated FAIL fixture not reused
38. evidence remains after fixture discarded
39. evidence seal immutable
40. fixture definition version mismatch blocks qualification
41. canonical asset identity does not rely on filename only
42. applicability domain declared before qualifying invocation
43. failing qualifying run cannot be retroactively excluded by silent domain narrowing
44. ProbeSuite aggregates refs without rewriting run evidence
45. ordinary production request cannot implicitly launch full suite in pure harness policy
46. no actual Resolve mutation
47. no actual target lookup
48. no rollback/Undo
49. no production project mutation
50. TASK-001..018 regression remains green

## Explicitly out of scope

- actual Resolve native mutation
- actual read-only adapter implementation
- actual fixture materialization in Resolve
- capability evidence aggregation beyond references
- rollback
- release automation
- background qualification scheduling

## Workflow

1. Do not start until TASK-018 is Chat APPROVED and merged unless Chat explicitly reorders.
2. Start from then-current main.
3. Treat ADR-031 and this spec as authoritative.
4. Red-first tests.
5. Implement pure immutable lifecycle/harness shell.
6. Full regression.
7. Python 3.11 CI / Ruff / strict mypy.
8. Write docs/reports/TASK_019_COMPLETION.md.
9. Open PR and request Chat Gate.
10. Do not merge or auto-start actual Resolve harness work.

## Success definition

Represent a probe run so destructive qualification can only be armed inside a registered disposable
probe project on one fresh CLEAN_VERIFIED fixture, execute at most one bounded invocation attempt,
seal evidence, and discard/quarantine the test state without touching production projects.


## Runtime control-plane additions

TASK-019 must also implement ADR-035 as pure immutable state/control-plane semantics.

Required additional domain:

- RegisteredProbeEnvironment
- EnvironmentVerification
- ProjectGenerationStatus
- ProbeLease
- NoFurtherMutationGate
- explicit authorization-consumption state
- containment classification:
  - CLEAN
  - UNEXPECTED_FIXTURE_LOCAL
  - PROJECT_LEVEL_CONTAMINATION
  - ENVIRONMENT_UNCERTAIN

Rules:

- registration != environment verification != arming
- name/path/sentinel alone never authorizes
- only VERIFIED_CLEAN project generation may arm qualifying work
- final pre-invocation failure consumes/discards the one-run authorization
- invocation submission consumes authorization regardless of native acknowledgement
- no global reusable arm flag
- UNEXPECTED_FIXTURE_LOCAL -> REVERIFY_REQUIRED
- project-level re-verification is observation-only and may not repair state
- successful independent re-verification may return REVERIFY_REQUIRED -> VERIFIED_CLEAN
- failed/unknown re-verification -> CONTAMINATED
- PROJECT_LEVEL_CONTAMINATION -> CONTAMINATED directly
- CONTAMINATED cannot become VERIFIED_CLEAN in-place
- rebuild creates a new project generation
- ENVIRONMENT_UNCERTAIN blocks further mutation until explicit re-establishment/rebuild
- BLOCKED no-further-mutation means no new calls; it does not claim in-flight cancellation
- exploratory mode cannot bypass these gates

Add tests proving these transitions and that OPEN-020 native registration authenticity is not
silently invented.
