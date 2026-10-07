# TASK-020 Qualification Campaign Aggregation Contract v1

Status: **ACCEPTED — Chat Product/Architecture baseline**

## Purpose

Define how TASK-020 combines independently sealed, project-generation-bound runtime validation runs
into one overall F0–F4 qualification campaign without weakening ADR-038's one-run/one-project-generation
binding.

This contract resolves OPEN-023.

## Core rule

> Aggregate conclusions may reference sealed runs. They may never splice their raw observations into
> a fictitious shared project generation.

## Required campaign membership

One complete v1 TASK-020 campaign contains exactly five sealed validation runs:

1. one F0_BASIC run;
2. one F1_REPEATED_MEDIA run;
3. one F2_TRACK_STATE run;
4. one F3_MARKER_SUBTITLE run;
5. one F4_IDENTITY_BOUNDARY run containing both F4-A and F4-B S1 contexts and all three S2 A→B→A
   round trips.

Thus the campaign covers six S1 contexts while preserving five independent project-generation
bindings.

F0–F3 may never be combined into the same validation_run_id merely to satisfy campaign counters.

## Campaign identity

A QualificationCampaign binds at least:

- campaign_ref
- campaign_contract_version
- exact adapter revision
- exact ReadProfile / RuntimeProfile compatibility signature
- installed stub digest
- normalization version
- canonical package digest
- fixture catalog version
- runtime policy version
- five sealed run refs
- five evidence checksum refs/digests
- campaign findings
- derivation version

Project/environment refs and project generations remain properties of the member runs and are not
rewritten into one synthetic campaign generation.

## Runtime profile compatibility

Every member run must use the same exact:

- Resolve product/version/version string;
- adapter revision;
- installed stub digest;
- architecture where required by ReadProfile;
- normalization version;
- canonical package digest;
- fixture catalog version;
- ADR-033/038 runtime policy contract.

If these differ, the campaign is INCOMPATIBLE/HOLD.

The campaign may span more than one operator session, but this never creates a cross-session identity
claim. Identity lifetime claims remain scoped to the exact member run that produced them.

## Required context ownership

- F0 run contains only F0.
- F1 run contains only F1.
- F2 run contains only F2.
- F3 run contains only F3.
- F4 run contains exactly F4-A and F4-B.

Duplicate ownership of one required context is ambiguous and blocks campaign completion.

Missing ownership of one required context is INCOMPLETE/HOLD.

## Evidence preservation

The campaign stores references/digests to sealed run evidence.

It does not:

- copy captures into another run;
- renumber S1 pairs;
- merge project generations;
- combine 5 pairs from one run with 5 pairs from another;
- replace failed evidence with a later successful run under the same campaign without retaining both
  attempts explicitly;
- rewrite run-local RV results.

If a failed run is superseded by a new clean run, both runs remain historical evidence and the
campaign explicitly names which run is the selected qualifying member and why the older run is
non-selected. There is no latest-wins default.

## Context qualification requirement

For campaign completion:

- F0/F1/F2/F3 selected runs each contain one S1 series with exactly 10 pairs and that series qualifies;
- F4 selected run contains qualified F4-A and F4-B S1 series, each exactly 10 pairs;
- F4 selected run contains exactly three accepted S2 round trips;
- no selected run contains operator-interference or stale-binding blocker;
- every selected run evidence checksum verifies.

A campaign never turns an unqualified member run into a qualified one.

## RV aggregation

RV-001..044 campaign results are derived from the contributor contexts declared by
`docs/TASK_020_RUNTIME_VALIDATION_MATRIX.md`.

The contributor map is versioned with the campaign contract.

Examples:

- RV-004 uses F0;
- RV-019/020 use F2;
- RV-036..040 use F3;
- F4 identity-switch evidence contributes only where the matrix explicitly names F4/S2;
- RV-041 uses all required S1 contexts;
- RV-042 uses F0/F1/F3;
- RV-043 uses F1;
- RV-044 uses F0/F1/F3.

For a required contributor set, aggregate conservatively:

1. any SUPPORTED_UNSTABLE -> SUPPORTED_UNSTABLE;
2. otherwise any UNKNOWN -> UNKNOWN;
3. otherwise all SUPPORTED_STABLE -> SUPPORTED_STABLE;
4. otherwise all UNSUPPORTED -> UNSUPPORTED;
5. mixed SUPPORTED_STABLE / UNSUPPORTED -> UNKNOWN unless a later matrix revision explicitly defines
   that mixed applicability.

No majority vote, percentage or best-run selection.

## Capability vs fixture result

Campaign RV aggregation remains separate from fixture correctness.

A member run may show a capability as SUPPORTED_STABLE while its fixture is MISMATCH.

Such a member does not satisfy campaign fixture qualification.

## Identity aggregation

Identity claims are never broadened by campaign aggregation.

- S1/S2 identity evidence remains bound to the member run/project.
- F4 S2 may support same-project switch-stability only inside the F4 run.
- Campaign membership does not prove identity across F0/F1/F2/F3 projects.
- Campaign membership does not prove project reopen or cross-session persistence.
- S3/S4 remain separately evidenced and optional according to ADR-033/038.

## Campaign status

Suggested status vocabulary:

- COMPLETE
- HOLD_INCOMPLETE
- HOLD_INCOMPATIBLE
- HOLD_MEMBER_FAILED
- HOLD_EVIDENCE_INVALID

COMPLETE means all required project-bound protocols were executed and the selected member runs satisfy
their fixture qualification requirements.

COMPLETE does not mean every RV capability is supported. The campaign report still preserves
SUPPORTED_STABLE / SUPPORTED_UNSTABLE / UNSUPPORTED / UNKNOWN per RV case.

## Campaign evidence output

Recommended pure derived output:

```text
evidence/task020-campaign/<campaign_ref>/
├─ campaign.json
├─ member-runs.json
├─ capability-results.json
├─ fixture-results.json
├─ identity-results.json
├─ TASK_020_CAMPAIGN_REPORT.md
└─ evidence.sha256
```

The campaign evidence contains refs/digests and derived summaries, not copied raw capture files.

## Implementation boundary

The campaign aggregator is a pure evidence-layer component.

It may:

- load/verify sealed TASK-020 run evidence;
- validate campaign compatibility;
- validate required context coverage;
- derive conservative RV campaign statuses;
- write a derived report/checksum.

It must not:

- connect to Resolve;
- create or repair fixtures;
- mutate projects;
- rerun missing captures;
- change run-local evidence;
- infer native identity across projects.

## Retry/new-run policy

A member run that failed remains sealed evidence.

To try again:

- create a new validation_run_id for that project generation/session as required by ADR-038;
- execute the full required protocol;
- retain the old failed run;
- update the campaign selection explicitly.

Do not mutate or delete the failed run.

## OPEN-023 resolution

OPEN-023 is **RESOLVED FOR v1** by this contract.

Phase B can therefore execute F0/F1/F2/F3 as four independent runs plus one F4 run, then derive one
campaign report after all five selected runs are sealed.

## Final principle

> Campaign aggregation joins conclusions by reference, never native worlds by fiction.
