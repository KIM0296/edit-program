# Read-only Probe Adapter & Fixture Materialization Contract v1

Status: **Accepted Chat Product/Architecture baseline**

## Purpose

Before destructive native probing, the system must prove that it can recreate a canonical test fixture exactly and observe that fixture reliably without changing it.

## Responsibility split

1. Probe Environment Controller: registered disposable project/timeline selection and project generation.
2. Fixture Materializer: canonical fixture creation from a versioned package.
3. Read-only Probe Adapter: observation only; no repair or mutation.
4. Native Probe Invoker: future bounded destructive probe component.

The Read-only Adapter has no generic execute/eval/script entry point and does not browse arbitrary projects by name.

## Read-only adapter contract

The adapter reports capability separately from observed value and preserves UNKNOWN/UNSUPPORTED instead of converting them to false/absent.

A ProbeSnapshot binds RuntimeProfile, environment/project generation, exact timeline identity, tracks/topology/control state, placements, media/source/timeline ranges, retime observations, declared markers/subtitles/transitions/effects/keyframes, identity evidence, capture consistency, completeness and observation-contract version.

Snapshots are immutable. Re-observation creates a new snapshot.

## Capture consistency

Do not assume Resolve exposes an atomic whole-timeline snapshot. Use a conservative consistency fence such as header A -> detailed observation -> header B. If the relevant project/timeline/state identity differs, the capture is UNSTABLE and cannot qualify a fixture.

## Canonical fixture identity

Canonical fixture identity is semantic, not generated native-ID equality. Fixture definitions use semantic roles such as PRIMARY_A, DOWNSTREAM_B, DOWNSTREAM_C, SUBTITLE_S1 and MARKER_M1.

Materialization creates explicit FixtureRoleBinding records. Zero matches are unresolved; multiple matches are ambiguous. Never first-match or use filename/name/current position alone as identity authority.

## Template-first materialization

v1 uses a CanonicalFixturePackage containing a versioned content-hashed project template, content-hashed canonical test assets, fixture definition, expected semantic snapshot and materialization-recipe version.

Canonical assets are dedicated test assets, not user footage. Missing assets or content-hash mismatches fail closed; similar filenames are never substituted.

Initial materialization steps stay minimal and typed, for example IMPORT_PROJECT_TEMPLATE, BIND_CANONICAL_ASSET and ACTIVATE_FIXTURE_TIMELINE. Arbitrary scripts are not allowed.

## Independent verification

Materializer return success does not create CLEAN_VERIFIED. Required path: materialize -> independent read-only capture -> canonical semantic comparison.

Verification statuses: MATCH, MISMATCH, INCOMPLETE, STALE, UNSUPPORTED. Only MATCH may become CLEAN_VERIFIED.

Missing required observation is INCOMPLETE. Known wrong value or unexpected canonical object is MISMATCH. Mismatch is discarded/rebuilt rather than repaired-and-qualified in place.

## Fixture verification profile

Use an explicit fixture verification requirement profile. Base requirements include runtime/project/timeline context, track topology/state, all declared placements, media/source/timeline ranges, retime and role-binding identity evidence. Challenge fixture classes add their declared marker/subtitle/transition/effect/keyframe/control-state requirements.

## Read stability

Before destructive mutation probing, repeated captures of an unchanged CLEAN_VERIFIED fixture must be semantically equal under the declared observation contract. Observer instability must not be confused with native mutation effects.

## Integration order

1. Read-only Probe Adapter
2. Fixture Materializer
3. Read Stability Qualification
4. Native Mutation Probe

Do not implement destructive mutation probing before the read path and fixture verification are proven.

## TASK-020 boundary

TASK-020 is the first real/non-mutating Resolve-facing component: RuntimeProfile capture, registered environment/project/timeline observation, fixture snapshot capture, capability/value separation, consistency fence, typed UNKNOWN/UNSUPPORTED reporting, FixtureRoleBinding and read stability. No mutation.

## TASK-021 boundary

After TASK-020 approval, TASK-021 implements the template-first CanonicalFixturePackage, template/asset hash validation, disposable probe-project allocation/binding, minimal typed materialization, and independent TASK-020 verification. No destructive capability probe.

## Accepted v1 decisions

1. Environment Controller, Materializer, Read-only Adapter and Native Invoker are separate.
2. Read-only Adapter exposes no generic mutation/eval/script surface.
3. v1 materialization is template-first with hashed project template and canonical assets.
4. Materializer success requires independent canonical MATCH.
5. Mismatched instances are discarded/rebuilt, not repaired-and-qualified.
6. Canonical semantic identity and generated native identity are separate.
7. FixtureRoleBinding is explicit and ambiguity fails closed.
8. Filename alone is never asset/object identity.
9. Missing required evidence is INCOMPLETE; known wrong state is MISMATCH.
10. Capture consistency is explicitly fenced.
11. Read stability is qualified before mutation probing.
12. Integration order is Read-only Adapter -> Materializer -> Read Stability -> Mutation Probe.
13. Actual Resolve API support is discovered for the exact installed RuntimeProfile rather than assumed.

## Final principle

> Materialization creates a candidate test state; independent read-only observation is what proves that the state is actually canonical.