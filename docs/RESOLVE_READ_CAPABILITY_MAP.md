# Resolve Read Capability Map v1

Status: **DOCUMENTED CANDIDATE MAP — runtime validation required**

This map supports OPEN-019 and TASK-020. It distinguishes a documented/public read surface from an
execution-grade or Safety-grade capability.

The exact installed Resolve Developer Scripting reference, especially
`DaVinciResolveScript.pyi` on Resolve 21.1+, is the implementation-time authority. Mirrored/public
references are useful for planning but do not replace runtime validation.

## Status vocabulary

- **TIER_A_CANDIDATE** — required first-pass read surface for TASK-020.
- **TIER_B_PARTIAL** — useful observation exists, but not enough for generic Safety proof.
- **TIER_C_UNKNOWN** — generic proof/lifetime semantics remain insufficient or unverified.
- **HOST_DERIVED** — supplied by the adapter host rather than Resolve object state.

None of these labels means SUPPORTED_VERIFIED until the exact RuntimeProfile is probed.

## Runtime and project context

| Field | Candidate surface | Tier | Notes |
| --- | --- | --- | --- |
| Resolve product/version/build | Resolve version/product getters | TIER_A_CANDIDATE | Bind exact runtime profile; validate returned shape. |
| Platform/architecture | adapter host | HOST_DERIVED | Keep separate from Resolve object identity. |
| current database/library context | ProjectManager current database/context reads | TIER_A_CANDIDATE | Context evidence, not project identity by itself. |
| current Project identity | Project.GetUniqueId() + current project binding | TIER_A_CANDIDATE | ID is readable; persistence lifetime is not yet proven. |
| Project settings required by fixture | Project settings getters | TIER_A_CANDIDATE | Only fields explicitly required by the fixture profile. |

## Timeline

| Field | Candidate surface | Tier | Notes |
| --- | --- | --- | --- |
| Timeline identity | Timeline.GetUniqueId() | TIER_A_CANDIDATE | Readable ID; lifetime across reload/session remains unverified. |
| name | Timeline.GetName() | TIER_A_CANDIDATE | Never identity authority by itself. |
| start/end frame | GetStartFrame()/GetEndFrame() | TIER_A_CANDIDATE | Exact integer values required. |
| start timecode | GetStartTimecode() | TIER_A_CANDIDATE | Label/timecode data, not source↔timeline mapping proof. |
| required timeline settings | Timeline setting reads | TIER_A_CANDIDATE | Type/shape validate; no silent coercion. |
| track count | GetTrackCount(type) | TIER_A_CANDIDATE | video/audio/subtitle. |

## Track state

| Field | Candidate surface | Tier | Notes |
| --- | --- | --- | --- |
| track name | GetTrackName(type,index) | TIER_A_CANDIDATE | Descriptive only. |
| audio subtype | GetTrackSubType(type,index) | TIER_A_CANDIDATE | Blank/non-audio result must be preserved as documented behavior. |
| enabled state | GetIsTrackEnabled(type,index) | TIER_A_CANDIDATE | Required for fixture control-state checks. |
| locked state | GetIsTrackLocked(type,index) | TIER_A_CANDIDATE | Useful input to Safety evidence. |
| stable Track identity | no proven persistent track-ID contract | TIER_C_UNKNOWN | type/index is locator/snapshot context, not persistent identity. |

## Timeline placement / TimelineItem

| Field | Candidate surface | Tier | Notes |
| --- | --- | --- | --- |
| item ID | TimelineItem.GetUniqueId() | TIER_A_CANDIDATE | Do not infer PERSISTENT_VERIFIED from ID shape. |
| item type | TimelineItem.GetType() on documented 21.1 surface | TIER_B_PARTIAL | Version guard required. |
| timeline start/end/duration | GetStart()/GetEnd()/GetDuration() | TIER_A_CANDIDATE | Validate integer/subframe behavior for exact fixture use. |
| source start/end | GetSourceStartFrame()/GetSourceEndFrame() | TIER_A_CANDIDATE | Raw correspondence input; not mapping EXACT by itself. |
| track membership | GetTrackTypeAndIndex() | TIER_A_CANDIDATE | Track index is not persistent Track identity. |
| MediaPool binding | GetMediaPoolItem() | TIER_A_CANDIDATE | Preserve explicit missing/None. |
| linked items | GetLinkedItems() | TIER_A_CANDIDATE | Descriptive relation only; not propagation semantics. |
| clip enabled | GetClipEnabled() | TIER_A_CANDIDATE | Boolean read candidate. |
| generic properties | GetProperty()/GetProperties() | TIER_B_PARTIAL | Static/exposed subset only; not generic effect/keyframe proof. |
| fixed/simple speed | documented 21.1 speed read where present | TIER_B_PARTIAL | Does not prove full variable-retime curve. |
| fades | documented 21.1 GetFades() where present | TIER_B_PARTIAL | Useful bounded observation, not generic transition proof. |
| complete variable retime | no complete generic curve proof yet | TIER_C_UNKNOWN | Keep unsupported/unknown for Safety readiness. |

## Media identity

| Field | Candidate surface | Tier | Notes |
| --- | --- | --- | --- |
| MediaPoolItem unique ID | GetUniqueId() | TIER_A_CANDIDATE | Native ID, separate from canonical asset hash. |
| Media ID | GetMediaId() | TIER_A_CANDIDATE | Preserve as native media evidence. |
| required clip properties | GetClipProperty/GetMetadata family | TIER_A_CANDIDATE | Only typed/versioned required fields. |
| canonical asset identity | content hash in fixture package | HOST_DERIVED | Filename is never sufficient identity. |

## Markers and subtitles

| Field | Candidate surface | Tier | Notes |
| --- | --- | --- | --- |
| timeline markers | Timeline.GetMarkers() | TIER_A_CANDIDATE | Record frame/duration/name/note/custom data as returned. |
| item markers | TimelineItem.GetMarkers() | TIER_A_CANDIDATE | Keep item-relative semantics explicit. |
| subtitle track enumeration | GetTrackCount("subtitle") / GetItemListInTrack | TIER_A_CANDIDATE | Exact installed return behavior must be validated. |
| subtitle item timing | TimelineItem start/end/duration | TIER_A_CANDIDATE | Candidate timing evidence. |
| subtitle text/name | TimelineItem.GetName() observed on subtitle items | TIER_B_PARTIAL | Runtime validation required before treating it as canonical text authority. |
| full subtitle style/animation | no complete generic read contract established | TIER_C_UNKNOWN | Do not infer from text/timing alone. |

## Transition / effect / keyframe structures

| Field | Candidate surface | Tier | Notes |
| --- | --- | --- | --- |
| transition-like item type/presence | TimelineItem type/item enumeration on supported 21.1 builds | TIER_B_PARTIAL | Presence/span may be observable; full semantics are not. |
| transition full alignment/parameters | insufficient generic readback for proof | TIER_C_UNKNOWN | Do not generate PRESERVATION_PROVEN. |
| Fusion composition presence | GetFusionCompCount/name/list access | TIER_B_PARTIAL | Presence is not full editability preservation. |
| color node graph presence | GetNodeGraph() surface | TIER_B_PARTIAL | Not equivalent to generic Edit FX graph. |
| generic Edit/Fairlight effect graph | no complete generic proof surface established | TIER_C_UNKNOWN | Keep fail-closed. |
| generic Inspector keyframes/interpolation | incomplete generic readback | TIER_C_UNKNOWN | Domain-specific future producers may be possible. |
| generic preservation proof | no approved producer | TIER_C_UNKNOWN | OPEN-015 remains authoritative. |

## Identity interpretation

Readable `GetUniqueId()` values for Project, Timeline, TimelineItem or MediaPoolItem are observations.
They do not establish lifetime semantics.

TASK-020 must separately test identity stability across only the boundaries it intends to claim.
Until proven:

- do not mark Project/Timeline/TimelineItem identity as PERSISTENT_VERIFIED;
- do not use filename/name/index/position as a substitute;
- session/reload/split/delete correspondence remains OPEN-001/006/012.

## Capability discovery protocol

For every field:

1. inspect the exact installed Developer Scripting reference / `DaVinciResolveScript.pyi`;
2. confirm the method on the actual native object surface;
3. issue only the bounded read call;
4. validate exact return type/shape and absence semantics;
5. repeat reads on an unchanged canonical fixture;
6. record one of:
   - SUPPORTED_STABLE
   - SUPPORTED_UNSTABLE
   - UNSUPPORTED
   - UNKNOWN

Do not treat `hasattr()`, a documentation string, method-name presence, or a non-throwing call as
sufficient runtime support.

## TASK-020 initial target

TASK-020 should prioritize Tier A only.

The first runtime milestone is:

```text
RuntimeProfile
→ registered disposable Project
→ exact Timeline
→ track topology/state
→ TimelineItems
→ timeline/source/media geometry
→ linked/enabled state
→ markers/subtitle enumeration
→ capture consistency fence
→ repeated read stability
→ immutable ProbeSnapshot
```

Tier B may be collected as non-authoritative diagnostic evidence. Tier C must remain UNKNOWN or
unsupported until a dedicated proof contract and runtime evidence exist.

## OPEN-019 resolution rule

OPEN-019 is only partially resolved by this document.

It may be further resolved when TASK-020 records stable runtime evidence for Tier A on the exact
Windows Resolve/adapter RuntimeProfile and TASK-021 verifies the required materialization path.
