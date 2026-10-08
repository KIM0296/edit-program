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
