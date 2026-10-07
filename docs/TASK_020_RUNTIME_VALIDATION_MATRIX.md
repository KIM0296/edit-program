# TASK-020 Runtime Validation Matrix v1

Status: **ACCEPTED — ADR-033 authoritative v1 runtime validation policy**

Purpose: convert OPEN-019's documented read candidates into an executable runtime validation plan for
the exact installed Windows Resolve + adapter RuntimeProfile.

This matrix does not claim support from documentation alone.

## Runtime result vocabulary

Every tested read capability ends with exactly one runtime result:

- SUPPORTED_STABLE
- SUPPORTED_UNSTABLE
- UNSUPPORTED
- UNKNOWN

Definitions:

### SUPPORTED_STABLE

The installed API surface exists, the bounded read returns the expected typed shape, the field can be
bound to the registered probe context, and repeated reads on an unchanged fixture remain semantically
stable.

### SUPPORTED_UNSTABLE

The bounded read exists and returns typed data, but repeated unchanged reads differ or capture
consistency cannot be maintained.

### UNSUPPORTED

The exact installed Developer Scripting surface does not expose the required read or the bounded call
consistently reports that the feature is unavailable for this RuntimeProfile.

### UNKNOWN

The result cannot distinguish API absence from bridge/runtime error, return semantics are ambiguous,
or required identity/correspondence cannot be proven.

No runtime result is inferred from documentation, method-name strings, hasattr(), or a non-throwing
call alone.

## General discovery protocol

For every row:

1. Record exact Resolve product/version/build using Resolve read methods.
2. Record platform/architecture and adapter version from the host.
3. Inspect the installed Developer Scripting reference / DaVinciResolveScript.pyi.
4. Confirm the method on the actual object surface.
5. Execute only the bounded read.
6. Validate exact return type/shape; bool is not accepted as int.
7. Perform the read-stability protocol.
8. Record raw value, normalized semantic value, evidence reference and final runtime result.

## Validation fixture policy

TASK-020 does not materialize fixtures. The initial runtime validation uses a pre-existing registered
disposable probe project prepared outside the read-only adapter.

Minimum manually/canonically prepared fixture classes:

- F0_BASIC
  - one timeline
  - at least one video and one audio track
  - at least three ordinary timeline placements with known timeline/source extents
- F1_REPEATED_MEDIA
  - the same MediaPoolItem placed at least twice at different declared roles/ranges
- F2_TRACK_STATE
  - at least one known enabled/unlocked track and one declared alternate lock/enable state if the
    external test fixture can provide it
- F3_MARKER_SUBTITLE
  - known timeline marker
  - known item marker
  - at least one subtitle track/item if supported by the fixture
- F4_IDENTITY_BOUNDARY
  - at least two timelines in the same disposable project for switch round-trip tests

No TASK-020 code may create or modify these fixtures.

## Read stability protocol

### S1 — same-context semantic stability

For every Tier A field used by a qualifying ProbeSnapshot:

- perform 10 consecutive capture pairs on one unchanged fixture
- each pair consists of two complete Tier A captures back-to-back
- the two captures in each pair must be semantically equal after only explicitly permitted
  non-semantic ordering normalization
- all 10 accepted pairs must produce the same semantic fixture snapshot

Any unexplained difference -> SUPPORTED_UNSTABLE for the affected field/scope.

A failed pair is not retried until it passes; it remains evidence.

### S2 — timeline switch round-trip

For project/timeline/placement identity candidates:

- switch from fixture timeline A to registered timeline B and back to A
- perform 3 independent round trips
- re-capture the same semantic fixture after each return

This validates same-project re-acquisition, not persistence.

### S3 — project reopen boundary

Only when the control-plane harness can safely reopen the dedicated disposable probe project:

- close/switch away from the probe project
- reopen the exact registered probe project
- perform 3 independent reopen cycles
- re-capture semantic state

This test is required before claiming identity survives project reload.

TASK-020 may omit S3 and keep identity scope UNKNOWN if the control-plane boundary is not yet
available.

### S4 — Resolve application restart

Not required for basic TASK-020 completion.

It is required before any Project/Timeline/TimelineItem identity is called PERSISTENT_VERIFIED across
application sessions.

Without S4, readable unique IDs remain observations only.

## Capture consistency rule

For Tier A runtime validation, use a double-capture semantic fence:

1. capture full required Tier A scope as A
2. immediately capture the same full required Tier A scope as B
3. require semantic A == B

If A != B, CaptureConsistency is UNSTABLE.

This is a conservative consistency test, not a claim of native atomic snapshot support.

## Matrix

| ID | Domain | Candidate installed API read | Expected runtime shape | Fixture | Stability | Acceptance for SUPPORTED_STABLE | Failure / conservative result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RV-001 | Resolve product | Resolve.GetProductName() | non-empty str | any | S1 | exact typed string stable | UNKNOWN on ambiguous bridge result |
| RV-002 | Resolve version | Resolve.GetVersion() | list/tuple [major,minor,patch,build,suffix] with typed fields | any | S1 | stable exact runtime tuple | UNKNOWN if shape differs |
| RV-003 | Resolve version string | Resolve.GetVersionString() | non-empty str | any | S1 | consistent with recorded version tuple without guessing normalization | SUPPORTED_UNSTABLE on drift |
| RV-004 | Project manager context | ProjectManager.GetCurrentDatabase() | dict with DbType, DbName, optional IpAddress | F0 | S1 | required keys typed and stable | UNKNOWN if malformed |
| RV-005 | Current project | Resolve/ProjectManager current project read | Project object | F0 | S1 | exact registered object can be read and subsequently queried | UNKNOWN on opaque/non-queryable object |
| RV-006 | Project observed ID | Project.GetUniqueId() | non-empty str | F0/F4 | S1+S2 | value stable within tested same-project boundaries | identity lifetime remains UNKNOWN; do not promote persistence |
| RV-007 | Project name | Project.GetName() | str | F0 | S1 | exact declared probe project name, stable | MISMATCH at environment layer if wrong; name never authority alone |
| RV-008 | Project settings snapshot | Project.GetSettings() | dict | F0 | S1 | declared required keys present with typed/string values | UNKNOWN/UNSUPPORTED per missing required key |
| RV-009 | Current timeline | Project/Resolve current timeline read | Timeline object | F0 | S1 | exact registered fixture timeline can be queried | UNKNOWN if no reliable object |
| RV-010 | Timeline observed ID | Timeline.GetUniqueId() | non-empty str | F0/F4 | S1+S2 | stable across 3 timeline switch round-trips | no persistent claim without S3/S4 |
| RV-011 | Timeline name | Timeline.GetName() | str | F0 | S1 | expected declared name | descriptive only |
| RV-012 | Timeline start | Timeline.GetStartFrame() | exact int, not bool | F0 | S1 | matches known fixture value | stable wrong value -> semantic MISMATCH, not read support failure |
| RV-013 | Timeline end | Timeline.GetEndFrame() | exact int, not bool | F0 | S1 | matches known fixture/native convention recorded explicitly | ambiguous end convention -> UNKNOWN semantic readiness |
| RV-014 | Timeline start TC | Timeline.GetStartTimecode() | str | F0 | S1 | stable syntactically valid returned label | never source/timeline mapping proof |
| RV-015 | Timeline settings | Timeline.GetSettings() | dict | F0 | S1 | required fixture keys present; deprecated singular getters not required | missing required setting -> UNKNOWN/UNSUPPORTED |
| RV-016 | Track count | Timeline.GetTrackCount(type) | exact int >=0 | F0/F3 | S1 | stable for video/audio/subtitle requested types | unsupported type behavior recorded exactly |
| RV-017 | Track name | Timeline.GetTrackName(type,index) | str | F0 | S1 | stable descriptive value | not identity authority |
| RV-018 | Track subtype | Timeline.GetTrackSubType(type,index) | str | F0 | S1 | audio subtype stable; documented blank on non-audio preserved | no inference from blank |
| RV-019 | Track enabled | Timeline.GetIsTrackEnabled(type,index) | bool | F2 | S1 | matches declared fixture state | missing/ambiguous -> UNKNOWN |
| RV-020 | Track locked | Timeline.GetIsTrackLocked(type,index) | bool | F2 | S1 | matches declared fixture state | missing/ambiguous -> UNKNOWN |
| RV-021 | Track item list | Timeline.GetItemListInTrack(type,index) | list of TimelineItem | F0/F1/F3 | S1 | deterministic semantic set after explicit sorting by observed stable keys | order alone has no semantic authority |
| RV-022 | Item observed ID | TimelineItem.GetUniqueId() | non-empty str | F0/F1/F4 | S1+S2 | stable within same timeline round-trips | no persistence claim without S3/S4/split tests |
| RV-023 | Item type | TimelineItem.GetType() when installed surface supports it | enum-like str | F0 | S1 | value in documented installed vocabulary | absent API -> UNSUPPORTED, not guessed |
| RV-024 | Item start | TimelineItem.GetStart(False) | exact int, not bool | F0/F1 | S1 | exact declared timeline start after explicit native convention check | float/nonintegral in False mode -> UNKNOWN for exact fixture |
| RV-025 | Item end | TimelineItem.GetEnd(False) | exact int, not bool | F0/F1 | S1 | exact declared native end value; relation to duration recorded | do not round |
| RV-026 | Item duration | TimelineItem.GetDuration(False) | exact int, not bool | F0/F1 | S1 | exact declared duration; start/end/duration relation validated empirically | inconsistent relation -> UNKNOWN mapping readiness |
| RV-027 | Source start | TimelineItem.GetSourceStartFrame() | exact int | F0/F1 | S1 | exact known source-start value | do not infer from timeline start |
| RV-028 | Source end | TimelineItem.GetSourceEndFrame() | exact int | F0/F1 | S1 | exact known source-end value and native convention recorded | ambiguous convention -> UNKNOWN mapping readiness |
| RV-029 | Track membership | TimelineItem.GetTrackTypeAndIndex() | [str,int] | F0/F1 | S1 | exact declared track type/index | index is locator only, not persistent Track identity |
| RV-030 | MediaPool binding | TimelineItem.GetMediaPoolItem() | MediaPoolItem or explicit None | F0/F1 | S1 | ordinary fixture clips bind expected MediaPoolItem | None preserved, never synthesized |
| RV-031 | MediaPool item ID | MediaPoolItem.GetUniqueId() | non-empty str | F0/F1 | S1+S2 | stable within tested context | persistence not inferred |
| RV-032 | Media ID | MediaPoolItem.GetMediaId() | str | F0/F1 | S1 | stable non-empty where runtime supplies it | empty/None preserved as UNKNOWN evidence |
| RV-033 | Clip properties | MediaPoolItem.GetClipProperty() | dict | F0 | S1 | required fixture property keys typed/stable | no deprecated single-key dependence |
| RV-034 | Linked items | TimelineItem.GetLinkedItems() | list of TimelineItem | linked fixture if externally prepared | S1 | exact observed link set stable | descriptive only, never propagation semantics |
| RV-035 | Clip enabled | TimelineItem.GetClipEnabled() | bool | F0/F2 | S1 | matches declared fixture state | UNKNOWN if unavailable |
| RV-036 | Timeline markers | Timeline.GetMarkers() | dict keyed by frame offsets | F3 | S1 | exact declared marker semantic data stable | float keys normalized only by explicit exact representation rule |
| RV-037 | Item markers | TimelineItem.GetMarkers() | dict keyed by item-relative offsets | F3 | S1 | exact declared item marker stable | preserve item-relative coordinate meaning |
| RV-038 | Subtitle track items | GetTrackCount('subtitle') + GetItemListInTrack('subtitle',i) | count + list | F3 | S1 | declared subtitle items enumerate stably | unsupported runtime -> UNSUPPORTED |
| RV-039 | Subtitle timing | subtitle TimelineItem start/end/duration | exact integer geometry if supported | F3 | S1 | matches declared subtitle timing | do not infer if item representation differs |
| RV-040 | Subtitle text/name | TimelineItem.GetName() on subtitle item | str | F3 | S1 | stable and exactly matches declared test caption before promoting to canonical text read | otherwise Tier B/UNKNOWN |
| RV-041 | Read-only non-mutation | pre/post semantic snapshot digest | equal semantic snapshots | all | S1 | 10 validation pairs show no adapter-induced semantic change | any change is HARNESS_ERROR/non-qualifying |
| RV-042 | Role binding unique | FixtureRoleBinding derivation | exactly one observed object per required role | F0/F1/F3 | S1 | 1:1 binding with evidence refs | zero -> unresolved; 2+ -> ambiguous |
| RV-043 | Repeated-media disambiguation | role binding with same MediaPoolItem placed twice | distinct placement observations | F1 | S1 | roles remain unambiguous using declared semantic fixture facts without filename/first-match | ambiguity -> non-ready |
| RV-044 | Full Tier A semantic fence | complete required snapshot A/B | semantically equal | F0/F1/F3 | S1 | all 10 pairs equal | any unexplained mismatch -> SUPPORTED_UNSTABLE scope |

## Tier B diagnostic validation

Tier B reads may be collected but cannot make a generic Safety check PASS.

| ID | Observation | Candidate read | Validation | Result use |
| --- | --- | --- | --- | --- |
| RB-001 | simple/fixed speed | installed speed/property surface | typed + S1 stability | diagnostic only; no variable-retime proof |
| RB-002 | fades | TimelineItem.GetFades() where installed | dict shape + S1 | diagnostic only |
| RB-003 | generic item properties | TimelineItem.GetProperties() | dict + explicit supported keys | diagnostic only |
| RB-004 | transition-like item | TimelineItem.GetType() == transition plus geometry | typed/stable | presence/span only |
| RB-005 | Fusion presence | documented Fusion comp access/count | typed/stable | presence only |
| RB-006 | color graph presence | GetNodeGraph() where supported | object/presence stable | presence only |

## Tier C mandatory fail-closed cases

TASK-020 must not claim the following unless a later dedicated validation contract is executed:

- persistent Project identity across Resolve restarts
- persistent Timeline identity across Resolve restarts
- persistent TimelineItem identity across split/delete/restart boundaries
- stable native Track identity independent of type/index
- complete transition alignment/parameter preservation
- generic Edit/Fairlight effect graph preservation
- generic Inspector keyframe/interpolation preservation
- complete variable-retime curve
- generic PRESERVATION_PROVEN production

Their runtime status remains UNKNOWN or UNSUPPORTED for the relevant Safety use.

## Identity boundary claim matrix

| Claim | Minimum test needed | TASK-020 default |
| --- | --- | --- |
| readable native ID | S1 | allowed as observation |
| stable after timeline switch | S2 | may record switch-stable evidence |
| stable after project reopen | S3 | optional; no claim if omitted |
| stable after Resolve restart | S4 | outside basic TASK-020 completion |
| stable after split/delete | future destructive identity probe | outside TASK-020 |
| PERSISTENT_VERIFIED | all product-claimed boundaries explicitly proven | not granted by TASK-020 by default |

## TASK-020 completion gate proposed

TASK-020 may be considered runtime-complete for its first milestone only if:

1. RuntimeProfile RV-001..003 are SUPPORTED_STABLE.
2. Registered Project/Timeline context required by the probe environment is readable and stable.
3. Core Timeline/Track/TimelineItem geometry and media binding required by F0 are SUPPORTED_STABLE.
4. Source start/end reads are stable and their native coordinate convention is explicitly recorded.
5. Track enabled/locked reads required by F2 are stable, or TASK-020 explicitly narrows its fixture
   profile if the installed API proves unsupported.
6. Marker/subtitle reads are either SUPPORTED_STABLE for the declared F3 fixture or explicitly
   removed from the qualifying fixture profile with Chat review; UNKNOWN cannot silently pass.
7. All required role bindings are unique.
8. All 10 Tier A full-snapshot capture pairs are semantically equal on each qualifying validation
   fixture.
9. The read-only adapter source/interface exposes no mutation, generic execute/eval or repair path.
10. No Project/Timeline/TimelineItem ID is upgraded to PERSISTENT_VERIFIED solely because it stayed
    constant in S1/S2.

## Evidence record per matrix row

Record:

- validation_case_id
- RuntimeProfile ref
- installed .pyi/API reference version/hash if available
- object/method candidate
- fixture ref
- raw return representation
- validated return type/shape
- semantic normalized value
- stability run refs
- final runtime result
- limitation/reason
- evidence contract version

## Final principle

A field is not supported because Resolve documents it. It is supported for TASK-020 only after the
installed runtime repeatedly returns a typed, context-bound, semantically stable value on an unchanged
registered probe fixture.


## Canonical fixture catalog binding

F0–F4 are fixed by ADR-034 and `docs/PROBE_FIXTURE_CATALOG.md`.

The runtime matrix must use those exact semantic fixture definitions rather than ad-hoc local test
timelines.

Key bindings:

- F0_BASIC: core geometry/media/source/link reads and full semantic fence
- F1_REPEATED_MEDIA: repeated-media placement disambiguation
- F2_TRACK_STATE: enabled/locked state matrix
- F3_MARKER_SUBTITLE: timeline/item markers and subtitle reads
- F4_IDENTITY_BOUNDARY: three same-project timeline-switch round trips

All catalog timeline ranges are half-open offsets from the observed timeline start T0. Do not assume
native timeline frame zero.

TASK-020 may not silently simplify a fixture. If the installed RuntimeProfile cannot read a required
field, record UNSUPPORTED/UNKNOWN and follow the completion-gate review path.


## Runtime execution binding

ADR-038 / `docs/TASK_020_RUNTIME_EXECUTION_EVIDENCE_RUNBOOK.md` defines how this matrix is executed
and evidenced.

Key operational interpretations:

- F0/F1/F2/F3/F4-A/F4-B each receive their own 10-pair S1 sequence.
- A pair is two complete back-to-back Tier A captures, not two reads of one field.
- Failed pairs remain in the same validation run and prevent SUPPORTED_STABLE for affected scope.
- S1 human interaction with Resolve state is prohibited.
- F4 S2 is 3 explicit A→B→A round trips after S1.
- raw adapter returns and semantic normalized snapshots are stored separately.
- capability support status is distinct from fixture MATCH/MISMATCH.
- the final runtime evidence bundle must retain all pair/round-trip findings and be checksummed.

This binding does not change RV-001..044 acceptance semantics; it fixes their execution protocol.
