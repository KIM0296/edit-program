# TASK-009 — Observation Evidence & Producer Provenance Foundation

Status: **Prepared for Codex; implementation not started**

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
