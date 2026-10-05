# Architecture Decisions

## ADR-001 — Resolve is Source of Truth
Status: ACCEPTED

AI는 별도 authoritative timeline을 유지하지 않는다.

## ADR-002 — Frame Integer as Internal Time Primitive
Status: ACCEPTED FOR DOMAIN PROTOTYPE

초기 domain model은 float seconds보다 integer frame을 우선한다.
Drop-frame/timecode 표현은 별도 mapping layer에서 처리한다.

## ADR-003 — No Filename-only Media Identity
Status: ACCEPTED

Media identity는 filename 단독으로 결정하지 않는다.

## ADR-004 — Stale Plan Cannot Auto-Execute
Status: ACCEPTED

base timeline version과 current version이 다르면 destructive plan을 그대로 실행하지 않는다.

## ADR-005 — Safety Core Before Resolve Destructive Integration
Status: ACCEPTED

P0 domain tests 없이 destructive Resolve integration을 시작하지 않는다.

## ADR-006 — LLM Emits IR Only
Status: ACCEPTED

LLM이 Python/Lua/Resolve scripting code를 직접 실행 경로에 생성하지 않는다.

---

# Open Decisions

## OPEN-001 — Persistent Timeline Item Identity
Status: OPEN

Resolve에서 session/프로젝트 재오픈 후에도 신뢰할 수 있는 persistent TimelineItem ID를 확보할 수 있는지 runtime/API 검증이 필요하다.

Options to investigate:

1. native unique id
2. media pool identity + source range + track context
3. synthetic session id
4. composite fingerprint

이 결정을 TASK-001에서 임의로 확정하지 않는다.
