# ADR-043 — Conversational Editing Interface Invariant

Status: User-directed product/architecture baseline, 2026-10-08.
Repository recording is not a new runtime qualification or execution authorization.

1. Studio and Free are one conversational editing product.
2. Users use the same natural-language Chat editing interface on both editions.
3. Edition differences are restricted to verified capability, transport, connection/startup UX,
   and execution availability.
4. Edition-specific Chat command languages or editing semantics are forbidden.
5. Shared Domain/IR/ExpectedDiff/Safety/Authority/Postflight semantics cannot fork.
6. Free must still understand, plan and explain a request when execution is unavailable, provided
   sufficient evidence exists and the corresponding shared planning contract permits it.
7. Missing facts stay UNKNOWN/UNSUPPORTED. They are never inferred merely to preserve UX.
8. A Free limitation cannot remove a verified Studio capability.
9. Free findings may strengthen shared contracts/tests, but cannot define Studio's capability ceiling.
10. UI automation cannot fabricate native capability or semantic parity evidence.
11. Human Edit Wins, Preserve Editability and Resolve-is-Source-of-Truth remain mandatory.
12. LLM output remains semantic IR, not arbitrary Resolve commands or scripts.

ADR-041 defines the transport boundary; ADR-042 defines semantic parity; ADR-043 fixes the user-facing
conversational contract across that boundary. There is no known conflict. A reviewed, fixed diagnostic
probe is not a product interface for generated scripts or generic remote invocation.

Read/reasoning readiness is not execution capability, Safety PASS, approval or authority. A request may
be explained as blocked when required evidence is absent. Do not invent a plan to claim UX parity.
No shared Core changes, UI implementation, persistence or IPC follow from recording this document.
