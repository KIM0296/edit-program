# Canonical Fixture Asset Package v1

Status: **ACCEPTED — Chat Product/Architecture baseline**

## Purpose

Define the exact media characteristics, deterministic diagnostic patterns, packaging, hashing and
versioning rules for the synthetic canonical assets referenced by ADR-034 Probe Fixture Catalog v1.

These assets exist to make Resolve adapter behavior easy to attribute. They are not editorial-quality
evaluation footage.

## Design priorities

In order:

1. deterministic frame/sample structure
2. frame-accurate intra-frame decode behavior
3. cross-platform Resolve readability
4. easy manual diagnosis
5. modest package size
6. visual/audio quality

Long-GOP delivery codecs are intentionally avoided for the canonical v1 probe package.

## Common video profile

All video-bearing assets use:

- raster: **1280 × 720**
- frame rate: **24/1 fps**
- scan: progressive
- sample aspect ratio: 1:1
- constant frame rate
- duration: **720 frames / 30.000 seconds**
- codec: **Avid DNxHR LB**
- bit depth / pixel family: 8-bit YUV 4:2:2 candidate encoding
- container: **QuickTime MOV**
- nominal color tags: BT.709 primaries / transfer / matrix, limited-range where the encoder exposes
  the fields consistently
- no alpha
- no variable frame rate
- no embedded timecode dependency for identity

The generated file must be validated against the exact installed Resolve RuntimeProfile before this
profile is considered runtime-supported.

Why DNxHR LB:

- intra-frame behavior is preferred over H.264/H.265 GOP behavior for source/frame probes;
- Resolve supports DNxHR decoding on its desktop platforms;
- LB keeps the fixture bundle materially smaller than higher-bitrate mastering profiles;
- image quality is not the test objective.

Codec choice is package policy, not production-media policy.

## Common audio profile

Audio-bearing assets use:

- sample rate: **48,000 Hz**
- sample format: **24-bit Linear PCM**
- channel layout: **stereo 2.0**
- duration: **1,440,000 samples / 30.000 seconds**
- no loudness normalization
- no lossy audio codec
- peak level kept below clipping

For A/V assets the PCM stream is embedded in the MOV container.

ASSET_AUDIO_ONLY uses a standalone WAV container with the same 48 kHz / 24-bit / stereo semantic
profile.

The exact native codec tag/endian representation written by the canonical generator is recorded in
the package manifest/toolchain evidence and validated by checksum; the semantic contract is 24-bit
Linear PCM stereo.

## Asset inventory

| Asset role | Media type | Video | Audio | Duration |
| --- | --- | --- | --- | --- |
| ASSET_ALPHA | A/V | DNxHR LB 720p24 | PCM stereo | 720 frames |
| ASSET_BETA | A/V | DNxHR LB 720p24 | PCM stereo | 720 frames |
| ASSET_GAMMA | A/V | DNxHR LB 720p24 | PCM stereo | 720 frames |
| ASSET_REPEAT | A/V | DNxHR LB 720p24 | PCM stereo | 720 frames |
| ASSET_VIDEO_ONLY | video only | DNxHR LB 720p24 | none | 720 frames |
| ASSET_AUDIO_ONLY | audio only | none | PCM stereo WAV | 30.000 s |

ASSET_REPEAT is one exact binary asset reused wherever repeated-media behavior is required. Do not
generate per-fixture copies with different metadata.

## Deterministic video diagnostic pattern

Every frame-bearing asset is generated from a deterministic synthetic frame generator.

The generator must not depend on system fonts.

Each frame contains:

1. an asset-specific background field;
2. a fixed asset-role code rendered with a generator-embedded bitmap/segment glyph set;
3. a zero-padded source-frame counter from 0000 through 0719;
4. a frame-within-second indicator from 00 through 23;
5. a moving vertical diagnostic bar whose x-position is a deterministic function of source-frame
   index;
6. fixed edge/border geometry to make accidental scaling/cropping visually obvious.

The frame counter is diagnostic only. It does not become identity authority for production
TimelineItems.

Suggested role background values in generator RGB space:

- ASSET_ALPHA: (32, 96, 160)
- ASSET_BETA: (160, 96, 32)
- ASSET_GAMMA: (112, 48, 160)
- ASSET_REPEAT: (96, 96, 96)
- ASSET_VIDEO_ONLY: (32, 128, 64)

Exact encoded/decoded pixel values are not a fixture verification invariant. Media bytes/content
hashes and timeline/source geometry are authoritative; the visual pattern exists for diagnosis.

## Deterministic audio diagnostic pattern

A/V and audio-only assets use deterministic, non-clipping stereo tone patterns.

Base tones:

| Asset | Left | Right |
| --- | ---: | ---: |
| ASSET_ALPHA | 440 Hz | 880 Hz |
| ASSET_BETA | 500 Hz | 1000 Hz |
| ASSET_GAMMA | 600 Hz | 1200 Hz |
| ASSET_REPEAT | 700 Hz | 1400 Hz |
| ASSET_AUDIO_ONLY | 800 Hz | 1600 Hz |

Recommended envelope:

- base level approximately -24 dBFS;
- a deterministic short sync-accent window at each whole-second boundary, peaking approximately
  -12 dBFS;
- short deterministic ramps around the accent to avoid accidental full-scale clicks.

The exact sample algorithm is versioned in the generator recipe. Runtime tests do not identify media
by measured tone frequency.

## File naming

Human-readable default names may be:

- alpha_v1.mov
- beta_v1.mov
- gamma_v1.mov
- repeat_v1.mov
- video_only_v1.mov
- audio_only_v1.wav

Filename is never asset identity.

The authoritative semantic asset IDs are:

- canonical:ASSET_ALPHA:v1
- canonical:ASSET_BETA:v1
- canonical:ASSET_GAMMA:v1
- canonical:ASSET_REPEAT:v1
- canonical:ASSET_VIDEO_ONLY:v1
- canonical:ASSET_AUDIO_ONLY:v1

## Package layout

The authoritative bundle contains only machine-relevant files:

```text
canonical-fixture-assets-v1/
├─ manifest.v1.json
├─ generator.lock.json
├─ checksums.sha256
└─ assets/
   ├─ alpha_v1.mov
   ├─ beta_v1.mov
   ├─ gamma_v1.mov
   ├─ repeat_v1.mov
   ├─ video_only_v1.mov
   └─ audio_only_v1.wav
```

Human documentation belongs in the repository, not inside the checksum-authoritative bundle.

## manifest.v1.json

The manifest records semantic expectations, not self-referential file hashes.

Minimum fields:

- contract_version
- package_name
- package_version
- fixture_catalog_version
- video_profile
- audio_profile
- asset records

Each asset record contains at least:

- asset_id
- role
- asset_revision
- relative_path
- media_kind
- expected duration frames and/or samples
- expected stream count
- expected video codec family/profile where applicable
- expected frame rate/raster where applicable
- expected audio sample rate/bit depth/channel count where applicable
- diagnostic_pattern_version
- checksum algorithm reference

Do not store a package hash inside the manifest itself.

## generator.lock.json

Generation provenance is separate from media identity.

Record at least:

- generator_name
- generator_version
- generator source revision / commit
- recipe_version
- Python/runtime version if used
- FFmpeg version
- libavcodec/libavformat build identifiers where available
- exact encoding arguments or normalized command recipe
- metadata normalization policy
- generation host platform for provenance only

The generator lock is included in package checksums.

## Metadata normalization

The canonical generator should minimize nondeterministic container metadata.

Where tooling permits:

- omit or normalize creation timestamps;
- omit arbitrary host/user paths;
- omit random UUID metadata;
- avoid system-font references;
- normalize language/title/comment tags;
- use explicit stream order;
- use deterministic asset-role metadata only when useful for diagnosis.

Embedded metadata is not identity authority even when deterministic.

## checksums.sha256

SHA-256 is the canonical binary integrity algorithm.

The checksum file contains the SHA-256 of:

- manifest.v1.json
- generator.lock.json
- every asset binary

Rules:

- paths are relative POSIX-style paths;
- entries sorted lexicographically by path;
- lowercase hexadecimal digest;
- UTF-8 text;
- LF line endings;
- checksums.sha256 does not hash itself.

The bundle's **package_digest** is:

```text
SHA256(exact bytes of checksums.sha256)
```

This avoids a self-referential package hash.

## Canonical identity rule

For v1:

> the shipped binary bytes are canonical; the generation recipe is provenance.

A locally regenerated file is not assumed identical merely because it uses the same recipe.

If regenerated bytes differ:

- do not silently replace the canonical file;
- create a new asset revision/package version;
- produce new checksums and package_digest;
- re-run the relevant TASK-020/021 validation.

## Versioning

Use semantic package versioning:

- MAJOR: incompatible fixture-media contract change
- MINOR: additive asset/profile expansion that does not alter existing canonical bytes/meaning
- PATCH: corrected canonical bytes/metadata or manifest/toolchain changes requiring a new bundle
  digest without changing the high-level fixture catalog semantics

Any authoritative asset-byte change requires a new package version or asset revision.

Never overwrite an already-published canonical bundle in place.

## Distribution

Do not store large canonical media as ordinary Git blobs.

Preferred v1 distribution:

- repository contains contract, generator source and expected package index;
- canonical binary bundle is published as a versioned release/artifact;
- installation/validation explicitly materializes the bundle to a local package directory;
- TASK-021 consumes a local verified package path.

Ordinary editing requests never download or regenerate canonical assets.

No hidden network dependency is allowed in the runtime editing path.

## TASK-021 validation sequence

Before import/materialization:

1. load manifest;
2. verify contract/package version;
3. verify checksums.sha256 formatting;
4. hash manifest, generator lock and every asset;
5. compute package_digest;
6. compare package_digest with the approved package index;
7. inspect required media stream properties;
8. reject missing/extra/hash-mismatched authoritative files;
9. only then allow typed materialization steps.

A correct filename with a wrong hash is invalid.

A correct hash with an unexpected required stream layout is also invalid.

## Runtime package index

The repository should contain a small approved package index after the binary package is first
generated.

Suggested record:

- package_name
- package_version
- package_digest
- fixture_catalog_version
- generator_recipe_version
- approved RuntimeProfile scope if/when validated
- release/artifact reference

The digest is unknown until actual canonical binaries are generated. Do not invent it in this ADR.

## Unit-test boundary

Normal Python unit/CI tests should not require downloading the full binary media package.

Unit tests may use:

- tiny fake byte files
- synthetic manifest/checksum records
- hash mismatch fixtures

Actual Resolve read/materialization qualification uses the full canonical package.

## Relationship to real footage

Real editorial footage remains completely separate.

Canonical package:

- adapter determinism
- source/timeline geometry
- media identity observations
- repeated-media behavior
- track/marker/subtitle fixture mechanics

Real footage:

- Pause/Dialogue quality
- semantic ambiguity
- natural pacing
- false-remove/over-tighten rates
- editor correction/review time
- Net Editing Time Saved

## Accepted v1 values

- 1280×720
- 24/1 fps progressive
- 720 frames / 30 s
- MOV + DNxHR LB for video-bearing assets
- 48 kHz / 24-bit / stereo Linear PCM
- WAV for audio-only asset
- SHA-256 exact-byte asset/package integrity
- package_digest = SHA256(checksums.sha256)
- exact shipped bytes are canonical
- no runtime regeneration
- no filename identity
- no ordinary-editor-path network download

## Final principle

> A canonical probe asset should be visually obvious to a human, boring to a decoder, immutable to
> the harness, and identifiable by exact bytes rather than by a convenient filename.


## Generator contract binding

ADR-037 / `docs/CANONICAL_ASSET_GENERATOR_CONTRACT.md` is authoritative for producing the actual
six canonical binaries.

Key requirements:

- integer-defined video and PCM source algorithms
- pinned Python/NumPy/FFmpeg/ffprobe toolchain
- software DNxHR LB encoding only
- bitexact mode + metadata normalization
- structural probe and full decode validation
- exact PCM decode equality
- two independent fresh generation runs with byte-for-byte package equality
- no fallback codec/profile/raster/fps
- immutable sealed package publication

The package contract still treats exact approved shipped bytes as canonical identity.
