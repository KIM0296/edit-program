# Resolve Edition / Transport Split v1

Status: **ACCEPTED — Chat Product/Architecture baseline**

## Purpose

Support both professional DaVinci Resolve Studio users and DaVinci Resolve Free users without
duplicating the editing intelligence, Safety Core or evidence model.

The product has one shared editing core and edition-specific Resolve transports.

## Product tracks

### Studio / Professional track

Transport:

```text
Assistant / local app
        ↓
External Python
        ↓
DaVinciResolveScript.scriptapp("Resolve")
        ↓
Resolve Studio
```

Current implementation checkpoint:

- PR #49 — TASK-020 Phase A read-only external adapter
- branch: `checkpoint/studio-task020-phase-a-v1`
- checkpoint commit: `6025e944bae260359635fe41e216a8fc22533cd7`
- Phase A: APPROVED
- Phase B: HOLD

This path is preserved for later continuation.

### Free track

Candidate transport:

```text
Assistant / local app
        ↓
bounded local transport
        ↓
small script running inside Resolve Free
        ↓
live in-process Resolve object
```

For Resolve Free 21.1.x, the first feasibility target is **Lua in-process scripting**.

Python in-process scripting may be tested later if the exact runtime exposes it, but is not assumed.

## Shared core

The following remain edition-independent:

- Domain model
- StableTarget / native mapping contracts
- Timeline Safety Core
- Relationship / topology rules
- Candidate authority
- Pause / dialogue intelligence
- Universal Editing IR
- ExpectedDiff
- Safety Preflight
- Transaction / postflight state model
- Probe evidence model
- F0–F4 canonical fixture definitions
- canonical package bytes/hashes
- evaluation contracts
- Human Edit Wins
- Preserve Editability
- Resolve is Source of Truth

Do not fork these into separate Studio and Free implementations.

## Edition-specific boundary

Only the native transport / capability producer may vary by edition.

Suggested interface:

```text
ResolveTransport
├─ StudioExternalTransport
└─ FreeInResolveTransport
```

Both transports must expose the same bounded typed observation/action contracts upward.

No transport may expose raw arbitrary script execution to the LLM or product layer.

## Capability negotiation

Edition name alone does not imply capability support.

Every runtime obtains an EditionRuntimeProfile containing at least:

- Resolve product name
- version/build where observable
- edition classification if observable/proven
- transport kind
- platform/architecture
- transport contract version
- observed read capabilities
- observed mutation capabilities
- limitations

A capability is enabled only from runtime evidence, not from assumed edition behavior.

## Free-track safety rules

1. No attempt to bypass licensed Studio-only features.
2. Use only APIs/contexts actually exposed to scripts running inside the Free runtime.
3. No UI automation fallback for core editing safety.
4. No arbitrary `Execute`, `eval`, generated Lua/Python or unrestricted remote method dispatch.
5. The first bridge is read-only.
6. External messages, if later introduced, use a typed allowlist.
7. Loopback/file IPC is a transport mechanism, never authority by itself.
8. The in-Resolve bridge must not hold an authoritative shadow timeline.
9. All existing Safety/ExpectedDiff/Postflight requirements remain.
10. A Free capability missing at runtime becomes UNSUPPORTED/UNKNOWN; the product does not fake parity.

## Free 21.1 feasibility uncertainty

External `scriptapp("Resolve")` returning no root is expected on the current Free installation.

Community evidence suggests:

- Free 21.0.x could run in-app scripts and obtain a live Resolve object.
- Reports for Free 21.1 indicate Python scripts may no longer appear in Workspace > Scripts while Lua
  remains available.

This is not treated as authoritative support.

The exact installed Free 21.1.1 runtime must be measured directly.

## UX target

Preferred Free experience:

```text
Launch Resolve
→ launch AI Bridge once from Workspace > Scripts
→ bridge remains available for that Resolve session
→ assistant can exchange typed local messages
```

Fallback, only if persistent bridge is impossible:

```text
Assistant prepares request
→ user runs bounded one-shot Resolve script
→ script reads/applies approved operation
→ result returned
```

The one-shot model is a compatibility tier, not equivalent UX to Studio.

## Non-goal

Do not rebuild the editor core twice.

Do not use mouse/keyboard/screen automation to simulate the missing API as the primary Free transport.

## Resume policy for Studio

Studio work can resume directly from:

`checkpoint/studio-task020-phase-a-v1`

Resume prerequisites:

- Resolve Studio available and running
- external scripting connection works
- dedicated probe-only Project Library
- prepared approved-package F0–F4 fixtures
- ADR-040 five-run campaign

No Free-track change may silently modify the preserved Studio checkpoint.

## Final principle

> One editor intelligence, one Safety Core, two transport adapters.
