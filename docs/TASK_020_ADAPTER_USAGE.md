# TASK-020 read-only adapter operation

Implementation and runtime qualification are separate gates. No native support has been qualified.
Installed documentation is candidate evidence only. Use a fresh evidence directory for each attempt;
existing records are never overwritten. Do not use this adapter to create, repair, or activate fixtures.

## Diagnostic discovery

From the repository, with the installed external Python 3.11 interpreter:

```powershell
& 'C:\Users\hellj\AppData\Local\Programs\Python\Python311\python.exe' -m davinci_ai_editor.resolve_probe discover --evidence-root '<fresh evidence directory>'
```

This fixed entry point loads the installed Blackmagic scripting module. It performs only the reviewed
read allowlist. The shipped ResolvePython interpreter did not discover the editable repository package
in the actual attempt; no installed interpreter settings were changed. Resolve must already be running
with external scripting available. The adapter never launches Resolve or changes that preference.
A missing root is RUNTIME_UNAVAILABLE / HOLD, not evidence of unsupported individual getters.
Discovery creates no qualifying RuntimeProfile when the required typed observations are unavailable.

## Qualification inputs

`qualify --configuration <json> --evidence-root <fresh directory>` accepts only this closed schema:

- validation_run_id, adapter_revision (exact discovery source fingerprint)
- environment_ref, registry_ref, project_generation (positive integer), project_id
- library (exact typed current database descriptor), operator_session
- package_digest (approved canonical package digest)
- registration_evidence_ref, currentness_evidence_ref
- operator_preflight: seven explicit booleans named registered_disposable, not_production,
  approved_package_verified, no_concurrent_edit, no_repair, failed_pairs_retained, currentness_supplied
- fixtures: one F0/F1/F2/F3 context, or F4-A and F4-B in the same project/generation

Each fixture supplies context (the Context enum value), timeline_id, fixture_instance, assets,
coordinate_evidence_ref, required_project_settings, include_optional_audio, item_marker_host_id,
and required_risks. An asset supplies asset_role, media_unique_id, asset_sha256, package_digest and
an independent evidence_ref. These are prior external materialization/registration facts; the adapter
does not discover identity by filename or import media. `required_project_settings` is a JSON object
whose exact value types are compared. No default required risk is inferred absent; callers can require
CapabilityKind values, and unverified risks prevent fixture MATCH.

F3 item_marker_host_id explicitly identifies the catalog HOST placement. The adapter does not choose
video versus audio by first match. coordinate_evidence_ref must establish the installed native endpoint
conventions before the canonical integer half-open comparisons are usable. No numeric adjustment is
performed. A float-valued native frame remains UNKNOWN even if mathematically integral.

All config fields are data, not script/command/extra-flag fields. The runtime checks exact active project,
library, timeline and profile against the binding before fixture enumeration. Names and indices are
observed descriptive values, never persistent identity or registration proof.

## Execution and evidence

The operator selects a prepared registered fixture externally before S1 and confirms readiness once.
The runner immediately performs a nonqualifying fixture audit, then ten uninterrupted A/B pairs.
Do not play, scrub, select, toggle, repair, or switch during S1. Explicit operator interference is recorded
and blocks further captures; the consistency fence is not an atomic native snapshot or an omniscient
observer of human actions. Failed pairs remain at their original sequence numbers. Known fixture
mismatch stops the affected scope. Unexpected shape/value remains raw evidence plus UNKNOWN.

F4 S2 requires both S1 scopes first. The operator externally switches at each A-before/B/A-after stage
and supplies an action evidence reference. Three round trips are recorded. No SetCurrentTimeline call
exists. S2 must retain the same semantic and identity baseline as S1. S3/S4 remain NOT_EXECUTED.

Each capture records independent fresh root-path start/end reads, raw native types/values/errors and
separate normalized semantic values. The writer rejects overwritten/missing captures before sealing.
`evidence.sha256` detects byte changes; it is not a signature or native authenticity attestation.

The run report contains all 44 RV rows, all six 10-pair tables, three S2 rows, missing scopes, findings,
and explicit non-claims. A scope's capability stability and fixture correctness are different outputs.
The overall task gate remains HOLD: OPEN-023 requires a reviewed cross-project aggregate contract.
Do not splice independently bound projects into one validation_run_id to satisfy a report counter.

## Current runtime limit

Actual external bridge discovery returned no Resolve root. No qualifying fixture config has been
supplied. Thus no S1 pair, S2 round trip, SESSION_LOCAL_VERIFIED or PERSISTENT_VERIFIED claim exists.
The adapter provides no mutation, native attestation, Safety PASS, authorization, or materialization.
