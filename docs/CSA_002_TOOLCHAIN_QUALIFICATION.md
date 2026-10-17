# CSA-002 — Pinned FFmpeg/ffprobe Synthetic Qualification

Status: **CI_REFERENCE_TOOLCHAIN_SYNTHETIC_QUALIFIED / G2–G7 HOLD**.

## Base

- Repository: KIM0296/edit-program
- Authoritative main: `7949c8b7fcb1a17fa612a6cd4279de6f3b245031`
- Main tree: `283b5c248d3bbcb0f2c9faba98bbf2d4a6fe5951`
- Main CI: Domain safety CI `38696421293` — SUCCESS
- CSA-001 / PR #61 is merged into this base.

## Purpose

CSA-002 proves that a specifically pinned FFmpeg/ffprobe toolchain can decode one
fixed synthetic AAC-LC 48 kHz fixture deterministically under the CSA-001 command
contract.

This is **not** a real-media qualification. It is a host/toolchain known-answer
qualification harness.

## Reference environment

The first execution target is intentionally a disposable GitHub-hosted Ubuntu
runner. The reference package is:

`ffmpeg 7:6.1.1-3ubuntu5`

The receipt pins:

- FFmpeg executable SHA-256;
- ffprobe executable SHA-256;
- complete `-version` output digest;
- `-buildconf` output digest;
- hashes of the eight FFmpeg core linked libraries;
- exact probe/decode argument contracts;
- fixed synthetic compressed-source and expected PCM digests/counts.

Pinning only the eight FFmpeg core libraries is deliberate. An earlier probe
attempted to bind all 214 transitive system libraries and proved too broad for a
decoder-toolchain identity: unrelated hosted-runner dependencies changed while
the exact FFmpeg package/binaries stayed pinned. The narrowed set is the bounded
FFmpeg runtime surface for this reference receipt.

## Synthetic fixture

The fixture is generated data only, then frozen as base64 bytes in Git:

- AAC-LC
- 48,000 Hz
- stereo
- one audio stream
- no user/project content

Known reference facts from the initial probe:

- compressed SHA-256:
  `ead1fe9beaff5010eaf4b9adde660b389dc8d90dd422ab2b0124874d4795e12a`
- compressed bytes: 6,819
- decoded PCM SHA-256:
  `39dc39bef5e87dd3e8b324257899f44bfaf7f5c54db9829873dcbfc6c01d1c47`
- PCM bytes: 49,152
- sample frames: 12,288
- second decode: byte-identical

## Fail-closed verification

The final runner requires all of the following:

1. exact ffmpeg and ffprobe binary pins;
2. exact version/build-configuration digests;
3. exact FFmpeg core-library hashes;
4. exact fixed compressed fixture SHA/size;
5. exactly one AAC-LC 48 kHz stereo audio stream;
6. exact global stream index;
7. exact no-seek/no-resample/no-downmix PCM16LE decode command;
8. two independent subprocess decodes of the fixed fixture;
9. byte-identical outputs;
10. exact expected PCM SHA, bytes and sample-frame count.

Any mismatch fails qualification.

## Development receipts

The failures are retained as evidence, not erased:

- CI `38696746802`: **FFMPEG_NOT_FOUND**. The stock `ubuntu-latest` runner did
  not provide ffmpeg on PATH. This established that a toolchain must be explicitly
  provisioned rather than assumed.
- A later temporary branch-only CI step installed exact package
  `ffmpeg=7:6.1.1-3ubuntu5` and produced the initial synthetic probe receipt.
- CI `38697183890`: verification with all transitive `ldd` libraries pinned
  failed with **FFMPEG_LIBRARIES_DRIFT**. The scope was narrowed to the eight
  FFmpeg core libraries; no tolerance or convenient result selection was used.
- CI `38697325137`: the narrowed pin and known-answer qualification step
  succeeded, but repository Ruff then found three style diagnostics in the new
  runner. Qualification evidence was not promoted from that failed full CI run.
  The style defects were corrected without weakening the qualification checks.

Final CI reference qualification receipt:

- qualified head: `e14e5e2dd2fdd9e771bbb9ad02820f23c9a2b193`
- workflow run: `38698069106`
- job: `116299281802`
- qualification result: `CI_REFERENCE_TOOLCHAIN_SYNTHETIC_QUALIFIED`
- scope: `GITHUB_HOSTED_UBUNTU_REFERENCE_ONLY`
- receipt SHA-256:
  `38f844c392bf4a5f5fab5f703536579c4fb9a443b901aaff38d846ff6c27b7ec`
- ffmpeg SHA-256:
  `ed16af623947494a72e284b6eb8ff225f2da22b38b5d5069c2fd4b4ba3384e41`
- ffprobe SHA-256:
  `272f6ebc634a63d9c8b4ca68e964119d980f25154e5aa2c35e5487da48e9a58f`
- synthetic fixture SHA-256:
  `ead1fe9beaff5010eaf4b9adde660b389dc8d90dd422ab2b0124874d4795e12a`
- PCM SHA-256:
  `39dc39bef5e87dd3e8b324257899f44bfaf7f5c54db9829873dcbfc6c01d1c47`
- PCM bytes / sample frames: `49152 / 12288`
- second decode: byte-identical
- full pytest: `2120 passed / 1 existing skip`
- Ruff: PASS
- repository mypy: PASS
- explicit strict mypy on tool + test: PASS (2 files)
- `g2_authorized=false`
- `windows_host_qualified=false`

The temporary branch-only CI provisioning/qualification steps are intentionally
removed from the final PR diff. The committed runner, synthetic fixture, receipt,
tests and status remain; ordinary repository CI therefore does not depend on
apt/FFmpeg availability or silently requalify a changed hosted runner.

## Chat Gate P1 corrections (after reviewed head `100821cf`)

The Chat Gate returned `CHANGES_REQUIRED` with two P1 blockers. Both are closed
in the runner without changing the receipt, fixture or known-answer values.

### P1-1 — receipt is evidence, not authority

- `APPROVED_RECEIPT_SHA256` (trusted code) fixes the canonical receipt digest
  `38f844c3…b7ec`. `load_receipt()` refuses any receipt whose digest differs
  (`RECEIPT_DIGEST_NOT_APPROVED`) **before** any substantive field is consumed.
  Duplicate JSON keys and non-finite numbers are refused at parse time.
- Independently of the digest, `validate_receipt_contract()` re-checks the
  receipt against code constants: exact key sets, type-strict values (no
  bool/int or int/float aliasing), Linux reference environment/scope, approved
  ffmpeg/ffprobe path+SHA-256, synthetic fixture pin, known-answer PCM
  SHA/bytes/frames, and the exact probe/decode argument contracts including
  placeholder count, order and position plus a forbidden-flag list.
- `verify()` materializes commands and known answers from the code constants,
  checks the committed fixture against the code-side pin, and refuses a
  non-Linux host (`HOST_PLATFORM_NOT_LINUX_REFERENCE`) before locating any tool.

### P1-2 — no unapproved binary is executed

Order is now: locate → resolve → read/hash bytes → compare approved path and
SHA-256 for **both** ffmpeg and ffprobe → stop if either fails. Only then are
`-version`, `-buildconf` and `ldd` run, the remaining pins compared, and the
synthetic decode performed. Binary bytes are re-hashed after the decode to
detect replacement during the run.

Every subprocess goes through `run_controlled()`: explicit
`PATH=/usr/bin:/bin`, `LC_ALL=C`, `LANG=C`, no other inherited variables,
`stdin=DEVNULL`, non-zero exit fails. `ldd` is invoked by absolute path.

Residual limit: a binary swapped between the hash and its execution (TOCTOU) is
not prevented, only detected afterwards by the post-run re-hash.

### Regressions added

Receipt: filter flag, resample/downmix/seek flags, unlisted argument drift,
malformed placeholder count/order/position, non-string tokens, receipt+fixture
modified together, known-answer PCM SHA/bytes/frames/type change, non-Linux
environment, rebound binary pin, extra/duplicate keys, non-Linux host.

Binary: PATH-hijacked ffmpeg, changed ffmpeg bytes at the approved path, valid
ffmpeg + changed ffprobe, ffprobe-only hijack, missing tool — all with zero
subprocess calls; approved bytes with version/build/library drift are inspected
then rejected without touching ffprobe; post-run byte swap is detected; the
controlled subprocess environment is asserted.

### Evidence status of the corrected head

The Linux reference qualification run above (`38698069106`) was produced by the
**previous** runner on head `e14e5e2`. The corrected runner changes the
subprocess environment and the `ldd` invocation path; the pinned values are
unchanged. Ordinary repository CI does not run FFmpeg.

Decision: the Ubuntu end-to-end re-run for the corrected head is **not
performed and not required**. The Linux reference receipt never contributes to
G2; only a separately pinned Windows host receipt can. Re-qualifying a
disposable hosted runner would add no gate evidence. Consequences:

- `38698069106` is retained as **historical** evidence of the previous runner
  only; it is not evidence for the corrected head.
- Whether the corrected runner reproduces the Linux reference result is
  `UNKNOWN` and stays `UNKNOWN`; it must not be claimed either way.
- The corrected runner's first real end-to-end use is the Windows host
  qualification, which requires its own Windows receipt, its own approved
  digest and Windows-specific inspection (no `ldd`; DLL pins instead).

## Qualification language

A successful run may claim only:

`CI_REFERENCE_TOOLCHAIN_SYNTHETIC_QUALIFIED`

It must also state:

- scope = `GITHUB_HOSTED_UBUNTU_REFERENCE_ONLY`
- `g2_authorized=false`
- `windows_host_qualified=false`

It does **not** imply:

- Windows toolchain qualification;
- real media acquisition qualification;
- permission/session authenticity;
- REAL_MEDIA_PRODUCER_QUALIFIED;
- NATIVE_READ_QUALIFIED;
- NATIVE_MUTATION_QUALIFIED;
- EDITOR_QUALITY_QUALIFIED;
- VERIFIED_LIVE.

## Next gate

After this CI reference harness is Chat Gate approved and merged, the same
known-answer principle must be applied to the actual Windows acquisition host
with a separately pinned Windows FFmpeg/ffprobe distribution.

Only the **Windows host qualification receipt**, plus the existing
source/session/permission prerequisites, can contribute to opening G2.

G2–G7 remain HOLD throughout CSA-002.
