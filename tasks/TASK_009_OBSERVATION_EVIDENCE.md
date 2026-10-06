# TASK-009 — Observation Evidence & Producer Provenance Foundation

Status: **Implemented; validation and Chat Gate tracked in docs/reports/TASK_009_COMPLETION.md**

Basis:
- ADR-018 Pause / Dialogue Editing v1
- ADR-019 Evaluation Data Contract v1
- ADR-020 Observation Evidence & Producer Provenance Contract v1
- TASK-007 Pause Candidate baseline
- TASK-008 Evaluation foundation

## Purpose

Implement the immutable evidence/provenance layer between future media-intelligence producers and
the existing PauseObservation domain.

No actual media intelligence is implemented.

## Required implementation

Create pure domain support for:

- ProducerRef / producer kinds
- EvidenceAssertion: PRESENT / ABSENT / UNKNOWN
- EvidenceStrength: STRONG / MODERATE / WEAK / UNKNOWN
- typed EvidenceKind and payloads
- snapshot/range EvidenceBinding
- immutable EvidenceRecord
- immutable EvidenceBundle
- conflict representation/detection
- PreparationStatus: READY / REVIEW_REQUIRED / STALE / UNSUPPORTED
- machine-readable PreparationReason
- pure conservative preparation into existing PauseObservation when safe

## Mandatory semantics

1. Missing evidence is represented by absence of a record; it is never inferred as ABSENT.
2. EvidenceStrength is a separate type from PauseCandidate Confidence.
3. Evidence is bound to timeline ID, base version, placement identity and observed range.
4. Mixed timeline/version/object evidence cannot become one READY observation.
5. No silent stale rebase.
6. No latest-wins or hidden producer priority.
7. Positive semantic cue conflicts remain visible and conservatively block READY when required.
8. ABSENT does not create an opposite positive cue.
9. Silence/duration alone never creates dead-air meaning.
10. TAKE_GAP boundary alone never creates failed-take meaning.
11. v1 supports one aligned placement; cross-clip/multi-placement preparation is not READY.
12. Local reference, if used for TIGHTEN preparation, must be positive and shorter than the pause.
13. Preparation/routing is not apply/approval/authority permission.
14. Existing TASK-007 classifier, authority and executor must not be called as side effects.

## Suggested tests

At minimum prove:

- immutable records and defensive tuple copying
- producer/version required
- assertion/strength typed separately from decision confidence
- missing != ABSENT != UNKNOWN
- duplicate evidence IDs reject
- mismatched timeline/version/object evidence rejects or returns non-READY
- stale base version produces STALE under explicit current-version validation
- record ranges outside declared context reject
- positive cue mapping to PauseSignal is explicit
- ABSENT/UNKNOWN/missing cues do not become positive signals
- emotional + dead-air evidence remains conflict/review
- contradictory boundary/band/content/reference values do not latest-win
- duration/silence alone cannot create REMOVE evidence
- TAKE_GAP alone cannot create failed-take cue
- unsafe/missing local reference cannot synthesize a target
- cross-placement/cross-clip input is non-READY
- repeated same evidence produces identical preparation result
- input evidence remains unchanged after derivation
- no Pause classifier / authority / safety preflight / FakeTimeline.apply invocation
- TASK-001..008 regression remains green

## Delivery

1. Start from latest main.
2. Commit this spec before implementation.
3. Red-first tests.
4. Implement only the pure evidence foundation.
5. Update DECISIONS/limitations/test matrix.
6. Run full pytest, Ruff, strict mypy, Python 3.11 CI.
7. Write docs/reports/TASK_009_COMPLETION.md.
8. Open PR and request Chat Gate Review.
9. Do not merge or start TASK-010 automatically.

## Explicitly out of scope

No VAD/STT/Whisper/diarization/prosody/LLM/media decode/Resolve extraction/native FPS mapping,
cross-clip rebinding, producer ranking, numerical calibration, database, telemetry, UI, training,
personalization or actual timeline editing.

## TASK-009 implementation notes (before code)

`evidence.py` will expose frozen provenance/binding/record/bundle values and a pure
`prepare_observation(bundle, current_snapshot)` function. The existing immutable
snapshot supplies only already-aligned fake placement ranges and current version;
no source conversion, adapter or snapshot resolver is called. A target and its
context must fit one concrete fragment of the named placement.

Payloads reuse typed pause band/boundary/content enums, a positive integer local
reference value, and a presence marker for kinds whose meaning is already typed.
Bundle construction rejects duplicate IDs, mixed bindings and out-of-context ranges.
Preparation retains the raw bundle and evidence IDs in diagnostics. Different
positive values, positive/negative contradictions and preserve/removal conflicts
block READY, regardless of order, strength or producer. Unknown assertions are
reviewed conservatively. Missing required boundary/band/content values require
review; missing optional cues remain missing and local reference stays None.
Only explicitly spoken content is supported. Invalid local targets are never repaired.

Evidence contract version support is explicit (`v1`); unknown or mixed contracts
remain representable but prepare as UNSUPPORTED. These API details introduce no
producer trust/strength policy, native mapping or editing authority. OPEN-009 and
OPEN-011 remain unresolved for real producers and native snapshot correspondence.

Submission note: newer main f229576 introduced accepted ADR-021 during TASK-009.
OPEN-011 is now resolved for the v1 contract; the preceding notes retain their original
pre-implementation context. TASK-009 still accepts only already-aligned ranges and does
not implement the separately prepared TASK-010.
