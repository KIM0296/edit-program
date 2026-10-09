# TASK-023 — Resolve Free In-Process Bridge Feasibility

Status: **AUTHORIZED — Free track first task**

Basis:

- Resolve Edition / Transport Split v1
- ADR-006 LLM Emits IR Only
- ADR-022 Read-only Resolve Snapshot
- ADR-033/038 runtime evidence principles
- ADR-039 environment authenticity principles
- approved TASK-022 canonical package remains unchanged

## Purpose

Determine whether the exact installed DaVinci Resolve Free 21.1.1 runtime can provide a safe,
non-mutating in-process scripting path suitable for a future Free-edition transport.

This is a feasibility task, not a production bridge.

## Phase F0 — Lua canary

Create/install a minimal Lua script that runs **inside Resolve** and performs read-only observations.

It may read only:

- live Resolve root availability
- product name/version/version string where exposed
- ProjectManager availability
- current database/library descriptor where exposed
- current Project availability/name/ID where exposed
- current Timeline availability/name/ID where exposed

It must not:

- create/delete/rename projects/timelines/tracks
- import media
- move/trim/delete/split items
- set markers/subtitles
- change preferences
- call arbitrary code
- open a listener
- write project state
- implement generic remote invocation

Console output is sufficient for the first canary.

## Phase F1 — In-process Tier-A read surface

Only if F0 proves a live root, inspect whether the current Free runtime exposes the same read
candidates needed by TASK-020.

Record each candidate as:

- AVAILABLE_TYPED
- AVAILABLE_AMBIGUOUS
- UNAVAILABLE
- UNKNOWN

Do not claim stability from one read.

## Phase F2 — Persistence feasibility

Only if F0/F1 pass, test whether a read-only Lua script can remain alive for one Resolve session
without blocking normal UI.

No networking yet.

Possible result:

- PERSISTENT_FEASIBLE
- ONE_SHOT_ONLY
- BLOCKING_OR_UNSAFE
- UNKNOWN

## Phase F3 — Local transport feasibility

Only after Chat review of F0–F2.

Future candidate transports:

- authenticated loopback socket
- bounded filesystem mailbox

Do not implement generic object proxying.

The external side must send typed allowlisted messages, not method names/arbitrary args.

## Required first canary output

At minimum:

```text
FREE_CANARY|ROOT|CONNECTED|NONE|ERROR
FREE_CANARY|PRODUCT|...
FREE_CANARY|VERSION_STRING|...
FREE_CANARY|PROJECT_MANAGER|OK|NONE
FREE_CANARY|DATABASE|...
FREE_CANARY|PROJECT|...
FREE_CANARY|TIMELINE|...
```

Errors are retained and do not fall back to guessed values.

## Runtime under test

Current observed installation:

- DaVinci Resolve Free
- installed binary file version previously observed as 21.1.1.10
- external Python `scriptapp("Resolve")` returns None

The live in-process product/build must still be observed rather than copied from the file version.

## Acceptance

TASK-023 feasibility is positive only if the exact Free runtime itself supplies the live in-process
objects/reads.

A community report, installed stub, or Studio behavior is not enough.

## Outcomes

### FREE_BRIDGE_FEASIBLE

In-process read-only access works and a future typed transport is credible.

### FREE_ONE_SHOT_FEASIBLE

In-process scripts work but persistent bridge operation is unsuitable.

### FREE_BRIDGE_NOT_AVAILABLE

The exact Free runtime does not expose a usable in-process scripting context.

### HOLD

The test cannot distinguish runtime restriction from installation/configuration failure.

## Completion report

Write:

`docs/reports/TASK_023_FREE_BRIDGE_FEASIBILITY.md`

Include:

- exact Resolve observed product/version
- script language/path used
- Workspace > Scripts visibility
- canary output
- read capability observations
- persistence result if tested
- explicit non-mutation statement
- limitations
- recommendation

Do not start a mutation bridge automatically.

## Final principle

> First prove that Free Resolve gives us a live, read-only in-process handle. Only then design the
> transport around it.
