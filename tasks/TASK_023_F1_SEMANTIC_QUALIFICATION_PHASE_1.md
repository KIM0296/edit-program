# TASK-023 F1 Semantic Qualification Phase 1

Status: design prepared for Chat Gate; runtime execution NOT AUTHORIZED in this task.
Base: 95cd83c5c45efb7a3d6c9b506b9c23f76f9324d7; PR #50; Free feasibility branch.
ADR-041/042/043 and mixed-key probe correction APPROVED per user. Shared contracts are unchanged.
This is a qualification specification, not an adapter, mapping implementation or new shared identity model.

## Existing contract audit (read-only)

| Free native fact | Existing shared requirement / authoritative source | Missing evidence / disposition |
| --- | --- | --- |
| Timeline 108000..108087; item 108000..108087, duration 87 | ADR-008 in DECISIONS.md; src/davinci_ai_editor/domain.py FrameRange: nonempty nonnegative integer half-open [start, end) | Native endpoint convention and origin correspondence NOT_ESTABLISHED; internal construction BLOCKED_UNKNOWN |
| Item and timeline starts coincide in one fixture | ADR-021, docs/NATIVE_TIME_SNAPSHOT_MAPPING.md: zero-based internal coordinate domains; native timecode/start offsets belong at adapter boundary | Native absolute/base-relative origin, rate and explicit translation proof missing; no subtract-start shortcut |
| false/true start/end/duration equal here | ADR-021 exact rational rate, both boundaries exact; NON_INTEGRAL never rounded | Fractional behavior and representability unqualified; equality is fixture-specific |
| Placement ID strings, same source ID across two placements | ADR-012 fake lineage is not production identity; docs/EDITING_IR.md StableTarget includes timeline/version/track/placement/media/source and timeline spans | Unique production correspondence, native track binding and source spans missing; OPEN-001/OPEN-006 remain OPEN |
| Immediate video ID/range reread matches | ADR-022, docs/READ_ONLY_RESOLVE_SNAPSHOT_CONTRACT.md: identity scope is categorical, consistency separate from completeness/readiness | I0 video fields only; no automatic SESSION_LOCAL_VERIFIED or PERSISTENT_VERIFIED; broader lifetime UNKNOWN |
| No edit reported between two reads | ADR-021 snapshot-bound timeline/version/state_token; ADR-022 trustworthy token may be absent | Currentness fence, product version binding and trustworthy mapping-state identity missing; BLOCKED_UNKNOWN, not CONSISTENT |
| Human may change Resolve after capture | ADR-015 docs/CANDIDATE_AUTHORITY.md; ADR-016 docs/PARALLEL_EDITING.md: Human Edit Wins, stale on source identity/version mismatch | Any known mismatch is STALE; no silent rebase, scope exemption or numeric version update |
| Snapshot observations / active timeline | ADR-022 Resolve-is-Source-of-Truth; ADR-015 active timeline is not Working Authority | Native observations cannot become authority or approval; missing facts stay UNKNOWN |
| Free raw observations vs Studio | ADR-041/042/043: same Domain/IR/ExpectedDiff/Safety/Authority/Postflight | Qualify evidence against existing semantics; never weaken Core or remove verified Studio capabilities |

No conflicts requiring a shared-contract change identified. The gap is evidence, not an alternative
Free coordinate/identity model. OPEN-001/006/008/012 retain native correspondence/currentness questions.
Resolve remains Source of Truth; historical evidence never overrides newer human work.

## Current P3 evidence (operator summary, not probe output)

Runtime context reported earlier: 21.1.1.10; project PF_FREE_CANARY_v1; Timeline 1.
Exact project/timeline ID values and complete capture/session provenance are not supplied here.
Timeline start = 108000; end = 108087.
Video placement ID = f961cbd6-6703-4df5-a4d3-d30aa439f47d.

| Read | false argument | true argument | Meaning established |
| --- | --- | --- | --- |
| GetStart | 108000 | 108000 | Equality in this fixture only |
| GetEnd | 108087 | 108087 | Equality in this fixture only |
| GetDuration | 87 | 87 | Equality in this fixture only |

Two consecutive no-edit reads returned the same video ID/start/end/duration. This is same-session
immediate reread stability observed for those fields only. No half-open parity, inclusive/exclusive
endpoint convention, subframePrecision irrelevance, cross-session stability or stable handle identity
is established. Reviewed probe remains NOT EXECUTED; no FREE_F1 output is synthesized from P3.

## Qualification record design

One future observation must preserve method and exact arguments, raw value/type (including nil/error),
provenance (P3 vs probe output), fixture/oracle reference, runtime build, session/capture order, observed
project/timeline/placement/source IDs, capture context and snapshot binding or explicit absence.
Record these as separate fields: coordinate basis, endpoint convention, rate/rate evidence,
source-vs-timeline coordinate domain and exact correspondence status. Unknowns have no default value.
Opaque handles may be retained as typed observations, never address/pointer equality identity proofs.
The specimen schema below is design metadata only. It is not a production evidence validator.

No inclusive/exclusive endpoint convention is assumed for ANY native getter. Timeline and item endpoint
conventions must be qualified independently. GetDuration need not establish the endpoint definition.
Raw native numbers are never cast, rounded or used to construct FrameRange to test a hypothesis.

Coordinate status meanings (orthogonal to capability, identity and freshness):
- NOT_ESTABLISHED: raw observations exist without a demonstrated correspondence.
- CORRESPONDENCE_CANDIDATE: an explicitly stated hypothesis fits available controlled observations;
  not permission to construct ranges, infer other fixtures, or lower a target.
- VERIFIED_EXACT: only after the bounded controlled matrix, independent oracle, exact rates/basis,
  both integer boundaries and current binding are evidenced and reviewed for a declared scope.
- CONFLICT: observations contradict the proposed correspondence; retain all competing evidence.
- UNKNOWN: required observation/interpretation unavailable or unreadable; preserve failure reason.
Missing conditional cases limit the declared scope; they are never counted as verified coverage.
VERIFIED_EXACT here is not TASK-010 MappingStatus.EXACT, Safety PASS or an identity promotion.
Even VERIFIED_EXACT is necessary but insufficient for downstream current mapping/target readiness.
This task constructs no FrameRange, StableTarget or mapping at any status.

## Controlled fixture matrix (design only)

Every case requires an independently documented oracle: approved fixture definition/version, source
identity, known intended frame count/placement layout, rates and verification provenance. A return from
the getter under test cannot serve as its own ground truth. Name, filename, index and expected result
alone are not correspondence evidence. Bind concrete placements explicitly; retain unexpected objects.
An existing approved canonical asset alone is not proof of a correctly materialized native fixture.
No qualifying fixture availability is asserted here. If unavailable, record NOT_OBSERVED and HOLD.
No fixture is created, repaired, moved, trimmed, switched or reopened by this task.

| Case | Required independently prepared fixture | Planned observations and discriminating comparison | Missing/blocked handling |
| --- | --- | --- | --- |
| C01 | Known single clip length; include a one-frame clip and a longer clip in distinct controlled captures | All five getters; compare reported duration and endpoint hypotheses against independently known counts, qualify timeline and item ends separately | One 87-frame observation alone insufficient |
| C02 | Two adjacent clips with independently verified no-gap layout | Preserve both placement IDs and all getter values; test each candidate endpoint convention against adjacency and known lengths | Do not assume end A equals start B implies exclusive endpoints |
| C03 | Two clips with exactly one independently verified timeline-frame gap | Compare C02 and C03 observations at same rate/base; reject hypotheses that cannot distinguish the one-frame gap exactly | No tolerance, default gap inference or repair |
| C04 | One-frame temporal overlap, only if naturally permitted in an externally prepared fixture; state track layout explicitly | Compare both spans and timeline extent; distinguish overlap evidence from transition semantics | If unavailable, NOT_OBSERVED and overlap correspondence remains UNKNOWN; no forced overlap or transition creation |
| C05 | Independently known trimmed placement and source span | Compare item duration/endpoints to known visible length; preserve source evidence separately | Offsets=0 never proves untrimmed/full source; source correspondence blocked without separate proof |
| C06 | Equivalent known layout in two externally prepared timelines with different documented start timecode/base | Read timeline start/end and all item values in each; compare candidate absolute vs relative bases against oracle and exact rate/label evidence | No automatic subtraction of 108000 or timecode parsing; unmatched bases are not rebased |
| C07 | false/true observations on integral fixtures and, if naturally supported and externally available, a known fractional audio placement | GetStart/GetEnd/GetDuration with both arguments; retain exact raw numbers and argument provenance | Integral equality does not generalize; fractional/unavailable evidence stays explicit, never round to FrameRange |

All cases require source and timeline rate evidence separately as exact rational values with provenance.
FPS ratio alone cannot establish a mapping. Display decimal rate or unqualified timecode label is not
exact rate proof. Same raw numbers in SOURCE_FRAME and TIMELINE_FRAME are not interchangeable.
No round/floor/ceil/clamp, tolerance, endpoint plus/minus-one repair, nearest coordinate, range shift or
silent rebase. A candidate interpretation may be evaluated against independent endpoints; it is never
applied as an adjustment merely to make a fixture pass. Contradictions remain CONFLICT, not averaged away.

## Identity/freshness evidence levels (measurement only)

Compare each directly observed field separately: project ID, timeline ID, placement ID, source
MediaPoolItem ID, native ranges and context. Record before/after provenance and any missing/error fields.
No matching by pointer/address, name, source-only ID, position or first-match fallback.
A duplicate or unbound target is AMBIGUOUS, not the closest-looking item.

| Level | Boundary to observe in a separately authorized future protocol | Current evidence |
| --- | --- | --- |
| I0 | Immediate reread in same context, no edit | Video placement ID/start/end/duration STABLE_OBSERVED_AT_LEVEL per P3; other comparison fields NOT_OBSERVED |
| I1 | Later reread in same session without edit; record actual elapsed time and intervening activity | NOT_OBSERVED; no arbitrary elapsed-time stability threshold |
| I2 | Switch timeline and return; bind A-before/B/A-after separately | NOT_OBSERVED; not executed/authorized by this design task |
| I3 | Close/reopen project; document boundary and independently bound project | NOT_OBSERVED; no invocation here |
| I4 | Restart Resolve and reopen project; document new session/build/context | NOT_OBSERVED; no invocation here |

Per-field outcomes: STABLE_OBSERVED_AT_LEVEL = directly comparable values match at that level;
CHANGED = directly comparable values differ; NOT_OBSERVED = missing comparison;
AMBIGUOUS = correspondence/shape/context cannot be established; ERROR = observed failed read.
NOT_OBSERVED is not STABLE_OBSERVED_AT_LEVEL. Do not aggregate partial I0 into an all-field pass.
A changed range does not automatically mean changed object identity, and a stable ID does not mean
unchanged editable state. No level automatically implies any other level or shared IdentityScope.
Even I4 equality for selected fields is not blanket PERSISTENT_VERIFIED without existing contract proof.

Freshness is independent: known snapshot/base mismatch -> STALE. Missing currentness -> BLOCKED_UNKNOWN.
Same reread values are not an atomic capture fence or trustworthy state_token. Do not synthesize tokens,
versions, no-edit proof or native guarantees. Record unknown consistency as UNVERIFIED under ADR-022.
If human activity/drift is reported, preserve it and block currentness; do not overwrite historical
records, retry until green or silently refresh a candidate. No native currentness producer implemented.

## Proposed minimal probe review (not implemented)

No native calls added. Existing probe is unchanged; execution still requires a separate Chat Gate.
For later review, the only argument-extension proposal is to observe true as well as false for the
three already allowlisted item methods below. This proposal alone cannot establish rates/freshness.

| Proposed read change | Why / shared requirement | Installed surface evidence | Candidate raw shape / failure meaning |
| --- | --- | --- | --- |
| GetStart(true) alongside existing false | C07, ADR-021 integer representability | Installed pyi line 2393, subframePrecision=False, return float | Lua number candidate, not guaranteed; nil/missing/error remain distinct; no cast |
| GetEnd(true) alongside existing false | C07, both boundaries exact | Installed pyi line 2396, same parameter | Same conservative shape/failure handling |
| GetDuration(true) alongside existing false | Compare precision effects without endpoint inference | Installed pyi line 2411, same parameter | Same; equality in one fixture is not global irrelevance |

P1 stub SHA-256 b91b53b86a946e1902789ea898eedf00cb7dd6107aba6f1276ca77fe508816ea.
Stub annotations are candidate documentation, not runtime support. GetStartFrame/GetEndFrame appear at
2192/2195 as int candidates; their descriptions do not resolve endpoints. No broad settings read added.
A future extension must also label arguments in its output without conflating false/true; output change
requires Chat review before implementation. Rate/base/currentness evidence remains UNKNOWN until a
separately reviewed producer/read proposal establishes exact method, key, raw shape and failure semantics.
No GetSetting/GetStartTimecode or new read is authorized by listing an evidence need.

## Machine-checkable specification constraints

These fields constrain this design document only; no native semantic validator or identity engine exists.

```json
{
  "coordinate_statuses": ["NOT_ESTABLISHED", "CORRESPONDENCE_CANDIDATE", "VERIFIED_EXACT", "CONFLICT", "UNKNOWN"],
  "native_endpoint_default": "NOT_ESTABLISHED",
  "native_basis_default": "UNKNOWN",
  "current_coordinate_status": "NOT_ESTABLISHED",
  "frame_range_gate": {
    "necessary_status": "VERIFIED_EXACT",
    "also_required": ["current_snapshot_binding", "placement_correspondence", "exact_integer_boundaries", "qualified_basis_and_endpoints", "exact_rate_evidence"]
  },
  "frame_range_construction_in_this_task": false,
  "forbidden_repairs": ["round", "floor", "ceil", "clamp", "tolerance", "shift", "silent_rebase"],
  "fixture_cases": ["C01", "C02", "C03", "C04", "C05", "C06", "C07"],
  "fixture_creation_authorized": false,
  "observation_fields": ["raw_value", "raw_type", "coordinate_basis", "endpoint_convention", "rate_evidence", "coordinate_domain", "correspondence_status", "provenance", "method_arguments", "fixture_oracle_ref", "snapshot_binding"],
  "identity_levels": ["I0", "I1", "I2", "I3", "I4"],
  "identity_outcomes": ["STABLE_OBSERVED_AT_LEVEL", "CHANGED", "NOT_OBSERVED", "AMBIGUOUS", "ERROR"],
  "cross_level_inference": false,
  "automatic_identity_scope_promotion": false,
  "handle_equality_is_identity_proof": false,
  "current_levels": {"I0": "PARTIAL_VIDEO_FIELDS_ONLY", "I1": "NOT_OBSERVED", "I2": "NOT_OBSERVED", "I3": "NOT_OBSERVED", "I4": "NOT_OBSERVED"},
  "freshness_rules": {"snapshot_mismatch": "STALE", "missing_currentness": "BLOCKED_UNKNOWN", "equal_reread_implies_current": false, "state_token_synthesis": false, "human_edit_priority": true},
  "shared_contract_changes": [],
  "edition_specific_semantics": false,
  "runtime_execution_authorized": false,
  "native_probe_changes": []
}
```

## Validation and stop

Deterministic static tests check only this spec's vocabulary, fixture coverage, required gates, evidence
levels and prohibited inference. They do not execute Lua, build FrameRange or qualify native semantics.
Do not modify existing shared semantic tests. No mutation, IPC/listener, persistence, UI automation,
parity runner, Studio checkpoint change or distribution/installer/macOS packaging work.
Open evidence needs are the independent fixture oracles/availability, rate/base/endpoint proof,
production correspondence and currentness producer. No open contract is resolved by this document.
Stop for Chat Gate after reporting; no runtime qualification or broader F1 reads in this task.
