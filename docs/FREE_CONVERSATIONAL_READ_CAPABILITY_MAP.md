# Free Conversational Editing Read Capability Map — F1 v1

Status: prepared map / F1 native capture NOT EXECUTED. No execution readiness is asserted.
Basis: ADR-041/042/043, TASK_023_F1_READ_CAPABILITY_MAP.md.

## Evidence provenance and interpretation

P0 = operator-provided F0 Console summary in the task request, not raw Console transcript captured by
this implementation. Product/version, live root/context and two timeline endpoints were reported.
P1 = installed developer candidate surface: DaVinciResolveScript.pyi SHA-256
b91b53b86a946e1902789ea898eedf00cb7dd6107aba6f1276ca77fe508816ea, inspected before implementation.
Python annotations describe candidates; they do not establish Lua return shape or availability.
P2 = future one-shot FREE_F1 Console output, absent today. Retain complete BOOT-through-END text,
operator session/context, exact probe commit/hash and runtime version with that output. Capture-local
paths are locators only. No inferred freshness/state token or persistent identity is created.

Every F1 row below currently has capability **UNKNOWN** and semantic mapping **NOT_ESTABLISHED**.
Expected forms are documented candidates, not observations. AVAILABLE_TYPED will mean one-shot raw
shape only. AVAILABLE_AMBIGUOUS retains ambiguous objects/coordinates/shape. UNAVAILABLE needs a direct
missing-method observation. ERROR and NIL are outcomes, not capability synonyms or proof of absence.

## First probe candidates

| Domain / conversational fact | Native candidate | Raw returned form today (candidate form) | Provenance | Coordinate / identity basis | Semantic mapping | Capability | Missing fact impact / reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A runtime interpretation | Resolve.GetProductName | NOT OBSERVED in F1 (string); P0 reports DaVinci Resolve | P0/P1, P2 missing | Not edition proof | NOT_ESTABLISHED | UNKNOWN | Runtime provenance incomplete |
| A runtime version | Resolve.GetVersionString | NOT OBSERVED in F1 (string); P0 reports 21.1.1.10 | P0/P1, P2 missing | Exact session/profile not yet bound | NOT_ESTABLISHED | UNKNOWN | Cannot reuse evidence across builds |
| A project access | Resolve.GetProjectManager | NOT OBSERVED in F1 (handle); P0 available | P0/P1, P2 missing | Opaque observation, not authority | NOT_ESTABLISHED | UNKNOWN | Blocks project traversal if absent |
| A/K current project | ProjectManager.GetCurrentProject | NOT OBSERVED in F1 (handle); P0 available | P0/P1, P2 missing | Current context only, not selected editing target | NOT_ESTABLISHED | UNKNOWN | Cannot bind request context |
| A/L project identity | Project.GetUniqueId | NOT OBSERVED (candidate string) | P1, P2 missing | Lifetime/cross-session correspondence unknown | NOT_ESTABLISHED | UNKNOWN | Freshness/target base unproven |
| B/K current timeline | Project.GetCurrentTimeline | NOT OBSERVED in F1 (handle); P0 available after operator opened Timeline 1 | P0/P1, P2 missing | Active is not Working Authority | NOT_ESTABLISHED | UNKNOWN | Cannot bind timeline-scoped request |
| B timeline identity | Timeline.GetUniqueId | NOT OBSERVED in F1 (string); P0 says call succeeded, value not supplied | P0/P1, P2 missing | No persistent identity claim | NOT_ESTABLISHED | UNKNOWN | Exact timeline binding missing |
| B timeline name | Timeline.GetName | NOT OBSERVED in F1 (string); P0 reports Timeline 1 | P0/P1, P2 missing | Descriptive only | NOT_ESTABLISHED | UNKNOWN | Name alone cannot resolve target |
| B timeline extent | Timeline.GetStartFrame / GetEndFrame | NOT OBSERVED in F1 (numbers); P0 reports 108000 / 108087 | P0/P1, P2 missing | Endpoint convention/rate unknown; no offset/rounding | NOT_ESTABLISHED | UNKNOWN | Cannot produce internal FrameRange yet |
| C track/type existence | Timeline.GetTrackCount(video/audio/subtitle) | NOT OBSERVED (candidate numeric counts) | P1, P2 missing | Type is explicit argument; index not persistent ID | NOT_ESTABLISHED | UNKNOWN | Layer inventory incomplete |
| D/H placement enumeration/membership | Timeline.GetItemListInTrack(type,index) | NOT OBSERVED (candidate Lua table of item handles) | P1, P2 missing | Collection key not chronological order/identity | NOT_ESTABLISHED | UNKNOWN | Cannot resolve second clip or complete overlap set |
| E placement identity | TimelineItem.GetUniqueId | NOT OBSERVED (candidate string) | P1, P2 missing | Separate from media ID; lifetime unknown | NOT_ESTABLISHED | UNKNOWN | Repeated-media placement targeting blocked |
| E placement label | TimelineItem.GetName | NOT OBSERVED (candidate string) | P1, P2 missing | No filename identity or semantic role inference | NOT_ESTABLISHED | UNKNOWN | Descriptive explanation only |
| E/H placement position/duration | TimelineItem.GetStart(false) / GetEnd(false) / GetDuration(false) | NOT OBSERVED (stub annotates float; Lua shape unproven) | P1, P2 missing | No numeric coercion, endpoint repair or source mapping | NOT_ESTABLISHED | UNKNOWN | Overlap/gap/target arithmetic blocked |
| F source binding | TimelineItem.GetMediaPoolItem | NOT OBSERVED (candidate handle or nil) | P1, P2 missing | Observed link only, no filename match | NOT_ESTABLISHED | UNKNOWN | Source trace unavailable without bound handle |
| F source identity | MediaPoolItem.GetUniqueId / GetMediaId | NOT OBSERVED (candidate strings) | P1, P2 missing | Source identity is not placement identity; lifetime unknown | NOT_ESTABLISHED | UNKNOWN | Cannot confirm same-source placement correspondence |

## Deferred domains (not called by the first probe)

| Domain | Intended fact / native candidate | Raw form / provenance | Basis / semantic mapping | Capability | Absence impact |
| --- | --- | --- | --- | --- | --- |
| A library | GetCurrentDatabase (F0 only) | P0 table available; exact entries NOT OBSERVED | Native descriptor not registration proof; NOT_ESTABLISHED | UNKNOWN | Environment authenticity unresolved |
| B settings/FPS | Timeline.GetSetting candidate; spelling/shape need installed/runtime review | NOT OBSERVED / no P2 | No rate assumption; NOT_ESTABLISHED | UNKNOWN | Coordinate interpretation blocked |
| F source spans | GetSourceStartFrame / GetSourceEndFrame candidates | NOT OBSERVED / P1 only | End convention and correspondence unknown; NOT_ESTABLISHED | UNKNOWN | Source range preservation proof missing |
| G A/V facts | GetLinkedItems candidate; no call in first probe | NOT OBSERVED | A link is not propagation policy; NOT_ESTABLISHED | UNKNOWN | Picture-preserving dialogue changes blocked |
| H semantic overlap | No direct B-roll role read asserted | NOT OBSERVED | Only proven coordinate facts can later support overlap derivation; NOT_ESTABLISHED | UNKNOWN | Cannot promise to avoid B-roll |
| I retime/speed | Exact reliable speed/retime read remains an open discovery question | NOT OBSERVED | No unknown-to-1x inference; NOT_ESTABLISHED | UNKNOWN | Exclude-retimed request blocked |
| J lock/enabled/protection | GetIsTrackLocked / GetIsTrackEnabled / GetClipEnabled candidates, deferred | NOT OBSERVED | Native lock is not complete protection context; NOT_ESTABLISHED | UNKNOWN | Destructive readiness not established |
| K selection | No selected-item API asserted; current timeline only | NOT OBSERVED | Current/selected/authoritative are distinct; NOT_ESTABLISHED | UNKNOWN | The phrase this clip remains ambiguous |
| L freshness/identity lifetime | No state-token or atomic capture API asserted | NOT OBSERVED | One-shot read is not currentness/stability proof; NOT_ESTABLISHED | UNKNOWN | No ready-for-apply or native identity promotion |

## Conversational readiness

These are reasoning/read readiness states only. NONE implies mutation, Safety PASS or approval.
All statuses below describe present evidence, not what a future probe might return.

| Intent | Required semantic facts | Reads intended to contribute / current Free evidence | Missing facts | Status |
| --- | --- | --- | --- | --- |
| 두 번째 클립 앞의 침묵을 줄여줘 | Explicit track/scope, ordered concrete placements, actual pause evidence, safe geometry, dependency/protection facts | Future item lists/IDs/ranges; currently F0 context only | Second-clip scope, proven coordinates, silence vs gap, pause constraints, safety evidence | BLOCKED_UNKNOWN |
| B-roll과 겹치는 곳은 건드리지 마 | Explicit B-roll role binding, complete multi-track placements, overlap geometry, protection scope | Future track/item inventory; no B-roll native fact observed | Role assignment, complete inventory, aligned coordinates, protection context | BLOCKED_UNKNOWN |
| 영상은 그대로 두고 대사 간격만 줄여줘 | Explicit dialogue targets, video preservation set, source ranges, A/V relationships, timing/dependency facts | Future media/item binding; no relationship evidence yet | Dialogue identity, source spans, sync meaning, geometry, picture preservation proof | BLOCKED_UNKNOWN |
| 속도 변경된 클립은 제외해 | Reliable per-placement retime/speed observation and complete target scope | No retime read in first probe | Retime vocabulary/mapping and actual per-item observations | BLOCKED_UNKNOWN |
| 이 클립이 어느 소스에서 온 건지 확인해 | Unambiguous concrete placement and directly observed media binding/IDs | Future GetMediaPoolItem and source IDs; F0 has no placement evidence | This-clip target, actual MPI link/IDs, lifetime limits | BLOCKED_UNKNOWN |

Understanding/explaining these requests remains available as shared conversational behavior; the blocked
state concerns evidence needed to reason concretely. No edition-specific command syntax is introduced.
No current row is BLOCKED_UNSUPPORTED because inability has not been directly demonstrated. READY_TO_REASON
requires sufficient verified semantic facts; PARTIAL requires useful observed facts for that exact intent.

## Open questions and operator handoff

1. Which proven in-process entry point can execute the reviewed file as one shot? Menu remains
   INCONCLUSIVE. No workaround is implemented; an operator must preserve the execution path as evidence.
2. What actual Lua types/collection keys/handles do these getters return on this exact runtime?
3. What are endpoint, fractional coordinate and source/timeline conventions? No correspondence inferred.
4. What identity lifetime, completeness and freshness can later evidence establish?
5. Which direct retime/relationship/lock/selection reads support the deferred intent facts?
6. Where will explicit B-roll/dialogue/target bindings come from under shared contracts?

On approved manual execution in the proven context: preserve the entire FREE_F1 BOOT/OBS/END transcript,
including NIL/ERROR/UNKNOWN, without deleting inconvenient reads or retrying until green. Missing END or
serialization errors mean incomplete capture. Opaque handle markers are not raw native identities;
retain their type and separate observed IDs. No automatic normalization, transport or file sink is added.
