# Cross-Edition Semantic Parity Contract v1

Status: **ACCEPTED — Chat Product/Architecture Review, 2026-10-08.**
ADR: ADR-042. Extends ADR-041 without changing existing Safety or runtime qualification contracts.

## Product and boundary

One shared editing product serves both editions. Studio is the reference runtime; Free is a
compatibility runtime. These roles are product architecture, not claims that either installed runtime
has been qualified. Studio TASK-020 Phase A stays at checkpoint/studio-task020-phase-a-v1,
6025e944bae260359635fe41e216a8fc22533cd7; Phase B stays HOLD.

User request -> shared Editing Intelligence -> shared Universal Editing IR -> ExpectedDiff/Safety
-> Execution Plan -> Resolve Adapter -> edition-specific transport -> DaVinci Resolve.

1. Studio is the reference runtime.
2. Free is the compatibility runtime.
3. Core semantics are edition-independent.
4. A transport cannot change snapshot semantics.
5. The same native facts produce the same typed semantic observations.
6. The same snapshot and request produce the same semantic IR under the same shared contract.
7. The same IR and safety evidence produce the same Safety verdict.
8. A proven unsupported Free capability is explicitly UNSUPPORTED. Unproven support remains UNKNOWN.
9. A Free limitation never removes a verified Studio capability from the shared product.
10. UI automation cannot fabricate parity evidence or substitute for native observations.
11. Edition-specific implementation stays below the transport/capability-producer boundary.
12. A shared feature requires parity tests for both editions before claiming cross-edition support.

## Semantics that cannot fork

Pause/dialogue decisions, target identity and resolution, integer half-open FrameRange, relationship
semantics, topology, ExpectedDiff, Safety verdicts, candidate authority, human approval, postflight
verification, Human Edit Wins and Preserve Editability remain shared. Neither transport can weaken
protection, infer missing facts, silently rebase, round frame boundaries, repair a plan, normalize
A/V boundaries, or expand participants to accommodate its native behavior.

Differences in language, process boundary, startup UX and verified native capabilities are allowed.
They do not authorize a Free-only editing algorithm, Safety Core, IR, timeline model or authority rule.
Studio capability is also evidence-based; the edition label does not imply full support.

## Parity gate

Compare corresponding, explicitly bound native facts through both producers. Preserve raw provenance,
profile, identity lifetime, freshness and capability evidence separately from semantic values. Different
producer metadata is not a reason to alter editing meaning. Do not equate unrelated native identities,
ignore a missing field, or invent correspondence to make snapshots compare equal.

Required future test layers:

- Corresponding native facts -> equal typed semantic observations/snapshot.
- Equal snapshot + request + shared contract inputs -> equal semantic IR/ExpectedDiff.
- Equal IR + safety evidence -> equal Safety verdict and findings.
- Missing, ambiguous, stale or unsupported inputs retain their fail-closed meaning on both tracks.
- Unsupported Free capability blocks only the dependent Free feature; verified Studio support remains.

Mock parity validates code semantics; it does not prove native runtime support. Runtime claims require
exact-profile evidence from each edition. An unavailable comparison is NOT VERIFIED, never a parity
PASS. Fixture correspondence and test tolerances cannot be invented; existing exact-frame rules apply.

## Current execution order and non-claims

Record/review ADR-042 -> Free F0.1 BOOT/root diagnostic -> Free Tier-A reads -> Studio/Free snapshot
parity -> separately reviewed Free transport. Do not skip stages or implement IPC during F0.1.

Canary revision 3aff59cbddc4920b95665697bf7529cecd5c0f92 adds BOOT first, injected global resolve first,
and app:GetResolve() fallback. The old two menu attempts with no Console output remain INCONCLUSIVE.
The revised canary has not yet been executed under confirmed filters. Physical Escape stopped the UI
session during restart observation. No F0 PASS, Free support, persistence, IPC or mutation is claimed.

This document defines the gate; it does not implement parity runners, new transport, native mutation,
UI editing automation or capability downgrade policy. Future unresolved correspondence/normalization
questions must be recorded OPEN rather than resolved in edition-specific code.
