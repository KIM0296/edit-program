# Free Conversational Editing Read Capability Map — F1 v1

Status: F1 runtime qualification IN PROGRESS. P3 manual observations recorded; reviewed P2 probe NOT EXECUTED. No execution readiness is asserted.
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

P3 = operator manual F1 Console observation, supplied as a summary in the reconciliation request.
P3 is separate from P0 and P2. The reviewed resolve_free_f1.lua has NOT run. No FREE_F1|OBS
transcript is synthesized. Complete Console commands, Lua numeric subtype, capture timestamp and
complete raw transcript were not supplied. Values below are preserved as reported, not re-measured.

AVAILABLE_TYPED means reported raw shape only, not qualified identity/coordinate semantics.
AVAILABLE_AMBIGUOUS preserves objects, collections and coordinate ambiguity. Unobserved candidates
remain UNKNOWN. UNAVAILABLE requires direct evidence; none was supplied. NIL and ERROR remain distinct
outcomes, not absence inferred from missing observations. Semantic mapping remains NOT_ESTABLISHED.

## P3 manual observation record

| Observation | Video track 1 / placement | Audio track 1 / placement | Classification / limit |
| --- | --- | --- | --- |
| GetTrackCount | 1 | 1 | AVAILABLE_TYPED, reported integer counts only |
| GetItemListInTrack | one item returned | one item returned | AVAILABLE_AMBIGUOUS; no ordering/completeness guarantee beyond this capture |
| Placement name | 0916.mp4 | 0916.mp4 | AVAILABLE_TYPED, descriptive string only |
| Placement GetUniqueId | f961cbd6-6703-4df5-a4d3-d30aa439f47d | bb080cbd-8c1f-4bc3-9049-036c64513643 | AVAILABLE_TYPED, raw strings; lifetime unqualified |
| Placement start | 108000 | 108000 | AVAILABLE_AMBIGUOUS |
| Placement end | 108087 | 108087 | AVAILABLE_AMBIGUOUS |
| Placement duration | 87 | 87 | AVAILABLE_AMBIGUOUS |
| GetMediaPoolItem | succeeded | succeeded | AVAILABLE_AMBIGUOUS native handles |
| Source GetUniqueId | 0939efdf-05b9-41bc-8091-6b7fd41075d3 | 0939efdf-05b9-41bc-8091-6b7fd41075d3 | AVAILABLE_TYPED, raw strings only |
| Track name | Video 1 | Audio 1 | AVAILABLE_TYPED, descriptive strings only |
| Track enabled | true | true | AVAILABLE_TYPED native booleans; not complete Safety evidence |
| Track locked | false | false | AVAILABLE_TYPED native booleans; not complete Safety evidence |
| Left offset | 0 | 0 | AVAILABLE_AMBIGUOUS |
| Right offset | 0 | 0 | AVAILABLE_AMBIGUOUS |

Two distinct placements were observed to reference the same source native ID. This does NOT establish
an explicit A/V link, J/L-cut relationship, propagation policy or stable identity lifetime. Matching
names do not establish identity. Zero offsets do NOT establish untrimmed source, full source coverage
or source coordinate correspondence. No internal FrameRange or temporal mapping is derived.
Exact manual invocation spellings/arguments for track state, names and offsets were not supplied;
method candidates below must not be mistaken for the manual command transcript.

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
| C track/type existence | Timeline.GetTrackCount(video/audio/subtitle) | P3 video=1, audio=1; subtitle NOT OBSERVED | P3; P2 missing | Reported integer counts; index not persistent ID | NOT_ESTABLISHED | AVAILABLE_TYPED for video/audio; UNKNOWN for subtitle | Complete layer inventory unqualified |
| D/H placement enumeration/membership | Timeline.GetItemListInTrack(type,index) | P3 one item in each video/audio track 1 | P3; P2 missing | No collection ordering or completeness guarantee | NOT_ESTABLISHED | AVAILABLE_AMBIGUOUS | Cannot resolve second clip or complete overlap set |
| E placement identity | TimelineItem.GetUniqueId | P3 two distinct strings, recorded above | P3; P2 missing | Separate from source ID; lifetime unknown | NOT_ESTABLISHED | AVAILABLE_TYPED | Raw shape only; current targeting unproven |
| E placement label | TimelineItem.GetName | P3 both 0916.mp4 | P3; P2 missing | No filename identity or role inference | NOT_ESTABLISHED | AVAILABLE_TYPED | Descriptive only |
| E/H placement position/duration | TimelineItem.GetStart / GetEnd / GetDuration; manual arguments not supplied | P3 both 108000 / 108087 / 87 | P3; P2 missing | No coercion, endpoint repair or source mapping | NOT_ESTABLISHED | AVAILABLE_AMBIGUOUS | Overlap/gap arithmetic blocked |
| F source binding | TimelineItem.GetMediaPoolItem | P3 succeeded for both placements | P3; P2 missing | Native handle, no filename matching | NOT_ESTABLISHED | AVAILABLE_AMBIGUOUS | Only reported capture binding |
| F source identity | MediaPoolItem.GetUniqueId; GetMediaId separately unobserved | P3 same source GetUniqueId string, recorded above | P3; P2 missing | Source ID is not placement ID; lifetime unknown | NOT_ESTABLISHED | AVAILABLE_TYPED for GetUniqueId; UNKNOWN for GetMediaId | This-clip targeting/currentness unproven |

## Domains outside the reviewed first probe (P3 observations distinguished)

| Domain | Intended fact / native candidate | Raw form / provenance | Basis / semantic mapping | Capability | Absence impact |
| --- | --- | --- | --- | --- | --- |
| A library | GetCurrentDatabase (F0 only) | P0 table available; exact entries NOT OBSERVED | Native descriptor not registration proof; NOT_ESTABLISHED | UNKNOWN | Environment authenticity unresolved |
| B settings/FPS | Timeline.GetSetting candidate; spelling/shape need installed/runtime review | NOT OBSERVED / no P2 | No rate assumption; NOT_ESTABLISHED | UNKNOWN | Coordinate interpretation blocked |
| F source spans | GetSourceStartFrame / GetSourceEndFrame candidates | NOT OBSERVED / P1 only | End convention and correspondence unknown; NOT_ESTABLISHED | UNKNOWN | Source range preservation proof missing |
| G A/V facts | GetLinkedItems candidate; no call in first probe | NOT OBSERVED | A link is not propagation policy; NOT_ESTABLISHED | UNKNOWN | Picture-preserving dialogue changes blocked |
| H semantic overlap | No direct B-roll role read asserted | NOT OBSERVED | Only proven coordinate facts can later support overlap derivation; NOT_ESTABLISHED | UNKNOWN | Cannot promise to avoid B-roll |
| I retime/speed | Exact reliable speed/retime read remains an open discovery question | NOT OBSERVED | No unknown-to-1x inference; NOT_ESTABLISHED | UNKNOWN | Exclude-retimed request blocked |
| J lock/enabled/protection | GetIsTrackLocked / GetIsTrackEnabled candidates; not in reviewed probe | P3 both tracks enabled=true, locked=false; exact commands not supplied | Native booleans, not complete protection context; NOT_ESTABLISHED | AVAILABLE_TYPED raw shape only; GetClipEnabled UNKNOWN | Destructive readiness not established |
| K selection | No selected-item API asserted; current timeline only | NOT OBSERVED | Current/selected/authoritative are distinct; NOT_ESTABLISHED | UNKNOWN | The phrase this clip remains ambiguous |
| L freshness/identity lifetime | No state-token or atomic capture API asserted | NOT OBSERVED | One-shot read is not currentness/stability proof; NOT_ESTABLISHED | UNKNOWN | No ready-for-apply or native identity promotion |


### Additional P3 collection and immediate reread findings

Operator manual GetItemListInTrack observations on Resolve 21.1.1 Lua:

| Collection | Key type | Key | Reported value |
| --- | --- | --- | --- |
| video track 1 | string | __flags | 4194304 |
| video track 1 | number | 1 | TimelineItem handle |
| audio track 1 | string | __flags | 4194304 |
| audio track 1 | number | 1 | TimelineItem handle |

This is P3 prose evidence, not FREE_F1 output. __flags meaning is UNKNOWN. Numeric keys are not
chronological ranks, native identities, semantic ordering or completeness evidence. Mixed metadata and
numeric entries do not themselves establish an unavailable API, runtime error or semantic failure.

The video placement ID/start/end/duration were identical over two consecutive no-edit reads:
f961cbd6-6703-4df5-a4d3-d30aa439f47d / 108000 / 108087 / 87.
Claim only: same-session immediate reread stability observed. No cross-session identity stability,
persistent handle identity, collection completeness or ordering semantics follows.
GetDuration(false) and GetDuration(true) both returned 87 for this fixture. This is equality for this
observation only, not proof that subframePrecision is irrelevant or coordinates are qualified.

The previous collection-wide positive-integer-key assumption was contradicted by P3. The correction
preserves raw nonnumeric metadata, inspects positive finite integer candidate keys independently and
diagnoses malformed entries individually. It does not interpret __flags or repair collections.
The revised source remains NOT EXECUTED and awaits Chat review; no runtime qualification claimed.

## Conversational readiness

These are reasoning/read readiness states only. NONE implies mutation, Safety PASS or approval.
All statuses below describe present evidence, not what a future probe might return.

| Intent | Required semantic facts | Reads intended to contribute / current Free evidence | Missing facts | Status |
| --- | --- | --- | --- | --- |
| 두 번째 클립 앞의 침묵을 줄여줘 | Explicit track/scope, ordered concrete placements, actual pause evidence, safe geometry, dependency/protection facts | P3 one video and one audio placement, raw IDs/ranges; no second-clip ordering proof | Second-clip scope, proven coordinates, silence vs gap, pause constraints, safety evidence | BLOCKED_UNKNOWN |
| B-roll과 겹치는 곳은 건드리지 마 | Explicit B-roll role binding, complete multi-track placements, overlap geometry, protection scope | P3 counts/placements and raw ranges; no B-roll role observed | Role assignment, complete inventory, aligned coordinates, protection context | BLOCKED_UNKNOWN |
| 영상은 그대로 두고 대사 간격만 줄여줘 | Explicit dialogue targets, video preservation set, source ranges, A/V relationships, timing/dependency facts | P3 distinct placements share a source ID; no relationship evidence | Dialogue identity, source spans, sync meaning, geometry, picture preservation proof | BLOCKED_UNKNOWN |
| 속도 변경된 클립은 제외해 | Reliable per-placement retime/speed observation and complete target scope | No retime read in first probe | Retime vocabulary/mapping and actual per-item observations | BLOCKED_UNKNOWN |
| 이 클립이 어느 소스에서 온 건지 확인해 | Unambiguous concrete placement and directly observed media binding/IDs | P3 both GetMediaPoolItem calls succeeded and share source GetUniqueId | This-clip target, currentness and identity lifetime remain unproven | PARTIAL |

Understanding/explaining these requests remains available as shared conversational behavior; the blocked
state concerns evidence needed to reason concretely. No edition-specific command syntax is introduced.
No current row is BLOCKED_UNSUPPORTED because inability has not been directly demonstrated. READY_TO_REASON
requires sufficient verified semantic facts; PARTIAL requires useful observed facts for that exact intent.

## Open questions and operator handoff

1. Which proven in-process entry point can execute the reviewed file as one shot? Menu remains
   INCONCLUSIVE. No workaround is implemented; an operator must preserve the execution path as evidence.
2. Which remaining Lua types/handle shapes can be qualified beyond the reported P3 mixed-key table?
3. What are endpoint, fractional coordinate and source/timeline conventions? No correspondence inferred.
4. What identity lifetime, completeness and freshness can later evidence establish?
5. Which direct retime/relationship/selection reads and complete protection evidence support deferred intents?
6. Where will explicit B-roll/dialogue/target bindings come from under shared contracts?

## Planned complete P2 capture — NOT EXECUTED

1. Before any execution, obtain Chat review of the mixed-key correction and record its exact commit.
   Previously approved source was at 240e0aec3cca8380dbf8759a023a2dc236a008cf. Revised source:
   tools/free_bridge_probe/resolve_free_f1.lua, SHA-256
   86d4a843fe6ea11dd086feaa99ba035ce6dab0f554dd0c66e549ed3453cf58e3.
   Record operator, runtime version, project/timeline context and session/time without inventing IDs.
2. Establish and document a directly evidenced in-process one-shot entry path for that exact source.
   Console printing/global root evidence alone does not prove execution of the reviewed file.
   Workspace launcher remains INCONCLUSIVE. If the path cannot be evidenced, HOLD; do not implement
   a loader, file sink, dynamic execution, UI fallback, listener or transport to bypass this prerequisite.
3. Operator confirms Console scripting/error visibility and Lua context; preserves pre-execution Console
   state and records the exact entry action/source identity. No project/timeline state changes for capture.
4. Execute the reviewed source exactly once via the evidenced path. This reconciliation does not execute
   it or assert that a path has been qualified. No automatic retry or retry-until-green.
5. Operator preserves the complete original BOOT -> OBS -> END output, including NIL/UNAVAILABLE/ERROR/
   UNKNOWN and any unprefixed runtime errors. Do not replace P3 prose with fabricated probe lines.
6. Missing BOOT, missing END, truncation or serialization error means incomplete evidence. Preserve the
   failure and path details for Chat review; do not repair or silently rerun. Keep P2 separate from P3.
7. Reconcile raw forms with semantic limitations only after receipt. No capability lifetime, coordinate
   correspondence, F2/F3, mutation or parity authorization follows from one completed capture.

## Semantic qualification Phase 1 — design only

Chat approves the F1 static probe/mixed-key correction; semantic qualification remains IN PROGRESS.
Specification and shared-contract audit:
[tasks/TASK_023_F1_SEMANTIC_QUALIFICATION_PHASE_1.md](../tasks/TASK_023_F1_SEMANTIC_QUALIFICATION_PHASE_1.md).

Additional operator P3 observations: video GetStart(false)=GetStart(true)=108000;
GetEnd(false)=GetEnd(true)=108087; GetDuration(false)=GetDuration(true)=87. Equality is limited to this
fixture; endpoint convention, origin, exact rate, source/timeline correspondence and subframe semantics
remain NOT_ESTABLISHED/UNKNOWN. No half-open FrameRange is constructed from these numbers.

Highest observed lifetime level: partial I0, video placement ID/start/end/duration only. Project/timeline/
source ID repeat comparisons were not supplied; I1-I4 NOT_OBSERVED. No shared IdentityScope promotion.
Same-session immediate equality does not establish currentness, atomic capture or a trustworthy token.
Freshness-required use stays BLOCKED_UNKNOWN; known snapshot/base mismatch stays STALE.

Seven controlled coordinate cases and independent I0-I4 comparisons are specified, not executed.
No fixture creation/repair, probe extension, new native calls or installer/distribution work.
All conversational readiness statuses above remain unchanged. Wait for Chat Gate before runtime work.

## Current reconciliation - approved C01 / C02 / I0 (2026-10-09)

This entry supersedes earlier evidence-availability summaries for these specific fixtures; earlier P3
observations remain historical. Full values, source hashes and approval links are retained in
[the appended runtime reconciliation report](reports/TASK_023_FREE_BRIDGE_FEASIBILITY.md#f1-runtime-evidence-reconciliation-report---c01--c02--i0).

| Evidence scope | Gate | Native fact / approved bounded finding | Semantic limit |
| --- | --- | --- | --- |
| C01, PF_FREE_C01_v1 / Timeline 1 | PASS bounded case | Timeline and placement 86400..87120; duration 720; independent visible source 0000..0719 = 720 | CORRESPONDENCE_CANDIDATE; endpoint NOT_ESTABLISHED |
| I0, same C01 context | PASS immediate reread | Project/timeline/placement/source IDs and start/end/duration identical in A/B | STABLE_OBSERVED_AT_LEVEL for seven fields at I0 only |
| C02 attempt 1 | INCOMPLETE | Unexpected A1 audio placement; stopped without deletion/repair/trim | Historical failure preserved; no adjacency result |
| C02 attempt 2, C02_ADJACENT_24_ATTEMPT2 | PASS bounded case | A 86400..87120; B 87120..87840; duration 720 each; independent A0719 -> next frame -> B0000 | Strengthened CORRESPONDENCE_CANDIDATE, not VERIFIED_EXACT |

Native context: product DaVinci Resolve, version 21.1.1.10; product is not proof of edition.
C01 track counts video=1/audio=1/subtitle=0. C02 attempt 2 video=2/audio=1/subtitle=0;
V1 has numeric entries 1,2 plus __flags=4194304; V2 and A1 have __flags only and no numeric items observed.
No collection completeness/ordering or __flags interpretation follows. Raw ID/name/count shapes remain
AVAILABLE_TYPED only; coordinates and collection correspondence remain AVAILABLE_AMBIGUOUS.

Endpoint convention NOT_ESTABLISHED; FrameRange construction NOT AUTHORIZED. No global half-open,
source/timeline coordinate identity, stable handle or shared IdentityScope promotion. I1-I4 NOT_OBSERVED.
Currentness/atomicity/state token remain unverified; existing fail-closed rules unchanged.
P3 sources are operator summaries and linked Chat approvals, not complete command/raw transcripts.
P2 reviewed probe NOT EXECUTED. No new capture or synthetic probe output. Workspace launcher INCONCLUSIVE.
These fixture results do not resolve the missing editorial facts for the five intents above or grant
mutation readiness. C03-C07 not authorized; no I1 work or F2/F3/IPC/mutation/persistence/parity/distribution.

## Current I1 reconciliation - later same-session observation

P3 operator summary now supplies I1 Set A 02:05:20 KST and Set B 11:35:20 KST; reported elapsed
interval 9 hours 30 minutes. Calendar dates/run IDs/exact commands/full transcript were not supplied.
Target match count=1 in both sets. Project/timeline/placement/source IDs and start/end/duration were
identical; all seven fields are STABLE_OBSERVED_AT_LEVEL at I1 only. Values and activity are preserved in
[the appended I1 report](reports/TASK_023_FREE_BRIDGE_FEASIBILITY.md#f1-i1-runtime-evidence-reconciliation-report).
The target is the reported C02 attempt 2 A placement, not the distinct C01/I0 placement.

Operator activity: no edit, playback/scrub, timeline switch or project close/reopen; PC idle.
Supplied I1 gate PASS applies to this same-session later reread and exact interval only. Earlier
NOT_OBSERVED entries remain historical; I2-I4 remain NOT_OBSERVED/NOT_AUTHORIZED. No inference between levels.
No SESSION_LOCAL_VERIFIED/PERSISTENT_VERIFIED promotion, native persistence, currentness/atomicity,
state token or handle stability proof. Raw capability classes and conversational readiness unchanged.
Coordinate CORRESPONDENCE_CANDIDATE; endpoint NOT_ESTABLISHED; FrameRange construction NOT_AUTHORIZED.
P2 probe still NOT_EXECUTED; P3 summary is not a complete transcript. No new Resolve execution or reads.
C03-C07/F2/F3/IPC/mutation/persistence/parity/distribution remain out of scope; stop for Chat Gate.
