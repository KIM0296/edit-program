# PVP-001A — Local PCM Acoustic Evidence Producer

Qualification: **CODE_COMPLETE / TEST_ONLY_SUPPORT**. The deterministic producer
was exercised using actual synthesized PCM16LE byte buffers. This is not real-media
producer qualification, calibrated VAD, semantic understanding, native read/mutation
qualification, or VERIFIED_LIVE. Silence is acoustic evidence, not editorial meaning.

## Base and scope receipt

Remote main verified exactly before editing:

- SHA: `3613d837e505e3dc28c0d669f0a2609a8cea5e78`
- Tree: `bac321f9ea1044706145c5959906b7f0fca7cc61`
- Branch: `feature/pvp001a-local-pcm-evidence`
- Worktree: `C:/Users/c/source/repos/edit-program-pvp001a`
- Final commit/tree and remote CI result are recorded in the PR.

Exact changed-file allowlist:

1. `src/davinci_ai_editor/pause_acoustic_producer.py`
2. `tests/test_pause_acoustic_producer.py`
3. `docs/PVP_001A_STATUS.md`

No existing production module, classifier, Evidence/OBS contract, TRUST/Safety/
Authority/runtime code, dependency, Ruff/mypy/pytest/CI configuration was changed.
No native mutation, subsequent producer or other milestone was started.

## New immutable types and existing consumers

- `PcmInput`: decoded bytes (or explicit unavailable None), format, integer sample
  rate, channel count, mandatory selected channel, exact SourceFrameRange, source
  ref and existing ObservationPlacementLink. Existing evidence types cannot safely
  hold the raw decoded input metadata. Mutable sample arrays are not accepted.
- `AcousticConfig`: explicit versioned detector/local timing parameters. No hidden
  calibrated/product defaults. All parameters participate in config_ref.
- `PcmDiagnostic`: producer-specific PCM/config/context input failures. Existing
  mapping, OBS and preparation statuses remain separate; no duplicate coverage,
  workflow or execution state machine.
- `AcousticResult`: derived records, exact retained map results and existing OBS
  result, input metadata/source ref/digest, producer/config and typed diagnostics.
  Does not retain PcmInput or raw PCM bytes. The exact link is retained through OBS.

Reused unchanged: ProducerKind.RULE, ProducerRef, EvidenceAssertion/Strength/Kind,
EvidenceBinding, Presence, LocalPauseReference, EvidenceRecord/EvidenceBundle;
FrameRate/NativeSnapshotRef/PlacementTemporalBinding/MappingRequest/map_range and
typed ranges/statuses; ObservationPlacementLink, AnalysisCoverage/CoverageStatus,
prepare_pause_candidates_from_native; RelativePauseBand and the existing
prepare_observation/classify_pause path. No new feature schema, timeline, generic
producer framework or model registry. Standard library only.

## Exact supported PCM domain

Signed PCM16 little-endian, interleaved channels, positive integer sample rate.
The caller must select one channel explicitly; no default selection, downmix,
resampling, stretching or interpolation. No file/codec decoding or extraction.

Compute `divmod(sample_rate * source_rate.denominator, source_rate.numerator)`.
Only a positive integer quotient with zero remainder is supported. Interleaved
sample frames must be complete and byte count must equal:

`source_frame_duration * samples_per_source_frame * channel_count * 2`.

The source window must map EXACT through existing map_range. The first profile
supports equal source/timeline span lengths consistent with OBS's existing Clip
projection, including exact equal-span affine where existing contracts permit it.
Non-integral samples/frame, non-EXACT mapping and non-1:1 projection fail closed.
No float-second conversion, round, nearest-frame, clamping, tolerance or rebasing.

PCM acquisition/source correspondence is supplied by the caller. Exact lengths,
links and hashes correlate content; they do not authenticate that the bytes came
from the claimed native source. Filename is never used as media identity.

## Versioned algorithm and explicit policy

Algorithm/config version: `pcm-frame-energy-v1`; ProducerRef RULE,
`local-pcm-acoustic`, producer version `v1`, evidence version `v1`.

Required config fields:

- mean_square_threshold: integer in 0..32768²;
- minimum_silent_frames: positive integer, inclusive;
- neighborhood_source_frames: positive inclusive start-to-start radius;
- minimum_neighbors: positive comparison population, excluding current pause;
- short_ratio, normal_ratio, long_ratio: strictly increasing positive Fraction
  values; inclusive duration/reference band boundaries;
- version: supported algorithm identifier.

config_ref is SHA-256 of a deterministic JSON encoding of all parameters and exact
rational numerator/denominator pairs. Evidence identities correlate source ref,
PCM digest, decoding/channel metadata, config, snapshot/link and region. These
digests are deterministic content correlation, not authentication or approval.

For each complete source-frame block, sum squares of the selected channel's signed
integer samples. A frame is acoustically silent under this policy iff
`sum_squares <= mean_square_threshold * samples_per_frame`.
Keep only contiguous runs meeting minimum_silent_frames. Never bridge noise gaps.
Non-silent means only above threshold, never speech. Threshold silence is not a
claim about words, breaths, intent, meaning or editing quality.

Every emitted region is mapped through map_range before producing its existing
timeline EvidenceBinding. No independently implemented temporal transformation.

Timing population is limited to emitted regions from the same decoded window and
placement, within the declared start-frame radius. Window-edge runs may be
truncated: retain their SILENCE_REGION but exclude them from timing, both as targets
and neighbors. Exclude self. If population is sufficient, sort durations and use
the lower median at `(n - 1) // 2`; no fractional median rounding. Compare exact
integer products against the rational band limits. Emit SHORT/NORMAL/LONG/VERY_LONG
as timing only. Emit LOCAL_PAUSE_REFERENCE only when `0 < reference < target duration`.
Insufficient population means both timing records are absent, not ABSENT assertions.
The record note retains the exact neighboring silence evidence IDs and rule.

No default threshold/population is exposed by production constructors. Test config
values are TEST_ONLY_SUPPORT, not editor-calibrated settings. EvidenceStrength
MODERATE is a baseline acoustic evidence label, not editorial confidence.

## Evidence and OBS composition

`produce_pause_evidence(..., context=(), analyze=True)` emits only:

- SILENCE_REGION with existing Presence / PRESENT;
- RELATIVE_PAUSE_BAND when the local population is sufficient;
- LOCAL_PAUSE_REFERENCE when a shorter positive local statistic exists.

It never emits SPEECH_REGION, CONTENT_MODE, TRANSCRIPT_BOUNDARY,
QUESTION_ANSWER_BOUNDARY, SPEAKER_CHANGE/OVERLAP, NATURAL_BREATH, HESITATION,
THINKING, EMOTIONAL, RECORDING_DEAD_AIR or FAILED_TAKE_GAP cues.

First reuse OBS with NOT_EVALUATED coverage and no bundles to validate native
readiness/link without claiming completed analysis. Stop on its actual blocking
diagnostics. After PCM analysis, reuse OBS for the produced EvidenceBundles.
No second readiness algorithm or classifier implementation exists.

Caller contextual EvidenceRecords must bind the exact snapshot/version/placement
and one detected pause range. They are never spread, moved or silently dropped.
Invalid/duplicate context returns CONTEXT_MISMATCH without candidates; honest
acoustic records/coverage remain retained. Valid context and acoustic records enter
existing EvidenceBundle validation and OBS. Reordered identical context gives the
same semantic result. Conflicting/UNKNOWN context follows existing preparation.

PCM-only context ordinarily leaves preparation unresolved and candidate=None.
With explicit supplied content/boundary and sufficient local timing, the existing
classifier may produce TIGHTEN. Question/answer context remains KEEP. Missing
reference may remain REVIEW. Explicit external removal cues may make the existing
classifier output REMOVE, but no removal cue is PCM-generated and no output grants
approval or execution. Automatic REMOVE remains HOLD.

Raw PCM is never copied into EvidenceRecord.note/payload, bundles, candidates or
semantic revision data. The result retains metadata, source ref and SHA-256 only;
raw storage/lifecycle stays outside this module.

## Coverage and staleness

Reuse the five OBS coverage statuses without another enum:

- Full valid linked source window: ANALYZED, including zero detected subjects.
- Valid proper subwindow: PARTIALLY_ANALYZED relative to the linked placement,
  even when the analyzed subwindow prepares candidates. No claim about its remainder.
- analyze=False: NOT_EVALUATED, not a no-pauses conclusion.
- Missing PCM, malformed/unsupported PCM or unrepresentable mapping: UNAVAILABLE.
- Snapshot/link/currentness mismatch: existing OBS stale result, no new evidence
  or candidate. No old approval carry-forward or silent rebase.

Immediately after native/link readiness succeeds, map the requested source window
through existing map_range, before analyze=False, PCM availability, format, channel,
sample-rate or config checks. Every EXACT result supplies the exact requested
timeline window to coverage, including early NOT_EVALUATED/UNAVAILABLE results.
If readiness prevents mapping or the requested range cannot map EXACT, the retained
placement envelope is explicitly labeled as neither the requested window nor
analyzed frames. The original source request and attempted mapping result remain
retained; non-EXACT mapping returns the existing typed MAPPING_NOT_EXACT failure.
No fallback inference, rounding, or second mapping algorithm. Producer authenticity
remains open.

## Validation receipt

- Red-first: producer import absent, initial test collection failed as expected;
  implementation then made that scenario pass.
- New PVP module: **60 passed**. Actual synthesized PCM bytes exercise mono/stereo,
  signed endpoints, exact threshold boundary, malformed metadata/bytes/counts,
  rational frame rate, minimum runs/no gap bridging, repeatability, source offsets,
  local populations/self exclusion/window edges, all forbidden output kinds,
  config changes, missing/conflicting/UNKNOWN context, TIGHTEN/KEEP/REVIEW/external
  REMOVE through existing classifier, coverage states, repeated media, stale
  snapshots and architectural imports/no rounding/no execution.
- Focused PVP + OBS + Evidence + temporal mapping + native snapshot + pause
  baseline/planning + orchestration: **522 passed**.
- Full regression: **1,896 passed / 1 skipped**. The sole skip remains the existing
  opt-in intentional red test `test_naive_inv001.py:27`.
- Ruff check .: **PASS**.
- Repository strict mypy: **PASS**, 41 source files.
- Explicit strict mypy on both new Python files: **PASS**.
- Expanded strict baseline was rerun against a checkout with exact base tree
  `bac321f9ea1044706145c5959906b7f0fca7cc61`: **840 errors in 4 legacy test modules**
  (19 checked files). Current with both new files: **same 840 errors / 4 modules**
  (21 checked files), **zero normalized diagnostic differences**. Both expanded
  commands exit 1, NOT green. Modules: test_safety_preflight, test_expected_diff,
  test_execution_ir, test_transaction. No suppression/config weakening or cleanup.
- Baseline/current logs retained outside repo under the temporary trust001-validation
  directory as pvp-base-strict.txt / pvp-current-strict.txt.
- Whitespace and exact three-file allowlist checked before commit. Remote CI receipt
  is added to the PR independently of local results.

## NOT_IMPLEMENTED and open dependencies

NOT_IMPLEMENTED: Resolve native audio extraction; codec decode; FFmpeg integration;
real VAD; STT/Whisper; word timestamps; diarization; speaker identification;
transcript boundary inference; question/answer inference; prosody model;
natural-breath recognition; hesitation recognition; thinking/emotional recognition;
dead-air semantic recognition; failed-take recognition; content-mode detection;
native read qualification; native mutation; staging; approval UI; delegated request
parser; full Editing DNA; DP001 human validation; Net Time Saved proof.

OPEN-009 is only advanced for local PCM silence, deterministic timing baseline and
producer-to-Evidence composition. Still open: semantic boundary/content producers,
real VAD qualification, prosody, emotion/thinking/breath/hesitation semantics,
confidence calibration, semantic dead-air/failed-take logic, real-media acquisition
authenticity, mixed/non-integral profiles beyond this domain, real editor calibration.
OPEN-002 / OPEN-008 and native read/mutation/staging qualification remain unchanged.

Final candidate: **GO for code/contract PR review**, CODE_COMPLETE / TEST_ONLY_SUPPORT;
all real-media/editor/native qualification remains unproven/HOLD. Recommended next
step after Chat Gate: an independently reviewed, bounded real-PCM calibration and
acquisition-evidence exercise before broader producers. Do not begin it here.
STOP after PR and CI receipt. Do not merge or begin another milestone.

## PR #59 coverage-truthfulness correction

The original early-stop paths incorrectly reported full-placement coverage for a
partial PCM request. Eight red-first regressions reproduced this: six early-stop
paths (not evaluated, PCM unavailable, format, channel, rate, config) and two
unmappable-request cases. The mapping-order change fixes the early ranges and
explicitly labels the unmapped placement envelope. Scope remains the same three
files; no existing contracts, acoustic algorithm or timing policy changed.

Updated validation: PVP **68 passed**; related regression **530 passed**; full
pytest **1,904 passed / 1 existing skip**; Ruff PASS; repository mypy PASS (41 files);
explicit strict PASS (2 files). Whitespace/allowlist checked before commit; remote
CI receipt recorded in the PR. The previously disclosed legacy expanded strict
baseline is not claimed green.
