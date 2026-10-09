# TASK-023 Free Resolve canary

This directory contains the first **read-only** DaVinci Resolve Free feasibility probe.

File:

- `resolve_free_canary.lua`

The script is intentionally tiny and performs no project mutation, file IO, network IO, eval or
generic remote invocation.

Before copying it anywhere, inspect the exact installed Resolve developer README / scripting folders.
Do not guess or modify the Resolve installation.

Run it from an in-Resolve scripting entry point such as Workspace > Scripts only when the current
Free runtime lists the Lua script.

Expected console prefix:

`FREE_CANARY|`

A missing root is evidence to preserve, not a reason to fall back to UI automation.

## F1 read-only capability map

`resolve_free_f1.lua` is a separate reviewed one-shot probe for the already-proven global `resolve`
context. It is not installed or executed automatically. F0 canary remains unchanged. Follow
`tasks/TASK_023_F1_READ_CAPABILITY_MAP.md` and retain complete FREE_F1 BOOT/OBS/END output.
A missing menu output remains inconclusive. No new launcher, transport, file sink or UI fallback exists.
Field meanings and current UNKNOWNs: `docs/FREE_CONVERSATIONAL_READ_CAPABILITY_MAP.md`.
