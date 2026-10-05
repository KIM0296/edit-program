# Test Matrix

## 단계 1 — Pure Domain Tests

실제 Resolve 없이 수행.

| ID | 테스트 | 우선순위 | 초기 상태 |
|---|---|---:|---|
| INV-001 | target coordinate stability | P0 | TODO |
| INV-002 | unrequested region invariance | P0 | TODO |
| INV-003 | protected range | P0 | TODO |
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
