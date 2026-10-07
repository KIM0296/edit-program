# Probe Fixture Catalog v1

Status: **ACCEPTED — ADR-034 canonical F0–F4 fixture catalog**

## Purpose

Define the exact canonical synthetic fixtures used by TASK-020 read-only runtime validation and
TASK-021 fixture materialization.

These fixtures validate Resolve adapter behavior, identity observations, coordinate reads and read
stability. They are not editorial-quality evaluation footage.

## Fixture media boundary

F0–F4 use dedicated synthetic canonical media only.

Real interview/talking-head/podcast/lecture footage belongs to Pause/Dialogue quality evaluation and
real-workflow pilots. Real footage must not silently replace a canonical probe asset because doing so
would destroy deterministic fixture identity and reproducibility.

## Common coordinate convention

All timeline ranges use integer half-open intervals.

For each fixture timeline:

- `T0 = observed Timeline.GetStartFrame()`
- catalog timeline ranges are expressed as offsets from T0
- example `[+100,+200)` means native timeline range `[T0+100,T0+200)`
- source ranges are source-frame coordinates and are not derived from timeline offsets
- no rounding or implicit frame-rate conversion is allowed

This deliberately avoids assuming that a Resolve timeline begins at native frame zero.

## Common timeline profile

Unless a fixture says otherwise:

- timeline rate: 24/1 fps
- display start timecode: 01:00:00:00
- one video format profile shared by the catalog
- no retime
- no transition
- no Edit/Fairlight effect
- no keyframe
- no marker/subtitle unless explicitly declared
- declared tracks are the complete expected track set for that fixture
- undeclared placements are a canonical MISMATCH

The exact raster/codec of canonical assets is package-level materialization data; TASK-021 records
their content hashes. Fixture semantics do not depend on filename.

## Canonical asset roles

TASK-021 will materialize and content-hash these asset roles:

| Asset role | Minimum semantic requirement | Minimum source length |
| --- | --- | ---: |
| ASSET_ALPHA | unique synthetic A/V content | 600 frames |
| ASSET_BETA | distinct synthetic A/V content | 600 frames |
| ASSET_GAMMA | distinct synthetic A/V content | 600 frames |
| ASSET_REPEAT | synthetic A/V content intentionally reused across placements/timelines | 600 frames |
| ASSET_VIDEO_ONLY | synthetic video-only content | 600 frames |
| ASSET_AUDIO_ONLY | synthetic audio-only tone/noise fixture | 600 frames |

A/V assets should contain simple deterministic visible/audible cues useful for manual diagnosis, but
their authoritative identity is the TASK-021 package hash, not filename or visual appearance.

## Common fixture role rules

Every placement has an explicit semantic role.

FixtureRoleBinding may use the entire expected semantic tuple while verifying a static canonical
fixture, including fixture timeline context, declared track, media role, source range and timeline
range.

It may not fall back to:

- first returned item
- filename
- clip name
- track name alone
- track index alone
- current position alone

A role with zero matches is unresolved. A role with more than one full semantic match is ambiguous.

---

# F0_BASIC — Basic geometry and linked A/V observation

## Purpose

Validate the core Tier A read path:

- timeline geometry
- track enumeration
- placement timeline ranges
- source ranges
- MediaPool binding
- linked A/V observation
- item/track identity observations
- gaps without treating gaps as placements

## Project

- fixture_ref: `F0_BASIC`
- fixture_version: `v1`
- one dedicated disposable project
- one timeline: `PF_F0_BASIC_v1`

## Tracks

| Role | Type/index | Enabled | Locked |
| --- | --- | --- | --- |
| V_MAIN | video/1 | true | false |
| A_MAIN | audio/1 | true | false |

## Placements

Each A/V role consists of a linked video item on V_MAIN and matching audio item on A_MAIN.

| Role | Asset | Timeline range | Source range |
| --- | --- | --- | --- |
| F0_A | ASSET_ALPHA | [+100,+200) | [24,124) |
| F0_B | ASSET_BETA | [+240,+340) | [48,148) |
| F0_C | ASSET_GAMMA | [+400,+500) | [72,172) |

Expected empty timeline intervals include:

- [+200,+240)
- [+340,+400)

The gaps are observations of absence, not objects with generated identity.

## Expected relationships

- video/audio members of each F0_A/F0_B/F0_C role are expected to be native-linked if the template
  preserves standard A/V linking
- no relationship is inferred between A, B and C
- GetLinkedItems() is descriptive evidence only

---

# F1_REPEATED_MEDIA — Repeated-media placement disambiguation

## Purpose

Prove that the adapter does not treat MediaPool identity, filename or source range as placement
identity.

## Project

- fixture_ref: `F1_REPEATED_MEDIA`
- fixture_version: `v1`
- one dedicated disposable project
- one timeline: `PF_F1_REPEAT_v1`

## Tracks

| Role | Type/index | Enabled | Locked |
| --- | --- | --- | --- |
| V_MAIN | video/1 | true | false |
| A_MAIN | audio/1 | true | false |

## Placements

All roles use the same ASSET_REPEAT MediaPool item.

| Role | Timeline range | Source range | Intent |
| --- | --- | --- | --- |
| F1_R1 | [+100,+200) | [120,220) | first placement |
| F1_R2 | [+260,+360) | [120,220) | same media AND same source range as R1 |
| F1_R3 | [+420,+520) | [240,340) | same media, different source range |

Each role may have linked audio/video members as in F0.

## Required validation property

R1 and R2 must remain distinct placement observations even though media identity and source range are
the same.

A resolver that collapses R1/R2 to one object or chooses the first returned item fails the fixture.

Timeline range participates in canonical fixture verification but does not become future
execution-grade persistent identity.

---

# F2_TRACK_STATE — Track control-state matrix

## Purpose

Validate track enabled/locked reads without mixing them with editorial mutation.

## Project

- fixture_ref: `F2_TRACK_STATE`
- fixture_version: `v1`
- one dedicated disposable project
- one timeline: `PF_F2_TRACK_STATE_v1`

## Tracks

The fixture intentionally covers four control-state combinations.

| Role | Type/index | Enabled | Locked | Placement |
| --- | --- | ---: | ---: | --- |
| V_ACTIVE | video/1 | true | false | F2_V1 |
| V_DISABLED | video/2 | false | false | F2_V2 |
| A_LOCKED | audio/1 | true | true | F2_A1 |
| A_DISABLED_LOCKED | audio/2 | false | true | F2_A2 |

## Placements

| Role | Track | Asset | Timeline range | Source range |
| --- | --- | --- | --- | --- |
| F2_V1 | V_ACTIVE | ASSET_VIDEO_ONLY | [+100,+180) | [40,120) |
| F2_V2 | V_DISABLED | ASSET_VIDEO_ONLY | [+220,+300) | [160,240) |
| F2_A1 | A_LOCKED | ASSET_AUDIO_ONLY | [+100,+180) | [40,120) |
| F2_A2 | A_DISABLED_LOCKED | ASSET_AUDIO_ONLY | [+220,+300) | [160,240) |

The placements are intentionally independent; no A/V linkage semantics are required.

## Fail-closed rule

If the exact RuntimeProfile cannot read one required enabled/locked state reliably, the affected
field is not silently defaulted and F2 cannot qualify unchanged.

---

# F3_MARKER_SUBTITLE — Marker and subtitle temporal observation

## Purpose

Validate temporal dependent reads used later for marker/subtitle integrity.

## Project

- fixture_ref: `F3_MARKER_SUBTITLE`
- fixture_version: `v1`
- one dedicated disposable project
- one timeline: `PF_F3_MARKER_SUBTITLE_v1`

## Tracks

| Role | Type/index | Enabled | Locked |
| --- | --- | --- | --- |
| V_MAIN | video/1 | true | false |
| A_MAIN | audio/1 | true | false |
| S_MAIN | subtitle/1 | true | false |

## Host placement

| Role | Asset | Timeline range | Source range |
| --- | --- | --- | --- |
| F3_HOST | ASSET_ALPHA | [+100,+340) | [0,240) |

F3_HOST may use linked video/audio members.

## Timeline marker

- role: `F3_TL_MARK_A`
- timeline offset: +120
- duration: 12 frames
- color: Blue
- name: `TL_MARK_A`
- note: `probe timeline marker`
- custom-data semantic value: `probe:tl:a` when the installed API exposes it

## Item marker

Bound to the F3_HOST item:

- role: `F3_ITEM_MARK_A`
- item-relative offset: +40 frames
- duration: 8 frames
- color: Green
- name: `ITEM_MARK_A`
- note: `probe item marker`
- custom-data semantic value: `probe:item:a` when exposed

Do not convert item-relative marker coordinates into timeline coordinates without explicit mapping.

## Subtitle items

| Role | Timeline range | Canonical text |
| --- | --- | --- |
| F3_SUB_A | [+160,+220) | `PROBE ALPHA 01` |
| F3_SUB_B | [+260,+320) | `PROBE BETA 02` |

Subtitle text is a runtime-validation candidate, not assumed authority. If the installed
TimelineItem.GetName() or equivalent does not return the exact canonical text stably, subtitle text
remains PARTIAL/UNKNOWN while subtitle enumeration/timing may still be supported.

---

# F4_IDENTITY_BOUNDARY — Same-project identity round-trip

## Purpose

Test re-acquisition across timeline switching without allowing content/geometry to identify the
timeline or placement.

## Project

- fixture_ref: `F4_IDENTITY_BOUNDARY`
- fixture_version: `v1`
- one dedicated disposable project
- two timelines:
  - `PF_F4_A_v1`
  - `PF_F4_B_v1`

## Timeline A and B semantic layout

Both timelines intentionally contain the same semantic media layout.

Tracks on each:

- video/1 enabled/unlocked
- audio/1 enabled/unlocked

Placement on each:

| Timeline | Role | Asset | Timeline range | Source range |
| --- | --- | --- | --- | --- |
| A | F4_ITEM_A | ASSET_REPEAT | [+100,+200) | [120,220) |
| B | F4_ITEM_B | ASSET_REPEAT | [+100,+200) | [120,220) |

A and B therefore cannot be distinguished by media, track, timeline range or source range.

## S2 identity test

For one validation cycle:

1. capture A
2. switch to B
3. capture B
4. switch back to A
5. capture A again
6. compare A-before vs A-after identity observations and semantic state

ADR-033 requires 3 independent A -> B -> A round trips for a same-project switch-stability claim.

Timeline names are diagnostic only. The identity claim must be supported by observed native identity
and registered environment context.

## Scope limit

F4 does not prove project-reopen or application-restart persistence.

Those require ADR-033 S3/S4 when such lifetime is claimed.

---

# Catalog completeness rules

A fixture is canonical only when:

1. exact fixture/project generation is registered;
2. timeline profile matches;
3. expected track set matches;
4. expected track enabled/locked state matches where declared;
5. every declared placement binds exactly once;
6. timeline/source ranges match exactly;
7. MediaPool bindings match declared asset roles;
8. no undeclared placement exists;
9. fixture-declared markers/subtitles match;
10. required observations are complete for that FixtureClass.

Missing required evidence -> INCOMPLETE.

Known wrong or extra state -> MISMATCH.

Ambiguous role binding -> MISMATCH/non-ready.

Do not repair the same instance and then qualify it.

# Relationship to TASK-020 matrix

- F0 supports RV-004..035 core geometry/media reads and RV-044 full Tier A fence.
- F1 is mandatory for RV-021/022/027..033/042/043 repeated-media disambiguation.
- F2 is mandatory for RV-019/020 track state reads.
- F3 is mandatory for RV-016/021/036..040/042 marker/subtitle reads.
- F4 is mandatory for RV-006/010/022/031 identity switch-boundary evidence.

Every qualifying fixture subject to Tier A completeness uses ADR-033's 10 double-capture stability
pairs.

F4 additionally uses the three S2 timeline-switch round trips.

# Relationship to TASK-021 materialization

TASK-021 should materialize each F0–F3 fixture as an independent disposable project instance.

F4 is one disposable project instance containing its two required timelines.

Do not materialize one shared F0–F4 mega-project and treat all fixtures as independently isolated
destructive-probe instances.

A package implementation may share canonical asset bytes across projects, but project/fixture
identity and lifecycle remain independent.

# Real footage boundary

Real footage is valuable, but it serves a different evidence purpose.

Use real footage later for:

- Pause/Dialogue decision quality
- natural pacing and semantic ambiguity
- false-remove / over-tighten evaluation
- editor review/correction cost
- real workflow Net Editing Time Saved
- realistic project complexity after the native safety foundations are stable

Do not use real editorial footage to satisfy F0–F4 canonical hashes or read-stability qualification.

# Final principle

> F0–F4 are deliberately boring, synthetic and exact. Their job is to make Resolve behavior easy to
> attribute. Real footage is where editorial quality is measured, not where adapter determinism is
> first proven.


## Canonical asset package binding

ADR-036 / `docs/CANONICAL_FIXTURE_ASSET_PACKAGE.md` is authoritative for the actual F0–F4 media
bytes.

The catalog asset roles map to one immutable package:

- ASSET_ALPHA / BETA / GAMMA / REPEAT: 720p24 MOV + DNxHR LB + 48 kHz/24-bit stereo PCM
- ASSET_VIDEO_ONLY: same video profile, no audio stream
- ASSET_AUDIO_ONLY: 48 kHz/24-bit stereo PCM WAV

All assets are 30 seconds / 720 frames where video applies.

ASSET_REPEAT must be reused byte-for-byte across F1/F4 placements.

Fixture verification uses package content hashes and semantic role binding; diagnostic frame counters,
colors and tones do not become production identity authority.
