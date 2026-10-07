# TASK-020 Runtime Execution & Evidence Runbook v1

Status: **ACCEPTED — Chat Product/Architecture baseline**

## Purpose

Define the operator-level and adapter-level procedure for executing TASK-020 runtime validation against
one exact installed DaVinci Resolve RuntimeProfile and the canonical F0–F4 probe fixtures.

This runbook converts ADR-033 / ADR-034 from validation policy into an auditable execution protocol.

It does **not** implement Resolve mutation, fixture materialization, destructive probes or capability
promotion beyond TASK-020's read-only runtime evidence.

## Product/runtime baseline

As of this runbook's design date, Blackmagic Design lists DaVinci Resolve 21.1 documentation in its
current support material. This is only a release baseline.

For an actual TASK-020 run, the implementation authority is:

1. the exact installed Resolve runtime;
2. the exact installed Developer Scripting documentation;
3. the exact installed `DaVinciResolveScript.pyi` / equivalent developer stub if present;
4. the approved repository contracts.

Documentation presence alone never establishes runtime support.

## Relationship to TASK-022 and TASK-021

TASK-020 full canonical runtime qualification requires the approved first TASK-022 asset package.

TASK-020 does not materialize fixtures.

Before a qualifying TASK-020 runtime session, F0–F4 must already exist in a registered disposable
probe project prepared outside the read-only adapter using the approved canonical package.

For v1, this preparation may be a controlled one-time/manual engineering setup.

TASK-020 must never repair or recreate it.

TASK-021 later automates canonical fixture materialization and independent verification.

## Core execution rule

> Once a qualifying fixture session begins, the adapter observes. It does not help the fixture become
> correct.

If the project, timeline, track, marker, subtitle, media binding or fixture geometry is wrong:

- preserve the evidence;
- classify the mismatch;
- end or invalidate the affected run;
- do not repair from TASK-020.

---

# 1. Roles

## Operator

The human operator may:

- launch Resolve;
- open/select the registered disposable probe project;
- select the required fixture timeline before a phase;
- perform only the explicitly required F4 timeline switching;
- start/stop the TASK-020 validation command;
- record an operator incident note;
- terminate the run if the environment becomes unsafe or unclear.

The operator must not edit fixture content during a qualifying capture phase.

## TASK-020 adapter

The adapter may:

- inspect installed read API capability;
- perform bounded typed read calls;
- capture raw read results;
- normalize only approved nonsemantic ordering;
- produce semantic snapshots;
- compare captures;
- bind FixtureRoles;
- record runtime evidence;
- derive per-field runtime status.

The adapter may not:

- create or delete projects/timelines/tracks;
- import media;
- repair fixtures;
- rename objects;
- toggle tracks;
- move playhead as a hidden targeting heuristic;
- add/remove markers or subtitles;
- set current timeline unless a separately approved control-plane action supplies that operation;
- call generic execute/eval/script;
- invoke a planner/Safety/executor/mutation path.

## Control plane

The control plane supplies the registered probe environment and currentness facts.

TASK-020 consumes them.

TASK-020 does not authenticate OPEN-020 native registry truth by itself.

---

# 2. Run identity and evidence root

Every runtime session receives an immutable `validation_run_id`.

Recommended format:

```text
task020-YYYYMMDD-HHMMSSZ-<short-random-or-monotonic-ref>
```

The string format is convenience only; identity comes from the stored run record.

One validation_run_id binds exactly:

- one RuntimeProfile;
- one registered environment/project generation;
- one canonical package digest;
- one fixture catalog version;
- one TASK-020 adapter version/commit;
- one observation contract version;
- one runtime-validation-policy version;
- one operator session.

A RuntimeProfile or project-generation change requires a new validation_run_id.

Do not splice evidence from two RuntimeProfiles into one run.

---

# 3. Evidence directory layout

Recommended layout:

```text
evidence/task020/<validation_run_id>/
├─ run.json
├─ runtime_profile.json
├─ installed_api/
│  ├─ api_inventory.json
│  ├─ developer_stub.sha256
│  └─ discovery_findings.jsonl
├─ environment/
│  ├─ registration.json
│  ├─ currentness_preflight.json
│  └─ operator_preflight.json
├─ fixtures/
│  ├─ F0_BASIC/
│  │  ├─ fixture_binding.json
│  │  ├─ s1/
│  │  │  ├─ pair-01/
│  │  │  │  ├─ capture-A.raw.json
│  │  │  │  ├─ capture-A.semantic.json
│  │  │  │  ├─ capture-B.raw.json
│  │  │  │  ├─ capture-B.semantic.json
│  │  │  │  └─ pair-result.json
│  │  │  └─ ...
│  │  └─ fixture-summary.json
│  ├─ F1_REPEATED_MEDIA/
│  ├─ F2_TRACK_STATE/
│  ├─ F3_MARKER_SUBTITLE/
│  └─ F4_IDENTITY_BOUNDARY/
│     ├─ timeline-A/
│     │  └─ s1/...
│     ├─ timeline-B/
│     │  └─ s1/...
│     └─ s2/
│        ├─ roundtrip-01/
│        │  ├─ A-before.raw.json
│        │  ├─ A-before.semantic.json
│        │  ├─ B.raw.json
│        │  ├─ B.semantic.json
│        │  ├─ A-after.raw.json
│        │  ├─ A-after.semantic.json
│        │  └─ roundtrip-result.json
│        └─ ...
├─ findings/
│  └─ findings.jsonl
├─ summary/
│  ├─ capability-results.json
│  ├─ fixture-results.json
│  ├─ identity-results.json
│  └─ TASK_020_RUNTIME_REPORT.md
└─ evidence.sha256
```

The exact implementation may vary in filenames, but evidence must remain separable by:

- run;
- fixture;
- capture pair;
- raw vs semantic observation;
- finding;
- final derived result.

## Evidence checksum

After the run is finalized, generate an `evidence.sha256` over all authoritative evidence files
except itself.

Evidence hashing does not prove native authenticity. It detects later accidental modification.

---

# 4. run.json minimum record

Record:

- validation_run_id
- run_started_at UTC
- run_completed_at UTC or null until finalization
- adapter source revision
- TASK-020 contract version
- ADR-033 runtime policy version
- ADR-034 fixture catalog version
- TASK-022 canonical package name/version/digest
- environment_ref
- registry_ref
- project_generation
- runtime_profile_ref
- operator/session opaque ref
- requested fixture set
- requested S1/S2/S3/S4 phases
- final session state
- abort reason if any

Wall-clock time is audit metadata, not ordering authority for captures.

Every capture has an explicit sequence number.

---

# 5. RuntimeProfile freeze

RuntimeProfile is frozen before the first qualifying fixture capture.

Minimum fields:

- Resolve product name
- Resolve version tuple
- Resolve version string
- Resolve build identifier where available
- OS
- architecture
- adapter name/version
- adapter source revision
- installed developer-stub digest where available
- observation contract version
- fixture catalog version
- canonical package digest
- runtime validation policy version

If any profile-defining field changes during the session:

```text
SESSION -> STALE
STOP QUALIFYING CAPTURES
PRESERVE ALL PRIOR EVIDENCE
START NEW validation_run_id
```

Do not append new-profile evidence to the old session.

---

# 6. Installed API discovery phase

Run once before S1 qualification.

For each candidate matrix row:

1. inspect installed Developer documentation/stub;
2. record candidate object/method;
3. record whether it is represented by the installed surface;
4. obtain the actual native object through the normal read path;
5. execute only the bounded read when safe;
6. record raw result type/shape or exception;
7. do not assign SUPPORTED_STABLE yet.

## Discovery result vocabulary

Per candidate:

- CANDIDATE_PRESENT
- CANDIDATE_ABSENT
- CALLABLE_TYPED
- CALLABLE_AMBIGUOUS
- CALL_FAILED
- OBJECT_UNAVAILABLE
- DEFERRED_FIXTURE_REQUIRED

These are discovery findings, not final runtime support statuses.

## Method absence

If the exact installed developer surface clearly does not expose a required read:

- candidate runtime result may become UNSUPPORTED;
- preserve the installed documentation/stub evidence.

If documentation and actual surface disagree or bridge behavior is ambiguous:

- use UNKNOWN rather than guessing UNSUPPORTED.

## No hasattr-only proof

`hasattr()`, method-name strings or a non-throwing bridge call may be diagnostic only.

They never establish support.

---

# 7. Operator preflight checklist

Before qualifying captures:

- [ ] Resolve is launched normally.
- [ ] Exact registered disposable probe project is selected.
- [ ] This is not the user's working/production project.
- [ ] No production timeline is open in the probe environment.
- [ ] Canonical package digest matches the TASK-022 approved package index.
- [ ] F0–F4 fixture definitions match ADR-034.
- [ ] No concurrent editor is intentionally modifying the probe project.
- [ ] No fixture correction is planned during the run.
- [ ] Adapter version/source revision is recorded.
- [ ] Evidence root is empty/new.
- [ ] RuntimeProfile preflight completed.
- [ ] Environment currentness evidence completed.
- [ ] Operator acknowledges that a failed pair remains evidence.

If any item is not established:

- do not begin qualifying S1.

---

# 8. Fixture preflight audit

This is read-only.

For every fixture, capture one **non-qualifying setup audit** to determine whether it appears suitable
to enter the qualifying sequence.

This setup audit must be labeled:

```text
purpose = PREFLIGHT_DIAGNOSTIC
counts_toward_s1 = false
```

Check:

- expected fixture/project/timeline registration;
- canonical asset role availability;
- expected track count/topology where readable;
- expected declared placements;
- source/timeline geometry where readable;
- markers/subtitles where required;
- unique role binding;
- no unexpected extra placement where the catalog forbids it.

A preflight MATCH does not count as one of the 10 pairs.

A preflight mismatch:

- blocks that fixture's qualifying S1;
- is preserved;
- is not repaired by TASK-020.

---

# 9. Raw capture contract

A raw capture stores the exact typed adapter observations before semantic normalization.

For every field record:

- matrix case ID
- object kind
- opaque object/locator evidence if available
- method/read candidate
- args
- return presence
- exact runtime type
- raw representable value
- exception/error category if any
- capture sequence
- fixture/timeline context
- RuntimeProfile ref

Raw evidence may redact machine paths or non-semantic host details only under an explicit evidence
redaction policy. Never transform a semantic native value for convenience.

---

# 10. Semantic normalization contract

Allowed normalization is limited to nonsemantic ordering where the native API does not define order.

Examples:

- sort track/item observations by explicitly observed semantic keys;
- sort marker maps by exact frame-offset key;
- sort role-binding evidence by FixtureRole.

Forbidden normalization:

- rounding frame values;
- converting float to int by coercion;
- replacing None/empty/false with each other;
- filling missing IDs from names;
- changing track index to a persistent track identity;
- dropping duplicate-looking repeated-media placements;
- normalizing unexpected objects away;
- treating unordered content as equal when multiplicity differs;
- ignoring a changed native ID to make snapshots equal;
- shifting source/timeline coordinates to match the catalog;
- converting an unsupported value to a default.

Every normalization function/version must be recorded in the observation contract.

---

# 11. Full semantic snapshot

A qualifying capture is not one API call.

It is one full required Tier A fixture observation.

The snapshot includes every required field for the fixture's qualification profile.

Capture order is deterministic and versioned.

Suggested high-level order:

1. runtime/project context
2. timeline identity/settings/range
3. track topology/state
4. item enumeration
5. item geometry/source
6. media-pool binding/properties
7. links/enabled state
8. markers
9. subtitles
10. fixture-role binding
11. completeness fence

The order does not confer semantic priority.

---

# 12. Capture consistency fence

Each complete capture records:

- capture_started sequence
- start environment/profile fence
- all reads
- end environment/profile fence
- completeness result

If the start and end fence disagree:

```text
capture_consistency = UNSTABLE
capture is retained
affected scope cannot qualify as stable
```

Do not silently re-run it.

This is not native atomic snapshot proof.

---

# 13. S1 protocol — 10 consecutive double-capture pairs

## Qualifying fixture targets

Run S1 for:

- F0_BASIC
- F1_REPEATED_MEDIA
- F2_TRACK_STATE
- F3_MARKER_SUBTITLE
- F4 timeline A
- F4 timeline B

Thus each registered current-timeline context used for qualification receives its own 10-pair
sequence.

If implementation later represents F4 as a single multi-timeline snapshot, that change requires
Chat review; do not silently reinterpret this runbook.

## Pair structure

For pair `n = 01..10`:

```text
PAIR_n_START
  ↓
Capture A: full Tier A scope
  ↓
Immediately Capture B: same full Tier A scope
  ↓
Compare semantic A vs B
  ↓
Persist pair result
PAIR_n_END
```

No successful pair substitutes for a failed earlier pair.

## Consecutive meaning

Between A and B:

- no human action;
- no timeline switch;
- no playback command;
- no scrubbing;
- no selection-based targeting change;
- no project switch;
- no fixture edit;
- no adapter repair.

Between pair N and N+1:

- no fixture mutation;
- no timeline switch;
- no track/marker/subtitle change;
- only the minimum operator action needed to continue/abort the validation runner.

If a user interaction occurs unexpectedly:

- record an OPERATOR_INTERFERENCE finding;
- do not erase the pair;
- affected fixture qualification becomes non-clean for that session;
- start a new validation_run_id if a clean qualifying sequence is desired.

## Pair acceptance

Pair accepted only when:

- both captures COMPLETE;
- both capture fences stable;
- same RuntimeProfile;
- same registered environment/project generation;
- same fixture/timeline context;
- semantic snapshot A == semantic snapshot B.

Otherwise pair result is FAILED or UNSTABLE with explicit reasons.

## 10/10 condition

For a field/scope to contribute to SUPPORTED_STABLE:

- all 10 pairs meet equality;
- all accepted semantic snapshots across all 10 pairs agree with the same fixture semantics.

One unexplained drift is enough to prevent SUPPORTED_STABLE for the affected scope.

Do not compute a pass percentage.

---

# 14. Per-field runtime classification

Classification is per capability/field and separately per fixture semantic result.

## SUPPORTED_STABLE

Use only if:

- installed read exists;
- bounded call succeeds;
- exact typed shape is understood;
- context binding is proven for TASK-020 scope;
- required S1 evidence is complete;
- no unexplained drift exists.

## SUPPORTED_UNSTABLE

Use if:

- read is available and semantically interpretable;
- but repeated unchanged captures drift or consistency fence fails.

## UNSUPPORTED

Use only when:

- installed surface explicitly lacks the required read; or
- installed runtime gives a consistent, understood unsupported result for this feature/profile.

## UNKNOWN

Use for:

- bridge ambiguity;
- malformed/undocumented return shape;
- object correspondence uncertainty;
- exception whose cause cannot distinguish absence from runtime failure;
- unresolved coordinate convention;
- ambiguous identity.

## Important separation: support vs fixture correctness

Example:

```text
GetStartFrame() returns stable exact int 86400 in all pairs
but canonical fixture expected T0=90000
```

Then:

- read capability may be SUPPORTED_STABLE;
- fixture semantic verification is MISMATCH.

Do not label the read UNSUPPORTED/UNSTABLE merely because the stable value is wrong for the fixture.

---

# 15. F0_BASIC execution

Purpose:

- establish core project/timeline/track/item/media geometry read path.

Required checks include relevant RV-004..035 rows.

Operator:

1. select registered F0 timeline before S1;
2. do not touch timeline during 10 pairs.

Adapter verifies:

- T0 and timeline range;
- tracks;
- F0_A/B/C video/audio placements;
- source ranges;
- declared gaps as absence;
- MediaPool bindings;
- links if readable;
- clip-enabled state;
- unique FixtureRoleBinding.

Do not treat gaps as generated native objects.

---

# 16. F1_REPEATED_MEDIA execution

Purpose:

- prove repeated media is not collapsed.

Required semantic distinction:

```text
F1_R1:
same media as R2
same source range as R2
different timeline placement

F1_R2:
same media as R1
same source range as R1
different timeline placement
```

Acceptance:

- both must remain separate observations;
- multiplicity must be two;
- role binding must be unique using the full canonical fixture facts.

Immediate failure finding:

- FIRST_MATCH_FALLBACK
- MEDIA_ID_COLLAPSE
- SOURCE_RANGE_COLLAPSE
- AMBIGUOUS_ROLE_BINDING

Filename is never a resolving key.

---

# 17. F2_TRACK_STATE execution

Purpose:

- validate enabled/locked state reads.

Read all four declared track-control combinations.

Do not toggle tracks during TASK-020.

If the installed API cannot read one required state:

- record field UNSUPPORTED or UNKNOWN based on evidence;
- fixture profile cannot silently default that state.

---

# 18. F3_MARKER_SUBTITLE execution

Purpose:

- validate temporal dependent observations.

Required:

- timeline marker semantic fields;
- item marker semantic fields;
- marker coordinate domain;
- subtitle track/item enumeration;
- subtitle timing;
- subtitle text only when the exact runtime read returns stable canonical text.

If subtitle timing is stable but subtitle text read is ambiguous:

- timing may qualify;
- text remains UNKNOWN/PARTIAL;
- do not make the entire observed object disappear.

Do not convert item-relative markers into timeline coordinates unless the explicit approved mapping
contract performs that mapping.

---

# 19. F4_IDENTITY_BOUNDARY S1 execution

F4 has two timelines with intentionally identical semantic layout.

Before S2:

- perform 10 S1 pairs on timeline A;
- perform 10 S1 pairs on timeline B.

Names are diagnostic only.

No identity claim may use:

- media equality;
- source range equality;
- track/range equality;
- timeline name alone.

---

# 20. S2 protocol — three A → B → A round trips

Purpose:

Validate same-project re-acquisition stability.

This is not persistent identity across project reload or application restart.

For each round trip 1..3:

1. operator/control plane establishes timeline A as current;
2. adapter captures complete A-before snapshot;
3. operator performs the one approved switch to registered timeline B;
4. adapter captures complete B snapshot;
5. operator switches back to registered timeline A;
6. adapter captures complete A-after snapshot;
7. compare A-before vs A-after semantic state and identity observations;
8. preserve B evidence;
9. record exact operator action sequence.

## S2 operator action boundary

Timeline switching is the only intentional state-changing UI/control action in S2.

It changes current context, not timeline content.

Do not:

- rename timelines;
- select a different B;
- edit either timeline;
- rebuild fixture;
- use name-only lookup as identity proof.

## S2 success

A same-project switch-stability claim requires all three round trips to satisfy:

- correct registered A/B contexts;
- complete captures;
- A-before semantic == A-after semantic;
- identity candidate value is stable for its explicitly claimed boundary;
- no ambiguity in re-acquisition.

Readable `GetUniqueId()`-like values remain observations.

S2 does not grant PERSISTENT_VERIFIED.

---

# 21. S3 project reopen protocol

Optional for basic TASK-020 completion.

Run only if:

- control plane has an approved safe way to leave/reopen the dedicated disposable project;
- exact project-generation/currentness can be re-established;
- the project-reopen lifetime claim is intentionally in scope.

If not, record:

```text
S3 = NOT_EXECUTED
project-reopen identity lifetime = UNKNOWN
```

Do not call it a failure.

If executed:

- 3 independent reopen cycles required;
- each cycle gets explicit before/after environment evidence;
- no stale authorization or old Python object is reused as native authority.

---

# 22. S4 Resolve restart protocol

Not required for TASK-020 basic completion.

Required before any cross-session PERSISTENT_VERIFIED identity claim.

If omitted:

- project/timeline/item IDs may be switch-stable observations;
- they are not persistent identity.

---

# 23. Allowed and forbidden human activity

## Allowed before a fixture qualifying phase

- opening Resolve;
- selecting registered probe project;
- selecting exact registered fixture timeline;
- confirming operator checklist;
- starting capture runner.

## Allowed during S1

- only abort/continue controls that do not alter Resolve state.

## Allowed during S2

- exact A→B→A current-timeline switching defined by the protocol;
- abort.

## Forbidden during qualifying captures

- edit/trim/move/split/delete;
- marker/subtitle changes;
- track lock/enable toggles;
- media relink;
- proxy/cache replacement intended to alter semantics;
- project settings changes;
- timeline settings changes;
- rename used to fix binding;
- manual correction after a mismatch;
- switching to an undeclared timeline;
- collaboration edits by another user;
- running TASK-021 materialization;
- native mutation probes.

---

# 24. Retry and rerun policy

## No retry-until-green

If pair 4 drifts:

- pair 4 remains failed evidence;
- pair 5 may still run for diagnostics;
- the scope does not regain 10/10 qualification in that validation_run_id.

Do not delete pair 4 and renumber later pairs.

## Infrastructure abort before qualifying evidence

If the runner fails before any qualifying S1 capture is created:

- session may end as ABORTED_INFRASTRUCTURE;
- a new validation_run_id may be started.

Preserve the aborted run record.

## Environment/profile change

Always start a new validation_run_id.

## Fixture discovered wrong

Do not repair inside the run.

TASK-020 stops qualification for that fixture.

A corrected externally prepared fixture requires a new fixture instance/generation and new
validation run evidence.

---

# 25. Exception / None / empty handling

## Exception

Record:

- exception category;
- message digest/redacted representation if needed;
- object/read candidate;
- context;
- sequence.

Classify UNKNOWN unless the exception is an explicitly understood unsupported behavior.

## None

Preserve None.

Do not convert to false, empty list, zero or absent.

## Empty string

Preserve empty string.

A field requiring non-empty identity cannot qualify from empty string.

## False

Preserve boolean false.

Do not confuse with unsupported/unknown.

## Empty collection

Preserve collection presence and cardinality.

An expected empty result can be valid only when fixture semantics expect it.

---

# 26. Capability result evidence

Each runtime matrix row produces:

- validation_case_id
- RuntimeProfile ref
- fixture refs contributing evidence
- installed API/stub evidence ref
- read candidate
- observed raw types/shapes
- semantic normalization version
- S1 pair refs
- S2/S3/S4 refs where relevant
- final runtime status
- confidence is not numeric
- limitation/reason list
- evidence refs

No hidden weighted score.

---

# 27. Fixture result evidence

Separate from capability support.

Each fixture final result:

- MATCH
- MISMATCH
- INCOMPLETE
- UNSTABLE
- UNSUPPORTED_REQUIRED_FIELD
- ABORTED
- STALE

A fixture cannot be MATCH if required role binding is ambiguous.

A fixture cannot be MATCH if an unexpected canonical object appears/disappears.

---

# 28. Finding severity for TASK-020 run operations

Operational findings:

## RUN_BLOCKER

Examples:

- wrong registered project;
- RuntimeProfile changed;
- project generation changed;
- canonical package digest mismatch;
- fixture identity ambiguity;
- operator edit during S1;
- evidence root collision/corruption.

Stop qualifying captures.

## FIXTURE_BLOCKER

Examples:

- F2 track state mismatch;
- F3 missing subtitle;
- F1 repeated-media ambiguity.

Stop qualification for that fixture; other fixtures may continue only if environment/currentness
remains valid.

## FIELD_BLOCKER

Example:

- one optional/isolated candidate read unavailable where the fixture can remain semantically complete
  without it under the approved matrix.

Continue while preserving the field result.

No blocker is automatically repaired.

---

# 29. Runtime drift handling

Examples of drift:

- same native ID changes on unchanged current timeline;
- track count changes;
- item order changes and cannot be explained by approved ordering normalization;
- source frame changes;
- marker key representation changes;
- same call alternates None/object;
- capture fence changes.

Response:

1. persist raw evidence;
2. mark affected pair;
3. classify field/scope SUPPORTED_UNSTABLE or UNKNOWN as appropriate;
4. continue only for diagnostics if safe;
5. do not retry until stable;
6. include drift in final report.

---

# 30. Evidence completeness gate

A TASK-020 runtime report cannot claim a fixture qualified unless all required files/evidence refs
exist.

At minimum:

- run metadata
- RuntimeProfile
- environment preflight
- installed API discovery evidence
- fixture binding
- 10 pair results for every required S1 context
- raw + semantic captures for each pair
- all findings
- F4 S2 three round trips
- final per-field classification
- final fixture classification
- evidence checksum

Missing evidence is INCOMPLETE, not pass.

---

# 31. Basic TASK-020 completion gate

Basic runtime completion requires:

1. exact RuntimeProfile frozen;
2. exact registered disposable environment;
3. approved canonical TASK-022 package;
4. F0 core project/timeline/item/media/source reads sufficient for required snapshot;
5. F1 repeated-media placement distinction;
6. F2 required track-state result, or explicit Chat-reviewed profile narrowing if genuinely
   unsupported;
7. F3 marker/subtitle result according to ADR-033 completion policy;
8. F4 identity-boundary evidence;
9. required S1 contexts complete with 10/10 double-capture equality;
10. F4 three S2 round trips complete;
11. no silent retry/erasure of failed evidence;
12. read-only adapter exposes no mutation/generic execute/eval/repair path;
13. no native ID upgraded to PERSISTENT_VERIFIED from S1/S2 only;
14. final report and evidence checksum produced.

S3/S4 are not required unless their lifetime claims are requested.

---

# 32. TASK-020 runtime report template

`TASK_020_RUNTIME_REPORT.md` should include:

## Run identity
- run ID
- adapter commit
- RuntimeProfile
- project/environment generation
- canonical package digest

## Operator preflight
- pass/fail
- deviations

## Installed API discovery
- Tier A summary
- Tier B diagnostics
- Tier C unresolved

## Fixture results
- F0
- F1
- F2
- F3
- F4-A
- F4-B

## S1 results
- 10 pair table per fixture context
- failed pair references
- drift summary

## S2 results
- 3 round-trip table
- identity observation summary

## Capability matrix
- RV-001..RV-044 final statuses

## Identity claims
- readable
- same-context stable
- switch-stable
- project-reopen
- cross-session
- explicitly unclaimed boundaries

## Findings
- blockers
- unstable observations
- UNKNOWNs
- unsupported fields

## Completion gate
- PASS / HOLD

## Explicit non-claims
- no destructive capability verified
- no mutation performed
- no PERSISTENT_VERIFIED unless S3/S4 and separate contract requirements were actually met
- no production-project safety inferred

---

# 33. Suggested runner UX

A future TASK-020 CLI may expose commands similar to:

```text
task020 probe preflight
task020 probe discover-api
task020 probe s1 --fixture F0_BASIC
task020 probe s1 --fixture F1_REPEATED_MEDIA
task020 probe s1 --fixture F2_TRACK_STATE
task020 probe s1 --fixture F3_MARKER_SUBTITLE
task020 probe s1 --fixture F4_IDENTITY_BOUNDARY --timeline A
task020 probe s1 --fixture F4_IDENTITY_BOUNDARY --timeline B
task020 probe s2 --fixture F4_IDENTITY_BOUNDARY
task020 probe finalize
```

Names are illustrative, not an authorization to implement a generic command executor.

Runner should display:

- current run ID;
- exact current fixture;
- pair/round-trip number;
- whether human interaction is currently forbidden;
- current blocker state.

---

# 34. Attention / operator-time principle

TASK-020 validation is engineering qualification, not normal editor workflow.

The runner should minimize active operator work by:

- automatically issuing bounded reads;
- automatically performing A/B captures once the correct fixture is selected;
- automatically comparing semantic snapshots;
- automatically writing evidence;
- batching results.

The operator should not manually transcribe API values.

F4 switching may be manual until an approved non-mutating/current-context controller exists.

---

# 35. Security and safety boundary

- no arbitrary script text;
- no eval/exec;
- no shell commands from user text;
- no mutation fallback;
- no production project;
- no hidden repair;
- no silently expanded observation scope;
- no network requirement during a qualifying capture;
- no automatic upload of project/media/raw evidence.

Evidence storage remains local unless separately approved.

---

# 36. Current version note

This runbook was prepared against the repository's Resolve 21.x architecture assumptions and the
current Blackmagic support baseline available on 2026-10-07.

Actual validation must record the exact installed Resolve product/version/build.

If the installed runtime is not the expected profile:

- do not rewrite the runbook;
- create a different RuntimeProfile-bound validation run;
- compare evidence explicitly.

---

# 37. Final principle

> A runtime qualification run is successful because the same exact read-only observation survives a
> controlled, fully recorded protocol — not because the API returned something that looked plausible
> once.
