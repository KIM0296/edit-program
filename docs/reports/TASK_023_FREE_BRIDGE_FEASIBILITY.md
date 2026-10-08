# F1 READ CAPABILITY REPORT

TASK-023 F1 — Free Conversational Editing Read Capability Map
Branch: feat/free-in-resolve-bridge-feasibility; base 9558c78639f23e97d6c5399cf80eb83faf440d73.
Spec-before-code commit: 792c265. Submission head is recorded in PR #50.
Status: probe/map implementation prepared; F1 runtime evidence NOT OBSERVED / HOLD.

## ADR-043

- recorded: YES, user-directed product/architecture baseline.
- files changed: DECISIONS.md; docs/CONVERSATIONAL_EDITING_INTERFACE_INVARIANT.md;
  IMPLEMENTATION_STATUS.md. F1 specification: tasks/TASK_023_F1_READ_CAPABILITY_MAP.md.
- conflicts with existing ADRs: none identified. ADR-041 transport boundary and ADR-042 semantic parity
  remain unchanged. Shared conversational intent is not a permission to infer missing facts or execute.

## F0 evidence status — operator-reported, separate from F1

The following is the user's observation summary, not an invented or agent-captured raw transcript:

- root: PASS; global resolve reportedly returned a live object; app:GetResolve() returned the same object.
- Console print path: works per operator.
- product/version: GetProductName -> DaVinci Resolve; GetVersionString -> 21.1.1.10.
  The product string alone is NOT native proof of Free edition. Edition label is operator-supplied.
- ProjectManager: available. Current database: table available; exact table entries NOT OBSERVED here.
- project: available, named PF_FREE_CANARY_v1. Exact project ID NOT OBSERVED in provided summary.
- timeline: available after opening Timeline 1; native start 108000, end 108087. GetUniqueId succeeded;
  exact returned ID NOT OBSERVED. No endpoint convention, duration or source correspondence is inferred.
- launcher: Workspace > Scripts canary menu execution remains INCONCLUSIVE / OPEN.
- F0 raw transcript: NOT SUPPLIED. Do not synthesize FREE_CANARY output from this prose summary.

## F1 probe

File: tools/free_bridge_probe/resolve_free_f1.lua.
Working-file SHA-256 at validation: 90ed7c352d28d45550cca96c6dee87921022df3e1968477897f957c0b093380b.
No installation or native execution was performed in this task. Existing F0 canary unchanged.

- domains tested: static source boundary only. Native F1 domains tested: NONE.
- prepared first reads: A runtime/context; B timeline ID/name/endpoints; C counts/type arguments;
  D item enumeration; E placement ID/name/start/end/duration; F source handle/IDs; minimal H/K context.
- AVAILABLE_TYPED: no native F1 observations yet.
- AVAILABLE_AMBIGUOUS: no native F1 observations yet.
- UNAVAILABLE: none demonstrated.
- UNKNOWN: all F1 candidates, including deferred G relationships, I retime, J protection and L freshness.
- raw F1 output: NOT OBSERVED. Probe has not run. Static tests do not establish Lua execution success.

The fixed allowlist contains 16 literal method names; every native call is an explicit read closure.
No object[method] dispatch or external method/argument input. Output distinguishes VALUE/NIL/UNAVAILABLE/
ERROR/UNKNOWN; lookup exceptions and call exceptions are preserved. Missing parents stay UNKNOWN.
Nil, false, empty strings and empty tables do not collapse. Raw number types remain Lua numbers;
coordinates/handles/collection semantics remain ambiguous. Diagnostic paths are not persistent IDs.
A completed read attempt is not complete semantic evidence, native stability, Safety PASS or approval.

P1 installed candidate stub SHA-256:
b91b53b86a946e1902789ea898eedf00cb7dd6107aba6f1276ca77fe508816ea.
Installed documentation/stub presence alone never establishes Free support.

## Conversational readiness

Full A-L field/provenance/semantic map: docs/FREE_CONVERSATIONAL_READ_CAPABILITY_MAP.md.

| Intent | Status | Blocking facts |
| --- | --- | --- |
| 두 번째 클립 앞의 침묵을 줄여줘 | BLOCKED_UNKNOWN | Scoped second placement, proven coordinates, actual pause vs gap, geometry/dependency/protection |
| B-roll과 겹치는 곳은 건드리지 마 | BLOCKED_UNKNOWN | Explicit B-roll roles, complete multi-track inventory, overlap coordinates/protection |
| 영상은 그대로 두고 대사 간격만 줄여줘 | BLOCKED_UNKNOWN | Dialogue targets, source ranges, A/V meaning, geometry and picture preservation |
| 속도 변경된 클립은 제외해 | BLOCKED_UNKNOWN | Reliable retime/speed observations and complete target scope |
| 이 클립이 어느 소스에서 온 건지 확인해 | BLOCKED_UNKNOWN | Concrete this-clip binding, observed MPI handle/IDs, identity lifetime limits |

These statuses concern evidence for concrete reasoning only. Requests retain shared meaning and may
be explained as blocked. No F0 context is stretched into item-level evidence. No unsupported verdict
is claimed without a direct observation; no Free-only Chat command language or planning path exists.

## Safety

- mutation performed: NO
- IPC/listener: NO
- persistence: NO
- shared Core changed: NO
- Studio checkpoint changed: NO; origin checkpoint ref still 6025e944bae260359635fe41e216a8fc22533cd7
- UI automation: NO
- full cross-edition parity: NOT VERIFIED; no parity runner
- stable native identities beyond observed scope: NOT CLAIMED
- Studio runtime qualification from Free observations: NOT CLAIMED

## Tests

- Red-first: 4 missing-probe failures, 1 spec test passed before implementation.
- New static tests: 5 passed. They inspect allowlist and literal native calls, forbidden surfaces,
  output vocabulary, failure distinctions, conservative mapping and no runtime-support claims.
- Python 3.11.9 full pytest: 1424 passed / 2 skipped / 0 failed, 111.13 seconds.
- Skips: Windows symlink privilege unavailable; opt-in intentional naive INV-001 demo.
- Ruff: PASS (src/tests/tools).
- strict mypy: PASS (33 existing Python source files). Mypy does NOT validate Lua.
- Lua interpreter/native F1 execution: NOT EXECUTED. No new interpreter installed.
- Existing shared semantic tests unchanged. No src/ files changed.

## Open questions — not resolved by assumption

1. Which directly evidenced in-process one-shot launch path will execute this reviewed file? Workspace
   menu remains INCONCLUSIVE. No UI/script-launch bypass is implemented.
2. What are actual Lua return types, collection key shapes and native handle representations?
3. What endpoint/fractional/source coordinate semantics can be proven for the exact runtime?
4. What placement/source identity lifetime, completeness and freshness can native evidence support?
5. What retime/relationship/lock/selection facts are directly readable in a later bounded set?
6. How will explicit target/B-roll/dialogue role bindings enter the existing shared contracts?

F1 runtime collection requires the operator's proven context; automating it here would require the
forbidden UI/transport path. Stop at the prepared probe and evidence map. Preserve complete actual
FREE_F1 output before classifying reads. Do not infer execution from menu visibility.
F2 persistence, F3 transport/IPC, mutation and parity runner remain NOT AUTHORIZED. No further work begun.
