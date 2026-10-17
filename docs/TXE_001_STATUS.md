# TXE-001B — ASR Transcript Evidence Contract, Ingest and Frame Projection

Qualification: **CODE_COMPLETE / TEST_ONLY_SUPPORT**.

Branch `wip/txe-001-ingest`, based on `038f1cefc5c20e476e9aee50008aecf3fcfb618c`
(TXE-001A frame-domain `TranscriptWord` / `TranscriptSnapshot`).

## Purpose

Hold what an external ASR tool (faster-whisper, whisperX) *said*, on the tool's
own clock, in integer milliseconds, and project it onto source frames as a
TXE-001A `TranscriptSnapshot` without inventing or moving any timing.

## Files

- `src/davinci_ai_editor/transcript_evidence.py` (new, stdlib only)
- `tests/test_transcript_evidence.py` (new, hand-written dict fixtures)
- `docs/TXE_001_STATUS.md` (this file)

`transcript.py` is unchanged; its semantics are reused.

## Contracts

- `TranscriptProducerRef`: tool, version, model id/revision, alignment model,
  VAD method + config digest, requested/detected language (`"UNKNOWN"` allowed,
  empty forbidden), language probability (`Fraction | None`; UNKNOWN carries none).
- `AudioClock`: decoded sample rate, `resampled`, `downmixed`, `window_offset_ms`.
  Both tools resample/downmix to 16 kHz mono, so this is a different clock than
  the CSA-001 source decode and can never map EXACT to source frames.
- `EvidenceWordTiming` mirrors `WordTimingStatus` (asserted by a test).
- `ConfidenceKind` {WHISPER_WORD_PROB, CTC_MEAN_SCORE, NONE}; values in [0, 1] as
  `Fraction`, not comparable across kinds, not calibrated.
- `TranscriptEvidenceWord`: timed statuses need both `start_ms`/`end_ms`;
  MISSING/UNKNOWN need both None (a half timing is never kept or completed).
- `TranscriptEvidenceSegment`: `words_status` {NOT_REQUESTED, PRESENT,
  ALIGNMENT_FAILED}; non-PRESENT carries no words; ALIGNMENT_FAILED needs text.
- `CoverageSpan` {TRANSCRIBED, VAD_EXCLUDED, NOT_EVALUATED}. **VAD_EXCLUDED is
  not silence**; it only states the producer's VAD skipped the span.
- `TranscriptEvidence`: integer ms, start ≤ end, strictly increasing segment
  index, non-decreasing segment start, non-decreasing timed-word start, words
  within their segment ±`resolution_ms`, every timed value an exact multiple of
  `resolution_ms`, coverage ordered/nonoverlapping. `coverage=None` = not
  declared (never inferred); empty `segments` = evaluated empty result.

## Ingest (`ingest_faster_whisper`, `ingest_whisperx`)

Plain JSON-like mappings only; the tools are never imported. Floats go through
`Decimal(str(x))`; NaN/inf/bool/strings/negative values and non-multiples of the
resolution are refused with typed `TranscriptIngestError(code)` (`IngestErrorCode`).
Contract violations are wrapped as `CONTRACT_VIOLATION`. `producer.tool` must
match the ingest function (`PRODUCER_MISMATCH`). Payload language fills the
producer's `language_detected` only when the producer said `UNKNOWN` or the same
language (`LANGUAGE_MISMATCH` otherwise). Extra top-level keys are ignored; a
non-mapping top level or non-list `segments` is refused.

- faster-whisper: resolution 10 ms; words HEURISTIC_ADJUSTED with
  WHISPER_WORD_PROB; `words: null` → NOT_REQUESTED; `words: []` with text →
  ALIGNMENT_FAILED.
- whisperX: resolution 1 ms; no start/end → MISSING; start+end without score →
  INTERPOLATED; with score → ALIGNED (CTC_MEAN_SCORE); `words: []` with text →
  ALIGNMENT_FAILED; missing/null `words` → NOT_REQUESTED; segment index =
  position.

## Projection (`project_to_source_frames`)

Returns `TranscriptProjection(snapshot, diagnostics)`. Source time =
`clock.window_offset_ms + t`; `source_offset_frames` = source frame at source
time 0. Start → floor, end → ceil (ranges only widen). `producer_ref =
evidence_id`; word refs `w000001…`. `tolerance_frames` must be ≥
ceil(resolution_ms in frames), else `ValueError`.

Explicit rules, each with a `ProjectionDiagnostic` and never a moved boundary:

- zero/negative length after projection → MISSING, `source_range=None`
  (`ZERO_LENGTH_AFTER_PROJECTION`);
- projected timed words that overlap (e.g. touching ms boundaries at 30000/1001
  where ceil/floor cross, or overlapping producer timings) → every word of the
  overlapping group becomes UNKNOWN with `source_range=None`; the producer ms
  timings and projected frames are kept in `OVERLAP_AFTER_PROJECTION`;
- NOT_REQUESTED / ALIGNMENT_FAILED segments produce no words and one
  `SEGMENT_WORDS_UNAVAILABLE` diagnostic.

## What this does NOT authorize

No ASR execution, no tool import/installation, no real media, no network, no
Resolve. No PauseBoundaryKind/PauseSignal/ContentMode, no filler/hesitation/
breath semantics (OPEN-009 stays open). No claim that transcript boundaries are
exact, that VAD exclusion means silence, or that confidences are calibrated or
comparable. No editing decision consumes this evidence yet.

## Validation (run on this branch, Windows host, Python 3.11 venv, `PYTHONPATH=<worktree>/src`)

| Command | Result |
| --- | --- |
| `python -m pytest -q -p no:cacheprovider --basetemp=<scratch> tests/test_transcript_evidence.py` | 39 passed |
| `python -m pytest -q -p no:cacheprovider --basetemp=<scratch>` | 2160 passed, 2 skipped |
| `python -m ruff check src tests tools` | All checks passed |
| `python -m ruff format --check src/davinci_ai_editor/transcript_evidence.py tests/test_transcript_evidence.py` | 2 files already formatted |
| `python -m mypy` | Success: no issues found in 43 source files |
| `python -m mypy --strict --explicit-package-bases src/davinci_ai_editor/transcript_evidence.py tests/test_transcript_evidence.py` | Success: no issues found in 2 source files |
| `git diff --check` | clean |

## OSS provenance

No third-party code was copied; therefore no `licenses/` file is added. Tool
behavior was verified by reading (never executing) extracted sources:

- faster-whisper (MIT, Copyright (c) 2023 SYSTRAN), `faster_whisper/transcribe.py`
  `WhisperModel.add_word_timestamps`: `median_duration`/`max_duration` clamping
  around sentence-end marks and first/last-word re-anchoring (→ HEURISTIC_ADJUSTED);
  word times `round(..., 2)` (→ 10 ms). `faster_whisper/vad.py`
  `SpeechTimestampsMap.get_original_time` rounds restored times to 2 decimals.
- whisperX (BSD-2-Clause, Copyright (c) 2024, Max Bain), `whisperx/alignment.py`
  `align`: char times `round(..., 3)` (→ 1 ms); words without alignable
  characters get no `score` and their `start`/`end` silently filled by
  `interpolate_nans` (→ INTERPOLATED); failed segment alignment keeps
  `"words": []` (→ ALIGNMENT_FAILED).

## Decision: float-noise grid snapping (option C, user decision 2026-10-17)

Producer floats can carry binary noise after post-rounding arithmetic (e.g.
`time_offset + k*0.02`, VAD time restoration): `0.30000000000000004`. Options
considered: (A) refuse all off-grid values — real tool output may be rejected
wholesale; (B) round everything to the resolution — hides genuinely off-grid
values by up to half a resolution step; (C) snap only noise.

Chosen: **C**. A value is snapped to the nearest resolution multiple only when
it lies within `GRID_SNAP_EPSILON_MS = 0.001` ms (1 µs) of it; float noise is
~1e-11 ms. Anything farther is still refused with `NOT_ON_RESOLUTION_GRID`.
Every snapped input location is recorded in `TranscriptEvidence.grid_snaps`
so the snap is auditable. Effect on frame projection: none (1 µs is far below
one frame and below the mandatory ≥1-frame tolerance). No gate change.

## Open questions

- Return type is `TranscriptProjection` (snapshot + diagnostics) rather than a
  bare `TranscriptSnapshot`, so the overlap/zero-length timings stay auditable.
