# TASK-023 F1 — Free Conversational Editing Read Capability Map

Status: AUTHORIZED read-only investigation. Specification recorded before probe implementation.
Base: 9558c78639f23e97d6c5399cf80eb83faf440d73. Branch: feat/free-in-resolve-bridge-feasibility.
Basis: ADR-041/042 APPROVED; ADR-043 user-directed baseline. Studio checkpoint is unchanged.

## Scope and evidence

F0 PASS is based on operator-provided Console observations, not a new agent capture. Live global resolve
and app:GetResolve() reportedly returned the same object; product DaVinci Resolve, version 21.1.1.10,
project PF_FREE_CANARY_v1, Timeline 1 range 108000..108087, timeline ID read succeeded but actual ID not
supplied. These are raw native endpoint numbers, not an inferred half-open range. Product name alone
is not proof of Free edition. Workspace menu launcher remains INCONCLUSIVE/OPEN.

Implement one reviewed one-shot Lua probe at tools/free_bridge_probe/resolve_free_f1.lua. It consumes
the already-proven global resolve context and prints only. It does not install itself, launch via UI,
write files, use IPC/network, persist, mutate, or offer generic method-name dispatch. Runtime execution
remains an operator step in the proven Lua context; menu visibility does not prove execution.

## First bounded surface

Runtime product/version; ProjectManager/current project/current timeline; project/timeline IDs;
timeline name/start/end; video/audio/subtitle track counts; per-track item lists; item ID/name/
start/end/duration; MediaPoolItem handle and unique/media IDs. No settings dump, relationships, retime,
selection, protection or other broad read expansion in this first revision.

Every call is a literal native read in a zero-input local closure, with a fixed declared allowlist.
The observation helper accepts closures, not a method-name lookup or external request. Installed stub
and README list these method candidates; this is not evidence of Free runtime support. Item getters
use explicit false subframePrecision. No frame coercion or source/timeline correspondence inference.

## Output contract v1

Prefix FREE_F1. BOOT/END delimit one invocation. Fixed schema columns per observation:
subject | method | outcome | raw_type | escaped_raw | capability | semantic_mapping.
Escaping percent, pipe, CR/LF and control bytes is lossless. Lua numbers use 17 significant digits;
raw type stays number (not Python int, not a converted FrameRange). nil, false, empty string and empty
table stay distinct. Tables are deterministically encoded by scalar key, including sparse lists;
opaque native handles are typed OPAQUE, never pointer-address identity. Their native IDs are separate
observations. No raw handle serialization can establish native correspondence.

Outcome vocabulary: VALUE / NIL / UNAVAILABLE / ERROR / UNKNOWN. Missing parent = UNKNOWN with
PARENT_NOT_OBSERVED, never UNAVAILABLE. Missing callable member = UNAVAILABLE. Lookup and call errors
are retained. A noncallable non-nil member is ambiguous, not proven absence. Errors are not mapped to
unsupported capability. F1 capability vocabulary: AVAILABLE_TYPED / AVAILABLE_AMBIGUOUS / UNAVAILABLE /
UNKNOWN. A supported shape is one-shot typed evidence, not stable runtime support.

All emitted semantic_mapping values are RAW_ONLY or NOT_ESTABLISHED. Scalar strings/valid counts may
be AVAILABLE_TYPED as raw shape only. Coordinates, object handles and collection correspondence stay
AVAILABLE_AMBIGUOUS. No identity lifetime, frame endpoint convention or intended object role is derived.
Traversal paths track/type/index/entry-key are capture-local diagnostic addresses, not persistent IDs,
chronological rank, semantic role or target resolution. Repeated-media placements are all retained.
Malformed enumeration keys produce diagnostics and block those reads, never a repaired list.

## Capability map and conversational readiness

Create docs/FREE_CONVERSATIONAL_READ_CAPABILITY_MAP.md covering A-L. Each row records intended editing
fact, method/property, raw form, provenance, identity/coordinate basis, mapping status, capability,
reason and intent-blocking impact. Separate planned reads, user-reported F0 and actual F1 output.
Unexecuted reads are UNKNOWN, not UNAVAILABLE. Deferred domains stay UNKNOWN. Reasoning vocabulary:
READY_TO_REASON / PARTIAL / BLOCKED_UNKNOWN / BLOCKED_UNSUPPORTED. None authorizes mutation.

Five initial intents: tighten silence before second clip; avoid B-roll overlap; keep picture and tighten
dialogue; exclude retimed clips; identify a clip's source. None is currently ready from F0 alone.
Do not equate temporal gaps with silence, track names with B-roll/dialogue, or linked flags with policy.

## Validation and stop conditions

Red-first static tests enforce literal allowlist/closures, no writes/network/dynamic code, exact output
vocabulary, nil/unknown/error separation, global-root-only F1 entry, diagnostic path non-identity,
no rounding or missing-value inference and no shared Core import/change. Preserve existing tests.
Full pytest, Ruff and strict mypy run. Static tests do not execute Lua or prove native runtime behavior.

Stop before any work requiring shared Core changes, edition-specific semantics, mutation, IPC/listener,
persistence, UI automation or invented correspondence. F2/F3 and parity runner are NOT AUTHORIZED.
Report at docs/reports/TASK_023_FREE_BRIDGE_FEASIBILITY.md, with F0/F1 evidence separated. Stop afterward.
