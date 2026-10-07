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


## Expected Diff & Temporal Displacement v1

Pause gap closure is represented as an explicit primary range removal plus an explicit concrete
displacement manifest. A ripple boolean or all-downstream instruction is not sufficient.

The compiler consumes a precomputed participant assessment and does not decide who participates.
Initial supported participants are pure translations with uniform integer delta equal to negative
removed duration. Within an explicit PreservationScope, any object not listed as changed is expected
unchanged.

ExpectedDiff completeness is separate from Safety acceptability: a fully described consequence may
be READY_FOR_PREFLIGHT even when Safety will reject it. Future postflight verification requires exact
Expected Diff = Actual Diff; unverified, missing, extra or one-frame-wrong changes do not count as a
match.

Detailed contract: `docs/EXPECTED_DIFF_TEMPORAL_DISPLACEMENT_CONTRACT.md`.


## Safety Preflight Integration v1

Safety validates a fully specified ExpectedDiff against current safety evidence and does not repair
or replan the edit. Preflight readiness is distinct from the Safety verdict: STALE, UNSUPPORTED and
INCOMPLETE never become PASS.

The Pause destructive v1 profile has 17 mandatory checks covering freshness, ExpectedDiff integrity,
protection, track locks, relationship/dependency coverage, retime, displacement preservation,
topology, transition/effect/keyframe editability and PreservationScope.

Unknown mandatory safety state always reduces autonomy. Transition/effect/keyframe structures that
are present may pass only with a valid typed PRESERVATION_PROVEN proof; present-without-proof requires
review, unknown evidence is incomplete, and explicit integrity violations reject.

Safety PASS remains separate from approval, execution and verified promotion.

Detailed contract: `docs/SAFETY_PREFLIGHT_INTEGRATION_CONTRACT.md`.


## Execution Transaction & Postflight Verification v1

Destructive execution is not committed when native commands merely return successfully. The product
commit point is after a fresh postflight observation proves ExpectedDiff == ActualDiff.

Transaction phase and terminal outcome are separate. Uncertain mutation responses use explicit
OUTCOME_UNKNOWN and may not be blindly retried. Rollback capability is never assumed and is separate
from automatic rollback policy; even rollback command success must be verified against the original
base state.

Any unrecovered partial mutation triggers a recovery-required lockdown that blocks further
destructive AI execution and promotion until a coherent authoritative state is explicitly
re-established.

Detailed contract: `docs/EXECUTION_TRANSACTION_POSTFLIGHT_CONTRACT.md`.


## Validated Execution IR & Resolve Executor Boundary v1

Pause-v1 execution uses only bounded logical REMOVE_RANGE and TRANSLATE_PLACEMENT operations. Every
ExpectedDiff effect must be realized exactly once, with no participant-expanding ripple opcode or
native side-effect expansion.

Destructive lowering requires execution-grade target identity, verified runtime capability, a verified
native effect model, verified post-read, and a verified reconciliation path. SNAPSHOT_LOCAL identity
is insufficient for destructive v1 targeting. Fragment-producing decompositions require explicit
verified rebinding.

Rollback capability remains a separate transaction-policy axis under ADR-027.

Detailed contract: `docs/VALIDATED_EXECUTION_IR_CONTRACT.md`.


## Native Capability Probe & Effect Model Evidence v1

Resolve-native destructive semantics become trusted only through isolated disposable probes with
verified fixture preconditions, independently observed before/after state, complete side-effect
scope, repeatability, and conflict-free exact-profile evidence.

A single successful call cannot create VERIFIED capability. Partial/unknown observation scope cannot
create VERIFIED. Conflicting qualifying evidence remains CONFLICTING and blocks destructive
eligibility rather than being resolved by recency or majority.

Concrete repetition counts and the final fixture/challenge matrix remain a separate versioned policy.

Detailed contract: `docs/NATIVE_CAPABILITY_PROBE_EVIDENCE_CONTRACT.md`.


## Capability Verification Policy & Challenge Matrix v1

Native destructive verification is automated engineering validation, not recurring editor work.
TRANSLATE_PLACEMENT requires 20 minimum positive runs (4 fixture classes × 5), REMOVE_RANGE requires
30 (6 × 5), and COMPOUND_RIPPLE requires 50 (10 × 5). Applicable challenge classes receive 3
additional independent clean runs each.

Qualifying evidence requires COMPLETE observation, zero semantic conflicts, zero unexpected side
effects, zero containment failures, zero ambiguous targets, VERIFIED post-read/reconciliation and
execution-grade identity. Capability models are bounded by an explicit ApplicabilityDomain.

Verified profile evidence is reused until stale and full probe suites are never repeated per ordinary
project/edit. The production editor is not asked to perform manual capability probing.

Detailed policy: `docs/CAPABILITY_VERIFICATION_POLICY.md`.


## Resolve Probe Harness & Fixture Lifecycle v1

Qualifying destructive native probes are isolated from production editing in dedicated disposable
probe projects. Each qualifying repetition starts from one fresh CLEAN_VERIFIED fixture instance,
permits at most one bounded invocation attempt, observes/seals evidence, and then discards the mutated
test state.

Dirty or quarantined fixtures are never repaired-and-reused for the same qualifying run. Undo is not
assumed as reset. Exploratory runs are distinct from qualifying runs, and containment failure or
project contamination stops further qualifying mutation in that generation.

Full probe suites are development/release/update validation workflows and never implicit ordinary
editing work.

Detailed contract: `docs/RESOLVE_PROBE_HARNESS_FIXTURE_LIFECYCLE.md`.

## Read-only Probe Adapter & Fixture Materialization v1

The first real Resolve probe integration proves observation and fixture reproducibility before destructive probing. Environment control, materialization, read-only observation and native invocation remain separate boundaries.

v1 uses a template-first canonical fixture package with content-hashed project template and canonical assets. Materialization is not self-certifying: only independent read-only canonical semantic MATCH can produce CLEAN_VERIFIED. Ambiguous role binding, missing evidence and unstable capture fail closed.

Integration order is Read-only Adapter -> Fixture Materializer -> Read Stability -> Native Mutation Probe.

Detailed contract: `docs/READ_ONLY_PROBE_ADAPTER_FIXTURE_MATERIALIZATION.md`.

## Documented Resolve Read Capability Tiers

OPEN-019 now has a documented candidate map for TASK-020, while exact runtime support remains
unverified until the installed Resolve/adapter profile is probed.

- Tier A: runtime/project/timeline, track topology/state, placement/media/source geometry,
  linked/enabled state, markers and subtitle enumeration.
- Tier B: partial diagnostics such as simple speed/fades, generic item properties, transition
  item surface, Fusion presence and color-node presence.
- Tier C: identity lifetime, stable Track identity, full transition/effect/keyframe semantics,
  full variable-retime curves and generic preservation-proof production.

The product does not convert documentation presence into runtime trust. Tier A must pass bounded
typed reads plus repeated stability before it can contribute to a qualifying ProbeSnapshot.

Detailed map: `docs/RESOLVE_READ_CAPABILITY_MAP.md`.


## TASK-020 Read Stability & Runtime Validation Policy v1

The first read-only Resolve integration uses 10 consecutive double-capture semantic stability pairs
per qualifying Tier A fixture. Any unexplained drift is retained and marks the affected read scope
SUPPORTED_UNSTABLE rather than being retried away.

Identity candidates require 3 timeline-switch round trips for a same-project switch-stability claim.
Project reopen requires 3 reopen cycles only when that lifetime is claimed, and Resolve restart is
required before cross-session PERSISTENT_VERIFIED identity can be claimed.

Basic TASK-020 completion does not require persistent identity across restart. Readable native IDs
remain observations until their claimed lifetime boundaries are separately proven.

Detailed policy: `docs/TASK_020_RUNTIME_VALIDATION_MATRIX.md`.


## Probe Fixture Catalog v1

Read-only/native capability verification uses deterministic synthetic canonical fixtures F0–F4,
not real editorial footage.

The catalog covers basic placement geometry, repeated-media disambiguation, track-state observation,
marker/subtitle timing and same-project identity switching. Timeline ranges are defined relative to
the observed Timeline.GetStartFrame() so the product does not assume native frame zero.

Real footage remains a separate evaluation asset for Pause/Dialogue quality, review/correction cost
and Net Editing Time Saved.

Detailed catalog: `docs/PROBE_FIXTURE_CATALOG.md`.


## Probe Runtime Control Plane v1

Probe qualification has an explicit control plane separate from ordinary editing.

Registration, environment verification and one-run arming are distinct. Every authorization is bound
to one disposable project generation, one clean fixture, one pre-snapshot and one typed invocation,
and is consumed after the final pre-invocation gate or invocation attempt.

Unexpected fixture-local mutation blocks additional qualifying probes until project-level
re-verification. Project-level contamination requires a new generation. Crash/bridge uncertainty
locks down new probe mutations rather than guessing that the environment remained clean.

No ordinary editing request implicitly arms this system.

Detailed contract: `docs/PROBE_RUNTIME_CONTROL_PLANE.md`.


## Canonical Fixture Asset Package v1

Probe fixtures use six deterministic synthetic canonical media assets. The v1 package uses 720p24
intra-frame DNxHR LB video and 48 kHz / 24-bit stereo Linear PCM where audio is present.

Asset identity is based on exact shipped SHA-256 bytes and semantic asset IDs, never filename.
Generator/toolchain metadata is provenance only. Ordinary editor workflows do not regenerate or
download these assets.

The binary bundle is versioned and checksum-locked separately from real editorial footage, which
remains dedicated to quality/workflow evaluation.

Detailed contract: `docs/CANONICAL_FIXTURE_ASSET_PACKAGE.md`.


## Canonical Asset Generator v1

Canonical probe media is generated from integer-defined synthetic video/audio signals under one
locked software toolchain. The generator validates stream structure, performs full decode checks,
generates the package twice from clean staging directories and requires byte-for-byte equality before
the bundle can be sealed.

FFmpeg/toolchain determinism is defense in depth; exact approved shipped SHA-256 bytes remain the
canonical identity. Generator success does not imply Resolve support.

Detailed contract: `docs/CANONICAL_ASSET_GENERATOR_CONTRACT.md`.


## Canonical Package Implementation Gate

The canonical-media architecture becomes executable through TASK-022. The generator/package task
produces the first real six-asset bundle, hashes and package_digest before full canonical F0–F4
runtime qualification and real fixture materialization.

Recommended dependency:

`TASK-019 → TASK-022 → TASK-020 full runtime qualification → TASK-021`.

TASK numbering is repository chronology and does not override this dependency graph.


## TASK-020 Runtime Execution & Evidence Runbook

Read-only Resolve qualification is executed through a fixed evidence protocol rather than manual
spot-checking. One run binds one exact RuntimeProfile/project generation/canonical package.

Each qualifying fixture context is captured in 10 consecutive A/B full-snapshot pairs, failed pairs
remain evidence, and F4 adds three A→B→A timeline-switch round trips. Raw returns and semantic
normalized observations are retained separately, and capability support remains distinct from fixture
correctness.

TASK-020 never repairs a mismatched fixture or retries until green.

Detailed runbook: `docs/TASK_020_RUNTIME_EXECUTION_EVIDENCE_RUNBOOK.md`.


## Native Probe Environment Authenticity v1

The first destructive native probes require a dedicated probe-only Project Library and a fresh
session-bound attestation. A project name, sentinel or UUID-shaped value cannot authenticate the
current Resolve project.

Environment authenticity combines external registration, canonical materialization provenance,
read-stable native Project Library/project/timeline observations, canonical semantic baseline MATCH
and an independent re-read. Immediately before one-run arming, the exact current target must be
re-proven.

Persistent cross-restart identity is not required for the first same-session destructive probes; a
restart/reopen beyond the proven boundary makes the attestation stale.

Detailed contract: `docs/NATIVE_PROBE_ENVIRONMENT_AUTHENTICITY.md`.
