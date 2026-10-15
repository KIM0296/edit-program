# CSA-001 — Compressed Source Acquisition Contracts

Qualification: **CODE_COMPLETE CANDIDATE / TEST_ONLY_SUPPORT**.

This PR implements only synthetic, offline contracts for the approved first
compressed-source acquisition profile. It does not run ffmpeg/ffprobe, inspect
real media, decode any user file, access Resolve, or authorize G2.

## Authoritative base

- Repository: KIM0296/edit-program
- Base main: f22c4d4cb717a067f7ada054c0fae66ac6dfab25
- Base tree: 407d2a8bb2adc5dfd675c04eea1726123dba57f5
- Base main CI: Domain safety CI 38541584486 — SUCCESS
- Branch: feature/csa001-compressed-acquisition

PR #60 / PVP-001B PRE-G2 harness is already merged into this base.
PVP-001B remains TEST_ONLY_SUPPORT and G2–G7 remain HOLD.

## Scope

Exact implementation allowlist:

1. tools/compressed_source_acquisition.py
2. tests/test_compressed_source_acquisition.py
3. tests/fixtures/compressed_source_acquisition/README.md
4. tests/fixtures/compressed_source_acquisition/profile.schema.json
5. tests/fixtures/compressed_source_acquisition/known_answer_manifest.json
6. docs/CSA_001_STATUS.md

No production src module, dependency, CI configuration, Evidence/OBS/TRUST,
Safety/Authority/runtime contract, or native adapter is modified.

## Initial supported profile

The contract accepts only the initial acquisition profile:

- M4A/MP4/MOV family
- AAC-LC audio
- native 48,000 Hz
- 1 or 2 channels
- exact explicit global audio stream
- exact explicit 0-based selected analysis channel
- headerless signed PCM16LE interleaved output
- original sample rate and channel count/order retained

Explicitly forbidden:

- resampling
- downmix
- normalization
- AGC correction
- denoise/filtering
- time stretching
- random-seek acquisition
- first-audio-stream guessing
- loudest-channel selection

44.1 kHz, MP3 and more-than-stereo inputs are refused by the initial profile,
not repaired or converted into eligibility.

## Toolchain pin

ToolBinaryPin and ToolchainPin retain supplied exact:

- ffmpeg/ffprobe references
- full version strings
- executable SHA-256
- build-configuration SHA-256
- platform/architecture
- library version/hash pins
- software CPU policy
- locale C
- one decode thread
- procedure SHA-256

The inventory-time Shotcut ffprobe is not silently promoted into an approved
decoder pin. This module authenticates none of the supplied toolchain facts.

## Permission / source boundary

SourcePin and PermissionBinding retain:

- source/session/owner/recorder references
- lineage references and evidence digest
- compressed source SHA-256 and byte count
- acquisition time
- permission evidence digest
- valid-from / exclusive expiry
- permitted operations and retention reference
- immutable snapshot reference

validate_source_use requires an explicit timezone-aware use interval and no wall
clock default. The source must satisfy:

valid_from <= acquired_at <= use_start <= use_end < expiry

and the requested decode operation must be explicitly permitted.

Hashes prove supplied byte consistency only. They do not prove recording
authenticity, ownership, human identity or independent-session truth.

## Stream and channel contract

StreamFingerprint records exact container family, global stream index, audio
ordinal, optional stream ID, AAC profile/extradata digest, native rate, channels,
channel order, time base and start PTS.

No automatic first-stream or language-tag selection exists.

Channel order is preserved. selected_channel is analysis metadata only; the
canonical decoded output keeps every approved channel interleaved.

## PCM canonicalization policy

DecodeProfile fixes output to signed 16-bit little-endian interleaved PCM with
native 48 kHz and no processing.

The profile also requires supplied, versionable policy references for:

- overall conversion
- rounding
- clipping
- non-finite input handling
- channel interleave
- known-answer suite

The module deliberately does not invent the installed FFmpeg conversion behavior.
A separately pinned toolchain must pass known-answer vectors before real-source
acquisition can be considered.

## Argument policy

canonical_argument_template represents the only accepted synthetic command
template for v1:

- exact input placeholder
- exact global stream mapping
- one software decode thread
- audio output codec pcm_s16le
- raw s16le muxer
- no seek
- no -ar / -ac
- no audio filters
- no non-audio output

The module never executes this template.

## Sample-origin contract

SampleOriginEvidence distinguishes UNKNOWN from ESTABLISHED. ESTABLISHED requires
explicit presentation start PTS, nonnegative priming / skip / end-padding counts,
explicit edit-list handling state, accounting reference/digest, and canonical
sample origin zero.

Unknown origin refuses ExtractionRequest with SAMPLE_ORIGIN_UNESTABLISHED.
Duration×sample-rate rounding is never an origin source.

## Extraction receipts

ExtractionReceipt is supplied evidence only. Validation binds it to the exact
request and checks:

- source pre/post SHA and byte count
- output SHA presence
- output_bytes = sample_frames × channels × 2
- scalar sample count
- native sample rate/channel/order
- selected channel
- origin digest
- EOF / flush / zero exit status
- bounded output size
- restricted output reference

No raw PCM is stored in public receipts.

## Independent extraction

validate_independent_comparison requires:

- the exact ExtractionRequest and zero validation findings for each extraction
  against that request before comparison eligibility; two equally invalid receipts
  return INDEPENDENT_EXTRACTION_UNQUALIFIED even if their bytes/hashes agree
- distinct first/second operators
- second operator distinct from source recorder
- distinct process and attempt IDs
- identical request binding
- identical PCM hash, bytes, sample/scalar counts, channel/order, selected channel
  and origin digest
- explicit byte-identical comparison across the entire output
- no first-difference offset

First extractor may be the recorder; the second cannot be.

This is supplied-record consistency, not authentication of human independence.

## Bounded 4×30-second policy

The preregistered 48 kHz / 25 fps policy is implemented as a pure integer
calculation:

- F = 1,920 sample frames
- W = 1,440,000 sample frames
- M = F × floor(N/F)
- four non-overlapping W-length windows distributed across [0,M)

Sources with M < 4W are refused. Window boundaries are exact F multiples.
No detector, listening or annotation result can move the windows.

## Known-answer gate

KnownAnswerVector / KnownAnswerRun / validate_known_answer_suite bind expected
PCM hashes and counts to the exact ToolchainPin and DecodeProfile digests.

KnownAnswerSuite retains an immutable ordered vector tuple and suite_ref. Before
evaluating runs, suite_ref and the canonical SHA-256 of the entire suite must match
the profile's pin. Every vector field and ordering participates. Matching runs cannot
rescue a changed vector/hash/count or an added/removed/reordered vector.

The committed manifest is synthetic metadata only and is not proof that any
installed FFmpeg build passed the vectors.

## Public receipt boundary

PublicReceipt permits only pseudonymous references, digests, nonnegative integer
counts and diagnostic codes. qualification is fixed to TEST_ONLY_SUPPORT.

Private source paths, URLs, raw media, PCM, annotations and permission documents
remain outside Git and CI.

## NOT_IMPLEMENTED / HOLD

Not implemented:

- ffmpeg/ffprobe subprocess execution
- media read/write
- real decoder/toolchain qualification
- real source probe/decode
- actual permission verification
- secure immutable storage or ledger
- cryptographic human/session authentication
- real sample-origin acquisition
- native Resolve correspondence/read/currentness
- G2 acquisition
- G3 dataset freeze
- G4 real-data validation
- G5 calibration/validation/holdout
- G6 reproduction
- G7 qualification
- semantic producers
- production config promotion
- native mutation/staging/Apply

Real-media access remains HOLD.

## Data dependency

Current inventory candidate ID 22 is 44.1 kHz and therefore unsupported by this
initial profile. The primary 12-session plan still needs one independent eligible
48 kHz replacement unless another separately reviewed candidate is qualified.

No inventory candidate is automatically eligible because of this implementation.

## Stop condition

After implementation tests, validation, push, PR and CI receipt:

STOP.

Do not merge.
Do not access the 23 source files.
Do not pin a real decoder automatically.
Do not begin G2.
Do not start another milestone.

Request Chat Gate review first.

## PR #61 correction receipt

Reviewed input head: `1f10e417362c253c22c7066c58f058472a6969a3`.
The correction stays inside the exact six-file allowlist above. No production src,
dependency, CI/config, subprocess, decoder, real-media or native-access change.

Additional integrity checks:

- Established presentation_start_pts must have exact Python int type, as must
  priming/skip/end-padding counts. Strings, floats and bools are not normalized.
- ProbeReceipt rejects audio_ordinal >= audio_stream_count; ExtractionRequest can
  therefore only consume a consistent supplied ordinal/count relationship.
- validate_window_manifests first validates the extraction against the exact request.
  It requires four unique references and indices exactly 0..3, matching source hash,
  full PCM hash, selected channel, and supplied preregistered policy digest. Every
  PlannedWindow must equal the existing plan_windows result at its index, including
  exact integer byte offsets/counts. Tail exclusion equals N % 1920. Input manifest
  enumeration order is immaterial; window index binds the plan. No repositioning.
- Profile documentation schema now explicitly names the supported channel set
  `supported_channels`; actual stream.channels remains one integer count.

The validators check supplied evidence consistency. They do not independently read
bytes, authenticate provenance or turn a matching receipt into native qualification.
Policy digest pinning does not certify its authenticity. G2-G7 remain HOLD.

Development failure receipts (retained, not qualification runs):

- Red-first adversarial tests: 25 failed / 60 passed. These reproduced missing
  comparison qualification, suite/window contracts, PTS typing and schema semantics.
- First implementation pass: 85 passed. Ruff found one fixable import-order issue;
  fixed without configuration changes.
- Initial explicit strict: 22 diagnostics in the CSA test file from dynamic
  dataclass replacement dictionaries (existing and newly added cases). Fixtures
  now use explicit typed branches; intentionally malformed PTS values are injected
  without runtime coercion. No ignores, lint/type suppression or config weakening.
- Final targeted CSA: **89 passed**.
- Related PVP-001B/PVP-001A: **186 passed**.
- Full pytest: **2111 passed / 1 existing intentional-red opt-in skip**.
- Ruff: PASS. Repository mypy: PASS (41 files). Explicit strict CSA tool/test:
  PASS (2 files). These are not expanded legacy strict claims.
- Whitespace and exact six-file allowlist checked before commit.
- Exact correction head/tree and remote CI receipt are recorded in PR #61.

Qualification remains **CODE_COMPLETE CANDIDATE / TEST_ONLY_SUPPORT**.
No real source was accessed or decoded. No acquisition, window selection on real
data, annotation, calibration or holdout execution occurred. Stop after push/CI.
