# Test Matrix

## 단계 1 — Pure Domain Tests

실제 Resolve 없이 수행.

| ID | 테스트 | 우선순위 | 초기 상태 |
|---|---|---:|---|
| INV-001 | target coordinate stability | P0 | PASS (TASK-001 fake scope) |
| INV-002 | unrequested region invariance | P0 | PASS (TASK-002 fake scope) |
| INV-003 | protected range | P0 | PASS (TASK-002 HARD_LOCK fake scope) |
| INV-004 | A/V sync preservation | P0 | TODO |
| INV-005 | track state preservation | P0 | TODO |
| INV-006 | relationship preservation | P0 | TODO |
| INV-007 | retime safety | P0 | TODO |
| INV-008 | hierarchy safety | P0 | TODO |
| INV-009 | transition handle | P0 | TODO |
| INV-010 | effect/keyframe | P0 | TODO |
| INV-011 | media identity | P0 | TODO |
| INV-012 | stale plan | P0 | TODO |
| INV-013 | atomic transaction | P0 | TODO |
| INV-014 | no silent partial success | P0 | TODO |
| INV-015 | post-edit verification | P0 | TODO |
| INV-016 | expected vs actual diff | P0 | TODO |
| INV-017 | human edit wins | P0 | TODO |
| INV-018 | marker/subtitle integrity | P0 | TODO |
| INV-019 | track/layer topology preservation | P0 | PASS (TASK-004 fake topology/provenance scope only) |

## 단계 2 — Fake Adapter Integration

- multiple delete
- ripple dependency
- transaction failure injection
- rollback
- version mismatch
- relationship graph

## 단계 3 — Resolve Read-only Integration

- project read
- timeline read
- track read
- item read
- marker read/write
- snapshot consistency

## 단계 4 — Resolve Destructive Sandbox

실제 작업 프로젝트에서 금지.
전용 테스트 프로젝트에서만 수행.

- safe trim
- safe delete
- safe ripple
- rollback validation

TASK-001 validation: 25 passed, 0 failed, 1 opt-in naive demonstration skipped.
Historical TASK-001 result. Current TASK-002 coverage includes INV-001/002/003; INV-004..018 remain TODO. See IMPLEMENTATION_STATUS.md for reproduction and limits.

TASK-002 local validation: 57 passed, 0 failed, 1 intentional naive demonstration skipped. Python 3.11.16 CI also passed: run 37274008568 (PR #1), 57 passed / 0 failed / 1 skipped.


## TASK-003 foundation (not a new invariant PASS)

83 passed / 0 failed / 1 skipped on local Python 3.14.6 and CI Python 3.11.16 (run 37276145821); Ruff and mypy passed.
New coverage: reference integrity, distinct repeated-media placements, immutable graphs,
independent J/L-cut ranges, per-member metadata, no relation-bearing mutation execution.
All existing TASK-001/002 tests retained unchanged. INV-004 and INV-006 remain TODO;
a representational foundation is not proof of sync correction or relationship-aware editing.


## TASK-004 topology foundation

114 passed / 0 failed / 1 skipped locally (Python 3.14.6) and on CI Python 3.11.16 (run 37279654222); Ruff/mypy passed.
Track identity/type/order, membership, expected versus actual diff, artifact-origin rejection,
whole-layer replacement REVIEW and immutable relationship-compatible projection are covered.
TASK-001/002/003 regression files unchanged. INV-004..018 remain uncertified; INV-019
is scoped domain validation, not evidence of native Resolve/editability behavior.


## TASK-005 pure dependency compiler (not execution invariant certification)

Local: 158 passed / 0 failed / 1 skipped; 44 new compiler tests. Ruff/mypy passed.
Python 3.11.16 CI passed: run 37282763459, 158 passed / 1 skipped, Ruff/mypy passed.

| Coverage | Evidence in tests/test_dependency_compiler.py |
| --- | --- |
| AV_LINK DELETE; valid J/L cut | sync REVIEW, original ranges unchanged, no boundary command |
| Subtitle DELETE/TRIM; B-roll anchor | RECALCULATE assessment / anchor REVIEW, no cascade |
| FOLLOW vs STAY; equal policies | conflicting evidence retained / no false conflict for equal metadata |
| Cycle vs diamond/PEER; disconnected cycle | exact directed SCCs, no recursive side effects, unrelated exclusion |
| Finite closure | 1,100-object chain and canonical multi-cycle evidence |
| Primary actions | all six dispatch paths; RETIME unsupported, SPLIT rebinding review |
| Identity and fragments | same media across placements distinct, ambiguous fragment candidates |
| Determinism and immutability | permuted members/relations/registry, repeated compile, frozen results |
| Base integrity | stale/missing target, topology graph/type/order/membership/version/origin rejection |
| Regression | all prior tests unchanged; relationship-bearing fake execution still rejects |

The single skipped case remains the opt-in intentional naive failure. Production
INV-004/full INV-006 and rollback remain unverified; no new invariant is marked PASS.


## TASK-006 candidate authority/concurrency state foundation

Local: 210 passed / 0 failed / 1 skipped; 52 new state tests. Ruff/mypy PASS.
Python 3.11.16 hosted CI passed: run 37287250147, 210 passed / 1 skipped, Ruff/mypy PASS.
No earlier regression tests or executors changed.

| User scenario | Evidence in tests/test_candidate_authority.py |
| --- | --- |
| Selection != approval | Only selection changes; authority and approval retained |
| Approval != apply/promotion | Explicit approval changes one axis; no result/authority writes |
| v42 vs v45; Human Edit Wins | Sticky STALE, blocked eligibility; no base rewrite or old-version resurrection |
| Unverified / verified promotion | Reject created/selected/approved/unverified; accept bound verified supplied result |
| Main -> B -> B2 | Same-base lineage, fresh ID, no copied approval/result or authority switch |
| Active preview switch | Only active ID changes; wrong authority observation rejected |
| Immutable / deterministic | Frozen nested values, same event yields same result, input unchanged |
| Invalid transitions | Mismatched evidence/replay/failed verification/stale/result changes reject |
| No execution | FakeTimeline.apply patched to raise; all pure transitions still work |

The single skip is the intentional naive red demonstration. INV-012/017 are not marked
fully PASS: live observer, actual concurrent apply and transaction/rollback remain absent.


## TASK-007 pause candidates (pure rules, not editing quality certification)

Local 277 passed / 0 failed / 1 skipped; 67 new tests. Ruff/mypy PASS.
Python 3.11.16 CI passed: run 37405319840, 277 passed / 1 skipped, Ruff/mypy PASS.
Earlier source and regression tests unchanged.

| Coverage | tests/test_pause_baseline.py evidence |
| --- | --- |
| No duration-only edit | Different absolute lengths, identical context; no absolute threshold |
| Explicit dead air | Dead-air/failed-take only REMOVE across short and long durations |
| Meaningful pauses | Emotional/thinking/QA/speaker KEEP; conflicts REVIEW |
| Natural breath/hesitation/generic long | Positive supplied target only; never hesitation REMOVE |
| Unsafe target | Missing/zero/negative/equal/longer -> REVIEW, no synthesized target |
| Unknown/scope | Preserve LOW or REVIEW; unsupported scope never proactive edit |
| Routing | HIGH edits -> shadow hint, MEDIUM -> batch, no Apply method/authority |
| Immutable/deterministic | Defensive canonical tuples, permutations, frozen nested reference |
| Systematic combinations | All 128 signal subsets x 5 relative bands x 6 boundaries |
| No execution | FakeTimeline.apply, safety.preflight and authority.transition patched to fail |

One skip remains the opt-in intentional naive failure. Real intelligence accuracy,
production false-removal rate, dialogue cleanup and timeline editing remain unverified.


## TASK-008 evaluation schema / pure derivation

Local: 342 passed / 0 failed / 1 skipped; 65 new tests. Ruff/mypy PASS.
Python 3.11.16 CI passed: run 37408687466, 342 passed / 1 skipped, Ruff/mypy PASS.
Earlier source/regression files unchanged.

| Coverage | tests/test_evaluation.py evidence |
| --- | --- |
| Source isolation / immutable refresh | Feedback cannot carry reference; new proposal/reference values retain old records |
| Append-only ordering | Sequence permutations, immutable append, duplicate IDs/gaps/replay/finalization rejection |
| Typed decision / reference | Payload shape, bound TIGHTEN target, inclusive reference range invariant |
| Outcomes / correction | Finalization, unknown revert result, KEEP vs actual restore, more/less retained direction |
| Missing timing | None/absent kind/partial coverage != explicit zero, measured source metadata retained |
| Paired savings | Scope/mode/case checks, absent pair, zero baseline, negative savings, blocked idle only |
| Editorial metrics | Exact critical definition/denominator, range comparison, review fraction, attention-event count |
| Identity / version | Case/proposal/activity/event binding and uniqueness, schema/producer/reference/metric versions |
| Purity / privacy | Immutable nested collections, deterministic derived result, no classifier/executor/authority calls, no required media/user identity |

Single skip is the intentional naive red demo. Actual benchmark data, pilot experiments,
telemetry accuracy, timing provenance and numerical release gates remain outside scope.


## TASK-009 observation evidence / provenance

Local: 415 passed / 0 failed / 1 skipped; 73 new tests in test_observation_evidence.py.
Ruff and strict mypy PASS. Python 3.11.16 CI PASS: run 37416008719, 415 passed / 1 skipped, Ruff/mypy PASS.
Earlier regression code/tests unchanged; intentional naive red demo remains opt-in.

| Contract coverage | Evidence |
| --- | --- |
| Immutable / defensive copy | Producer, binding, record, bundle, conflict, result and nested tuples |
| Provenance / typed payloads | Required name/version, config, kind-specific types, unknown contract fails closed |
| Strength / assertions | Distinct Confidence type; PRESENT/ABSENT/UNKNOWN versus no record; no confidence conversion |
| Binding / staleness | Mixed timeline/version/placement rejected; current snapshot mismatch; no base rewrite |
| Concrete ranges | Out-of-context rejection, same-media wrong placement, split spans and cross-clip context |
| Narrow mapping | Six explicit PRESENT cues only; absent/unknown/missing do not become positive |
| Conflict diagnostics | Emotional/dead-air, QA/failed-take, assertions, band/boundary/content/reference; IDs retained even stale |
| No hidden priority | Input permutations, agreeing producers, mixed strengths and producer kinds |
| No meaning inference | Silence/duration and TAKE_GAP do not create editorial removal cues |
| Conservative preparation | Required missing/unknown values, unsupported content, crosstalk, unsafe/missing local target |
| Purity / boundary | Determinism and raw retention; classifier/authority/preflight/FakeTimeline patched to fail |

Native FPS/timecode, real media intelligence, live snapshot acquisition, producer truth and
production integration are not verified or implemented by these tests.


## TASK-010 native time / snapshot mapping

Local Windows CPython 3.14.6: 486 passed / 0 failed / 1 skipped; 71 new tests.
Ruff / strict mypy PASS (12 source files). Python 3.11.16 CI PASS: run 37419956502, 486 passed / 1 skipped, Ruff/mypy PASS.
Earlier source/tests unchanged. The skip remains the opt-in intentional naive red demo.

| Contract | tests/test_temporal_mapping.py evidence |
| --- | --- |
| Exact rates | Positive ints, canonical equivalent fractions, 30000/1001 != 30/1, reject floats/bools |
| Coordinate separation | Distinct typed wrappers; raw/wrong domain rejected, same numbers mean different positions |
| Explicit correspondence | IDENTITY_1X/equal spans and AFFINE_FORWARD both directions; rates never used as transform |
| Mixed FPS | Integral boundaries EXACT, either/both fractional boundaries NON_INTEGRAL; no output pair on failure |
| Exact arithmetic | Large 10**30 origins and exhaustive small-span divisibility/roundtrip oracle |
| Containment | One-frame outside rejects, exact endpoints, half-open split boundary, no clamp or fragment union |
| Identity / ambiguity | Repeated media placements, wrong identity, multiple containing spans, duplicate mapping refs |
| Staleness | Timeline/version/state token mismatch; old+fresh candidates never silently replace historical binding |
| Unsupported kinds | REVERSE/FREEZE/VARIABLE_RETIME/UNKNOWN never identity-lowered |
| Immutable / deterministic | Frozen nested values, defensive tuples, permutations, invalid result shapes rejected |
| Purity | Classifier/authority/preflight/FakeTimeline/evidence calls forbidden; only pure stdlib/domain imports |

These tests do not certify retime safety, native correspondence, production timecode parsing,
state-token realization, real Resolve behavior, actual A/V sync or rollback.


## TASK-011 read-only snapshot / feature readiness

Local Windows CPython 3.14.6: 563 passed / 0 failed / 1 skipped; 77 new tests.
Ruff / strict mypy PASS (13 source files). Python 3.11 CI: pending PR run.
Previous source/tests unchanged. One skip remains the intentional opt-in naive failure.

| Contract | tests/test_native_snapshot.py evidence |
| --- | --- |
| Immutable snapshots/provenance/profile/result | Frozen fields, nested defensive tuples, repeated deterministic evaluation |
| Identity lifetime | Four categorical scopes, no numeric confidence, filename basis rejected, snapshot-assigned not promoted |
| Capability versus value | SUPPORTED + UNKNOWN valid; unsupported/unknown cannot carry TRUE/FALSE; omitted capability unknown |
| Consistency | CONSISTENT needs supplied reference, UNSTABLE review, UNVERIFIED fails consistency requirement |
| Completeness versus readiness | PARTIAL not auto-ready, absent supported fields reject complete claim, richer profile UNKNOWN review |
| Freshness | No state token synthesis, missing token/current ref blocked; timeline/version/token mismatch STALE |
| Native membership | Repeated media distinct, duplicate IDs/member mismatch/unknown tracks/mixed captures reject |
| Descriptive metadata | Track index/name no role/identity inference; provenance retained |
| Retime/ranges/rates | UNKNOWN retained, unsupported kinds represented but analysis blocked; timeline rate coherence |
| Optional risks/states | Effects/transitions/keyframes/hierarchy/link/sync and lock/mute/enable/solo/autoselect typed only |
| Execution boundary | Mapper/classifier/relationship compiler/evidence/safety/authority/FakeTimeline forbidden; pure imports |

Initial missing-module red reproduced before source. Additional tests reproduced unknown
track type passing READY and conflicting timeline rate acceptance before fixing both.
Real Resolve/API capability, identity/token truth, actual atomic capture, A/V or rollback
integration remain unverified; no production P0 certification.
