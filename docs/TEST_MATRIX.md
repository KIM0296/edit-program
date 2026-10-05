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
