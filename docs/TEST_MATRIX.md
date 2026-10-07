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
Ruff / strict mypy PASS (13 source files). Python 3.11.16 CI PASS: run 37422177969, 563 passed / 1 skipped, Ruff/mypy PASS.
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


## TASK-012 pause edit planning

Local Windows CPython 3.14.6: 645 passed / 0 failed / 1 skipped; 82 new tests.
Ruff / strict mypy PASS (14 source files). Python 3.11.16 CI PASS: run 37424238137, 645 passed / 1 skipped, Ruff/mypy PASS.
Previous source/tests unchanged. Single skip remains intentional opt-in naive red demo.

| Contract | tests/test_pause_planning.py evidence |
| --- | --- |
| KEEP / REVIEW | NO_OP / REVIEW_ONLY even with supplied invalid/stale geometry; no proposal |
| Explicit geometry | Missing TIGHTEN/REMOVE geometry blocked; no retained-only generation |
| TIGHTEN | One contained range, exact retained arithmetic; multi/zero/outside/mismatch fail closed |
| REMOVE | Explicit full-pause, zero retained; partial/adjacent-speech expansion rejected |
| No repair | One-frame overflow and arbitrary valid supplied cut positions preserved verbatim |
| Binding / Human priority | Candidate/geometry/facts timeline/version/token, placement/pause/candidate ref checks |
| Target / snapshot readiness | Only supplied current EXACT/READY; missing and all other statuses block |
| Primary-range exactness | Whole-pause EXACT cannot authorize different removal boundaries |
| Dependency | Unresolved/conflict/unsupported, geometry ID/range/intent mismatch blocks; no cascade |
| Confidence / repeated media | HIGH cannot bypass gates; media identity cannot rebind placement |
| Immutable / deterministic | Frozen nested values, defensive tuples, raw reasons/input retention |
| Pure boundary | No mapper/evaluator/classifier/compiler/evidence/safety/authority/executor; import whitelist |

No geometry resolver, native runtime, Safety certification, actual A/V sync, mutation or
rollback integration is implemented/tested. READY_FOR_PREFLIGHT is not Safety PASS.


## TASK-013 Cut Geometry Resolution

87 tests in tests/test_cut_geometry.py cover typed immutable inputs/results, defensive
copies, four constraint kinds, confidence type separation, all confidence combinations,
explicit and paired-anchor paths, no duration-only defaults, exact arithmetic/no repair,
preserve overlap, allowed-range intersection, dedup with all provenance, deterministic
permutations, mixed/current binding, non-EXACT mapping, cross-placement/multi-range failure,
unchanged editorial action, retained leading/trailing totals and invalid diagnostics.
Monkeypatch isolation blocks mapper, snapshot readiness, classifier, evidence preparation,
planner, relationship compiler, safety, authority and FakeTimeline.apply. Import whitelist
excludes media-analysis and execution dependencies.

Red first: spec notes dae94b0, test commit 7cc71f8; missing cut_geometry module produced
one collection error before implementation. Local full suite: 732 passed, 0 failed,
1 intentional naive-demo skip. Ruff and strict mypy (15 source files) PASS.
Python 3.11.16 CI PASS: run 37426493653, 732 passed / 1 skipped; Ruff/mypy PASS. Earlier TASK-001..012 source/tests unchanged.


## TASK-014 Expected Diff and synthetic verification

78 tests in tests/test_expected_diff.py cover immutable typed values, defensive ordering,
exact primary copy (TIGHTEN/REMOVE), supplied-only/empty participant sets, uniform -D,
nonuniform/crossing/cross-track/unsupported-retime rejection, gap consequence requirements,
explicit scope coverage, unchanged object invariance, metadata preservation and J/L boundaries,
protected-risk versus Safety separation, current/proposal/geometry/base mismatch, no repair,
exact synthetic comparison, missing/extra changes, one-frame error, before/source/media/track/
duration/retime/identity failures, incomplete identity/coverage, stale post relation and
constructor guards. Monkeypatches block mapper/evaluator/planner/resolver/compiler/classifier/
Safety/Authority/FakeTimeline execution; import whitelist excludes native/media infrastructure.

Red first: notes 46adfff, tests 99bab2e; missing expected_diff module caused one collection
error before implementation. Local full suite: 810 passed / 0 failed / 1 intentional naive
skip. Ruff and strict mypy (16 source files) PASS. Python 3.11.16 CI PASS: run 37558489702, 810 passed / 1 skipped; Ruff/mypy PASS.
Existing TASK-001..013 source/tests unchanged; native integration/rollback remain unverified.


## TASK-015 Safety Preflight Integration

126 tests in tests/test_safety_preflight.py cover all 55 prepared-spec requirements:

| Required IDs | Coverage |
| --- | --- |
| 1-6 | Frozen values, defensive ordering, exact 17-check profile, strict result aggregation constructors |
| 7-9 | All status/verdict combinations and retention of reject/review/incomplete findings |
| 10-12 | Current/context freshness, non-ready ExpectedDiff, primary/proposal integrity and no repair |
| 13-19 | Complete-empty/incomplete protection, direct/displacement HARD_LOCK, every affected track lock |
| 20-23 | Precomputed relationship/dependency unknown, exact forward, unknown/unsupported/conflicting retime |
| 24-28 | Corrupted displacement media/source/duration/track guards and unsupported topology |
| 29-35 | Transition/effect/keyframe full five-state matrices |
| 36-38 | Wrong/stale diff/snapshot/subject/kind/version/outcome proof; no proof production |
| 39-43 | Scope omission, all-check PASS, review/reject and diagnostic precedence |
| 44-45 | No confidence/override path or repair/replanning |
| 46-54 | Monkeypatch layer isolation, import whitelist, no runtime/execution dependencies |
| 55 | TASK-001..014 full regression retained unchanged |

Red-first notes e565d81 and tests 05b12a5 precede source; missing safety_preflight module
caused one collection error. Local full regression: 936 passed / 0 failed / 1 intentional
naive-demo skip. Ruff PASS; strict mypy PASS (17 source files). Python 3.11.16 CI PASS: run 37561231902, 936 passed / 1 skipped; Ruff/mypy PASS.
Native proof authenticity, actual Resolve integration and rollback remain unverified.


## TASK-016 Transaction / Postflight foundation

96 tests in tests/test_transaction.py cover all 48 prepared requirements:

| Required IDs | Coverage |
| --- | --- |
| 1-5 | Frozen values, defensive lists, separate enum axes, exact terminal prerequisites |
| 6-10 | Normal phase path, forbidden direct commit, stale/blocked precommit, partial failure |
| 11-18 | UNKNOWN distinct, no retry, fresh reconciliation, native report insufficient, MATCH-only commit |
| 19-23 | Exact capability/policy enums, default derivation and full supported policy/request matrix |
| 24-30 | Command result versus base verification, recovered failures, mismatch/unknown lockdown, no promotion |
| 31-35 | Strict current promotion facts and authorization/diff/Safety/base bindings |
| 36-40 | Monotonic journal, append-only failures and recovery, immutable definition binding, determinism |
| 41-47 | Monkeypatch isolation and import whitelist; no native/Undo/snapshot/compiler/Safety/Authority/executor calls |
| 48 | TASK-001..015 full regression unchanged |

Red-first spec notes e6c8f56 and tests db3dbd1 precede source; missing transaction module
caused one collection error. Local full regression: 1032 passed / 0 failed / 1 intentional
naive-demo skip. Ruff PASS; strict mypy PASS (18 source files). Python 3.11.17 CI PASS: [run 37565075683](https://github.com/KIM0296/edit-program/actions/runs/37565075683), 1032 passed / 1 skipped; Ruff and strict mypy PASS (18 source files).
Actual Resolve atomicity, rollback reliability and native postflight proof remain unverified.

## TASK-017 — Validated Execution IR

`tests/test_execution_ir.py`: 117 new tests. Full regression: 1149 passed, 1 intentional naive-demo
skip. Ruff PASS; strict mypy PASS (19 source files). Python 3.11 CI PASS: [run 37572985389](https://github.com/KIM0296/edit-program/actions/runs/37572985389). PR #37; final-head evidence in PR body.

| Prepared requirements | Tests / evidence |
| --- | --- |
| 1 | immutable_defensive_copy_determinism; all_nested_records_frozen_and_source_unchanged |
| 2–5 | vocabulary_exact_and_ready_effects; ir_exact_semantics |
| 6–9 | ir_exact_semantics; duplicate_realization_is_invalid; two_independent_realizations_each_once |
| 10–12 | vocabulary_exact_and_ready_effects; native_exact_effect_multiplicity; effect_model_matrix |
| 13–17 | identity_matrix; session_requires_all_proofs; session_change_is_stale_and_locator_not_identity |
| 18–22 | target_resolution; structural_binding_gaps_fail_closed; session_change_is_stale_and_locator_not_identity |
| 23–24 | fragment_decomposition_requires_bound_verified_evidence; compound_fragment_path |
| 25–28 | capability_matrix (four states across primitive/identity/post-read/reconciliation) |
| 29–34 | effect_model_matrix; model_evidence_required; native_exact_effect_multiplicity |
| 35 | scope_expansion_not_repaired; structural_binding_gaps_fail_closed |
| 36–37 | each_step_postread_and_reconciliation_required; reconciliation_evidence_required |
| 38 | rollback_separate (all four states) |
| 39–40 | runtime_profile_currentness; bound_evidence_cannot_be_transplanted; missing_primitive_no_runtime_fallback |
| 41–42 | ir_exact_semantics; scope_expansion_not_repaired; structural_binding_gaps_fail_closed |
| 43–47 | no_upstream_or_execution_calls; import allowlist; pure value-only module |
| 48 | full TASK-001..016 pytest regression |

Additional: Safety non-PASS blocking, authorization currentness, contract versions, forged result
rejection, status precedence and complete diagnostic retention. Native integration remains unverified.

## TASK-018 — Probe evidence qualification

`tests/test_probe_evidence.py`: 110 new tests; full regression 1259 passed / 1 intentional naive-demo
skip. Ruff PASS; strict mypy PASS (20 source files). Python 3.11 CI PASS: [run 37575858937](https://github.com/KIM0296/edit-program/actions/runs/37575858937). PR #40; final-head evidence in PR body.

| Prepared requirements | Tests / evidence |
| --- | --- |
| 1–2 | immutable_copy_append_and_deterministic_result; axis_enums_are_independent_and_typed |
| 3–5 | invalid_fixture_nonqualifying; authoritative_working_fixture_cannot_qualify; clean_independent_fixture_required |
| 6–7 | exact_profile_stale; mixed_profile_evidence_is_stale; independent_evidence_wrong_profile_cannot_be_promoted |
| 8–11 | axis_enums_are_independent_and_typed; incomplete_scope_blocks_even_with_extra_passes; missing_observed_subject_and_category_incomplete |
| 12–16 | exact_budget; not_a_pass_rate; coverage_not_just_total_count; policy_explicit_cannot_weaken; one_missing_positive_with_all_challenges_never_qualifies; challenges_cannot_substitute_for_positive_budget |
| 17–22 | exact_budget; conflict_preserved_no_majority_recency_or_filtering; verified_effects_only_when_all_inside_runs_agree |
| 23–24 | observed_collateral_changes_never_filtered (all 9 subject kinds); observed_addition_and_deletion_not_lost; conflict_preserved_no_majority_recency_or_filtering |
| 25–26 | zero_tolerance; out_of_scope_observation_retained_and_fails_containment; api_success_alone_insufficient_and_availability |
| 27–30 | missing_provenance_rejected; exact_profile_stale; mixed_profile_evidence_is_stale |
| 31–35 | exact_budget; policy_explicit_cannot_weaken; api_success_alone_insufficient_and_availability; forged_derived_result_rejected |
| 36–39 | post_read_independent; reconciliation_axis; axis_enums_are_independent_and_typed |
| 40–43 | weak_identity_not_execution_grade; uuid_not_persistent_proof_and_session_staleness; wrong_identity_subject_and_unverified_correspondence |
| 44–46 | fragment_status_independent; fragment_heuristics_not_proof; fragment_required_but_missing |
| 47–48 | clean_independent_fixture_required; duplicate_capture_cannot_inflate_repetitions; immutable_copy_append_and_deterministic_result; conflict_preserved_when_later_profile_stales |
| 49–54 | no_runtime_or_upstream_calls; import allowlist; no executable native surface or production conversion |
| 55 | full TASK-001..017 pytest regression |

Additional: outside-domain unsupported isolation; anti-narrowing binding; explicit bounded invocation;
all failure statuses; extra inconclusive run with full positive budget; status/contract typing; all
finding retention. Fixtures and complete observations are synthetic, not runtime proof or native coverage.

## TASK-019 — Probe harness / ADR-035 control plane

All tests below are synthetic pure-domain tests in `tests/test_probe_harness.py`; native Resolve
behavior is unverified. Parametrization yields 88 new tests. Original specification coverage:

| Spec requirements | Tests / evidence |
| --- | --- |
| 1–2 immutable / defensive copies | `test_immutable_defensive_copy_deterministic`, suite copies, frozen seal |
| 3–6 isolation / exact registration | production/working rejection, name/path/sentinel, environment exact binding |
| 7–10 lifecycle / clean-only | legal/illegal transitions, MATCH-only fixture verification |
| 11–15 dirty / fresh instance / no Undo | non-MATCH cases, no repair, materialization identity reuse rejection, no-native import guard |
| 16–22 one-run exact authorization | 30 mismatch cases across both modes; repeated final gate, used auth, invalidated lease; constructor binding |
| 23–24 modes | exploratory no qualifying count; exploratory runs through identical gates |
| 25–27 fixed symmetric observation | scope mismatch, expanded post-scope retention, partial/stale observation blocks |
| 28–31 containment / generation | four-class matrix; contaminated cannot clean in place; explicit new generation; old proof stale |
| 32–35 uncertainty / crash | four acknowledgement outcomes, pre-crash new verification/run, post-crash quarantine; no cancellation field |
| 36–39 discard / seal | mutated pass/fail never reused; evidence survives discard; seal requires bound submission/observation/containment |
| 40–41 fixture definition / assets | wrong version cannot verify; required asset hash/metadata (no filename inference) |
| 42–43 domain declaration / no narrowing | final-gate domain mismatch; sealed history cannot change declared domain |
| 44–45 suite / efficiency | immutable refs include failed evidence; matching primitive/profile, no ordinary-edit purpose; zero editor work |
| 46–49 prohibited calls | monkeypatched qualification/evaluator/transaction/authority/FakeTimeline; static import guard; no native callback |
| 50 regression | TASK-001–018 plus TASK-019: 1347 passed, 1 intentional naive-demo skip |

ADR-035 additions:

| Rule | Tests / evidence |
| --- | --- |
| registration != verification != arming | `test_registration_verification_arming_are_separate` |
| exact verification / only clean generation | four non-VERIFIED statuses, registry/generation/catalog/profile mismatch |
| unique fixture lease / no global arm | second active lease rejected; authorization tied to one run; typed target containment |
| validation failure consumes | 30 mismatch cases, invalidated lease, BLOCKED gate; all have zero attempts |
| submission consumes for every native outcome | SUCCEEDED / FAILED / TIMEOUT / OUTCOME_UNKNOWN, duplicate ack/gate rejection |
| local failure -> reverify / failure -> contamination | independent fresh read after discard; verified/mismatch/incomplete matrix |
| contamination cannot recover in place | direct verification/reverification rejected; new generation retains old seals |
| uncertainty -> BLOCKED / no cancellation | pending attempt retained; no retry; no cancellation method |
| diagnostics retained | multiple final-gate failures, unexpected scope and native failure records retained |
| no native authenticity invented | opaque supplied registration evidence only; OPEN-020 documented |

Python 3.11.16 CI PASS: [run 37578746926](https://github.com/KIM0296/edit-program/actions/runs/37578746926); 1347 passed / 1 skipped, Ruff and strict mypy PASS.

## TASK-022 — Canonical generator and first-package candidate

| Spec requirements | Evidence |
| --- | --- |
| 1–9 video / frozen recipe / glyphs / pixels / source digest | Literal independent A/7 glyph and selected frame 0/1/23/24/719 pixels, MSB binary order, bar, roles, invalid indices; source digest mismatch rejection |
| 10–18 PCM / WAV | Literal stereo samples at requested boundaries, signed packing/interleave, exact length, integer deterministic source, strict RIFF fmt/data header |
| 19–24 serialization / hash / paths / sealing | Canonical byte literals, malformed data, traversal, checksum/digest mismatch, collisions, reservation ownership |
| 25–30 typed commands / errors / schema | Closed recipes; unsupported capability; encoder/decode failure; manifest/lock schema; no arbitrary flags or shell |
| 31–39 actual FFmpeg integration | Locked Windows FFmpeg: real DNxHR LB MOV + PCM copy mux; explicit stream/frame/WAV evidence; full video and audio decode |
| 40–54 full build / real hashes / equality / index | Two fresh six-asset runs; all nine files exact byte equality; complete pre-seal validation; actual hashes and sealed local candidate |
| 55 no ordinary Git media | Only small metadata/index/comparison evidence added to canonical_assets/first-package-candidate-v1 |
| 56–59 regression / Python 3.11 / Ruff / mypy | Local Python 3.11.9: 1417 passed / 2 skipped; Ruff PASS; strict mypy 33 files PASS; Python 3.11 CI 1418 passed / 1 skipped; run 37591852493 linked in report |

71 new cases: 70 passed / 1 Windows symlink privilege skip. Existing naive INV-001 opt-in red demo also
skipped in full regression. Ordinary CI excludes full media generation; the explicit real integration
command and sealed output are recorded in docs/reports/TASK_022_COMPLETION.md. No Resolve tests ran.

## TASK-020 — read-only adapter and qualification protocol

55 tests across test_read_probe_values.py, test_read_probe_adapter.py, test_read_probe_runner.py.

| Requirement | Test coverage |
| --- | --- |
| Immutable nested evidence / defensive copy / bool-not-int | values, adapter |
| Fixed installed read allowlist / no mutation imports or calls | adapter surface AST + fake call records |
| Profile, project, generation, timeline binding / fresh root fence | adapter + runner |
| Raw vs semantic / None,false,empty / floats UNKNOWN | values + adapter + writer |
| Unique, zero, ambiguous role / repeated-media no collapse | adapter |
| Native ordering only / no ID or filename fallback | adapter |
| F0 links, F2 track state, F3 markers/subtitle, timeline geometry | adapter |
| Stable capability vs wrong fixture / Tier C not absent | adapter + qualification |
| Ten pairs, no retry, preserved failure, operator interference | runner |
| Three external F4 roundtrips / S1 identity baseline retained | runner |
| Evidence append-only / missing or changed bytes / seal verification | runner |
| All 44 RV rows / six pair tables / three S2 rows | writer + unavailable discovery |
| Actual runtime qualification | NOT EXECUTED; actual diagnostic RUNTIME_UNAVAILABLE / HOLD |

Red observed: initial missing modules; wrong native timeline end and missing F0 links accepted;
F3 missing host misclassified; mutable payload accepted; missing persisted capture not rejected.
Each was corrected before green. Actual native evidence remains separate from these mocks.
