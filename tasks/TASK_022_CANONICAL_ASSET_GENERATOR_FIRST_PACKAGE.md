# TASK-022 — Canonical Asset Generator & First Package Build

Status: **CHAT APPROVED / first package candidate sealed — merge pending**

Execution dependency note:

TASK numbering is repository chronology, not runtime dependency order.

Recommended execution order after TASK-019:

```text
TASK-019 Probe Harness Foundation
    ↓
TASK-022 Canonical Asset Generator + First Package
    ↓
TASK-020 Read-only Resolve Adapter runtime validation
    ↓
TASK-021 Fixture Materializer
```

TASK-022 may therefore execute before TASK-020/021 even though its numeric ID is later.

Authoritative basis:

- ADR-034 — Probe Fixture Catalog v1
- ADR-036 — Canonical Fixture Asset Package v1
- ADR-037 — Canonical Asset Generator Contract v1
- `docs/PROBE_FIXTURE_CATALOG.md`
- `docs/CANONICAL_FIXTURE_ASSET_PACKAGE.md`
- `docs/CANONICAL_ASSET_GENERATOR_CONTRACT.md`
- OPEN-021 — Canonical Fixture Binary Generation / First Package Digest

## Purpose

Implement the deterministic canonical asset generator, build the first six binary probe assets,
validate the resulting package, generate its exact SHA-256/package_digest evidence, and prepare one
immutable first-package index for Chat approval.

This task does **not** use DaVinci Resolve and does not implement TASK-020/021.

## Success definition

TASK-022 succeeds only when:

1. generator unit/domain logic is implemented and tested;
2. exact FFmpeg/ffprobe toolchain is recorded;
3. six canonical binaries are generated;
4. all structural/decode validations pass;
5. two clean full generation runs are byte-for-byte identical;
6. `manifest.v1.json`, `generator.lock.json`, `checksums.sha256` are canonical and identical
   across the two clean runs;
7. exact six asset SHA-256 values and `package_digest` are produced from real bytes;
8. package is sealed without overwriting any prior sealed package;
9. repository package-index candidate is prepared with real digest/hash values;
10. full unit regression / Python 3.11 / Ruff / strict mypy pass;
11. Chat Gate reviews the actual package evidence before it becomes an approved canonical package.

Generator success is **not** Resolve runtime support.

## Non-goals / forbidden scope

Do not implement:

- Resolve API calls
- Resolve import
- Resolve project/timeline creation
- fixture materialization
- native mutation/probing
- TASK-020 adapter
- TASK-021 materializer
- production editing media ingestion
- real editorial footage processing
- arbitrary shell execution
- arbitrary user/LLM FFmpeg arguments
- codec/profile/raster/fps fallback
- automatic release publication without Chat Gate
- automatic network download during an ordinary edit workflow

## Proposed repository structure

Implementation should prefer:

```text
tools/canonical_assets/
├─ __init__.py
├─ generate.py
├─ video_pattern.py
├─ audio_pattern.py
├─ wav.py
├─ ffmpeg.py
├─ manifest.py
├─ checksums.py
├─ validate.py
├─ package.py
├─ glyphs_5x7.py
└─ recipe.v1.json

tests/
├─ test_canonical_video_pattern.py
├─ test_canonical_audio_pattern.py
├─ test_canonical_package_format.py
└─ test_canonical_generator_integration.py
```

Exact filenames may vary only if responsibility boundaries remain equally explicit.

Do not place generator logic in the production Resolve adapter package unless there is a separately
approved reason. Canonical media generation is engineering tooling, not runtime editing behavior.

## Phase 1 — Pure deterministic source generator

### Video constants

Implement exact ADR-037 constants:

- width = 1280
- height = 720
- fps = 24/1
- frame_count = 720
- RGB24 source
- frame indices 0..719

Background RGB:

- ALPHA = [32,96,160]
- BETA = [160,96,32]
- GAMMA = [112,48,160]
- REPEAT = [96,96,96]
- VIDEO_ONLY = [32,128,64]

Implement exactly:

- 8 px [235,235,235] border
- embedded 5x7 glyphs
- role glyph at [40,40], 16x16 cell
- four-digit frame counter at [40,180], 12x12 cell
- two-digit frame-within-second counter at [40,300]
- 10-bit MSB-first binary code at y=400
- 28x48 bit blocks, 8 px gap
- 0 = [16,16,16]
- 1 = [240,240,240]
- moving bar:
  - x = 200 + ((frame_index * 13) % 1000)
  - width = 16
  - y = 520..671 inclusive
  - RGB = [240,220,32]
- second boundary indicator:
  - frames frame_index % 24 == 0
  - x = 1120..1223
  - y = 40..119
  - active [255,64,64]
  - inactive [32,32,32]

No system font, PIL font lookup or antialiasing.

### Required video unit evidence

Tests must independently lock at least:

- array shape/dtype
- frame 0 role glyph/border
- frame 1 moving bar x
- frame 23 frame-within-second encoding
- frame 24 second-boundary indicator
- frame 719 counter/binary code bounds
- no array write outside raster
- deterministic repeat calls
- each asset role has the expected background
- ALPHA/BETA/GAMMA/REPEAT/VIDEO_ONLY source frames differ where intended
- REPEAT generation is byte-identical across repeated generator calls

Add a **small hand-audited literal golden vector** for selected glyph matrices/pixels. Do not make
all tests derive expected output from the same production function.

### Source RGB digest

For every video asset, compute SHA-256 over the concatenation of all 720 RGB24 source frames in order.

This digest is provenance only.

Tests must prove frame-order changes alter the digest.

## Phase 2 — Pure deterministic audio generator

### PCM constants

Implement exactly:

- sample_rate = 48000
- channels = 2
- samples/channel = 1,440,000
- signed 24-bit
- little-endian packed PCM
- 30.000 seconds

Frequencies:

- ALPHA L/R = 440/880
- BETA = 500/1000
- GAMMA = 600/1200
- REPEAT = 700/1400
- AUDIO_ONLY = 800/1600

Amplitude constants:

- BASE_A = 524288
- ACCENT_A = 2097152

Envelope per second:

- 0..239: integer ramp BASE_A -> ACCENT_A
- 240..719: ACCENT_A
- 720..959: integer ramp ACCENT_A -> BASE_A
- 960..47999: BASE_A

Implement the exact ADR-037 integer triangle oscillator and freeze integer operation ordering.

No:

- float trig
- float amplitude conversion
- random noise
- dither
- normalization
- limiter
- resampling

### Required audio golden tests

Tests must include fixed literal sample expectations around:

- sample 0
- first several oscillator samples
- 239 / 240
- 719 / 720
- 959 / 960
- 47999 / 48000
- final sample

Test both left/right channels for at least one asset.

Also test:

- all samples fit 24-bit signed range
- exact 3-byte two's-complement pack/unpack
- stereo interleave order
- exact total byte length
- repeated generation exact equality
- different asset roles yield different PCM
- REPEAT regenerated PCM exact equality

Do not validate the generator only through the same inverse helper used in production.

### Source PCM digest

Compute SHA-256 of exact interleaved source PCM bytes for each audio-bearing asset.

This is provenance, not canonical binary identity.

## Phase 3 — Deterministic WAV writer

Implement a small explicit WAV writer or equivalently controlled writer that produces:

- RIFF/WAVE
- PCM integer
- 2 channels
- 48000 Hz
- 24 bits/sample
- exact generated PCM data
- no LIST/INFO/timestamps/host metadata

Required tests:

- RIFF sizes correct
- fmt fields correct
- data length exact
- no extra chunk unless explicitly allowed by contract
- data chunk byte-equals generated PCM
- duplicate writes byte-identical

ASSET_AUDIO_ONLY canonical binary uses this writer.

## Phase 4 — Toolchain abstraction / preflight

Implement a typed immutable ToolchainProfile.

At minimum record:

- Python version
- NumPy version
- FFmpeg version text
- ffprobe version text
- FFmpeg build/configuration fingerprint
- ffmpeg executable path used during tooling execution
- ffprobe executable path
- executable SHA-256 if accessible
- supported dnxhd encoder/profile evidence
- MOV muxer evidence
- WAV muxer evidence
- pcm_s24le evidence
- bitexact option evidence
- toolchain contract version

Absolute executable paths are local runtime evidence and must not leak into authoritative
`generator.lock.json` if they make the package nondeterministic. Store normalized binary identity
instead.

### Preflight fail-closed

Preflight must fail if it cannot establish the required toolchain.

Do not automatically:

- download a different FFmpeg
- search arbitrary internet locations
- choose a hardware encoder
- switch codec/profile
- change pixel format
- change frame rate/raster

If no compatible toolchain is available, report TOOLCHAIN_UNSUPPORTED and stop.

## Phase 5 — Typed FFmpeg command construction

Create command token arrays from typed constants only.

No API accepts:

- raw shell command string
- shell=True
- arbitrary extra args from user text
- arbitrary LLM-provided flags

Subprocess calls use token arrays.

Paths must remain under the selected staging root for outputs/temp files.

### Video encode semantics

Raw RGB24 via stdin:

- 1280x720
- 24/1
- 720 frames
- software `dnxhd` encoder
- `dnxhr_lb` profile
- `yuv422p`
- no audio
- bitexact where supported/required by ADR-037
- explicit metadata normalization
- MOV

The exact final token array becomes locked provenance.

### Final A/V mux semantics

For ALPHA/BETA/GAMMA/REPEAT:

- input 0 = validated video-only MOV
- input 1 = deterministic PCM WAV
- explicit stream map
- video stream copy
- audio stream copy if locked MOV toolchain accepts PCM as specified
- no extra streams
- bitexact/metadata normalization

If exact PCM stream copy is unsupported, stop with MUX_FAILURE/TOOLCHAIN_UNSUPPORTED.

No lossy fallback.

## Phase 6 — Structural validator

Parse ffprobe JSON using typed validation.

Reject missing, unexpected or ambiguous fields.

### A/V asset required shape

- exactly 2 media streams total unless ffprobe exposes ignorable container metadata separately
- exactly 1 video
- exactly 1 audio
- no subtitle/data/attachment stream
- video codec family consistent with DNxHD/DNxHR
- profile = DNxHR LB
- width = 1280
- height = 720
- pix_fmt = yuv422p
- r_frame_rate = 24/1
- avg_frame_rate = 24/1
- progressive/no interlace semantic result
- audio = 48 kHz
- 2 channels
- 24-bit PCM semantic format

### VIDEO_ONLY

Exactly one video stream; zero audio/subtitle/data/attachment streams.

### AUDIO_ONLY

Exactly one PCM audio stream; zero video/subtitle/data/attachment streams.

Do not trust filename extension.

## Phase 7 — Full decode validation

### Video

Decode every video asset fully with the locked FFmpeg build.

Require:

- process success
- no decode errors
- exactly 720 frames
- exactly 1280x720 each

If the validation implementation computes a decoded RGB/YUV digest, keep it diagnostic/provenance only.

Do not require encoded->decoded RGB to byte-equal the original RGB24 because DNxHR/YUV conversion is
not lossless in RGB value space.

### Audio

For ALPHA/BETA/GAMMA/REPEAT:

- decode final MOV audio to raw signed 24-bit LE stereo
- require exact byte equality to source PCM
- require exact sample count

For AUDIO_ONLY:

- parse/decode WAV data
- require exact byte equality to source PCM

Any mismatch = AUDIO_DECODE_MISMATCH.

## Phase 8 — Canonical JSON serializers

Implement one shared canonical JSON writer:

- UTF-8
- no BOM
- sorted keys
- compact separators
- LF
- exactly one trailing LF
- no locale formatting
- no NaN/Infinity

Tests must include fixed literal expected bytes for representative nested structures.

## Phase 9 — manifest.v1.json

Generate only after all six assets pass validation.

Required package metadata includes the ADR-036 semantic contract and validated stream facts.

Each asset record includes at least:

- asset_id
- role
- revision
- relative_path
- media_kind
- duration frames/samples
- stream counts
- actual validated video codec/profile/raster/fps/pix_fmt as applicable
- actual validated audio sample rate/bit depth/channels as applicable
- diagnostic pattern version
- source_rgb24_digest if applicable
- source_pcm_digest if applicable
- checksum algorithm = SHA-256

Do not put final asset SHA-256 values or package_digest into manifest itself.

## Phase 10 — generator.lock.json

Generate with the same canonical serializer.

Required:

- generator contract version
- generator source git commit
- recipe.v1.json SHA-256
- Python version
- NumPy version
- FFmpeg/ffprobe versions/build fingerprint
- executable SHA-256 if available
- normalized exact encode token arrays
- normalized exact mux token arrays
- metadata normalization policy version
- structural validation version
- decode validation version

Do not record random temp paths, timestamps, username or hostname.

## Phase 11 — checksums and package digest

Generate `checksums.sha256` exactly as ADR-036/037.

Hash:

- manifest.v1.json
- generator.lock.json
- all six final asset binaries

Exclude:

- checksums.sha256 itself
- temp files
- logs
- source/intermediate essences

Format:

```text
<64 lowercase hex><two ASCII spaces><relative POSIX path><LF>
```

Sort paths lexicographically.

Then:

```text
package_digest = SHA256(exact checksums.sha256 bytes)
```

Required tests:

- order independent input -> sorted deterministic output
- path separator normalization
- lowercase digest
- exactly two spaces
- LF only
- final digest changes on any authoritative file-byte change

## Phase 12 — Clean two-run reproduction

Implement an explicit integration command, e.g.:

```text
python -m tools.canonical_assets.generate verify-reproducible ...
```

Exact CLI name may differ.

It must:

1. create fresh staging A
2. generate complete package candidate A
3. create separate fresh staging B
4. generate complete package candidate B
5. compare exact bytes of all authoritative paths
6. produce a deterministic comparison report
7. fail if any path differs

Authoritative comparison paths:

- six assets
- manifest.v1.json
- generator.lock.json
- checksums.sha256

A single successful run never seals a package.

## Phase 13 — Package sealing

Only after duplicate clean-run equality.

Sealing input must include:

- package name/version
- approved staging candidate
- package_digest
- output destination

Rules:

- destination package version absent -> may seal
- destination exists with same digest -> do not overwrite; report EXISTING_IDENTICAL
- destination exists with different digest -> PACKAGE_VERSION_COLLISION hard failure

No mutation of sealed bundle.

No publish-to-network action in core generator.

## Phase 14 — Repository package-index candidate

After real package generation, produce a small repository file candidate, suggested:

`canonical_assets/package-index.v1.json`

or equivalent approved location.

It must contain real values only:

- package_name
- package_version
- package_digest
- fixture_catalog_version
- asset package contract version
- generator contract version
- recipe version
- manifest SHA-256
- generator.lock SHA-256
- six asset IDs + SHA-256
- publication/storage reference if one exists
- Chat approval reference initially null/pending until Gate

Do not fabricate a publication URL.

The package-index candidate is reviewed in the TASK-022 PR.

## Package binary delivery rule

Do **not** commit large binary assets as ordinary Git blobs.

TASK-022 completion may present:

- sealed local package path/evidence,
- package index candidate,
- hashes/digest,
- generation logs/reports,

while binary publication/storage can use the approved versioned release/artifact mechanism.

If the available GitHub tooling cannot safely publish the large bundle, do not invent a release
link or commit the binaries. Record the local sealed-package evidence and leave publication as an
explicit completion limitation requiring a supported delivery path.

## Test strategy

### A. Always-on unit tests

Must run in normal CI without full canonical binary build.

Cover at least:

1. frozen/typed recipe/domain values
2. glyph tables exact dimensions/bits
3. selected video pixel golden vectors
4. deterministic frame generation
5. frame boundary/index validation
6. binary frame-code encoding
7. moving-bar math
8. second-boundary indicator
9. source RGB digest stability
10. integer oscillator golden vectors
11. envelope boundary samples
12. 24-bit range
13. 24-bit pack/unpack
14. stereo interleave
15. PCM byte length
16. source PCM digest stability
17. deterministic WAV header/body
18. no unwanted WAV metadata chunk
19. canonical JSON exact bytes
20. SHA-256 file hashing
21. checksums formatting
22. package_digest
23. safe relative path validation
24. existing sealed package collision policy
25. typed FFmpeg token builder
26. no shell=True/raw shell
27. no arbitrary FFmpeg arg injection
28. failure status derivation
29. manifest schema validation
30. generator-lock schema validation

### B. Optional/explicit FFmpeg integration tests

Marked/segregated so ordinary CI can skip when the locked toolchain is unavailable.

Cover:

31. toolchain preflight
32. short video encode
33. short PCM MOV mux
34. ffprobe parser
35. stream validation
36. video frame decode count
37. audio exact decode
38. metadata normalization
39. short two-run byte equality

### C. Full package generation acceptance

Run explicitly for TASK-022 completion:

40. six assets generated
41. all source digests generated
42. all stream validations pass
43. four A/V assets audio-decode exact
44. video-only structure exact
45. audio-only structure/data exact
46. all video assets exactly 720 decoded frames
47. all audio assets exactly 1,440,000 samples/channel
48. manifest canonical
49. generator lock canonical
50. checksums canonical
51. package_digest real
52. full clean run A/B byte equality
53. no sealed version collision
54. package index candidate uses actual real hashes
55. no authoritative asset binary committed as ordinary Git blob

### D. Repository regression

56. TASK-001..019 regression remains green at implementation time
57. Python 3.11 CI PASS
58. Ruff PASS
59. strict mypy PASS

If TASK-020 or later code has landed before TASK-022 implementation starts, full then-current
regression is required instead of freezing the regression boundary to TASK-019.

## Required failure cases

Tests/integration must explicitly exercise:

- invalid frame index
- unknown asset role
- unsupported toolchain
- missing dnxhr_lb capability
- encoder failure
- mux failure
- wrong stream count
- wrong codec/profile
- wrong raster/fps/pix_fmt
- unexpected subtitle/data stream
- wrong audio sample rate/channels/format
- frame count mismatch
- sample count mismatch
- audio decode mismatch
- source digest mismatch where checked
- malformed manifest
- malformed generator lock
- malformed checksums
- checksum mismatch
- package_digest mismatch
- path traversal attempt
- output outside staging root
- shell/argument injection attempt
- nondeterministic second run
- package version collision

No failure case falls back to another media profile.

## Implementation completion report

Write:

`docs/reports/TASK_022_COMPLETION.md`

It must contain:

- branch/base/head
- changed source/test files
- exact toolchain evidence
- exact FFmpeg/ffprobe version/build
- command recipes
- unit/integration/full-generation test results
- six final asset paths/names
- six final asset SHA-256
- manifest SHA-256
- generator.lock SHA-256
- package_digest
- clean-run A/B equality result
- package sealed location or publication limitation
- package-index candidate path/content summary
- explicit statement that Resolve runtime validation has not happened
- OPEN-021 remaining items, if any
- deviations from ADR-036/037
- next recommendation
- Chat Gate section

Do not put fake placeholder hashes in the completed report.

## Chat Gate

TASK-022 PR must remain unmerged until Chat reviews:

- generator implementation
- independent unit/integration evidence
- exact toolchain
- actual generated package hashes
- two-run determinism evidence
- package-index candidate
- absence of silent fallback
- absence of large binary Git blobs
- current full regression

Do not start TASK-020 or TASK-021 automatically after completion.

## OPEN-021 resolution rule

OPEN-021 may be marked:

### RESOLVED FOR FIRST PACKAGE GENERATION

only when TASK-022 Chat Gate approves actual:

- generator implementation
- six real canonical binaries
- exact hashes
- package_digest
- deterministic two-run equality
- package-index candidate

Resolve import/read/materialization support remains a separate TASK-020/021 concern and must not be
collapsed into OPEN-021 generator completion.

## Final principle

> TASK-022 does not merely write six media files. It creates one auditable, reproducible, immutable
> measurement instrument whose exact bytes become part of the native-safety evidence chain.

## Implementation notes before code

- Engineering tooling lives in `tools/canonical_assets`, not the production adapter package.
- Recipe v1 freezes embedded glyph bitmaps, one-cell inter-glyph spacing, and endpoint-inclusive
  integer envelope interpolation: ramp denominator 239, attack offset n, release offset n-720.
  Oscillator floor division occurs only after multiplying the signed numerator by the amplitude.
- NumPy is pinned to 2.3.5. Actual generation requires Python 3.11.x and explicitly selected local
  FFmpeg/ffprobe binaries. No tool downloads or profile fallback are part of the generator.
- Unit tests run without FFmpeg. Actual preflight, full six-asset Run A/B generation and exact
  comparison completed on the locked toolchain; real metadata/index evidence is in
  canonical_assets/first-package-candidate-v1. Chat Gate APPROVED on PR #48 (2026-10-07).
