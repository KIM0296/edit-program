# Capability Verification Policy & Challenge Matrix v1

Status: **Accepted Chat Product/Architecture baseline**

## Purpose

Define the concrete v1 verification policy required before selected destructive native primitives may
be derived as SUPPORTED_VERIFIED under ADR-029.

This policy verifies deterministic native semantics. It is not a statistical success-rate target and
is not performed by the production editor during ordinary editing.

> Verification cost belongs to the product/development system, not to the editor.

## Common VERIFIED gate

A destructive native capability may become SUPPORTED_VERIFIED only when all applicable requirements
are satisfied for the exact RuntimeProfile and ApplicabilityDomain:

- canonical disposable fixture pre-state verified
- observation scope COMPLETE for every qualifying run
- exact semantic effect equality across all qualifying positive runs
- semantic conflicts = 0
- unexpected side effects = 0
- containment failures = 0
- ambiguous target resolutions = 0
- verified execution-grade identity
- verified post-read capability
- verified reconciliation capability
- all required positive fixture classes covered
- all required challenge classes executed
- minimum repetition budget satisfied

## Primitive positive-run policy

### TRANSLATE_PLACEMENT
Positive classes: isolated placement; adjacent placements; pre-existing gap; repeated-media placements.
Each class requires 5 independent clean runs: **4 × 5 = 20 minimum positive runs**.

### REMOVE_RANGE
Positive classes: middle removal; near-leading boundary; near-trailing boundary; adjacent placements;
existing downstream gap; repeated-media placements.
Each class requires 5 independent clean runs: **6 × 5 = 30 minimum positive runs**.

### COMPOUND_RIPPLE
Positive classes: simple contiguous single-track; existing gaps; multiple downstream placements;
large downstream set; explicit multi-track state; repeated-media placements; linked A/V;
intentional J/L; markers/subtitles present; track participation/control-state variation.
Each class requires 5 independent clean runs: **10 × 5 = 50 minimum positive runs**.

## Mandatory challenge policy

Each destructive primitive also receives **3 independent clean runs per applicable challenge class**,
additional to the positive budget.

Baseline challenge classes:
1. linked A/V
2. intentional J/L cut
3. marker/subtitle temporal dependents
4. transition/effect/keyframe structure
5. track participation/control-state variation

## ApplicabilityDomain

Every NativeEffectModel declares the exact conditions under which its semantics apply.

Conflict inside the declared applicability domain -> CONFLICTING.

Different behavior in an explicitly outside-domain challenge does not retroactively invalidate the
narrower model; that context remains UNSUPPORTED until separately verified.

The domain may not be silently narrowed after a failing qualifying run merely to hide a conflict.

## Deterministic interpretation

This is not a pass-rate threshold. 19/20 is not sufficient.

For qualifying runs:
- one semantic conflict blocks VERIFIED
- one unexpected side effect blocks VERIFIED
- one containment failure blocks VERIFIED
- incomplete observation blocks VERIFIED

Five repetitions per positive class are an engineering minimum for run/session/fixture nondeterminism;
fixture diversity and complete observation are the stronger requirements.

## RuntimeProfile binding and invalidation

Verification is bound at least to Resolve version/build where available, platform, adapter
mutation/read implementation version, invocation contract, observation contract, effect-model
contract and verification-policy version.

Raw immutable probe evidence is retained. Compatible raw evidence may be re-derived under a new
policy when it contains all required information. Runtime/adapter/observation semantic changes may
require new probes.

Session-local identity evidence is invalidated on session change independently from broader effect
semantics.

## Efficiency Gate

Capability verification must reduce recurring editor verification work.

v1 requirements:
- ordinary production editor manual capability-probe work = 0
- full 20/30/50 suites are not repeated per project or per edit
- VERIFIED RuntimeProfile evidence is reusable until explicitly stale
- probe suites run in development/release/update validation contexts
- ordinary runtime work is limited to bounded currentness/Safety/precommit/postflight checks
- uncertainty reduces autonomy instead of creating repeated manual editor supervision

This supports Net Editing Time Saved and Human Active Time Saved.

## Verification is not Auto-Apply permission

SUPPORTED_VERIFIED proves native semantics only. Auto-apply still depends on Safety, Authorization,
ADR-027 transaction/rollback policy, release gate and real-workflow/pilot evidence.

## Accepted v1 values

| Primitive | Positive classes | Runs/class | Positive minimum | Challenge runs/class |
| --- | ---: | ---: | ---: | ---: |
| TRANSLATE_PLACEMENT | 4 | 5 | 20 | 3 |
| REMOVE_RANGE | 6 | 5 | 30 | 3 |
| COMPOUND_RIPPLE | 10 | 5 | 50 | 3 |

Hard qualification values:
- conflicts = 0
- unexpected side effects = 0
- containment failures = 0
- ambiguous targets = 0
- scope = COMPLETE
- post-read = VERIFIED
- reconciliation = VERIFIED
- identity = execution eligible

## Final principle

> Prove native semantics once per exact supported runtime domain, reuse that proof while it remains
> valid, and never make the editor repeatedly supervise the same machine behavior.
