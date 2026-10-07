# Native Probe Environment Authenticity Contract v1

Status: **ACCEPTED — Chat Product/Architecture baseline**

## Purpose

Define how the system proves that the currently active DaVinci Resolve world is the exact registered
disposable probe environment intended for native capability testing.

This contract exists to prevent the highest-severity category of probe error:

> A destructive probe is submitted to a user working/production project because the current Resolve
> context merely looks like the registered probe project.

This contract does not implement native lookup, registry persistence, atomic lease consumption or
destructive probing. It defines the evidence chain those implementations must satisfy.

## Core safety decision

A project name, path, filename, timeline name, sentinel, current selection, UUID-shaped value or one
successful API lookup is never sufficient authenticity evidence.

Native probe environment authenticity is established only from an exact agreement between:

1. an external immutable registration record;
2. an approved dedicated probe-only Project Library scope;
3. fresh native library/project/current-context observations;
4. materialization provenance for the disposable project generation;
5. an independently observed canonical semantic project/fixture baseline;
6. a fresh final currentness proof immediately before arming/submission.

No majority vote, recency preference or fallback heuristic may replace a missing layer.

---

# 1. Threat model

The contract must fail closed against at least:

- operator has the wrong Resolve project open;
- a production project shares the same display name;
- a copied/duplicated project carries similar timelines/assets;
- a probe sentinel has been copied into another project;
- the same canonical media exists in another project;
- a project was rebuilt/re-imported but old registration evidence is reused;
- Resolve was restarted and same-session identity assumptions are silently reused;
- the current Project Library changed;
- a shared/cloud/network library allows another user/process to edit concurrently;
- a stale Python/adapter object refers to a previously current project;
- one native unique ID is readable but its lifetime is not proven;
- the correct project is open but the wrong fixture timeline is current;
- a fixture has drifted after environment attestation;
- a crash/bridge reconnect leaves current native state uncertain;
- an old immutable authorization/control-plane snapshot is replayed.

---

# 2. Qualifying environment policy

## Dedicated probe-only Project Library is required for v1 destructive qualification

For the first qualifying destructive native probes, the registered environment must use a Project
Library operationally dedicated to probe work.

The library must not intentionally contain ordinary user working/production projects.

Shared/cloud/collaborative/network-backed libraries are **non-qualifying for v1 destructive probes**
unless a later approved contract proves equivalent single-writer/currentness guarantees.

The preferred v1 environment is a local, single-user probe-only Project Library.

This is a product/safety requirement, not a claim that Resolve currently exposes a perfect native
persistent Project Library ID.

If the installed API cannot provide enough native evidence to bind the current library to the
registered dedicated scope, environment authenticity remains INCOMPLETE/UNKNOWN and destructive
arming is blocked.

## Why this is hard-required

Project-level identity evidence can fail.

A dedicated probe-only library adds an independent isolation boundary so a wrong-project selection
is less likely to point at valuable user work.

This does not replace exact project authentication.

---

# 3. Separation of concepts

The system keeps these distinct:

## EnvironmentRegistration

What the control plane says is allowed to be tested.

## MaterializationReceipt

How this disposable project generation was created from approved package/template inputs.

## NativeEnvironmentObservation

What Resolve currently reports about library/project/session context.

## CanonicalBaselineObservation

What the read-only adapter observes semantically inside the project.

## NativeEnvironmentAttestation

Derived result saying the observed native world matches the registration for a specific claimed
lifetime scope.

## NativeTargetCurrentnessProof

Fresh proof that, immediately before one bounded native invocation, the current project/timeline/
fixture/pre-snapshot are still the same world that was attested.

Registration is not observation.
Observation is not attestation.
Attestation is not arming.
Arming is not execution success.

---

# 4. External immutable EnvironmentRegistration

The authoritative registration record lives outside the Resolve project.

Minimum fields:

- environment_ref
- registry_ref
- registry_generation
- project_library_ref
- project_library_policy_version
- probe_project_ref
- project_generation
- expected RuntimeProfile scope
- fixture_catalog_ref/version
- canonical package name/version/digest
- project template/package provenance refs
- expected fixture definition/version
- materialization contract version
- authenticity contract version
- created_by opaque engineering actor/process ref
- registration evidence refs
- production = false
- authoritative = false
- disposable = true
- dedicated_probe_library_required = true

The record must be immutable once used for evidence.

Changing registration facts creates a new registry generation or project generation.

Display names may be stored for diagnostics but are not authority fields.

---

# 5. Probe Project Library registration

Project Library registration is external policy plus native observation.

Minimum registered descriptor:

- project_library_ref
- expected native database/library type classification
- expected native database/library name if exposed
- expected server/address descriptor if exposed and relevant
- local/shared classification
- collaboration allowed = false for v1
- probe-only operational classification
- registration evidence ref
- descriptor contract version

The exact Resolve-returned keys are RuntimeProfile-specific and must be confirmed against installed
Developer documentation and actual read results.

Do not hard-code undocumented key names into the architecture contract.

## Library authenticity status

- VERIFIED_SESSION
- MISMATCH
- INCOMPLETE
- UNSUPPORTED
- UNKNOWN
- STALE

Only VERIFIED_SESSION may contribute to v1 destructive environment attestation.

A stable library name alone cannot produce VERIFIED_SESSION.

---

# 6. MaterializationReceipt

TASK-021 or an approved controlled predecessor process produces an immutable MaterializationReceipt.

Minimum fields:

- receipt_ref
- environment_ref
- project_generation
- project template/content hash
- canonical package_digest
- canonical asset manifest digest
- fixture definition/version
- materialization_generation
- materializer version/contract
- source project/template provenance
- expected project-level semantic baseline digest/ref
- expected timeline/fixture role inventory
- creation result
- evidence refs

The receipt proves provenance supplied to the materializer.

It does **not** prove that the currently open native Resolve project is that project.

---

# 7. Native library observation

Every environment attestation re-acquires library context from the Resolve root object path.

Do not rely only on cached Project/Timeline proxies from an earlier observation.

Candidate observations include, where the installed runtime exposes them:

- current database/library descriptor;
- database/library type;
- database/library name;
- server/address descriptor;
- current ProjectManager context.

Exact methods are RuntimeProfile-specific.

Each observation records:

- raw return;
- typed shape;
- semantic value;
- RuntimeProfile;
- capture sequence;
- installed API evidence ref.

Ambiguous or malformed values remain UNKNOWN.

---

# 8. Native project observation

Re-acquire the current project through the normal native root path.

Candidate observations:

- current Project object availability;
- Project.GetUniqueId() or installed equivalent when actually supported;
- project name as diagnostic data;
- required project settings;
- current timeline object;
- current timeline unique ID observation when supported;
- project/timeline semantic inventory required by the registered fixture.

## Unique ID rule

A readable non-empty project/timeline unique ID is strong same-session evidence only after TASK-020
validates its read stability for the claimed boundary.

UUID syntax is never proof of persistence.

For v1 destructive probes:

- same-session stable native project ID may contribute to SESSION_BOUND_VERIFIED;
- it cannot by itself establish reopen or cross-session identity;
- after Resolve restart, project reopen, or an unproven bridge reconnection, the old claim becomes
  STALE unless the corresponding lifetime was separately verified.

---

# 9. Canonical project/fixture baseline

Native identity is combined with semantic project evidence.

The read-only observer captures a canonical baseline bound to:

- exact project generation;
- exact fixture instance/materialization generation;
- exact canonical package digest;
- exact fixture definition/version;
- exact target timeline;
- expected track topology/state;
- expected placements/media/source/timeline geometry;
- declared markers/subtitles;
- required role bindings;
- project-level containment baseline.

This baseline is derived only from independently observed native reads.

Materializer success flags or registration metadata cannot substitute for it.

Only independent MATCH may contribute to authenticity.

---

# 10. Environment semantic fingerprint

A versioned EnvironmentSemanticFingerprint may be computed from normalized observed semantic evidence.

It contains/refers to:

- registered Project Library semantic descriptor;
- observed project identity evidence;
- project generation;
- canonical package digest;
- fixture definition/version;
- observed timeline identity evidence;
- canonical semantic baseline digest;
- RuntimeProfile;
- observation contract version.

The fingerprint is for exact comparison/currentness.

It is not a synthetic native persistent ID.

Do not compare fingerprints across incompatible RuntimeProfiles/contracts by silently dropping fields.

---

# 11. Optional machine-readable generation witness

A project-local machine-readable witness may strengthen re-acquisition only if a later materializer/
runtime contract proves a safe typed field for it.

Examples could include a declared project/timeline marker custom-data record or another bounded native
metadata primitive.

Rules:

- witness creation must be explicit materialization behavior;
- witness value is random/unique per project generation or bound to registration generation;
- witness is read-only during probe qualification;
- copied witness does not authenticate another project;
- sentinel/witness alone never authorizes probing;
- missing witness is INCOMPLETE when the active profile requires it;
- do not invent a witness mechanism before actual runtime capability is proven.

v1 architecture does not require a specific Resolve field for this witness.

---

# 12. Attestation capture protocol

A NativeEnvironmentAttestation uses two fresh observation phases.

## Phase A — full authenticity observation

Capture:

1. RuntimeProfile;
2. current Project Library descriptor;
3. current project observation;
4. current timeline/fixture observation;
5. canonical semantic baseline;
6. materialization receipt binding;
7. package/fixture contract binding.

## Phase B — independent re-read

Immediately re-acquire from the Resolve root path and re-read at least:

- Project Library descriptor;
- current project identity observation;
- current timeline identity observation;
- environment semantic fingerprint inputs required by the profile.

Do not reuse only cached proxy object values.

Phase A and B must agree for the claimed same-session scope.

Any unexplained difference -> STALE / UNKNOWN / MISMATCH, never retry-until-green.

---

# 13. Attestation result vocabulary

## SESSION_BOUND_VERIFIED

May be issued only when:

- dedicated probe-only library policy satisfied;
- registered library descriptor and fresh native observation agree;
- registered project generation/current project agree;
- same-session native project identity evidence is stable where required;
- materialization receipt matches registration;
- approved canonical package digest matches;
- canonical baseline observation is MATCH;
- fixture/timeline role binding is unique;
- Phase A and independent Phase B agree;
- no conflicting/unknown mandatory fact exists.

This is sufficient only for a same-session destructive probe whose final currentness gate also passes.

## REOPEN_BOUND_VERIFIED

Requires explicit project reopen lifetime evidence under ADR-033 S3 plus all SESSION_BOUND conditions.

Not granted by default.

## CROSS_SESSION_VERIFIED

Requires explicit Resolve restart/cross-session evidence under ADR-033 S4 and a separately approved
persistence contract.

Not required for first destructive probes.

## MISMATCH

Use when a known observed value conflicts with registration/canonical baseline.

Examples:

- wrong library descriptor;
- wrong project observed ID;
- wrong project generation;
- wrong canonical package/fixture;
- unexpected project/timeline state.

## INCOMPLETE

Mandatory evidence is absent.

## UNKNOWN

Native/bridge semantics are ambiguous.

## UNSUPPORTED

Installed runtime demonstrably cannot expose a mandatory field/path for the claimed profile.

## STALE

Previously valid evidence is no longer current for the active session/project generation/runtime
boundary.

## CONTAMINATED

The registered project generation has known project-level contamination under ADR-035.

---

# 14. Session-bound v1 destructive eligibility

The first native destructive probe does **not** require persistent project identity across Resolve
restarts.

It requires:

- SESSION_BOUND_VERIFIED environment authenticity;
- exact CLEAN_VERIFIED fixture;
- exact current target proof;
- one-run authorization;
- no project/library switch since attestation;
- no adapter/runtime reconnect whose native object continuity is unknown;
- no collaboration/concurrent writer;
- no contamination.

If Resolve restarts or the probe project is reopened before the run:

- old SESSION_BOUND_VERIFIED becomes STALE;
- re-attest from scratch;
- do not treat same display name/UUID-shaped value as continuity.

This allows progress without overclaiming persistent native identity.

---

# 15. Final NativeTargetCurrentnessProof

Immediately before destructive arming/submission, obtain a fresh bounded currentness proof.

Bind exactly:

- attestation_ref;
- environment_ref;
- project_generation;
- RuntimeProfile;
- library observation ref;
- current project observation ref;
- target timeline observation ref;
- fixture instance/materialization generation;
- CLEAN_VERIFIED fixture proof;
- authorized pre-snapshot digest/ref;
- observation scope;
- containment envelope;
- capture sequence;
- currentness contract version.

## Minimum final re-read

At minimum re-read:

- current library descriptor;
- current project native identity observation;
- current timeline native identity observation;
- exact fixture/pre-snapshot currentness fence.

If any value differs from the attested/authorized state:

- no native invocation;
- consume/abort authorization under ADR-035;
- preserve finding;
- require fresh attestation or new generation as appropriate.

The final proof should be short-lived logically through state binding, not through wall-clock TTL.

---

# 16. Currentness invalidation events

SESSION_BOUND_VERIFIED attestation becomes stale on:

- Resolve application restart;
- project close/reopen unless S3 lifetime explicitly proven;
- current Project Library switch;
- current project switch;
- project generation rebuild/re-import;
- RuntimeProfile change;
- adapter reconnect where native object/session continuity is unknown;
- canonical fixture rematerialization;
- canonical package/fixture definition change;
- project-level contamination;
- operator edits affecting the registered baseline;
- concurrent/collaboration modification;
- unexplained read drift in mandatory authenticity fields.

Timeline switching inside the same project invalidates target currentness proof but does not
necessarily destroy environment registration; a fresh target proof is required.

---

# 17. Wrong-project fail-closed matrix

## Same project name, different native project observation

MISMATCH.

## Same canonical assets, wrong project

MISMATCH.

## Same sentinel, wrong project

MISMATCH.

## Native project ID unavailable but complete canonical baseline matches

INCOMPLETE for v1 destructive authenticity unless an approved equivalent strong identity evidence
profile exists.

Do not silently weaken the contract because semantic content looks correct.

## Native project ID stable but canonical baseline mismatches

MISMATCH.

## Correct project but wrong current timeline

Target currentness failure; no invocation.

## Correct project/library but fixture ambiguous

INCOMPLETE/MISMATCH; no invocation.

## Library evidence ambiguous

UNKNOWN; no invocation.

---

# 18. Negative production-project protection

The v1 protection strategy is layered:

1. dedicated probe-only Project Library;
2. registration says production=false/authoritative=false;
3. fresh native library observation;
4. fresh current project identity observation;
5. materialization provenance;
6. canonical semantic baseline;
7. exact target currentness proof;
8. one-run authorization.

No single caller-supplied boolean is treated as proof that a project is non-production.

If evidence unexpectedly indicates a non-probe library/project:

- hard block;
- do not offer an override;
- do not fall back to another current project.

---

# 19. Collaboration/concurrency policy

Qualifying destructive probe environments are single-writer in v1.

If the current Project Library/project can be concurrently modified by another workstation/process
and the harness cannot prove single-writer isolation:

- authenticity result cannot reach SESSION_BOUND_VERIFIED.

This includes collaboration/cloud/shared workflows until a separate contract proves deterministic
currentness and atomic authority.

User production collaboration features are not disabled globally; they are simply outside qualifying
probe environments.

---

# 20. Registry persistence boundary

EnvironmentRegistration must eventually be persisted outside Resolve.

The persistence layer must be able to answer:

- which environment_ref/project_generation is current;
- which generations are retired/contaminated;
- which native observations/attestations support the registration;
- which sealed probe runs consumed authority.

This contract does not choose SQLite/Postgres/file store.

In-memory Python objects are insufficient for durable cross-process/native authority.

---

# 21. Durable authorization / cross-process lease is separate

Native environment authenticity and durable one-run authority are related but distinct.

ADR-039 resolves the authenticity contract.

It does not solve:

- atomic compare-and-consume across processes;
- crash-safe durable authorization consumption;
- OS/process-level exclusive probe lease;
- restart reconciliation of pending invocation;
- replay prevention across independent Python processes.

These become a separate OPEN decision.

Until implemented, actual destructive native probe execution must not claim crash-safe/cross-process
single-use authority.

---

# 22. Evidence bundle

A NativeEnvironmentAttestation evidence bundle retains:

- registration record ref/digest;
- project library registration;
- Phase A raw/semantic observations;
- Phase B raw/semantic observations;
- materialization receipt;
- canonical package/fixture refs;
- canonical baseline snapshot/digest;
- native project/timeline identity observations;
- optional generation witness evidence;
- RuntimeProfile;
- attestation result/scope;
- findings;
- explicit non-claims;
- evidence checksum.

A final NativeTargetCurrentnessProof is stored separately per authorized probe run.

---

# 23. Evidence conflict policy

Conflicts are retained.

Do not:

- choose the newest project ID;
- majority-vote multiple observations;
- prefer the value matching registration;
- discard a mismatch after re-read;
- narrow the evidence scope after failure.

If a mandatory authenticity fact conflicts within one claimed scope:

- no VERIFIED attestation.

---

# 24. Relationship to TASK-020

TASK-020 provides the first trusted read-only native observation producer.

TASK-020 must gather the library/project/timeline facts needed by this contract where the installed
runtime supports them.

TASK-020 does not itself issue destructive authorization.

ADR-038 runtime evidence may later satisfy the read-stability prerequisites for SESSION_BOUND native
identity observations.

If TASK-020 proves a required authenticity field is unsupported/ambiguous, this contract remains
fail-closed and architecture review decides whether an equivalent evidence path is acceptable.

---

# 25. Relationship to TASK-021

TASK-021 supplies:

- canonical materialization;
- MaterializationReceipt;
- project/fixture generation provenance;
- independent canonical MATCH through TASK-020.

TASK-021 success is necessary but not sufficient for native environment authenticity.

After materialization, a separate fresh native attestation must prove the currently open Resolve
world matches the receipt/registration.

---

# 26. Relationship to destructive native mutation probe

Before the first destructive mutation probe:

```text
Dedicated Probe Library
        ↓
External EnvironmentRegistration
        ↓
TASK-021 MaterializationReceipt
        ↓
TASK-020 Native Read Observation
        ↓
Canonical Baseline MATCH
        ↓
Phase A + Phase B Native Attestation
        ↓
SESSION_BOUND_VERIFIED
        ↓
Fresh NativeTargetCurrentnessProof
        ↓
ADR-035 One-run Authorization
        ↓
One bounded native invocation
```

Any missing layer blocks invocation.

---

# 27. Runtime implementation order

Do not implement this whole contract before runtime evidence exists.

Recommended order:

1. TASK-022 first canonical package;
2. TASK-020 read-only adapter + runtime evidence;
3. TASK-021 materializer + MaterializationReceipt;
4. implement NativeEnvironmentAttestation producer using the proven read surfaces;
5. validate SESSION_BOUND_VERIFIED on dedicated local probe library;
6. only then authorize first destructive native probe.

This prevents speculative API architecture from becoming safety authority.

---

# 28. Accepted v1 decisions

1. First qualifying destructive probes require a dedicated probe-only Project Library.
2. Shared/cloud/network/collaborative libraries are non-qualifying for v1 unless later proven safe.
3. Project name/path/timeline name/sentinel/UUID shape/one API success never authenticate an environment.
4. External registration and native observation remain separate.
5. MaterializationReceipt proves provenance, not current native identity.
6. SESSION_BOUND_VERIFIED is sufficient for first same-session destructive probes; persistent
   cross-restart identity is not required.
7. Same-session native project/timeline unique-ID observations may contribute only after TASK-020
   read-stability evidence.
8. Canonical semantic baseline MATCH is mandatory in addition to native identity observations.
9. Attestation uses a full observation plus independent root-path re-read.
10. A fresh NativeTargetCurrentnessProof is required immediately before one-run arming/submission.
11. Project/library/runtime/rebuild/reconnect changes invalidate attestation according to claimed scope.
12. No majority/latest/retry-until-green conflict resolution.
13. A project-local witness/sentinel is optional supporting evidence and never sole authority.
14. Native ID unavailable/ambiguous blocks v1 destructive authenticity unless a separately approved
    equivalent strong evidence profile exists.
15. Collaboration/concurrent writers are outside v1 qualifying probe environments.
16. Durable cross-process authorization consumption is a separate problem and is not claimed solved.
17. If actual TASK-020 runtime evidence contradicts an assumed candidate read, the contract fails
    closed and returns to architecture review rather than weakening itself silently.

---

# 29. OPEN-020 resolution scope

ADR-039 resolves OPEN-020 at the architecture-contract level for:

- native environment authenticity evidence composition;
- dedicated-library v1 policy;
- session-bound authenticity scope;
- attestation/currentness invalidation rules;
- materialization/read-only evidence binding;
- wrong-project fail-closed behavior.

It does not resolve actual runtime production of those facts.

OPEN-020 remains PARTIALLY RESOLVED until TASK-020/021 prove the required native observations and the
attestation producer is implemented.

Durable/atomic authorization consumption and cross-process lease are split into OPEN-022.

---

# 30. Final principle

> We do not ask “does this project look like our test project?”
>
> We ask “does a fresh, independently re-read native world match the exact externally registered
> disposable generation, canonical materialization provenance and semantic baseline we intended to
> destroy?”
