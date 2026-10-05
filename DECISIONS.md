# Architecture Decisions

# Accepted Decisions

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

## ADR-007 — Main Repository and Product-first Development
Status: ACCEPTED — 사용자 지시, 2026-10-05

이 저장소를 메인 제품으로 삼고 기존 영상 편집자동화 시스템연구는 재사용 자산/검증 사례로 보존한다. 제품은 Mac 전용이 아니며 Windows는 현재 개발 환경이다. OS별 설치·권한·연결 검증은 핵심 구축 후 마무리 단계에 수행한다. 기존 Safety Core 경로를 유지하며 이번 결정은 invariant 완화나 실제 API 검증 생략을 뜻하지 않는다. 비교 결과: (historical review artifact is not present in this repository).

## ADR-008 - Integer Half-open Internal FrameRange
Status: ACCEPTED - Chat Gate Review, 2026-10-05

All internal FrameRange values use integer half-open [start, end) coordinates.

## ADR-009 - Version Advances on Successful Plan Commit
Status: ACCEPTED - Chat Gate Review, 2026-10-05

TimelineVersion increases by one per successfully committed EditPlan/Transaction,
not per command. Failure or rollback does not increase it. An empty fake plan is
an uncommitted no-op. This decision does not authorize transaction/rollback implementation.

## ADR-010 - TASK-002 ProtectedRange Is HARD_LOCK
Status: ACCEPTED - Chat Gate Review, 2026-10-05

Direct edits and ripple-induced absolute timeline position changes are violations.
Reject the entire offending plan before mutation. No override is provided in TASK-002.

## ADR-011 - Unrequested Content Preservation
Status: ACCEPTED - Chat Gate Review, 2026-10-05

INV-002 preserves unrequested media identity, source range, and content order.
Timeline positions may change only by ripple displacement explicitly approved in EditPlan.

## ADR-012 - Fake Placement Lineage Identity
Status: ACCEPTED - Chat Gate Review, 2026-10-05

TASK-001 FakeTimeline clip_id is fake placement lineage identity, not a production
persistent TimelineItem ID. Resolve persistent identity remains OPEN-001.

# Open Decisions

## OPEN-002 — Candidate Approval and Live Timeline Authority
Status: OPEN

Context: 기존 요구는 별도 후보 비교와 승인 후 다음 기준본 자동 선택이다. 메인 계약은 Resolve 실제 상태 우선 및 stale plan 자동 실행 금지다.
Observed behavior: 구 workflow.select는 로컬 선택만 기록하며, batch planner는 과거 후보 recipe를 사용한다. 사람의 이후 편집까지 보존하는 일반 snapshot 기반 revision은 미구현이다.
Options: 후보 선택과 실제 현재 snapshot 검증을 분리하거나, 후보를 명시적으로 활성화한 후 검증된 snapshot을 다음 요청의 기준으로 채택한다.
Recommendation: 선택/승인 이력은 유지하되 매 요청의 실행 기준은 최신 실제 snapshot으로 검증한다. 진행 중 plan의 자동 rebase/자동 승인은 하지 않는다.
Needs Chat decision: 후보 승인 시 Resolve 활성 타임라인 전환·저장까지 포함하는지, 재생 후보와 현재 타임라인이 다를 때의 기본 UX. 이번 검토에서는 확정하거나 구현하지 않는다. TASK-001을 막지 않는다.

## OPEN-001 — Persistent Timeline Item Identity
Status: OPEN

Resolve에서 session/프로젝트 재오픈 후에도 신뢰할 수 있는 persistent TimelineItem ID를 확보할 수 있는지 runtime/API 검증이 필요하다.

Options to investigate:

1. native unique id
2. media pool identity + source range + track context
3. synthetic session id
4. composite fingerprint

이 결정을 TASK-001에서 임의로 확정하지 않는다.

## OPEN-004 — Range boundaries and multi-item delete scope
Status: PARTIALLY RESOLVED by ADR-008/010/011; cross-clip and multi-track scope remains OPEN

Context: TASK-001 does not specify end-frame inclusion, gaps, overlapping requests,
or ripple participation across tracks and clips.
Observed behavior: a minimal INV-001 fixture needs an exact frame interval convention.
Options: half-open versus inclusive end; split cross-clip requests versus review;
track-local versus dependency-based ripple.
Codex recommendation: use integer [start, end) only inside the TASK-001 fake;
accept one track, 1:1 source mapping, and targets contained in a single clip fragment.
Reject unsupported or overlapping requests explicitly, without choosing production policy.
Needs Chat decision: confirm production interval and ripple scope before broadening support.

## Chat Gate resolution - TASK-001 / TASK-002, 2026-10-05

TASK-001 Domain Model, FakeTimeline, StableTarget and INV-001: APPROVED WITH CHANGES.
ADR-008..012 above record the explicit user approval in this session.
OPEN-003 is resolved for fake lineage and version granularity by ADR-009/012;
production split identity remains deferred to OPEN-001.
OPEN-004 is resolved for interval convention and TASK-002 protection/ripple policy
by ADR-008/010/011. Multi-track and cross-clip request scope remains OPEN and unsupported.
Original OPEN descriptions are retained as historical context, not competing policy. Current status labels and accepted ADRs take precedence.
TASK-002 is authorized only for INV-002/003; work on feat/task-002-inv002-inv003,
submit a PR, and request Chat Gate. Do not merge or proceed to further tasks automatically.

# Resolved Decision History

## OPEN-003 — Split identity and version granularity
Status: RESOLVED FOR FAKE by ADR-009/012; production identity remains OPEN-001

Context: stable targets must survive an earlier delete within the same plan, while stale
plans cannot execute. Persistent identity is already OPEN-001.
Options: fragment IDs with parent lineage versus composite source identity; version per
edit versus per plan. Production transaction/rollback semantics remain a separate task.
Codex recommendation: fake-only clip_id denotes placement lineage; fragments retain it
and are distinguished by source range. Distinct placements require distinct clip IDs.
The fake checks the base snapshot before application and advances version once per plan.
Needs Chat decision: production split identity and version/transaction boundaries.
No Resolve identity, automatic rebase, or rollback guarantee is established by TASK-001.
