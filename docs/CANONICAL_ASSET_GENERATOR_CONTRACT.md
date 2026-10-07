# Canonical Asset Generator Contract v1

Status: **ACCEPTED — Chat Product/Architecture baseline**

## Purpose

Define the exact generation algorithm, toolchain contract, validation gates and publishing workflow
for the six binary assets in ADR-036 Canonical Fixture Asset Package v1.

This contract resolves the generator design portion of OPEN-021. It does not fabricate the first
binary hashes/package_digest; those exist only after an authorized generation run.

## Core rule

> The generator must be deterministic enough to fail loudly when its own output changes, but exact
> shipped bytes remain the canonical identity.

FFmpeg bitexact mode and a locked toolchain reduce nondeterminism. They do not replace final SHA-256
approval.

## Generator implementation profile

v1 generator is a repository-controlled Python CLI with a locked toolchain.

Required logical dependencies:

- Python 3.11.x generation environment
- NumPy, exact version pinned by the generator environment/lock
- FFmpeg + ffprobe, exact binary build/version recorded
- no system fonts
- no network access
- no GPU encoder
- no hardware decoder/encoder path
- no wall-clock/random/hostname/user/path-derived media content

Generation math for pixels and PCM uses integer operations only.

The generator may use temporary files under an isolated staging directory. Temporary paths are never
written into authoritative media metadata.

## Top-level generator phases

One package generation run executes these phases in order:

1. TOOLCHAIN_PREFLIGHT
2. STAGING_INIT
3. SOURCE_PATTERN_GENERATION
4. VIDEO_ESSENCE_ENCODING
5. AUDIO_ESSENCE_GENERATION
6. FINAL_CONTAINER_MUX
7. STRUCTURAL_PROBE
8. DECODE_VALIDATION
9. MANIFEST_WRITE
10. GENERATOR_LOCK_WRITE
11. CHECKSUM_WRITE
12. PACKAGE_DIGEST_COMPUTE
13. CLEAN_REPRODUCTION_RUN
14. BYTE_FOR_BYTE_REPRODUCTION_COMPARE
15. SEAL_STAGING_PACKAGE

A failure in any phase invalidates the whole package candidate.

No partial package is published.

## Toolchain preflight

Before writing media:

- record Python version
- record NumPy version
- run ffmpeg -version
- run ffprobe -version
- capture FFmpeg build/configuration identifier
- verify the dnxhd encoder is present
- verify the installed encoder advertises DNxHR LB support
- verify yuv422p output is accepted by the chosen encoder/profile combination
- verify MOV muxer availability
- verify pcm_s24le support
- verify WAV muxer availability
- verify bitexact option support used by the locked recipe

FFmpeg's current DNxHD encoder exposes DNxHR LB as a named profile. The exact executable/toolchain is
still pinned because a profile name existing does not prove byte-identical output across arbitrary
builds.

If 1280x720 / 24 fps / DNxHR LB / yuv422p is rejected by the locked FFmpeg build:

- generation stops;
- no fallback profile/codec/raster is selected;
- ADR-036 requires review before changing the package contract.

## Generator source contract

Suggested repository structure:

```text
tools/canonical_assets/
├─ generate.py
├─ video_pattern.py
├─ audio_pattern.py
├─ manifest.py
├─ validate.py
├─ glyphs_5x7.py
└─ recipe.v1.json
```

A future implementation may package these modules differently, but the responsibilities and recipe
version must remain explicit.

## Deterministic video source algorithm

### Frame domain

For each video-bearing asset:

- width = 1280
- height = 720
- source pixel format = RGB24
- frames = 720
- frame indexes = 0..719
- fps = 24/1

Each frame is created as a NumPy uint8 array with shape [720, 1280, 3].

No floating-point pixel math is used.

### Background colors

Exact generator RGB bytes:

- ASSET_ALPHA: [32, 96, 160]
- ASSET_BETA: [160, 96, 32]
- ASSET_GAMMA: [112, 48, 160]
- ASSET_REPEAT: [96, 96, 96]
- ASSET_VIDEO_ONLY: [32, 128, 64]

These are generator-source values. Decoded DNxHR RGB reconstruction is not required to equal them
bit-for-bit.

### Fixed border

Draw an 8-pixel border:

- top/bottom/left/right
- RGB [235, 235, 235]

Inside the border, no scaling/cropping operation is performed by the generator.

### Asset-role glyph

Draw one asset role code using an embedded 5x7 bitmap glyph table, nearest/integer rectangles only.

Role codes:

- A = ASSET_ALPHA
- B = ASSET_BETA
- G = ASSET_GAMMA
- R = ASSET_REPEAT
- V = ASSET_VIDEO_ONLY

Glyph rules:

- 5x7 bit matrix stored in source code
- cell size = 16x16 pixels
- origin = [40, 40]
- foreground RGB = [255,255,255]
- no antialiasing
- no font library

### Source-frame counter

Draw a four-digit zero-padded counter 0000..0719.

- embedded 5x7 digit glyphs
- cell size = 12x12
- origin = [40, 180]
- foreground RGB = [255,255,255]

This counter is diagnostic only.

### Frame-within-second counter

Draw two digits:

```text
frame_index % 24
```

- 00..23
- origin = [40, 300]
- same glyph rules

### Binary frame code

Draw 10 binary blocks representing frame_index in unsigned 10-bit form.

- most-significant bit first
- origin x = 40
- origin y = 400
- block = 28x48
- horizontal gap = 8
- bit 0 RGB = [16,16,16]
- bit 1 RGB = [240,240,240]

720 fits within 10 bits.

This code is for diagnosis/readback experiments only, not object identity.

### Moving bar

Draw a 16-pixel-wide vertical bar:

```text
x = 200 + ((frame_index * 13) % 1000)
y = 520..671 inclusive
RGB = [240, 220, 32]
```

The bar always remains within the 1280-pixel raster.

### Second-boundary indicator

For frames where:

```text
frame_index % 24 == 0
```

draw a fixed rectangle:

- x = 1120..1223
- y = 40..119
- RGB = [255, 64, 64]

Otherwise the rectangle uses RGB [32,32,32].

### Pixel-source digest

Before encoding, compute one SHA-256 over the concatenation of all 720 RGB24 frame byte arrays in
frame order.

Record it as `source_rgb24_digest` in generation provenance.

This digest is audit data, not the canonical asset identity.

## Video encoding pipeline

The raw RGB24 frames are streamed to FFmpeg through stdin. Do not write a multi-gigabyte rawvideo
file into the final package.

The required encoding semantics are:

- input: rawvideo RGB24 1280x720 at 24/1
- output codec: dnxhd encoder
- output profile: dnxhr_lb
- output pixel format: yuv422p
- output frame rate: 24/1 CFR
- encoder time base: 1/24 where the installed FFmpeg accepts the explicit setting
- audio disabled during the video-essence phase
- bitexact mode enabled
- metadata inherited from the generator process/input removed
- CPU/software path only

FFmpeg documents `bitexact` as a regression-oriented mode for writing platform/build/time-independent
data, and exposes DNxHR LB as a DNxHD-family encoder profile. The package still pins one exact FFmpeg
build and validates duplicate clean runs.

The exact CLI token sequence is written to generator.lock.json after implementation validation.

No generator implementation may silently:

- change to H.264/H.265
- change to ProRes
- change DNxHR profile
- change raster/fps
- use hardware acceleration
- use an alternate pixel format

## Deterministic audio source algorithm

### PCM domain

For every audio-bearing role:

- sample rate = 48000
- channels = 2
- sample format = signed 24-bit integer
- samples/channel = 1,440,000
- duration = exactly 30 seconds
- little-endian serialized PCM for canonical WAV/intermediate essence

No floating-point trig functions are used.

### Frequency table

- ALPHA: left 440 Hz, right 880 Hz
- BETA: left 500 Hz, right 1000 Hz
- GAMMA: left 600 Hz, right 1200 Hz
- REPEAT: left 700 Hz, right 1400 Hz
- AUDIO_ONLY: left 800 Hz, right 1600 Hz

### Integer triangle oscillator

For sample index n, channel frequency f and sample rate SR=48000:

```text
phase = (n * f) % SR
```

Map one cycle to a signed integer triangle wave using integer arithmetic only:

```text
if phase < SR/4:
    unit_num = 4 * phase
    signed = +(A * unit_num) // SR
elif phase < 3*SR/4:
    signed = A * (2*SR - 4*phase) // SR
else:
    signed = A * (-4*SR + 4*phase) // SR
```

Implementation must freeze the exact integer-operation order in tests. Do not replace it with
mathematically equivalent floating-point code.

### Amplitude envelope

Use exact integer peak amplitudes:

- BASE_A = 524288
- ACCENT_A = 2097152

These are comfortably inside signed 24-bit range.

Each whole second starts at an oscillator zero crossing because all chosen frequencies are integer
Hz.

Within each second:

- samples 0..239: linear integer ramp BASE_A -> ACCENT_A
- samples 240..719: ACCENT_A
- samples 720..959: linear integer ramp ACCENT_A -> BASE_A
- samples 960..47999: BASE_A

Use exact floor integer interpolation defined in the recipe implementation.

No dither, normalization, limiter or resampling.

### PCM packing

Clamp only as a defensive assertion; the designed signal must already fit the 24-bit range.

Serialize each signed sample as exactly three little-endian two's-complement bytes.

Interleave L,R,L,R...

Compute SHA-256 of the exact raw interleaved PCM bytes and record as `source_pcm_digest`.

## WAV generation

Temporary/canonical WAV files are written deterministically:

- RIFF/WAVE
- PCM integer
- 2 channels
- 48000 Hz
- 24 bits/sample
- data bytes exactly equal to generated source PCM

ASSET_AUDIO_ONLY's canonical binary is this normalized WAV.

For temporary A/V audio essence, the same deterministic WAV writer is used.

The WAV writer must not add LIST/INFO timestamps or host metadata.

## Final A/V mux

Generate A/V assets in two essence stages:

1. encode video-only DNxHR LB MOV
2. generate deterministic PCM WAV
3. mux the two into final MOV using stream-copy semantics for both essences when accepted by the
   locked FFmpeg/MOV muxer

Required final streams:

- stream 0: DNxHR LB video
- stream 1: 48k/24-bit/stereo PCM audio

If stream-copy PCM-in-MOV is not accepted by the locked toolchain, stop and review the contract.
Do not silently audio-reencode with a different format.

Final mux uses:

- explicit stream mapping
- bitexact mode
- metadata inheritance removed
- normalized deterministic package metadata only
- no chapters
- no attachments
- no additional data streams

ASSET_VIDEO_ONLY stops after normalized video MOV generation and contains exactly one video stream.

## Metadata normalization policy

Authoritative output must not contain uncontrolled host/time/user metadata.

Generator must remove or normalize, where supported:

- creation_time
- modification_time
- absolute source paths
- hostnames
- usernames
- random UUID-like custom tags
- arbitrary comments
- source filenames inherited as title
- non-required language/title metadata

Allowed diagnostic metadata, if written, is static and recipe-versioned only.

If the MOV muxer emits unavoidable build-dependent fields, they are accepted only after the two-run
byte-determinism gate passes on the locked toolchain.

## Structural probe with ffprobe

After each candidate file is created, invoke ffprobe in JSON mode and validate the returned structure
with typed checks.

### Video-bearing asset requirements

- exactly 1 video stream
- A/V assets: exactly 1 audio stream
- VIDEO_ONLY: exactly 0 audio streams
- codec family/name corresponds to DNxHD/DNxHR
- profile corresponds to DNxHR LB
- width = 1280
- height = 720
- pixel format = yuv422p
- progressive field order / no interlace indication
- r_frame_rate = 24/1
- avg_frame_rate = 24/1
- no unexpected streams

### Audio requirements

- codec = pcm_s24le or the exact equivalent codec tag established by the approved toolchain
- sample_rate = 48000
- channels = 2
- no unexpected extra audio stream

### Frame/sample count validation

Do not trust container duration alone.

Validation must decode/count:

- video: exactly 720 readable frames
- audio: exactly 1,440,000 samples per channel

If ffprobe does not expose one count directly, validation may use bounded decode/count tooling.
The exact validated method is locked into generator.lock.json.

## Decode validation

### Video

Decode all video frames with the locked FFmpeg build.

Require:

- zero decode errors
- exactly 720 decoded frames
- raster exactly 1280x720 for every frame

A locked-toolchain decoded raw digest may be recorded for diagnostics, but it is not cross-version
identity authority because codec-decoder implementations may differ.

### Audio

Decode canonical A/V audio to raw signed 24-bit little-endian stereo PCM.

Require exact byte equality with the originally generated source PCM.

This is stronger than duration/metadata checking and must pass for ALPHA/BETA/GAMMA/REPEAT.

For AUDIO_ONLY, parse WAV data and require exact source PCM equality.

## Manifest generation

Only after all six binaries pass structural/decode validation, write manifest.v1.json.

JSON canonicalization:

- UTF-8
- no BOM
- LF line ending
- one trailing LF
- keys sorted lexicographically
- separators exactly `,` and `:` with no insignificant whitespace
- no NaN/Infinity
- integers remain JSON integers
- strings normalized exactly as generator constants; no locale formatting

The implementation may use Python json.dumps with equivalent locked options.

Manifest asset records include actual validated stream properties and source provenance digests, but
do not include the asset file's own SHA-256; binary checksums belong to checksums.sha256.

## generator.lock.json generation

Write with the same canonical JSON rules.

Minimum fields:

- generator contract/version
- generator git commit
- recipe.v1.json SHA-256
- Python version
- NumPy version
- FFmpeg version string
- FFmpeg build/configuration fingerprint
- ffmpeg executable SHA-256 where distributable/accessible
- ffprobe executable SHA-256 where distributable/accessible
- normalized video encode command token array
- normalized final mux command token array
- metadata normalization policy version
- validation method versions

Do not record absolute staging paths in the lock.

## checksums.sha256 generation

After manifest and generator lock exist:

1. compute SHA-256 for manifest.v1.json
2. compute SHA-256 for generator.lock.json
3. compute SHA-256 for each of six final assets
4. sort relative paths lexicographically
5. write lowercase hex + two ASCII spaces + relative POSIX path + LF
6. write no extra comments

Then:

```text
package_digest = SHA256(exact checksums.sha256 bytes)
```

## Clean reproduction gate

A candidate package is not sealable after only one generation.

Required:

### Run A
Generate complete candidate in a fresh empty staging directory.

### Run B
Delete all generated state except the locked source/toolchain and generate again in a second fresh
staging directory.

Compare exact bytes for:

- six final assets
- manifest.v1.json
- generator.lock.json
- checksums.sha256

All must be byte-for-byte equal.

Any difference fails generation and the differing paths are reported.

Do not average, select the newest, or accept "semantically equivalent" files.

This is the generator's own determinism gate; it does not replace Resolve runtime validation.

## Cross-host reproduction

Cross-host or cross-platform byte equality is useful diagnostic evidence but is not required to
approve v1 canonical bytes.

Reason: exact shipped bytes, not universal toolchain reproducibility, define package identity.

If a second host differs:

- retain both diagnostic results;
- do not rewrite the approved package;
- investigate before changing toolchain/package version.

## Failure policy

Any failure produces no published package.

Classes include:

- TOOLCHAIN_UNSUPPORTED
- SOURCE_GENERATION_FAILURE
- ENCODE_FAILURE
- MUX_FAILURE
- STRUCTURE_MISMATCH
- FRAME_COUNT_MISMATCH
- SAMPLE_COUNT_MISMATCH
- AUDIO_DECODE_MISMATCH
- NONDETERMINISTIC_OUTPUT
- MANIFEST_FAILURE
- CHECKSUM_FAILURE
- PACKAGE_VERSION_COLLISION

No failure triggers codec/profile fallback.

## Staging and atomic sealing

Generate only under a new staging directory.

After validation and two-run equality:

1. compute final package_digest
2. verify destination package version does not already exist
3. create immutable sealed package directory/artifact
4. write external approved package-index record
5. mark staging run SEALED

If destination version already exists:

- same digest: do not overwrite; report existing canonical package
- different digest: PACKAGE_VERSION_COLLISION; hard fail

Never mutate a sealed canonical bundle.

## Approved package index

Repository-side small index record should include:

- package_name
- package_version
- package_digest
- asset contract version
- generator contract version
- fixture catalog version
- manifest SHA-256
- generator.lock SHA-256
- six asset SHA-256 values
- publication reference
- approval evidence / PR or gate ref

Do not add this record until actual binaries exist.

## Implementation test levels

### Unit

No FFmpeg required:

- glyph rendering
- exact frame source bytes for selected frames
- integer oscillator sample vectors
- 24-bit packing
- canonical JSON serialization
- checksum formatting
- package digest calculation
- failure-state derivation

### Toolchain integration

FFmpeg required, no Resolve:

- preflight
- encode one short sample
- mux
- ffprobe structural validation
- audio exact decode comparison
- duplicate clean generation byte equality

### Full canonical generation

Generate all six 30-second assets, validate and produce package candidate.

### Resolve qualification

Separate later gate under TASK-020/TASK-021:

- import
- stream/property observation
- canonical fixture materialization
- read stability

The generator cannot self-approve Resolve support.

## Security / containment

Generator accepts no arbitrary shell fragments from LLM/user text.

FFmpeg commands are built from typed/constant token arrays.

Output path must be under the explicitly selected staging root.

Refuse path traversal or existing sealed destination mutation.

No network access is needed during generation.

## Relationship to OPEN-021

ADR-037 fixes:

- source pixel algorithm
- source PCM algorithm
- toolchain locking
- encoding/mux semantics
- validation gates
- deterministic double-generation gate
- manifest/checksum/package digest algorithm
- publish/immutability behavior

OPEN-021 remains open only for the actual first implementation/generation/approval:

- generator code not yet implemented
- exact FFmpeg build not yet selected/locked
- six binary assets do not yet exist
- first SHA-256 values/package_digest do not yet exist
- Resolve import/read qualification has not occurred

## Final principle

> Generate from integer-defined signals, lock every external tool, validate the decoded result,
> reproduce the package twice, and trust only the exact approved bytes.
