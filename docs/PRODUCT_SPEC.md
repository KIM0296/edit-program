# Product Spec

## 제품 정의

DaVinci Resolve에서 작업 중인 영상을 AI가 이해하고, 자연어 요청을 안전한 편집 명령으로 변환하여 반복적인 탐색·판단·러프컷 시간을 줄이는 AI Assistant Editor.

## 초기 타깃

DaVinci Resolve를 이미 사용하면서 편집 시간이 비용으로 직결되는 사용자.

- YouTube 편집자
- 인터뷰 / 팟캐스트 편집자
- 1인 제작자
- 영상 외주 편집자
- 소규모 프로덕션
- 콘텐츠 팀

## 장기 사용자 경험

### Expert Assist
전문가가 결정을 유지한다.

- 선택 영역 기반 명령
- 정확한 timecode / frame
- preview / approve
- conservative automation
- 기존 편집 보존

### Guided Edit
일반 사용자가 결과 옵션을 경험한다.

- Conservative
- Balanced
- Aggressive
- 장르 preset
- 여러 edit version preview

초기 제품은 Expert Assist에 우선한다.

## 핵심 가치

North Star Metric:

**Net Editing Time Saved**

```text
기존 예상 편집 시간
- AI 사용 시간
- AI 결과 검수 시간
- AI 오류 수정 시간
= 실제 절감 시간
```

AI가 빠르게 결과를 만들었다는 사실만으로 성공으로 보지 않는다.

## 핵심 품질 철학

- Zero-shot Quality Floor
- Style Bootstrap
- Confidence-gated Autonomy
- Shadow Learning
- Pause Intelligence
- Timeline Integrity

개인화는 낮은 품질을 구제하는 수단이 아니다.

```text
나쁜 첫 결과 → 학습 → 좋은 결과
```

가 아니라:

```text
쓸 만한 첫 결과 → 조용한 학습 → 사용자 스타일에 가까운 결과
```

이어야 한다.


## Preserve Editability / Native Editing Environment Preservation

Approved in TASK-004 user instruction: AI edits must retain the native Track/Layer/Object
structure so the user can continue individual editing. Preview/render output may flatten,
but must not replace editable project state or become the editable source of truth.
Track additions/removals/moves require explicit expected topology changes (INV-019).

## Preferred Effects Implementation Path (future product boundary only)

1. Editorial effects: prefer Edit Page / Resolve FX.
2. Motion graphics, tracking and simple compositing: consider Fusion first when feasible.
3. Fusion is preferred, not required.
4. Unrestricted full Fusion automation is not initial scope.
5. Future effect automation should prioritize editable, reversible, inspectable structures.
6. Complex specialist VFX: prioritize VFX Assist / Handoff over direct automation.
7. External VFX integrations are later priorities, considered only when they preserve the
   native editing environment. These notes authorize no TASK-004 effect implementation.

## Attention Economy v1 (approved TASK-006 product notes)

The goal is to minimize time to the final editable result by reducing Human Active
Time, Mandatory Attention Time, Decision Interruptions, AI-induced idle time and
conflict rework; maximizing the number of automated actions is not the objective.

- **Batch Decisions by Default:** collect non-blocking review items for grouped review
  rather than interrupting the editor with one question at a time.
- **Automate Bundles, Not Clicks:** prioritize time-consuming bundles of search,
  repetition, analysis and candidate generation. This does not prohibit small commands.
- **Prepare the Decision, Don't Offload the Problem:** future review should prepare
  Original, AI Proposal, Difference, Reason, Impact and Available choices, rather than
  asking the editor to diagnose an unprepared problem.

These are product/architecture notes only. TASK-006 adds no UI, notifications, review
batching implementation, metric instrumentation or telemetry.


## Effect / VFX Boundary v1

The product does not equate technical possibility with product responsibility.

### E1 - Editorial Effects
Core editor-level effects may be supported directly after normal safety validation.

### E2 - Controlled Motion / Simple Composite
Support is limited and should favor validated editable primitives/templates. For a
Resolve-centered implementation, Fusion is preferred when appropriate, but not required.

### V1 - VFX Assist / Handoff
Complex roto, difficult removal/keying/tracking/reconstruction and similar specialist work
should be identified, scoped and prepared for handoff rather than freely automated.

### V2 - Specialist VFX
Outside the core Assistant Editor responsibility.

Effect automation eligibility depends on Predictability, Reversibility, Inspectability,
Editability and Verifiability. Existing effect/node/keyframe structures are user-owned.

**Initial product decision: no unrestricted Effect ALL Auto.** The project will first prove
time savings and safety for bounded E1/E2 primitives. A future validated Effect Auto Pass may
be reconsidered over an approved primitive set; it is not part of the initial scope.

Color, Audio and Generative Asset Creation remain separate product verticals.


## Pause / Dialogue Editing v1

The first value vertical is spoken-content pacing and conservative dialogue cleanup.

### Decision vocabulary

- KEEP: preserve the pause.
- TIGHTEN: reduce, but do not erase, the pause.
- REMOVE: only high-confidence meaningless recording gaps/dead air.
- REVIEW: defer ambiguous editorial intent to the editor.

Absolute pause duration never determines removal by itself. Local pacing, dialogue structure,
speaker transition, question/answer context, semantic continuity and supplied prosodic evidence
may influence the decision when available.

The first implementation uses HIGH / MEDIUM / LOW confidence bands. HIGH-confidence changes may
enter a Shadow Candidate, MEDIUM-confidence items are batched for review, and LOW-confidence
items remain unchanged or require review. Main is never silently mutated by confidence alone.

### v1 dialogue scope

Included: immediate restarts, short repetitions, obvious self-corrections, excessive hesitation
and conservative filler candidates.

Excluded from automatic deletion: long-range semantic redundancy, story restructuring, best-take
selection, narrative pacing, automatic B-roll/effect/music decisions and fully automatic filler
removal.

### Initial genre scope

Interview, talking head, podcast/video podcast, lecture, commentary and similar spoken content.
Narrative film, drama, music video and experimental pacing remain outside the first vertical.

### Success metrics

Primary: Net Time Saved, Human Active Time, Review Time, Correction Time, false removal of necessary
pauses, accepted suggestion rate and reverted AI edits.

Compression ratio is not a quality target.

### TASK-007 implementation boundary

Start with immutable Pause Candidate domain/schema and deterministic conservative rules over
caller-supplied observations. Do not add STT/VAD/prosody inference/LLM reasoning or real timeline
mutation in the first implementation.


## Evaluation Data Contract & Feedback Event Schema v1

Pause Intelligence evaluation separates immutable evidence from derived metrics.

- BENCHMARK: fixed adjudicated reference judgments for regression/model comparison.
- PILOT: reference + assisted workflow evidence for gate calibration.
- PRODUCT_FEEDBACK: real-use decisions, corrections, reverts and timing; not benchmark truth.

Store immutable AI proposal snapshots and append-only feedback/timing evidence. Derived outcomes,
correction classes and metrics must be reproducible from raw evidence. Proposal refresh creates a new
proposal rather than mutating the old one.

Primary derived product metrics include critical false removal, TIGHTEN range quality, review load,
decision interruptions, correction debt, human active/mandatory attention time and net time saved.
Numerical gate thresholds remain a separate versioned policy and are not set before pilot evidence.

The core product-feedback contract should work with opaque references and metadata without requiring
raw media/full transcripts. Feedback collection does not imply training consent.


## Observation Evidence & Producer Provenance v1

Pause Intelligence does not allow VAD/STT/prosody/semantic producers to directly author executable
edits. Producers emit immutable, typed evidence bound to a specific timeline snapshot, placement and
observed range.

Evidence assertions distinguish PRESENT, ABSENT and UNKNOWN; missing evidence is the absence of a
record and is never interpreted as ABSENT. Evidence strength is separate from editorial decision
confidence. Conflicting producer evidence remains visible and is not resolved by latest-wins or
hidden producer priority.

v1 preparation supports already-aligned single-placement internal frame ranges only. Stale,
cross-placement, cross-clip or unresolved conflicting evidence fails closed rather than silently
rebasing or synthesizing meaning. Native Resolve time/FPS/source mapping is a separate next contract.

Detailed architecture: docs/OBSERVATION_EVIDENCE_CONTRACT.md.


## Native Time & Snapshot Mapping v1

Native/source/timeline frame coordinates remain separate typed domains and are mapped only through an
explicit snapshot-bound placement correspondence. Frame-rate metadata uses exact rational values and
is not itself mapping authority.

Mixed FPS is supported conservatively: explicit mappings are EXACT only when requested boundaries
land exactly on integer internal frames. Non-integral boundaries return NON_INTEGRAL and are never
rounded. The project-wide time primitive remains integer half-open FrameRange; sub-frame/rational
time is not introduced globally in v1.

Snapshot mismatch is STALE, and mappings do not silently rebase after human edits. EXACT temporal
mapping is not approval or Safety authority. Detailed contract:
`docs/NATIVE_TIME_SNAPSHOT_MAPPING.md`.


## Read-only Resolve Snapshot & Adapter Observation v1

Resolve remains the Source of Truth. The adapter produces immutable read-only snapshots and does not
invent native facts that Resolve does not expose.

Identity lifetime is explicit (persistent/session-local/snapshot-local/unknown), capability support
is separate from observed values, and capture consistency distinguishes CONSISTENT, UNSTABLE and
UNVERIFIED. Unknown/unsupported native state reduces automation rather than becoming a false default.

Snapshot completeness is not feature readiness. Each downstream feature evaluates an explicit
requirement profile, and readiness never implies Apply/Safety/Authority permission.

Detailed contract: `docs/READ_ONLY_RESOLVE_SNAPSHOT_CONTRACT.md`.


## Pause Edit Planning & Safety Lowering v1

PauseCandidate expresses editorial intent, not executable cut geometry. KEEP produces no-op planning,
REVIEW produces review-only planning, and destructive TIGHTEN/REMOVE requires a separate explicit
PauseCutGeometry bound to the same base target.

TIGHTEN v1 supports one contiguous removal range only. The geometry must exactly match the candidate
retained duration and is never clamped or inferred from duration alone. REMOVE also retains a separate
full-pause geometry artifact for provenance.

The planner consumes already-computed target/snapshot/dependency readiness and stops at
READY_FOR_PREFLIGHT. Planning readiness is not Safety PASS, approval or apply authority. Geometry
generation is deferred to OPEN-013 / a future Cut Geometry Resolution Contract.

Detailed contract: `docs/PAUSE_EDIT_PLANNING_CONTRACT.md`.


## Cut Geometry Resolution v1

TIGHTEN retained duration defines how much pause remains, not where the cut occurs. Exact cut
geometry is resolved from explicit typed constraints only.

The v1 vocabulary is limited to CUT_START_ANCHOR, CUT_END_ANCHOR, MUST_PRESERVE_RANGE and
ALLOWED_REMOVAL_RANGE. GeometryConfidence is producer-supplied descriptive metadata and is neither
derived nor used to rank alternatives.

The resolver preserves natural editorial ambiguity:

```text
0 distinct valid geometries -> UNRESOLVED
1 distinct valid geometry  -> RESOLVED
2+ distinct valid geometries -> REVIEW_REQUIRED
```

TASK-013 is a pure geometry-resolution foundation. Raw audio/VAD/STT/prosody/semantic geometry
producers, confidence calibration, alternative ranking, seam treatment and actual editing remain
outside v1.

Detailed contract: `docs/CUT_GEOMETRY_RESOLUTION_CONTRACT.md`.
