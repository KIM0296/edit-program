# Observation Evidence & Producer Provenance Contract v1

Status: **Accepted Chat Product/Architecture baseline**

## Purpose

Define a safe, inspectable language between future media-intelligence producers and Pause
Intelligence without implementing any VAD, STT, diarization, prosody, semantic model or Resolve media
extraction.

The contract answers:

1. what was observed,
2. by which producer/version,
3. against which timeline snapshot/object/range,
4. whether the claim is positive, negative or unknown,
5. whether multiple claims conflict,
6. whether enough evidence exists to prepare a PauseObservation safely.

Evidence is descriptive. It never grants edit/apply authority.

## Architectural position

```text
Raw Audio / Transcript / Timeline
            ↓
future evidence producers
(VAD / STT / Diarization / Prosody / Semantic / Human)
            ↓
Observation Evidence Contract
            ↓
Evidence Bundle / Preparation Result
            ↓
PauseObservation
            ↓
TASK-007 deterministic decision baseline
            ↓
Candidate / Authority / Safety layers
```

TASK-009 implements only the contract layer and pure validation/preparation.

## Core principle: Observation confidence != Editorial confidence

Producer evidence strength and PauseCandidate confidence are different concepts and different types.

- Evidence strength asks: "How strongly does this producer support this observation?"
- Candidate confidence asks: "How confidently may the editing system make this editorial decision?"

There is no implicit mapping such as STRONG evidence => HIGH editorial confidence.

## Producer provenance

Every evidence record carries a typed producer reference with at least:

- producer_kind
- producer_name
- producer_version
- evidence_contract_version
- optional producer_config_ref

Initial producer kinds:

- HUMAN_SUPPLIED
- VAD
- STT
- DIARIZATION
- PROSODY
- SEMANTIC
- TIMELINE_ADAPTER
- RULE

Producer identity/version is provenance only. It is not authority, approval or trust bypass.

## Snapshot binding

Every evidence record is bound to the snapshot it observed:

- timeline_id
- base_version
- object_id / placement identity
- observed_range

v1 preparation supports one aligned placement only.

Evidence from different timeline IDs, base versions or placement identities must not be silently
merged into one executable PauseObservation.

If timeline state has advanced, old evidence is stale evidence. A future mapping/revalidation layer
may refresh it; TASK-009 must not silently rebase it.

Production Resolve persistent identity remains governed by OPEN-001. Native time/frame mapping is
deferred to the Native Time & Snapshot Mapping contract.

## Evidence vocabulary

The contract supports typed evidence kinds sufficient to express future pause producers without
requiring their implementation.

Initial kinds:

### Timing / speech structure
- SILENCE_REGION
- SPEECH_REGION
- TRANSCRIPT_BOUNDARY
- QUESTION_ANSWER_BOUNDARY
- SPEAKER_CHANGE
- SPEAKER_OVERLAP

### Pause meaning / texture cues
- NATURAL_BREATH_CUE
- HESITATION_CUE
- THINKING_CUE
- EMOTIONAL_CUE
- RECORDING_DEAD_AIR_CUE
- FAILED_TAKE_GAP_CUE

### Observation preparation values
- RELATIVE_PAUSE_BAND
- LOCAL_PAUSE_REFERENCE
- CONTENT_MODE

The exact algorithm that produces any of these remains outside this contract.

## Evidence assertion: Present, Absent, Unknown, Missing

A record may explicitly assert:

- PRESENT: producer positively observed the evidence.
- ABSENT: producer explicitly evaluated the feature and claims it is absent.
- UNKNOWN: producer evaluated but cannot make a reliable positive/negative claim.

**Missing is not an enum value.**

Missing means no evidence record exists for that producer/kind/scope.

Therefore:

```text
Missing != ABSENT
Unknown != ABSENT
Missing != Unknown
```

No consumer may turn missing evidence into a negative claim.

## Evidence strength

Each explicit record may carry:

- STRONG
- MODERATE
- WEAK
- UNKNOWN

This is an evidence-strength label, not a calibrated probability and not PauseCandidate confidence.

Numeric confidence calibration is deferred until real producer data exists.

## Typed payloads

Evidence values must be structurally typed.

Examples:

- boundary evidence carries a PauseBoundaryKind-compatible boundary value
- relative-pause evidence carries RelativePauseBand
- local-reference evidence carries a positive integer frame count
- content-mode evidence carries ContentMode
- cue evidence identifies a specific cue/signal

Do not use arbitrary free-form dictionaries as the authoritative contract.

Human-readable notes may exist only as non-authoritative metadata.

## Evidence range rules

All v1 internal ranges continue to use integer half-open [start, end) FrameRange values.

The contract does **not** decide how native Resolve timecode, drop-frame, source FPS or mixed FPS are
converted into those values. That belongs to the next Native Time & Snapshot Mapping contract.

TASK-009 may only validate already-aligned internal ranges.

## EvidenceBundle

An immutable EvidenceBundle binds:

- bundle_id
- timeline_id
- base_version
- target_object_id
- target_pause_range
- optional context_range
- evidence records
- evidence_contract_version

All included evidence must belong to the same timeline/version/placement in v1.

A record may observe the target pause itself or its declared local context, but must not reference an
unrelated range.

Duplicate evidence IDs reject.

Bundles do not select "the winning producer".

## Conflict preservation

Conflicting evidence must remain visible.

Examples:

- EMOTIONAL_CUE PRESENT + RECORDING_DEAD_AIR_CUE PRESENT
- QUESTION_ANSWER boundary + FAILED_TAKE_GAP cue
- two PRESENT boundary values that are mutually exclusive
- two different PRESENT relative-pause bands
- incompatible local-reference values
- incompatible content-mode claims

v1 must not resolve these conflicts through hidden producer priority, latest-wins behavior, or
confidence arithmetic.

A conflict is represented explicitly in the preparation result and routed conservatively.

## Positive and negative evidence

ABSENT evidence may be retained for audit/evaluation but must not be converted into the opposite
positive cue.

For example:

```text
EMOTIONAL_CUE = ABSENT
```

does not imply:

```text
RECORDING_DEAD_AIR_CUE = PRESENT
```

Likewise SILENCE_REGION PRESENT does not imply dead air.

Duration/silence remains evidence, never editorial meaning by itself.

## Preparation result

Pure preparation consumes one EvidenceBundle and returns a result such as:

- READY
- REVIEW_REQUIRED
- STALE
- UNSUPPORTED

If READY, it may carry a prepared PauseObservation.

If not READY, it carries machine-readable preparation reasons and no proactive executable
observation.

Preparation is not approval, candidate selection, execution permission or Main mutation.

## Conservative preparation rules v1

A bundle may be READY only when:

1. timeline ID/version/object binding is internally consistent,
2. target pause range is valid and contained in the supported placement/context,
3. content mode is supported spoken content,
4. required typed values needed for the selected observation are non-conflicting,
5. any proactive TIGHTEN target is a positive local reference shorter than the original pause,
6. no unsupported cross-placement/cross-clip mapping is required,
7. no unresolved producer conflict makes the semantic observation unsafe.

Observed positive cue mapping may preserve multiple simultaneous cues; meaningful/removal conflicts
must remain conflicts rather than being discarded.

Unknown or missing evidence must not be invented.

## Mapping to PauseObservation

TASK-009 may define a narrow, explicit mapping from supported evidence to the existing
PauseObservation fields.

Examples of valid direction:

- PRESENT EMOTIONAL_CUE -> PauseSignal.EMOTIONAL
- PRESENT THINKING_CUE -> PauseSignal.THINKING
- PRESENT NATURAL_BREATH_CUE -> PauseSignal.NATURAL_BREATH
- PRESENT HESITATION_CUE -> PauseSignal.HESITATION
- PRESENT RECORDING_DEAD_AIR_CUE -> PauseSignal.RECORDING_DEAD_AIR
- PRESENT FAILED_TAKE_GAP_CUE -> PauseSignal.FAILED_TAKE_GAP

But:

- ABSENT does not create an opposite signal
- UNKNOWN does not create a positive signal
- missing does not create a positive or negative signal
- conflicting authoritative values do not use latest-wins
- silence duration alone does not create RECORDING_DEAD_AIR
- TAKE_GAP boundary alone does not create FAILED_TAKE_GAP

Boundary/band/content/reference mapping must be typed and explicit.

## Cross-clip and multi-speaker behavior

v1 does not merge evidence across multiple placement identities into one READY PauseObservation.

If a candidate pause crosses clip boundaries, depends on unresolved source/timeline mapping, or has
multi-speaker overlap requiring semantic interpretation, preparation returns REVIEW_REQUIRED or
UNSUPPORTED.

Crosstalk may be represented as evidence, but its editorial interpretation is not implemented here.

## Staleness and Human Priority

Evidence belongs to the timeline snapshot it observed.

Human edits after evidence creation take priority.

TASK-009 must not silently transfer evidence from an old base_version to a new timeline version.
Recomputation/revalidation is a later coordinator responsibility.

## Immutability and reproducibility

Evidence records, producer references, bundles and preparation results are immutable values.

Re-running the same pure preparation over identical evidence yields the same result.

Updating a producer result creates new evidence values rather than mutating historical evidence.

## Privacy / media boundary

The evidence contract must not require raw video/audio bytes, full transcripts, filenames, project
names or user identity.

Opaque references and typed evidence are sufficient for the domain contract.

This does not prohibit future media-processing components from handling media; it only keeps raw media
outside this core evidence value layer.

## TASK-009 implementation boundary

Implement:

- immutable ProducerRef
- immutable EvidenceBinding / EvidenceRecord
- explicit EvidenceAssertion
- explicit EvidenceStrength
- typed evidence kinds/payloads
- immutable EvidenceBundle
- structural binding/range validation
- conflict detection
- pure conservative EvidenceBundle -> preparation result
- narrow explicit mapping to existing PauseObservation where safely supported
- deterministic/machine-readable preparation reasons

Do not implement:

- VAD
- Whisper/STT
- diarization
- prosody/emotion models
- LLM semantic classification
- audio/video decoding
- Resolve media extraction
- native timecode/FPS conversion
- mixed-FPS mapping
- cross-clip rebinding
- automatic producer trust ranking
- numeric confidence calibration
- local pacing algorithm
- target generation
- actual timeline mutation
- Candidate Authority transitions
- telemetry/DB/network
- UI
- model training/personalization

## Deferred decisions

The following remain open for later contracts/real data:

- production native timeline/source time mapping
- drop-frame and mixed-FPS conversion
- cross-placement pause representation
- producer-specific feature algorithms
- producer calibration / trust policies
- transcript/prosody schemas beyond the minimal typed evidence contract
- local pacing-window algorithm
- exact TIGHTEN target generation
- multi-speaker/crosstalk editorial policy

## Safety summary

> Evidence tells the system what was observed. It does not tell the system what it is allowed to
> edit.

> Missing evidence is not negative evidence.

> Conflicting evidence is preserved, not silently resolved.

> Evidence from a stale or different timeline snapshot is not silently rebased.
